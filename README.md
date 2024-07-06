# Timetable processor

Integrates the process of bus scheduling and route visualization directly from reading timetable data.

## Prerequisites
The TTP was tested on Linux and Windows. A Python 3.10 interpreter is required.

## Installation
1. Download the source codes from the attached ZIP file
2. Go to the root folder.
3. Set up Python environment and install the required packages by running:
`python3 .10 -m venv venv && . venv/bin/ activate`
`python3 .10 -m pip install -r requirements .txt`
4. Launch the server by interpreting file Flask_Main.py from the folder
TimetableBusScheduling. As for the port, select a number such as (5000)
that is not already in use.
`python3.10 Browser_Interface / Flask_Main .py -p <port >`
5. You can also use flag `-d` to run the server in developer mode.
6. Launch your browser and go to `127.0.0.1:<port>` to use the app.
7. If needed, the server can be stopped by pressing Ctrl+C in the terminal.

## Testing data
Some basic data can be seen in `Examples/JDF`.
They can be uploaded to the server by using the `Upload JDF`
module in the TTP (load the whole folder).
The locations of most stops relevant to those datasets are already included in
the server filesystem. To add more, follow the user documentation (todo, needs formatting).

## Pre-loaded data
The data created by the server will be stored in the online_files folder. This
folder is also provided separately in the `Examples` folder where
the data generated during the testing run is already included. You can compare
the results of your run with the provided data.

## Remote server
To use the server on remote PC, use port forwarding, e.g.
`ssh -L 5000: localhost :5000 user@remote_server`
and install everything on the remote server as described above. You can then
access the server from your local browser.