"""!
@file Table_Export.py
@namespace Timetable_Calculations
@brief This file contains functions for exporting JDF data to a timetable format
"""

import csv
import os
import pathlib
from typing import List, Optional, Tuple, Set, Dict, TextIO

from JDF_Conversion import Timetable_Calculations, JDF_Classes, Utilities
from JDF_Conversion.Table_Import import STOP_NAME_SEPARATOR
from JDF_Conversion.Timetable_Enums import NotStoppingStr, NotStopping

import xlsxwriter
import zipfile


def CreateEmptyTrip(stopCount: int) -> List[str]:
    """!
    @brief Create an empty trip row
    @param stopCount Number of stops
    @return List of empty strings
    """
    return [""] * (stopCount + 2)


def MakeTimetable(jdfProcessor: Timetable_Calculations.JdfProcessor,
                  line: Tuple[int, int], forward: bool, splitByOpDays: bool) \
        -> List[List[str]]:
    """!
    @brief Make a timetable, containing trips,stops,trip properties and times
    @param jdfProcessor JDF processor object
    @param line Line number and version
    @param forward True if forward direction, False if backward direction
    @return Timetable as a list of lists
    """
    ARR = "arrival"
    DEP = "departure"
    TC = "TNo"
    STOP_HEADER = "Stop"

    # Find the respective line
    line: JDF_Classes.JdfLinka
    lineData = jdfProcessor.JdfLinky.get(line)
    if lineData is None:
        return []
    lineStops = lineData.Zastavky
    stopRows = sorted(lineStops, key=lambda x: x.TC, reverse=not forward)
    stopIndexes = [s.TC for s in stopRows]
    stopNames = []
    for s in stopRows:
        name = s.Zastavka.GetName()
        signs = [str(k.CodeSign.value) for k in s.Zastavka.Kody]
        stopNames.append(name + STOP_NAME_SEPARATOR + " ".join(signs))
    depTable = []
    arrTable = []
    trips = sorted((trip for trip in lineData.Spoje.values() if trip.Smer == (1 if forward else -1)),
                   key=lambda t: t.First.Odjezd)
    if splitByOpDays:
        buckets = Utilities.CreateBuckets(trips, lambda t: t.GetOperationalPeriodType())
        # concatenate the contents of buckets, separated by None
        trips = []
        for k in sorted(buckets.keys()):
            trips += [item for item in buckets[k]] + [None]
    # We make departure-arrival for both directions together so they can be mirrored
    # (even if only one direction has different DA)
    # These stops will be printed with separate departure and arrival time
    daStops = set(stopEvent.TC
                  for trip in lineData.Spoje.values()
                  for stopEvent in trip.StopEvents.values()
                  if stopEvent.Odjezd >= 0 and stopEvent.Prijezd >= 0)
    if not trips:
        depTable = [CreateEmptyTrip(len(stopRows))]
        arrTable = [CreateEmptyTrip(len(stopRows))]
    else:
        for trip in trips:
            if not trip:
                depTable.append(CreateEmptyTrip(len(stopRows)))
                arrTable.append(CreateEmptyTrip(len(stopRows)))
                continue
            newRowDep = [None] * len(stopRows)
            newRowArr = [None] * len(stopRows)

            tripStops = trip.StopEvents.values()
            tripStops = sorted(tripStops, key=lambda x: x.TC, reverse=not forward)
            for stopEvent in tripStops:
                idx = stopIndexes.index(stopEvent.TC)
                codes = [str(k.CodeSign.value) for k in stopEvent.Kody]
                newRowDep[idx] = Utilities.SplitToHHMM(stopEvent.Odjezd)
                newRowDep[idx] += (" " + " ".join(codes)) if codes else ""
                newRowArr[idx] = Utilities.SplitToHHMM(stopEvent.Prijezd)
                newRowArr[idx] += (" " + " ".join(codes)) if codes else ""
            # Add trip number
            number = trip.CisloSpoje
            # Add trip properties
            signs = [str(tp.CodeSign.value) for tp in trip.Kody]
            timecode = [str(trip.TimeSign.CisloZnacky)] if trip.TimeSign else []
            props = " ".join(signs + timecode)  # returns empty string if no properties
            depTable.append([number] + [props] + newRowDep)
            arrTable.append([number] + [props] + newRowArr)
    # Transpose the tables
    depTable = list(map(list, zip(*depTable)))
    arrTable = list(map(list, zip(*arrTable)))

    # Add tariff numbers and stop names
    assert (len(depTable) == len(arrTable))
    for i in range(2, len(arrTable)):
        stopidx = i - 2
        if stopIndexes[stopidx] in daStops:
            for j in range(len(arrTable[i])):
                if Utilities.IsEmptyStoppingTime(arrTable[i][j]):
                    arrTable[i][j] = depTable[i][j]
                if Utilities.IsEmptyStoppingTime(depTable[i][j]):
                    depTable[i][j] = arrTable[i][j]
            arrTable[i] = [stopIndexes[stopidx], stopNames[stopidx]] + [ARR] + arrTable[i]
            depTable[i] = [stopIndexes[stopidx], stopNames[stopidx]] + [DEP] + depTable[i]
        else:
            # Merge the arrival and departure rows
            for j in range(len(arrTable[i])):
                if Utilities.IsEmptyStoppingTime(depTable[i][j]):
                    depTable[i][j] = arrTable[i][j]
                arrTable[i][j] = ""
            arrTable[i] = [stopIndexes[stopidx], stopNames[stopidx]] + [""] + arrTable[i]
            depTable[i] = [stopIndexes[stopidx], stopNames[stopidx]] + [""] + depTable[i]
    depTable[0] = [TC, STOP_HEADER, ""] + depTable[0]
    arrTable[0] = [TC, STOP_HEADER, ""] + arrTable[0]
    depTable[1] = ["", "", ""] + depTable[1]
    arrTable[1] = ["", "", ""] + arrTable[1]
    # Interleave the tables
    timetable = [depTable[0], depTable[1]]
    for i in range(2, len(depTable)):
        if arrTable[i][0] in daStops:
            timetable.append(arrTable[i])
            timetable.append(depTable[i])
        else:
            timetable.append(depTable[i])

    # Departure is implicit, so remove it if the previous row is for a different stop"
    for i in range(2, len(timetable)):
        r = timetable[i]
        if r[2] == DEP:
            if timetable[i - 1][0] != r[0]:
                r[2] = ""
    timetable[2][2] = DEP
    timetable[-1][2] = ARR
    # Replace all nones with empty strings
    timetable = [[x or "" for x in row] for row in timetable]

    return timetable


