"""!
@file Flask_Scheduling.py
@namespace Flask_Gui
@brief Functions for scheduling buses to serve trips
"""
import datetime
import io
import json
import os
import pathlib
import urllib
import warnings
from typing import Any, Dict, List, Tuple, Union, Optional

import numpy as np
from flask import Blueprint, redirect, render_template, request, session, url_for

import Bus_Scheduling
from Browser_Interface import Flask_Query
from Browser_Interface import Flask_Stops
from Bus_Scheduling import Scheduling_Main, Scheduling_Precalculation, Schedule_Rendering, Scheduling_Utilities
from Bus_Scheduling.Scheduling_Precalculation import Trip
from JDF_Conversion import Timetable_Calculations, Utilities
from Map_Visualization import Map_Visualizer
from Map_Visualization import OSM_Distances

root = pathlib.Path("online_files")
jdfRoot = pathlib.Path(root, "upload")

Scheduling_Api = Blueprint('Flask_Scheduling', __name__)


@Scheduling_Api.route('/schedules/form')
def ScheduleForm():
    global jdfRoot
    error = request.args.get('error')
    folderNames = [x.name for x in Utilities.GetSubFolders(jdfRoot)]
    # Letters come before numbers, as custom names will be lettered
    folderNames.sort(key=lambda x: (not x[0].isalpha(), x))
    folderNames = [""] + folderNames
    stopNames = Flask_Stops.getSavedStopNames()

    return render_template("schedule_form.html",
                           errors=[error],
                           jdfFolderNames=folderNames,
                           stopNames=stopNames)


