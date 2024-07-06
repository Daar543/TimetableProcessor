"""!
@file Table_Import.py
@namespace Timetable_Calculations
@brief Functions for converting timetables from tabular data to jdf
"""
import datetime
import os
import pathlib
import re
import csv
import warnings
from typing import Tuple, Dict, List, Optional

from JDF_Conversion import JDF_Classes, JDF_Serialization, Timetable_Enums, Utilities, Timetable_Calculations
from Map_Visualization.Stops import StopWithLocation

import openpyxl

STOP_NAME_SEPARATOR = "  "

def LoadTimetablesFromExcel(path: pathlib.Path) -> Dict[str, List[List[str]]]:
    """!
    @brief Load timetables from an excel file
    @param path The path to the excel file
    @return A dictionary of timetables, where the key is name of timetable and the value is a list of rows
    """
    # open the workbook
    workbook = openpyxl.load_workbook(path)
    # get the sheet names
    sheet_names = workbook.sheetnames
    # create a dictionary of timetables
    timetables = {}
    # loop through the sheets
    for sheet_name in sheet_names:
        # get the sheet
        sheet = workbook[sheet_name]
        # get the rows
        rows = sheet.rows
        # extract content as string from timetable
        timetable = [[cell for cell in row] for row in sheet.values]
        # add the timetable to the dictionary
        timetables[sheet_name] = timetable
    return timetables


