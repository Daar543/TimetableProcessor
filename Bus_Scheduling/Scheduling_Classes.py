"""!
@file Scheduling_Classes.py
@package Bus_Scheduling
@brief Here are saved classes for trips used in bus scheduling.
"""


import csv
import datetime
import json
import pathlib
from dataclasses import dataclass
from time import time
from typing import List, TextIO, Union, Optional, Dict, Any, Tuple

import networkx as nx
import numpy as np

from Bus_Scheduling.Scheduling_Utilities import StrToTuple, ParseHxM

@dataclass
class Trip:
    Line: int
    TripNo: int
    StartStop: str
    EndStop: str
    StartTime: str
    EndTime: str
    Via: Optional[List[Dict]]
    Day: datetime.date = datetime.date.min

    StartTimeMins = -1
    EndTimeMins = -1

    def RecalcMinutes(self, firstDay: Optional[datetime.date] = None):
        """!
        Initializes minutes relative to the start day to the object as a number (e.g. 10:00 as StartTime will create 600 StartTimeMins)
        """
        self.StartTimeMins = ParseHxM(self.StartTime)
        self.EndTimeMins = ParseHxM(self.EndTime)
        assert (self.StartTimeMins >= 0)
        assert (self.EndTimeMins >= 0)
        if self.EndTimeMins < self.StartTimeMins:
            self.EndTimeMins += 24 * 60
        if self.Day and firstDay:
            daydiff = (self.Day - firstDay).days
            self.StartTimeMins += daydiff * 24 * 60
            self.EndTimeMins += daydiff * 24 * 60

        return

    def ToDictForJson(self) -> Dict:
        res = {}
        if self.Day:
            res["Day"] = self.Day.strftime("%Y-%m-%d")
        res.update({
            "Line": self.Line,
            "Trip": self.TripNo,
            "Start stop": self.StartStop,
            "End stop": self.EndStop,
            "Start time": self.StartTime,
            "End time": self.EndTime
        })
        if self.Via:
            res["Stops"] = self.Via

        return res

    @staticmethod
    def FromDictForJson(d:Dict[str,Any])-> "Trip":
        return Trip(
            Line=d["Line"],
            TripNo=d["Trip"],
            StartStop=d["Start stop"],
            EndStop=d["End stop"],
            StartTime=d["Start time"],
            EndTime=d["End time"],
            Via=d.get("Stops"),
            Day=datetime.datetime.strptime(d["Day"], "%Y-%m-%d").date() if d.get("Day") else None
        )

    def __lt__(self, other):
        if self.StartTimeMins != other.StartTimeMins:
            return self.StartTimeMins < other.StartTimeMins
        if self.EndTimeMins != other.EndTimeMins:
            return self.EndTimeMins < other.EndTimeMins
        return ((self.Day,datetime.datetime.strptime(self.StartTime, "%H:%M"),
                 datetime.datetime.strptime(self.EndTime, "%H:%M"))) < (
            (other.Day,datetime.datetime.strptime(other.StartTime, "%H:%M"),
                    datetime.datetime.strptime(other.EndTime, "%H:%M")))


@dataclass
class Deadhead:
    StartStop: str
    EndStop: str
    DurationMins: int
    EarliestTimeMins = -1
    EarliestTime = None

