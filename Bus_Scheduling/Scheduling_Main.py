import argparse
import copy
import difflib
import json
import math
import os
import pathlib
import random
import sys
import time

from typing import Any, Dict, List, Union, Iterable, Tuple, Optional

import mip
import networkx as nx
import numpy as np

from Bus_Scheduling import Scheduling_Precalculation
from Bus_Scheduling.Schedule_Rendering import FormatSchedule, TableSchedules, PrintTabularSchedules
from Bus_Scheduling.Scheduling_Precalculation import Trip, Deadhead, ReadTripsJson, ReadDistanceMatrix
from Bus_Scheduling.Scheduling_Utilities import ConvertToHxM, SelectRandomWeightedIdx, StrToTuple


def ConvertEdgesToBuses(tripsCount: int, edges: List[Tuple[int, int]]) -> List[List[int]]:
    """!
    @brief Creates bus schedules based on edges of chained trips
    @param tripsCount Number of trips
    @param edges List of tuples (u,v) where u is the trip index and v is the next trip index
    @return List of buses, where each bus is a list of trip indices
    """
    edges.sort()
    used = set()  # Trips already covered
    be = {u: v for u, v in edges}
    chains = []
    for u, v in be.items():
        if u in used or v in used:
            continue
        current = [u, v]
        used.add(u)
        used.add(v)
        while v := be.get(v):
            used.add(v)
            if v >= tripsCount:
                break
            current.append(v)
        chains.append(current)
    solo = [i for i in range(tripsCount) if i not in used]
    buses = chains + [[i] for i in solo]
    buses.sort(key=lambda bs: (-len(bs), bs[0]))
    return buses


def OptimizeTripsDefault(trips: List[Trip], dists: np.ndarray, stops: Dict[str, int], asTrips: bool = True) -> Union[
    List[List[Trip]], List[List[int]]]:
    """!
    @brief Creates bus schedules based on default algorithm in order to minimize bus count
    @param trips List of trips, see Trip class
    @param dists 2D matrix (time distance)
    @param stops Map of stop names to indices in the matrix
    @param asTrips If True, returns list of lists of trips; if False, returns list of lists of trip indices
    """
    startTime = time()

    # Use easy (polynomial) optimization: we have no depot, buses can start and end anywhere, no driver limits
    edges = Scheduling_Precalculation.CreateFeasibilityGraph(trips, stops, dists, 24)

    print("Edges count:", len(edges))
    print("Trips count:", len(trips))
    n = len(trips)

    G = nx.Graph()
    # Nodes {0..n-1} correspond to arrival, {n..2n-1} to departure, n=len(trips)
    arrivalRange = range(n)
    departureRange = range(n, 2 * n)
    G.add_nodes_from(arrivalRange)
    G.add_nodes_from(departureRange)
    # Edges: Arrival x Departure
    G.add_edges_from((ta, n + td) for ta, td in edges)
    print("Graph created")
    # Find maximum cardinality matching (the graph may be disconnected)
    matching = nx.bipartite.maximum_matching(G, top_nodes=arrivalRange)
    print("Matching found")
    # Read chained trips from matching - only take tuples with lower node, as the matching returns both directions
    chosenEdges = sorted([(f, t - n) for f, t in matching.items() if f < t and f < n])
    print("Number of chained trips:", len(chosenEdges))
    print("Number of trips:", n)
    buses = ConvertEdgesToBuses(n, chosenEdges)
    print("Amount of buses:", len(buses))
    endTime = time()
    print("Optimized in:", endTime - startTime, "seconds")
    if asTrips:
        return [[trips[x] for x in buses[i]] for i in range(len(buses))]
    else:
        return buses


def OptimizeTripsOptionalDepot(trips: List[Trip], dists: np.ndarray, stops: Dict[str, int],
                               depotIdx: None, asTrips=True) -> Union[
    List[List[Trip]], List[List[int]]]:
    """!
    @brief Creates bus schedules based on single depot algorithm
    @param trips List of trips, see Trip class
    @param dists 2D matrix (time distance)
    @param stops Map of stop names to indices in the matrix
    @param depotName Name of the depot (closest match will be found)
    @param asTrips If True, returns list of lists of trips; if False, returns list of lists of trip indices
    """
    startTime = time.process_time()
    if depotIdx is not None:
        try:
            depotName = [k for k, v in stops.items() if v == depotIdx][0]
            print("Depot:", depotName)
        except IndexError:
            raise IndexError("Depot not found")
    else:
        depotIdx = -1
        print("Depot not specified")
    # Use easy (polynomial) optimization (max one depot, no driver limits)
    edges = Scheduling_Precalculation.CreateFeasibilityGraph(
        trips, stops, dists, 24)

    print("Trip count:", len(trips))
    print("Edge count:", len(edges))
    n = len(trips)

    G = nx.Graph()
    # Nodes {0..n-1} correspond to arrival, {n..2n-1} to departure, n=len(trips)
    arrivalRange = range(n)
    departureRange = range(n, 2 * n)
    G.add_nodes_from(arrivalRange)
    G.add_nodes_from(departureRange)
    # Edges: Arrival x Departure

    G.add_weighted_edges_from(
        (ta, td + n,
         Scheduling_Precalculation.GetDistFromEdge((ta, td), trips, stops, dists))
        for ta, td in edges)
    print("Graph created with weights")
    # Find maximum cardinality matching (the graph may be disconnected)
    matching = nx.bipartite.maximum_matching(G, top_nodes=arrivalRange)
    print("Matching found")
    # Read chained trips from matching - only take tuples with lower node, as the matching returns both directions
    chosenEdges = sorted([(a, d - n) for a, d in matching.items() if a in arrivalRange and d in departureRange])
    buses = ConvertEdgesToBuses(len(trips), chosenEdges)
    m = len(buses)
    print("Amount of buses:", m)
    # Nodes {2n..2n+m-1} correspond to pull-out, {2n+m..2n+2m-1} to pull-in, m=len(buses)
    pullOutRange = range(2 * n, 2 * n + m)
    pullInRange = range(2 * n + m, 2 * n + 2 * m)
    G.add_nodes_from(pullOutRange)
    G.add_nodes_from(pullInRange)

    if depotIdx >= 0:
        G.add_weighted_edges_from((b, d, Scheduling_Precalculation.GetDistFromEdge(
            (-1, d - len(trips)), trips, stops, dists, depotIdx, depotVal=24 * 60, linePenalty=10))
                                  for b in pullOutRange for d in departureRange)
        G.add_weighted_edges_from((a, b, Scheduling_Precalculation.GetDistFromEdge(
            (a, -2), trips, stops, dists, depotIdx, depotVal=24 * 60, linePenalty=10))
                                  for a in arrivalRange for b in pullInRange)
    else:
        # I put 1440 so it is non-zero, and picked only when there is no other option
        G.add_weighted_edges_from((b, d, 24 * 60) for b in pullOutRange for d in departureRange)
        G.add_weighted_edges_from((a, b, 24 * 60) for a in arrivalRange for b in pullInRange)

    matching = nx.bipartite.minimum_weight_full_matching(G)

    chainEdges = sorted([(a, d - n) for a, d in matching.items() if a in arrivalRange and d in departureRange])
    pullOutEdges = sorted([(b, d) for b, d in matching.items() if b in pullOutRange])
    pullInEdges = sorted([(a, b) for a, b in matching.items() if b in pullInRange])
    assert (len(pullOutEdges) == len(pullInEdges))
    assert (len(pullOutEdges) == m)
    assert (len(chainEdges) + len(pullOutEdges) == len(trips))
    buses = ConvertEdgesToBuses(len(trips), chainEdges)
    endTime = time.process_time()
    print(f"Optimized in {int((endTime-startTime)*1000)} ms")
    if asTrips:
        schedules = [[trips[x] for x in buses[i]] for i in range(m)]
    else:
        schedules = buses
    return schedules


