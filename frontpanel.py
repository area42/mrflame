#
# modified from thread/processor written by Dorian Wiskow - Janaury 2021
#
import sys

if sys.implementation.name != "micropython":
    from typing import Dict, Optional, Union, Any, Tuple

from time import sleep_ms  # type: ignore
from machine import Pin, Timer, ADC  # type: ignore
from sys import stdin
import uresponsivevalue

import uselect  # type: ignore
from neopixel import Neopixel

# ---------------------------------- timer ---------------------------------- #
_ts: int = 0


def ts_tick():
    global _ts
    _ts = _ts + 1


ts_timer = Timer(period=1, mode=Timer.PERIODIC, callback=lambda t: ts_tick())


def ts() -> int:
    return _ts


# --------------------------------- globals --------------------------------- #
bufferSize = 1024  # size of circular buffer to allocate
buffer = [" "] * bufferSize  # circuolar incomming USB serial data buffer (pre fill)
bufferEcho = True  # USB serial port echo incooming characters (True/False)
bufferNextIn, bufferNextOut = (
    0,
    0,
)  # pointers to next in/out character in circualr buffer
terminateThread = False  # tell 'processIO' function to terminate (True/False)

# global track changes
fp_changed = True

button_matrix = [
    ["lmi", "f8", "f16"],
    ["len", "f7", "f15"],
    ["s4", "f5", "f13"],
    ["s5", "f6", "f14"],
    ["s3", "f4", "f12"],
    ["s2", "f3", "f11"],
    ["sst", "f1", "f9"],
    ["s1", "f2", "f10"],
]


button_state = {}
mode_keys = {}
lmode_keys = {}
seq_keys = {}
flame_buttons = {}
overall_mode = "s1"
learn_mode = None
sequencer_state = False

flame_cnt = 16
flame_names = []
flame_name_pixel_map = {}
for flame in range(flame_cnt):
    flame_name = f"f{flame+1}"
    flame_names.append(flame_name)
    flame_name_pixel_map[flame_name] = flame 

mode_map = {
    "s1" : "off",
    "s2" : "learn",
    "s3" : "test",
    "s4" : "live",
    "s5" : "livelearn"
}

# -------------------------------- setup ADC -------------------------------- #
activity_threshold = 1000
snap_multiplier=0.1
max_value=65535

hold_time_out_min = 0
hold_time_out_max = 1000 # ms
hold_time_out_factor = (hold_time_out_max-hold_time_out_min)/max_value
hold_time: int = -1
hold_time_adc = ADC(Pin(26))
hold_time_reader = uresponsivevalue.ResponsiveValue(
    hold_time_adc.read_u16, max_value=max_value, activity_threshold=activity_threshold, snap_multiplier=snap_multiplier
)

max_time_out_min = 0
max_time_out_max = 2000 # ms
max_time_out_factor = (max_time_out_max-max_time_out_min)/max_value
max_time: int = -1
max_time_adc = ADC(Pin(27))
max_time_reader = uresponsivevalue.ResponsiveValue(
    max_time_adc.read_u16, max_value=max_value, activity_threshold=activity_threshold, snap_multiplier=snap_multiplier
)

sequencer_speed_out_min = 10
sequencer_speed_out_max = 360 # fpm
sequencer_speed_out_factor = (sequencer_speed_out_max-sequencer_speed_out_min)/max_value
sequencer_speed: int = -1
sequencer_speed_adc = ADC(Pin(28))
sequencer_speed_reader = uresponsivevalue.ResponsiveValue(
    sequencer_speed_adc.read_u16, max_value=max_value, activity_threshold=activity_threshold, snap_multiplier=snap_multiplier
)

# ----------------------------- poller interface ---------------------------- #
spoll = uselect.poll()
spoll.register(stdin, uselect.POLLIN)

# -------------------------- Prep dicts and states -------------------------- #
key_rows = range(len(button_matrix))
key_cols = range(len(button_matrix[0]))
key_debouncer_timer: Dict[str, int] = {}
key_debouncer_state: Dict[str, Optional[bool]] = {}

for row in key_rows:
    for col in key_cols:
        key = button_matrix[row][col]

        button_state[key] = False
        key_debouncer_state[key] = None
        key_debouncer_timer[key] = 0

        if key.startswith("f"):
            flame_buttons[key] = False
        elif key.startswith("sst"):
            seq_keys[key] = False
        elif key.startswith("s"):
            mode_keys[key] = key
        elif key.startswith("l"):
            lmode_keys[key] = key

