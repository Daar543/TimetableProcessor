#!/usr/bin/env python3

"""!
@file Utilities.py
@namespace Utilities
@brief  Various utilities for the JDF_Conversion project, not specific to timetables
"""

import datetime
import pathlib
import re
from typing import Tuple, List, Union, Dict, Optional, Any, Iterable, Callable
import unicodedata

import czech_holidays
import numpy as np

from JDF_Conversion.Timetable_Enums import NotStopping, NotStoppingStr

DAYMINS: int = 24 * 60


def IsEven(value: int) -> bool:
    """!
    @brief  Checks if the value is even
    @param  value: int
    @return True if the value is even, False otherwise
    """
    return value % 2 == 0


def IsOdd(value: int) -> bool:
    """!
    @brief  Checks if the value is odd
    @param  value: int
    @return True if the value is odd, False otherwise
    """
    return not IsEven(value)


def ParseHM(hhmm: Union[str, NotStoppingStr]) -> int:
    """!
    @brief Parses a string in the format HHMM into minutes.
    @brief Also supports timetable special values (for stop being not served)
    @param hhmm: Hours and minutes in the format HHMM, or "", "<", "|"
    @return Minutes, or negative values for special values
    @throws ValueError if the string cannot be parsed as (valid) hours and minutes
    """
    if hhmm == NotStoppingStr.UnusedStop.value:
        return NotStopping.UnusedStop.value
    elif hhmm == NotStoppingStr.DifferentRoute.value:
        return NotStopping.DifferentRoute.value
    elif hhmm == NotStoppingStr.PassedStop.value:
        return NotStopping.PassedStop.value
    hh = int(hhmm[:-2])
    mm = int(hhmm[-2:])
    if not (0 <= hh < 24):
        raise ValueError("More than 23 hours")
    if not (0 <= mm < 60):
        raise ValueError("More than 60 minutes")
    return 60 * hh + mm


def ParseHMColon(hhmm: str) -> int:
    """!
    @brief Parses a string in the format HH:MM into minutes.
    @brief Also supports timetable special values (for stop being not served)
    @param hhmm: Hours and minutes in the format HH:MM, or "", "<", "|"
    @return Minutes, or negative values for special values
    @throws ValueError if the string cannot be parsed as (valid) hours and minutes
    """
    if hhmm == NotStoppingStr.UnusedStop.value:
        return NotStopping.UnusedStop.value
    elif hhmm == NotStoppingStr.DifferentRoute.value:
        return NotStopping.DifferentRoute.value
    elif hhmm == NotStoppingStr.PassedStop.value:
        return NotStopping.PassedStop.value
    hh, mm = hhmm.split(":")
    hh = int(hh)
    mm = int(mm)
    if not (0 <= hh < 24):
        raise ValueError("More than 23 hours")
    if not (0 <= mm < 60):
        raise ValueError("More than 60 minutes")
    return 60 * hh + mm


def SplitToHHMM(mins: int) -> str:
    """!
    @brief  Splits minutes into hours and minutes
    @brief Also supports timetable special values (for stop being not served) put as negative values
    @param  mins: Minutes (from 0 to 1439) or -1, -2, -3
    @return Tuple of hours and minutes
    """
    if mins == NotStopping.UnusedStop.value:
        return NotStoppingStr.UnusedStop.value
    elif mins == NotStopping.DifferentRoute.value:
        return NotStoppingStr.DifferentRoute.value
    elif mins == NotStopping.PassedStop.value:
        return NotStoppingStr.PassedStop.value
    hh, mm = divmod(mins, 60)
    return str(hh).rjust(2, "0") + ":" + str(mm).rjust(2, "0")


def ConvertDDMMYYYY(ddmmyyyy: str) -> datetime.date:
    """!
    @brief  Converts a date in the format DDMMYYYY to datetime object
    @param  ddmmyyyy: Date in the format DDMMYYYY, e.g. 01012020
    @return datetime.date object
    @throws ValueError if the date cannot be parsed
    """
    return datetime.datetime.strptime(ddmmyyyy, "%d%m%Y").date()


def ConvertToDDMMYYYY(date: Union[datetime.date, datetime.datetime]) -> str:
    """!
    @brief Converts datetime object to date
    in form DDMMYYYY
    """
    return date.strftime("%d%m%Y")


def BetweenDates(checkedDate: datetime.date, limitingDates: Tuple[datetime.date, datetime.date]) -> bool:
    """!
    @brief  Checks if the checkedDate is between the limitingDates (inclusive)
    @param  checkedDate: Date to be checked
    @param  limitingDates: Tuple of two dates, the first one is the lower limit, the second one is the upper limit
    @return True if the checkedDate is between the limitingDates, False otherwise
    """

    d1, d2 = limitingDates
    return d1 <= checkedDate <= d2


