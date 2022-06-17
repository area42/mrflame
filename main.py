#
# USB serial communication for the Raspberry Pi Pico (RD2040) using the second RD2040
# thread/processor (written by Dorian Wiskow - Janaury 2021)
#
from _thread import start_new_thread
from time import sleep_ms   
from machine import Pin
from sys import stdin

#
# global variables to share between both threads/processors
#
bufferSize = 1024  # size of circular buffer to allocate
buffer = [" "] * bufferSize  # circuolar incomming USB serial data buffer (pre fill)
bufferEcho = True  # USB serial port echo incooming characters (True/False)
bufferNextIn, bufferNextOut = (
    0,
    0,
)  # pointers to next in/out character in circualr buffer
terminateThread = False  # tell 'BackgroundProc' function to terminate (True/False)

key_matrix = [
    ["lmi", "f8", "f16"],
    ["len", "f7", "f15"],
    ["s4", "f5", "f13"],
    ["s5", "f6", "f14"],
    ["s3", "f4", "f12"],
    ["s2", "f3", "f11"],
    ["sst", "f1", "f9"],
    ["s1", "f2", "f10"],
]


key_state = {}
mode_keys = {}
lmode_keys = {}
seq_keys = {}
flame_keys = {}

overall_mode = ""
learn_mode = None
sequencer_state = False

print("loaded")

import uselect

spoll = uselect.poll()
spoll.register(stdin, uselect.POLLIN)

key_rows = range(len(key_matrix))
key_cols = range(len(key_matrix[0]))
key_debouncer_timer = {}
key_debouncer_state = {}

for row in key_rows:
    for col in key_cols:
        key = key_matrix[row][col]

        key_state[key] = False
        key_debouncer_state[key] = None
        key_debouncer_timer[key] = 0

        if key.startswith("f"):
            flame_keys[key] = False
        elif key.startswith("sst"):
            seq_keys[key] = False
        elif key.startswith("s"):
            mode_keys[key] = key
        elif key.startswith("l"):
            lmode_keys[key] = key

STABLE_TIME = 20  # ms

col_pins = [13, 14, 15]
row_pins = [0, 1, 2, 3, 4, 5, 6, 7]

col_gpio = []
for pin in col_pins:
    col_gpio.append(Pin(pin, Pin.OUT, value=0))

row_gpio = []
for pin in row_pins:
    row_gpio.append(Pin(pin, Pin.IN, Pin.PULL_UP))

#
# BackgroundProc() function to execute in parallel on second Pico RD2040 thread/processor
#
def BackgroundProc():
    global buffer, bufferSize, bufferEcho, bufferNextIn, terminateThread, key_matrix, key_state, flame_keys, mode_keys, lmode_keys, overall_mode, learn_mode, seq_keys, sequencer_state
    global key_debouncer_state, key_debouncer_timer

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
        global sequencer_state, learn_mode, overall_mode, flame_keys, key_state, key_debouncer_state, key_debouncer_timer

        for col in key_cols:
            col_gpio[col].low()
            for row in key_rows:
                key = key_matrix[row][col]
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

                key_state[key] = new_state
                if key in flame_keys:
                    flame_keys[key] = new_state
                elif key in mode_keys and new_state:
                    overall_mode = key
                elif key in lmode_keys and new_state:
                    learn_mode = key
                elif key in seq_keys and new_state:
                    sequencer_state = not sequencer_state
            col_gpio[col].high()
            if not any([key_state[lmode_key] for lmode_key in lmode_keys]):
                learn_mode = None

    if terminateThread:  # if requested by main thread ...
        return  #    ... exit loop
    scan_keys()
    read_input()


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


def getKeyState(key: str) -> bool:
    global key_state
    return key_state.get(key, False)


def getFlameState() -> dict:
    global flame_keys
    return flame_keys.copy()


def getMode() -> str:
    global overall_mode
    return overall_mode


def getLearnMode() -> str:
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


old_flames = None
old_mode = None
old_lmode = None

try:
    inputOption = "LINE"  # get input from buffer one BYTE or LINE at a time
    while True:
        BackgroundProc()
        if inputOption == "BYTE":  # NON-BLOCKING input one byte at a time
            buffCh = getByteBuffer()  # get a byte if it is available?
            if buffCh:  # if there is...
                print(buffCh, end="")  # ...print it out to the USB serial port

        elif inputOption == "LINE":  # NON-BLOCKING input one line at a time (ending LF)
            buffLine = getLineBuffer()  # get a line if it is available?
            if buffLine:  # if there is...
                print(buffLine)  # ...print it out to the USB serial port

        flames = getFlameState()
        md = getMode()
        lm = getLearnMode()
        if (
            old_flames is None
            or any([flames[f] != old_flames[f] for f in flames.keys()])
            or old_mode != md
            or old_lmode != lm
        ):
            print("flames:|", end="")
            for f in range(len(flames)):
                key = f"f{f+1}"
                if flames[key]:
                    print("F", end="|")
                else:
                    print(".", end="|")
            print(f" mode {md} learn mode {lm}")
            old_flames = flames
            old_mode = md
            old_lmode = lm


except KeyboardInterrupt:  # trap Ctrl-C input
    terminateThread = True  # signal second 'background' thread to terminate
    print("interupted")
    exit()