@Scheduling_Api.route('/schedules/prepare', methods=['POST'])
def PrecalculateSchedules():
    args = request.form

    global root
    tripFolder = pathlib.Path(root, "temp", "trips")
    os.makedirs(tripFolder, exist_ok=True)

    scheduleModeArg = args.get('mode')
    # Pick the other arguments based on mode
    if scheduleModeArg == "default":
        schedule = {"mode": "default"}
    elif scheduleModeArg == "depot":
        schedule = {"mode": "depot"}
        depotArg = args.get("depot")
        if not depotArg:
            return redirect(url_for("Flask_Scheduling.ScheduleForm", error="Error: No depot specified"))
        schedule["depot"] = depotArg
    elif scheduleModeArg == "circular":
        schedule = {"mode": "circular"}
        iterationsArg = args.get("iterations")
        if not iterationsArg:
            return redirect(url_for("Flask_Scheduling.ScheduleForm", error="Error: No number of iterations specified"))
        try:
            iterations = int(iterationsArg)
            if iterations < 1:
                raise ValueError
        except ValueError:
            return redirect(url_for("Flask_Scheduling.ScheduleForm",
                                    error=[f"Error: Invalid number of iterations ({iterationsArg})"]))
        schedule["iterations"] = iterations
        samplesArg = args.get("samples")
        if not samplesArg:
            return redirect(url_for("Flask_Scheduling.ScheduleForm", error="Error: No number of samples specified"))
        try:
            samples = int(samplesArg)
            if samples < 1:
                raise ValueError
        except ValueError:
            return redirect(
                url_for("Flask_Scheduling.ScheduleForm", error=f"Error: Invalid number of samples ({samplesArg})"))
        schedule["samples"] = samples
        multiplicationsArg = args.get("multiplications")
        if not multiplicationsArg:
            return redirect(
                url_for("Flask_Scheduling.ScheduleForm", error="Error: No number of multiplications specified"))
        try:
            multiplications = int(multiplicationsArg)
            if multiplications < 1:
                raise ValueError
        except ValueError:
            return redirect(url_for("Flask_Scheduling.ScheduleForm",
                                    error=f"Error: Invalid number of multiplications ({multiplicationsArg})"))
        schedule["multiplications"] = multiplications

    else:
        return redirect(url_for("Flask_Scheduling.ScheduleForm", error=f"Error: Invalid mode {scheduleModeArg}"))

    startDateTimeArg = args.get("startdate")
    if startDateTimeArg:
        try:
            startDateTime = datetime.datetime.strptime(startDateTimeArg, "%Y-%m-%dT%H:%M")
        except ValueError:
            return redirect(url_for("Flask_Scheduling.ScheduleForm",
                                    error=f"Error: Invalid start date and time format ({startDateTimeArg})"))
    else:
        return redirect(url_for("Flask_Scheduling.ScheduleForm", error="Error: No start date and time specified"))
    endTimeArg = args.get("endtime")
    if endTimeArg:
        try:
            endTime = datetime.datetime.strptime(endTimeArg, "%H:%M")
        except ValueError:
            return redirect(url_for("Flask_Scheduling.ScheduleForm"
                                    , error=f"Error: Invalid end time format ({endTimeArg})"))
        # The end datetime is within 24 hours of the start datetime
        endDateTime = datetime.datetime.combine(startDateTime.date(), endTime.time())
        if endDateTime <= startDateTime:
            endDateTime += datetime.timedelta(days=1)
    else:
        # Add 24 hours to the start time
        endDateTime = startDateTime + datetime.timedelta(hours=24)
    folder = args.get("JDF_folder")
    if not folder:
        return redirect(url_for("Flask_Scheduling.ScheduleForm", error="Error: No folder specified"))
    path = pathlib.Path(jdfRoot, folder)
    distanceMethod = {}
    distanceType = args.get("distancesCalc")
    if distanceType == "timetable":
        distanceMethod["type"] = "timetable"
    elif distanceType == "upload":
        distanceMethod["type"] = "upload"
        matrixFile = request.files.get("distancesCalc_matrix")
        if not matrixFile:
            return redirect(url_for("Flask_Scheduling.ScheduleForm", error="Error: No distance matrix file specified"))
        distanceMethod["upload"] = matrixFile
    elif distanceType == "map":
        distanceMethod["type"] = "map"
    else:
        return redirect(url_for("Flask_Scheduling.ScheduleForm", error="Error: Invalid distance calculation method"))
    invalidateDistanceCache = args.get("invalidate_distance") == "on"
    if invalidateDistanceCache:
        distanceMethod["cached"] = False
    else:
        distanceMethod["cached"] = True
    invalidateScheduleCache = args.get("invalidate_schedule") == "on"
    if invalidateScheduleCache:
        schedule["cached"] = False
    else:
        schedule["cached"] = True
    # Parse the folder
    jdfProcessor = Timetable_Calculations.ParseSingleFolder(str(path))
    jdfName = path.name
    if not jdfProcessor:
        return redirect(url_for("Flask_Scheduling.ScheduleForm",
                                error="Error: Folder does not contain all files for the JDF format"))
    if distanceType == "timetable":
        distanceMethod["jdfProcessor"] = jdfProcessor

    maxLimit = 10000
    success, res = Flask_Query.QueryTrips(jdfName, jdfProcessor,
                                          startDateTime.date().strftime("%Y-%m-%d"),
                                          endDateTime.date().strftime("%Y-%m-%d"),
                                          tripFolder, False, True, 10000)
    if not success:
        return redirect(url_for("Flask_Scheduling.ScheduleForm", error=[res]))
    # Get trips from given range
    trips = CropTrips(res, startDateTime, endDateTime)
    if len(trips) > maxLimit:
        return redirect(url_for("Flask_Scheduling.ScheduleForm",
                                error=f"Error: Too many trips (over {maxLimit}), please select a smaller range"))
    success, preview = PreviewScheduling(folder, trips, schedule, distanceMethod)
    if not success:
        return redirect(url_for("Flask_Scheduling.ScheduleForm", error=str(preview)))
    session["preview"] = preview
    return redirect(url_for("Flask_Scheduling.ShowPreview"))


