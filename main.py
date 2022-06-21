#
#
from time import sleep_ms  # type: ignore
from machine import Timer
import SX1509
from IO_Types import *

import frontpanel as fp
import re

flame_state_template = {
    "enabled": False,
    "note": None,
    "open": False,
    "midi": False,  # midi learn modus
    "hold_timer": None,
    "max_time_timer": None,
    "ioport": 0
}

flame_state = {}
flame_names = fp.getFlamesNames()
ioport =0 
for flame in flame_names:
    flame_state[flame] = flame_state_template.copy()
    flame_state[flame]["ioport"] = ioport
    ioport = ioport + 1

note_to_flame = {}  # type: ignore

def holdTimeExpired(flame):
    global flame_state
    flame_state[flame]["hold_timer"].deinit()
    flame_state[flame]["hold_timer"] = None     # can I just remove the timer?
    killFlame(flame,False)
    
def lightFlame(flame):
    global flame_state, update_leds
    if flame_state[flame]["enabled"]:
        flame_state[flame]["open"] = True
        if flame_state[flame]["hold_timer"] is None and fp.getHoldTime()>0: 
            flame_state[flame]["hold_timer"] = Timer(period=fp.getHoldTime(), 
                                                        mode=Timer.ONE_SHOT, 
                                                        callback=lambda t: holdTimeExpired(flame))
        update_leds = True

def killFlame(flame, ignore_hold_time=False):
    global flame_state, update_leds
    
    if ignore_hold_time:
        holdTimeExpired(flame)
        
    if flame_state[flame]["hold_timer"] is None: 
        flame_state[flame]["open"] = False
        update_leds = True

def setFlameStateLeds(color_map):
    global flame_names, flame_state

    for flame in flame_names:
        state = flame_state[flame]
        # print(flame,state)
        if state["open"]:
            fp.setFlameLed(flame, color_map["open"])
        elif state["enabled"]:
            if state["midi"]:
                fp.setFlameLed(flame, color_map["midi"])
            elif state["note"] is not None:
                fp.setFlameLed(flame, color_map["note"])
            else:
                fp.setFlameLed(flame, color_map["enabled"])
        else:
            fp.setFlameLed(flame, color_map["disabled"])

# ------------------------------- setup relays ------------------------------ #

ioexpander = SX1509.SX1509()
for r in range(15):
    ioexpander.pinMode(r,PIN_TYPE_OUTPUT)
    ioexpander.digitalWrite(r,0)
    
def updateRelay(flame):
    global flame_state, ioexpander
    if flame_state[flame]["enabled"] and flame_state[flame]["open"]:
        ioexpander.digitalWrite(flame_state[flame]["ioport"],1)
    else:
        ioexpander.digitalWrite(flame_state[flame]["ioport"],0)

def updateRelays():    
    for flame in flame_names:
        updateRelay(flame)   

def allRelayOff(update_state=False):
    global ioexpander, flame_state, update_leds
    ioexpander._write_reg_16(SX1509._SX1509_RegDataB,0)
    if update_state:
        for flame in flame_names:
            flame_state[flame]["open"] = False
            update_leds = True

def next_flame(flame) -> str:
    global flame_state
    found_it = False
    ret = None
    for f in flame_names:
        if f == flame:
            found_it = True
            continue
        
        if found_it:
            if flame_state[f]["enabled"]:
                return f
    
    # fall through
    if flame != first_flame:
        return next_flame(first_flame)
    
    return ret 

note_cmd_re = re.compile(r'^midi (note_.*) channel=(\d+) note=(\d+) velocity=(\d+)')
note_cmd = ""
update_leds = False
lastSeqState = None
seqflame = None
first_flame = flame_names[0]
last_flame = flame_names[-1]


