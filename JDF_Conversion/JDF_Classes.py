#!/usr/bin/env python3

"""!
@file JDF_Classes.py
@namespace JDF_Classes
@brief Classes corresponding to the timetable data in the JDF format
@note Uses corresponding Czech names
"""

import warnings

from JDF_Conversion.Timetable_Enums import *
from JDF_Conversion.Utilities import *


class JdfVerze:
    """!
    @brief Metadata about the generated JDF package
    """

    def __init__(self,
                 verze: str,
                 du: str,
                 kraj: str,
                 identifikator: str,
                 datum: str,
                 jmeno: str
                 ):
        assert (verze == "1.11" or verze == "1.10")
        assert (len(datum) == 8)
        self.Verze = verze
        self.DU = du
        self.OkresKraj = kraj
        self.IdentifikatorDavky = identifikator
        self.DatumVyroby = datum
        self.Jmeno = jmeno

    def ConvertTimes(self):
        self.DatumVyroby = ConvertDDMMYYYY(self.DatumVyroby)

    def Serialize(self):
        res = [
            self.Verze,
            self.DU,
            self.OkresKraj,
            self.IdentifikatorDavky,
            ConvertToDDMMYYYY(self.DatumVyroby),
            self.Jmeno
        ]
        return res

    def __str__(self):
        return f"Verze: {self.Verze} \n Datum vyroby: {self.DatumVyroby}"

    def __repr__(self):
        return self.__str__()


class JdfZastavka:
    """!
    @brief Stop
    @note There is no documentation for the fields which are only copied from the JDF files
    """

    def __init__(self, cislo, obec, cast, misto, okres, stat, *kody):
        self.CisloZastavky = int(cislo)
        self.Obec = obec
        self.CastObce = cast
        self.BlizsiMisto = misto
        self.BlizkaObec = okres
        self.Stat = stat
        self.Kody = list(kody)

        self.Linky = None
        self.Odjezdy = None
        self.Prijezdy = None

    def BindCodes(self, dictKody: Dict[str, "JdfPevnyKod"]):
        """!
        @brief Convert time codes for this stop
        @param dictKody Dictionary of codes
        """
        self.Kody = [dictKody[x] for x in self.Kody if x]

    def AddDepartures(self,
                      linky: Dict[Tuple[int, int], "JdfLinka"],
                      linZasColl: Dict[int, List["JdfZasLinka"]],
                      zasSpoje: Dict[int, List["JdfZasSpoj"]]):
        """!
        @brief Add departures and arrivals for this stop
        @param linky Lines
        @param linZasColl Stops on lines
        @param zasSpoje Departures
        @note See type hints for more details
        """
        linka: JdfLinka
        zsl: JdfZasLinka
        zsp: JdfZasSpoj
        self.Linky = {}
        self.Odjezdy = {}
        self.Prijezdy = {}

        zasLinkaList = linZasColl.get(self.CisloZastavky, [])
        for zsl in zasLinkaList:
            linka = linky[(zsl.CisloLinky, zsl.RozliseniLinky)]
            self.Linky[(zsl.CisloLinky, zsl.RozliseniLinky)] = linka
            TC = zsl.TC

            for cisloSpoje in linka.Spoje.keys():
                keyZsp = (zsl.CisloLinky, zsl.RozliseniLinky, cisloSpoje, TC)
                keySp = (zsl.CisloLinky, zsl.RozliseniLinky, cisloSpoje)
                zsp = zasSpoje.get(keyZsp)  # Spoj nemusi tuto zastavku navstivit
                if not zsp:
                    continue

                # One trip can visit one stop multiple times
                if zsp.Prijezd >= 0 or zsp.Odjezd >= 0:
                    prij = self.Prijezdy.get(keySp)
                    if not prij:
                        self.Prijezdy[keySp] = [zsp]
                    else:
                        prij.append(zsp)
                if zsp.Odjezd >= 0:
                    odj = self.Odjezdy.get(keySp)
                    if not odj:
                        self.Odjezdy[keySp] = [zsp]
                    else:
                        odj.append(zsp)
        return

    def HasClo(self) -> bool:
        """!
        @brief Check if the stop has a CLO code
        @return: True if the stop has a CLO code
        """
        return PevneKody.Clo in self.Kody

    def GetName(self) -> str:
        """!
        @brief Get the standardized name for a stop, removing trailing commas. The "Blízká obec" is always at the end.
        @return: The standardized name for a stop, with optional Blízká Obec at the end
        @summary Example:
        Obec = "Kunovice", CastObce = "", BlizsiMisto = "žel.st", BlizkaObec = VS
        -> "Kunovice,,žel.st.[VS]"
        """
        name = f"{self.Obec},{self.CastObce},{self.BlizsiMisto}".rstrip(",") + f"[{self.BlizkaObec}]"
        return name

    def __hash__(self) -> int:
        return hash(self.GetID())

    def GetID(self) -> int:
        """!
        @brief Get the ID of the stop
        @return: The ID of the stop
        """
        return self.CisloZastavky

    def __str__(self) -> str:
        return f"{self.GetName()} {[k.CodeSign.value for k in self.Kody]}"

    def __repr__(self) -> str:
        return str(self)

    def Serialize(self) -> List[str]:
        """!
        @brief Serialize the stop to a list of strings
        @return: The serialized stop
        """
        res = [
            str(self.CisloZastavky),
            self.Obec,
            self.CastObce,
            self.BlizsiMisto,
            self.BlizkaObec,
            self.Stat,
            *UnpackCodes(self.Kody, 6)
        ]
        return [str(r) for r in res]


# "Soubor Pevnykod je číselník pevných kódů..." - conversion of number to sign (see enum PevneKody)
class JdfPevnyKod:
    """!
    @brief A "table" of converting numeric strings to timetable signs (see enum PevneKody)
    @note All other CSV files in the JDF use numeric strings for the timetable signs (for unknown reason)
    """

    def __init__(self, number: str, sign: str, *_):
        """!
        @brief Constructor. If the sign is invalid, throws an error
        @param number: Numeric string
        @param sign: Timetable sign
        @param _: Reserved fields (columns in CSV)
        @throws Exception: If the sign is invalid
        """
        try:
            self.CodeSign = PevneKody(sign)
        except ValueError as ve:
            raise Exception("CodeSign kodu neexistuje!") from ve
        self.CodeNumber = number

    def GetID(self) -> str:
        """!
        @brief Get the numeric string used for encoding the timetable sign
        @return: The numeric string used for encoding the timetable sign
        """
        return self.CodeNumber

    def Serialize(self) -> List[str]:
        """!
        @brief Serialize the timetable sign to a row in CSV
        @return: The serialized timetable sign
        """
        res = [
            self.CodeNumber,
            self.CodeSign.value,
            ""  # rezerva
        ]
        return [str(r) for r in res]