@Scheduling_Api.route('/schedules/preview', methods=['GET'])
def ShowPreview():
    def sessionExpired():
        return redirect(url_for("Flask_Scheduling.ScheduleForm", error="Session expired, please submit again"))

    preview = session.get("preview")
    if not preview:
        return sessionExpired()
    estimate = preview.get("Estimate")
    if not estimate:
        return sessionExpired()
    edgec = estimate.get("Edges count", 0)
    tripc = estimate.get("Trip count", 0)
    firstTrip = preview.get("First trip")
    lastTrip = preview.get("Last trip")
    dtFrom = datetime.datetime.combine(firstTrip.Day, datetime.datetime.strptime(firstTrip.StartTime, "%H:%M").time())
    # Here we only check if last trip is over midnight
    # (could probably be simplified for efficiency)
    lastDay = lastTrip.Day \
        if (datetime.datetime.strptime(lastTrip.EndTime, "%H:%M").time() \
            >= datetime.datetime.strptime(lastTrip.StartTime, "%H:%M").time()) \
        else lastTrip.Day + datetime.timedelta(days=1)
    dtTo = datetime.datetime.combine(lastDay, datetime.datetime.strptime(lastTrip.EndTime, "%H:%M").time())
    scheduleArgs = preview.get("ScheduleArgs")
    if not scheduleArgs:
        return sessionExpired()
    schedulingMethod, otherArgs = FormatScheduleArgs(scheduleArgs)
    jdfName = preview.get("JdfName")
    if not jdfName:
        return sessionExpired()
    distanceMethod = preview.get("DistanceMethod")
    if not distanceMethod:
        return sessionExpired()
    # We need: starting time, ending time, schedule mode, JDF folder name, distance calculation mode
    return render_template("schedule_preview.html", edgec=edgec, tripc=tripc,
                           firstTrip=firstTrip, lastTrip=lastTrip, dtFrom=dtFrom, dtTo=dtTo,
                           schedulingMethod=schedulingMethod, schedulingParams=otherArgs,
                           schedulingParamsJson=json.dumps(otherArgs),
                           jdfName=jdfName, distanceMethod=distanceMethod)


@Scheduling_Api.route("/schedules/submit", methods=["GET"])
def SubmitScheduling():
    args = request.args
    try:
        success, message = HandleScheduling(args)
    except Exception as e:
        success, message = False, f"Error: {e}"
    downloadArgs = {
        "JDF_name": args.get("JDF_name"),
        "distanceMethod": args.get("distanceMethod"),
        "schedulingMethod": args.get("schedulingMethod"),
        "startdt": args.get("startdt"),
        "enddt": args.get("enddt"),
    }
    if success:
        return redirect(url_for("Flask_Scheduling.ShowSchedules", **downloadArgs))
    else:
        return redirect(url_for("Flask_Scheduling.ScheduleForm", error=message))


@Scheduling_Api.route("/schedules/display", methods=["GET"])
def ShowSchedules():
    args = request.args
    downloadArgs = {
        "JDF_name": args.get("JDF_name"),
        "distanceMethod": args.get("distanceMethod"),
        "schedulingMethod": args.get("schedulingMethod"),
        "startdt": args.get("startdt"),
        "enddt": args.get("enddt"),
    }
    try:
        scheduleFile = GetScheduleLocation(downloadArgs["JDF_name"], downloadArgs["startdt"], downloadArgs["enddt"],
                                           downloadArgs["distanceMethod"], downloadArgs["schedulingMethod"])
    except ValueError as e:
        return redirect(
            url_for("Flask_Scheduling.ScheduleForm", error=f"Error: Invalid arguments in query ({str(downloadArgs)})"))
    try:
        with open(scheduleFile, "r", encoding="utf-8") as f:
            schedules, scheduleAttrs = Bus_Scheduling.Schedule_Rendering.SchedulesDirectly(json.load(f))
    except FileNotFoundError:
        return redirect(url_for("Flask_Scheduling.ScheduleForm", error="Error: Schedules not found"))
    except json.JSONDecodeError as e:
        return redirect(url_for("Flask_Scheduling.ScheduleForm", error=f"Error when reading schedules: {e}"))
    except Exception as e:
        return redirect(url_for("Flask_Scheduling.ScheduleForm", error=f"Error: {e}"))
    if not schedules:
        return redirect(url_for("Flask_Scheduling.ScheduleForm", error="Error reading schedules"))
    return render_template("schedule_result.html", schedules=schedules,
                           scheduleAttrs=scheduleAttrs, downloadArgs=urllib.parse.urlencode(downloadArgs))


