"""!
@file Flask_Visualization.py
@namespace Flask_Gui
@brief This module serves for visualizing the trips on map
"""

import datetime
import io
import json
import os
import pathlib
import shutil
import urllib
import random
import zipfile
from typing import Any, Dict, List, Tuple, Union

import numpy as np
from flask import Blueprint, redirect, render_template, request, send_file, session, url_for

from JDF_Conversion import Utilities
from Map_Visualization import Map_Visualizer, OSM_Distances, Stops

root = pathlib.Path("online_files")
jdfRoot = pathlib.Path(root, "upload")

Visualization_Api = Blueprint('Flask_Visualization', __name__)


@Visualization_Api.route('/visualize', methods=['GET'])
def VisualizationForm():
    error = request.args.get("error")
    return render_template('visualization_form.html', error=error)


@Visualization_Api.route('/visualize_result', methods=['GET'])
def ShowResult():
    error = request.args.get("error")
    downloadArgs = request.args.get("downloadArgs")
    return render_template('visualization_result.html', error=error, downloadArgs=downloadArgs)


@Visualization_Api.route('/visualize/submit', methods=['POST'])
def ProcessVisualization():
    file = request.files.get('scheduleFile')
    if not file:
        return redirect(url_for('Flask_Visualization.VisualizationForm', error="Error: No file uploaded"))
    trackComplexity = request.form.get("track_complexity")
    if trackComplexity not in ["direct", "navigation"]:
        return redirect(url_for('Flask_Visualization.VisualizationForm',
                                error=f"Error: Invalid option for rendering track complexity: ({trackComplexity})"))
    sameRoutes = request.form.get("same_routes")
    if sameRoutes not in ["overlap", "parallel", "curve"]:
        return redirect(url_for('Flask_Visualization.VisualizationForm',
                                error=f"Error: Invalid option for rendering trips going through same stops: ({sameRoutes})"))
    # read file and convert to json
    fname_safe = Utilities.Slugify(file.filename)
    file_content = file.read()
    try:
        json_content = json.loads(file_content)
    except json.decoder.JSONDecodeError as e:
        return redirect(url_for('Flask_Visualization.VisualizationForm',
                                error=f"Error: Invalid file format (not valid JSON): + {e}"))
    except UnicodeDecodeError as e:
        return redirect(url_for('Flask_Visualization.VisualizationForm',
                                error=f"Error: Invalid file format (not valid JSON): + {e}"))
    except Exception as e:
        return redirect(url_for('Flask_Visualization.VisualizationForm', error=f"Error when parsing JSON: {e}"))
    stopsDbPath = pathlib.Path(root, "stop_locations.csv")
    try:
        with open(stopsDbPath, "r", encoding="utf-8") as f:
            stopLocations = Stops.GetStopLocations(f)
    except FileNotFoundError:
        return redirect(
            url_for('Flask_Visualization.VisualizationForm', error="Error: Stop locations database not found"))
    except Exception as e:
        return redirect(url_for('Flask_Visualization.VisualizationForm', error=f"Error: {e}"))
    stopLocationMap = {s.GetName(): (s.Longitude, s.Latitude) for s in stopLocations}
    schedules = json_content

    mapRoot = pathlib.Path(root, "temp", "maps")
    os.makedirs(mapRoot, exist_ok=True)
    # Try to create the directory for temporary files with random id in case of collisions
    created, attempts = False, 0
    random_id = random.randint(1, 10000)
    mapDir = None
    while not created:
        mapDir = pathlib.Path(mapRoot, f"{fname_safe}_{random_id}")
        try:
            os.makedirs(mapDir)
            created = True
        except FileExistsError:
            attempts += 1
            if attempts > 100:
                return redirect(url_for('Flask_Visualization.VisualizationForm',
                                        error="Error: Server is busy, please try again later"))
            random_id += 1
            continue
    try:
        bs = schedules.get("Bus schedules")
        if not bs:
            return redirect(url_for('Flask_Visualization.VisualizationForm',
                                    error="Error: No bus schedules were provided" + \
                                          "or they are not in the correct format"))
        cutSchedules = {}
        for s in bs:
            trips = s.get("Trips")
            if not trips:
                return redirect(url_for('Flask_Visualization.VisualizationForm',
                                        error="Error: Missing field 'Trips'"))
            busNo = s.get("Bus number")
            if not busNo:
                return redirect(url_for('Flask_Visualization.VisualizationForm',
                                        error="Error: Missing field 'Bus number'"))
            cutSchedules[busNo] = trips
        try:
            OSM_Distances.PlotSchedules(cutSchedules, stopLocationMap, mapDir, trackComplexity, sameRoutes)
        except Exception as e:
            return redirect(url_for('Flask_Visualization.VisualizationForm', error=f"Error: {e}"))
        # zip the directory using zip module
        zipPath = mapDir.with_name(mapDir.name + ".zip")
        with zipfile.ZipFile(zipPath, "w") as zfile:
            for fname in os.listdir(mapDir):
                if os.path.isfile(pathlib.Path(mapDir, fname)):
                    zfile.write(pathlib.Path(mapDir, fname), fname)
        # first only redirect, link to download will be provided on the next page
        args = {"zipName": mapDir.name}
        downloadArgs = urllib.parse.urlencode(args)
        return redirect(url_for('Flask_Visualization.ShowResult', downloadArgs=downloadArgs))

    except TypeError as e:
        return redirect(
            url_for('Flask_Visualization.VisualizationForm',
                    error=f"Error: Invalid file format (not valid JSON): {e}"))
    except AttributeError as e:
        return redirect(
            url_for('Flask_Visualization.VisualizationForm',
                    error=f"Error: Invalid file format (not valid JSON): {e}"))
    except Exception as e:
        return redirect(url_for('Flask_Visualization.VisualizationForm', error=f"Error: {e}"))
    finally:
        shutil.rmtree(mapDir)


def GetZippedMapsLocation(zipName: str) -> pathlib.Path:
    return pathlib.Path(root, "temp", "maps", zipName + ".zip")