try:
    while True:
        fp.processIO()
        buffLine = fp.getLineBuffer()  # get a line if it is available?
        if buffLine:  # if there is...
            print(f'>{buffLine}<')  # ...print it out to the USB serial port
            # midi note_off channel= note=47 velocity=0 time=0
            if note_cmd_re.match(buffLine):
                m = note_cmd_re.match(buffLine)
                note_cmd = m.group(1)
                if note_cmd == "note_on":
                    note = m.group(3)
                    print(f'note {note} on')
                if note_cmd == "note_off":
                    note = m.group(3)
                    print(f'note {note} off')
        
        button_changed = fp.fpChanged()
        if not (button_changed or buffLine or update_leds):
             continue

        update_leds = False
        
        if fp.sequencer_speed_reader.has_changed or fp.getSeqState() != lastSeqState:
            if fp.getSeqState():
                fp.blinkSequenceLed("green")
                if not lastSeqState:
                    seqflame = next_flame(first_flame)
            else:
                fp.blinkSequenceLed("blue")
            lastSeqState = fp.getSeqState()



        modus = fp.getMode()
        lmodus = fp.getLearnMode()
        fbs = fp.getFlameButtonState()

        print(f"mode {modus}, lmodus {lmodus} ({fp.ts()})")
        if modus != "learn" or (modus == "learn" and fp.getLearnMode() != "lmi"):  # not midi mode
            for midiflame in flame_names:
                flame_state[midiflame]["midi"] = False

        if  modus not in ("live", "learnlive"):
            allRelayOff()
            
        if modus == "off":
            fp.allFlameLeds("off")
        elif modus == "learn":
            if fp.getLearnMode() == "len":  # enable mode
                setFlameStateLeds(
                    {
                        "disabled": "orange",
                        "enabled": "green",
                        "midi": "blue",
                        "note": "white",
                        "open": "red",
                    }
                )
                for flame in flame_names:
                    if button_changed and fbs[flame]:
                        print(flame, flame_state[flame]["enabled"])
                        flame_state[flame]["enabled"] = not (
                            flame_state[flame]["enabled"]
                        )
                        print(flame, flame_state[flame]["enabled"])
                        
            if fp.getLearnMode() == "lmi":  # midi mode
                setFlameStateLeds(
                    {
                        "disabled": "off",
                        "enabled": "green",
                        "midi": "blue",
                        "note": "white",
                        "open": "red",
                    }
                )
                
                for flame in flame_names:                    
                    if button_changed and fbs[flame] and flame_state[flame]["enabled"]:
                        for midiflame in flame_names:
                            if midiflame != flame:
                                flame_state[midiflame]["midi"] = False
                                update_leds = True
                        flame_state[flame]["midi"] = not flame_state[flame]["midi"]
                        if flame_state[flame]["midi"]:
                            if flame_state[flame]["note"]:
                                ntf = []
                                for nf in note_to_flame[flame_state[flame]["note"]]:
                                    if nf != flame:
                                        ntf.append(nf)
                                note_to_flame[note] = ntf
                            flame_state[flame]["note"]= None  
                            update_leds = True
                              
                if note_cmd == "note_on":
                    for midiflame in flame_names:           
                        if flame_state[midiflame]["midi"]:
                            flame_state[midiflame]["note"] = note # type: ignore
                            if note not in note_to_flame:
                                note_to_flame[note] = []
                            note_to_flame[note].append(midiflame)
                            flame_state[midiflame]["midi"] = False
                            note_cmd = ""
                            update_leds = True
                            print(note_to_flame)
                    note_cmd = ""
    
        elif modus in ("test", "live", "learnlive"):
            if modus == "test":
                setFlameStateLeds(
                    {
                        "disabled": "off",
                        "enabled": "green",
                        "midi": "blue",
                        "note": "blue",
                        "open": "violet",
                    }
                )
            else:
                setFlameStateLeds(
                    {
                        "disabled": "off",
                        "enabled": "purple",
                        "midi": "blue",
                        "note": "blue",
                        "open": "yellow",
                    }
                )
                
            if button_changed:
                for flame in flame_names:                     
                    if fbs[flame]:
                        if not flame_state[flame]["open"]:
                            lightFlame(flame)
                    else:
                        if flame_state[flame]["open"]:
                            killFlame(flame)
                                    
            if note_cmd:
                if note_cmd == "note_on":
                    if note in note_to_flame:
                        for nf in note_to_flame[note]:
                            lightFlame(nf)
                    note_cmd = ""
                elif note_cmd == "note_off":
                    if note in note_to_flame:
                        for nf in note_to_flame[note]:
                            killFlame(nf)
                    note_cmd = ""
                    
            if  modus in ("live", "learnlive"):
                updateRelays()

except KeyboardInterrupt:  # trap Ctrl-C input
    terminateThread = True  
    print("interupted")
    exit()