class JdfDopravce:
    """!
    @brief Information about a transport company
    """

    def __init__(
            self,
            ic: str,
            dic: str,
            jmeno: str,
            druh: str,
            osoba: str,
            sidlo: str,
            tel1: str,
            tel2: str,
            tel3: str,
            fax: str,
            email: str,
            web: str,
            rozliseni: str,
    ):

        self.IC = ic
        self.DIC = dic
        self.Jmeno = jmeno
        if druh == "2":
            self.Fyzicka = True
        elif druh == "1":
            self.Fyzicka = False
        else:
            raise Exception("Neni rozlisena fyzicka x pravnicka osoba")
        self.Osoba = osoba
        self.Sidlo = sidlo
        self.Telefony = [t if t else None for t in [tel1, tel2, tel3]]
        self.Fax = fax
        self.Email = email
        self.Web = web
        self.RozliseniDopravce = int(rozliseni)

    def GetID(self) -> Tuple[str, int]:
        """!
        @brief Get the ID of the transport company
        @return: The IC of the transport company and extra field for duplicate ICs
        """
        return self.IC, self.RozliseniDopravce

    def __hash__(self) -> int:
        return hash(self.GetID())

    def Serialize(self):
        """!
        @brief: Serializes the fields into original CSV columns
        @return: A list with the same data as when being constructed
        """
        res = [
            self.IC,
            self.DIC,
            self.Jmeno,
            "2" if self.Fyzicka else "1",
            self.Osoba if self.Fyzicka else "",
            self.Sidlo,
            self.Telefony[0],
            self.Telefony[1],
            self.Telefony[2],
            self.Fax,
            self.Email,
            self.Web,
            self.RozliseniDopravce,
        ]
        res = ["" if r is None else str(r) for r in res]
        return res

    @staticmethod
    def GetColumns():
        """!
        @brief Get the column names of the CSV file
        @return: The column names of the CSV file
        """
        return [
            "IC",
            "DIC",
            "Jmeno",
            "Druh",
            "Osoba",
            "Sidlo",
            "Tel1",
            "Tel2",
            "Tel3",
            "Fax",
            "Email",
            "Web",
            "RozliseniDopravce",
        ]

    def SerializeWithCols(self):
        """
        @brief: Serializes the fields into original CSV columns
        @return: A tuple (columnName,columnValue) with the same data as when being constructed
        """
        ret = [
            ("IČ", self.IC)
            , ("DIČ", self.DIC)
            , ("Obchodní jméno", self.Jmeno)
            , ("Druh firmy", "2" if self.Fyzicka else "1")
            , ("Jméno fyz.osoby", self.Osoba if self.Fyzicka else "")
            , ("Sídlo (adresa)", self.Sidlo)
            , ("Telefon sídla", self.Telefony[0])
            , ("Telefon dispečink", self.Telefony[1])
            , ("Telefon informace", self.Telefony[2])
            , ("Fax", self.Fax)
            , ("E-mail", self.Email)
            , ("www", self.Web)
            , ("Rozlišení dopravce", self.RozliseniDopravce)
        ]
        ret = [(r[0], "" if r[1] is None else str(r[1])) for r in ret]
        return ret