def GetScheduleLocation(jdfName: str, startDateTime: str, endDateTime: str,
                        distanceMethod: str, schedulingMethod: str) -> pathlib.Path:
    """!
        @brief Create a name for file with schedules
        @param jdfName Name of the JDF
        @param startDateTime Datetime of first trip
        @param endDateTime Datetime of last trip (last stop)
        @param distanceMethod How was the distance calculated
        @param schedulingMethod Scheduling mode
        @note The names do not use scheduling arguments as that could clutter the database too much
        @return Location of scheduling file
    """
    if not jdfName or not startDateTime or not endDateTime or not distanceMethod or not schedulingMethod:
        raise ValueError("Invalid arguments")
    scheduleDir = pathlib.Path(root, "temp", "schedules")
    schedulePath = pathlib.Path(scheduleDir,
                                f"{jdfName}_{startDateTime}_{endDateTime}_"
                                f"{distanceMethod}_{schedulingMethod}.json")
    return schedulePath


def GetDistanceMatrixLocation(jdfName: str, distanceMethod: str) -> pathlib.Path:
    """!
    @brief Create a name for file with distances
    @param jdfName Name of the JDF
    @param distanceMethod How was the distance calculated
    @return Location of distance matrix file
    """
    if not jdfName or not distanceMethod:
        raise ValueError("Invalid arguments")
    folder = pathlib.Path(root, "distances", distanceMethod)
    matrixPath = pathlib.Path(folder, f"{jdfName}.tsv")
    return matrixPath


def FormatScheduleArgs(scheduleArgs: Dict):
    mode = scheduleArgs.get("mode")
    otherArgs = {key: value for key, value in scheduleArgs.items() if key != "mode"}
    return mode, otherArgs


def CropTrips(dayTrips: List[Dict], startDateTime: datetime.datetime, endDateTime: datetime.datetime):
    """!
    @brief Crop trips to given time range. Trips must not only start, but also end within the time range
    @param dayTrips List of days and trips within them
    @param startDateTime Start of the time range
    @param endDateTime End of the time range
    @return List of cropped trips
    """
    result = []
    for day in dayTrips:

        currentTrips = []
        daydt = datetime.datetime.strptime(day["Day"], "%Y-%m-%d").date()
        if daydt < startDateTime.date() or daydt > endDateTime.date():
            continue
        for trip in day["Trips"]:
            departureTime = datetime.datetime.combine(daydt,
                                                      datetime.datetime.strptime(trip["Departure time"], "%H:%M").time())
            arrivalTime = datetime.datetime.combine(daydt,
                                                    datetime.datetime.strptime(trip["Arrival time"], "%H:%M").time())
            if arrivalTime < departureTime:
                arrivalTime += datetime.timedelta(days=1)
            if startDateTime <= departureTime and arrivalTime <= endDateTime:
                currentTrips.append(trip)
        result.append({"Day": day["Day"], "Trips": currentTrips})
    return result


