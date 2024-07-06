"""!
@file Flask_Query.py
@namespace Flask_Gui
@brief Functions for querying trips
"""

import datetime
import io
import json
import os
import pathlib
from typing import Optional

from flask import Blueprint, render_template, request, redirect, url_for

from Browser_Interface import Flask_Stops
from JDF_Conversion import Utilities, Timetable_Calculations
from JDF_Conversion.Timetable_Calculations import JdfProcessor

root = pathlib.Path("online_files")
# root = pathlib.Path("Browser_Interface/online_files")

jdfRoot = pathlib.Path(root, "upload")

Query_Api = Blueprint('Flask_Query', __name__)


# Form with options
@Query_Api.route('/query/main')
def QueryForm():
    global jdfRoot
    folderNames = [x.name for x in Utilities.GetSubFolders(jdfRoot)]
    # Letters come before numbers, as custom names will be lettered
    folderNames.sort(key=lambda x: (not x[0].isalpha(), x))
    stopNames = Flask_Stops.getSavedStopNames()

    return render_template('query_trips.html',
                           jdfFolderNames=[""] + folderNames,
                           stopNames=stopNames,
                           error=request.args.get("error")
                           )


@Query_Api.route('/query/result', methods=['GET'])
def QueryResult():
    errors = []

    global jdfRoot
    dataFolder = pathlib.Path(jdfRoot)
    arrivalsFolder = pathlib.Path(dataFolder, "temp", "arrivals")
    departuresFolder = pathlib.Path(dataFolder, "temp", "departures")
    # Get the data from the form
    # Assume at least one input is valid, therefore requires JDF parsing
    jdfName = request.args.get("JDF_folder")
    if not jdfName:
        return redirect(url_for("Flask_Query.QueryForm", error="No folder specified"))

    # Check if tripsShow is on
    tripsShowArg = request.args.get('tripsShow')

    tripsFromArg = request.args.get('tripsFrom')
    tripsToArg = request.args.get('tripsTo')
    stopArrArg = request.args.get('arrivals')
    stopDepArg = request.args.get('departures')
    stopArrWhenArg = request.args.get('arrivalsWhen')
    stopDepWhenArg = request.args.get('departuresWhen')

    showTrips = True if tripsShowArg == "on" else False
    if not (
            (showTrips and (tripsFromArg and tripsToArg))
            or (stopArrArg and stopArrWhenArg)
            or (stopDepArg and stopDepWhenArg)
    ):
        return redirect(url_for("Flask_Query.QueryForm", error="Nothing to query"))

    path = pathlib.Path(jdfRoot, jdfName)
    # Parse the folder
    jdfProcesser = Timetable_Calculations.ParseSingleFolder(str(path))
    if not jdfProcesser:
        return redirect(url_for("Flask_Query.QueryForm", error="Folder does not contain all files for the JDF format"))

    trips = []
    maxAmount = 30000
    if showTrips:
        if tripsFromArg and tripsToArg:
            success, res = QueryTrips(jdfName, jdfProcesser,
                                      tripsFromArg, tripsToArg, dataFolder,
                                      False, False, maxAmount)
            if not success:
                errors.append(res)
            else:
                trips = res
        else:
            errors.append("Date range for trips not specified")

    arrivals = []
    if stopArrArg:
        stopArr = stopArrArg
        if stopArrWhenArg:
            success, res = QueryArrivals(jdfProcesser,
                                         stopArr, stopArrWhenArg, arrivalsFolder)
            if not success:
                errors.append(res)
            else:
                arrivals = res
        else:
            errors.append("Date for arrivals not specified")
    departures = []
    if stopDepArg:
        stopDep = stopDepArg
        if stopDepWhenArg:
            success, res = QueryDepartures(jdfProcesser,
                                           stopDep, stopDepWhenArg, departuresFolder)
            if not success:
                errors.append(res)
            else:
                departures = res
        else:
            errors.append("Date for departures not specified")

    trips = unpackTrips(trips)
    departures = UnpackDepartures(departures)
    arrivals = unpackArrivals(arrivals)

    if len(trips) > maxAmount:
        errors.append(f"Too many trips, cut off after reaching {maxAmount}")
    focus = "trips" if trips else "departures" if departures else "arrivals" if arrivals else "trips"  # first non-empty
    rdr = render_template("query_result.html", errors=errors, trips=trips, arrivals=arrivals, departures=departures,
                          focus=focus)
    return rdr