class JdfLinka:
    """!
    @brief Information about a line - used interchangeably with "timetable"
    """
    LineTypes = "ABNPVZD"
    VehicleTypes = "AELMPT"
    ArgCount = 17
    ReserveIndex = 9

    def __init__(
            self,
            cislo: str,
            nazev: str,
            dopravce: str,
            typ: str,
            prostredek: str,
            vylukovy: str,
            seskupeni: str,
            oznacniky: str,
            jednosm: str,
            rezerva: str,
            licČ: str,
            licOd: str,
            licDo: str,
            jrOd: str,
            jrDo: str,
            rozlisDopravce: str,
            rozlisLinky: str,
    ):
        self.CisloLinky = int(cislo)
        self.NazevLinky = nazev
        self.DopravceIC = dopravce
        if typ not in self.LineTypes:
            raise Exception("Spatny typ linky")
        self.Typ = TypLinky(typ)
        if prostredek not in self.VehicleTypes:
            raise Exception("Spatny typ prostredku")
        self.Prostredek = Prostredek(prostredek)
        self.Vyluka = vylukovy == "1"
        self.Seskupeni = seskupeni == "1"
        self.Oznacniky = oznacniky == "1"
        self.Jednosmerny = jednosm == "1"

        self.ValidFrom = jrOd
        self.ValidTo = jrDo
        self.RozliseniDopravce = int(rozlisDopravce)
        # stejná linka, jen více JŘ (např.výlukový)
        self.RozliseniLinky = int(rozlisLinky)

        self.Rezerva = rezerva
        self.LicencniCislo = licČ
        self.PlatnostLicenceOd = licOd
        self.PlatnostLicenceDo = licDo

        self.TarCisla = None
        self.Spoje = None
        self.Zastavky = None
        self.IdsCisla = None
        self.Dopravce = None
        self.AlternativniDopravci = None

    def Bind(self,
             zaslinkyColl: Dict[Tuple[int, int], List["JdfZasLinka"]],
             idsZaznamy: List["JdfLinkaExt"],
             dopravci: List[JdfDopravce],
             spojeColl: Dict[Tuple[int, int], List["JdfSpoj"]],
             altDopravciColl: Optional[Dict[Tuple[int, int], List["JdfAlternDopravce"]]] = None
             ):
        """!
        @brief Create references to other objects
        @param zaslinkyColl: Stops per lines
        @param idsZaznamy: Integrated transport systems related to the lines
        @param dopravci: Transport companies
        @param spojeColl: Trips belonging to the lines
        @param altDopravciColl: Alternative transport companies for a line
        """

        zl: JdfZasLinka
        sp: JdfSpoj
        ids: JdfLinkaExt
        self.TarCisla = []
        zaslinky = zaslinkyColl[self.GetID()]
        for zl in zaslinky:
            self.TarCisla.append(zl.TC)
        self.TarCisla.sort()
        zaslinky.sort(key=lambda zl: zl.TC)
        # zaslinky,self.TarCisla = [(z,t) for z,t in sorted(zip(zaslinky,self.TarCisla))]
        self.Zastavky = zaslinky

        self.Spoje = {}
        spoje = spojeColl[self.GetID()]
        for sp in spoje:
            self.Spoje[sp.CisloSpoje] = sp

        self.IdsCisla = []
        for ids in idsZaznamy.values():
            if ExtractLinka(ids) == self.GetID():
                self.IdsCisla.append((ids.Poradi, ids.Oznaceni))
        self.IdsCisla = [oznaceni for (poradi, oznaceni) in sorted(self.IdsCisla)]

        self.Dopravce = dopravci[(self.DopravceIC, self.RozliseniDopravce)]
        self.AlternativniDopravci = altDopravciColl.get(self.GetID())

    def ConvertTimes(self):
        """!
        @brief Convert times of timetable validity from string to datetime.date
        """
        self.ValidFrom = ConvertDDMMYYYY(self.ValidFrom)
        self.ValidTo = ConvertDDMMYYYY(self.ValidTo)
        return

    # Checks all higher versions of this line, if its validity is not overwritten
    # Returns the currently valid version (0 if none)
    def AnotherVersionValid(self, linky: Dict[Tuple[int, int], "JdfLinka"], datum: datetime.date) -> int:
        """!
        @brief Check if there is a higher version of the line that is valid
        @param linky: All lines
        @param datum: Date to check
        @return: The currently valid version (0 if the current version is valid)
        @note Deprecated
        """
        version = self.RozliseniLinky + 1
        while True:
            newLine = linky.get((self.CisloLinky, version))
            if not newLine:  # Current version is the highest
                return 0
            if (
                    newLine.ValidFrom <= datum <= newLine.ValidTo
            ):  # New version overwrites current
                return version
            version += 1  # New version exists, but at different date

    # Checks all versions of this line, if another timetable was not introduced recently
    # Returns the currently valid version
    def VersionValidByDate(self, linky, datum: datetime.date):
        """!
        @brief Checks all versions of this line, if another timetable is not valid
        @brief A version with later starting date is considered to overwrite the older timetable
        @param linky: All lines
        @param datum: Date to check
        @return: The currently valid version
        """
        version = 1
        bestDate = datetime.date.min
        chosenVersion = self.RozliseniLinky
        while True:
            newLine = linky.get((self.CisloLinky, version))
            if not newLine:  # Current version is the highest
                return chosenVersion
            # This version is valid
            if newLine.ValidFrom <= datum and datum <= newLine.ValidTo:
                # and its validity is closest to the current date
                if newLine.ValidFrom >= bestDate:  # equality, as later version might be also valid
                    bestDate = newLine.ValidFrom
                    chosenVersion = version
            version += 1

    def __hash__(self) -> int:
        return hash(self.GetID())

    def GetID(self) -> Tuple[int, int]:
        """!
        @brief Get line ID
        @return: Line number and version
        """
        return self.CisloLinky, self.RozliseniLinky

    def __str__(self) -> str:
        return f"Linka {self.CisloLinky} ({self.RozliseniLinky})"

    def __repr__(self) -> str:
        return f"Linka {self.CisloLinky} ({self.RozliseniLinky})"

    @staticmethod
    def GetColumns():
        """!
        @brief Get column names
        @return: Column names
        """
        return ["CisloLinky", "RozliseniLinky", "DopravceIC", "RozliseniDopravce", "ValidFrom", "ValidTo",
                "Rezerva",
                "Oznacniky", "LicencniCislo", "PlatnostLicenceOd", "PlatnostLicenceDo"]

    def Serialize(self) -> List[str]:
        """!
        @brief Serialize the line to a CSV row
        @return: Serialized line
        """
        res = [
            str(self.CisloLinky).zfill(6),
            self.NazevLinky,
            self.DopravceIC,
            self.Typ.value,
            self.Prostredek.value,
            BoolToNumeric(self.Vyluka),
            BoolToNumeric(self.Seskupeni),
            BoolToNumeric(self.Oznacniky),
            BoolToNumeric(self.Jednosmerny),
            self.Rezerva,
            self.LicencniCislo,
            self.PlatnostLicenceOd,
            self.PlatnostLicenceDo,
            ConvertToDDMMYYYY(self.ValidFrom),
            ConvertToDDMMYYYY(self.ValidTo),
            self.RozliseniDopravce,
            self.RozliseniLinky
        ]
        return EnsureStrings(res)


# Získá ID např. linky pro cokoliv, co není přímo linka, ale obsahuje vazbu na linku
def ExtractLinka(linka: Union["JdfLinka", "JdfLinkaExt", "JdfSpoj", "JdfZasLinka"]) -> Tuple[int, int]:
    """!
    @brief Get line ID from any object that contains a reference to a line (e.g. JdfSpoj)
    @param linka: Object having the fields CisloLinky and RozliseniLinky
    @return: A tuple which can be used to query a line by its ID
    """
    return linka.CisloLinky, linka.RozliseniLinky


def ExtractZastavka(zast: Union["JdfZastavka", "JdfZasLinka"]) -> int:
    """!
    @brief Get stop ID from any object that contains a reference to a stop (e.g. JdfSpoj)
    @param zast: Object having the field CisloZastavky
    @return: A tuple which can be used to query a stop by its ID
    """
    return zast.CisloZastavky


def ExtractSpoj(spoj: Union["JdfSpoj", "JdfZasLinka"]) -> Tuple[int, int, int]:
    """!
    @brief Get trip ID from any object that contains a reference to a trip (e.g. JdfCasSpojLinkaZastavka)
    @param spoj: Object having the fields CisloLinky, RozliseniLinky and CisloSpoje
    @return: A tuple which can be used to query a trip by its ID
    """
    return spoj.CisloLinky, spoj.RozliseniLinky, spoj.CisloSpoje


