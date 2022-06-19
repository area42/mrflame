#
#
from time import sleep_ms  # type: ignore
from machine import Timer

import frontpanel as fp
import re

flame_state_template = {
    "enabled": False,
    "note": None,
    "open": False,
    "midi": False,  # midi learn modus
    "hold_timer": None,
    "max_time_timer": None
}

flame_state = {}
flame_names = fp.getFlamesNames()
for flame in flame_names:
    flame_state[flame] = flame_state_template.copy()

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

note_cmd_re = re.compile(r'^midi (note_.*) channel=(\d+) note=(\d+) velocity=(\d+)')
note_cmd = ""
update_leds = False

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
        
        if fp.getSeqState():
            fp.blinkSequenceLed("green")
        else:
            fp.blinkSequenceLed("blue")

        modus = fp.getMode()
        lmodus = fp.getLearnMode()
        fbs = fp.getFlameButtonState()

        print(f"mode {modus}, lmodus {lmodus} ({fp.ts()})")
        if modus != "learn" or (modus == "learn" and fp.getLearnMode() != "lmi"):  # not midi mode
            for midiflame in flame_names:
                flame_state[midiflame]["midi"] = False

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
                        "open": "red",
                    }
                )
            else:
                setFlameStateLeds(
                    {
                        "disabled": "off",
                        "enabled": "green",
                        "midi": "blue",
                        "note": "blue",
                        "open": "orange",
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
        
        

except KeyboardInterrupt:  # trap Ctrl-C input
    terminateThread = True  
    print("interupted")
    exit()
