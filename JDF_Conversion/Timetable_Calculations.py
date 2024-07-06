"""!
@file Timetable_Calculations.py
@namespace JDF_Conversion
@brief Functions extracting data from timetables
"""

import csv
import difflib
import gc
import itertools
import json
import os
import pathlib
from time import process_time
from typing import Set, TextIO

import scipy.sparse as scp

from JDF_Conversion import JDF_Serialization
from JDF_Conversion.JDF_Classes import *

JDF_ENCODING = "cp1250"
PROJECT_ENCODING = "utf-8"


class JdfBatch:
    """
    A class for storing the JDF data in Python arrays.
    The variable names use the Czech names from the JDF files.
    """

    def __init__(self):
        """!
        @brief Formal constructor with no extra functionality.
        @note The actual loading of the JDF files is done in the LoadJDF method.
        """
        self.Zastavky = []
        self.Dopravci = []
        self.PevneKody = []
        self.Linky = []
        self.LinkyExt = []
        self.ZasLinky = []
        self.Spoje = []
        self.ZasSpoje = []
        self.CasKody = []
        self.Navaznosti = []
        self.AltDopravci = []

        self.Loaded = False
        self.Success = True

    def _loadSingleJDF(
            self,
            filename,
            mandatory: bool,
            objType,
            collectionName,
            delimiter=",",
            lineterminator=";",
    ):
        """!@brief  Loads a single JDF file (CSV table) into a collection of objects.
        @param filename (str): The name of the file to load.
        @param mandatory: Whether the file must be contained in the JDF batch
        @param objType: The type of the objects to be created from the file
        @param collectionName: The name of the collection to store the objects in
        @param delimiter: The delimiter used in the CSV file
        @param lineterminator: The line terminator used in the CSV file
        """
        # The source JDF is in ansi, beware
        try:
            with open(filename, encoding=JDF_ENCODING, errors="replace") as f:
                data = list(list(item)
                            for item in
                            csv.reader(f, delimiter=delimiter, lineterminator=lineterminator))
                for row in data:
                    row[-1] = row[-1].rstrip(lineterminator)  # Hotfix for line terminator sometimes kept at the end
                    # Hotfix for jdf 1.10 -> 1.11:
                    if objType == JdfLinka and len(row) == 16:
                        row.insert(8, "");
                    elif objType == JdfZasSpoj and len(row) == 12:
                        row = [row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], "", row[8], row[9], "",
                               row[10], "", row[11]]
                    elif objType == JdfNavaznost and len(row) == 11:
                        row.insert(11, "")

                    jdfObject = objType(*row)
                    collectionName.append(jdfObject)
        except FileNotFoundError:
            if mandatory:
                print(f'Mandatory file "{filename}" not found in the JDF batch.')
                self.Success = False
                return
            else:
                pass
        except TypeError:  # initializer has wrong type of arguments
            print(f"File '{filename}' has the wrong amount of columns.")
            self.Success = False
            return

    def LoadJDF(self, folderName: str, delimiter: str = ",", lineterminator: str = ";", verbose: bool = False):
        """!
        Loads the CSV files from JDF folder into the JDF batch.
        @param folderName: The name of the folder containing the CSV files
        @param delimiter: The delimiter used in the CSV files
        @param lineterminator: The line terminator used in the CSV files
        @param verbose: Whether to print the loading progress
        """
        if verbose:
            print("Načítám soubory...")
        self._loadSingleJDF(
            folderName + "/Zastavky.txt",
            True,
            JdfZastavka,
            self.Zastavky,
            delimiter,
            lineterminator,
        )
        self._loadSingleJDF(
            folderName + "/Dopravci.txt",
            True,
            JdfDopravce,
            self.Dopravci,
            delimiter,
            lineterminator,
        )
        self._loadSingleJDF(
            folderName + "/Linky.txt",
            True,
            JdfLinka,
            self.Linky,
            delimiter,
            lineterminator,
        )
        self._loadSingleJDF(
            folderName + "/Zaslinky.txt",
            True,
            JdfZasLinka,
            self.ZasLinky,
            delimiter,
            lineterminator,
        )
        self._loadSingleJDF(
            folderName + "/LinExt.txt",
            False,
            JdfLinkaExt,
            self.LinkyExt,
            delimiter,
            lineterminator,
        )
        self._loadSingleJDF(
            folderName + "/Zasspoje.txt",
            True,
            JdfZasSpoj,
            self.ZasSpoje,
            delimiter,
            lineterminator,
        )
        self._loadSingleJDF(
            folderName + "/Spoje.txt",
            True,
            JdfSpoj,
            self.Spoje,
            delimiter,
            lineterminator,
        )
        self._loadSingleJDF(
            folderName + "/Pevnykod.txt",
            True,
            JdfPevnyKod,
            self.PevneKody,
            delimiter,
            lineterminator,
        )
        self._loadSingleJDF(
            folderName + "/Caskody.txt",
            True,
            JdfCasKod,
            self.CasKody,
            delimiter,
            lineterminator,
        )
        self._loadSingleJDF(
            folderName + "/Navaznosti.txt",
            False,
            JdfNavaznost,
            self.Navaznosti,
            delimiter,
            lineterminator,
        )
        self._loadSingleJDF(
            folderName + "/Altdop.txt",
            False,
            JdfAlternDopravce,
            self.AltDopravci,
            delimiter,
            lineterminator,
        )
        # self._loadSingleJDF(folderName+"/Spojskup.txt",False,JdfSpojSkup,self.SkupinySpoju,delimiter,lineterminator)
        # self._loadSingleJDF(folderName+"/Mistenky.txt",False,JdfMistenka,self.JdfMistenky,delimiter,lineterminator)

        self.Loaded = True