def PreviewScheduling(jdfName: str, trips: List[Dict], scheduleArgs: Dict, distanceType: Dict) -> \
        Tuple[bool, Union[str, Dict[str, Any]]]:
    """!
    @brief Show user the data about trips and show estimate of optimization
    """
    if not trips:
        return False, "Error: No trips in given range"

    trips = Scheduling_Precalculation.CompactMultiDayTrips(trips)
    if not trips:
        return False, "Error: No trips in given range"
    distanceMethod = distanceType.get("type")
    distCached = distanceType.get("cached")
    if not distanceMethod:
        return False, "Error: No distance type specified"
    if distanceMethod not in ["upload", "timetable", "map"]:
        return False, "Error: Invalid distance type"
    depotStop = scheduleArgs.get("depot") if scheduleArgs.get("mode") == "depot" else None
    terminals = Scheduling_Precalculation.GetTerminals(trips)
    if depotStop and depotStop not in terminals:
        terminals.append(depotStop)
    cacheHit = distCached
    stops, distances = None, None
    if distanceMethod == "upload":
        cacheHit = False  # Here we always set to false to force rewriting the file passed by user
        matrixFile = distanceType.get("upload")
        if not matrixFile:
            return False, "Error: No matrix file provided"
        try:
            with io.TextIOWrapper(matrixFile, encoding='utf-8') as f:
                stops, distances = Timetable_Calculations.ReadDistances(f)
            matrixFile = GetDistanceMatrixLocation(jdfName, "upload")
            if not set(terminals).issubset(set(stops)):
                missingStops = sorted(set(terminals) - set(stops))
                missingStopsStr = "\n".join(missingStops)
                if len(missingStops) > 100:
                    missingStopsStr = missingStopsStr[:100] + "..."
                return False, f"Error: Not all stops are in the uploaded matrix. Missing stops:\n{missingStopsStr}"
        except Exception as e:
            return False, f"Error: {e}"
    elif distanceMethod == "timetable":
        matrixFile = GetDistanceMatrixLocation(jdfName, "timetable")
        if distCached:
            try:
                with open(matrixFile, encoding="utf-8") as f:
                    stops, distances = Timetable_Calculations.ReadDistances(f)
            except FileNotFoundError:
                print("File not found, calculating")
            except Exception as e:
                return False, f"Error: {e}"
        # check if our cached matrix is relevant
        if stops and (not set(terminals).issubset(set(stops))):
            stops, distances = None, None
        if stops is None or distances is None:
            cacheHit = False
            jdfProcessor: Timetable_Calculations.JdfProcessor = distanceType.get("jdfProcessor")
            if not jdfProcessor:
                return False, "Error: No JDF processor specified"
            try:
                jdfStops, missedStops = jdfProcessor.FindStopsByName(terminals, "exact")
                if missedStops:
                    missedNames = "\n".join(missedStops)
                    return False, f"Error: Some stops could not be found in the JDF:\n{missedNames}"
                stops, distances = jdfProcessor.GetDeadheadMatrixByTT(jdfStops)
                stops = [s.GetName() for s in stops]
            except Exception as e:
                return False, f"Error: {e}"
    elif distanceMethod == "map":
        matrixFile = GetDistanceMatrixLocation(jdfName, "map")
        if distCached:
            try:
                with open(matrixFile, encoding='utf-8') as f:
                    stops, distances = Timetable_Calculations.ReadDistances(f)
            except FileNotFoundError:
                print("File not found, calculating")
            except Exception as e:
                return False, f"Error: {e}"
        if stops and (not set(terminals).issubset(set(stops))):
            stops, distances = None, None
        if stops is None or distances is None:
            cacheHit = False
            stopLocationsFile = pathlib.Path(root, "stop_locations.csv")
            stopLocations, errorStops = Map_Visualizer.ReadStopLocations(terminals, stopLocationsFile)
            if errorStops:
                if len(errorStops) > 50:
                    errorStops = errorStops[:50]
                    errorStops.append("...")
                errorNames = "\n".join(errorStops)
                errorMsg = f"Error: Some stops could not be found on the map:\n{errorNames}"
                return False, errorMsg
            stops, distances = OSM_Distances.GetDistancesFromMap(stopLocations)
    else:
        return False, "Error: Invalid distance type"
    # Alright, now we have the distances
    # preview trips with passed trips and distances
    if not cacheHit:
        os.makedirs(matrixFile.parent, exist_ok=True)
        with open(matrixFile, "w+", encoding="utf-8", newline="") as f:
            Timetable_Calculations.SaveDistances(f, stops, distances)
    print("Calculating estimate")
    firstTrip = min(trips, key=lambda x: x.StartTimeMins)
    lastTrip = max(trips, key=lambda x: x.EndTimeMins)
    estimate = Scheduling_Precalculation.EstimateScheduling(trips, stops, distances, scheduleArgs)
    result = {"Estimate": estimate,
              "First trip": firstTrip, "Last trip": lastTrip,
              "First stop": stops[0], "Last stop": stops[-1],
              "ScheduleArgs": scheduleArgs,
              "JdfName": jdfName, "DistanceMethod": distanceMethod}
    return True, result