class BareTimeTable:
    STOPS_ROW = 2
    STOPS_COL = 1

    DA_ROW = STOPS_ROW
    DA_COL = 3

    TC_HEADER_ROW = STOPS_ROW
    TC_VAL_ROW = TC_HEADER_ROW + 1
    TC_COL = 0

    TRIPS_NO_ROW = 0
    TRIPS_CHAR_ROW = 1
    TRIPS_TIME_ROW = STOPS_ROW
    TRIPS_COL = 3

    KM_HEADER_ROW = 0
    KM_ROW = TRIPS_TIME_ROW

    def __init__(self):
        """!
        @brief Initializes timetable with empty collections
        """
        self.Stops: List[Tuple[int, str, bool]] = []
        self.TripNotes: Dict[int, List[str]] = {}
        self.Times: Dict[int, List[int]] = {}
        self.Kilometrages: List[List[int]] = []

    def Extract(self, table: List[List[str]], firstCol: int, firstRow: int):
        """!
        @brief Gets all the data from a table
        @param table The table to get the data from
        @param firstCol The first column of the timetable
        @param firstRow The first row of the timetable
        """
        lastRow = BareTimeTable.getBottomRow(table, firstCol, firstRow)
        BareTimeTable.stringifyTable(table, firstCol, firstRow, lastRow)
        self.Stops = BareTimeTable.getStops(table, firstCol, firstRow, lastRow)
        self.TripNotes = BareTimeTable.getTripNotes(table, firstCol, firstRow, lastRow)
        self.Times = BareTimeTable.getTripTimes(table, firstCol, firstRow, lastRow)
        self.Kilometrages = BareTimeTable.getKilometrages(table, firstCol, firstRow, lastRow)
        return

    @staticmethod
    def getBottomRow(table: List[List[str]], firstCol: int, firstRow: int) -> int:
        """!
        @brief Gets the bottom row of the timetable to consider when extracting data
        @return The bottom row of the timetable, exclusive
        """
        for x in range(firstRow + BareTimeTable.TC_VAL_ROW, len(table)):
            consideredCol = table[x][firstCol + BareTimeTable.TC_COL]
            try:
                tc = int(consideredCol)
                if tc == 0:
                    return x
            except (ValueError, TypeError):
                return x
        return len(table)

    @staticmethod
    def stringifyTable(table: List[List[str]], firstCol: int, firstRow: int, lastRow: int):
        """!
        @brief Converts all values in the table to strings for unified approach
        @param table The table to convert
        @param firstCol The first column of the timetable
        @param firstRow The first row of the timetable
        @param lastRow The last row of the timetable
        """
        for row in range(firstRow, lastRow):
            for col in range(firstCol, len(table[row])):
                if table[row][col] is None:
                    table[row][col] = ""
                else:
                    table[row][col] = str(table[row][col])
        return

    @staticmethod
    def getStops(table: List[List[str]], firstCol: int, firstRow: int, lastRow: int) -> List[Tuple[int, str, bool]]:
        """!
        @brief Gets the stops from a table
        @param table The table to get the stops from
        @param firstCol The first column of the timetable
        @param firstRow The first row of the timetable
        @param lastRow The last row of the timetable
        @return A list of stops in the timetable
        """
        stops = []
        startRow = firstRow + BareTimeTable.STOPS_ROW
        tcCol = firstCol + BareTimeTable.TC_COL
        stopNameCol = firstCol + BareTimeTable.STOPS_COL
        lastTc = -1
        for row in range(startRow, lastRow):
            stopName = table[row][stopNameCol]
            if not stopName:
                break
            stopName = stopName.strip()
            tc = table[row][tcCol]
            tc = int(tc)
            if tc == lastTc:
                stops.append((tc, stopName, False))
            else:
                stops.append((tc, stopName, True))
                lastTc = tc
        stops[-1] = (stops[-1][0], stops[-1][1], False)
        return stops

    @staticmethod
    def getTripNotes(table: List[List[str]], firstCol: int, firstRow: int, lastRow: int) -> Dict[int, List[str]]:
        """!
        @brief Gets the trip notes from a table
        @param table The table to get the trip notes from
        @param firstCol The first column of the timetable
        @param firstRow The first row of the timetable
        @return A dictionary of trip notes in the timetable
        """
        tripNotes = {}
        tripNotesCol = firstCol + BareTimeTable.TRIPS_COL
        tripNosRow = firstRow + BareTimeTable.TRIPS_NO_ROW
        tripNotesRow = firstRow + BareTimeTable.TRIPS_CHAR_ROW
        for col in range(tripNotesCol, len(table[firstRow])):
            tripNoFull = table[tripNosRow][col]
            if not tripNoFull:
                continue
            tripNo = str(tripNoFull).strip().split(" ")[-1]
            if tripNo == "km":
                break
            elif not tripNo:
                continue
            try:
                tripNo = int(tripNo)
            except ValueError:
                break
            tripNote = table[tripNotesRow][col]
            if tripNote == "":
                tripNote = None
            else:
                tripNote = str(tripNote).split(" ")
            # verify if we do not duplicate trips
            if tripNo in tripNotes:
                raise ValueError("Duplicate trip number in timetable")
            tripNotes[tripNo] = tripNote
        return tripNotes

    @staticmethod
    def getTripTimes(table: List[List[str]], firstCol: int, firstRow: int, lastRow: int) -> Dict[int, List[str]]:
        """!
        @brief Gets the times from a table
        @param table The table to get the times from
        @param firstCol The first column of the timetable
        @param firstRow The first row of the timetable
        @return A dictionary of times in the timetable
        """
        times = {}
        startCol = firstCol + BareTimeTable.TRIPS_COL
        tripNosRow = firstRow + BareTimeTable.TRIPS_NO_ROW
        tripTimesRow = firstRow + BareTimeTable.TRIPS_TIME_ROW
        for col in range(startCol, len(table[firstRow])):
            tripNoFull = table[tripNosRow][col]
            if not tripNoFull:
                continue
            tripNo = str(tripNoFull).strip().split(" ")[-1]
            if tripNo == "km":
                break
            elif not tripNo:
                continue
            try:
                tripNo = int(tripNo)
            except ValueError:
                break
            tripTimes = []
            for row in range(tripTimesRow, lastRow):
                currentTime = table[row][col]
                tripTimes.append(currentTime)
            if tripNo in times:
                raise ValueError("Duplicate trip number in timetable")
            times[tripNo] = tripTimes
        return times

    @staticmethod
    def getKilometrages(table: List[List[str]], firstCol: int, firstRow: int, lastRow: int) -> List[List[str]]:
        """!
        @brief Gets the kilometrages from a table
        @param table The table to get the kilometrages from
        @param firstCol The first column of the timetable
        @param firstRow The first row of the timetable
        @param lastRow The last row of the timetable
        @return A list of kilometrages in the timetable
        """
        kilometrages = []
        # Detect kilometrages col by iterating from right
        kilometragesHeaderRow = firstRow + BareTimeTable.KM_HEADER_ROW
        col = len(table[firstRow])
        kilometragesRow = firstRow + BareTimeTable.KM_ROW
        while True:
            col -= 1
            if col <= firstCol + BareTimeTable.TRIPS_COL:
                break
            header = table[kilometragesHeaderRow][col]
            if header == "":
                continue
            elif header != "km":
                break
            currentKm = []
            for row in range(kilometragesRow, lastRow):
                kilometrage = table[row][col]
                currentKm.append(kilometrage)
            # if whole currentKm is empty, we are done
            if all([not x for x in currentKm]):
                break
            kilometrages.append(currentKm)
        return kilometrages


