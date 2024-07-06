#!/usr/bin/env python

"""!
@file StopOrdering.py
@namespace StopOrdering
@brief This file contains functions for ordering stops in a timetable
"""
import json
from typing import List, Any, TextIO, Dict, Tuple


def FindLongestCommonSubsequence(list1: List[Any], list2: List[Any]) -> List[Any]:
    """!
    @brief Find longest common subsequence of two lists
    @param list1 First list
    @param list2 Second list
    @return Longest common subsequence expressed as a list
    """
    if len(list1) == 0 or len(list2) == 0:
        return []
    for i, element in enumerate(list1):
        if element in list2:
            return [element] + FindLongestCommonSubsequence(list1[i + 1:], list2[list2.index(element) + 1:])
    return []

def CheckForSuperSequence(list1: List[Any], list2: List[Any]) -> bool:
    """!
    @brief Check if list1 is a supersequence of list2
    @param list1 First list
    @param list2 Second list
    @return True if list1 is a supersequence of list2
    """
    lcs = FindLongestCommonSubsequence(list1, list2)
    return len(lcs) == len(list2)

def FindSubsequenceRemainder(sequence: List[Any], subsequence: List[Any]) -> List[Any]:
    """!
    @brief Find remainder of a sequence after removing a subsequence
    @param sequence List of elements
    @param subsequence Subsequence to be removed
    @return Remainder of the sequence
    """
    if len(subsequence) == 0:
        return sequence
    if len(sequence) == 0:
        return []
    result = []
    i = 0
    for j, element in enumerate(sequence):
        if element == subsequence[i]:
            i += 1
            if i == len(subsequence):
                result += sequence[j + 1:]
                break
        else:
            result.append(element)
    return result


def MergeBidirectionalTimetable(someForward: List[str],someBackward: List[str],
                                 stopsForward: List[str]= [], stopsBackward: List[str] = []) -> List[Any]:
    """!
    @brief Merge two timetables with stops in opposite directions
    @param stopsForward List of stops in forward direction
    @param stopsBackward List of stops in backward direction
    @param someBackward: List of "main" stops in forward direction
    @param someForward: List of "main" stops in backward direction
    @return List of stops in merged timetable
    """
    assert len(FindLongestCommonSubsequence(stopsForward, someForward)) == min(len(stopsForward), len(someForward))
    assert len(FindLongestCommonSubsequence(stopsBackward, someBackward)) == min(len(stopsBackward), len(someBackward))

    # Inefficient but correct
    if not stopsForward:
        stopsForward =someForward
    if not stopsBackward:
        stopsBackward = someBackward



    stopsBackward = stopsBackward[::-1]
    someBackward = someBackward[::-1]

    # Encoding the stop attributes
    Forward = 1
    Backward = 2
    ForwardOcc = 3
    BackwardOcc = 4

    lcs = FindLongestCommonSubsequence(stopsForward, stopsBackward)
    fi = 0
    bi = 0
    merged = []
    for stop in lcs:
        while stopsForward[fi] != stop:
            merged.append((stopsForward[fi], True, False, True, False))
            fi += 1
        while stopsBackward[bi] != stop:
            merged.append((stopsBackward[bi], False, True, False, True))
            bi += 1
        merged.append((stop, True, True, True, True))
        fi += 1
        bi += 1
    while fi < len(stopsForward):
        merged.append((stopsForward[fi], True, False, True, False))
        fi += 1
    while bi < len(stopsBackward):
        merged.append((stopsBackward[bi], False, True, False, True))
        bi += 1

    # The result now treats all stops as occasional; if they are backed-up with the "some" list of stops, they will be marked as regular
    i = 0
    for j, stop in enumerate(someForward):
        while merged[i][0] != stop:
            i += 1
        m = list(merged[i])
        m[ForwardOcc] = False
        merged[i] = tuple(m)

    i = 0
    for j, stop in enumerate(someBackward):
        while merged[i][0] != stop:
            i += 1
        m = list(merged[i])
        m[BackwardOcc] = False
        merged[i] = tuple(m)
    result = [RenderStop(stop) for stop in merged]
    return result


