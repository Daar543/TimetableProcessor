# Copyright (c) 2024 František Mrkus
# SPDX-License-Identifier: MIT

"""!
@file Flask_Main.py
@namespace Flask_Gui
@brief Default code for running the Flask server
"""

import secrets
import time
import random
import pathlib
import os
import sys
import logging
import argparse

sys.path.insert(0, os.getcwd())

from flask import Flask, g, render_template
from flask_session import Session

from Browser_Interface import Flask_Downloads, Flask_Query, Flask_Scheduling, Flask_Stops, Flask_Timetable_Export, \
    Flask_Timetable_Import, Flask_Upload, Flask_Visualization

app = Flask(__name__, static_folder='static')
app.register_blueprint(Flask_Query.Query_Api)
app.register_blueprint(Flask_Stops.Stops_Api)
app.register_blueprint(Flask_Timetable_Export.Timetable_Export_Api)
app.register_blueprint(Flask_Timetable_Import.Timetable_Import_Api)
app.register_blueprint(Flask_Upload.Upload_Api)
app.register_blueprint(Flask_Scheduling.Scheduling_Api)
app.register_blueprint(Flask_Downloads.Download_Api)
app.register_blueprint(Flask_Visualization.Visualization_Api)

secret = secrets.token_urlsafe(32)
app.secret_key = secret
app.config['SESSION_TYPE'] = 'filesystem'
app.config['TEMPLATES_AUTO_RELOAD'] = True
Session(app)

random.seed(time.process_time())  # Random seems to return the same value without this
random.seed(1)

root  = pathlib.Path("online_files")
jdfRoot = pathlib.Path(root, "upload")


@app.route('/')
def index():
    template = render_template('main_menu.html')

    return template


# Calculating time for request - source: https://stackoverflow.com/a/51874656
@app.before_request
def before_request():
    random.seed(1)
    # sys.stdout = open(os.devnull, 'w')
    g.start = time.perf_counter()


@app.after_request
def after_request(response):
    # sys.stdout = sys.__stdout__
    if (response.response and
            (200 <= response.status_code < 300) and
            (response.content_type.startswith('text/html'))):
        diff = time.perf_counter() - g.start
        millis = int(round(diff * 1000))
        print(f"Request took {millis} ms")

    return response


def mainDev(port:int):
    app.run(debug=True, threaded=True, port=port)


def mainProd(port:int):
    import waitress
    logger = logging.getLogger('waitress')
    logger.setLevel(logging.INFO)
    app.threaded = True
    waitress.serve(app,host='localhost', port=port)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the Flask server')
    parser.add_argument('-d','--dev', action='store_true', help='Run in development mode')
    parser.add_argument('-p','--port', type=int, default=5000, help='Port to run the server on', required=True)
    args = parser.parse_args()
    port = args.port
    dev = args.dev
    if args.dev:
        mainDev(port)
    else:
        mainProd(port)