class JdfProcessor:
    """
    A class for processing the JDF data.
    """

    def __init__(self, jdfFolder: str):
        """!
        Constructor for the JDF processor. Immediately loads the JDF data.
        @param jdfFolder: The folder containing the JDf data
        """
        batch = JdfBatch()
        batch.LoadJDF(jdfFolder)
        if not batch.Loaded:
            raise Exception("Error while loading JDF")
        if not batch.Success:
            raise Exception("Some JDF files were not found")
        self.JDF = batch

        self.JdfLinky = None
        self.JdfSpoje = None
        self.JdfZastavky = None
        self.JdfCasyZastavek = None
        self.JdfZastavkyLinek = None
        self.JdfDopravci = None
        self.JdfAltDopravci = None
        self.JdfLinkyExt = None
        self.JdfNavaznosti = None
        self.JdfCasoveKody = None

        self.Vsechno = None
        self.JdfPevneKody = None

        self.SeznamyZasLinek = None
        self.SeznamyLinZastavek = None
        self.SeznamyCasu = None
        self.SeznamyCasovychKodu = None

        self.SeznamySpoju = None
        self.SlovnikyAltDop = None
        self.SortedTrips = None

    fields = [
        "JdfAltDopravci",
        "JdfCasoveKody",
        "JdfDopravci",
        "JdfLinky",
        "JdfLinkyExt",
        "JdfNavaznosti",
        "JdfPevneKody",
        "JdfSpoje",
        "JdfZastavkyLinek",
        "JdfCasyZastavek",
        "JdfZastavky"
    ]

    def parseGeneric(self, jdfList: str, dictName: dict, typeName: str = ""):
        """!
        Parses a JDF file into a dictionary.
        @param jdfName: List of JDF objects
        @param dictName: The name of the dictionary (member object) to be created
        @param typeName: The name of the type, corresponding to the JDF file
        """
        if not self.JDF.Loaded:
            raise AttributeError("JDF was not yet loaded successfully")

        for x in jdfList:
            k = x.GetID()
            if k not in dictName:
                dictName[k] = x
            else:
                if x == dictName[k]:
                    warnings.warn(f"Duplicate record of {typeName} ({k})")
                else:
                    continue

    def copyGeneric(self, sourceDict, targetDict, skip=False):
        """!
        Copies the contents of a dictionary into another dictionary.
        @param sourceDict: The source dictionary
        @param targetDict: The output dictionary
        @param skip: Skip the copying if the output already contains the key
        """
        for i, x in sourceDict.items():
            if skip:
                if targetDict.get(i):
                    continue
            targetDict[i] = x
        return

    def MakeDicts(self):
        """!
        brief Creates the dictionaries from the JDF batch (which is loaded in the constructor).
        brief The key is created by the GetID() method of the JDF object.
        """
        self.JdfLinky = {}
        self.JdfSpoje = {}
        self.JdfZastavky = {}
        self.JdfCasyZastavek = {}
        self.JdfZastavkyLinek = {}
        self.JdfDopravci = {}
        self.JdfAltDopravci = {}
        self.JdfLinkyExt = {}
        self.JdfNavaznosti = {}
        self.JdfCasoveKody = {}
        # self.JdfAltLinky = {}

        self.Vsechno = [
            self.JdfLinky,
            self.JdfSpoje,
            self.JdfZastavky,
            self.JdfCasyZastavek,
            self.JdfZastavkyLinek,
            self.JdfDopravci,
            self.JdfAltDopravci,  # self.JdfAltLinky,
            self.JdfLinkyExt,
            self.JdfNavaznosti,
            self.JdfCasoveKody,
        ]
        # self.JdfCasoveKody = {}

        self.parseGeneric(self.JDF.Linky, self.JdfLinky)
        self.parseGeneric(self.JDF.Spoje, self.JdfSpoje)
        self.parseGeneric(self.JDF.Zastavky, self.JdfZastavky)
        self.parseGeneric(self.JDF.ZasSpoje, self.JdfCasyZastavek)
        self.parseGeneric(self.JDF.ZasLinky, self.JdfZastavkyLinek)
        self.parseGeneric(self.JDF.CasKody, self.JdfCasoveKody)
        self.parseGeneric(self.JDF.Dopravci, self.JdfDopravci)
        self.parseGeneric(self.JDF.AltDopravci, self.JdfAltDopravci)
        self.parseGeneric(self.JDF.LinkyExt, self.JdfLinkyExt)
        self.parseGeneric(self.JDF.Navaznosti, self.JdfNavaznosti)
        # self.parseGeneric(self.JDF.AltLinky,self.JdfAltLinky)
        # self.parseGeneric(self.JDF.Mistenky,self.JdfMistenky)

        self.JdfPevneKody = {}
        for c in self.JDF.PevneKody:
            self.JdfPevneKody[c.CodeNumber] = JdfPevnyKod(c.CodeNumber, c.CodeSign)
        for sezn in self.Vsechno:
            for v in sezn.values():
                if hasattr(v, "BindCodes"):
                    v.BindCodes(self.JdfPevneKody)

    def ParseAll(self, verbose=False):
        """!
        Create references of the JDF objects between each other, calling the Bind methods.
        @param verbose: Print the progress
        """

        # self.parseGeneric(self.JDF.CasKody,self.JdfCasoveKody)

        if verbose:
            print("Grouping objects")

        self.SeznamyZasLinek = {}
        self.SeznamyLinZastavek = {}
        zal: JdfZasLinka
        for zal in self.JdfZastavkyLinek.values():
            zal.Bind(self.JdfZastavky)
            zal.AddToLinky(self.SeznamyZasLinek)
            zal.AddToZastavky(self.SeznamyLinZastavek)
        zsl: JdfZasSpoj
        self.SeznamyCasu = {}
        for zsl in self.JdfCasyZastavek.values():
            zsl.Bind(self.JdfZastavkyLinek)
            zsl.AddTo(self.SeznamyCasu)

        ck: JdfCasKod
        self.SeznamyCasovychKodu = {}
        for ck in self.JdfCasoveKody.values():
            ck.AddTo(self.SeznamyCasovychKodu)

        ald: JdfAlternDopravce
        self.SlovnikyAltDop = {}
        for ald in self.JdfAltDopravci.values():
            ald.Bind(self.JdfDopravci)
            ald.AddTo(self.SlovnikyAltDop)

        sp: JdfSpoj
        self.SeznamySpoju = {}
        for sp in self.JdfSpoje.values():
            sp.Bind(
                self.JdfLinky,
                self.SeznamyCasu,
                self.SeznamyCasovychKodu,
                self.SlovnikyAltDop,
                None,
                self.JdfNavaznosti,
                None,
            )
            sp.AddTo(self.SeznamySpoju)

        lin: JdfLinka
        for lin in self.JdfLinky.values():
            lin.Bind(
                self.SeznamyZasLinek,
                self.JdfLinkyExt,
                self.JdfDopravci,
                self.SeznamySpoju,
                self.SlovnikyAltDop,
            )
            lin.ConvertTimes()

        return

    def UnifyCodes(self):
        """!
        @brief Unifies the PevneKody in the whole batch (especially after merging) by iterating over all objects using
        them creating a dictionary of the codes and their new IDs
        """
        self.JdfPevneKody = {}
        codeToNumber = {}
        usedNumbers = set()
        uniqueNumber = 1
        for sezn in self.Vsechno:
            for v in sezn.values():
                if hasattr(v, "Kody"):
                    for i, e in enumerate(v.Kody):
                        # If we have number for given code change it to the new one
                        if e.CodeSign in codeToNumber:
                            e.CodeNumber = codeToNumber[e.CodeSign]
                        # Otherwise we add it to the dictionary but beware of collisions
                        else:
                            if e.CodeNumber in usedNumbers:  # We assign unqiue lowest number
                                while str(uniqueNumber) in usedNumbers:
                                    uniqueNumber += 1
                                e.CodeNumber = str(uniqueNumber)
                            codeToNumber[e.CodeSign] = e.CodeNumber
                            usedNumbers.add(e.CodeNumber)
                else:
                    break
        self.JdfPevneKody = {v: JdfPevnyKod(v, k) for k, v in codeToNumber.items()}
        assert (len(self.JdfPevneKody) == len(codeToNumber))

    def FormatTimesTrips(self, showProgress=False):
        """!
        Creates departure times by converting them from minutes.
        Sorts the stops within one trip.
        @param showProgress: Whether to print the progress
        """
        if showProgress:
            print("Formatting trip stops")

        jst: JdfZasSpoj
        for jst in progressBar(self.JdfCasyZastavek.values()) if showProgress else self.JdfCasyZastavek.values():
            jst.FormatTime()

        if showProgress:
            print("Formatting timecode restrictions")

        sp: JdfSpoj
        for _, sp in progressBar(self.JdfSpoje.items()) if showProgress else self.JdfSpoje.items():
            sp.SortStops()
            sp.CompressTimeCodes()
        self.SortedTrips = []

        if showProgress:
            print("Adding stop departures")
        za: JdfZastavka
        for za in progressBar(self.JdfZastavky.values()) if showProgress else self.JdfZastavky.values():
            za.AddDepartures(
                self.JdfLinky, self.SeznamyLinZastavek, self.JdfCasyZastavek
            )

    def CheckTripsInDay(self, verbose: bool, day: datetime.date, fullTrip=False, output: TextIO = None):
        """!
        Prints all trips for a given day (in JSON format if into a file).
        @param verbose: Whether to print the progress
        @param day: The day to check
        @param fullTrip: Whether to print the intermediate stops
        @param output: The file to write the results to
        """

        if verbose:
            print("Date:", day)
            print("--------------\n")
        # time.sleep(0.5)
        if len(self.JdfSpoje) != len(self.SortedTrips):
            # check if we did not add trips
            self.SortedTrips = sorted(
                self.JdfSpoje.values(), key=lambda spoj: spoj.First.Odjezd
            )

        result = []
        sp: JdfSpoj
        for sp in self.SortedTrips:
            linka = sp.Line
            jede = IsTripOperated(day, sp, self.JdfLinky)
            if not jede:
                continue
            cisloSpoje = sp.CisloSpoje
            vychoziCZ = sp.First
            konecnaCZ = sp.Last
            vychoziCas = SplitToHHMM(vychoziCZ.Odjezd)
            konecnyCas = SplitToHHMM(konecnaCZ.Prijezd)
            zastVychozi = vychoziCZ.Zastavka.GetName()
            zastKonecna = konecnaCZ.Zastavka.GetName()
            if verbose:
                ln = f"Line: {linka.CisloLinky} \n Trip: {cisloSpoje} \n" \
                     + f"From: {zastVychozi} at {vychoziCas} \n To: {zastKonecna} at {konecnyCas} \n"
                if fullTrip:
                    ln += "Stops:\n"
                    stops = sp.SerializeStops()
                    for name, time in stops:
                        ln += f"{name} {time} \n"
                print(ln)

            lnd = {
                "Line number": linka.CisloLinky,
                "Trip number": cisloSpoje,
                "Initial stop": zastVychozi,
                "Departure time": vychoziCas,
                "Terminal stop": zastKonecna,
                "Arrival time": konecnyCas,
            }
            if fullTrip:
                lnd["Stops"] = [{name: time} for name, time in sp.SerializeStops()]
            result.append(lnd)
        if output:
            try:
                json.dump(result, output, indent=4, ensure_ascii=False)
            except UnicodeEncodeError as ude:
                print(ude)

    def FindStop(self, stop: str) -> Tuple[int, JdfZastavka]:
        """!
        Finds a stop by its name or ID.
        @param stop: The name or ID of the stop
        @return: The stop's ID and object
        """
        try:
            stop = int(stop)
            stopX = self.JdfZastavky[stop]
            return stop, stopX
        except ValueError:
            pass  # Find by string
        except KeyError as exc:
            raise KeyError("Stop code number not found", stop) from exc
        za: JdfZastavka
        for zid, za in self.JdfZastavky.items():
            if za.GetName() == stop:
                return zid, za
        return None, None

    def CalculateShortestTime(self, stop1: Union[JdfZastavka, str], stop2: Union[JdfZastavka, str], mirror=True) -> int:
        """!
        Calculates the shortest time between two stops, using only one trip.
        @param stop1: The first stop
        @param stop2: The second stop
        @param mirror: Check also the trips in the opposite direction (return the minimum)
        @note: The maximum time is 2**15 minutes (so it can be stored in a 16-bit integer)
        @return: The shortest time between these stops in minutes
        """
        stopA: JdfZastavka
        stopB: JdfZastavka
        if isinstance(stop1, JdfZastavka):
            idA, stopA = stop1.GetID(), stop1
        else:
            idA, stopA = self.FindStop(stop1)
        if isinstance(stop2, JdfZastavka):
            idB, stopB = stop2.GetID(), stop2
        else:
            idB, stopB = self.FindStop(stop2)

        # No turnaround time assumed
        if idA == idB:
            return 0

        maxValue = 2 ** 15
        currentMin = maxValue
        for idSp, odjA in stopA.Odjezdy.items():
            odjB = stopB.Prijezdy.get(
                idSp
            )  # Prijezd is also defined if only Odjezd is defined (except for starting stop)
            if not odjB:
                continue
            combos = itertools.product(odjA, odjB)
            for a, b in combos:
                CasB = b.Prijezd if b.Prijezd >= 0 else b.Odjezd
                # Unnecessary check, since Odjezdy only takes real stoppings, not ignored ones
                if a.Odjezd >= 0 and CasB >= 0:
                    currentMin = min(currentMin, abs(CasB - a.Odjezd))
        if mirror:
            minMirror = self.CalculateShortestTime(idB, idA, False)
            currentMin = min(minMirror, currentMin)
        return currentMin

    def GetTerminalStops(self, sortBy: str = "") -> List[JdfZastavka]:
        """!
        Gets all terminal stops (stops where a trip starts or ends)
        @param sortBy: Sort the stops by the given attribute (e.g. "Name"). Default is empty string (no sorting)
        """
        if sortBy not in [None, "", "id", "name"]:
            raise ValueError("Wrong sorting parameter")
        stops = set()
        for sp in self.JdfSpoje.values():
            stops.add(sp.First.Zastavka)
            stops.add(sp.Last.Zastavka)
        if not sortBy:
            return list(stops)
        elif sortBy == "id":
            return sorted(stops, key=lambda st: st.GetID())
        elif sortBy == "name":
            return sorted(stops, key=lambda st: st.GetName())
        else:
            raise ValueError("Wrong sorting parameter")

    def GetBranchingStops(self, terminals: Optional[List[JdfZastavka]], branchCount: int = 2, sortby: str = ""):
        """!
        Finds all stops with more than 2 neighbors and add them to the list of terminals
        (stops with 2 neighbors will never improve pathfinding algorithm, as they can be condensed)
        @param terminals: List of terminal stops (stops where a trip starts or ends)
        @param branchCount: Minimum number of neighbors to be considered a branching stop
        (default is 2, see description)
        @param sortby: Sort the stops by the given attribute (e.g. "Name"). Default is empty string (no sorting)
        @return: List of terminal stops with branching stops added
        """
        if sortby not in [None, "", "id", "name"]:
            raise ValueError("Wrong sorting parameter")
        stops = set(terminals if terminals else self.GetTerminalStops(sortby))
        za: JdfZastavka
        for za in self.JdfZastavky.values():
            neighbor = set()
            for prid, prij in za.Prijezdy.items():
                if len(neighbor) > branchCount:
                    break
                sp = self.JdfSpoje[prid]
                for pr in prij:
                    tc = pr.TC
                    for i in range(tc + 1, sp.Last.TC + 1):
                        zsp = sp.StopEvents.get(i)
                        if not zsp:
                            continue
                        else:
                            if zsp.Odjezd >= 0 or zsp.Prijezd >= 0:
                                neighbor.add(zsp.Zastavka)
                                break
                    for i in reversed(range(sp.First.TC, tc)):
                        zsp = sp.StopEvents.get(i)
                        if not zsp:
                            continue
                        else:
                            if zsp.Odjezd >= 0 or zsp.Prijezd >= 0:
                                neighbor.add(zsp.Zastavka)
                                break
            if len(neighbor) > branchCount:
                stops.add(za)

        if not sortby:
            return list(stops)
        elif sortby == "id":
            return sorted(stops, key=lambda st: st.GetID())
        elif sortby == "name":
            return sorted(stops, key=lambda st: st.GetName())
        else:
            raise ValueError("Wrong sorting parameter")

    # Calculates time matrix, as according to timetables; does not deal with time zones
    def CalculateTimeMatrix(
            self, stops: List[JdfZastavka], vehicleType: Optional[Prostredek], verbose: bool = False
    ) -> np.ndarray:
        """!
        Calculates the time matrix between all stops in the given list, accordingly to the timetable
        Ignores international connections (because of time zones),
        the trips are calculated as if they were split by the border (CLO) stops
        @param stops: List of stops to calculate the time matrix for
        @param vehicleType: Type of vehicle to use (e.g. "Autobus"). If None, all vehicles are used
        @param verbose: Print progress
        @return: Time matrix (2D, 16-bit integers), in minutes
        """
        matrix = np.ndarray(shape=(len(stops), len(stops)), dtype="int16")
        matrix.fill(np.iinfo(np.int16).max)
        idex = {stops[k].GetID(): k for k in range(len(stops))}
        rnge = progressBar(range(len(stops))) if verbose else range(len(stops))
        for i in rnge:
            matrix[i, i] = 0
            za: JdfZastavka
            za = stops[i]
            for idSp, zspl in za.Odjezdy.items():
                sp: JdfSpoj
                sp = self.JdfSpoje[idSp]

                if vehicleType:
                    ln: JdfLinka
                    ln = self.JdfLinky[(sp.CisloLinky, sp.RozliseniLinky)]
                    if ln.Prostredek != vehicleType:
                        continue
                if not (sp.HasClo()):
                    firstTC = sp.First.TC
                    lastTC = sp.Last.TC
                    assert (firstTC * sp.Smer < lastTC * sp.Smer)

                    for zsp in zspl:
                        assert (firstTC * sp.Smer <= zsp.TC * sp.Smer)
                        smer = sp.Smer
                        tc_range = (
                            range(zsp.TC + smer, lastTC + smer, smer)
                        )

                        cas1 = zsp.Odjezd
                        for k in tc_range:
                            if k == zsp.TC:
                                continue
                            zsp2 = self.JdfCasyZastavek.get(
                                (sp.CisloLinky, sp.RozliseniLinky, sp.CisloSpoje, k)
                            )
                            if zsp2:
                                za2 = self.JdfZastavkyLinek[
                                    (sp.CisloLinky, sp.RozliseniLinky, k)
                                ].Zastavka
                                cas2 = (
                                    zsp2.Prijezd if zsp2.Prijezd >= 0 else zsp2.Odjezd
                                )
                                if cas2 < 0:  # Passing a stop
                                    continue
                                casX = abs(cas1 - cas2)
                                j = idex.get(za2.GetID())
                                if j == None:
                                    continue
                                else:
                                    matrix[i, j] = min(matrix[i, j], casX)

                # Prozkoumej pouze ty zastávky, které nejsou odděleny zastávkou s "CLO" (tzn. omez minTC a maxTC)
                else:  # if sp.HasClo()
                    minTC = sp.First.TC
                    maxTC = sp.Last.TC

                    for zsp in zspl:
                        tc_range = (
                            range(zsp.TC + 1, maxTC + 1)
                            if sp.Smer == 1
                            else reversed(range(minTC, zsp.TC))
                        )

                        cas1 = zsp.Odjezd
                        for k in tc_range:
                            if k == zsp.TC:
                                continue
                            zsp2 = self.JdfCasyZastavek.get(
                                (sp.CisloLinky, sp.RozliseniLinky, sp.CisloSpoje, k)
                            )
                            if zsp2:
                                za2 = self.JdfZastavkyLinek[
                                    (sp.CisloLinky, sp.RozliseniLinky, k)
                                ].Zastavka
                                if za2.HasClo():
                                    break  # Break current range (split by CLO)
                                cas2 = (
                                    zsp2.Prijezd if zsp2.Prijezd >= 0 else zsp2.Odjezd
                                )
                                if cas2 < 0:
                                    continue
                                casX = abs(cas1 - cas2)
                                j = idex.get(za2.GetID())
                                if j == None:
                                    continue
                                else:
                                    matrix[i, j] = min(matrix[i, j], casX)
        return matrix

    def ChangeKeyLine(self, ln: JdfLinka, dictio: Dict[Tuple[int, int], JdfLinka], newKey: Tuple[int, int]):
        """!
        Changes the key of a line in a dictionary
        @param ln: Line to change the key of
        @param dictio: Dictionary to change the key in
        @param newKey: New key (tuple of CisloLinky and RozliseniLinky)
        """
        oldKey = ln.GetID()
        for k, x in list(dictio.items()):
            if (x.CisloLinky, x.RozliseniLinky) == oldKey:
                x.CisloLinky, x.RozliseniLinky = newKey
                dictio[x.GetID()] = x
                del dictio[k]

    def ChangeKey(
            self, objekt: Union[JdfLinka, JdfZastavka], newKey: Union[Tuple[int, int], int, str]
    ):
        """!
        Changes the key of an object in all dictionaries
        @param objekt: Object to change the key of
        @param newKey: New key
        @note Must be called on the original JDF batch before bindings
        """
        if isinstance(objekt, JdfZastavka):
            za: JdfZastavka
            za = objekt
            oldKey = za.GetID()

            for _, zl in list(self.JdfZastavkyLinek.items()):
                if zl.CisloZastavky == oldKey:
                    zl.CisloZastavky = newKey
            za.CisloZastavky = newKey
            self.JdfZastavky[newKey] = za
            del self.JdfZastavky[oldKey]
            return
        elif isinstance(objekt, JdfLinka):
            ln: JdfLinka
            ln = objekt
            oldKey = ln.GetID()

            self.ChangeKeyLine(ln, self.JdfSpoje, newKey)
            self.ChangeKeyLine(ln, self.JdfCasyZastavek, newKey)
            self.ChangeKeyLine(ln, self.JdfZastavkyLinek, newKey)
            self.ChangeKeyLine(ln, self.JdfAltDopravci, newKey)
            self.ChangeKeyLine(ln, self.JdfLinkyExt, newKey)
            # self.ChangeKeyLine(ln,self.JdfUdaje,newKey)
            self.ChangeKeyLine(ln, self.JdfCasoveKody, newKey)
            self.ChangeKeyLine(ln, self.JdfNavaznosti, newKey)
            # self.ChangeKeyLine(ln,self.JdfAltLinky,newKey)
            # self.ChangeKeyLine(ln,self.JdfMistenky,newKey)

            ln.CisloLinky, ln.RozliseniLinky = newKey
            self.JdfLinky[newKey] = ln
            del self.JdfLinky[oldKey]
        else:
            raise TypeError("Neplatny typ objektu")

    def testDateByUserInput(self, verbose: bool, endToken: str, fullTrip: bool = False, outFolder: str = None,
                            datum: datetime.date = None):
        """!
        Prints all trips for a date given by user input
        @param verbose: Verbose output
        @param endToken: Token to end the input
        @param fullTrip: Print the trip, including intermediate stops
        @param outFolder: Output folder for the trips (name of file is the date+.json)
        @param datum: Date to test (if None, user input is used)
        """
        """
        if datum == None:
            datum = input("Zadej datum ve formatu DD.MM.RRRR: ")
        if datum == endToken:
            return
        try:
            datum = datetime.strptime(datum, "%d.%m.%Y")
        except ValueError:
            print("Neplatny format data")
            return
        """
        if not datum:
            datum = input("Zadej datum ve formátu DD.MM.RRRR: ")
        else:
            print("Datum:", datum)
        if datum == endToken:
            return False
        try:
            den = datetime.datetime.strptime(datum, "%d.%m.%Y").date()
        except ValueError:
            print("Nespravny format data")
            return True
        if outFolder:
            target = os.path.join(outFolder, str(den) + ".json")
            os.makedirs(outFolder, exist_ok=True)
            with open(target, "w", encoding=PROJECT_ENCODING) as f:
                self.CheckTripsInDay(verbose, den, fullTrip, f)
        else:
            self.CheckTripsInDay(verbose, den, fullTrip)
        return True

    def GetAllStopMatrixByTT(self):
        """!
        Returns a matrix of all stops, with the time between them
        @return Matrix of all stops, with the shortest theoretical time by bus (queried from the timetables)
        @note See more on GetDeadheadMatrixByTT()
        """
        vsechnyZastavky = sorted(
            self.JdfZastavky.values(), key=lambda za: za.GetName()
        )
        print(
            "Calculating times between all stops",
            f"(total:{len(vsechnyZastavky)})",
        )
        timeC = process_time()
        matica = self.CalculateTimeMatrix(vsechnyZastavky, Prostredek.Autobus, True)
        print(process_time() - timeC)
        timeC = process_time()

        print("Optimizing stop times")
        matica = FindSelectedDistancesInAdjMatrix(matica, range(len(vsechnyZastavky)))

        print(process_time() - timeC)
        timeC = process_time()

        return vsechnyZastavky, matica

    def GetDeadheadMatrixByTT(self, terminalStops: List[JdfZastavka]) -> Tuple[List[JdfZastavka], np.ndarray]:
        """!
        Calculates a matrix of terminal stops with the minimum deadhead time between them
        @param terminalStops: Stops for calculation
        @param limit: Maximum amount of stops, otherwise some non-terminal stops are eliminated
        @return: List of terminal stops and the matrix of deadhead times (time in minutes, 16-bit integer)
        """
        timeC = process_time()
        selectedStops = terminalStops

        print(
            "Calculating times between terminal stops "
            f"({len(selectedStops)})",
        )

        mtrx = self.CalculateTimeMatrix(selectedStops, Prostredek.Autobus, True)

        print(f"Direct connection time matrix calculated in {int((process_time() - timeC) * 1000)} ms")
        timeC = process_time()
        print(f"Optimizing times between stops (total terminals: {len(selectedStops)})")
        mtrx = SymmetrizeDM(mtrx)

        idxy = [selectedStops.index(k) for k in terminalStops]
        mtrx = FindSelectedDistancesInAdjMatrix(mtrx, idxy)

        # Select only the terminal stops
        reducedMatrix = np.array(mtrx[np.ix_(idxy, idxy)])

        print(f"Deadhead time matrix optimized in {int((process_time() - timeC) * 1000)} ms")
        return terminalStops, reducedMatrix

    def SerializeOut(self, outFolder: pathlib.Path):
        """!
        @brief Serializes the data back into JDF (csv files within one folder)
        @param outFolder: Folder to save the data into
        """
        # Create the folder
        os.makedirs(outFolder, exist_ok=True)
        # Start serialization
        ffs = [
            ("Dopravci", self.JdfDopravci, None),
            ("Zastavky", self.JdfZastavky, lambda z: z.GetName()),
            ("Spoje", self.JdfSpoje, None),
            ("Zasspoje", self.JdfCasyZastavek, None),
            ("Linky", self.JdfLinky, None),
            ("Zaslinky", self.JdfZastavkyLinek, None),
            ("Pevnykod", self.JdfPevneKody, None),
            ("Caskody", self.JdfCasoveKody, None),
        ]
        for file, dic, sortfn in ffs:
            with open(os.path.join(outFolder, file + ".txt"), "w+", encoding=JDF_ENCODING) as f:
                JDF_Serialization.SerializeJdfCollection((v for k, v in sorted(dic.items(),
                                                                               key=lambda x: sortfn(
                                                                                   x[1]) if sortfn else (x[0]))), f)

    def FindStopByName(self, stopName: str, accuracy: str) -> \
            Optional[JdfZastavka]:
        """!
        @brief Finds a stop with the given name
        @param stopName: Name of the stop
        @param accuracy: "approximate","name","exact"
        @param allStopNames: All stop names
        @return: The stop
        """
        if accuracy == "approximate":  # Find closest stop with this name
            allStopNames = [z.GetName() for z in self.JdfZastavky.values()]
            candidates = difflib.get_close_matches(stopName, allStopNames, n=1, cutoff=0.5)
            if len(candidates) == 0:
                warnings.warn("No stop found")
                return None
            realStopName = candidates[0]
        elif accuracy == "exact":
            allStopNames = [z.GetName() for z in self.JdfZastavky.values()]
            isin = stopName in allStopNames
            if not isin:
                warnings.warn("No stop found")
                return None
            realStopName = stopName
        elif accuracy == "name":  # Ignore region and double commas
            stopName = stopName.split("[")[0].replace(",,", ",")
            allStopNames = [z.GetName() for z in self.JdfZastavky.values()]
            allStopNames = [x.split("[")[0].replace(",,", ",") for x in allStopNames]
            candidates = difflib.get_close_matches(stopName, allStopNames, n=3, cutoff=0.95)
            if len(candidates) == 0:
                warnings.warn("No stop found")
                return None
            realStopName = candidates[0]
        else:
            raise ValueError("Unknown accuracy")
        stopObjs = [z for z in self.JdfZastavky.values() if z.GetName() == realStopName]
        if not stopObjs:
            warnings.warn("No stop found")
            return None
        return stopObjs[0]

    def FindStopsByName(self, stopNames: List[str], accuracy: str) -> \
            Tuple[List[JdfZastavka], List[str]]:
        """!
        @brief Finds stops with the given names
        @param stopNames: Names of the stops
        @param accuracy: "approximate","name","exact"
        @return Two lists: First of stops as objects, second as list of not found stop names
        """
        allStopNames = [z.GetName() for z in self.JdfZastavky.values()]
        realStopNames = []
        success = []
        fail = []
        if accuracy == "approximate":
            # Find the closest stop with this name
            for stopName in stopNames:
                candidates = difflib.get_close_matches(stopName, allStopNames, n=1, cutoff=0.5)
                if len(candidates) == 0:
                    fail.append(stopName)
                else:
                    realStopName = candidates[0]
                    for z in self.JdfZastavky.values():
                        if z.GetName() == realStopName:
                            success.append(z)
                            break
        elif accuracy == "exact":
            for stopName in stopNames:
                if stopName in allStopNames:
                    realStopNames.append(stopName)
                else:
                    fail.append(stopName)
        elif accuracy == "name":
            # Ignore region and double commas
            changedStopNames = [x.split("[")[0].replace(",,", ",") for x in allStopNames]
            for stopName in stopNames:
                stopName = stopName.split("[")[0].replace(",,", ",")
                candidates = difflib.get_close_matches(stopName, changedStopNames, n=1, cutoff=0.95)
                if not candidates:
                    fail.append(stopName)
                else:
                    realStopNames.append(candidates[0])
        else:
            raise ValueError("Unknown accuracy")
        for realStopName in realStopNames:
            found = False
            for z in self.JdfZastavky.values():
                if z.GetName() == realStopName:
                    found = True
                    success.append(z)
                    break
            if not found:
                fail.append(realStopName)
        return success, fail

    def GetDeparturesInInterval(self, stop: JdfZastavka,
                                timeFrom: datetime.datetime, timeTo: datetime.datetime):

        # Find the departures
        departures = []
        odjezd: JdfZasSpoj
        spoj: JdfSpoj
        for idSpoje, odjezdy in stop.Odjezdy.items():
            spoj = self.JdfSpoje[idSpoje]
            currentTime = timeFrom
            while currentTime <= timeTo:
                for odjezd in odjezdy:  # porovnat čas odjezdu
                    # Do not care for departures at the last stop
                    if spoj.Last == odjezd:
                        continue
                    departureTime = odjezd.Odjezd
                    try:
                        hrs, mins = divmod(int(departureTime), 60)
                    except ValueError:
                        continue
                    departureDateTime = currentTime.replace(hour=hrs, minute=mins)
                    if not (timeFrom <= departureDateTime <= timeTo):
                        continue

                    # check the actual date of trip, assume under 24 hours and no timezone change
                    if spoj.First.Odjezd > departureTime:
                        tripDate = currentTime.date() - datetime.timedelta(days=1)
                    else:
                        tripDate = currentTime.date()
                    operates = IsTripOperated(tripDate, spoj, self.JdfLinky)
                    if operates:
                        departures.append((spoj, odjezd, departureDateTime))

                currentTime += datetime.timedelta(days=1)

        departures.sort(key=lambda d: (d[2], d[1].Odjezd))
        return departures

    def GetArrivalsInInterval(self, stop: JdfZastavka,
                              timeFrom: datetime.datetime, timeTo: datetime.datetime):

        # Find the departures
        arrivals = []
        prijezd: JdfZasSpoj
        spoj: JdfSpoj
        for idSpoje, prijezdy in stop.Prijezdy.items():
            spoj = self.JdfSpoje[idSpoje]
            currentTime = timeFrom
            while currentTime <= timeTo:
                for prijezd in prijezdy:  # compare time
                    # Ignore first stop of the trip
                    if spoj.First == prijezd:
                        continue
                    arrivalTime = prijezd.Prijezd if prijezd.Prijezd >= 0 else prijezd.Odjezd
                    try:
                        if arrivalTime < 0:
                            continue
                        hrs, mins = divmod(int(arrivalTime), 60)
                    except ValueError:
                        continue
                    arrivalDateTime = currentTime.replace(hour=hrs, minute=mins)
                    if not (timeFrom <= arrivalDateTime <= timeTo):
                        continue

                    # check the actual date of trip, assume under 24 hours and no timezone change
                    elif spoj.First.Odjezd > arrivalTime:
                        tripDate = currentTime.date() - datetime.timedelta(days=1)
                    else:
                        tripDate = currentTime.date()
                    operates = IsTripOperated(tripDate, spoj, self.JdfLinky)
                    if operates:
                        arrivals.append((spoj, prijezd, arrivalDateTime))

                currentTime += datetime.timedelta(days=1)

        arrivals.sort(key=lambda d: (d[2], d[1].Prijezd if d[1].Prijezd >= 0 else d[1].Odjezd))
        return arrivals

    @staticmethod
    def WriteDepartures(departures: List[Tuple[JdfSpoj, JdfZasSpoj, datetime.datetime]],
                        stream: TextIO):
        """!
        @brief Write departures to a stream
        """
        pds = [JDF_Serialization.PackDeparture(d[1], d[0], d[2]) for d in departures]
        json.dump(pds, stream, ensure_ascii=False, indent=2, sort_keys=False)

    @staticmethod
    def WriteArrivals(arrivals: List[Tuple[JdfSpoj, JdfZasSpoj, datetime.datetime]],
                      stream: TextIO):
        """!
        @brief Write arrivals to a stream
        """
        pds = [JDF_Serialization.PackArrival(a[1], a[0], a[2]) for a in arrivals]
        json.dump(pds, stream, ensure_ascii=False, indent=2, sort_keys=False)

    def WriteStopMatrix(self, stream: TextIO, stops: Iterable[JdfZastavka], matrix: np.ndarray):
        """!
        @brief Write stop matrix to a stream as csv
        """
        stream.write("Stops")
        for za in stops:
            stream.write("\t" + za.GetName())
        stream.write("\n")
        for i, s in enumerate(stops):
            stream.write(s.GetName())
            for dist in matrix[i]:
                stream.write("\t" + str(dist))
            stream.write("\n")


