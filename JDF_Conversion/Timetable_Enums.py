#!/usr/bin/env python3

"""!
@file Timetable_Enums.py
@namespace Timetable_Enums
@brief Enums for timetables
"""

from enum import Enum, IntEnum


class PevneKody(Enum):
    """!
    @brief Enum for various notes in timetables
    """

    # Mon-Sun
    Po = "1"
    Ut = "2"
    St = "3"
    Ct = "4"
    Pa = "5"
    So = "6"
    Ne = "7"

    PracovniDny = "X"  # Workdays
    Svatky = "+"  # Holidays+Sundays

    NaZnameni = "x"  # Request stop
    NaObjednani = "T"  # Trip must be pre-ordered
    Podminene = "!"  # Conditional trip

    Projizdi = "|"  # Does not stop at
    JinaTrasa = "<"  # Does not go through

    Vystup = "("  # Exit only
    Nastup = ")"  # Boarding only

    Mistenka = "R"  # Seat can be reserved
    PovinnaMistenka = "#"  # Seat has to be reserved

    Bezbarierovy = "@"  # Low floor
    CastecneBezbarierovy = "{"  # Low entry
    ProNevidome = "}"  # Help for visually impaired
    ProVozickare = "t"  # Help for physically disabled

    WC = "W"
    BezbWC = "w"
    Obcerstveni = "%"  # Restaurant

    # Transfer to
    MHD = "~"  # Local transport
    PrestupVlak = "v"  # Trains
    PrestupBus = "b"  # Large bus terminal
    PrestupMetro = "U"  # Underground
    PrestupLod = "S"  # Ferry
    PrestupLetadlo = "L"  # Plane
    ParkAndRide = "P"  # Parking

    # Cannot sell ticket for these relations
    Paragraf = "§"
    Paragraf1 = "A"
    Paragraf2 = "B"
    Paragraf3 = "C"

    Clo = "$"  # State borders, boarding not allowed

    PrepravaZavazadel = "["  # Luggage transport supported
    PrepravaKol = "O"  # Bike transport supported


class Prostredek(Enum):
    """!
    @brief Enum for transport vehicles
    """
    Autobus = "A"
    Tramvaj = "E"
    Lanovka = "L"
    Metro = "M"
    Lod = "P"
    Trolejbus = "T"


class TypLinky(Enum):
    """!
    @brief Enum for line types (usually regarding tariff and distance)
    """
    Mestska = "A"
    Primestska = "B"
    Regionalni = "V"
    Mezikrajska = "Z"
    Dalkova = "D"
    MezinarodniVnitrostatni = "P"
    Mezinarodni = "N"


class TypCasovehoKodu(IntEnum):
    """!
    @brief Enum for operating specifications (whether the trip is served or not) - time codes
    """
    Jede = 1
    JedeTake = 2
    JedeJen = 3
    Nejede = 4
    LicheTydny = 5
    SudeTydny = 6
    LicheTydnyOdDo = 7
    SudeTydnyOdDo = 8

    def __eq__(self, other):
        return self.value == other


class DnyProvozu(Enum):
    """!
    @brief Enum for days of operation
    """
    Pondeli = "1"
    Utery = "2"
    Streda = "3"
    Ctvrtek = "4"
    Patek = "5"
    Sobota = "6"
    Nedele = "7"
    PracovniDny = "X"
    Svatky = "+"


class CanOperate(Enum):
    """!
    @brief Enum for determining the result of time codes (see TypCasovehoKodu) compared to a queried date
    """
    Restricted = 0  # contradicts restrictive sign
    Maybe = 1  # depends on type of day (workday, weekend)
    Surely = 2  # JedeJen/JedeTake

class OperationalPeriodType(IntEnum):
    Workdays = 1
    Either = 2
    Weekends = 3

class NotStopping(IntEnum):
    UnusedStop = -1
    DifferentRoute = -2
    PassedStop = -3

class NotStoppingStr(Enum):
    UnusedStop = ""
    DifferentRoute = PevneKody.JinaTrasa.value
    PassedStop = PevneKody.Projizdi.value