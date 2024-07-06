"""!
@file Flask_Upload.py
@namespace Flask_Gui
@brief Functions for uploading/merging JDF files and storing them on the server
"""
import os
import pathlib
import shutil
from typing import List

from flask import Blueprint, request, redirect, url_for, render_template, session

from JDF_Conversion import Timetable_Calculations, Utilities

root = pathlib.Path("online_files")
jdfRoot = pathlib.Path(root, "upload")

Upload_Api = Blueprint('Flask_Upload', __name__)


@Upload_Api.route('/upload/main')
def Load():
    error = request.args.get('error')
    return render_template("upload_form.html", error=error)


# When folder gets uploaded, parse it as a single JDF
@Upload_Api.route('/upload/main/submit', methods=['POST'])
def SubmitFolder():
    global root
    temp = pathlib.Path(root, "temp")
    upload = pathlib.Path(root, "upload")
    # Get the files from the request
    incomingFiles = request.files.getlist("file[]")
    mergeType = request.form.get("merge")
    if mergeType == "no-merge":
        doMerge = False
        doCopy = True
    elif mergeType == "only-merge":
        doMerge = True
        doCopy = False
    elif mergeType == "keep-merge":
        doMerge = True
        doCopy = True
    else:
        doMerge = False
        doCopy = False
    if not incomingFiles or (not doMerge and not doCopy):
        return redirect(url_for('Flask_Upload.Load'))
    mergeName = request.form.get("merge_name")
    # sanitize for normal name
    if not mergeName:
        mergeName = "Merged"
    mergeName = Utilities.RemoveDirectoryMarks(mergeName)
    # Split files into folders based on the name
    foldersFiles = {}
    for f in incomingFiles:
        if not f.filename:
            continue
        path = pathlib.Path(f.filename)
        folderName = path.parent.name
        if folderName not in foldersFiles:
            foldersFiles[folderName] = []
        foldersFiles[folderName].append(f)
    os.makedirs(temp, exist_ok=True)
    good = []
    bad = []
    if not foldersFiles:
        return redirect(url_for('Flask_Upload.Load', error="Error: No folders were uploaded."))
    for folderName, files in foldersFiles.items():
        newFolder = pathlib.Path(temp, folderName)
        shutil.rmtree(newFolder, ignore_errors=True)
        os.makedirs(newFolder, exist_ok=True)
        for f in files:
            path = pathlib.Path(f.filename)
            res_name = path.name
            f.save(pathlib.Path(newFolder, res_name))
        # Parse the folder
        jdfProcessor = Timetable_Calculations.ParseSingleFolder(str(newFolder))
        if not jdfProcessor:
            bad.append(folderName)
        else:
            good.append(folderName)
    # Try to merge all good
    mergeOk = False
    if good and (not bad) and doMerge:
        jdfProcessor = Timetable_Calculations.ParseMultipleFolders([str(pathlib.Path(temp, g)) for g in good])
        if jdfProcessor:
            mergeOk = True
            os.makedirs(pathlib.Path(temp, mergeName), exist_ok=True)
            jdfProcessor.SerializeOut(pathlib.Path(temp, mergeName))

    # Now we move folders from the temp folder to the upload folder
    goodNew = []
    badNew = []
    goodOverwrite = []
    badOverwrite = []
    mergeOverwrite = False
    if doCopy:
        for g in good:
            newFolder = pathlib.Path(upload, g)
            if os.path.exists(newFolder):
                goodOverwrite.append(g)
            else:
                goodNew.append(g)
            shutil.rmtree(newFolder, ignore_errors=True)
            shutil.move(pathlib.Path(temp, g), newFolder)
        for b in bad:
            newFolder = pathlib.Path(upload, b)
            if os.path.exists(newFolder):
                badOverwrite.append(b)
            else:
                badNew.append(b)
    else:
        goodNew = good
        badNew = bad
    if doMerge:
        newFolder = pathlib.Path(upload, mergeName)
        if mergeOk:
            if os.path.exists(newFolder):
                mergeOverwrite = True
            else:
                mergeOverwrite = False
            shutil.rmtree(newFolder, ignore_errors=True)
            shutil.move(pathlib.Path(temp, mergeName), newFolder)
        else:
            if os.path.exists(newFolder):
                mergeOverwrite = True
            else:
                mergeOverwrite = False

    request_dict = {
        'doCopy': doCopy,
        'doMerge': doMerge,
        'goodNew': goodNew,
        'badNew': badNew,
        'goodOverwrite': goodOverwrite,
        'badOverwrite': badOverwrite,
        'mergeName': mergeName,
        'mergeOverwrite': mergeOverwrite,
        'mergeOk': mergeOk
    }

    session['request_dict'] = request_dict

    return redirect(url_for('Flask_Upload.ShowUploadResult'))