class JdfLinkaExt:
    """!
    @brief A class representing alternative line numbers with relation to the integrated transport system (IDS)
    """

    def __init__(self, cislo: str, poradi: str, kod: str, oznaceni: str, pref: str, _: str, rozliseni: str):
        self.CisloLinky = int(cislo)
        self.Poradi = int(poradi)
        self.Kod = int(kod)  # IDS code
        self.Oznaceni = oznaceni  # Simplified line number
        self.Preference = pref == "1"
        self.RozliseniLinky = int(rozliseni)

    def __hash__(self) -> int:
        return hash(self.GetID())

    def GetID(self) -> Tuple[int, int, int]:
        return self.CisloLinky, self.RozliseniLinky, self.Poradi

    def Serialize(self) -> List[str]:
        res = [
            str(self.CisloLinky).zfill(6),
            self.Poradi,
            self.Kod,
            self.Oznaceni,
            BoolToNumeric(self.Preference),
            self.RozliseniLinky
        ]
        return EnsureStrings(res)


class JdfSpoj:
    """!
    @brief A class representing a trip (list of stops with departures/arrivals)
    """

    # PovoleneKody = "X+1234567R#@%{[OT!"
    def __init__(
            self,
            linka: str,
            spoj: str,
            k1: str,
            k2: str,
            k3: str,
            k4: str,
            k5: str,
            k6: str,
            k7: str,
            k8: str,
            k9: str,
            k10: str,
            kodSkupiny: str,
            rozliseni: str
    ):
        self.CisloLinky = int(linka)
        self.CisloSpoje = int(spoj)
        self.Smer = 1 if self.CisloSpoje % 2 == 1 else -1
        self.RozliseniLinky = int(rozliseni)
        self.Kody = [k1, k2, k3, k4, k5, k6, k7, k8, k9, k10]
        self.KodSkupiny = kodSkupiny


        self.TripNo = None
        self.StopEvents = None
        self.First = None
        self.Last = None
        self.TimeCodes = None
        self.Line = None
        self.AltOperators = None
        self.OperatingDays = None
        self.InfoCodes = None
        self.TimeSign = None

    def Bind(
            self,
            linky: Dict[Tuple[int, int], JdfLinka],
            zasSpojeColl: Dict[Tuple[int, int, int], List["JdfZasLinka"]],
            casKodyColl: Dict[Tuple[int, int, int], List["JdfCasKod"]],
            altDoprColl: Optional[Dict[Tuple[int, int], List["JdfAlternDopravce"]]] = None,
            mistenky=None,
            navaznosti=None,
            spojSkup=None,
    ):
        """!
        @brief Create references to other objects
        @param linky: Dictionary of all lines
        @param zasSpojeColl: Used to get a list of departures/arrivals for this trip
        @param casKodyColl: Used to get a list of time codes for this trip
        @param altDoprColl: Used to get a list of alternative transport operators for this trip
        @param mistenky: Unused
        @param navaznosti: Unused
        @param spojSkup: Unused
        """
        sid = self.GetID()
        zsc = zasSpojeColl[sid]
        self.StopEvents = zsc
        self.TimeCodes = casKodyColl.get(sid, [])
        self.Line = linky[(self.CisloLinky, self.RozliseniLinky)]
        self.AltOperators = altDoprColl.get(
            (self.CisloLinky, self.RozliseniLinky), {}
        ).get(self.CisloSpoje)

        self.OperatingDays = []
        k: JdfPevnyKod
        for k in self.Kody:
            try:
                k = DnyProvozu(k.CodeSign.value)
                self.OperatingDays.append(k)
            except ValueError:
                continue

    def BindCodes(self, dictKody):
        """!
        @brief Decode time codes
        """
        self.Kody = [dictKody[k] for k in self.Kody if k]

    def AddTo(
            self, dictSpojeColl: Dict[Tuple[int, int], List["JdfSpoj"]]
    ):  # Prida spoj do seznamu v prislusnem slovniku, resp. vytvori novy seznam s timto spojem
        """!
        @brief Add this trip to a collection of trips for each line
        @param dictSpojeColl: Dictionary of trips for each line (line ID -> list of trips)
        """
        key = (self.CisloLinky, self.RozliseniLinky)
        coll = dictSpojeColl.get(key)
        if not coll:
            dictSpojeColl[key] = [self]
        else:
            coll.append(self)

    def SortStops(self):
        """!
        @brief Sort stops by their order in the trip
        @note Does not use actual departure/arrival times, but TC (tariff number of the stop),
         depending on the direction of the trip
        """
        self.StopEvents.sort(key=lambda st: st.TC * self.Smer)
        self.First = self.StopEvents[0]
        self.Last = self.StopEvents[-1]
        self.StopEvents = {zsp.TC: zsp for zsp in self.StopEvents}
        if self.First.Odjezd < 0:
            if self.First.Prijezd < 0:
                raise ValueError("Odjezd prvni zastavky neni uveden")
            else:
                self.First.Odjezd = self.First.Prijezd
                warnings.warn("Odjezd prvni zastavky neni uveden, pouzit prijezd")
        if self.Last.Prijezd < 0:
            if self.Last.Odjezd < 0:
                raise ValueError("Prijezd na posledni zastavku neni uveden")
            else:
                self.Last.Prijezd = self.Last.Odjezd
                warnings.warn("Prijezd na posledni zastavku neni uveden, pouzit odjezd")
        return

    def CompressTimeCodes(self):
        """!
        @brief Compress time codes (restrictions) into TimeSign - an object representing a set of restrictions,
        shown in timetables
        @note Example: [20] shows that the trip does not operate on school holidays; since there are more intervals
        of these holidays, in JDF they must be split into individual restrictions
        """
        self.InfoCodes = []
        self.TimeSign = None
        ck: JdfCasKod
        for ck in self.TimeCodes:
            if not ck.Typ:
                self.InfoCodes.append(ck)
            else:  # add negative sign
                if not self.TimeSign:
                    self.TimeSign = CasovaZnacka(ck.Znacka)
                self.TimeSign.PridejOmezeni(ck)

    def SerializeStops(self) -> List[Tuple[str, str]]:
        """!
        @brief Serialize stops into a dictionary consisting of entries {stopName:departureTime}
        @return: List of pairs of stops and their departure times
        @note If the departure time is not known, the arrival time is used instead
        """
        res = []
        zsp: JdfZasSpoj
        for zsp in self.StopEvents.values():
            itime = zsp.Odjezd if zsp.Odjezd >= 0 else zsp.Prijezd
            if itime >= 0:
                time = SplitToHHMM(itime)
            else:
                continue
            name = zsp.Zastavka.GetName()
            res.append((name, time))
        return res

    def JedeVDen(self, datum: datetime.date) -> bool:
        """!
        @brief Check if the trip operates on a given day.
        @param datum: Date to check
        @return: True if the trip operates on the given day, False otherwise
        @note Checks all available info: timetable validity, restrictions, and days of week/holidays
        """
        # zkontroluj datova omezeni
        if self.TimeSign:
            # jede pomoci 2 nebo 3 -> True
            # nejede kvuli omezeni -> False
            jede = self.TimeSign.DanyDenPovolen(datum)
            if jede == CanOperate.Surely:
                return True
            elif jede == CanOperate.Restricted:
                return False
        # zkontroluj typ dne
        # správný typ dne -> True
        # jinak -> False
        if not self.OperatingDays:  # provoz není omezen značkou
            return True
        CisloDne = datum.isocalendar()[2]
        for k in self.OperatingDays:

            if k == DnyProvozu.Svatky:
                if CisloDne == 7 or VypocetSvatku.JeSvatek(datum):  # nebo nedele
                    return True
            elif k == DnyProvozu.PracovniDny:
                if VypocetSvatku.JePracovniDen(datum):
                    return True

            else:
                if int(k.value) == CisloDne:  # 1234567
                    return True

        return False

    def GetOperationalPeriodType(self) -> "OperationalPeriodType":
        """!
        @brief Determine if trip operates in working days or weekends
        @return: Workdays if the trip does not operate on weekends,
         Weekends if the trip does not operate on workdays,
         Either if operates on both
        """
        res = 2
        # Check for 6.7,+
        if DnyProvozu.Svatky in self.OperatingDays or \
                DnyProvozu.Sobota in self.OperatingDays or \
                DnyProvozu.Nedele in self.OperatingDays:
            res += 1
        # Check for 1-5,x
        if DnyProvozu.PracovniDny in self.OperatingDays or \
                DnyProvozu.Pondeli in self.OperatingDays or \
                DnyProvozu.Utery in self.OperatingDays or \
                DnyProvozu.Streda in self.OperatingDays or \
                DnyProvozu.Ctvrtek in self.OperatingDays or \
                DnyProvozu.Patek in self.OperatingDays:
            res -= 1
        """Nothing specified: returns 2; 1-5,x only returns 1; 6.7,+ only returns 3"""
        return OperationalPeriodType(res)

    def HasClo(self) -> bool:
        """!
        @brief Check if the trip passes through a stop with CLO (border crossing)
        @return: True if the trip passes through a stop with CLO, False otherwise
        """
        zcs: JdfZasSpoj
        return any(zcs.Zastavka.HasClo() for zcs in self.StopEvents.values())

    def __hash__(self) -> int:
        return hash(self.GetID())

    def __eq__(self, other) -> bool:
        return self.GetID() == other.GetID()

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)

    def GetID(self) -> Tuple[int, int, int]:
        return self.CisloLinky, self.RozliseniLinky, self.CisloSpoje

    def __str__(self) -> str:
        line1 = f"Spoj {self.CisloSpoje} linky {self.CisloLinky}/{self.RozliseniLinky}"
        line2 = ""
        if getattr(self, "First"):
            line2 = (
                f"Z: {self.First.Zastavka.GetName()} v {SplitToHHMM(self.First.Odjezd)}"
            )
        line3 = ""
        if getattr(self, "Last"):
            line3 = (
                f"Do: {self.Last.Zastavka.GetName()} v {SplitToHHMM(self.Last.Prijezd)}"
            )
        return f"{line1}\n{line2}\n{line3}"

    def __repr__(self) -> str:
        return str(self)

    def Serialize(self) -> List[str]:
        """!
        @brief Serialize the trip into a row in CSV
        @return: List of strings representing the trip
        """
        res = [
            str(self.CisloLinky).zfill(6),
            self.CisloSpoje,
            *UnpackCodes(self.Kody, 10),
            self.KodSkupiny,
            self.RozliseniLinky
        ]
        # assert((self.CisloSpoje%2==1 and self.Smer==1) or( self.CisloSpoje%2==0 and self.Smer==-1))
        return EnsureStrings(res)


