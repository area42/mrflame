# coding=utf-8
# python

# Current delay is
# - 140 milliseconds for HID processing.
# -
# DEBOUNCE_MAX = 20

from machine import Pin
import time

column1 = Pin(0, Pin.IN, Pin.PULL_UP)
column2 = Pin(1, Pin.IN, Pin.PULL_UP)
column3 = Pin(2, Pin.IN, Pin.PULL_UP)
column4 = Pin(3, Pin.IN, Pin.PULL_UP)
column7 = Pin(4, Pin.IN, Pin.PULL_UP)
column6 = Pin(5, Pin.IN, Pin.PULL_UP)
column5 = Pin(6, Pin.IN, Pin.PULL_UP)
column8 = Pin(7, Pin.IN, Pin.PULL_UP)

columns = [column1, column2, column3, column4, column5, column6, column7, column8]

row1 = Pin(13, Pin.OUT,value=0)
row2 = Pin(14, Pin.OUT,value=0)
row3 = Pin(15, Pin.OUT,value=0)

rows = [row1, row2, row3]

buf = bytearray(8)
last_buf = bytearray(8)
last_buf[2] = 0
last_buf[0] = 0
something_pressed = False
ROW_RANGE = range(3)
COLUMN_RANGE = range(8)

matrix = [
    ['mi','f8','f16'],
    ['en','f7','f15'],
    ['s4','f5','f13'],
    ['s5','f6','f14'],
    ['st','f1','f9'],
    ['s2','f36','f11'],
    ['s3','f4','f12'],
    ['s1','f2','f10'],
]

while True:
    for y in ROW_RANGE:
        row = rows[y]
        row.low()
        for x in COLUMN_RANGE:
            column = columns[x]
            key_string = matrix[x][y]
            if not column.value():
                print(key_string,end=" ")
        row.high()
    time.sleep_ms(20)