STABLE_TIME = 10  # ms

col_pins = [13, 14, 15]
row_pins = [0, 1, 2, 3, 4, 5, 6, 7]

col_gpio = []
for pin in col_pins:
    col_gpio.append(Pin(pin, Pin.OUT, value=0))

row_gpio = []
for pin in row_pins:
    row_gpio.append(Pin(pin, Pin.IN, Pin.PULL_UP))

# ------------------------------- setup pixels ------------------------------ #
numpix = 17
pixels = Neopixel(numpix, 0, 22, "RGB")

seq_blink_timer = Timer()    # just allocate

colorTable: Dict[str,Tuple]= {
    "off" : (0,0,0),
    "red" : (255,0,0),
    "green" : (0,255,0),
    "orange" : (196,50,0),  
    "white": (255,255,255),
    "blue" :(0,0,255),
}

pixels.brightness(255)
pixels.fill(colorTable["off"])
pixels.show()

# --------------------------------------------------------------------------- #
#                              main IO processor                              #
# --------------------------------------------------------------------------- #
def processIO():
    """_summary_

    Raises:

    Returns:
        _type_: _description_

    Side Effects:
        None
    """
    global buffer, bufferSize, bufferEcho, bufferNextIn, terminateThread, button_matrix, button_state, flame_buttons, mode_keys, lmode_keys, overall_mode, learn_mode, seq_keys, sequencer_state
    global key_debouncer_state, key_debouncer_timer, fp_changed

    def readpoll():
        return stdin.read(1) if spoll.poll(0) else None

    def read_input():
        global buffer, bufferNextIn
        pending_char = readpoll()
        if pending_char is not None:
            buffer[
                bufferNextIn
            ] = pending_char  # wait for/store next byte from USB serial
            if bufferEcho:  # if echo is True ...
                print(buffer[bufferNextIn], end="")  #    ... output byte to USB serial
            bufferNextIn += 1  # bump pointer
            if bufferNextIn == bufferSize:  # ... and wrap, if necessary
                bufferNextIn = 0

    def scan_keys():
        global sequencer_state, learn_mode, overall_mode, flame_buttons, button_state, key_debouncer_state, key_debouncer_timer
        global fp_changed

        for col in key_cols:
            col_gpio[col].low()
            for row in key_rows:
                key = button_matrix[row][col]
                new_state = row_gpio[row].value() == 0

                # debounce keys
                if key_debouncer_state[key] == new_state:
                    if key_debouncer_timer[key] < STABLE_TIME:
                        key_debouncer_timer[key] += 1
                        continue
                else:
                    key_debouncer_timer[key] = 0
                    key_debouncer_state[key] = new_state
                    continue

                if button_state[key] != new_state:
                    fp_changed = True
                    button_state[key] = new_state
                    if key in flame_buttons:
                        flame_buttons[key] = new_state
                    elif key in mode_keys and new_state:
                        overall_mode = key
                    elif key in lmode_keys and new_state:
                        learn_mode = key
                    elif key in seq_keys and new_state:
                        sequencer_state = not sequencer_state

            col_gpio[col].high()
            if not any([button_state[lmode_key] for lmode_key in lmode_keys]):
                learn_mode = None

    def update_adc():
        global hold_time_reader, max_time_reader, sequencer_speed_reader, fp_changed

        hold_time_reader.update()
        max_time_reader.update()
        sequencer_speed_reader.update()
        fp_changed = (
            fp_changed
            or hold_time_reader.has_changed
            or max_time_reader.has_changed
            or sequencer_speed_reader.has_changed
        )

    if terminateThread:  # if requested by main thread ...
        return  #    ... exit loop
    scan_keys()
    read_input()
    update_adc()


#
# function to check if a byte is available in the buffer and if so, return it
#
def getByteBuffer():
    global buffer, bufferSize, bufferNextOut, bufferNextIn

    if bufferNextOut == bufferNextIn:  # if no unclaimed byte in buffer ...
        return ""  #    ... return a null string
    n = bufferNextOut  # save current pointer
    bufferNextOut += 1  # bump pointer
    if bufferNextOut == bufferSize:  #    ... wrap, if necessary
        bufferNextOut = 0
    return buffer[n]  # return byte from buffer