class TimetableDataExtractor:

    def __init__(self, timetable, name, locale="cz"):
        """!
        @brief Extracts data from a timetable
        @param timetable The timetable to extract data from
        @param name The name of the sheet
        @param locale Language of the notes in the timetable (CZ/EN supported)
        """
        self.timetable = timetable
        self.name = name
        self.Locale = locale.lower()
        self.ExtractedTimeTable = None
        self.LineNo = None
        self.Validity = None
        self.LineName = None
        self.Operator = None
        self.ClassifiedTrips = None
        self.TripCodes = None
        self.ReadyToConvert = False

    def Extract(self):
        """!
        @brief Extracts data from two timetables, which are treated as opposite directions of the same line
        """
        ldr, ldc = self.FindLineDeclarationLocation()
        # get the line declaration
        line_declaration = self.timetable[ldr][ldc]
        # get the line number
        # get the line name
        lnr, lnc = self.FindLineNameLocation((ldr, ldc))
        line_name = self.timetable[lnr][lnc]
        # get the left top corner of time and stops
        ttr, ttc = self.FindTimeTableLocation()
        barett = BareTimeTable()
        barett.Extract(self.timetable, ttc, ttr)

        self.ExtractedTimeTable = barett

        # check the operator
        opr, opc = self.FindOperatorLocation()
        operator = self.timetable[opr][opc]
        # check the validity
        vr, vc = self.FindValidityLocation()
        validity = self.timetable[vr][vc]

        self.Operator = self.ExtractOperator(operator)
        self.Validity = self.ExtractValidity(validity)
        self.LineName = self.ExtractLineName(line_name)
        self.LineNo = self.ExtractLineNo(line_declaration)

    def ExtractLineNo(self, line_declaration: str) -> int:
        tokens = line_declaration.split(" ")
        return int(tokens[-1])

    def ExtractLineName(self, line_name: str) -> str:
        return line_name

    def ExtractValidity(self, validity: str) -> Tuple[datetime.date, datetime.date]:
        if self.Locale == "cz":
            # "Platnost od YYYY-MM-DD do YYYY-MM-DD"
            tokens = validity.split(" ")
            from_date = tokens[2]
            to_date = tokens[4]
        elif self.Locale == "en":
            # "Valid from YYYY-MM-DD to YYYY-MM-DD"
            tokens = validity.split(" ")
            from_date = tokens[2]
            to_date = tokens[4]
        else:
            raise ValueError("Unsupported locale")
        try:
            from_date = datetime.datetime.strptime(from_date, "%Y-%m-%d").date()
            to_date = datetime.datetime.strptime(to_date, "%Y-%m-%d").date()
        except ValueError as ve:
            # backup for CZ format
            if self.Locale == "cz":
                from_date = datetime.datetime.strptime(from_date, "%d.%m.%Y").date()
                to_date = datetime.datetime.strptime(to_date, "%d.%m.%Y").date()
            else:
                raise ve
        return from_date, to_date

    def ExtractOperator(self, operator: str) -> Dict[str, str]:
        # "Přepravu zajišťuje: ČSAD BUS Uherské Hradiště a.s., Malinovského 874, 686 19 Uherské Hradiště, www.csaduh.cz"
        intro, data = operator.split(":", 1)
        data = data.strip()
        values = data.split(",")
        res = {}
        if len(values) >= 1:
            res["name"] = values[0].strip()
        else:
            if self.Locale == "cz":
                res["name"] = "Neznámý dopravce"
            elif self.Locale == "en":
                res["name"] = "Unknown operator"
            else:
                raise ValueError("Unsupported locale")
        if len(values) >= 3:
            res["address"] = ",".join([values[1].strip(), values[2].strip()])
        if len(values) >= 3:
            res["web"] = values[3].strip()
        return res

    def FindLineDeclarationLocation(self) -> Tuple[int, int]:
        line_no = "Line number" if self.Locale == "cz" else "Line" if self.Locale == "en" else None
        if line_no is None:
            raise ValueError("Unsupported locale")
        for rowno, rowcells in enumerate(self.timetable):
            for colno, cell in enumerate(rowcells):
                if cell and str(cell).startswith(line_no):
                    return rowno, colno
        raise ValueError("Timetable does not contain line declaration")

    def FindLineNameLocation(self, lineDeclarationLocation:Tuple[int,int]) -> Optional[Tuple[int, int]]:
        row = lineDeclarationLocation[0]
        col = lineDeclarationLocation[1]
        for i in range(1, 2+1):
            if self.timetable[row][col+i]:
                return row,col+i
        raise ValueError("Line name not found")

    def FindTimeTableLocation(self) -> Tuple[int, int]:
        # find cell with "Tč" for cz or "TNo" for en
        tc = "Tč" if self.Locale == "cz" else "TNo" if self.Locale == "en" else None
        if tc is None:
            raise ValueError("Unsupported locale")
        for rowno, rowcells in enumerate(self.timetable):
            if tc in rowcells:
                return rowno, rowcells.index(tc)
        raise ValueError("Timetable does not contain time table column")

    def FindValidityLocation(self) -> Optional[Tuple[int, int]]:
        # find cell with "Platnost od" for cz or "Valid from" for en
        validity = "Platnost od" if self.Locale == "cz" else "Valid from" if self.Locale == "en" else None
        if validity is None:
            raise ValueError("Unsupported locale")
        for rowno, rowcells in enumerate(self.timetable):
            for colno, cell in enumerate(rowcells):
                if cell and str(cell).startswith(validity):
                    return rowno, colno
        return None

    def FindOperatorLocation(self) -> Tuple[int, int]:
        text = "Přepravu zajišťuje:" if self.Locale == "cz" else "Operated by:" if self.Locale == "en" else None
        if text is None:
            raise ValueError("Unsupported locale")
        for rowno, rowcells in enumerate(self.timetable):
            for colno, cell in enumerate(rowcells):
                if cell and str(cell).startswith(text):
                    return rowno, colno
        raise ValueError("Timetable does not contain operator")

    def ClassifyTrips(self):
        self.fixTimes()
        tripsToKm = self.identifyKilometrages()
        self.ClassifiedTrips = self.compactTrips(tripsToKm)
        self.TripCodes = self.ExtractedTimeTable.TripNotes
        self.ReadyToConvert = True

    def fixTimes(self):
        """!
        @brief Fixes the times in the timetable by replacing None with empty string
        """
        for tripId in self.ExtractedTimeTable.Times:
            currentTrip = self.ExtractedTimeTable.Times[tripId]
            self.ExtractedTimeTable.Times[tripId] = [Timetable_Enums.NotStoppingStr.UnusedStop.value
                                                     if x is None else x for x in currentTrip]

    def identifyKilometrages(self) -> Dict[int, Optional[List[int]]]:
        """!
        @brief Assigns kilometres to each trip based on the route
        """
        allTrips = self.ExtractedTimeTable.Times
        allKm = self.ExtractedTimeTable.Kilometrages
        result = {}
        for tripId, tripTimes in allTrips.items():
            kmIndex = self.identifyKilometrageCurrentTrip(tripTimes, allKm)
            if kmIndex == -1:
                result[tripId] = [None for _ in range(len(tripTimes))]
            else:
                assert (0 <= kmIndex < len(allKm))
                result[tripId] = allKm[kmIndex]
        return result

    @staticmethod
    def identifyKilometrageCurrentTrip(trip: List[str], kilometrages: List[List[str]]) -> int:
        """!
        @brief Identifies kilometrage of the trip
        @param trip List of stop times
        @param kilometrages List of kilometrages (each kilometrage is list of distances)
        @return Index of kilometrage
        @note If a stop has time, a km value must appear.
        If the stop is on a different route, then km value must not appear.
        """
        firstRow = -1
        consideredIndexes = list(range(len(kilometrages)))
        for row, stopTime in enumerate(trip):
            if stopTime == Timetable_Enums.NotStoppingStr.UnusedStop.value:
                continue  # unused stop
            elif stopTime == Timetable_Enums.NotStoppingStr.PassedStop.value:
                # eliminate kilometrages where is None or empty
                consideredIndexes = [x for x in consideredIndexes
                                     if kilometrages[x][row] is not None and kilometrages[x][row] != ""]
            elif stopTime == Timetable_Enums.NotStoppingStr.DifferentRoute.value:
                # eliminate kilometrages where is a value
                consideredIndexes = [x for x in consideredIndexes
                                     if kilometrages[x][row] is None or kilometrages[x][row] == ""
                                     or kilometrages[x][row] == Timetable_Enums.NotStoppingStr.DifferentRoute.value]
            else:  # Assume the time is valid
                if firstRow == -1:
                    firstRow = row
                # eliminate kilometrages which cannot be converted to int
                consideredIndexes = [x for x in consideredIndexes
                                     if Utilities.IsNum(kilometrages[x][row])]
        if len(consideredIndexes) == 1:
            return consideredIndexes[0]
        elif len(consideredIndexes) > 1:
            # prioritize kilometrages starting with "0"
            zeroKmIndexes = [x for x in consideredIndexes if kilometrages[x][firstRow] == "0"]
            if len(zeroKmIndexes) >= 1:
                return zeroKmIndexes[0]
            else:
                return consideredIndexes[0]
        else:
            return -1

    def compactTrips(self, tripKilometrages) -> Dict[int, List[Tuple[int, bool, str, str]]]:
        """!
        @brief Compacts trips into a single definition
        @param tripKilometrages Kilometrages of each trip
        @return Dictionary of trip definitions
        """
        result = {}
        stops = self.ExtractedTimeTable.Stops
        for tripId, tripTimes in self.ExtractedTimeTable.Times.items():
            km = tripKilometrages[tripId]
            if km is None:
                km = [None for _ in range(len(tripTimes))]
            result[tripId] = self.compactTrip(stops, tripTimes, km)
        return result

    def compactTrip(self, stops: List[Tuple[int, str, bool]], tripTimes: List[str], kilometrage: List[str]) \
            -> List[Tuple[int, bool, str, str]]:
        """!
        @brief Compacts a single trip into a single definition
        @param tripId Id of the trip
        @param tripTimes List of stop times
        @param kilometrages List of kilometrages
        @return List of stops: (tariff number, departure/arrival, time with characteristics, kilometrage)
        """
        result = []
        currentKm = 0
        kmOffset = 0
        first = True
        for s, t, k in zip(stops, tripTimes, kilometrage):
            tc, nm, da = s
            if t == Timetable_Enums.NotStoppingStr.UnusedStop.value:
                # Ignore unused stops
                continue
            elif t == Timetable_Enums.NotStoppingStr.PassedStop.value:
                # kilometrage is assumed to exist, but no issue if it does not
                try:
                    km = int(k)
                except (ValueError, TypeError):
                    km = currentKm
            elif t == Timetable_Enums.NotStoppingStr.DifferentRoute.value:
                # always skip kilometrage
                km = -1
            else:
                if k is None:  # kilometrage is undefined
                    km = currentKm
                else:  # otherwise kilometrage should be a number
                    km = int(k)
            if first and km is not None:
                kmOffset = km
                first = False

            if km == -1:
                km_str = Timetable_Enums.NotStoppingStr.DifferentRoute.value
            else:
                km_str = str(km - kmOffset)

            result.append((tc, da, t, km_str))
        # Last stop is always arrival only
        result[-1] = (result[-1][0], False, result[-1][2], result[-1][3])

        return result