class JdfMerger:
    """!
    Class for merging multiple JDF batches (represented by JdfProcessor objects)
    In general, stops and companies are merged while lines (trips) are given multiple versions.
    Can be also used to parse a single JDF batch.
    """

    def __init__(self, blacklist: Optional[Set[str]] = None):
        """!
        Constructor for JdfMerger
        @param blacklist: Set of folders to ignore
        """
        self.StopNames = {}
        self.MaxZastID = 0
        self.Blacklist = blacklist if blacklist else set()
        self.OriginalProcessor = None
        return

    fields = [
        "JdfAltDopravci",
        "JdfCasoveKody",
        "JdfDopravci",
        "JdfLinky",
        "JdfLinkyExt",
        "JdfNavaznosti",
        # "JdfPevneKody",
        "JdfSpoje",
        "JdfZastavkyLinek",
        "JdfCasyZastavek",
        "JdfZastavky"
    ]

    def AddNew(self, folder: str, checkBL: bool = False):
        """!
        Tries to add a new JDF batch
        @param folder: Folder with the individual CSV files
        @param checkBL: Whether to check the blacklist (ignore the folder if it is in the blacklist)
        @note The file is always added to the blacklist if invalid
        """
        if checkBL and folder in self.Blacklist:
            return
        try:
            newJdf = JdfProcessor(folder)
            newJdf.MakeDicts()
        except Exception as e:
            print(e)
            self.Blacklist.add(folder)
            return
        if not self.OriginalProcessor:
            self.OriginalProcessor = newJdf
            self.StopNames = {
                zast.GetName(): zast.GetID() for zast in newJdf.JdfZastavky.values()
            }
        else:
            self.MergeJdf(self.OriginalProcessor, newJdf)
        recount = False
        if recount:
            if not (
                    len(set(z.GetName() for z in self.OriginalProcessor.JdfZastavky.values()))
                    == len(self.OriginalProcessor.JdfZastavky)
            ):
                for z in sorted(
                        x.GetName() for x in self.OriginalProcessor.JdfZastavky.values()
                ):
                    print(z)
                input("Počet se neshoduje")

    def FinishMerge(self) -> Optional[JdfProcessor]:
        """!
        Parses the merged data
        @return: The merged JDF batch or None if no data was added (succesfully)
        """
        if not self.OriginalProcessor:
            return None
        print("Parsing the merged data")
        self.OriginalProcessor.ParseAll(False)
        self.OriginalProcessor.UnifyCodes()
        self.OriginalProcessor.FormatTimesTrips(False)
        print("Processor created")
        return self.OriginalProcessor

    def MergeJdf(self, old: JdfProcessor, new: JdfProcessor):
        """!
        Merges two JDF batches.
        Duplicate lines are treated as new versions; duplicate stops are merged, if the BlizkaObec values are equal as well
        @param old: The original JDF batch (after merging, it will contain the merged data)
        @param new: The new JDF batch
        """
        # New ID of stop / version of line are changed to the highest current + 1
        self.MaxZastID = max(old.JdfZastavky.keys())
        for linka in list(new.JdfLinky.values()):
            # If a line with this ID already exists in old batch, change its key
            linka2 = old.JdfLinky.get(linka.GetID())
            if linka2:
                # Find lowest version available
                i = 0
                while True:
                    i += 1
                    lid = (linka.CisloLinky, i)
                    if old.JdfLinky.get(lid):
                        continue
                    else:
                        new.ChangeKey(linka, lid)
                        break
        lz = list(new.JdfZastavky.values())
        # We start from highest id to prevent overwriting
        for i in reversed(range(len(new.JdfZastavky))):
            new.ChangeKey(lz[i], lz[i].GetID() + self.MaxZastID)
        self.MaxZastID = max(new.JdfZastavky.keys())
        # zast and zast3 are in new, zast2 in old
        for zast in list(new.JdfZastavky.values()):
            name = zast.GetName()
            zast2ID = self.StopNames.get(name)
            if zast2ID:
                # Same name - change the ID to match
                # but first check if we do not overwrite ID of another stop
                zast3 = new.JdfZastavky.get(zast2ID)
                if zast3:
                    self.MaxZastID += 1
                    new.ChangeKey(zast3, self.MaxZastID)
                    name3 = zast3.GetName()
                    self.StopNames[name3] = zast3.GetID()
                new.ChangeKey(zast, zast2ID)
            else:
                self.StopNames[name] = zast.GetID()
                # Find if already exists stop with this ID and update it
                zast2 = old.JdfZastavky.get(zast.GetID())
                if zast2:
                    assert False
                    self.MaxZastID += 1
                    new.ChangeKey(zast, self.MaxZastID)
                    self.StopNames[name] = zast.GetID()

        old.copyGeneric(new.JdfAltDopravci, old.JdfAltDopravci, True)
        old.copyGeneric(new.JdfCasoveKody, old.JdfCasoveKody, True)
        old.copyGeneric(new.JdfDopravci, old.JdfDopravci, True)
        old.copyGeneric(new.JdfLinky, old.JdfLinky, True)
        old.copyGeneric(new.JdfLinkyExt, old.JdfLinkyExt, True)
        old.copyGeneric(new.JdfNavaznosti, old.JdfNavaznosti, True)
        # old.copyGeneric(new.PevneKody,old.JdfPevneKody)
        old.copyGeneric(new.JdfSpoje, old.JdfSpoje, True)
        old.copyGeneric(new.JdfZastavkyLinek, old.JdfZastavkyLinek, True)
        old.copyGeneric(new.JdfCasyZastavek, old.JdfCasyZastavek, True)
        old.copyGeneric(new.JdfZastavky, old.JdfZastavky, True)


