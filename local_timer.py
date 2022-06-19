from machine import Pin, Timer, ADC # type: ignore
from sys import stdin


_ts:int = 0 

def ts_tick():
    global _ts
    _ts = _ts+1