def OptimizeTripsSingleDepotLP(trips: List[Trip], dists: np.ndarray, stops: Dict[str, int], depot: str):
    closestDepotNames = difflib.get_close_matches(depot, stops)
    if not closestDepotNames:
        raise ValueError(f"Depot \"{depot}\" not found")
    depotName = closestDepotNames[0]
    depotId = stops[depotName]
    print("Depot:", depotName)
    print("Trip count:", len(trips))

    # All trips must start and end at a depot (provided stop), deadhead is incounted
    edges = Scheduling_Precalculation.CreateFeasibilityGraph(trips, stops, dists, 24)
    pullout = [(-1, t) for t in range(len(trips))]  # -1 as start, -2 as end
    pullin = [(t, -2) for t in range(len(trips))]

    print("Creating model:")
    m = mip.Model(sense=mip.MAXIMIZE, solver_name=mip.CBC)

    for u, v in edges + pullin + pullout:
        m.add_var(name=str((u, v)), var_type=mip.BINARY)

    for t in range(len(trips)):
        incomingEdges = [ed for ed in edges if ed[1] == t]
        rgsum = mip.xsum(m.var_by_name(str(ed)) for ed in incomingEdges) + m.var_by_name(
            str((-1, t)))  # Sum of all edges terminating in t...
        m += (rgsum == 1)  # is exactly 1

    for t in range(len(trips)):
        outgoingEdges = [ed for ed in edges if ed[0] == t]
        rgsum = mip.xsum(m.var_by_name(str(ed)) for ed in outgoingEdges) + m.var_by_name(
            str((t, -2)))  # Sum of all edges starting in t...
        m += (rgsum == 1)  # is exactly 1

    returnEdge = m.add_var(name="(-2,-1)", var_type=mip.INTEGER, lb=0)
    pulloutSum = mip.xsum(m.var_by_name(str(e)) for e in pullout)
    pullinSum = mip.xsum(m.var_by_name(str(e)) for e in pullin)
    m += (pulloutSum == pullinSum)
    m += (pulloutSum == returnEdge)

    maxval = 2 ** 15
    # and add objective to minimize deadheads
    # 0.001 is added for zero deadheads so we do not pick useless edges
    m.objective = mip.minimize(mip.xsum(
        max(Scheduling_Precalculation.GetDistFromEdgeStr(var.name, trips, stops, dists, depotId, depotVal=maxval),
            0.001) * var for var in
        m.vars))
    print("Minimizing deadhead time:")
    m.optimize()
    print("Minimum deadhead time:", int(m.objective_value))

    print("Number of trips:", str(len(trips)))
    chosenVars = m.vars
    chosenEdges = []

    for cv in chosenVars:
        if abs(cv.x - 1) < 2 ** -4:  # Since they are represented as floats, better be sure
            chosenEdges.append(StrToTuple(cv.name))

    buses: List[List[int]] = [[]]

    chosenEdges.sort(key=lambda x: x[0])

    startingTrips = [trips[v] for u, v in chosenEdges if u == -1 and v != -2]
    endingTrips = [trips[u] for u, v in chosenEdges if v == -2 and u != -1]
    remEdges = [(u, v) for u, v in chosenEdges if u != -1 and v != -2]
    buses = ConvertEdgesToBuses(len(trips), remEdges)
    assert (len(startingTrips) == len(endingTrips))

    schedules = [[trips[x] for x in b] for i, b in enumerate(buses)]
    schedules.sort(key=lambda sched: (sched[0].StartTime, -len(sched)))
    return schedules, startingTrips, endingTrips


