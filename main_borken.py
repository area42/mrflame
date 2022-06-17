print("at begin")
import process_io
import time

#
# main program begins here ...
#
# set 'inputOption' to either  one byte ‘BYTE’  OR one line ‘LINE’ at a time. Remember, ‘bufferEcho’
# determines if the background buffering function ‘bufferSTDIN’ should automatically echo each
# byte it receives from the USB serial port or not (useful when operating in line mode when the
# host computer is running a serial terminal program)
#
# start this MicroPython code running (exit Thonny with code still running) and then start a
# serial terminal program (e.g. putty, minicom or screen) on the host computer and connect
# to the Raspberry Pi Pico ...
#
#    ... start typing text and hit return.
#
#    NOTE: use Ctrl-C, Ctrl-C, Ctrl-D then Ctrl-B on in the host computer terminal program 
#           to terminate the MicroPython code running on the Pico 
#
# Ctrl-A on a blank line will enter raw REPL mode. This is similar to permanent paste mode, except that characters are not echoed back.
# Ctrl-B on a blank like goes to normal REPL mode.
# Ctrl-C cancels any input, or interrupts the currently running code.
# Ctrl-D on a blank line will do a soft reset (and will auto run anything defined in main.py).
# Ctrl-E enters ‘paste mode’ that allows you to copy and paste chunks of text. Exit this mode using Ctrl-D.
# Ctrl-F performs a “safe-boot” of the device that prevents boot.py and main.py from executing

print("before loop")
try:
    process_io.inputOption = 'LINE'                    # get input from buffer one BYTE or LINE at a time
    while True:
        print(".",end="")
        if process_io.inputOption == 'BYTE':           # NON-BLOCKING input one byte at a time
            buffCh = process_io.getByteBuffer()        # get a byte if it is available?
            if buffCh:                      # if there is...
                print (buffCh, end='')      # ...print it out to the USB serial port

        elif process_io.inputOption == 'LINE':         # NON-BLOCKING input one line at a time (ending LF)
            buffLine = process_io.getLineBuffer()      # get a line if it is available?
            if buffLine:                    # if there is...
                print (buffLine)            # ...print it out to the USB serial port

        print("flames:|")
        flames = process_io.flame_keys
        for flame in range(len(flames)):
            if flames[flame]:
                print("F",end="|")
            else:
                print(".",end="|")
        print("|")

        time.sleep_ms(100)

except KeyboardInterrupt:                   # trap Ctrl-C input
    terminateThread = True                  # signal second 'background' thread to terminate 
    print("interupted")
    exit()