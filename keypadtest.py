import SX1509
import sys
import uselect

mux = SX1509.SX1509()

rows = 3
cols = 8
mux.keypad(rows, cols, 0, 8, 4)

lv = 0
state = [False] * rows * cols
keys = []
for i in range(0, 16):
    keys.append(f"f{i}")

keys.append("m")
keys.append("e")

for i in range(0, 6):
    keys.append(f"s{i}")

keys.append("st")

def read_serial_input():
    buffer_input = ""
    # stdin.read() is blocking which means we hang here if we use it. Instead use select to tell us if there's anything available
    # note: select() is deprecated. Replace with Poll() to follow best practises
    select_result = uselect.select([sys.stdin], [], [], 0)
    while select_result[0]:
        # there's no easy micropython way to get all the bytes.
        # instead get the minimum there could be and keep checking with select and a while loop
        input_character = sys.stdin.read(1)
        # add to the buffer
        buffered_input.append(input_character)
        # check if there's any input remaining to buffer
        select_result = uselect.select([sys.stdin], [], [], 0)
    if len(buffer_input) > 0:
        print(f'>{buffer_input}<')

for rp in range(100000):
    read_serial_input()

    nv = mux.readKeypad()
    if nv == 0 or nv == lv:
        continue
    lv = nv

    idx = mux.getRow(nv) * cols + mux.getCol(nv)
    r = mux.getRow(nv)
    c = mux.getCol(nv)
    print("", end="|")
    for i in range(len(keys)):
        if i == idx:
            print(f"{keys[i]}", end="|")
        else:
            l = len(keys[i])
            print("-" * l, end="|")
    print(f" row {r} col {c} idx {idx} loop {rp} `{lv:>016b}`")