#
# function to check if a line is available in the buffer and if so return it
# otherwise return a null string
#
# NOTE 1: a line is one or more bytes with the last byte being LF (\x0a)
#      2: a line containing only a single LF byte will also return a null string
#
def getLineBuffer():
    global buffer, bufferSize, bufferNextOut, bufferNextIn

    if bufferNextOut == bufferNextIn:  # if no unclaimed byte in buffer ...
        return ""  #    ... RETURN a null string

    n = bufferNextOut  # search for a LF in unclaimed bytes
    while n != bufferNextIn:
        if buffer[n] == "\x0a":  # if a LF found ...
            break  #    ... exit loop ('n' pointing to LF)
        n += 1  # bump pointer
        if n == bufferSize:  #    ... wrap, if necessary
            n = 0
    if n == bufferNextIn:  # if no LF found ...
        return ""  #    ... RETURN a null string

    line = ""  # LF found in unclaimed bytes at pointer 'n'
    n += 1  # bump pointer past LF
    if n == bufferSize:  #    ... wrap, if necessary
        n = 0

    while bufferNextOut != n:  # BUILD line to RETURN until LF pointer 'n' hit

        if buffer[bufferNextOut] == "\x0d":  # if byte is CR
            bufferNextOut += 1  #    bump pointer
            if bufferNextOut == bufferSize:  #    ... wrap, if necessary
                bufferNextOut = 0
            continue  #    ignore (strip) any CR (\x0d) bytes

        if buffer[bufferNextOut] == "\x0a":  # if current byte is LF ...
            bufferNextOut += 1  #    bump pointer
            if bufferNextOut == bufferSize:  #    ... wrap, if necessary
                bufferNextOut = 0
            break  #    and exit loop, ignoring (i.e. strip) LF byte
        line = line + buffer[bufferNextOut]  # add byte to line
        bufferNextOut += 1  # bump pointer
        if bufferNextOut == bufferSize:  #    wrap, if necessary
            bufferNextOut = 0
    return line  # RETURN unclaimed line of input


def getButtonState(key: str) -> bool:
    global button_state
    return button_state.get(key, False)


def getFlameButtonState() -> dict:
    global flame_buttons
    return flame_buttons.copy()

def getFlamesNames() -> list:
    global flame_names
    return flame_names

def getMode() -> str:
    global overall_mode
    
    return mode_map[overall_mode]


def getLearnMode() -> Optional[str]:
    global learn_mode
    return learn_mode


def getSeqState() -> bool:
    global sequencer_state
    return sequencer_state


def StartSeqState() -> bool:
    global sequencer_state
    cur_state = sequencer_state
    sequencer_state = True
    return cur_state


def StopSeqState() -> bool:
    global sequencer_state
    cur_state = sequencer_state
    sequencer_state = False
    return cur_state


def getHoldTime() -> int:
    
    return int(hold_time_out_min + (max_value - hold_time_reader.responsive_value) * hold_time_out_factor  )


def getMaxTime() -> int:
    return int(max_time_out_min + (max_value - max_time_reader.responsive_value) * max_time_out_factor  )


def getSeqSpeed() -> int:
    return int(sequencer_speed_out_min + (max_value - sequencer_speed_reader.responsive_value) * sequencer_speed_out_factor  )


def fpChanged() -> bool:
    """has anything changed in the FP settings since last fpChanged()

    Raises:

    Returns:
        bool: True
            first call and
            if a button or setting has changed since last fpChanged

    Side Effects:
        reset fp_changed to false
    """
    global fp_changed
    if fp_changed:
        fp_changed = False
        return True
    return False

def allFlameLeds(color):
    global pixels
    
    pixels.set_pixel_line(0,15,colorTable[color])
    pixels.show()
    
def setFlameLed(flame, color):
    global pixels, flame_name_pixel_map, colorTable
    
    pixels.set_pixel(flame_name_pixel_map[flame],colorTable[color])
    pixels.show() 
    
def blinkSequenceLed(color):
    global seq_blink_timer
    
    LedState = False
    ct = colorTable[color]
    blinktime=int((60/getSeqSpeed())*1000)
    
    def blink_toggle(color):
        nonlocal LedState
        if LedState:
            pixels.set_pixel(16,color)
        else:
            pixels.set_pixel(16,(0,0,0))
        LedState = not LedState
        pixels.show()    
 
    seq_blink_timer.init(period=blinktime,mode=Timer.PERIODIC,callback=lambda t:blink_toggle(ct))
    