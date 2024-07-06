"""!
@file Scheduling_Precalculation.py
@package Bus_Scheduling
@brief This module serves for estimating the time needed for the scheduling process.
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
from Bus_Scheduling.Scheduling_Classes import Trip, Deadhead


def GetTerminalsPacked(daysTrips: List[Dict[str, Union[str, List]]]):
    terminals = sorted((s for s in ((td["Initial stop"], td["Terminal stop"]) for td in
                                    (d.get("Trips", []) for d in daysTrips))))
    return terminals


def GetTerminals(trips: List[Trip]) -> List[str]:
    terminals = sorted({t.StartStop for t in trips} | {t.EndStop for t in trips})
    return terminals


def CompactMultiDayTrips(trips: List[Dict[str, Union[str, List]]]) -> List[Trip]:
    res = []
    for d in trips:
        day = d["Day"]
        dayTrips = d["Trips"]
        for t in dayTrips:
            res.append(Trip(
                Line=t["Line number"],
                TripNo=t["Trip number"],
                StartStop=t["Initial stop"],
                EndStop=t["Terminal stop"],
                StartTime=t["Departure time"],
                EndTime=t["Arrival time"],
                Via=t.get("Stops"),
                Day=datetime.datetime.strptime(day, "%Y-%m-%d").date()
            ))
    RecalcAllTrips(res)
    return res


def RecalcAllTrips(trips: List[Trip], firstDay: Optional[datetime.date] = None):
    if not trips:
        return
    if not firstDay:
        firstDay = min(t.Day for t in trips)
    for t in trips:
        t.RecalcMinutes(firstDay)


def ReadTripsJson(tripsFile):
    with open(tripsFile, "r", encoding="utf-8") as f:
        return GetMultiDayTrips(f)


def GetMultiDayTrips(stream: TextIO):
    loaded_trips = json.load(stream)
    return CompactMultiDayTrips(loaded_trips)


def GetOneDayTrips(stream: TextIO, day: datetime.date):
    loaded_trips = json.load(stream)
    return CompactOneDayTrips(loaded_trips, day)


def CompactOneDayTrips(trips: List[Dict[str, Union[str, List]]], day: datetime.date) -> List[Trip]:
    res = []
    for t in trips:
        res.append(Trip(
            Line=t["Line number"],
            TripNo=t["Trip number"],
            StartStop=t["Initial stop"],
            EndStop=t["Terminal stop"],
            StartTime=t["Departure time"],
            EndTime=t["Arrival time"],
            Via=t.get("Stops"),
            Day=day
        ))
    return res


def ReadDistanceMatrix(csvMatrix: pathlib.Path, delimiter="\t"):
    with open(csvMatrix, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=delimiter)
        stops = next(reader)[1:]
        distances = []
        for el in reader:
            row = el[1:]
            distances.append(row)
        distances = np.array(distances).astype(int)
    return distances, stops


def GetDistFromEdge(edge: Tuple[int, int], trips: List[Trip], stopsMap: Dict[str, int],
                    distances: np.ndarray,
                    depotIdx=None, depotVal=0, linePenalty=0):
    """!
    @brief Get deadhead cost of two trips
    @param edge Tuple of two trip indices, -1 and -2 are pull-out and pull-in
    @param trips List of trips
    @param stopsMap Dictionary mapping stop names to indices
    @param distances 2d array of distances between stops
    @param depotIdx Index of depot in stopsMap
    @param depotVal Cost of depot stop
    @param linePenalty Penalty for changing lines
    """
    trip1, trip2 = edge

    distance = 0
    if trip1 == -1:
        if depotIdx is None:
            raise ValueError("Depot not specified")
        fromId = depotIdx
        distance += depotVal
    else:
        tripn1 = trips[trip1]
        fromId = stopsMap.get(tripn1.EndStop)
    if trip2 == -2:
        if depotIdx is None:
            raise ValueError("Depot not specified")
        toId = depotIdx
        distance += depotVal
    else:
        tripn2 = trips[trip2]
        toId = stopsMap.get(tripn2.StartStop)
    if trip1 >= 0 and trip2 >= 0:
        if trips[trip1].Line != trips[trip2].Line:
            distance += linePenalty
        # waiting penalty, experimental
        waitingTime = trips[trip2].StartTimeMins - trips[trip1].EndTimeMins - distances[fromId, toId]
        if waitingTime > 0:
            distance += 0.001 * waitingTime
    if fromId is None or toId is None:
        raise ValueError("Stop not found")
    distance += int(distances[fromId, toId])
    if distance < 0:
        print(f"Edge: {edge}, distance: {distance}, fromId: {fromId}, toId: {toId},trip1: {trip1}, trip2: {trip2}")
        print(distance-int(distances[fromId, toId]))
        print(distances[fromId, toId])
        print(trips[trip1])
        print(trips[trip2])
        raise ValueError("Negative distance")
    return distance


def GetDistFromEdgeCached(edge: tuple, edgesWeights):
    return edgesWeights[edge]


def CreateDeadheadMap(edges: List[tuple], trips, stops, distances, depotIdx=None, depotVal=0, linePenalty=0) \
        -> Dict[Tuple[int, int], int]:
    """
    Same as GetDistFromEdge, just on multiple edges at once (efficiency by not calling index)
    """
    indexMap = {stop: i for i, stop in enumerate(stops)}
    dhMap = {
        (trip1, trip2): GetDistFromEdge((trip1, trip2), trips, indexMap, distances, depotIdx, depotVal, linePenalty)
        for trip1, trip2 in edges}
    return dhMap


def GetDistFromEdgeStr(edge: str, trips, stops, distances, depotIdx=None, depotVal=0, linePenalty=0):
    trip1, trip2 = StrToTuple(edge)
    trip1 = int(trip1)
    trip2 = int(trip2)
    return GetDistFromEdge((trip1, trip2), trips, stops, distances, depotIdx, depotVal, linePenalty)


def CreateFeasibilityGraph(trips: List[Trip], stopsMap: Dict[str, int], distances: np.ndarray, maxWaitHours: int) -> \
List[Tuple[int, int]]:
    # Edges - indices of trips which can follow each other (reduce maxWaitHours to eliminate long gaps)

    edges = [(i, j)
             for i, t1 in enumerate(trips)
             for j, t2 in enumerate(trips)
             if t1.EndTimeMins + distances[stopsMap[t1.EndStop], stopsMap[t2.StartStop]]
             <= t2.StartTimeMins <=
             t1.EndTimeMins + maxWaitHours * 60
             ]

    return edges


def EstimateScheduling(trips, stops, distances, scheduleArgs):
    # might add more args for better estimation
    stopsMap = {stop: i for i, stop in enumerate(stops)}
    return EstimateTripsNoDepot(trips, distances, stopsMap)


def EstimateTripsNoDepot(trips: List[Trip], dists: np.ndarray, stops: Dict[str, int], onlyFeas=False, asTrips=True) -> \
        Dict[str, Any]:
    """!
    Trips - see definition of Trip
    dists - 2d matrix (time distance)
    stops - list of stops, correspond to matrix headers
    depot - If none, the buses can start and end anywhere (can add final DH trip); if specified, all buses must start at the specified stop
    Note: if the depot is not a terminal it will not be present in the list; the name does not have to be accurate, closest is found by edit distance
    """
    edges = CreateFeasibilityGraph(trips, stops, dists, 24)
    res = {
        "Trip count": len(trips),
        "Edges count": len(edges)
    }
    return res
