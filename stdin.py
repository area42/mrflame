import sys
import select

for i in range(10000):
    if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
        line = sys.stdin.readline()
        print(line)
    else:
        print(".",end="")