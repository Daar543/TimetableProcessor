#!/usr/bin/env python3

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Tuple

import geopy.distance
import matplotlib.pyplot as plt
import mplleaflet
import numpy as np

from Map_Visualization import Stops
from Map_Visualization import StopsSearcher


def ReadTrips(tripsFile):
    with open(tripsFile, "r", encoding="utf_8") as f:
        json_data = json.load(f)
    return json_data


def ReadStopLocations(stops, stopsFile):
    loadedStops = {}
    with open(stopsFile, "r", encoding="utf_8") as f:
        reader = csv.reader(f, delimiter=',')
        for row in reader:
            if not row:
                continue
            try:
                loadedStop = Stops.StopWithLocation(*row)
            except ValueError:
                continue
            except TypeError as e:
                print(row)
                raise e
            stopName = loadedStop.GetName()
            loadedStops[stopName] = loadedStop
    stopLocs = {}
    failedStops = []
    for stop in stops:
        stopData = loadedStops.get(stop)
        if not stopData:
            failedStops.append(stop)
        else:
            stopLocs[stop] = (stopData.Latitude, stopData.Longitude)
    return stopLocs, failedStops


# def ShowBusRoute(trips):

def GetLineLength(p1: Tuple[int, int], p2: Tuple[int, int]):
    return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5


def GetGpsLength(p1: Tuple[int, int], p2: Tuple[int, int]):
    length = geopy.distance.geodesic(p1, p2)
    return length.km


def PerpendicularBisector(x1, y1, x2, y2, returnZero=True):
    xm, ym = ((x1 + x2) / 2), ((y1 + y2) / 2)
    if y1 == y2:
        if returnZero:
            return None, None, xm, ym
        else:
            raise ZeroDivisionError
    slop = (y2 - y1) / (x2 - x1)

    a = -1 / slop
    b = -a * xm + ym
    assert (abs(a * xm + b - ym) < 0.00001)
    return a, b, xm, ym


def MakeBezier(p1: Tuple[float, float], p2: Tuple[float, float], p3: Tuple[float, float], samples: int) \
        -> Tuple[np.array, np.array]:
    """!
    @brief Make a Bézier curve given three points
    @param p1: First point
    @param p2: Second point
    @param p3: Third point
    @param samples: Number of samples
    @return: sampled x and y coordinates of the curve
    """
    t = np.linspace(0, 1, samples)
    xs_current = (1 - t) ** 2 * p1[0] + 2 * (1 - t) * t * p2[0] + t ** 2 * p3[0]
    ys_current = (1 - t) ** 2 * p1[1] + 2 * (1 - t) * t * p2[1] + t ** 2 * p3[1]
    return xs_current, ys_current