def QueryTrips(jdfName: str, jdfProcesser, startDate, endDate, tripFolder, cacheRead, cacheWrite, maxTrips):
    try:
        startDateDT = datetime.datetime.strptime(startDate, "%Y-%m-%d")
        endDateDT = datetime.datetime.strptime(endDate, "%Y-%m-%d")
    except ValueError as e:
        return False, f"Error: Invalid date format ({e})"
    result = []
    totalTrips = 0
    currDate = startDateDT
    while currDate <= endDateDT:
        if totalTrips > maxTrips:
            break
        resPath = pathlib.Path(tripFolder, f"{jdfName}_{currDate.date()}.json")
        stream = io.StringIO()

        if cacheRead and resPath.exists():
            try:
                with open(resPath, "r+", encoding="utf-8") as f:
                    stream.write(f.read())
            except FileNotFoundError:
                pass

        if stream.getvalue() == "":
            jdfProcesser.CheckTripsInDay(False, currDate.date(), True, stream)
            if cacheWrite:
                os.makedirs(resPath.parent, exist_ok=True)
                with open(resPath, "w+", encoding="utf-8") as f:
                    f.write(stream.getvalue())
        currentTrips = json.loads(stream.getvalue())
        totalTrips += len(currentTrips)
        if len(currentTrips) > 0:
            print(f"Found {len(currentTrips)} trips on {currDate.date()}")
            currDateStr = currDate.strftime("%Y-%m-%d")
            result.append({"Day": currDateStr, "Trips": currentTrips})
        currDate += datetime.timedelta(days=1)
    return True, result


def QueryDepartures(jdfProcesser: JdfProcessor, stopName: str, dateTime: str, cacheFolder: Optional[pathlib.Path]):
    try:
        dtFrom = datetime.datetime.strptime(dateTime, "%Y-%m-%dT%H:%M")
    except ValueError as e:
        return False, f"Error: Invalid date format ({e})"
    dtTo = dtFrom + datetime.timedelta(days=1)
    safeStopName = Utilities.Slugify(stopName)

    stream = io.StringIO()

    # Find the stop
    stop = jdfProcesser.FindStopByName(stopName, "approximate")
    if not stop:
        return False, f"Could not query departures: No stop found close to name '{stopName}'"
    deps = jdfProcesser.GetDeparturesInInterval(stop, dtFrom, dtTo)
    jdfProcesser.WriteDepartures(deps, stream)

    if cacheFolder:
        resPath = pathlib.Path(cacheFolder, f"departures_{safeStopName}.json")
        os.makedirs(resPath.parent, exist_ok=True)
        with open(resPath, "w+", encoding="utf-8") as f:
            f.write(stream.getvalue())

    return True, json.loads(stream.getvalue())


def QueryArrivals(jdfProcesser: JdfProcessor, stopName: str, dateTime: str, cacheFolder: Optional[pathlib.Path]):
    try:
        dtFrom = datetime.datetime.strptime(dateTime, "%Y-%m-%dT%H:%M")
    except ValueError as e:
        return False, f"Error: Invalid date format ({e})"
    dtTo = dtFrom + datetime.timedelta(days=1)
    safeStopName = Utilities.Slugify(stopName)

    stream = io.StringIO()

    # Find the stop
    stop = jdfProcesser.FindStopByName(stopName, "approximate")
    if not stop:
        return False, f"Could not query arrivals: No stop found close to name '{stopName}'"
    arrs = jdfProcesser.GetArrivalsInInterval(stop, dtFrom, dtTo)
    jdfProcesser.WriteArrivals(arrs, stream)

    if cacheFolder:
        resPath = pathlib.Path(cacheFolder, f"arrivals_{safeStopName}.json")
        os.makedirs(resPath.parent, exist_ok=True)
        with open(resPath, "w+", encoding="utf-8") as f:
            f.write(stream.getvalue())

    return True, json.loads(stream.getvalue())


def UnpackDepartures(departures):
    result = []
    for departure in departures:
        resDep = {
            "Stop": departure["Stop name"],
            "Day": departure["Date"],
            "Time": departure["Stop time"],
        }
        trip = departure["Trip number"]
        tripFields = ["Line number", "Trip number", "Initial stop", "Departure time", "Terminal stop", "Arrival time"]
        tripFieldsTranslated = ["LineNo", "TripNo", "StopFrom", "TimeFrom", "StopTo", "TimeTo"]
        for f, ft in zip(tripFields, tripFieldsTranslated):
            resDep[ft] = trip[f]
        result.append(resDep)
    return result


def unpackArrivals(arrivals):
    result = []
    for arrival in arrivals:
        resArr = {
            "Stop": arrival["Stop name"],
            "Day": arrival["Date"],
            "Time": arrival["Stop time"],
        }
        trip = arrival["Trip number"]
        tripFields = ["Line number", "Trip number", "Initial stop", "Departure time", "Terminal stop", "Arrival time"]
        tripFieldsTranslated = ["LineNo", "TripNo", "StopFrom", "TimeFrom", "StopTo", "TimeTo"]
        for f, ft in zip(tripFields, tripFieldsTranslated):
            resArr[ft] = trip[f]
        result.append(resArr)
    return result


def unpackTrips(trips):
    result = []
    for dt in trips:
        day = dt["Day"]
        currTrips = dt["Trips"]
        result.extend(
            [{
                "Day": day,
                "LineNo": trip["Line number"],
                "TripNo": trip["Trip number"],
                "StopFrom": trip["Initial stop"],
                "StopTo": trip["Terminal stop"],
                "TimeFrom": trip["Departure time"],
                "TimeTo": trip["Arrival time"]
            } for trip in currTrips])

    return result
