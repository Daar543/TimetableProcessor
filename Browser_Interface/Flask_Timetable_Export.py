"""!
@file Flask_Timetable_Export.py
@namespace Flask_Gui
@brief Functions for displaying timetables as tabular data
"""

import os
import pathlib

from flask import Blueprint, request, redirect, url_for, render_template, send_file

from JDF_Conversion import Timetable_Calculations, Table_Export,Utilities

root = pathlib.Path("online_files")
jdfRoot = pathlib.Path(root,"upload")

Timetable_Export_Api = Blueprint('Flask_Timetables', __name__)


@Timetable_Export_Api.route('/timetables/export/main', methods=['GET'])
def TimetablesForm():
    global jdfRoot
    folderNames = [x.name for x in Utilities.GetSubFolders(jdfRoot)]
    # Letters come before numbers, as custom names will be lettered
    folderNames.sort(key=lambda x: (not x[0].isalpha(), x))
    return render_template('timetables_export_form.html',
                            jdfFolderNames=folderNames,
                           error=request.args.get('error'))


@Timetable_Export_Api.route('/timetables/export/download', methods=['GET', 'POST'])
def TimetablesDownload():
    if request.method == 'POST':
        folder = request.form['JDF_folder']
        oneFile = request.form.get('oneFile', False)
        splitDays = request.form.get('splitDays', False)
        bidirectional = request.form.get('bidirectional', False)

        # redirect as GET request
        return redirect(url_for('Flask_Timetables.TimetablesDownload', folder=folder,
                                oneFile=oneFile,
                                splitDays=splitDays, bidirectional=bidirectional))
    jdfName = request.args.get('folder')
    oneFile = request.args.get('oneFile', False) == "on"
    splitDays = request.args.get('splitDays', False) == "on"
    bidirectional = request.args.get('bidirectional', False) == "on"

    # Check if the folder exists
    if not jdfName:
        return redirect(url_for('Flask_Timetables.TimetablesForm', error="Folder not specified"))
    folder = pathlib.Path(jdfRoot, jdfName)
    tempFolder = pathlib.Path(root, "temp")
    outZip = Utilities.Slugify(jdfName) + ".zip"
    # must be directory
    if not os.path.isdir(folder):
        return redirect(url_for('Flask_Timetables.TimetablesForm', error="Invalid folder"))
    # try to package the files into a zip
    try:
        jdfProcessor = Timetable_Calculations.ParseSingleFolder(str(folder))
        if oneFile:
            Table_Export.ExcelTimetables(jdfProcessor, outZip,tempFolder,
                                         "default", False,splitDays)
        else:
            Table_Export.ZipTimetables(jdfProcessor, outZip, tempFolder,
                                       "default", bidirectional, splitDays)
    except Exception as e:
        #raise
        return redirect(url_for('Flask_Timetables.TimetablesForm', error="Error: " + str(e)))
    # try to download the zip
    fileLoc = pathlib.Path(tempFolder, outZip)
    return send_file(fileLoc.absolute(), as_attachment=True)
