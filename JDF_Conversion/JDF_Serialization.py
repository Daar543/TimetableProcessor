#!/usr/bin/env python3

"""!
@file JDF_Serialization.py
@namespace JDF_Classes
@brief This file contains functions for serializing timetable objects into CSV files
@note Uses corresponding Czech names
"""
import csv
import datetime
from typing import Dict, Iterable, List, TextIO

import pandas as pd

from JDF_Conversion import JDF_Classes, Utilities


def PackDeparture(departure: JDF_Classes.JdfZasSpoj, trip: JDF_Classes.JdfSpoj,
                  date: datetime.date = None):
    """!
    @brief Serialize departure into string
    """
    dic = {}
    dic["Stop name"] = departure.Zastavka.GetName()
    dic["Stop time"] = Utilities.SplitToHHMM(int(departure.Odjezd))
    if date:
        dic["Date"] = date.strftime("%Y-%m-%d")
    dic["Trip number"] = PackTrip(trip)
    return dic


def PackArrival(departure: JDF_Classes.JdfZasSpoj, trip: JDF_Classes.JdfSpoj,
                date: datetime.date = None):
    """!
    @brief Serialize departure into dict
    """
    dic = {}
    dic["Stop name"] = departure.Zastavka.GetName()
    dic["Stop time"] = Utilities.SplitToHHMM(int(departure.Prijezd if departure.Prijezd >= 0 else departure.Odjezd))
    if date:
        dic["Date"] = date.strftime("%Y-%m-%d")
    dic["Trip number"] = PackTrip(trip)
    return dic


def PackTrip(trip: JDF_Classes.JdfSpoj):
    """!
    @brief Serialize trip into dict
    """
    vychoziCZ = trip.First
    konecnaCZ = trip.Last
    vychoziCas = Utilities.SplitToHHMM(vychoziCZ.Odjezd)
    konecnyCas = Utilities.SplitToHHMM(konecnaCZ.Prijezd)
    zastVychozi = vychoziCZ.Zastavka.GetName()
    zastKonecna = konecnaCZ.Zastavka.GetName()
    trp = {
        "Line number": trip.CisloLinky,
        "Trip number": trip.CisloSpoje,
        "Initial stop": zastVychozi,
        "Departure time": vychoziCas,
        "Terminal stop": zastKonecna,
        "Arrival time": konecnyCas,
    }
    return trp


def SerializeWrite(columns: Dict[str, List[str]], outFile: TextIO):
    """!
    @brief Write the columns into CSV file as for JDF specification:
    @note Formát dat: CSV (comma separated values) – záznamově orientovaný formát dat s oddělovači
    (pole oddělena čárkou, záznamy odděleny středníkem a CRLF). Všechny údaje jsou uvedeny
    v textovém tvaru (textová pole uzavřená ve znacích uvozovky nahoře). Uvozovky uvnitř textu není
    třeba zdvojovat.
    @param columns: Dictionary of columns to write
    """
    df = pd.DataFrame(columns)
    """No header, columns separated by comma, rows separated by semicolon and CRLF,
    text fields are enclosed with quotation marks
    """
    df.to_csv(outFile, sep=",", index=False, header=False, lineterminator=";\n", quoting=csv.QUOTE_ALL)

def SerializeJdfCollection(coll: Iterable, outFile: TextIO):
    serialized = [x.Serialize() for x in coll]
    # Columns will have only numeric headers
    if not serialized:
        return
    columns = {str(i): [] for i in range(len(serialized[0]))}
    for ser in serialized:
        for col, var in zip(columns, ser):
            columns[col].append(var)
    SerializeWrite(columns, outFile)