def OptimizeTripsFindOptimalDepot(trips: List[Trip], dists: np.ndarray, stops: Dict[str, int],
                                  asTrips: bool = True
                                  ) -> Tuple[Union[List[List[Trip]], List[List[int]]], int, int]:
    """!
        @brief Creates bus schedules based on single depot algorithm
        @param trips List of trips, see Trip class
        @param dists 2D matrix (time distance)
        @param stops Map of stop names to indices in the matrix
        @param depotName Name of the depot (closest match will be found)
        @param asTrips If True, returns list of lists of trips; if False, returns list of lists of trip indices
        @return List of trips or trips indices, and the depot index which should yield the best result
        """

    startTime = time.process_time()
    edges = Scheduling_Precalculation.CreateFeasibilityGraph(
        trips, stops, dists, 24)

    print("Trip count:", len(trips))
    print("Edge count:", len(edges))
    n = len(trips)

    G = nx.Graph()
    # Nodes {0..n-1} correspond to arrival, {n..2n-1} to departure, n=len(trips)
    arrivalRange = range(n)
    departureRange = range(n, 2 * n)
    G.add_nodes_from(arrivalRange)
    G.add_nodes_from(departureRange)
    # Edges: Arrival x Departure

    G.add_weighted_edges_from(
        (ta, td + n,
         Scheduling_Precalculation.GetDistFromEdge((ta, td), trips, stops, dists))
        for ta, td in edges)
    print("Graph created with weights")
    # Find maximum cardinality matching (the graph may be disconnected)
    matching = nx.bipartite.maximum_matching(G, top_nodes=arrivalRange)
    print("Matching found")
    # Read chained trips from matching - only take tuples with lower node, as the matching returns both directions
    chosenEdges = sorted([(a, d - n) for a, d in matching.items() if a in arrivalRange and d in departureRange])
    buses = ConvertEdgesToBuses(len(trips), chosenEdges)
    m = len(buses)
    print("Amount of buses:", m)
    # Nodes {2n..2n+m-1} correspond to pull-out, {2n+m..2n+2m-1} to pull-in, m=len(buses)
    pullOutRange = range(2 * n, 2 * n + m)
    pullInRange = range(2 * n + m, 2 * n + 2 * m)
    G.add_nodes_from(pullOutRange)
    G.add_nodes_from(pullInRange)
    G.add_weighted_edges_from((b, d, 0) for b in pullOutRange for d in departureRange)
    G.add_weighted_edges_from((a, b, 0) for a in arrivalRange for b in pullInRange)

    matching = nx.bipartite.minimum_weight_full_matching(G)

    chainEdges = sorted([(a, d - n) for a, d in matching.items() if a in arrivalRange and d in departureRange])
    pullOutEdges = sorted([(b, d) for b, d in matching.items() if b in pullOutRange])
    pullInEdges = sorted([(a, b) for a, b in matching.items() if b in pullInRange])
    assert (len(pullOutEdges) == len(pullInEdges))
    assert (len(pullOutEdges) == m)
    assert (len(chosenEdges) + len(pullOutEdges) == len(trips))
    # here we ignore the pull-out and pull-in edges so we can recycle the default matching fn
    buses = ConvertEdgesToBuses(len(trips), chainEdges)
    initTime = time.process_time()
    print(f"Initial solution in {int((initTime-startTime)*1000)} ms")

    # Look at the first and last trip for each bus, and find which depot will have the best sum of deadheads
    def evalDepot(depotId):
        return sum(Scheduling_Precalculation.GetDistFromEdge(
            (b[0], -1), trips, stops, dists, depotId) +
                   Scheduling_Precalculation.GetDistFromEdge(
                       (b[-1], -2), trips, stops, dists, depotId)
                   for b in buses)

    depotIdxToValue = {depotId: evalDepot(depotId) for depotId in stops.values()}
    bestDepotHeur = min(depotIdxToValue, key=depotIdxToValue.get)
    results = {}
    for depotId in depotIdxToValue:
        st1 = time.process_time()
        # Remove this if you want to take your time calculating
        if depotId != bestDepotHeur: continue
        depotName = next(k for k, v in stops.items() if v == depotId)
        for a in arrivalRange:
            for b in pullInRange:
                G[a][b]["weight"] = Scheduling_Precalculation.GetDistFromEdge(
                    (a, -2), trips, stops, dists, depotId, depotVal=0)
        for b in pullOutRange:
            for d in departureRange:
                G[b][d]["weight"] = Scheduling_Precalculation.GetDistFromEdge(
                    (-1, d - len(trips)), trips, stops, dists, depotId, depotVal=0)
        tempMatching = nx.bipartite.minimum_weight_full_matching(G)
        chainEdges = sorted([(a, d) for a, d in tempMatching.items() if a in arrivalRange and d in departureRange])
        chosenEdges = [(a, d - n) for a, d in chainEdges]
        pullOutEdges = sorted([(b, d) for b, d in tempMatching.items() if b in pullOutRange])
        pullInEdges = sorted([(a, b) for a, b in tempMatching.items() if b in pullInRange])
        result = sum(G[a][b]["weight"] for a, b in pullInEdges) + sum(G[b][d]["weight"] for b, d in pullOutEdges) + \
                 sum(G[a][d]["weight"] for a, d in chainEdges)
        busesTemp = ConvertEdgesToBuses(len(trips), chosenEdges)
        schedules = [[trips[x] for x in b] for i, b in enumerate(busesTemp)]
        results[depotId] = (depotName, result, busesTemp, schedules)
        et1 = time.process_time()
        print(f"Depot {depotId} - {depotName} evaluated in {int((et1 - st1)*1000)} ms")
    endTime = time.process_time()
    bestDepotCalc = min(results, key=lambda x: results[x][1])
    print(f"Fully optimized in {int((endTime - startTime) * 1000)} ms")
    if asTrips:
        schedules = results[bestDepotHeur][3]
    else:
        schedules = results[bestDepotHeur][2]
    return schedules, bestDepotHeur, bestDepotCalc