class VypocetSvatku:
    """!
    @brief  Class for checking if a date is a (Czech) holiday
    @note The list of holidays is taken from the czech_holidays package and is cached
    """
    ulozeneSvatky = {}  # Cache of holidays

    @staticmethod
    def JeSvatek(datum: datetime.date):  # nedele se nepočítají
        """!
        @brief  Checks if the date is a holiday (being Sunday if not a sufficient condition)
        @param  datum: Date to be checked
        @return True if the date is a Czech national holiday, False otherwise
        """
        rok = datum.year
        svatky = VypocetSvatku.ulozeneSvatky.get(rok)
        if not svatky:
            svatky = czech_holidays.czech_holidays(rok)
            svatky = [sv[0] for sv in svatky]
            VypocetSvatku.ulozeneSvatky[rok] = svatky
        return datum in svatky

    @staticmethod
    def JePracovniDen(datum: datetime.date):
        """!
        @brief  Checks if the date is a working day (Monday to Friday and not a holiday)
        @param  datum: Date to be checked
        @return False if the date is a weekend or a holiday, True otherwise
        """
        den = datum.isocalendar()[2]
        return not (
                den == 6 or den == 7 or VypocetSvatku.JeSvatek(datum)
        )  # neni so/ne/svatek


def FloydWarshallFastest(adjacencyMatrix: np.ndarray) -> np.ndarray:
    """!
    @brief  Computes the shortest path between all pairs of nodes in a graph
    @param  adjacencyMatrix: An NxN NumPy array describing the directed distances between N nodes.
    @return An NxN NumPy array such that result[i,j] is the shortest distance to travel between node i and node j.
    If no such path exists then result[i,j] == numpy.inf
    @note Author: Amit Moscovich Eiger https://gist.github.com/mosco/11178777
    @note If there is no edge connecting i->j then adjacency_matrix[i,j] should be equal to numpy.inf.
    @note The diagonal of adjacency_matrix should be zero.
    """
    # Amit Moscovich Eiger, 22/4/2014.
    """floyd_warshall_fastest(adjacency_matrix) -> shortest_path_distance_matrix

    Input
        An NxN NumPy array describing the directed distances between N nodes.

        adjacency_matrix[i,j] = distance to travel directly from node i to node j (without passing through other nodes)

        Notes:
        * If there is no edge connecting i->j then adjacency_matrix[i,j] should be equal to numpy.inf.
        * The diagonal of adjacency_matrix should be zero.

    Output
        An NxN NumPy array such that result[i,j] is the shortest distance to travel between node i and node j.
        If no such path exists then result[i,j] == numpy.inf
    """
    (mat, n) = CheckAndConvertAdjMatrix(adjacencyMatrix)

    for k in range(n):
        # if(k%32==0):
        #   print(f"{k}/{n}")
        mat = np.minimum(mat, mat[np.newaxis, k, :] + mat[:, k, np.newaxis])

    return mat


def CheckAndConvertAdjMatrix(adjacencyMatrix: Union[np.ndarray, List[List[int]]]) -> Tuple[np.ndarray, int]:
    """!
    @brief  Checks if the adjacency matrix is valid and converts it to NumPy array
    @param  adjacencyMatrix: Adjacency matrix as numpy array, 16-bit integer, or list of lists
    @return Tuple of NumPy array and number of rows
    @throws AssertionError if the adjacency matrix does not have zero diagonal
    @note Author: Amit Moscovich Eiger https://gist.github.com/mosco/11178777
    """

    mat = np.asarray(adjacencyMatrix, dtype="int16")

    (nrows, ncols) = mat.shape
    assert nrows == ncols
    n = nrows

    assert (np.diagonal(mat) == 0.0).all()

    return (mat, n)


def SymmetrizeDM(matrix: Union[np.ndarray, List[List[int]]]) -> Union[np.ndarray, List[List[int]]]:
    """!
    @brief  Symmetrizes an adjacency (distance) matrix
    @param  matrix: Adjacency matrix
    @return Symmetrized adjacency matrix
    """
    for i in range(len(matrix)):
        for j in range(len(matrix)):
            matrix[i, j] = min(matrix[i, j], matrix[j, i])
    return matrix


def InFile(text: str, file: str, encod: Optional[str] = None, ignoreNonexistent: bool = True) -> bool:
    """!
    @brief  Checks if the text is in the file
    @param  text: Text to be searched for
    @param  file: File to be searched in
    @param  encod: Encoding of the file
    @param  ignoreNonexistent: If True, the function will not throw
    @return True if the text is in the file, False otherwise
    @throws FileNotFoundError if the file does not exist and ignoreNonexistent is False
    """
    try:
        with open(file, "r", encoding=encod, errors="replace") as f:
            return text in f.read()
    except FileNotFoundError:
        if ignoreNonexistent:
            return False
        else:
            raise


