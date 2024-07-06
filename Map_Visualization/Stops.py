import json
import os
import csv
import sys
import pathlib
from typing import List, TextIO, Union

"""!
@file Stops.py
@namespace Map_Visualization
@brief Functions for requesting and displaying stop data
"""


class StopWithLocation:
    """!
    @brief Class for storing stop data with location
    """

    def __init__(self, obec: str, castObce: str, blizsiMisto: str, blizkaObec: str,
                 latitude: Union[str, float], longitude: Union[str, float]):
        self.Obec = obec
        self.CastObce = castObce
        self.BlizsiMisto = blizsiMisto
        self.BlizkaObec = blizkaObec
        self.Latitude = float(latitude)
        self.Longitude = float(longitude)

    def __lt__(self, other):
        if self.Obec != other.Obec:
            return self.Obec < other.Obec
        if self.BlizkaObec != other.BlizkaObec:
            return self.BlizkaObec < other.BlizkaObec
        if self.CastObce != other.CastObce:
            return self.CastObce < other.CastObce
        if self.BlizsiMisto != other.BlizsiMisto:
            return self.BlizsiMisto < other.BlizsiMisto
        return (self.Latitude, self.Longitude) < (other.Latitude, other.Longitude)

    @staticmethod
    def ParseName(fullName: str):
        parts = fullName.split("[")
        if len(parts) == 2:
            blizkaObec = parts[1].rstrip("]")
        else:
            blizkaObec = ""
        if not parts[0]:
            raise ValueError(f"Invalid stop name {fullName}")
        parts = parts[0].split(",")
        if len(parts) == 3:
            obec, castObce, blizsiMisto = parts
        elif len(parts) == 2:
            obec, castObce = parts
            blizsiMisto = ""
        else:
            obec = parts[0]
            castObce = ""
            blizsiMisto = ""
        return obec, castObce, blizsiMisto, blizkaObec

    def GetName(self, blizkaObecMode: str = ""):
        if not blizkaObecMode or blizkaObecMode == "default":
            return ",".join([self.Obec, self.CastObce, self.BlizsiMisto]).rstrip(",") + \
                f"[{self.BlizkaObec}]"
        if blizkaObecMode == "optional":
            return ",".join([self.Obec, self.CastObce, self.BlizsiMisto]).rstrip(",") + \
                (f"[{self.BlizkaObec}]" if self.BlizkaObec else "")
        if blizkaObecMode == "beginning":
            obec = self.Obec + f"[{self.BlizkaObec}]"
            return ",".join([obec, self.CastObce, self.BlizsiMisto]).rstrip(",")
        if blizkaObecMode == "beginning_optional":
            obec = self.Obec
            if self.BlizkaObec:
                obec = obec + f"[{self.BlizkaObec}]"
            return ",".join([obec, self.CastObce, self.BlizsiMisto]).rstrip(",")


def SanitizeStopName(obec, castObce, blizsiMisto, blizkaObec):
    obec = obec.strip()
    castObce = castObce.strip()
    blizsiMisto = blizsiMisto.strip()
    blizkaObec = blizkaObec.strip()
    obec = obec.lstrip(",")
    # Solve the issue if all parts are written at the beginning, also strips extra commas this way
    # Basically the only invalid characters are comma and square brackets
    defaultName = ",".join([obec, castObce, blizsiMisto])
    defaultName += ",,,"
    defaultName.replace("[", "")
    defaultName.replace("]", "")
    blizkaObec.replace("[", "")
    blizkaObec.replace("]", "")
    obec, castObce, blizsiMisto, _ = defaultName.split(",", 3)
    return obec, castObce, blizsiMisto, blizkaObec


def GetStopLocations(file: TextIO):
    stops = []
    reader = csv.reader(file, delimiter=',')
    for row in reader:
        if not row:
            continue
        try:
            loadedStop = StopWithLocation(*row)
        except ValueError:
            continue
        except TypeError as e:
            print(row)
            raise e
        stops.append(loadedStop)
    return sorted(stops)


def generateStopLocationFile(jsonFiles: List[pathlib.Path], outPath: pathlib.Path, mode: str = "append"):
    if mode not in ("drop", "append", "overwrite", "skip"):
        raise ValueError(f"Illegal mode {mode}, allowed only 'drop','append','overwrite','skip'")
    stops = []
    for file in jsonFiles:
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # data is a list of objects with atrributes "name","lat","lon"
        for stop in data:
            fullName = stop["name"]
            info = stop["info"]
            if not info:
                continue
            try:
                obec, castObce, blizsiMisto, blizkaObec = StopWithLocation.ParseName(fullName)
            except ValueError:
                continue
            stops.append(StopWithLocation(obec, castObce, blizsiMisto, blizkaObec, info["lat"], info["lon"]))

    if mode == "drop":
        res = stops
    else:
        try:
            with open(outPath, "r", encoding="utf-8", newline="") as f:
                oldStops = GetStopLocations(f)
        except FileNotFoundError:
            pass
        if mode in ("overwrite", "skip"):
            newStopsD = {s.GetName(): s for s in stops}
            oldStopsD = {s.GetName(): s for s in oldStops}
            for sn,sd in newStopsD.items():
                print(sn,sd)
            for sn, sd in oldStopsD.items():
                print(sn, sd)
            if mode == "skip":
                rt = newStopsD
                for s in oldStopsD:
                    rt[s] = oldStopsD[s]
            else:
                rt = oldStopsD
                for s in newStopsD:
                    rt[s] = newStopsD[s]
            res = list(rt.values())
            for r in res:
                print(r.GetName())
        else:
            res = stops + oldStops
    stops = sorted(res, key=lambda s: s.GetName())
    with open(outPath, 'w+', encoding='utf-8', newline="") as f:
        writer = csv.writer(f, delimiter=',', lineterminator='\n')
        for stop in stops:
            writer.writerow(
                [stop.Obec, stop.CastObce, stop.BlizsiMisto, stop.BlizkaObec, stop.Latitude, stop.Longitude]
            )


def main():
    fileTo = sys.argv[1]
    filesFrom = sys.argv[2:]
    generateStopLocationFile([pathlib.Path(f) for f in filesFrom], pathlib.Path(fileTo))


if __name__ == "__main__":
    main()