def CompleteTimetableMetadata(jdfProcessor: Timetable_Calculations.JdfProcessor,
                              timetable: List[List[str]],
                              line: Tuple[int, int], forward: bool) -> None:
    """!
    @brief Add metadata to a timetable such as line number.
    The output should look in the same way as tabular file from portal.radekpapez.cz
    @param jdfProcessor JDF processor object
    @param timetable The timetable with stop names and trips
    @param line Line number and version
    @param forward True if forward direction, False if backward direction
    """

    # Find the respective line
    line: JDF_Classes.JdfLinka
    lineData = jdfProcessor.JdfLinky.get(line)
    if lineData is None:
        lineNo = "?"
        lineName = "Unknown line"
        validFrom = "????-??-??"
        validTo = "????-??-??"
    else:
        lineNo = str(lineData.CisloLinky).zfill(6)
        lineName = lineData.NazevLinky
        validFrom = lineData.ValidFrom
        validTo = lineData.ValidTo
    lineCompleteNo = f"Line {lineNo}"
    if lineData:
        operator = lineData.Dopravce
    elif jdfProcessor.JdfDopravci and len(jdfProcessor.JdfDopravci) == 1:
        operator = next(iter(jdfProcessor.JdfDopravci.values()))
    else:
        operator = None
    if not operator:
        operatorData = "Unknown operator"
    else:
        operatorData = ", ".join([operator.Jmeno, operator.Sidlo, operator.Web, operator.IC])
    # Expand the timetable
    # two rows upwards
    timetable.insert(0, [""] * len(timetable[0]))
    timetable.insert(0, [""] * len(timetable[0]))
    # add line number
    timetable[0][0] = lineCompleteNo
    timetable[0][2] = lineName
    timetable[1][0] = f"Valid from {validFrom} to {validTo}"
    # add inverse if backward
    if not forward:
        timetable[1][2] = "reverse direction"
    # two rows downwards, add operator at the bottom
    timetable.append([""] * len(timetable[0]))
    timetable.append([""] * len(timetable[0]))
    timetable[-1][0] = f"Operated by: {operatorData}"
    return