def OptimizeTripsCircularsExact(trips: List[Trip], dists: np.ndarray, stops: Dict[str, int]) -> List[List[Trip]]:
    # Each bus must end at the same stop where it started
    # Note: As it is exact method with constraints, it is too slow for real models
    """
    Trips - see definition of Trip
    dists - 2d matrix (time distance)
    stops - list of stops, correspond to matrix headers
    depot - If none, the buses can start and end anywhere (can add final DH trip); if specified, all buses must start at the specified stop
    Note: if the depot is not a terminal it will not be present in the list; the name does not have to be accurate, closest is found by edit distance
    """

    # Use easy (polynomial) optimization: we have no depot, buses can start and end anywhere, no driver limits
    edges = Scheduling_Precalculation.CreateFeasibilityGraph(trips, stops, dists, 24)

    defaultSolution = OptimizeTripsOptionalDepot(trips, dists, stops, None, asTrips=False)

    print("Default solution:", defaultSolution)
    m = mip.Model(sense=mip.MINIMIZE, solver_name=mip.CBC)
    buscount = len(defaultSolution)
    m = mip.Model(solver_name=mip.CBC)

    _ = [m.add_var(name=f"B{b},{u},{v}", var_type=mip.BINARY) for b in range(buscount) for u, v in edges]
    # back_edges = CreateReturningFeasibilityGraph(trips,stops,dists)
    back_edges = [(v, u) for u, v in edges] + [(t, t) for t in range(len(trips))]
    back_edges = [(u, v) for u, v in back_edges if trips[v].StartTimeMins + 24 * 60 >= trips[u].EndTimeMins]

    _ = [m.add_var(name=f"B{b},{u},{v}", var_type=mip.BINARY)
         for b in range(buscount) for u, v in back_edges]

    # Initialize the default solution
    startEdges = {f"B{b},{defaultSolution[b][i - 1]},{defaultSolution[b][i]}": 1
                  for b in range(buscount) for i in range(len(defaultSolution[b]))}
    startZeroes = {f"B{b},{u},{v}": 0
                   for b in range(buscount) for u, v in edges + back_edges
                   if f"B{b},{u},{v}" not in startEdges.keys()}
    startAll = sorted(list(startEdges.items()) + list(startZeroes.items()),
                      key=lambda x: (int(x[0].split(',')[0][1:]), int(x[0].split(',')[1]), int(x[0].split(',')[2])))
    startx = [(m.var_by_name(s[0]), s[1]) for s in startAll]

    m.start = startx

    # Now we add the constraints

    # Incoming, outgoing edge
    for t in range(len(trips)):
        incomingEdges = [(u, v) for u, v in edges + back_edges if v == t]
        isum = mip.xsum(m.var_by_name(f"B{b},{u},{v}") for b in range(buscount) for u, v in incomingEdges)
        m += (isum == 1)

        outgoingEdges = [(u, v) for u, v in edges + back_edges if u == t]
        osum = mip.xsum(m.var_by_name(f"B{b},{u},{v}") for b in range(buscount) for u, v in outgoingEdges)
        m += (osum == 1)

    # One back edge per bus
    for b in range(buscount):
        besum = mip.xsum(m.var_by_name(f"B{b},{u},{v}") for u, v in back_edges)
        m += (besum <= 1)

    # Incoming and outgoing edge have the same bus (this turns the problem into a constraint programming)
    for t in range(len(trips)):
        incomingEdges = [(u, v) for u, v in edges + back_edges if v == t]
        outgoingEdges = [(u, v) for u, v in edges + back_edges if u == t]
        for b in range(buscount):
            sumin = mip.xsum(m.var_by_name(f"B{b},{u},{v}") for u, v in incomingEdges)
            sumout = mip.xsum(m.var_by_name(f"B{b},{u},{v}") for u, v in outgoingEdges)
            m += (sumin == sumout)
        # print(sumin,sumout)

    m.objective = 0
    # and add objective to minimize deadheads
    m.objective = mip.minimize(mip.xsum(Scheduling_Precalculation.GetDistFromEdgeStr(
        f"({var.name.split(',')[1]},{var.name.split(',')[2]})", trips, stops, dists
    ) * var for var in m.vars))
    # m.max_seconds = 300

    # m.write("model.lp")
    currtime = time.process_time()

    status = m.optimize()
    if status == mip.OptimizationStatus.NO_SOLUTION_FOUND or status == mip.OptimizationStatus.INFEASIBLE:
        with open("model.sol", "w+", encoding="utf-8") as f:
            for var in m.vars:
                f.write(f"{var.name} {(var.x)}\n")
            f.write(f"{m.objective_value}\n")
        raise Exception("No solution found")
    with open("model.sol", "w+", encoding="utf-8") as f:
        for var in m.vars:
            if var.x >= 1 - (2 ** -4):
                f.write(f"{var.name} {int(var.x)}\n")
        f.write(f"{m.objective_value}\n")

    print("\nMinimum deadhead time:", m.objective_value)
    print("Time taken:", time.process_time() - currtime)
    print(m.num_solutions)
    currtime = time.process_time()

    print("Number of trips:", str(len(trips)))
    chosenVars = m.vars

    combinations = []
    for i in range(len(chosenVars)):
        if abs(chosenVars[i].x - 1) < 2 ** -4:  # Since they are represented as floats, better be sure
            combinations.append(chosenVars[i].name)

    buses = [set() for b in range(buscount)]
    for c in combinations:
        b, f, t = c.split(',')
        b = b[1:]
        buses[int(b)].add(int(f))
    buses = [sorted(list(bs)) for bs in buses]
    # print(buses)
    schedules = [[trips[x] for x in buses[i]] for i in range(len(buses))]
    return schedules