def HandleScheduling(args: Dict) -> Tuple[bool, Optional[str]]:
    """!
    @brief Handle the scheduling request
    @param args: Dictionary of arguments
    Arguments in HTML:
        <input type="hidden" name="JDF_name" placeholder="JDF name" value="{{jdfName}}">
        <input type="hidden" name="startdt" id="startdt" value="{{dtFrom.strftime('%Y-%m-%d %H:%M')}}">
        <input type="hidden" name="enddt" id="enddt" value="{{dtTo.strftime('%Y-%m-%d %H:%M')}}">
        <input type="hidden" name="distanceMethod" id="distanceMethod" value="{{distanceMethod}}">
        <input type="hidden" name="schedulingMethod" id="schedulingMethod" value="{{schedulingMethod}}">
        <input type="hidden" name="schedulingParams" id="schedulingParams" value="{{schedulingParams|tojson}}">
    @return: Tuple of success and optional error
    """
    jdfName = args.get("JDF_name")
    if not jdfName:
        return False, "Error: Invalid form"
    startdt = args.get("startdt")
    if not startdt:
        return False, "Error: Invalid form"
    try:
        startDateTime = datetime.datetime.strptime(startdt, "%Y-%m-%d_%H%M")
    except ValueError as e:
        return False, f"Error: Invalid value of start date ({startdt})"
    enddt = args.get("enddt")
    if not enddt:
        return False, "Error: Invalid form"
    try:
        endDateTime = datetime.datetime.strptime(enddt, "%Y-%m-%d_%H%M")
    except ValueError as e:
        return False, f"Error: Invalid value of end date ({enddt})"
    distanceMethod = args.get("distanceMethod")
    if not distanceMethod:
        return False, "Error: Invalid form"
    if distanceMethod not in ["upload", "timetable", "map"]:
        return False, "Error: Invalid distance method"
    schedulingMethod = args.get("schedulingMethod")
    if not schedulingMethod:
        return False, "Error: Invalid form"
    if schedulingMethod not in ["default", "depot", "circular"]:
        return False, "Error: Invalid scheduling mode"
    schedulingParamsJson = args.get("schedulingParams")
    if not schedulingParamsJson:
        return False, "Error: Invalid form"
    try:
        schedulingParams = json.loads(schedulingParamsJson)
    except json.JSONDecodeError as e:
        return False, f"Error: Invalid scheduling params {schedulingParamsJson}"
    # Alright, now we have all the data
    global root
    temp = pathlib.Path(root, "temp")
    # Distances file:
    try:
        distanceFile = GetDistanceMatrixLocation(jdfName, distanceMethod)
        with open(distanceFile, "r", encoding="utf-8", newline="") as f:
            stops, distances = Timetable_Calculations.ReadDistances(f)
    except FileNotFoundError:
        return False, f"Error: File with distances not found - refresh scheduling query"
    # Trips file:
    allTrips = []
    currentDay = startDateTime.date()
    while currentDay <= endDateTime.date():
        day = currentDay.strftime("%Y-%m-%d")
        try:
            tripsFile = pathlib.Path(temp, "trips", f"{jdfName}_{day}.json")
            with open(tripsFile, "r", encoding="utf-8") as f:
                trips = Scheduling_Precalculation.GetOneDayTrips(f, currentDay)
                if currentDay == startDateTime.date():
                    trips = [t for t in trips if
                             datetime.datetime.combine(currentDay,
                                                       datetime.datetime.strptime(t.StartTime, "%H:%M").time())
                             >= startDateTime]
                if currentDay == endDateTime.date():
                    trips = [t for t in trips if
                             datetime.datetime.combine(currentDay,
                                                       datetime.datetime.strptime(t.EndTime, "%H:%M").time())
                             <= endDateTime
                             and  # trip ends before midnight
                             datetime.datetime.strptime(t.StartTime, "%H:%M").time()
                             <= datetime.datetime.strptime(t.EndTime, "%H:%M").time()
                             ]
                allTrips.extend(trips)
        except FileNotFoundError:
            return False, f"Error: File with trips not found - refresh scheduling query"
        except json.JSONDecodeError as e:
            return False, f"Error: Error reading trips file: {e}. Refresh scheduling query"
        currentDay += datetime.timedelta(days=1)
    Scheduling_Precalculation.RecalcAllTrips(allTrips)
    # Start with the optimization
    outFolder = pathlib.Path(temp, "schedules")
    os.makedirs(outFolder.parent, exist_ok=True)
    tryCache = schedulingParams.get("cached", False)
    # We do not actually need to read the schedules here, as we redirect when reading them from a file
    CreateSchedules(allTrips, stops, distances, distanceMethod, schedulingMethod, schedulingParams,
                    outFolder, jdfName, startDateTime, endDateTime, tryCache)
    return True, None