def InFileRE(regexp: re.Pattern, file: str, encod: Optional[str] = None, ignoreNonexistent: bool = True) -> bool:
    """!
    @brief  Checks if the regular expression matches a text in the file
    @param  regexp: Regular expression to be searched for
    @param  file: File to be searched in
    @param  encod: Encoding of the file
    @param  ignoreNonexistent: If True, the function will not throw
    @return True if the regular expression matches a text in the file, False otherwise
    @throws FileNotFoundError if the file does not exist and ignoreNonexistent is False
    """
    try:
        with open(file, "r", encoding=encod, errors="replace") as f:
            return bool(regexp.search(f.read()))
    except FileNotFoundError:
        if ignoreNonexistent:
            return False
        else:
            raise


def progressBar(iterable: Iterable[Any], prefix: str = '', suffix: str = '', decimals: int = 1, length: int = 100,
                fill: str = '█', printEnd: str = "\r"):
    """!
    @brief  Call in a loop to create a progress bar to be shown on a terminal
    @param  iterable: Iterable to be iterated over
    @param  prefix: Prefix string
    @param  suffix: Suffix string
    @param  decimals: Positive number of decimals in percent complete
    @param  length: Character length of bar
    @param  fill: Bar fill character
    @param  printEnd: End character (e.g. "\\r", "\\r\\n")
    @author https://stackoverflow.com/users/2206251/greenstick
    @note Original code: https://stackoverflow.com/questions/3173320/text-progress-bar-in-terminal-with-block-characters?noredirect=1&lq=1
    @summary Example usage: for i, item in enumerate(progressBar(myList, 'Progress:', 'Complete', 1, 50)): doSomething(item)
    """
    total = len(iterable)
    if total == 0:
        return

    # Progress Bar Printing Function
    def printProgressBar(iteration):
        percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
        filledLength = int(length * iteration // total)
        bar = fill * filledLength + '-' * (length - filledLength)
        print(f'\r{prefix} |{bar}| {percent}% {suffix}', end=printEnd)

    # Initial Call
    printProgressBar(0)
    # Update Progress Bar
    for i, item in enumerate(iterable):
        yield item
        printProgressBar(i + 1)
    # Print New Line on Complete
    print()


def EnsureStrings(l: List[Any]) -> List[str]:
    """!
    @brief  Ensures that all elements of a list are strings
    @param  List: List to be checked
    @return List with all elements converted to strings
    """
    return ["" if e is None else str(e) for e in l]


def BoolToNumeric(b: bool) -> str:
    """!
    @brief  Converts a boolean to a numeric string
    @param  b: Boolean to be converted
    @return "1" if b is True, "0" otherwise
    """
    return "1" if b else "0"


def IsNum(s: Any) -> bool:
    """!
    @brief Checks if a string can be converted to number
    @param s Testing value
    @return True if value can be converted, False otherwise
    """
    try:
        num = int(s)
    except (ValueError, TypeError):
        return False
    return True


def Slugify(value, allow_unicode=True):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    value.replace("/", "_")
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')


def RemoveDirectoryMarks(s: str) -> str:
    """!
    @brief  Removes forbidden directory marks from a string, replacing them with underscores
    @param  s: String to be cleaned
    @return Cleaned string
    """
    return (s.replace("..", "_")
            .replace(".", "_")
            .replace("/", "_")
            .replace("\\", "_")
            .replace(":", "_")
            .replace("*", "_")
            .replace("?", "_")
            .replace("\"", "_")
            .replace("<", "_")
            .replace(">", "_")
            .replace("|", "_"))


def CreateBuckets(items: Iterable[Any], fn: Callable) -> Dict[Any, List[Any]]:
    """!
    @brief  Creates buckets of items based on a function
    @param  items: Items to be bucketed
    @param  fn: Function to be used for bucketing
    @return Dictionary of buckets
    """
    buckets = {}
    for item in items:
        key = fn(item)
        if key not in buckets:
            buckets[key] = []
        buckets[key].append(item)
    return buckets


def IsEmptyStoppingTime(t: Optional[str]) -> bool:
    """!
    @brief  Checks if the value is one of the ones marking "not stopping"
    @param  t: Value to be checked
    @return True if the value is NotStoppingStr or None,otherwise False
    """
    return t in [
        None,
        "",
        NotStoppingStr.UnusedStop,
        NotStoppingStr.PassedStop,
        NotStoppingStr.DifferentRoute
    ]


def GetSubFolders(path: pathlib.Path) -> List[pathlib.Path]:
    """!
    @brief  Gets all shallow subfolders of a folder
    @param  path: Path to the folder
    @return List of subfolders
    """
    # Do not return anything if the path does not exist or is not a directory
    if not path.is_dir():
        return []
    return [f for f in path.iterdir() if f.is_dir()]