class UploadReport:
    def __init__(self, text: str, color: str, names: List[str]):
        self.text = text
        self.color = color
        self.names = names

@Upload_Api.route('/upload/result', methods=['GET'])
def ShowUploadResult():
    request_dict = session.get('request_dict', {})
    doCopy = request_dict.get('doCopy')
    doMerge = request_dict.get('doMerge')
    goodNew = request_dict.get('goodNew', [])
    badNew = request_dict.get('badNew', [])
    goodOverwrite = request_dict.get('goodOverwrite', [])
    badOverwrite = request_dict.get('badOverwrite', [])
    mergeName = request_dict.get('mergeName')
    mergeOverwrite = request_dict.get('mergeOverwrite')
    mergeOk = request_dict.get('mergeOk')

    results = []
    # Merge only
    if (not doCopy) and doMerge:
        if mergeOk:
            # Good merge, all folders were correct
            if mergeOverwrite:
                res = f"Folder {mergeName} was overwritten by merge from the following folders: "
                col = "green"
            else:
                res = f"Folder {mergeName} was created by merge from the following folders: "
                col = "blue"
            folders = goodNew
            results.append(UploadReport(res, col, folders))
        else:
            # Show which folders were valid for merge
            if mergeOverwrite:
                res = f"Merge failed, old folder {mergeName} remains."
                col = "brown"
                results.append(UploadReport(res, col, []))
            else:
                res = f"Merge failed, folder {mergeName} was not created."
                col = "red"
                folders = []
                results.append(UploadReport(res, col, folders))
            if goodNew:
                res = "Valid folders:"
                col = "green"
                folders = goodNew
                results.append(UploadReport(res, col, folders))
            if badNew:
                res = "Invalid folders:"
                col = "red"
                folders = badNew
                results.append(UploadReport(res, col, folders))
    # Copy and/or merge
    if doCopy:
        if goodNew:
            res = "Added new folders to the collection: "
            col = "green"
            folders = goodNew
            results.append(UploadReport(res, col, folders))
        if goodOverwrite:
            res = "Replaced these folders from collection: "
            col = "blue"
            folders = goodOverwrite
            results.append(UploadReport(res, col, folders))
        if badNew:
            res = "Upload failed for these folders: "
            col = "red"
            folders = badNew
            results.append(UploadReport(res, col, folders))
        if badOverwrite:
            res = "Upload failed, old versions remain:"
            col = "brown"
            folders = badOverwrite
            results.append(UploadReport(res, col, folders))
        # Merge and copy
        if doMerge:
            if mergeOk:
                if mergeOverwrite:
                    res = f"Merged into folder: {mergeName}"
                    col = "green"
                    folders = []
                    results.append(UploadReport(res, col, folders))
                else:
                    res = f"Merged into and replaced folder: {mergeName}"
                    col = "blue"
                    folders = goodNew
            else:
                if mergeOverwrite:
                    res = f"Merge failed, old folder {mergeName} remains."
                    col = "brown"
                    folders = []
                else:
                    res = f"Merge failed, folder {mergeName} was not created."
                    col = "red"
                    folders = []
            results.append(UploadReport(res, col, folders))
    return render_template("upload_result.html", error="", reports=results)