class JdfZasLinka:
    """!
    @brief Class representing the relation whether a stop is in a line's timetable
    """

    def __init__(self, linka: str, tc: str, pasmo: str, cislo: str, cas: str,
                 k1: str, k2: str, k3: str, rozliseni: str):
        self.CisloLinky = int(linka)
        self.TC = int(tc)
        self.Pasmo = pasmo
        self.CisloZastavky = int(cislo)
        self.PrumCas = cas
        self.Kody = [k1, k2, k3]
        self.RozliseniLinky = int(rozliseni)

        self.Zastavka = None

    def Bind(self, zastavky: Dict[int, JdfZastavka]):
        """!
        @brief Create a reference to a JdfZastavka object
        """
        self.Zastavka = zastavky[self.CisloZastavky]

    def BindCodes(self, dictKody):
        """!
        @brief Decode the notes for this stop
        """
        self.Kody = [dictKody[k] for k in self.Kody if k]

    def AddToLinky(
            self, dictLin: Dict[Tuple[int, int], List["JdfZasLinka"]]
    ):
        """!
        @brief Add the line to the list of lines serving this stop
        """
        key = (self.CisloLinky, self.RozliseniLinky)
        coll = dictLin.get(key)
        if not coll:
            dictLin[key] = [self]
        else:
            coll.append(self)

    def AddToZastavky(self, dictZast: Dict[int, List["JdfZasLinka"]]):
        """!
        @brief Add the stop to the list of stops served by this line
        """
        key = self.CisloZastavky
        coll = dictZast.get(key)
        if not coll:
            dictZast[key] = [self]
        else:
            coll.append(self)

    def __hash__(self) -> int:
        return hash(self.GetID())

    def GetID(self) -> Tuple[int, int, int]:
        return self.CisloLinky, self.RozliseniLinky, self.TC

    def Serialize(self) -> List[str]:
        """!
        @brief Serialize the stop into a row in CSV
        @return: List of strings representing the stop
        """
        res = [
            str(self.CisloLinky).zfill(6), self.TC, self.Pasmo, self.CisloZastavky, self.PrumCas,
            *UnpackCodes(self.Kody, 3),
            self.RozliseniLinky
        ]
        return EnsureStrings(res)