def OptimizeTripsCircularApprox(trips: List[Trip], dists: np.ndarray, stopsMap: Dict[str, int], asTrips=True,
                                iterations=100, kept=30, multiplications=5) -> List[List[Trip]]:
    # Each bus must end at the same stop where it started
    # Tries only to approximate the exact solution local search
    """
    Trips - see definition of Trip
    dists - 2d matrix (time distance)
    stops - list of stops, correspond to matrix headers
    """
    startTime = time.process_time()
    # Find exact solution if we did not consider back trips
    # defaultSolution = OptimizeTripsOptionalDepot(trips, dists, stopsMap, None, asTrips=False)
    defaultSolution, bestDepotQuick, bestDepotSlow = OptimizeTripsFindOptimalDepot(trips, dists, stopsMap,
                                                                                   asTrips=False)
    buses = defaultSolution

    print("Default solution found")

    length = EvaluateLength(defaultSolution, trips, dists, stopsMap)
    print("Total deadhead time:", length)

    # Now let's consider the optimization
    edges = Scheduling_Precalculation.CreateFeasibilityGraph(trips, stopsMap, dists, 24)
    edgesWeights = Scheduling_Precalculation.CreateDeadheadMap(edges, trips, stopsMap, dists)
    for u, v in edges:
        dist = Scheduling_Precalculation.GetDistFromEdge((v, u), trips, stopsMap, dists)
        edgesWeights[(v, u)] = dist
    sedges, edges = set(edges), None  # Set for quicker feasibility func
    # Find swappable edges: (busIndex1, tripIndex1, busIndex2, tripIndex2)
    # Trip a1: schedules[busIndex1][tripIndex1]
    # Trip a2: schedules[busIndex1][tripIndex1]+1
    # Trip b1: schedules[busIndex2][tripIndex2]
    # Trip b2: schedules[busIndex2][tripIndex2]+1
    # Edge (a1,a2) and (b1,b2) must always exist
    # Edge (a1,b2) and (b1,a2) must exist if we want to swap
    possibleSwaps = set()
    for busIndex1, bus1 in enumerate(buses):
        for busIndex2 in range(busIndex1 + 1, len(buses)):
            assert busIndex1 != busIndex2
            bus2 = buses[busIndex2]
            for tripIndex1 in range(-1, len(bus1)):
                a1 = bus1[tripIndex1] if tripIndex1 >= 0 else None
                a2 = bus1[tripIndex1 + 1] if tripIndex1 + 1 < len(bus1) else None
                assert (a1 is None or a2 is None or (a1, a2) in sedges)
                for tripIndex2 in range(-1, len(bus2)):
                    b1 = bus2[tripIndex2] if tripIndex2 >= 0 else None
                    b2 = bus2[tripIndex2 + 1] if tripIndex2 + 1 < len(bus2) else None
                    assert (b1 is None or b2 is None or (b1, b2) in sedges)
                    # If we use none then max one can be none
                    if (sum(1 for item in (a1, a2, b1, b2) if item is None) > 1) \
                            or (b1 is not None and a2 is not None and (b1, a2) not in sedges) \
                            or (a1 is not None and b2 is not None and (a1, b2) not in sedges):
                        continue

                    possibleSwaps.add((busIndex1, tripIndex1, busIndex2, tripIndex2))

    solutions = [(None, buses, length, possibleSwaps)]
    swapCount = 0
    while swapCount < iterations:
        try:
            newSolutions = solutions.copy()
            proposedSolutions = []

            for _, buses, length, possibleSwaps in solutions:
                # We do random sampling from dictionary keys
                multiSol = sorted(random.sample(
                    range(len(possibleSwaps)), min(multiplications, len(possibleSwaps)))
                )
                msi = 0
                chosenIdx = multiSol[msi]
                swapSols = []
                for idx, swap in enumerate(possibleSwaps):
                    if idx != chosenIdx:
                        continue
                    msi += 1
                    swapSols.append(swap)
                    if msi >= len(multiSol):
                        break
                    chosenIdx = multiSol[msi]
                    # -----
                for swap in swapSols:
                    # currentBuses,currentLength,currentSwappableEdges = buses.copy(),length,possibleSwaps.copy()
                    bus1I, trip1I, bus2I, trip2I = swap
                    # What we do now: first we swap the buses
                    # bus1 = currentBuses[bus1I]
                    # bus2 = currentBuses[bus2I]
                    bus1 = buses[bus1I]
                    bus2 = buses[bus2I]
                    a1 = bus1[trip1I] if trip1I >= 0 else None
                    a2 = bus1[trip1I + 1] if trip1I + 1 < len(bus1) else None
                    b1 = bus2[trip2I] if trip2I >= 0 else None
                    b2 = bus2[trip2I + 1] if trip2I + 1 < len(bus2) else None
                    swd = EvaluateSwapDiffShort(bus1, bus2, a1, a2, b1, b2, edgesWeights)
                    newValue = length + swd
                    proposedSolutions.append((swap, buses, newValue, possibleSwaps))

            newSolutions += proposedSolutions

            newSolutions.sort(key=lambda ns: ns[2])
            swapCount += 1
            print("Iteration no:", swapCount)
            print(f"Solution range: {newSolutions[0][2]} - {newSolutions[-1][2]}")
            # Enable for weighted roulette
            weighted = False
            if weighted:
                solutions = [newSolutions[0]]  # Always keep the best one
                newSolutions = newSolutions[1:]
                if newSolutions and kept > 1:
                    maxLength = newSolutions[-1][2]
                    weights = [maxLength + 1 - n[2] for n in newSolutions]
                    for _ in range(kept):
                        if not weights:
                            break
                        idx = SelectRandomWeightedIdx(weights)
                        solutions.append(newSolutions[idx])

                        # Compress the list in constant time
                        newSolutions[idx] = newSolutions[-1]
                        newSolutions.pop()
                        weights[idx] = weights[-1]
                        weights.pop()
            else:
                # Reduce solutions by a factor of N twice: first by random, then by best
                solutions = [newSolutions[0]]  # Always keep the best one
                # kept*N*N=len(solutions) => n=sqrt(solutions/kept)
                lns = len(newSolutions) - 1
                if kept > 1:
                    n = math.sqrt(lns / (kept - 1))
                    n = max(n, 1)
                    randomlyChosen = random.sample(newSolutions[1:], int(lns / n))
                    bestRandoms = sorted(randomlyChosen, key=lambda ns: ns[2])[:kept - 1]
                    solutions += bestRandoms
            # Now we create the new solutions for the new iteration
            for i, s in enumerate(solutions):
                swap, buses, currentLength, possibleSwaps = s
                currentBuses, currentSwappableEdges = buses.copy(), possibleSwaps.copy()
                if not swap:
                    solutions[i] = (None, currentBuses, currentLength, currentSwappableEdges)
                    continue
                bus1I, trip1I, bus2I, trip2I = swap
                # What we do now: first we swap the buses
                bus1 = currentBuses[bus1I]
                bus2 = currentBuses[bus2I]
                # Swap them and replace
                busA = bus1[:trip1I + 1] + bus2[trip2I + 1:]
                busB = bus2[:trip2I + 1] + bus1[trip1I + 1:]
                assert (len(busA) + len(busB) == len(bus1) + len(bus2))
                currentBuses[bus1I] = busA
                currentBuses[bus2I] = busB
                # Remove all swappable edges for these currentBuses
                currentSwappableEdges = {e for e in currentSwappableEdges
                                         if not (e[0] == bus1I or e[0] == bus2I or e[2] == bus1I or e[2] == bus2I)}
                # And re-create (basically copying the code from above, just for our two buses)
                ourBuses = [(bus1I, busA), (bus2I, busB)]
                for bus1I, bus1 in ourBuses:
                    for tripIndex1 in range(-1, len(bus1)):
                        a1 = bus1[tripIndex1] if tripIndex1 >= 0 else None
                        a2 = bus1[tripIndex1 + 1] if tripIndex1 + 1 < len(bus1) else None
                        assert (a1 is None or a2 is None or (a1, a2) in sedges)
                        for bus2I, bus2 in enumerate(currentBuses):
                            if bus2I in (ourBuses[0][0], ourBuses[1][0]):
                                continue
                            for tripIndex2 in range(-1, len(bus2)):
                                b1 = bus2[tripIndex2] if tripIndex2 >= 0 else None
                                b2 = bus2[tripIndex2 + 1] if tripIndex2 + 1 < len(bus2) else None
                                assert (b1 is None or b2 is None or (b1, b2) in sedges)
                                # If we use none then max one can be none
                                if (sum(1 for item in (a1, a2, b1, b2) if item is None) > 1) \
                                        or (b1 is not None and a2 is not None and (b1, a2) not in sedges) \
                                        or (a1 is not None and b2 is not None and (a1, b2) not in sedges):
                                    continue
                                currentSwappableEdges.add((bus1I, tripIndex1, bus2I, tripIndex2))
                solutions[i] = (None, currentBuses, currentLength, currentSwappableEdges)
            solutions.sort(key=lambda ss: (ss[2], random.random()))  # For multiple local optima select randomly

        except KeyboardInterrupt:
            break
        except Exception as e:
            # get context
            exc_type, exc_obj, tb = sys.exc_info()
            print(f"Error in iteration {swapCount}:", e, "at line", tb.tb_lineno)
            raise
    _, buses, length, _ = solutions[0]
    endTime = time.process_time()
    print(f"Total time taken: {int((endTime - startTime) * 1000)} ms")
    print("Iterations:", swapCount, "Total:", length)
    buses.sort(key=lambda b: (-len(b), b[0]))
    if asTrips:
        return [[trips[x] for x in b] for b in buses]
    else:
        return buses