def RenderStop(stop: Tuple[str, bool, bool, bool, bool]) -> str:
    """!
    @brief Render stop with appendix indicating its attributes
    @param stop Stop to be rendered
    @return Stop with added "T" for forward regular, "Z" for backward regular, "o" for occasional.
    If both T and Z exist, they get removed
    """
    name = stop[0]
    signage = []
    if stop[1] and not stop[3]:
        signage.append("T")
    if stop[2] and not stop[4]:
        signage.append("Z")
    if stop[1] and stop[3]:
        signage.append("To")
    if stop[2] and stop[4]:
        signage.append("Zo")
    if "To" in signage and "Zo" in signage:
        signage.remove("To")
        signage.remove("Zo")
        signage.append("o")
    if "T" in signage and "Z" in signage:
        signage.remove("T")
        signage.remove("Z")
    if signage:
        appendix = "(" + ",".join(signage) + ")"
    else:
        appendix = ""
    return name + appendix


def ReadTrips(f: TextIO) -> Dict[int, List[Any]]:
    """!
    @brief Read trips from json file
    @param f File object
    @return Dictionary: Line -> list of trips
    """
    result = {}
    content = json.load(f)
    for trip in content:
        lineNo = trip["Line number"]
        result.setdefault(lineNo, []).append(trip)
    return result


def SplitTripsIntoRoutes(trips: List[Any]) -> Tuple[Dict[Tuple[str, ...], int], Dict[Tuple[str, ...], int]]:
    """!
    @brief Analyze how much regular is a line by splitting trips into routes and counting such routes
    @param trips List of trips
    @return Dictionary: number of trips -> list of stops with such trip
    """
    resultF = {}
    resultB = {}
    for trip in trips:
        if trip["Trip number"] % 2 == 0:
            r = resultB
        else:
            r = resultF
        stoptimes = [k for k in trip["Zastavky"]]
        stops = tuple(list(k.keys())[0] for k in stoptimes)
        if stops in r:
            r[stops] += 1
        else:
            r[stops] = 1
    return resultF, resultB


def FindMajorRoutes(routes: Dict[Tuple, int]) -> Tuple[List[str],List[str]]:
    """!
    @brief Find major route which goes forward and backward
    @param routes Dictionary of key route (as tuple of stop names) and value frequency
    @return Main forward and main backward route
    @todo Include sub-route into larger ones (if they do not conflict in any way)
    """
    if len(routes) == 1:
        return list(list(routes.keys())[0]),[]
    res = sorted(routes.items(), key=lambda route: route[1], reverse=True)
    ret1 = res[0][0]
    ret2 = []
    # Definition of a subroute: Must have frequency at least 1/4 of the original route and be a supersequence of it
    for i, r in enumerate(res):
        if i==0:continue
        if r[1] < res[0][1] / 4:
            break
        if CheckForSuperSequence(r[0],ret1):
            ret2 = list(r[0])
            break
    return list(ret1),ret2


def main():
    tripsFileSun = "../JDF_Conversion/online_files/temp/trips_2020-01-01.json"
    with open(tripsFileSun, "r", encoding="utf-8") as f:
        lines = ReadTrips(f)
    tripsFileWed = "../JDF_Conversion/online_files/temp/trips_2020-01-06.json"
    with open(tripsFileWed, "r", encoding="utf-8") as f:
        lines2 = ReadTrips(f)
    for lineno, tripsln in lines2.items():
        if lineno in lines.keys():
            tripsA = lines[lineno]
            tripsB = tripsln
            lines[lineno] = tripsA + tripsB
        else:
            lines[lineno] = lines2[lineno]

    with open ("../SharedData/Stop_Sequences/custom.txt","w+",encoding="utf-8") as fall:
        for lineno, tripsln in sorted(lines.items()):
            splitted = SplitTripsIntoRoutes(tripsln)

            relevantF = FindMajorRoutes(splitted[0]) if splitted[0] else ([],[])
            print(relevantF)

            relevantB = FindMajorRoutes(splitted[1]) if splitted[1] else ([],[])
            print(relevantB)

            merged = MergeBidirectionalTimetable(relevantF[0], relevantB[0],relevantF[1], relevantB[1])
            outFile = f"../SharedData/Stop_Sequences/{lineno}.txt"
            with open(outFile, "w+", encoding="utf-8") as f:
                fall.write(str(lineno))
                fall.write("\n\n")
                for m in merged:
                    f.write(m)
                    f.write("\n")
                f.flush()
                f.seek(0)

                fall.write(f.read())
                fall.write("\n------\n\n")

if __name__ == "__main__":
    main()