class JdfZasSpoj:
    """!
    @brief Class representing departures/arrivals at a stop
    @note If one trip has multiple departures/arrivals at a stop, they differ by TC (tariff number)
    """

    def __init__(
            self,
            linka: str,
            spoj: str,
            tc: str,
            zastid: str,
            oznacnik: str,
            nastupiste: str,
            k1: str,
            k2: str,
            k3: str,
            km: str,
            prijezd: str,
            odjezd: str,
            prMin: str,
            odjMax: str,
            rozliseni: str,
    ):
        self.CisloLinky = int(linka)
        self.CisloSpoje = int(spoj)
        self.TC = int(tc)
        self.ZastID = int(zastid)
        self.Oznacnik = oznacnik
        self.Nastupiste = nastupiste
        self.Kody = [k1, k2, k3]
        self.Vzdalenost = km if km else ""
        self.Prijezd = prijezd
        self.PrijezdMin = prMin
        if prMin not in ["", NotStoppingStr.PassedStop.value, NotStoppingStr.DifferentRoute.value, " "]:
            self.Prijezd = prMin
        self.Odjezd = odjezd
        self.OdjezdMax = odjMax
        if odjMax not in ["", NotStoppingStr.PassedStop.value, NotStoppingStr.DifferentRoute.value, " "]:
            self.Odjezd = odjMax
        self.RozliseniLinky = int(rozliseni)

        self.Zastavka = None

    def Bind(self, zasLinky: Dict[Tuple[int, int, int], JdfZasLinka]):
        """!
        @brief Create a reference to a JdfZasLinka object
        @param zasLinky: Dictionary of JdfZasLinka objects with key by stop on a line
        """
        zl = zasLinky[(self.CisloLinky, self.RozliseniLinky, self.TC)]
        self.Zastavka = zl.Zastavka

    def BindCodes(self, dictKody: Dict[str, "JdfPevnyKod"]):
        """!
        @brief Decode the notes for this stop
        """
        self.Kody = [dictKody[k] for k in self.Kody if k]

    def AddTo(
            self, dictZasSpojeColl: Dict[Tuple[int, int, int], List["JdfZasSpoj"]]
    ):  # Prida spoj do seznamu v prislusnem slovniku, resp. vytvori novy seznam s timto spojem
        """!
        @brief Add the D/A to a list of trip's stops
        @param dictZasSpojeColl Dictionary of lists of D/A per trip
        """
        key = (self.CisloLinky, self.RozliseniLinky, self.CisloSpoje)
        coll = dictZasSpojeColl.get(key)
        if not coll:
            dictZasSpojeColl[key] = [self]
        else:
            coll.append(self)

    def FormatTime(self):
        """!
        @brief Format the time of departure/arrival (from HHMM to minutes)
        """
        self.Prijezd = ParseHM(self.Prijezd)
        self.Odjezd = ParseHM(self.Odjezd)
        return

    def GetID(self) -> Tuple[int, int, int, int]:
        """!
        @brief Get the ID of the D/A
        """
        return self.CisloLinky, self.RozliseniLinky, self.CisloSpoje, self.TC

    def __hash__(self) -> int:
        return hash(self.GetID())

    def __eq__(self, other) -> bool:
        return self.GetID() == other.GetID()

    def Serialize(self) -> List[str]:
        """!
        @brief Serialize the D/A into a row in CSV
        @return: List of strings representing the D/A
        """
        res = [
            str(self.CisloLinky).zfill(6), self.CisloSpoje, self.TC, self.ZastID,
            self.Oznacnik, self.Nastupiste,
            *UnpackCodes(self.Kody, 3),
            self.Vzdalenost, SplitToHHMM(self.Prijezd).replace(":", ""), SplitToHHMM(self.Odjezd).replace(":", ""),
            self.PrijezdMin, self.OdjezdMax,
            self.RozliseniLinky
        ]
        return EnsureStrings(res)


class JdfCasKod:
    """!
    @brief Class representing a "time code" - characterization of a trip, including time restrictions
    """
    allowedSigns = ["O", "[", "p", "T", "!"]

    def __init__(
            self,
            linka: str, spoj: str,
            cislo: str, oznaceni: str, typ: str,
            datumOd: str, datumDo: str,
            poznamka: str, rozliseni: str
    ):
        self.CisloLinky = int(linka)
        self.RozliseniLinky = int(rozliseni)
        self.CisloSpoje = int(spoj)
        self.PoradoveCislo = int(cislo)
        self.Znacka = oznaceni  # plati jak pro negativní značku (10-99), tak pro spoje typu "podmínečné" atd (O,p,!...)
        if typ:
            typ = int(typ)
            if not (1 <= typ <= 8):
                raise ValueError(f"Neplatny typ casoveho kodu ({typ})")
            self.Znacka = int(self.Znacka)
            if not (10 <= self.Znacka <= 99):
                raise ValueError(f"Neplatne cislo pro negativni znacku ({self.Znacka})")
        else:
            if self.Znacka not in JdfCasKod.allowedSigns:
                raise ValueError(f"Neplatna znacka casoveho kodu ({self.Znacka})")
        self.Typ = typ
        self.DatumOd = datumOd
        self.DatumDo = datumDo
        self.Poznamka = poznamka

    @staticmethod
    def CreateMock(typ: str, dateFrom: str, dateTo: Optional[str] = "") -> "JdfCasKod":
        """!
        @brief Create a mock time code for testing
        @param typ: Type of restriction
        @param dateFrom: Start date of restriction
        @param dateTo: End date of restriction (unused if the restriction covers only one date)
        @return Time code with one restriction type
        """
        mock = JdfCasKod(0, 0, 0, 99, typ, dateFrom, dateTo, "", 0)
        return mock

    def AddTo(self, dictColl: Dict[Tuple[int, int, int], List["JdfCasKod"]]):
        """!
        @brief Add the time code to a list of trip's time codes
        @param dictColl Dictionary of lists of time codes per trip
        """
        key = (self.CisloLinky, self.RozliseniLinky, self.CisloSpoje)
        coll = dictColl.get(key)
        if not coll:
            dictColl[key] = [self]
        else:
            coll.append(self)

    def GetID(self) -> Tuple[int, int, int, int]:
        """!
        @brief Get the ID of the time code
        @return Tuple of line number, line version, trip number, time code number
        """
        return (
            self.CisloLinky,
            self.RozliseniLinky,
            self.CisloSpoje,
            self.PoradoveCislo,
        )

    def __hash__(self) -> int:
        return hash(self.GetID())

    def Serialize(self) -> List[str]:
        res = [
            str(self.CisloLinky).zfill(6), self.CisloSpoje, self.PoradoveCislo,
            self.Znacka, self.Typ,
            self.DatumOd, self.DatumDo,
            self.Poznamka, self.RozliseniLinky
        ]
        return EnsureStrings(res)