def CreateSchedules(allTrips: List[Trip], stops: List[str], distances: np.ndarray, distanceMethod: str,
                    schedulingMethod: str, scheduleArgs: dict,
                    outFolder: pathlib.Path, jdfName: str, startDateTime: datetime.datetime,
                    endDateTime: datetime.datetime,
                    useCache: bool) -> Tuple[bool, Dict[str, Any]]:
    """!
    @brief Schedule branching - either read the schedules from cache or calculate them again
    @param allTrips List of all trips
    @param stops List of stops
    @param distances Distance matrix
    @param schedulingMethod Scheduling mode
    @param scheduleArgs Scheduling arguments
    @param outFolder Output folder
    @param jdfName Name of the JDF batch
    @param startDateTime Datetime of first trip
    @param endDateTime Datetime of last trip
    @param useCache Whether to read the schedules from cache if available
    @return Tuple, first argument is if schedules were read from cache, second is the schedules
    """
    schedules = None
    schedulesPath = GetScheduleLocation(jdfName, startDateTime.strftime('%Y-%m-%d_%H%M'),
                                        endDateTime.strftime('%Y-%m-%d_%H%M'), distanceMethod, schedulingMethod)
    if useCache:
        try:
            with open(schedulesPath, "r", encoding="utf-8") as f:
                schedulesJson = json.load(f)
            schedules, scheduleArgsTotal = Schedule_Rendering.SchedulesFromJsonDict(schedulesJson)
        except FileNotFoundError:
            schedules = None
        except Exception as e:
            warnings.warn(f"Error reading schedules file: {e}")
            schedules = None
    if schedules is not None:
        return True, schedules
    schedules = Scheduling_Main.CalculateGeneral(
        allTrips, stops, distances, schedulingMethod, scheduleArgs
    )

    # decorate schedules with additional information
    addedInfo = {
        "JDF batch name": jdfName,
        "First trip": startDateTime.strftime('%Y-%m-%d %H:%M'),
        "Last trip": endDateTime.strftime('%Y-%m-%d %H:%M'),
        "Distance calculated using": distanceMethod,
    }
    # Obviously this is irrelevant info if we read from cache again we will not rewrite the attribute to true
    schedules.pop("cached")
    schedules.update(addedInfo)
    os.makedirs(schedulesPath.parent, exist_ok=True)
    with open(schedulesPath, "w+", encoding="utf-8") as f:
        json.dump(schedules, f, indent=2, ensure_ascii=False, sort_keys=True)
    return False, schedules
