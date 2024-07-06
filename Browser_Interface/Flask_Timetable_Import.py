"""!
@file Flask_Timetable_Import.py
@namespace Flask_Gui
@brief Functions for importing timetables
"""

import os
import pathlib
import shutil

from flask import Blueprint, request, redirect, url_for, render_template

import JDF_Conversion.Table_Import as Table_Import
from JDF_Conversion import Timetable_Calculations, Utilities

root = pathlib.Path('Browser_Interface/online_files')
jdfRoot = pathlib.Path(root, 'upload')

Timetable_Import_Api = Blueprint('Flask_Timetable_Import', __name__)


@Timetable_Import_Api.route('/timetables/import/main', methods=['GET'])
def ImportForm():
    return render_template('timetables_import_form.html',
                           error=request.args.get('error'))


@Timetable_Import_Api.route('/timetables/import/result', methods=['GET'])
def ImportResult():
    overwritten = request.args.get('overwritten') == 'True'
    resultColor = 'blue' if overwritten else 'green'
    return render_template('timetables_import_result.html',
                           resultName=request.args.get('resultName'),
                           overwritten=overwritten,
                           resultColor=resultColor)


@Timetable_Import_Api.route('/timetables/import/submit', methods=['POST'])
def ImportSubmitted():
    resultName = request.form.get('jdfName')
    if not resultName:
        return redirect(url_for('Flask_Timetable_Import.ImportForm', error='Error: Name not provided'))
    resultName = Utilities.RemoveDirectoryMarks(resultName)
    tempFolder = pathlib.Path(root, 'temp','imported')
    # get the Excel file
    file = request.files.get('file')
    if not file:
        return redirect(url_for('Flask_Timetable_Import.ImportForm', error='Error: File not provided'))
    # get the name of the file
    filename = file.filename
    # check if the file is an Excel file
    if not filename.endswith('.xlsx'):
        return redirect(url_for('Flask_Timetable_Import.ImportForm', error='Error: File must be an excel file'))
    os.makedirs(pathlib.Path(tempFolder), exist_ok=True)
    file.save(pathlib.Path(tempFolder, filename))
    excelPath = pathlib.Path(tempFolder, filename)
    # time to generate the timetables
    try:
        tts = Table_Import.LoadTimetablesFromExcel(excelPath)
        # If there are only two timetable sheets, assume that they are forward and backward
        # Otherwise try to pair the sheets for forward and backward
        list_tts = list(tts.items())
        jdfNames = []
        name1, name2 = None, None
        for i in range(0, len(list_tts), 2):
            try:
                jdfName = f"{resultName}_{i // 2}"
                name1, tt1 = list_tts[i]
                name2, tt2 = list_tts[i + 1]

                extractorF = Table_Import.TimetableDataExtractor(tt1, name1, "en")
                extractorF.Extract()
                extractorF.ClassifyTrips()

                extractorB = Table_Import.TimetableDataExtractor(tt2, name2, "en")
                extractorB.Extract()
                extractorB.ClassifyTrips()

                convertor = Table_Import.TimetableDataToJdfConvertor.InitializeBidirectional(extractorF, extractorB)
                convertor.Convert(pathlib.Path(root, tempFolder, jdfName))
                jdfNames.append(jdfName)
            except Exception as e:
                return redirect(url_for('Flask_Timetable_Import.ImportForm',
                                        error=f'Error when parsing one of worksheets ({name1},{name2}): {str(e)}'))
        # Merge all the JDFs into one
        jdfProcessor = Timetable_Calculations.ParseMultipleFolders(
            [str(pathlib.Path(root, tempFolder, jdfName)) for jdfName in jdfNames]
        )
    except Exception as e:
        return redirect(url_for('Flask_Timetable_Import.ImportForm', error="Error when parsing: " + str(e)))
    try:
        # Copy from result folder to uploads, check if the folder exists
        outFolder = pathlib.Path(root, resultName)
        os.makedirs(outFolder, exist_ok=True)
        jdfProcessor.SerializeOut(outFolder)
        resultFolder = pathlib.Path(jdfRoot, resultName)
        overwritten = os.path.exists(resultFolder)
        shutil.rmtree(resultFolder, ignore_errors=True)
        shutil.move(outFolder, resultFolder)
    except Exception as e:
        return redirect(
            url_for('Flask_Timetable_Import.ImportForm', error="Error when saving imported file: " + str(e)))
    return redirect(
        url_for('Flask_Timetable_Import.ImportResult', resultName=resultName, overwritten=overwritten))