def FindSelectedDistancesInAdjMatrix(adjacencyMatrix: np.ndarray, selectedIndices: List[int], cutoff: int = 2 ** 13):
    """!
    Optimizes the adjacency matrix by calculating the distances between the selected indices only.
    The other cells are used for intermediate calculations.
    The matrix is modified in place.
    @param adjacencyMatrix: Adjacency matrix
    @param selectedIndices: Indices of the selected stops
    @param cutoff: Maximum distance to be considered (reduce if the expected maximum distance is lower)
    @return: The modified adjacency matrix
    @note Uses Dijkstra's algorithm for multiple-sources shortest path
    """
    # Dumb down matrix with replacing zeroes
    adj_reduced = np.copy(adjacencyMatrix)
    adj_reduced[adj_reduced >= cutoff] = 0
    adj = scp.csr_matrix(adj_reduced)
    adj_reduced = None

    dist_matrix = scp.csgraph.dijkstra(adj, directed=False, indices=selectedIndices, limit=cutoff)

    for row, nfrom in enumerate(selectedIndices):
        for nto in range(len(dist_matrix[row])):
            dist = dist_matrix[row, nto]
            adjacencyMatrix[nfrom, nto] = int(min(adjacencyMatrix[nfrom, nto], dist))
    return adjacencyMatrix


