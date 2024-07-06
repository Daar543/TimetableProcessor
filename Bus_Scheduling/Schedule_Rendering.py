"""!
@file Scheduling_Utilities.py
@package Bus_Scheduling
@brief Functions for formatting schedules in pretty tables.
"""

import prettytable
from typing import Any, List, Optional, Dict, Tuple
from Bus_Scheduling.Scheduling_Precalculation import Trip, Deadhead
import numpy as np
import difflib
from Bus_Scheduling.Scheduling_Utilities import ConvertToHxM


# Inserts deadheads between trips for each schedule and verifies feasibility
def FormatSchedule(scheduledTrips: List[List[Trip]], distances: np.ndarray, stops: List[str],
                   addFinalDeadhead: bool = False, depot=None):
    if depot:
        actualDepotName = difflib.get_close_matches(depot, stops, n=1)[0]
        depotId = stops.index(actualDepotName)

    formattedTrips = []
    deadheadTimes = []
    for schedule in scheduledTrips:
        currentSchedule = []
        currentDHTime = 0

        if depot:
            distance = distances[depotId, stops.index(schedule[0].StartStop)]
            pullout = Deadhead(stops[depotId], schedule[0].StartStop, distance)
            pullout.EarliestTimeMins = schedule[0].StartTimeMins
            pullout.EarliestTime = ConvertToHxM(pullout.EarliestTimeMins)
            currentSchedule.append(pullout)
            currentDHTime += pullout.DurationMins

        currentSchedule.append(schedule[0])
        for i in range(1, len(schedule)):
            OldTrip = schedule[i - 1]
            NewTrip = schedule[i]
            if OldTrip.EndStop == NewTrip.StartStop:
                currentSchedule.append(NewTrip)
                continue
            else:
                # This could be optimized, but is not a bottleneck
                fromId = stops.index(OldTrip.EndStop)
                toId = stops.index(NewTrip.StartStop)
                distance = distances[fromId, toId]
                if not (OldTrip.EndTimeMins + distance <= NewTrip.StartTimeMins):
                    # assert(False)
                    pass

                deadhead = Deadhead(OldTrip.EndStop, NewTrip.StartStop, distance)
                deadhead.EarliestTimeMins = OldTrip.EndTimeMins + distance
                deadhead.EarliestTime = ConvertToHxM(deadhead.EarliestTimeMins)
                currentDHTime += deadhead.DurationMins

                currentSchedule.append(deadhead)
                currentSchedule.append(NewTrip)

        if depot:
            distance = distances[stops.index(schedule[-1].EndStop), depotId]
            pullin = Deadhead(schedule[-1].EndStop, stops[depotId], distance)
            pullin.EarliestTimeMins = schedule[-1].EndTimeMins + distance
            pullin.EarliestTime = ConvertToHxM(pullin.EarliestTimeMins)
            currentSchedule.append(pullin)
            currentDHTime += pullin.DurationMins

        elif addFinalDeadhead:
            OldTrip = schedule[-1]
            NewTrip = schedule[0]
            if OldTrip.EndStop != NewTrip.StartStop:
                fromId = stops.index(OldTrip.EndStop)
                toId = stops.index(NewTrip.StartStop)
                distance = distances[fromId, toId]
                deadhead = Deadhead(OldTrip.EndStop, NewTrip.StartStop, distance)
                deadhead.EarliestTimeMins = OldTrip.EndTimeMins + distance
                deadhead.EarliestTime = ConvertToHxM(deadhead.EarliestTimeMins)
                currentSchedule.append(deadhead)
                currentDHTime += deadhead.DurationMins

        formattedTrips.append(currentSchedule)
        deadheadTimes.append(currentDHTime)

    return formattedTrips, deadheadTimes


def TableSchedules(scheduledTrips: List):
    schedules = []

    for i in range(len(scheduledTrips)):
        table = []
        header = ["Row", "Line", "ConnNo", "StartStop", "EndStop", "StartTime", "EndTime", "Duration"]
        table.append(header)
        rown = 0
        for x in scheduledTrips[i]:
            rown += 1
            if hasattr(x, "DurationMins"):
                x: Deadhead
                row = [rown, "-", "-", x.StartStop, x.EndStop, ConvertToHxM(x.EarliestTimeMins - x.DurationMins),
                       x.EarliestTime, ConvertToHxM(x.DurationMins)]
                table.append([str(attr) for attr in row])
            else:
                x: Trip
                row = [rown, x.Line, x.TripNo, x.StartStop, x.EndStop, x.StartTime, x.EndTime,
                       ConvertToHxM(x.EndTimeMins - x.StartTimeMins)]
                table.append([str(attr) for attr in row])
        schedules.append(table)

    return schedules


def PrintTabularSchedules(tabularSchedules, deadheads=None):
    print("Amount of buses needed: " + str(len(tabularSchedules)))

    print("Schedules:\n")
    for i in range(len(tabularSchedules)):
        print(f"Bus {i + 1}:")
        print("---")
        tbl = prettytable.PrettyTable()
        tbl.field_names = tabularSchedules[i][0]
        tbl.add_rows(tabularSchedules[i][1:])
        print(tbl)
        if deadheads:
            print(f"(deadhead {deadheads[i]} mins, {ConvertToHxM(deadheads[i])})\n")

    return


def SchedulesToJsonDict(schedule: List[List[Trip]], scheduleArgs: Dict[str, Any]) -> Dict[str, Any]:
    res = {k: v for k, v in scheduleArgs.items()}
    trips = []
    for i, bus in enumerate(schedule):
        ts = {"Bus": i + 1, "Trips": [t.ToDictForJson() for t in bus]}
        trips.append(ts)
    res["Bus schedules"] = trips
    return res


def SchedulesFromJsonDict(schedules: Dict) -> Tuple[List[List[Trip]], Dict[str, Any]]:
    scheduleArgs = {k: v for k, v in schedules.items() if k not in ["Bus schedules"]}
    buses = schedules["Bus schedules"]
    res = [[Trip.FromDictForJson(t) for t in b["Trips"]] for b in buses]
    return res, scheduleArgs

def SchedulesDirectly(schedules:Dict) -> Tuple[Dict[str,Any],Dict[str,Any]]:
    scheduleArgs = {k: v for k, v in schedules.items() if k not in ["Bus schedules"]}
    buses = schedules["Bus schedules"]
    return buses, scheduleArgs

def TranslateSchedulingMethod(method: str) -> str:
    if method=="default":
        return "Default"
    if method == "circular":
        return "Circular without depot"
    elif method == "depot":
        return "With a single depot"
    else:
        return "Unknown"