def AddTimetableKilometrage(jdfProcessor: Timetable_Calculations.JdfProcessor,
                            timetable: List[List[str]], line: Tuple[int, int], forward: bool) -> None:
    """!
    @brief Add kilometrage to a timetable, based on trips in the direction
    @note The kilometrage columns are ordered by the first occurence of such a trip
    @param jdfProcessor JDF processor object
    @param timetable The timetable with stop names and trips
    @param line Line number and version
    @param forward True if forward direction, False if backward direction
    """
    # Find the respective line
    line: JDF_Classes.JdfLinka
    lineData = jdfProcessor.JdfLinky.get(line)
    if lineData is None:
        return
    # Do not make any assumptions about trip ordering, just read them directly from the table
    tripsRow = timetable[2]
    tripNos = []
    for i in range(3, len(tripsRow)):
        if tripsRow[i]:
            try:
                tripNos.append(int(tripsRow[i]))  # might parse more complicated trip number (e.g. "Spoj 12")
            except ValueError:  # if we end with undefined, do not parse
                continue
    trips = [lineData.Spoje.get(tripNo) for tripNo in tripNos]
    stopsToKm: Dict[Tuple[int, ...], List[str, ...]] = {}
    # Skipped stops (with "|") also count for the kilometrage, so we remove duplicities this way
    for trip in trips:
        currentStops: List[int] = []
        currentKm: List[str] = []
        stop: JDF_Classes.JdfZasSpoj
        for stop in trip.StopEvents.values():
            if stop.Odjezd == Utilities.NotStopping.PassedStop and stop.Prijezd == Utilities.NotStopping.PassedStop:
                currentKm.append(stop.Vzdalenost or NotStoppingStr.PassedStop.value)
                currentStops.append(stop.TC)
            elif stop.Odjezd == Utilities.NotStopping.DifferentRoute and stop.Prijezd == Utilities.NotStopping.DifferentRoute:
                continue
            else:
                currentKm.append(stop.Vzdalenost)
                currentStops.append(stop.TC)
        currentStopsT = tuple(currentStops)
        existingKm = stopsToKm.get(currentStopsT)
        if not existingKm:
            stopsToKm[currentStopsT] = currentKm
        else:
            newKm = list(existingKm)
            newKm = [currentKm[i] if e == NotStoppingStr.PassedStop.value else e for i, e in enumerate(newKm)]
            stopsToKm[currentStopsT] = newKm
    # Add the kilometrage columns

    for stopTcs, kmVals in stopsToKm.items():
        row = 2
        newColumn = ["" for _ in range(len(timetable))]
        newColumn[2] = "km"
        # Insert "<" for stops that are not in the trip
        for tc, km in zip(stopTcs, kmVals):
            for i in range(row + 1, len(timetable)):
                if timetable[i][0] == tc:  # watch out for data types, if string or int
                    row = i
                    break
                elif row > 2:  # do not insert until the first stop is found
                    newColumn[i] = NotStoppingStr.DifferentRoute.value
            newColumn[row] = km
            if timetable[row + 1][0] == tc:  # departure and arrival on the same stop
                row += 1
                newColumn[row] = km
        for ttrow, cell in zip(timetable, newColumn):
            ttrow.append(cell)
    return


def WriteAsCsv(file: TextIO, timetable: List[List[str]]) -> None:
    """!
    @brief Write a timetable as a CSV file
    @param file File to write to
    @param timetable The timetable with stop names and
    @note Better not use any other delimiter, as the stop names may contain commas
    """
    writer = csv.writer(file, delimiter="\t", lineterminator="\n")
    writer.writerows(timetable)
    return


def WriteAsExcel(file: str, sheetName: str, timetable: List[List[str]]) -> None:
    """!
    @brief Write a timetable as an Excel file
    @param file File NAME to write to
    @param sheetName Name of the sheet (only one)
    @param timetable The timetable with stop names and times
    """
    with xlsxwriter.Workbook(file) as workbook:
        worksheet = workbook.add_worksheet(sheetName)

        for row_num, data in enumerate(timetable):
            worksheet.write_row(row_num, 0, data)
        worksheet.autofit()
    return


def WriteBidirTimetable(file: str, timetableForward: List[List[str]], timetableBackward: List[List[str]]) -> None:
    """!
    @brief Write a timetable as Excel file with two sheets
    @param file File NAME to write to
    @param timetableForward Forward timetable
    @param timetableBackward Backward timetable
    """
    with xlsxwriter.Workbook(file, {"in_memory": True}) as workbook:
        worksheet1 = workbook.add_worksheet("Forward")

        for row_num, data in enumerate(timetableForward):
            worksheet1.write_row(row_num, 0, data)
        worksheet1.autofit()

        worksheet2 = workbook.add_worksheet("Backward")
        for row_num, data in enumerate(timetableBackward):
            worksheet2.write_row(row_num, 0, data)
        worksheet2.autofit()
    return