"""!\cond"""


class JdfNavaznost:
    def __init__(
            self,
            typ,
            linka,
            spoj,
            tc,
            prestLinka,
            zast,
            oznacnik,
            konZast,
            konOznacnik,
            cas,
            poznamka,
            rozliseni,
    ):
        if typ == "m":
            self.Typ = False
        elif typ == "M":
            self.Typ = True
        else:
            raise Exception("Chybny typ navaznosti")

        self.CisloLinky = int(linka)
        self.RozliseniLinky = int(rozliseni)
        self.CisloSpoje = int(spoj)
        self.TC = int(tc)
        self.PrestupniLinka = int(prestLinka) if prestLinka else -1
        self.PrestupniZastavka = int(zast) if zast else -1
        self.Oznacnik = oznacnik
        self.VychKonZastavka = int(konZast) if konZast else -1
        self.VychKonOznacnik = konOznacnik
        self.CasCekani = int(cas) if cas else ""
        self.Poznamka = poznamka

    def GetID(self):
        return (
            self.CisloLinky,
            self.RozliseniLinky,
            self.CisloSpoje,
            self.TC,
            self.PrestupniLinka,
            self.Poznamka,
        )

    def Serialize(self) -> List[str]:
        res = [
            self.Typ, str(self.CisloLinky).zfill(6), self.CisloSpoje, self.TC,
            self.PrestupniLinka, self.PrestupniZastavka, self.Oznacnik, self.VychKonZastavka, self.VychKonOznacnik,
            self.CasCekani, self.Poznamka, self.RozliseniLinky
        ]
        return EnsureStrings(res)


"""!\endcond"""

"""!\cond"""


class JdfAlternDopravce:
    ArgCount = 15
    ReserveIndex = 10

    def __init__(
            self,
            linka,
            spoj,
            ic,
            k1,
            k2,
            k3,
            k4,
            k5,
            k6,
            typKodu,
            rezerva,
            datOd,
            datDo,
            rozlisD,
            rozlisL,
    ):
        self.CisloLinky = int(linka)
        self.RozliseniLinky = int(rozlisL)
        self.CisloSpoje = int(spoj)
        self.DopravceIC = ic
        self.RozliseniDopravce = int(rozlisD)
        self.Kody = [k1, k2, k3, k4, k5, k6]
        self.TypCasKodu = typKodu
        self.DatumOd = datOd
        self.DatumDo = datDo
        self.Rezerva = rezerva

        self.Dopravce = None

    def Bind(self, dopravci):
        doprID = (self.DopravceIC, self.RozliseniDopravce)
        self.Dopravce = dopravci[doprID]

    def BindCodes(self, dictKody):
        self.Kody = [dictKody[k] for k in self.Kody if k]

    # altdopColl: Line -> Trip -> Altdop[]
    def AddTo(self, altdopColl):
        lineKey = (self.CisloLinky, self.RozliseniLinky)
        tripKey = self.CisloSpoje
        lineColl = altdopColl.get(lineKey)
        if not lineColl:
            lineColl = {}
            altdopColl[lineKey] = lineColl
        tripColl = lineColl.get(tripKey)
        if not tripColl:
            lineColl[tripKey] = [self]
        else:
            tripColl.append(self)

    def GetID(self):
        return (
            self.CisloLinky,
            self.RozliseniLinky,
            self.DopravceIC,
            self.RozliseniDopravce,
            self.DatumOd,
            self.DatumDo,
        )

    def Serialize(self) -> List[str]:
        """!
        @brief Serialize the Altdop to a CSV row
        @return List of strings
        """
        res = [
            str(self.CisloLinky).zfill(6), self.CisloSpoje, self.DopravceIC,
            *UnpackCodes(self.Kody, 6),
            self.TypCasKodu, self.Rezerva, self.DatumOd, self.DatumDo,
            self.RozliseniDopravce, self.RozliseniLinky
        ]
        return EnsureStrings(res)


"""!\endcond"""


class CasovyKod:
    """!
    @brief A class representing restriction-like time code without any JDF-ballast
    """

    def __init__(self, typ: int, validFrom: str, validTo: Optional[str] = None):
        self.Type = int(typ)
        self.From = validFrom
        self.To = validTo