def EvaluateLength(buses: List[List[int]], trips: List[Trip], dists: np.ndarray, stopsMap: Dict[str, int]) -> int:
    val = sum(
        (Scheduling_Precalculation.GetDistFromEdge((bus[i - 1], bus[i]), trips, stopsMap, dists)
         ) for bus in buses for i in range(len(bus)))
    return val


def EvaluateSwapDiffShort(bus1, bus2, a1, a2, b1, b2, edgeWeights):
    # AX AY | BX BY -> AX BY | BX AY
    oldChain1 = edgeWeights.get((a1, a2), 0)
    oldChain2 = edgeWeights.get((b1, b2), 0)
    oldReturn1 = edgeWeights.get((bus1[-1], bus1[0]), 0)
    oldReturn2 = edgeWeights.get((bus2[-1], bus2[0]), 0)
    sumOld = oldChain1 + oldReturn1 + oldChain2 + oldReturn2

    # Chain here is automatically 0 if the trip is None
    newChain1 = edgeWeights.get((a1, b2), 0)
    newChain2 = edgeWeights.get((b1, a2), 0)
    newReturn1 = edgeWeights.get((bus2[-1], bus1[0]), 0)
    newReturn2 = edgeWeights.get((bus1[-1], bus2[0]), 0)
    # Special cases for degenerate splits
    if a1 is None:
        # (AX) AY | BX BY -> (AX) BY | BX AY
        newReturn1 = edgeWeights.get((bus2[-1], b2), 0)
    if a2 is None:
        # AX (AY) | BX BY -> AX BY | BX (AY)
        newReturn2 = edgeWeights.get((b1, bus2[0]), 0)
    if b1 is None:
        # AX AY | (BX) BY -> AX BY | (BX) AY
        newReturn2 = edgeWeights.get((bus1[-1], a2), 0)
    if b2 is None:
        # AX (AY) | BX (BY) -> AX (BY) | BX AY
        newReturn1 = edgeWeights.get((a1, bus1[0]), 0)
    # AX AY | BX BY -> AX BY | BX AY
    sumNew = newChain1 + newReturn1 + newChain2 + newReturn2
    return sumNew - sumOld


