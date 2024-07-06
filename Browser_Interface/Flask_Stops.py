"""!
@file Flask_Timetable_Export.py
@namespace Flask_Gui
@brief Functions for displaying and editing stops
"""

import csv
import io
import json
import os
import warnings
import pathlib

from flask import Blueprint, request, redirect, url_for, render_template, send_file

from typing import List, Dict, Tuple

from werkzeug.utils import secure_filename

from Map_Visualization import Stops

root  = pathlib.Path("online_files")
jdfRoot = pathlib.Path(root, "upload")
stopsFile = pathlib.Path(root, "stop_locations.csv")

Stops_Api = Blueprint('Flask_Stops', __name__)

DEFAULT_ZOOM = 13

@Stops_Api.route('/stops', methods=['GET'])
def ListStopData():
    error = request.args.get("error")
    stops = GetSavedStops()
    stopsDicts = [{"temporary_id": i, "name": stop.GetName(),
                   "latitude": stop.Latitude, "longitude": stop.Longitude} for i, stop in enumerate(stops)]
    initialLatitude = stops[0].Latitude if stops else 0
    initialLongitude = stops[0].Longitude if stops else 0
    return render_template('stops_list.html', error=error, stops=stopsDicts,
                           initialLatitude=initialLatitude, initialLongitude=initialLongitude,
                           initialZoom=DEFAULT_ZOOM)

@Stops_Api.route('/stops/import/', methods=['POST'])
def importStops():
    args = request.form
    # Read the file name
    importFile = request.files.get("import_file")
    if not importFile:
        return redirect(url_for('Flask_Stops.ListStopData', error="No file provided"))
    try:
        fileName = secure_filename(importFile.filename)
        overwriteStops = args.get("overwrite_import") == "on"
        # Create pathlib path towards this file
        importFilePath = pathlib.Path(root, "temp","stops", fileName)
        os.makedirs(importFilePath.parent,exist_ok=True)
        importFile.save(importFilePath)
        Stops.generateStopLocationFile([importFilePath],
                                       stopsFile, "overwrite" if overwriteStops else "append")
    except Exception as e:
        return redirect(url_for('Flask_Stops.ListStopData', error=f"Error when processing stops file: {e}"))
    return redirect(url_for('Flask_Stops.ListStopData'))
@Stops_Api.route('/stops/edit', methods=['POST'])
def changeStops():
    # Verify indexes for delete
    deli = request.form.get("delete")
    if not deli:
        warnings.warn("No indexes to delete")
        deleteIndexes = []
    else:
        deleteIndexes = sanitizeIndexes(deli)

    # Verify stops for add
    adds = request.form.get("add")
    if not adds:
        warnings.warn("No stops to add")
        addStops = []
    else:
        addStops = sanitizeStops(adds)
    # Load initial stops
    with open(stopsFile, "a+", encoding="utf-8") as f:  # a+ to initialize if not exists
        f.seek(0)
        stops = Stops.GetStopLocations(f)
    # Skip stops with given indexes (make sure to use the same sort)
    remainingStops = [stop for i, stop in enumerate(stops) if i not in deleteIndexes]
    # Add new stops
    remainingStops += addStops
    # Rewrite stop file
    with open(stopsFile, "w", encoding="utf-8") as f:
        csv_writer = csv.writer(f, delimiter=',', lineterminator='\n')
        for stop in remainingStops:
            csv_writer.writerow(
                [stop.Obec, stop.CastObce, stop.BlizsiMisto, stop.BlizkaObec, stop.Latitude, stop.Longitude])
    # Redirect to stops list
    return redirect(url_for('Flask_Stops.ListStopData'))


def GetSavedStops():
    try:
        with open(stopsFile, "a+", encoding="utf-8") as f:
            f.seek(0)
            stops = Stops.GetStopLocations(f)
    except FileNotFoundError:
        warnings.warn(f"File {stopsFile} not found, creating empty list of stops")
        stops = []
    return stops


def getSavedStopNames():
    stops = GetSavedStops()
    return [stop.GetName() for stop in stops]


def sanitizeIndexes(indexes: str) -> List[int]:
    """!
@brief Verify that indexes are valid and return them as integers
@param indexes List of indexes to verify as JSON string
    """
    indexesjs = json.loads(indexes)
    if not isinstance(indexesjs, list):
        raise ValueError(f"Invalid indexes {indexes}")
    indexes = [int(i) for i in indexesjs]
    indexes = [i for i in indexes if i >= 0]
    return indexes


def sanitizeStops(stops: str) -> List[Stops.StopWithLocation]:
    """!
@brief Verify that stops are valid and return them as StopWithLocation objects
@param stops List of stops to verify as JSON string
    """
    stopsjs = json.loads(stops)
    if not isinstance(stopsjs, list):
        raise ValueError(f"Invalid stops {stops}")
    stops = [Stops.StopWithLocation(
        *Stops.SanitizeStopName(stop["city_name"], stop["city_part"], stop["object_name"], stop["region"]),
        stop["latitude"], stop["longitude"])
        for stop in stopsjs]
    return stops