class CasovaZnacka:
    """!
    @brief A class representing a restriction sign; collection of time-code restrictions under a double-digit code
    """

    def __init__(self, cislo):
        cislo = int(cislo)
        if 10 <= cislo <= 99:
            self.CisloZnacky = cislo
        else:
            raise ValueError(f"Nepovolene cislo negativni znacky ({cislo})")

        self.Omezeni = [None, [], [], [], [], False, False, [], []]
        self.BezOmezeni = True

    def __repr__(self) -> str:
        return str(self.CisloZnacky)

    # Ve specifikaci JDF nelze uvést některé kombinace typů omezení.
    # Nicméně tentýž typ je vždy možno uvést vícekrát, jelikož každé jednotlivé omezení je definováno jako 1 day nebo rozsah mezi 2 dny.
    NepovoleneKombinace = [
        None,  # so we have 1-based array
        [7, 8],
        [],
        [1, 2, 4, 5, 6, 7, 8],
        [],
        [6, 7, 8],
        [5, 7, 8],
        [5, 6, 8],
        [5, 6, 7],
    ]

    def ZkontrolujNepovoleneKombinace(self, typ: int):  # Předpokládá se, že typ časové značky je platný
        """!
        @brief Checks if the sign does not have conflicting types of restrictions
        @throws ValueError if the sign has conflicting types of restrictions
        """
        nepovoleneTypy = CasovaZnacka.NepovoleneKombinace[typ]
        for d in nepovoleneTypy:
            if self.Omezeni[d]:
                raise ValueError(
                    f"Neplatna kombinace casoveho kodu (existujici:{d}, pridany:{typ})"
                )
        return True

    def PridejOmezeni(self, casovyKod: JdfCasKod):
        """!
        @brief Adds a restriction to the sign
        @param casovyKod A time code to be added
        @throws ValueError if the time code is in conflict with other restrictions
        @throws ValueError if the time code is not a restriction
        @throws ValueError if the time code has no date specified
        """

        typ = casovyKod.Typ
        if not typ:
            raise ValueError("CodeSign nema typ")
        datum1 = casovyKod.DatumOd
        datum2 = casovyKod.DatumDo

        self.ZkontrolujNepovoleneKombinace(typ)

        self.BezOmezeni = False
        if typ == TypCasovehoKodu.LicheTydny or typ == TypCasovehoKodu.SudeTydny:
            self.Omezeni[typ] = True
            return

        if (not datum1) and (not datum2):
            raise ValueError(f"Datum nebylo specifikovano ({typ})")
        elif not datum1:
            datum1 = datum2
        elif not datum2:
            datum2 = datum1

        datum1 = ConvertDDMMYYYY(datum1)
        datum2 = ConvertDDMMYYYY(datum2)
        if datum2 < datum1:
            datum1, datum2 = datum2, datum1

        if (
                typ == TypCasovehoKodu.JedeJen or typ == TypCasovehoKodu.JedeTake
        ):  # konkretni data: 2,3
            self.Omezeni[typ].append(datum1)
        else:  # rozsah dat: 1,4,7,8
            self.Omezeni[typ].append((datum1, datum2))

    # Následující algoritmus řeší značky bez ohledu na druh dne (jen podle data);
    # Značka 3 je unikátní - spoj buďto jede, je-li uveden nebo nejede, pokud není
    # Značka 2 platí bez ohledu na day, tedy spoj by měl v takovém případě vždy jet
    # Značka 4 vylučuje provoz ve zmíněné dny, měla by mít tedy prioritu před dalšími
    # Značka 1 omezuje rozsah provozu na určité dny, mimo tento rozsah spoje nejezdí
    # Značky 5/6 se rozhodují podle toho, zdali se jedná o sudý nebo lichý týden (pouze bool hodnota)
    # Značky 7/8 mají stejný význam jako 1+5/1+6 (a nejdou tak s nimi kombinovat)

    def DanyDenPovolen(self, den: datetime.date) -> CanOperate:
        """!
        @brief Checks if the sign allows the operation on the given day
        @param den A day to be checked
        @return CanOperate.Ano if the restriction allows explicitly
        @return CanOperate.Ne if the restriction forbids explicitly
        @return CanOperate.Maybe if the day is not in a conflict with the restriction
        @note Does not check a type of day (weekday/weekend) and neither the timetable validity
        """
        if (
                not self.Omezeni
        ):  # Zefektivneni branchingu pro pripad, kdy spoje nemaji negativni znacku (kterych je dost)
            return CanOperate.Maybe

        zk = self.Omezeni[TypCasovehoKodu.JedeJen.value]
        if zk:
            if den in zk:
                return CanOperate.Surely
            else:
                return CanOperate.Restricted

        zk = self.Omezeni[TypCasovehoKodu.JedeTake.value]
        if den in zk:
            return CanOperate.Surely

        zk = self.Omezeni[TypCasovehoKodu.Nejede.value]
        for rozsah in zk:
            if BetweenDates(den, rozsah):
                return CanOperate.Restricted

        zk = self.Omezeni[TypCasovehoKodu.Jede.value]
        if zk and (
                not any(BetweenDates(den, rozsah) for rozsah in zk)
        ):  # pokud neni v rozsahu "jede"
            return CanOperate.Restricted

        Tyden = den.isocalendar()[1]

        if (self.Omezeni[TypCasovehoKodu.LicheTydny] and (Tyden % 2 != 1)) or (
                self.Omezeni[TypCasovehoKodu.SudeTydny] and (Tyden % 2 != 0)
        ):
            return CanOperate.Restricted

        zk = self.Omezeni[TypCasovehoKodu.LicheTydnyOdDo]
        if zk:
            if not IsOdd(Tyden):
                return CanOperate.Restricted
            elif not any(BetweenDates(den, rozsah) for rozsah in zk):
                return CanOperate.Restricted

        zk = self.Omezeni[TypCasovehoKodu.SudeTydnyOdDo]
        if zk:
            if not IsEven(Tyden):
                return CanOperate.Restricted
            elif not any(BetweenDates(den, rozsah) for rozsah in zk):
                return CanOperate.Restricted

        return CanOperate.Maybe

def IsLineValid(datum: datetime.date, line: JdfLinka, allLines: Optional[Dict[Tuple[int, int], JdfLinka]] = None) -> bool:
    """!
    @brief Checks if a line is valid on a given day
    @param datum A day to be checked
    @param line A line to be checked
    @param allLines A dictionary of all lines (optional) to check for a different version
    """
    if not BetweenDates(datum, (line.ValidFrom, line.ValidTo)):
        return False
    if allLines and line.VersionValidByDate(allLines, datum) != line.RozliseniLinky:
        return False
    return True


def IsTripOperated(datum: datetime.date, trip: JdfSpoj, allLines: Optional[Dict[Tuple[int, int], JdfLinka]] = None):
    """!
    @brief Checks if a trip operates on a given day
    @param datum A day to be checked
    @param trip A trip to be checked
    @param allLines A dictionary of lines (optional)
    @return Whether a trip operates. Considers all restrictions as well as timetable validity and type of day.
    """
    line: JdfLinka
    line = trip.Line
    # check line duration
    if not IsLineValid(datum, line, allLines):
        return False
    return trip.JedeVDen(datum)


"""!\cond"""


def CreateMockTrip(
        linka,
        rozliseni,
        cislo,
        dnyprovozu,
        caskody: List[JdfCasKod],
        platnostOd,
        platnostDo,
):
    trip = JdfSpoj(linka, cislo, "", "", "", "", "", "", "", "", "", "", "", rozliseni)
    trip.TimeSign = None
    trip.OperatingDays = dnyprovozu
    trip.TimeCodes = caskody
    trip.CompressTimeCodes()
    trip.Line = type("linka", (), {})
    trip.Line.PlatnostOd = ConvertDDMMYYYY(platnostOd)
    trip.Line.PlatnostDo = ConvertDDMMYYYY(platnostDo)
    return trip


"""!\endcond"""


def UnpackCodes(kody: List[JdfPevnyKod], length: int) -> List[Union[int, str]]:
    """!
    @brief Pads a list of PevneKody to a given length, unpacks and returns list of code numbers
    """
    unpadded = [k.CodeNumber for k in kody]
    return unpadded + ([""] * (length - len(unpadded)))
