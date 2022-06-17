import time
import SX1509
import IO_Types


PIN_VUSB = 1
PIN_LBO = 2
PIN_AMP_SD = 3

PIN_RESET_BUTTON = 10

DEVICE_ADDRESS = 0x3E  # device address of SX1509

#Set up I2C

#Initialize the expander
IOExpander = SX1509.SX1509()
IOExpander.clock(oscDivider = 4)
IOExpander.debounceTime(32)

#Set up pins
IOExpander.keypad(rows=3,columns=8)
#IOExpander.enableInterrupt(PIN_RESET_BUTTON, IO_Types.INTERRUPT_STATE_RISING)
#IOExpander.enableInterrupt(PIN_VUSB, IO_Types.INTERRUPT_STATE_FALLING)
#IOExpander.enableInterrupt(PIN_LBO, IO_Types.INTERRUPT_STATE_FALLING)

print('IO Expander Initialized')

while 1:
#  InterruptVals = IOExpander.interruptSource()
#  if(InterruptVals & (1<<PIN_RESET_BUTTON)):
#   print('Reset button pressed')
#  elif(InterruptVals & (1<<PIN_VUSB)):
#   print('USB Power Lost')
#  elif(InterruptVals & (1<<PIN_LBO)):
#   print('Low Battery')
 time.sleep(.2)