def ZipTimetables(jdfProcessor: Timetable_Calculations.JdfProcessor, packName: str, targetFolder: pathlib.Path,
                  namingMode: str, bidirectional: bool, splitDays: bool) -> None:
    """!
    @brief Pack all timetables into a ZIP
    @param jdfProcessor JDF processor object
    @param packName Name of the ZIP file
    @param targetFolder Folder to write the ZIP to
    @param namingMode How to name the individual timetables
    @note Creates intermediate files
    """
    # Get the access to the output folder
    if not os.path.isdir(targetFolder):
        os.makedirs(targetFolder, exist_ok=True)
        if not os.path.isdir(targetFolder):
            raise Exception(f"Cannot access the target folder {targetFolder}")
    # iterate over all lines
    fnames: List[str] = []
    for lineNo, lineVersion in sorted(jdfProcessor.JdfLinky.keys()):
        timetableF = None
        timetableB = None
        for direction in [True, False]:
            timetable = MakeTimetable(jdfProcessor, (lineNo, lineVersion), direction, splitDays)
            if not timetable:
                continue
            CompleteTimetableMetadata(jdfProcessor, timetable, (lineNo, lineVersion), direction)
            AddTimetableKilometrage(jdfProcessor, timetable, (lineNo, lineVersion), direction)
            # now we need to save the timetable before zippping it
            if direction:
                timetableF = timetable
            else:
                timetableB = timetable
        if namingMode == "default":  # just in case, will not add more modes rn
            lineName = f"{lineNo:06d}_{lineVersion:02d}"
            fileName = lineName + ".xlsx"
            sheetForwardName = lineName + "_T"
            sheetBackwardName = lineName + "_Z"
            if bidirectional:
                fnames.append(fileName)
            else:
                fileNameF = sheetForwardName + ".xlsx"
                fileNameB = sheetBackwardName + ".xlsx"
                fnames.append(fileNameF)
                fnames.append(fileNameB)
        else:
            raise Exception(f"Unknown naming mode {namingMode}")
        if bidirectional:
            WriteBidirTimetable(os.path.join(targetFolder, fileName), timetableF, timetableB)
        else:
            WriteAsExcel(os.path.join(targetFolder, fileNameF), sheetForwardName, timetableF)
            WriteAsExcel(os.path.join(targetFolder, fileNameB), sheetBackwardName, timetableB)

    # now we can zip the files
    with zipfile.ZipFile(os.path.join(targetFolder, packName), "w") as zfile:
        for fname in fnames:  # first one at the top
            zfile.write(os.path.join(targetFolder, fname), fname)
    # remove the intermediate files
    for fname in fnames:
        try:
            os.remove(os.path.join(targetFolder, fname))
        except PermissionError:
            continue
    return


def ExcelTimetables(jdfProcessor: Timetable_Calculations.JdfProcessor, packName: str, targetFolder: pathlib.Path,
                    namingMode: str, metadata: bool, splitDays: bool) -> None:
    """!
    @brief Create an Excel file with all timetables, then pack it into a ZIP
    @param jdfProcessor JDF processor object
    @param packName Name of the ZIP file
    @param targetFolder Folder to write the ZIP to
    @param namingMode How to name the individual timetables
    """
    # Get the access to the output folder
    if not os.path.isdir(targetFolder):
        os.makedirs(targetFolder, exist_ok=True)
        if not os.path.isdir(targetFolder):
            raise Exception(f"Cannot access the target folder {targetFolder}")
    # Make excel name be the same as the zip name, just with .xlsx extension
    excelName = pathlib.Path(packName).stem + ".xlsx"

    # iterate over all lines
    with xlsxwriter.Workbook(pathlib.Path(targetFolder, excelName)) as workbook:
        for lineNo, lineVersion in sorted(jdfProcessor.JdfLinky.keys()):
            for direction in [True, False]:
                timetable = MakeTimetable(jdfProcessor, (lineNo, lineVersion), direction, splitDays)
                if not timetable:
                    continue
                CompleteTimetableMetadata(jdfProcessor, timetable, (lineNo, lineVersion), direction)
                AddTimetableKilometrage(jdfProcessor, timetable, (lineNo, lineVersion), direction)
                # now we need to save the timetable before zippping it
                if namingMode == "default":  # just in case, will not add more modes rn
                    sheetName = f"{lineNo:06d}_{lineVersion:02d}_{'T' if direction else 'Z'}"
                else:
                    raise Exception(f"Unknown naming mode {namingMode}")
                worksheet = workbook.add_worksheet(sheetName)
                for row_num, data in enumerate(timetable):
                    worksheet.write_row(row_num, 0, data)
                worksheet.autofit()
    # now we can zip the file
    with zipfile.ZipFile(pathlib.Path(targetFolder, packName), "w") as zfile:
        zfile.write(pathlib.Path(targetFolder, excelName), excelName)
    try:
        os.remove(pathlib.Path(targetFolder, excelName))
    except PermissionError:
        pass
    return