class TimetableDataToJdfConvertor:

    def __init__(self):
        self.Locale: str = ""
        self.Operator: Dict[str, str] = {}
        self.Validity: Tuple[Optional[datetime.datetime], Optional[datetime.datetime]] = (None, None)
        self.LineName: str = ""
        self.LineNo: str = ""
        self.Stops: List[Tuple[int, str, bool]] = []
        self.Trips: Dict[int, List[Tuple[int, bool, str, str]]] = {}
        self.TripCodes: Dict[int, List[str]] = {}
        self.uniDirectional: bool = True

    @staticmethod
    def CanBeMerged(e1: TimetableDataExtractor, e2: TimetableDataExtractor) -> Tuple[bool, str]:
        if not e1.ReadyToConvert:
            return False, "Timetable on initial extractor must be prepared before merging"
        if not e2.ReadyToConvert:
            return False, "Timetable on merged extractor must be prepared before merging "
        metadataEqual = \
            e1.Operator == e2.Operator and \
            e1.Validity == e2.Validity and \
            e1.LineName == e2.LineName and \
            e1.LineNo == e2.LineNo
        if not metadataEqual:
            return False, "Metadata of timetables must be equal before merging"
        stops1 = sorted((s[0], s[1]) for s in e1.ExtractedTimeTable.Stops)
        stops2 = sorted((s[0], s[1]) for s in e2.ExtractedTimeTable.Stops)
        if not stops1==stops2:
            # Place the stops in one line for better comparison
            errorLines = zip(stops1, stops2)
            errorInfo = "\n".join([(f"{s1} x {s2}") + ("OK" if s1==s2 else "DIFFERENT") for s1, s2 in errorLines])
            return False, "Stops of timetables must be equal or opposite before merging. \n" + errorInfo

        return True, ""

    @staticmethod
    def InitializeUnidirectional(e1: TimetableDataExtractor):
        c = TimetableDataToJdfConvertor()
        c.Locale = e1.Locale
        c.Operator = e1.Operator
        c.Validity = e1.Validity
        c.LineName = e1.LineName
        c.LineNo = e1.LineNo
        c.Stops = e1.ExtractedTimeTable.Stops
        c.Trips = e1.ClassifiedTrips
        c.TripCodes = e1.ExtractedTimeTable.TripNotes
        c.uniDirectional = True
        return c

    @staticmethod
    def InitializeBidirectional(e1: TimetableDataExtractor, e2: TimetableDataExtractor):
        canMerge, reason = TimetableDataToJdfConvertor.CanBeMerged(e1, e2)
        if not canMerge:
            raise ValueError(reason)
        c = TimetableDataToJdfConvertor()
        c.Locale = e1.Locale
        c.Operator = e1.Operator
        c.Validity = e1.Validity
        c.LineName = e1.LineName
        c.LineNo = e1.LineNo
        c.Stops = e1.ExtractedTimeTable.Stops
        c.Trips = e1.ClassifiedTrips
        c.Trips.update(e2.ClassifiedTrips)
        c.TripCodes = e1.ExtractedTimeTable.TripNotes
        c.TripCodes.update(e2.ExtractedTimeTable.TripNotes)
        c.uniDirectional = False
        return c

    def Convert(self,outputFolder:pathlib.Path):
        codeIdentifiers = {}
        codeDict = {}
        operatorIdentifier: str = self.Operator.get("IC", "88888888")
        operatorDiscriminator: str = "1"
        lineDiscriminator: str = "1"
        operatorPhone: str = self.Operator.get("phone","123456789")
        operatorEmail: str = self.Operator.get("email","")
        state = "CZ"

        line = JDF_Classes.JdfLinka(
            str(self.LineNo),
            str(self.LineName),
            operatorIdentifier,
            Timetable_Enums.TypLinky.Regionalni.value,
            Timetable_Enums.Prostredek.Autobus.value,
            Utilities.BoolToNumeric(False),
            Utilities.BoolToNumeric(False),
            Utilities.BoolToNumeric(False),
            Utilities.BoolToNumeric(self.uniDirectional),
            "",
            "",
            "",
            "",
            Utilities.ConvertToDDMMYYYY(self.Validity[0]),
            Utilities.ConvertToDDMMYYYY(self.Validity[1]),
            operatorDiscriminator,
            lineDiscriminator,
        )
        line.ConvertTimes()


        stopNameToId = {}
        tcToStopId = {}
        stopIdToGlobalStopCodes = {}
        stopId = 1
        for stopTc, stopName, isDeparture in self.Stops:
            stopNameIsolated = stopName.split(STOP_NAME_SEPARATOR)[0]
            if stopNameIsolated not in stopNameToId:
                stopNameToId[stopNameIsolated] = str(stopId)
                stopId += 1
            tcToStopId[stopTc] = stopNameToId[stopNameIsolated]
        zasLinky = {}
        codeId = 1
        for stopTc, stopName, isDeparture in self.Stops:
            stopCellSplit = stopName.split(STOP_NAME_SEPARATOR,1)
            stopNameIsolated = stopCellSplit[0]
            # these should be only 1 chars
            stopNameCharacteristics = stopCellSplit[1].split(" ") if len(stopCellSplit) > 1 else []
            stopId = stopNameToId[stopNameIsolated]
            globalCharacteristics = stopIdToGlobalStopCodes.get(stopId, [])
            localCharacteristics = []
            for c in stopNameCharacteristics:
                # check if c is in enum PevneKody
                try:
                    c = Timetable_Enums.PevneKody(c)
                except ValueError:
                    raise ValueError("Unknown stop characteristic: " + c)
                if c in [Timetable_Enums.PevneKody.Paragraf,
                         Timetable_Enums.PevneKody.Paragraf1,
                         Timetable_Enums.PevneKody.Paragraf2,
                         Timetable_Enums.PevneKody.Paragraf3]:
                    category = "local"
                elif c in [Timetable_Enums.PevneKody.NaZnameni,
                           Timetable_Enums.PevneKody.Vystup,
                           Timetable_Enums.PevneKody.Nastup]:
                    category = "either"
                else:
                    category = "global"
                c = c.value
                if c not in codeIdentifiers:
                    fullCode = JDF_Classes.JdfPevnyKod(str(codeId), c)
                    codeIdentifiers[c] = fullCode
                    codeDict[str(codeId)] = fullCode
                    codeId += 1
                if category == "global":
                    globalCharacteristics.append(codeIdentifiers[c])
                elif category == "local":
                    localCharacteristics.append(codeIdentifiers[c])
                elif category == "either":
                    # we can run into an edge case here if a stop has 3 local codes, but I believe this is rare
                    localCharacteristics.append(codeIdentifiers[c])

            zasLinky[stopTc] = (stopId, localCharacteristics)
            stopIdToGlobalStopCodes[stopId] = globalCharacteristics

        lineStops = [JDF_Classes.JdfZasLinka(
            str(self.LineNo),
            str(tc),
            "",
            str(zid),
            "",
            *[codes[i].CodeNumber if len(codes) > i else "" for i in range(3)],
            str(lineDiscriminator)
        )
            for tc, zl in zasLinky.items() for zid, codes in [zl]
        ]
        for l in lineStops:
            l.BindCodes(codeDict)

        spoje = {}
        # codeId stays
        for tripId, tripCodes in sorted(self.TripCodes.items()):
            if not tripCodes:
                tripCodes = []
            currentCodes = []
            for c in tripCodes:
                try:
                    c = Timetable_Enums.PevneKody(c).value
                except ValueError:
                    # check for time code
                    try:
                        c = int(c)
                        if not 10 <= c <= 99:
                            raise ValueError("Time code must be between 10 and 99")
                        else:
                            #warnings.warn(f"Time code ({c}) will be ignored when parsing hand-written timetables")
                            continue
                    except ValueError:
                        raise ValueError("Unknown trip characteristic: " + c)
                if c not in codeIdentifiers:
                    fullCode = JDF_Classes.JdfPevnyKod(str(codeId), c)
                    codeIdentifiers[c] = fullCode
                    codeDict[str(codeId)] = fullCode
                    codeId += 1
                currentCodes.append(codeIdentifiers[c])
            spoje[tripId] = currentCodes
        trips = [JDF_Classes.JdfSpoj(
            str(self.LineNo),
            str(tripId),
            *[tripCodes[i].CodeNumber if len(tripCodes) > i else "" for i in range(10)],
            "",
            str(lineDiscriminator)
        )
            for tripId, tripCodes in spoje.items()
        ]
        for t in trips:
            t.BindCodes(codeDict)

        zasSpoje = {}
        # codeId stays
        print(f"{self.LineNo}",end=" ")
        stopHelper = [(tc, dep) for tc, name, dep in self.Stops]
        for tripId, tripTimes in sorted(self.Trips.items()):
            lastTc = -1
            tcadk = []
            for tc, dep, t, km in tripTimes:
                codes = []
                if t == "None":
                    t = Timetable_Enums.NotStoppingStr.UnusedStop.value # fix for badly imported None values
                if len(t) >= 4:
                    if t[2] == ":":
                        # either HH:MM or HH:MM:SS (to work from excel imports)
                        try:
                            dt = datetime.datetime.strptime(t[0:8], "%H:%M:%S")
                            currentCodes = t[8:]
                        except ValueError:
                            try:
                                dt = datetime.datetime.strptime(t[0:5], "%H:%M")
                                currentCodes = t[5:]
                            except ValueError:
                                raise ValueError(f"Time must be in HH:MM:SS or HH:MM format (provided {t})")
                        timeVal = dt.strftime("%H%M")
                    else:
                        raise ValueError(f"Time must be in HH:MM format (provided {t})")
                    for c in currentCodes:
                        if not c: continue
                        try:
                            c = Timetable_Enums.PevneKody(c).value
                        except ValueError:
                            warnings.warn(f"Unknown code for departure/arrival: {c}")
                            continue
                        if c not in codeIdentifiers:
                            fullCode = JDF_Classes.JdfPevnyKod(str(codeId), c)
                            codeIdentifiers[c] = fullCode
                            codeDict[str(codeId)] = fullCode
                            codeId += 1
                        codes.append(codeIdentifiers[c])
                else:
                    if t == Timetable_Enums.NotStoppingStr.UnusedStop.value or not t:
                        continue
                    elif t == Timetable_Enums.NotStoppingStr.PassedStop.value:
                        timeVal = str(t)
                    elif t == Timetable_Enums.NotStoppingStr.DifferentRoute.value:
                        timeVal = str(t)
                    else:
                        raise ValueError("Unknown time for departure/arrival: " + t)
                """
                if tc != lastTc:
                    tcadk.append((tc,codes,"",time,km))
                else:
                    lastTcad = tcadk[-1]
                    tcadk[-1] = (lastTcad[0],lastTcad[1],time,lastTcad[3])
                """
                if dep:
                    tcadk.append((tc, codes, "", timeVal, km))
                else:
                    tcadk.append((tc, codes, timeVal, "", km))
                lastTc = tc
            # if last element of tcad has empty arrival, exchange it with departure
            lastTcad = tcadk[-1]
            if not lastTcad[2]:
                tcadk[-1] = (lastTcad[0], lastTcad[1], lastTcad[3], "",lastTcad[4])
            zasSpoje[tripId] = tcadk

        stopTimes = [JDF_Classes.JdfZasSpoj(
            self.LineNo,
            str(tripId),
            str(tc),
            str(tcToStopId[tc]),
            "",
            "",
            *[codes[i].CodeNumber if len(codes) > i else "" for i in range(3)],
            km,
            arr,
            dep,
            arr,
            dep,
            lineDiscriminator
        )
            for tripId, tcadk in zasSpoje.items() for tc, codes, arr, dep, km in tcadk
        ]
        for st in stopTimes:
            st.BindCodes(codeDict)
            st.FormatTime()

        timeCodes = []  # they are mandatory, but will stay empty

        jdfVersion = JDF_Classes.JdfVerze(
            "1.11",
            "",
            "",
            "",
            datetime.datetime.now().strftime("%d%m%Y"),
            "",
        )
        jdfVersion.ConvertTimes()

        globalStops = []
        for stopName, stopId in stopNameToId.items():
            stopCodes = stopIdToGlobalStopCodes[stopId]
            obec, castObce, blizsiMisto, blizkaObec = StopWithLocation.ParseName(stopName)
            globalStops.append((stopId, obec, castObce, blizsiMisto, blizkaObec, stopCodes))

        allStops = [JDF_Classes.JdfZastavka(
            str(stopId),
            obec,
            castObce,
            blizsiMisto,
            blizkaObec,
            state,
            *[stopCodes[i].CodeNumber if len(stopCodes) > i else "" for i in range(6)]
        )
            for stopId, obec, castObce, blizsiMisto, blizkaObec, stopCodes in globalStops
        ]
        for s in allStops:
            s.BindCodes(codeDict)

        operator = JDF_Classes.JdfDopravce(
            operatorIdentifier,
            "",
            self.Operator.get("name","Unknown operator"),
            "1",
            "",
            self.Operator.get("address","Unknown address"),
            self.Operator.get("phone","123456789"),
            "",
            "",
            "",
            self.Operator.get("email","Unknown email"),
            self.Operator.get("web","Unknown web"),
            operatorDiscriminator
        )

        fileNamesCollections = [
            ("Caskody.txt", timeCodes),
            ("Dopravci.txt",[operator]),
            ("Linky.txt", [line]),
            ("Pevnykod.txt", list(codeDict.values())),
            ("Spoje.txt", trips),
            ("VerzeJDF.txt", [jdfVersion]),
            ("Zaslinky.txt",lineStops),
            ("Zasspoje.txt", stopTimes),
            ("Zastavky.txt", allStops),
        ]
        os.makedirs(outputFolder,exist_ok=True)
        for fname,collection in fileNamesCollections:
            with open(os.path.join(outputFolder,fname),"w",encoding=Timetable_Calculations.JDF_ENCODING) as f:
                JDF_Serialization.SerializeJdfCollection(collection,f)

        return