def SaveDistances(f: TextIO, stops: List[str], matrix: np.ndarray):
    """!
    Dumps a distance matrix with stop names as the first row/column
    @param f: File to write to (on windows, set newline='' to avoid double newlines)
    @param stops: List of stops
    @param matrix: Distance matrix
    """
    if len(stops) != len(matrix):
        raise ValueError("Stops and matrix have different lengths")
    # if not square matrix:
    if matrix.shape[0] != matrix.shape[1]:
        raise ValueError("Matrix is not square")
    csvWriter = csv.writer(f, delimiter='\t', quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
    csvWriter.writerow(["Stop names"] + stops)
    for i in range(len(matrix)):
        csvWriter.writerow([stops[i]] + list(matrix[i]))
    return


def ReadDistances(f: TextIO) -> Tuple[List[str], np.ndarray]:
    """!
    Reads a distance matrix with stop names as the first row/column
    @param f: File to read from
    @return: Tuple of stop names and distance matrix
    """
    csvReader = csv.reader(f, delimiter='\t', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    stops = next(csvReader)[1:]
    matrix = []
    for row in csvReader:
        matrix.append(row[1:])
    matrix = [m for m in matrix if m]
    try:
        matrix = np.array(matrix, dtype="int")
        if np.any(matrix < 0):
            raise ValueError("Negative values in the distance matrix")
    except ValueError:
        raise
    return stops, matrix


def ParseSingleFolder(folder: str) -> Optional[JdfProcessor]:
    """!
    Create a JdfProcessor containing a single JDF batch
    @param folder: Folder containing the JDF batch
    @return: JdfProcessor containing the JDF batch or None if failed
    """
    merger = JdfMerger()
    merger.AddNew(folder)
    processor = merger.FinishMerge()
    return processor


def ParseMultipleFolders(folders: List[str], attemptParse=False) -> Optional[JdfProcessor]:
    """!
    Create a JdfProcessor created from multiple JDF batches
    @param folders: List of folders containing the JDF batches
    @param attemptParse: Attempt to if a folder does not contain a JDF batch (forward the error)
    @return: JdfProcessor containing a merged JDF batch
    """
    merger = JdfMerger(None)
    try:
        for f in progressBar(folders, prefix='Progress:', suffix='Complete', length=50):

            if os.path.exists(os.path.join(f, "Zastavky.txt")) or attemptParse:
                print("\n", f, sep="")
                merger.AddNew(f)
            else:
                print("Skip folder " + f)
            gc.collect(0)
    except KeyboardInterrupt:
        print("Interrupted")
    except:
        raise
    finally:
        process = merger.FinishMerge()
    gc.collect()
    print("Done")
    return process


def FilterJdfFolders(folderList: Iterable[str], stop: Optional[str] = None, company: Optional[str] = None,
                     line: Optional[str] = None):
    """!
    Filter folders of JDF data by stop, company or line (to be exact, the string must appear in the corresponding file)
    @param folderList: List of folders to filter
    @param stop: Regex which must appear in <em>Zastavky.txt</em> for accepting the folder
    @param company: Regex which must appear in <em>Dopravci.txt</em> for accepting the folder
    @param line: Regex which must appear in <em>Linky.txt</em> for accepting the folder
    @return: List of filtered folders
    """
    stopCB = lambda r, f: InFileRE(r, os.path.join(f, "Zastavky.txt"), JDF_ENCODING) if stop else True
    companyCB = lambda r, f: InFileRE(r, os.path.join(f, "Dopravci.txt"), JDF_ENCODING) if company else True
    lineCB = lambda r, f: InFileRE(r, os.path.join(f, "Linky.txt"), JDF_ENCODING) if line else True
    regexStop = re.compile(stop) if stop else None
    regexCompany = re.compile(company) if company else None
    regexLine = re.compile(line) if line else None
    return [folder for folder in folderList if
            stopCB(regexStop, folder) and
            companyCB(regexCompany, folder) and
            lineCB(regexLine, folder)]