def EvaluateSwapDiff(buses, e1, e2, edgesWeight, trips, stops, dists) -> int:
    tripId, nextTripId, busNo, tripNo = e1
    tripId2, nextTripId2, busNo2, tripNo2 = e2

    # Calculate difference only due to swapped edges and last trips
    bus1current = edgesWeight[(buses[busNo][tripNo], buses[busNo][tripNo + 1])] if tripNo < len(buses[busNo]) - 1 else 0
    bus1circle = edgesWeight.get((buses[busNo][-1], buses[busNo][0]),
                                 Scheduling_Precalculation.GetDistFromEdge((buses[busNo][-1], buses[busNo][0]), trips,
                                                                           stops,
                                                                           dists))
    # Order swapped because of symmetry allowing us to consider the forward edge
    bus2current = edgesWeight[(buses[busNo2][tripNo2], buses[busNo2][tripNo2 + 1])] if tripNo2 < len(
        buses[busNo2]) - 1 else 0
    bus2circle = edgesWeight.get((buses[busNo2][-1], buses[busNo2][0]),
                                 Scheduling_Precalculation.GetDistFromEdge((buses[busNo2][-1], buses[busNo2][0]), trips,
                                                                           stops, dists))

    sumnow = bus1current + bus2current + bus1circle + bus2circle

    # Find how much this changes when edges get swapped
    bus1new = edgesWeight[(buses[busNo][tripNo], buses[busNo2][tripNo2 + 1])] if tripNo2 < len(
        buses[busNo2]) - 1 else 0  # Current 1 Next 2
    bus1circlen = edgesWeight.get((buses[busNo][-1], buses[busNo2][0]),
                                  Scheduling_Precalculation.GetDistFromEdge((buses[busNo][-1], buses[busNo2][0]), trips,
                                                                            stops,
                                                                            dists))  # Last 2 First 1
    bus2new = edgesWeight[(buses[busNo2][tripNo2], buses[busNo][tripNo + 1])] if tripNo < len(
        buses[busNo]) - 1 else 0  # Current 2 Next 1
    bus2circlen = edgesWeight.get((buses[busNo2][-1], buses[busNo][0]),
                                  Scheduling_Precalculation.GetDistFromEdge((buses[busNo2][-1], buses[busNo][0]), trips,
                                                                            stops,
                                                                            dists))  # Last 1 First 2

    sumnext = bus1new + bus2new + bus1circlen + bus2circlen
    return sumnext - sumnow


def CalculateGeneral(allTrips: List[Trip], stops: List[str], distances: np.ndarray,
                     schedulingMethod: str, scheduleArgs: dict):
    stopsMap = {s: i for i, s in enumerate(stops)}
    try:
        if schedulingMethod == "default":
            schedules = OptimizeTripsOptionalDepot(allTrips, distances, stopsMap, None, True)
            schedules = EvaluateSchedules(schedules, stopsMap, distances, schedulingMethod, scheduleArgs)
        elif schedulingMethod == "depot":
            depot = scheduleArgs.get("depot")
            if not depot:
                raise ValueError("No depot specified")
            closestDepotNames = difflib.get_close_matches(depot, stops)
            if not closestDepotNames:
                raise ValueError(f'Depot "{depot}" not found')
            depotName = closestDepotNames[0]
            depotIdx = stopsMap[depotName]
            schedules = OptimizeTripsOptionalDepot(allTrips, distances, stopsMap, depotIdx, True)
            schedules = EvaluateSchedules(schedules, stopsMap, distances, schedulingMethod, scheduleArgs)
        elif schedulingMethod == "circular":
            iterations = scheduleArgs.get("iterations", 100)
            samples = scheduleArgs.get("samples", 10)
            multiplications = scheduleArgs.get("multiplications", 5)
            schedules = OptimizeTripsCircularApprox(allTrips, distances, stopsMap, True, iterations, samples,
                                                    multiplications)
            schedules = EvaluateSchedules(schedules, stopsMap, distances, schedulingMethod, scheduleArgs)
        else:
            raise ValueError("Unknown scheduling mode")
    except Exception as e:
        print("Error:", e)
        exc_type, exc_obj, tb = sys.exc_info()
        print("Error at line", tb.tb_lineno)
        print("Error in", exc_type)
        raise
    return schedules


