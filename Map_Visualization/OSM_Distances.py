#!/usr/bin/env python3

"""!
@file OSM_Distances.py
@namespace OSM_Distances
@brief Functions for downloading OSM data and calculating distances between OSM nodes
"""
import argparse
import math
import os
import pathlib
import sys
import time
from datetime import datetime
from typing import Tuple, List, Dict, Any

import matplotlib.pyplot as plt
import mpllf_remake
import networkx as nx
import osmnx as ox
import numpy as np
from shapely.geometry import Point, LineString, Polygon

from Map_Visualization import Map_Visualizer as mv
from Map_Visualization import StopsSearcher
from JDF_Conversion import Utilities

sys.path.insert(0, os.getcwd())

BOUNDING_AREA_EXPAND = 5 #km


def ChooseDownloadArea(points: List[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    """!
    @brief Choose the area to download from OSM
    @param points: List of points to choose from: each point is a tuple (north, east)
    @return: Bounding north, south, east, west
    """
    north = max(points, key=lambda x: x[0])[0]
    south = min(points, key=lambda x: x[0])[0]
    east = max(points, key=lambda x: x[1])[1]
    west = min(points, key=lambda x: x[1])[1]
    return north, south, east, west


def DownloadOSMDataBox(north: float, south: float, east: float, west: float) -> nx.classes.multidigraph.MultiDiGraph:
    """!
    @brief Download OSM data from OSM
    @param north: Bounding north
    @param south: Bounding south
    @param east: Bounding east
    @param west: Bounding west
    @return: OSM data as graph
    """
    print("Downloading graph. Border coordinates: ", north, south, east, west)
    try:

        graph = ox.graph_from_bbox(north, south, east, west, network_type='drive')
    except Exception as e:
        print(f"Failed to download the graph from OSM: {e}")
        return nx.MultiDiGraph()
    return graph


def ExpandBoundingBox(north, south, east, west, radius: int):
    """!
    @brief Expand bounding box
    @param north: Bounding north
    @param south: Bounding south
    @param east: Bounding east
    @param west: Bounding west
    @param radius: Radius in kilometers
    """
    # Add the radius, with recounting the longitude using haversine formula
    northaw = north + radius / 110.574
    southaw = south - radius / 110.574

    avg_lat = (north + south) / 2
    # For east and west, we need to use the cosine of the latitude
    eastaw = east + radius / (111.320 * math.cos(avg_lat / 180 * math.pi))
    westaw = west - radius / (111.320 * math.cos(avg_lat / 180 * math.pi))

    return northaw, southaw, eastaw, westaw


def DownloadOSMDataCountry(country: str) -> nx.classes.multidigraph.MultiDiGraph:
    """!
    @brief Download OSM data from OSM
    @param country: Country to download
    @return: OSM data
    """
    return ox.graph_from_place(country, network_type='drive')


def GetBoundingBoxFromTwoPoints(p1: Tuple[float, float], p2: Tuple[float, float], radius: int) -> Tuple[
    float, float, float, float]:
    """!
    @brief Get bounding box from two points
    @param p1: First point (x/y)
    @param p2: Second point (x/y)
    @param radius: Radius in kilometers
    @return: Bounding north, south, east, west with added radius
    """
    north = max(p1[1], p2[1])
    south = min(p1[1], p2[1])
    east = max(p1[0], p2[0])
    west = min(p1[0], p2[0])

    northaw, southaw, eastaw, westaw = ExpandBoundingBox(north, south, east, west, radius)

    return northaw, southaw, eastaw, westaw


def DownloadOSMDataTwoPoints(p1: Tuple[float, float], p2: Tuple[float, float],
                             radius: int) -> nx.classes.multidigraph.MultiDiGraph:
    """!
    @brief Download OSM data from OSM
    @param p1: First point (x/y)
    @param p2: Second point (x/y)
    @param radius: Radius in kilometers
    @return: OSM data
    """
    north, south, east, west = GetBoundingBoxFromTwoPoints(p1, p2, radius)

    return ox.graph_from_bbox(north, south, east, west, network_type='drive')


def SaveOSMData(G: nx.classes.multidigraph.MultiDiGraph, file: pathlib.Path) -> None:
    """!
    @brief Save OSM data to file
    @param G: OSM data as graph
    @param file: File to save to
    """
    ox.save_graphml(G, file)


def LoadOSMData(file: pathlib.Path) -> nx.classes.multidigraph.MultiDiGraph:
    """!
    @brief Load OSM data from file
    @return: OSM data as graph
    """
    return ox.load_graphml(file)


def FindDrivingTime(G: nx.classes.multidigraph.MultiDiGraph, start: int,
                    end: int, maximum: int) -> int:
    """!
    @brief Find the driving time between two points
    @param G: OSM data
    @param start: Starting point
    @param end: Ending point
    @param maximum: Maximum value to return if no path is found
    @return: Driving time in seconds
    """
    try:
        travel_time_sec = nx.shortest_path_length(G, start, end, weight="travel_time")
    except nx.NetworkXNoPath:
        travel_time_sec = maximum
    return travel_time_sec


def ReduceSpeedForBus(originalSpeed: float) -> float:
    """!
    @brief Reduce speed for bus
    @param originalSpeed: Original speed
    @return: Reduced speed
    """
    if originalSpeed < 50:
        return originalSpeed * 0.9
    else:
        return originalSpeed * 0.8


def GetDistancesFromMap(stopNamesLocs: Dict[str, Tuple[float, float]]) -> Tuple[List[str], np.ndarray]:
    """!
    @brief Get distances from map
    @param stopNamesLocs: Dictionary mapping stop names to locations
    @return: Stop names and matrix of distances
    """
    timeC = time.process_time()
    limit = 2 ** 15
    # create two lists for stops and locations
    stopNames = list(stopNamesLocs.keys())
    stopLocations = list(stopNamesLocs.values())
    distances = np.ndarray((len(stopLocations), len(stopLocations)), dtype=int)
    distances.fill(limit)

    G = ExtractGraphFromPoints(stopLocations)
    print("Graph downloaded and projected")
    G = ox.add_edge_speeds(G, fallback=50)
    for u, v, key, data in G.edges(keys=True, data=True):
        data['speed_kph'] = ReduceSpeedForBus(data['speed_kph'])
    G = ox.add_edge_travel_times(G)
    print("Graph edges travel times added")
    projectedPoints = [ox.projection.project_geometry(Point((yx[1], yx[0]))) for yx in stopLocations]
    print(f"Finding nearest nodes, node count {len(projectedPoints)}")
    graphPoints = ox.nearest_nodes(G, [p[0].x for p in projectedPoints], [p[0].y for p in projectedPoints])
    print(f"Finding travel times, node count {len(graphPoints)}")
    for i, p1 in enumerate(Utilities.progressBar(graphPoints)):
        travelTimes = nx.single_source_dijkstra_path_length(G, p1, weight="travel_time")
        for j, p2 in enumerate(graphPoints):
            if i == j:
                distances[i][j] = 0
            else:
                distances[i][j] = math.ceil(travelTimes.get(p2,limit*60) / 60)  # mins
    print(f"Distances fully calculated in {int((time.process_time() - timeC) * 1000)} ms")
    return stopNames, distances

def ExtractGraphFromPoints(points: List[Tuple[float, float]], expand:int=0) -> nx.classes.multidigraph.MultiDiGraph:
    """!
    @brief Extract graph from points
    @param points: List of points (lat/lon)
    @return: Graph
    """
    bboxArea = ChooseDownloadArea(points)
    bboxAreaExpanded = ExpandBoundingBox(*bboxArea,expand)
    Gu = DownloadOSMDataBox(*bboxAreaExpanded)
    return ox.project_graph(Gu)

def InterpolateRoutes(points: List[Tuple[float, float]], projectedGraph:nx.MultiDiGraph) \
        -> List[List[Tuple[float, float]]]:
    """!
    @brief Visualize the route going through all points
    @param points: List of points as a tuple (lat/lon)
    @param projectedGraph: OSM graph
    @return: 2D list of (x,y) points on respective routes
    """

    nearestPoints = [min(projectedGraph.nodes,
                          key=lambda n: (projectedGraph.nodes[n]["lon"] - lon) ** 2 +
                                        (projectedGraph.nodes[n]["lat"] - lat) ** 2)
                      for lat,lon in points]
    nearestPoints = [s for s in nearestPoints if s >= 0]

    # Add speed to the edges
    projectedGraph = ox.add_edge_speeds(projectedGraph, fallback=50)
    for u, v, key, data in projectedGraph.edges(keys=True, data=True):
        data['speed_kph'] = ReduceSpeedForBus(data['speed_kph'])
    projectedGraph = ox.add_edge_travel_times(projectedGraph)
    weighed_by = "travel_time"
    weighed_by = "length"

    # For each consecutive pair of points, we find the shortest path
    print("Finding routes")
    routes = [ox.shortest_path(
        projectedGraph, nearestPoints[i], nearestPoints[i + 1], weight=weighed_by
    ) for i in range(len(nearestPoints) - 1)]
    routes_points = []
    for i, r in enumerate(routes):
        routes_points.append([])
        if r:
            for j in r:
                routes_points[i].append((projectedGraph.nodes[j]["lon"], projectedGraph.nodes[j]["lat"]))
        else: # no route found, direct line
            start = nearestPoints[i]
            end = nearestPoints[i + 1]
            routes_points[i] = [(projectedGraph.nodes[start]["lon"], projectedGraph.nodes[start]["lat"]),
                                (projectedGraph.nodes[end]["lon"], projectedGraph.nodes[end]["lat"])]
    return routes_points

def ExtractStopsFromSchedule(busBlocks:List[List[Dict]]) -> List[str]:
    """!
    @brief Extract stops from schedules
    @param schedule: List of bus blocks (each block is a list of trips)
    @return: List of stops
    """
    wantedStops = set()
    for block in busBlocks:
        for trip in block:
            wantedStops.add(trip["Start stop"])
            wantedStops.add(trip["End stop"])
            viastops = trip.get("Stops")
            if viastops:
                for stop in viastops:
                    wantedStops.add(list(stop.keys())[0])
    return sorted(list(wantedStops))

def PlotSchedules(schedules: Dict[Any,List[Dict]], stopLocations: Dict, targetDir: pathlib.Path, trackComplexity: str, sameRoutes: str):
    """!
    @brief Plots schedules as trips on a map, colored by time;
    @brief one plot per bus
    @param schedules List of bus blocks to plot
    @param stopLocations Dictionary of stop locations
    @param targetDir Directory to save the plots to
    @param trackComplexity How to render each route between two stops (either a plain line, or try to be more accurate with OSM); allowed values are "direct" and "navigation"
    @param sameRoutes How to render routes which have the same pair of stops; allowed values are "overlap","parallel","curve"
    """

    if trackComplexity not in ["direct", "navigation"]:
        raise ValueError("trackComplexity must be either 'direct' or 'navigation'")
    if sameRoutes not in ["overlap", "parallel", "curve"]:
        raise ValueError("sameRoutes must be either 'overlap','parallel' or 'curve'")

    projectedGraph = None
    if trackComplexity == "navigation":
        stopList = ExtractStopsFromSchedule(list(schedules.values()))
        #transpose!
        stopLocations = {k: (v[1],v[0]) for k, v in stopLocations.items() if k in stopList}
        projectedGraph = ExtractGraphFromPoints(list(stopLocations.values()), BOUNDING_AREA_EXPAND)

    for i, (blockName,busBlock) in enumerate(schedules.items()):
        if busBlock is None:
            continue

        fig, ax = plt.subplots(figsize=(20, 10))
        lastStop = None
        lastTime = None
        lastStopX = None
        lastStopY = None
        lastStopId = None
        lastTripNo = None

        xs = []
        ys = []
        ids = []
        times = []
        styles = []
        tripNos = []

        busBlock = mv.ExpandTrips(busBlock)
        busBlock += [busBlock[0]]  # Plot also the last returning trip
        for k in range(len(busBlock)):
            trip = busBlock[k]
            # Read from and to stop
            fromStop = trip["Start stop"]
            toStop = trip["End stop"]
            tripNo = f"{trip['Line']}/{trip['Trip']}"

            # Format start and end time
            startTime = datetime.strptime(trip["Start time"], "%H:%M")
            endTime = datetime.strptime(trip["End time"], "%H:%M")

            fromStopX, fromStopY = stopLocations.get(fromStop, (None, None))
            toStopX, toStopY = stopLocations.get(toStop, (None, None))

            if fromStopX is None or toStopX is None:
                print(f"Cannot find route from {fromStop} to {toStop}")
                continue

            # Deadhead
            if lastTripNo and lastTripNo != tripNo:
                xs.append((lastStopX, fromStopX))
                ys.append((lastStopY, fromStopY))
                ids.append((lastStopX, fromStopY))
                times.append((lastTime, startTime))
                styles.append("deadhead")
                tripNos.append(f"{lastTripNo} -> {tripNo}")

            if k < len(busBlock) - 1 and lastStopX:
                # print(fromStop, "->", toStop)

                # Plot the route
                xs.append((lastStopX, toStopX))
                ys.append((lastStopY, toStopY))
                times.append((startTime, endTime))
                styles.append("trip")
                tripNos.append(f"{tripNo}")

            lastStop = toStop
            lastStopX, lastStopY = toStopX, toStopY
            lastTime = endTime
            lastTripNo = tripNo

        # xs = x locations of start and end of each segment
        # ys = y locations of start and end of each segment
        # times = list of tuples, start and end time of each segment

        # Find the area to plot
        x_locs = [x[0] for x in xs]
        y_locs = [y[0] for y in ys]
        points_locations = [(x, y) for x, y in zip(x_locs, y_locs)]
        if trackComplexity == "navigation":
            routes = InterpolateRoutes(points_locations, projectedGraph)
        elif trackComplexity == "direct":
            routes = [[points_locations[i], points_locations[i + 1]]
                      for i in range(len(points_locations) - 1)]
        else:
            raise ValueError("trackComplexity must be either 'direct' or 'navigation'")
        xs_ys_times_styles_tripNos = []
        if not routes:
            continue
        for j, route in enumerate(routes):
            for k in range(len(route) - 1):
                pointStart = route[k]
                pointEnd = route[k + 1]
                xs_ys_times_styles_tripNos.append(
                    ((pointStart[0], pointEnd[0]), (pointStart[1], pointEnd[1]), times[j], styles[j], tripNos[j]))
        if not xs_ys_times_styles_tripNos:
            print(f"Block {blockName} has no routes to plot")
            continue
        xs, ys, times, styles, tripNos = zip(*xs_ys_times_styles_tripNos)
        mv.PlotRoutes(fig, ax, xs, ys, times, styles, tripNos, sameRoutes)
        path = pathlib.Path(targetDir, f"{blockName}.pdf")
        print(f"Saving bus {blockName} block as pdf")
        fig.savefig(path)
        print("Saving as mplleaflet")
        # in mplleaflet/mplexporter/utils.py, change axis._gridOnMajor to axis._major_tick_kw['gridOn']
        try:
            mpllf_remake.save_html(fig, str(pathlib.Path(targetDir, f"{blockName}.html")))
        except Exception as e:
            print(e)
            pass
        plt.close(fig)
    return


def main():
    argv = sys.argv
    parser = argparse.ArgumentParser(description="Visualizer of schedules on map")

    parser.add_argument("scheduleFile", help="File with the schedules", action="store")
    parser.add_argument("stopDataSource", help="File to load/save the stop data", action="store")
    parser.add_argument("-l", "--load", help="Load data from file before querying", action="store_true")
    parser.add_argument("-m", "--map-dir", help="Directory to save the map files into", action="store", default="Maps")
    parser.add_argument("-r", "--regions", help="Select regions (kraje) where to find the stops", required=True,
                        action="store", nargs="+")
    parser.add_argument("-a","--admin", help="Administrative value of the searched region (default 6)",
                        action="store", default=6, type=int)
    parser.add_argument("-s", "--stops-only", help="Only find the stops and write them down", action="store_true")

    args = parser.parse_args(argv[1:])

    schedule_file = args.scheduleFile
    stopDataSource = args.stopDataSource
    regions = args.regions
    admin = args.admin
    load = args.load
    mapDir = args.map_dir
    schedules = mv.ReadTrips(schedule_file)

    wantedStops = set()
    scheduleList = schedules.get("Bus schedules", None)
    if scheduleList is None:
        raise ValueError("Cannot find the Bus schedules key in the file")
    for schedule in scheduleList:
        for trip in schedule["Trips"]:
            wantedStops.add(trip["Start stop"])
            wantedStops.add(trip["End stop"])
            viaStops = trip.get("Stops")
            if viaStops:
                for stop in viaStops:
                    wantedStops.add(list(stop.keys())[0])
    wantedStops = sorted(list(wantedStops))

    stopInfo = StopsSearcher.FindRespectiveStopsInfo(wantedStops, regions, admin, stopDataSource, load)
    print("Stops found")
    if args.stops_only:
        return

    os.makedirs(mapDir, exist_ok=True)

    PlotSchedules(schedules, stopInfo, mapDir,"direct","overlap")

    return


if __name__ == "__main__":
    main()
