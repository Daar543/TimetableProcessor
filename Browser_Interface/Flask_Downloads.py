"""!
@file Flask_Downloads.py
@namespace Flask_Gui
@brief Routes for downloading files stored on the server
"""

import datetime
import io
import json
import os
import pathlib
from typing import Any, Dict, List, Tuple, Union

import numpy as np
from flask import Blueprint, redirect, render_template, request, send_file, session, url_for, send_from_directory

from Browser_Interface import Flask_Scheduling
from Browser_Interface import Flask_Visualization


root  = pathlib.Path("online_files")
jdfRoot = pathlib.Path(root, "upload")

Download_Api = Blueprint('Flask_Downloads', __name__)


@Download_Api.route('/download/distance-matrix', methods=['GET'])
def DownloadDistanceMatrix() -> Any:
    """!
    @brief Download distance matrix used for the current schedule if previewing
    """
    global root

    def ern():
        return "File not found", 404

    preview = session.get("preview")
    if not preview:
        return "Session expired", 404
    distanceMethod = preview.get("DistanceMethod")
    if not distanceMethod:
        return ern()
    jdfName = preview.get("JdfName")
    if not jdfName:
        return ern()
    matrixPath = Flask_Scheduling.GetDistanceMatrixLocation(jdfName, distanceMethod)
    matrixPath = matrixPath.resolve()
    try:
        return send_from_directory(matrixPath.parent, matrixPath.name, as_attachment=True,
                                   mimetype="text/tab-separated-values")
    except FileNotFoundError as e:
        return ern()
    except Exception as e:
        return f"Error: {e}", 500


@Download_Api.route('/download/schedule', methods=['GET'])
def DownloadSchedule() -> Any:
    """!
    @brief Download schedule used for the current preview
    """
    temp = pathlib.Path(root, "temp")

    def ern():
        return "File not found", 404

    args = request.args
    jdfName = args.get("JDF_name")
    dtFrom = args.get("startdt")
    dtTo = args.get("enddt")
    schedulingMethod = args.get("schedulingMethod")
    distanceMethod = args.get("distanceMethod")
    if not (jdfName and dtFrom and dtTo and schedulingMethod and distanceMethod):
        return "Bad query parameters", 404
    schedulePath = Flask_Scheduling.GetScheduleLocation(jdfName, dtFrom, dtTo, distanceMethod, schedulingMethod)
    scheduleDir = schedulePath.parent.resolve()
    schedulePath = schedulePath.resolve()
    try:
        return send_from_directory(scheduleDir, schedulePath.name, as_attachment=True)
    except FileNotFoundError as e:
        return ern()
    except Exception as e:
        return f"Error: {e}", 500


@Download_Api.route('/download/visualization', methods=['GET'])
def DownloadVisualizedSchedule():
    args = request.args
    zipName = args.get("zipName")
    if not zipName:
        return "Bad query parameters", 404
    zipPath = Flask_Visualization.GetZippedMapsLocation(zipName)
    zipPath = zipPath.resolve()
    try:
        return send_from_directory(zipPath.parent, zipPath.name, as_attachment=True)
    except FileNotFoundError as e:
        return "File not found", 404
    except Exception as e:
        return f"Internal error", 500