def PlotRoutes(figure, axes, xs, ys, times, styles, tripNos, sameRoutes, thicknessMin=2, thicknessMax=6):
    # Plot routes. If multiple routes have the same coordinates (or they are flipped), then curve them not to overlap
    # https://math.stackexchange.com/questions/983875/equation-of-a-curved-line-that-passes-through-3-points
    # https://stackoverflow.com/questions/71363592/plotting-a-curved-line-between-3-points-with-matplotlib
    # Get the perpendicular bisector, then change x a bit, adjust y accordingly

    if not (len(xs) == len(ys) and len(ys) == len(times) and len(times) == len(styles)):
        raise ValueError("xs, ys, times and styles must have the same length")
    if sameRoutes not in ["overlap", "curve", "parallel"]:
        raise ValueError("sameRoutes must be overlap, curve or parallel")
    marked = [False] * len(xs)
    similar = []
    for i in range(len(xs)):

        # Check how many routes have the same start and end (+tolerance)
        if marked[i]:
            continue
        marked[i] = True
        currentSimilar = [i]
        for j in range(i + 1, len(xs)):
            if marked[j]:
                continue
            if (abs(xs[i][0] - xs[j][0]) < 0.000001 and abs(ys[i][0] - ys[j][0]) < 0.000001 \
                and abs(xs[i][1] - xs[j][1]) < 0.000001 and abs(ys[i][1] - ys[j][1]) < 0.000001) \
                    or (abs(xs[i][0] - xs[j][1]) < 0.000001 and abs(ys[i][0] - ys[j][1]) < 0.000001 \
                        and abs(xs[i][1] - xs[j][0]) < 0.000001 and abs(ys[i][1] - ys[j][0]) < 0.000001):
                currentSimilar.append(j)
                marked[j] = True

        similar.append(currentSimilar)

    colors = plt.cm.gist_rainbow(np.linspace(0, 1, 1440))

    for sims in similar:
        am, bm, xm, ym = PerpendicularBisector(xs[sims[0]][0], ys[sims[0]][0], xs[sims[0]][1], ys[sims[0]][1])
        if am is None or bm is None:  # No bisector = zero length line, would just clutter the plot
            continue
        # Get the offset lines in order of their starting points - it means if trips have literally opposite
        # distances, they will be segregated
        mid = (len(sims) - 1) / 2  # Midpoint for offsets
        sims.sort(key=lambda ind: (xs[ind], ys[ind]))
        x1, y1, x2, y2 = xs[sims[0]][0], ys[sims[0]][0], xs[sims[0]][1], ys[sims[0]][1]
        a = (y2 - y1) / (x2 - x1)
        b = y1 - a * x1
        kmLength = GetGpsLength((x1, y1), (x2, y2))
        lineLength = GetLineLength((x1, y1), (x2, y2))
        if kmLength < 1 / 1000 or lineLength < 0.00001:  # Assert again the line is not super short
            continue

        current_sims = []
        for ind in sims:
            startTime = int((times[ind][0] - datetime.strptime("0:00", "%H:%M")).total_seconds() // 60)
            endTime = int((times[ind][1] - datetime.strptime("0:00", "%H:%M")).total_seconds() // 60)
            timeDelta = endTime - startTime
            if timeDelta < 0: timeDelta += 24 * 60
            timeDelta = max(timeDelta, 1)
            speed = lineLength / (timeDelta * 60)
            width = (thicknessMax - thicknessMin) * max(speed / 80, 1) + thicknessMin  # 80 km/h max speed
            direction = xs[ind][0] < xs[ind][1] \
                         or (xs[ind][0] == xs[ind][1] and ys[ind][0] < ys[ind][1])
            color = colors[startTime]
            current_sims.append((ind, width, direction, color, startTime))

        swapDirection = sum([1 if s[2] else 0 for s in current_sims]) < len(current_sims) / 2
        if swapDirection:
            current_sims = [(i, width, not direction, color, startTime)
                            for i, width, direction, color, startTime in current_sims]
        # Parallel (overlapping) lines are rendered in order top-bottom,
        # while the ones which go left-right are rendered before the ones which go right-left
        current_sims.sort(key=lambda x: (0, x[4]) if x[2] else (1, x[4]))
        if sameRoutes == "overlap":
            startingX = x1
            segmentX = (x2 - x1) / len(current_sims)
            startingY = y1
            segmentY = (y2 - y1) / len(current_sims)
        elif sameRoutes == "parallel":
            totalWidth = sum([width for i, width, direction, color, startTime in current_sims])
            currentWidth = 0
            perp = np.array([-a, 1]) / np.sqrt(a ** 2 + 1)

        for c, (i, width, direction, color, startTime) in enumerate(current_sims):
            """
            c - count of plotted lines so far
            i - index of line
            """
            xs_current, ys_current = [x1, x2], [y1, y2]
            style = styles[i]

            # Only save index as a label, the actual labels will be done after sorting
            label = str(i)

            if style == "deadhead":
                lw, st = 1, ":"
            elif style == "trip":
                lw, st = 1, "-"
            else:
                raise ValueError("Unknown style: " + style)
            offsetFactor = 0

            if sameRoutes == "curve":
                offsetFactor = c - mid
                offsetDist = offsetFactor * lineLength / 10
                xm_current = xm + offsetDist / np.sqrt(1 + am ** 2)
                ym_current = am * xm_current + bm

                xs_current = [x1, xm_current, x2]
                ys_current = [y1, ym_current, y2]
            elif sameRoutes == "parallel":
                offsetFactor = totalWidth / 2 - currentWidth - width / 2
                offsetDist = offsetFactor * 3 / 111000  # 3 meters
                currentWidth += width
                # Move the line in parallel to itself
                disx, disy = offsetDist * perp

                x1_current = x1 + disx
                y1_current = y1 + disy
                x2_current = x2 + disx
                y2_current = y2 + disy
                xs_current = [x1_current, x2_current]
                ys_current = [y1_current, y2_current]

            elif sameRoutes == "overlap":
                xs_current = [startingX + c * segmentX, startingX + (c + 1) * segmentX]
                ys_current = [startingY + c * segmentY, startingY + (c + 1) * segmentY]

            if sameRoutes == "curve" and offsetFactor != 0 and (
                    (xs_current[0], ys_current[0]) != (xs_current[2], ys_current[2])):
                control_points = np.array(
                    [(xs_current[0], ys_current[0]), (xs_current[1], ys_current[1]), (xs_current[2], ys_current[2])]
                )
                num_segments = 20
                xs_current, ys_current = MakeBezier(control_points[0], control_points[1], control_points[2],
                                                    num_segments)
            axes.plot(xs_current, ys_current, color=color,
                      linewidth=width * lw, linestyle=st, label=label)

    return


def ExpandTrips(schedule: List[Dict]):
    newSchedule = []
    for trip in schedule:
        via: List[Dict]
        via = trip.get("Stops")
        if not via:
            newSchedule.append(trip)
            continue
        lastStop = trip["Start stop"]
        lastTime = trip["Start time"]
        for i, v in enumerate(via):
            newTrip = trip.copy()
            newTrip["Start stop"] = lastStop
            newTrip["Start time"] = lastTime
            name, tim = list(via[i].items())[0]
            newTrip["End stop"] = name
            newTrip["End time"] = tim
            del newTrip["Stops"]
            newSchedule.append(newTrip)
            lastStop = name
            lastTime = tim

        newTrip = trip.copy()
        newTrip["Start stop"] = lastStop
        newTrip["Start time"] = lastTime
        newTrip["End stop"] = trip["End stop"]
        newTrip["End time"] = trip["End time"]
        newSchedule.append(newTrip)
    return newSchedule


def main():
    argv = sys.argv
    parser = argparse.ArgumentParser(description="Visualizer of schedules on map")

    parser.add_argument("scheduleFile", help="File with the schedules", action="store")
    parser.add_argument("stopDataSource", help="File to load/save the stop data", action="store")
    parser.add_argument("-l", "--load", help="Load data from file before querying", action="store_true")
    parser.add_argument("-m", "--map-dir", help="Directory to save the map files into", action="store", default="Maps")
    parser.add_argument("-s", "--stops-only", help="Only save the stop data", action="store_true")
    parser.add_argument("-d", "--districts", help="Select districts (kraje) where to find the stops", required=True,
                        action="store", nargs="+")

    args = parser.parse_args(argv[1:])

    schedule_file = args.scheduleFile
    stopDataSource = args.stopDataSource
    districts = args.districts
    load = args.load
    mapDir = args.map_dir
    stopsOnly = args.stops_only
    schedules = ReadTrips(schedule_file)

    tm = time.time()

    wantedStops = set()
    for schedule in schedules["Bus schedules"]:
        for trip in schedule["Trips"]:
            wantedStops.add(trip["Start stop"])
            wantedStops.add(trip["End stop"])
            viastops = trip.get("Stops")
            if viastops:
                for stop in viastops:
                    wantedStops.add(list(stop.keys())[0])
    wantedStops = sorted(list(wantedStops))

    StopInfo = StopsSearcher.FindRespectiveStopsInfo(wantedStops, districts, "kraj", stopDataSource, load)
    if stopsOnly:
        print("Found these stops:")
        for s in StopInfo.keys():
            print(s)
        return

    os.makedirs(mapDir, exist_ok=True)

    # Plot trip for individual bus
    for i in range(len(schedules)):
        schedule = schedules[i]

        fig, ax = plt.subplots(figsize=(20, 10))
        lastStop = None
        lastTime = None
        lastStopInfo = None
        lastTripNo = None

        xs = []
        ys = []
        times = []
        styles = []
        tripNos = []

        schedule = ExpandTrips(schedule)
        schedule += [schedule[0]]  # Plot also the last returning trip
        for j in range(len(schedule)):
            trip = schedule[j]
            # Read from and to stop
            fromStop = trip["Start stop"]
            toStop = trip["End stop"]
            tripNo = f"{trip['Line']}/{trip['Trip']}"

            # Format start and end time
            startTime = datetime.strptime(trip["Start time"], "%H:%M")
            endTime = datetime.strptime(trip["End time"], "%H:%M")

            fromStopInfo = StopInfo.get(fromStop)
            toStopInfo = StopInfo.get(toStop)

            if fromStopInfo is None or toStopInfo is None:
                print(f"Cannot find route from {fromStop} to {toStop}")
                continue

            # Deadhead
            if lastTripNo and lastTripNo != tripNo:
                xs.append((lastStopInfo["lon"], fromStopInfo["lon"]))
                ys.append((lastStopInfo["lat"], fromStopInfo["lat"]))
                times.append((lastTime, startTime))
                styles.append("deadhead")
                tripNos.append(f"{lastTripNo} -> {tripNo}")
            else:
                if lastStopInfo:
                    fromStopInfo = lastStopInfo  # Deal with interrupted subtrips within one trip

            if j < len(schedule) - 1 and lastStopInfo:
                print(fromStop, "->", toStop)

                # Plot the route
                xs.append((lastStopInfo["lon"], toStopInfo["lon"]))
                ys.append((lastStopInfo["lat"], toStopInfo["lat"]))
                times.append((startTime, endTime))
                styles.append("trip")
                tripNos.append(f"{tripNo}")

            lastStop = toStop
            lastStopInfo = toStopInfo
            lastTime = endTime
            lastTripNo = tripNo

        PlotRoutes(fig, ax, xs, ys, times, styles, tripNos, True)
        # mplleaflet cannot deal with legend, so plot it here
        print("Saving as mplleaflet")
        mplleaflet.save_html(fig, os.path.join(mapDir, f"Bus{i + 1}.html"))

        # Screenshot the plot so it can be used offline (no zoom)
        # Using selenium - disabled for now

        print("Creating labels for plot")
        # Eliminate duplicate labels and add both time and trip to each label
        handles, labels = ax.get_legend_handles_labels()
        tempResult = {tripNos[int(l)]: (h, times[int(l)]) for l, h in zip(labels, handles)}
        trts = sorted(tempResult.items(), key=lambda x: x[1][1][0])
        trips = [t[0] for t in trts]
        handles = [t[1][0] for t in trts]
        times = [t[1][1] for t in trts]
        labelNames = [f"{trips[i]} ({times[i][0].strftime('%H:%M')} - {times[i][1].strftime('%H:%M')})" for i in
                      range(len(trips))]

        ax.set_position([0, 0, 1, 1])
        ax.legend(handles, labelNames, loc='center left', bbox_to_anchor=(1, 0.5))

        ax.set_title(f"Bus {i + 1}")
        fig.savefig(os.path.join(mapDir, f"plot_Bus{i + 1}.png"), bbox_inches='tight')

    return


if __name__ == "__main__":
    main()
