"""!
@file Scheduling_Utilities.py
@package Bus_Scheduling
@brief General functions for parsing time and string formatting, with relation to scheduling.
"""
import random

def ParseHxM(hhmm: str) -> int:
    shh, smm = hhmm.split(":")

    if len(shh) != 1 and len(shh) != 2:
        raise ValueError("Invalid time format")
    if len(smm) != 2:
        raise ValueError("Invalid time format")
    hh = int(shh)
    mm = int(smm)
    if not (0 <= hh < 24):
        raise ValueError("More than 23 hours")
    if not (0 <= mm < 60):
        raise ValueError("More than 60 minutes")
    return 60 * hh + mm

def ConvertToHxM(mins: int) -> str:
    mins %= (24 * 60)
    hh = mins // 60
    mm = mins % 60
    shh = str(hh)
    smm = str(mm).rjust(2, "0")
    return f"{shh}:{smm}"


def StrToTuple(tpl: str):
    a, b = tpl[1:-1].split(",")
    return int(a), int(b)

# https://stackoverflow.com/questions/9259989/select-random-item-with-weight
def SelectRandomWeightedIdx(wts, precalcSums=None, precalcTotals=None):
    totals = []
    if not precalcSums:
        running_total = 0

        for w in wts:
            running_total += w
            totals.append(running_total)
    else:
        totals = precalcSums
        if not precalcTotals:
            running_total = sum(totals)
        else:
            running_total = precalcTotals
    rnd = random.random() * running_total
    for i, total in enumerate(totals):
        if rnd < total:
            return i