def EvaluateSchedules(schedule: List[List[Trip]], stops: Dict[str, int], distanceMatrix: np.ndarray,
                      schedulingMethod: str, scheduleArgs: Dict[str, Any]) -> Dict[str, Any]:
    """!
    @brief Evaluate time data for schedules
    @schedule The scheduled trips
    @stops Dictionary of stop names to indices
    @distanceMatrix Array of deadhead distances between stops
    @depotIdx Index of the depot, can be -1 if no depot, and -2 if you want to include turnaround trip
    @countLastReturn If True, the last trip deadhead time will be counted as returning to the first stop
    @scheduleArgs Additional arguments
    @return Dictionary, where keys are data (waiting time, deadhead), values are dictionaries with key for bus and total value
    """
    if schedulingMethod not in ["default", "depot", "circular"]:
        raise ValueError("Unknown scheduling mode")
    res = {"Scheduling method": schedulingMethod}
    res.update({k: v for k, v in scheduleArgs.items()})
    depot = scheduleArgs.get("depot")
    blocks = []
    for busNo, busBlock in enumerate(schedule, 1):
        # converting to int from numpy array
        tripTimes = [int(trip.EndTimeMins - trip.StartTimeMins) for trip in busBlock]
        tripTimeTotal = sum(tripTimes)
        deadheadTimes = [int(distanceMatrix[stops[busBlock[i].EndStop]]
                             [stops[busBlock[i + 1].StartStop]])
                         for i in range(len(busBlock) - 1)]
        deadheadTimeTotal = sum(deadheadTimes)
        waitingTimes = [int(busBlock[i + 1].StartTimeMins -
                            (busBlock[i].EndTimeMins + deadheadTimes[i]))
                        for i in range(len(busBlock) - 1)]
        waitingTimeTotal = sum(waitingTimes)
        trips = [trip.ToDictForJson() for trip in busBlock]
        for i in range(len(busBlock) - 1):
            trips[i].update({
                "Trip time": tripTimes[i],
                "Waiting time": waitingTimes[i],
                "Deadhead time": deadheadTimes[i],
            })
        trips[-1].update({"Trip time": tripTimes[-1]})

        lastTrip = busBlock[-1]
        firstTrip = busBlock[0]
        returnTime = int(distanceMatrix[stops[lastTrip.EndStop]][stops[firstTrip.StartStop]])
        waitingTime = int((firstTrip.StartTimeMins - (lastTrip.EndTimeMins + returnTime)) % (24 * 60))
        # Overlap to the next day

        if schedulingMethod == "circular":
            deadheadTimeTotal += returnTime
        if not depot:
            pullOut = None
            pullIn = None
            lastReturn = {
                "Start stop": lastTrip.EndStop,
                "End stop": firstTrip.StartStop,
                "Return time": returnTime,
                "Reserve time": waitingTime,
            }
        else:
            lastReturn = None
            pullOutTime = int(distanceMatrix[stops[depot]][stops[firstTrip.StartStop]])
            deadheadTimeTotal += pullOutTime

            pullOut = {
                "Depot": depot,
                "First departure": firstTrip.StartStop,
                "Pull-out time": pullOutTime
            }
            pullInTime = int(distanceMatrix[stops[lastTrip.EndStop]][stops[depot]])
            deadheadTimeTotal += pullInTime
            pullIn = {
                "Depot": depot,
                "Last arrival": lastTrip.EndStop,
                "Pull-in time": pullInTime
            }
        busDict = {
            "Bus number": busNo,
            "Pull-out": pullOut,
            "Trips": trips,
            "Pull-in": pullIn,
            "Turn-around": lastReturn,
            "Total trip time": tripTimeTotal,
            "Total deadheading time": deadheadTimeTotal,
            "Total waiting time": waitingTimeTotal,
        }
        blocks.append(busDict)

    res["Bus schedules"] = blocks
    res["Global trip time"] = sum(bus["Total trip time"] for bus in blocks)
    res["Global deadhead time"] = sum(bus["Total deadheading time"] for bus in blocks)
    res["Global waiting time"] = sum(bus["Total waiting time"] for bus in blocks)
    res["Global trip count"] = sum(len(bus["Trips"]) for bus in blocks)
    return res


def main(argv):
    parser = argparse.ArgumentParser(description="Visualizer of schedules on map")

    parser.add_argument("tripsFile", help="File with trips per each day (json)", action="store")
    parser.add_argument("distancesFile", help="File with distances between terminal stops (matrix)", action="store")
    parser.add_argument("outputFile", help="Where to print the schedules", action="store")

    parser.add_argument("-d", "--depot", help="Common depot (first and last stop for each bus)", action="store")
    parser.add_argument("-c", "--circular",
                        help="Optimize trips in circular manner (first stop of each bus is also its last stop)",
                        action="store_true")

    parser.add_argument("-i", "--iterations", help="Number of iterations for circle optimization", action="store",
                        default=100, type=int)
    parser.add_argument("-k", "--kept", help="Number of instances per iteration for circle optimization",
                        action="store", default=30, type=int)
    parser.add_argument("-m", "--multiplications", help="Number of multiplications for circle optimization",
                        action="store",
                        default=5, type=int)

    args = parser.parse_args(argv[1:])

    tripsFile = args.tripsFile
    distancesFile = args.distancesFile
    outputFile = args.outputFile
    depot = args.depot
    circular = args.circular

    if args.depot and args.circular:
        print("Depot and circular options are mutually exclusive")
        parser.print_help()
        return
    trips = Scheduling_Precalculation.ReadTripsJson(tripsFile)
    trips.sort(key=lambda x: x.StartTimeMins)
    distances, stops = ReadDistanceMatrix(distancesFile)

    os.makedirs("Schedules", exist_ok=True)

    schedules = None

    if depot:
        closestDepotNames = difflib.get_close_matches(depot, stops)
        if not closestDepotNames:
            raise ValueError(f'Depot "{depot}" not found')
        depotName = closestDepotNames[0]
        depotIdx = stops[depotName]
        print(f"Optimizing trips with depot '{depotName}'")
        estimate = Scheduling_Precalculation.EstimateTripsNoDepot(trips, distances, stops)
        print(estimate)
        schedules = OptimizeTripsOptionalDepot(trips, distances, stops, depotIdx)
    else:
        if circular:
            print("Optimizing trips in circular manner")
            estimate = Scheduling_Precalculation.EstimateTripsNoDepot(trips, distances, stops)
            print(estimate)
            schedules = OptimizeTripsCircularApprox(trips, distances, stops, True, args.iterations, args.kept,
                                                    args.multiplications)
        else:
            print("Optimizing trips quickly without depot")
            estimate = Scheduling_Precalculation.EstimateTripsNoDepot(trips, distances, stops)
            print(estimate)
            schedules = OptimizeTripsOptionalDepot(trips, distances, stops)

    with open(outputFile, "w+", encoding="utf-8") as f:
        json_schedule = json.dumps(schedules, default=lambda o: o.toDictForJson(), ensure_ascii=False, indent=True)
        f.write(json_schedule)

    formattedSchedules, deadheads = FormatSchedule(schedules, distances, stops, True, depot)
    tabularSchedules = TableSchedules(formattedSchedules)
    PrintTabularSchedules(tabularSchedules, deadheads)


if __name__ == "__main__":
    # cProfile.run("main()")
    main(sys.argv)
