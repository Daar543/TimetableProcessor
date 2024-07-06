import os
import overpy
import difflib
import json
import time
from typing import List
from types import SimpleNamespace


def FindDetailsOfStops(stopNames: List[str], stopList: List, cutoff=0.5) -> List[str]:
    stops = []
    stopList = [stop for stop in stopList if GetNameOfStopNode(stop)]  # Filter stops not having name
    officialNames = [GetNameOfStopNode(stop) for stop in stopList]
    assert (not (None in officialNames))

    for sn in stopNames:
        allSimilarNames = difflib.get_close_matches(sn, officialNames, cutoff=cutoff)
        if not allSimilarNames:
            print("No similar names found for", sn)
            stops.append(None)
            continue
        mostSimilar = allSimilarNames[0]
        idx = officialNames.index(mostSimilar)
        stops.append(stopList[idx])
    return stops


def Requery(datafile):
    api = overpy.Overpass()
    try:
        with open(datafile, "r+", encoding="utf-8") as f:
            simple_stops = json.load(f)
    except BaseException as ex:
        print(ex)
        pass
    ids = [str(stop["id"]) for stop in simple_stops]
    query = f"[out:json][timeout:25];(  node(id:{', '.join(ids)}););out body;"
    print("Querying ids:", query)
    stops = api.query(query).nodes
    return stops


def ConvertJson(datafile):
    with open(datafile, "r+", encoding="utf-8") as f:
        simple_stops = json.load(f, object_hook=lambda d: SimpleNamespace(**d))
    # Only converts tags back to dict
    for i in range(len(simple_stops)):
        simple_stops[i].tags = vars(simple_stops[i]).tags
    return simple_stops


def AreaTypeAdminLevel(areaType):
    if areaType == "obec":
        adminLevel = 8
    elif areaType == "kraj":
        adminLevel = 6
    elif areaType == "okres":
        adminLevel = 7
    elif areaType == "stát":
        adminLevel = 2
    else:
        raise ValueError(f"Unknown area type ({areaType})")
    return adminLevel


def FindStopsInArea(areaName, areaType, outputFile=None):
    if areaType == "obec":
        adminLevel = 8
    elif areaType == "kraj":
        adminLevel = 6
    elif areaType == "okres":
        adminLevel = 7
        if not areaName.startsWith("okres"):
            areaName = "okres " + areaName
    else:
        raise Exception(f"Unknown area type {areaType}")

    query = f"""area["name"="{areaName}"]["boundary"="administrative"]["admin_level"={adminLevel}];(node["highway"="bus_stop"](area););out body;"""
    api = overpy.Overpass()
    print("Querying:", query)
    success = False
    sleep = 0.5
    while (not success):
        try:
            stops = api.query(query).nodes
            success = True

        except:
            time.sleep(sleep)
            sleep *= 1.5

    if outputFile:
        try:
            simple_stops = [{'id': stop.id, 'lat': float(stop.lat), 'lon': float(stop.lon), 'tags': stop.tags} for stop
                            in stops]
            os.makedirs(os.path.dirname(outputFile), exist_ok=True)
            with open(outputFile, "w+", encoding="utf-8") as f:
                zdr = json.dumps(simple_stops, indent=4, ensure_ascii=False)
                f.write(zdr)
        except BaseException as ex:
            print(ex)
            pass

    return stops


def RunQuery(query: str):
    api = overpy.Overpass()
    print("Querying:\n", query)
    success = False
    sleep = 0.5
    while (not success):
        try:
            res = api.query(query).nodes
            success = True
        except KeyboardInterrupt:
            raise
        except:
            time.sleep(sleep)
            sleep *= 1.5
    return res


def ConvertJsonStopsInfo(datafile):
    with open(datafile, "r+", encoding="utf-8") as f:
        simple_stops = json.load(f)
    # Only converts tags back to dict
    names = [ni["name"] for ni in simple_stops]
    infos = [SimpleNamespace(**ni["info"]) if ni["info"] else None for ni in simple_stops]
    return {n: i for n, i in zip(names, infos)}


def ExtractTownName(stopName):
    # Basically just take the first part before comma
    # if it contains okres, then ignore it
    defaultName_okres = stopName.split("[", 2)
    defaultName = defaultName_okres[0]
    ocb = defaultName.split(",", 3)
    obec = ocb[0]
    return obec


def GetNameOfStopNode(stopNode):
    try:
        return stopNode.tags.get("official_name") or stopNode.tags.get("name") or ""
    except:
        return ""


def SortTwoLists(l1, l2):
    # Sorts both lists by l1
    l1, l2 = zip(*sorted(zip(l1, l2), key=lambda x: x[0]))
    return l1, l2


def IndexTuple(keys):
    # For each key, make a list of indices it appears on (keys are duplicate)
    d = {k: [] for k in keys}
    i = -1
    for k in keys:
        i += 1
        d[k].append(i)
    return d


def FindRespectiveStopsInfo(inputStopNames: List[str], areaNames: List[str], areaAdminLevel, outputFile, load):
    """
    fullStopNames: Full names of stops, including district (e.g. "Olomouc,,Hlavní nádraží[OL]")
    areaName: Name of the area (e.g. "Olomouc")
    areaType: Type of the area (e.g. "obec")
    throwaway: If true, stops not found in the area are mapped to None; otherwise they are mapped to centre of town
    """
    if load:
        try:
            namesInfo = ConvertJsonStopsInfo(outputFile)
        except FileNotFoundError:
            namesInfo = {}
    else:
        namesInfo = {}

    # No new data to be queried, end
    if all([ni in namesInfo for ni in inputStopNames]):
        stopInfos = [{"name": name, "info": {'id': stop.id, 'lat': float(stop.lat), 'lon': float(stop.lon),
                                             'tags': stop.tags} if stop else None} for name, stop in namesInfo.items()]
        return {si["name"]: si["info"] for si in stopInfos}

    townsMap = {}
    allAreas = "|".join(areaNames)
    print("Finding full town names")

    # First map all shortcut/mangled names to proper town names
    query_p1 = f"""(area["name"~"{allAreas}"]["boundary"="administrative"]["admin_level"="{areaAdminLevel}"];)->.searchArea;"""
    query_p2 = f"""(node["place"~"town|city|village"](area.searchArea););out body;"""

    townNodes = RunQuery("\n".join([query_p1, query_p2]))
    townNames = [tn if tn else "" for tn in [GetNameOfStopNode(t) for t in townNodes]]
    print("Town names found")
    townNames, townNodes = SortTwoLists(townNames, townNodes)

    for fullName in inputStopNames:
        townName = ExtractTownName(fullName)
        alreadyCached = townsMap.get(townName, -1)  # None is used for nonfound towns

        if alreadyCached == -1:
            closestMatches = difflib.get_close_matches(townName, townNames, cutoff=0.5)
            if closestMatches:
                actualName = closestMatches[0]
                index = townNames.index(actualName)
                townsMap[townName] = townNodes[index]

                if townName != actualName:
                    print(f"{townName} -> {actualName}")
            else:
                townsMap[townName] = None
                print(f"Could not find {townName}")

    print("Town names assigned")

    # Query all stops
    print("Querying stops in area")
    query_p1 = f"""(area["name"~"{allAreas}"]["boundary"="administrative"]["admin_level"="{areaAdminLevel}"];)->.searchArea;"""
    query_p2 = f"""(node["highway"="bus_stop"](area.searchArea););out body;"""
    foundStopNodes = RunQuery("\n".join([query_p1, query_p2]))
    foundStopNames = [sn if sn else "" for sn in [GetNameOfStopNode(t) for t in foundStopNodes]]

    foundStopNames, foundStopNodes = SortTwoLists(foundStopNames, foundStopNodes)
    foundStopTownNames = [sn.split(",")[0] for sn in foundStopNames]
    foundStopTownNames = IndexTuple(foundStopTownNames)

    print("Stop names found")
    for fullName in inputStopNames:

        if fullName in namesInfo:
            continue
        print(fullName)

        # Unpack the name parts
        defaultName_okres = fullName.split("[", 2)
        okres = defaultName_okres[1][:-1] if len(defaultName_okres) > 1 else None
        defaultName = defaultName_okres[0]

        ocb = defaultName.split(",", 3)
        townNode = townsMap.get(ocb[0])
        obecLong = townNode.tags.get("name") if townNode else ocb[0]
        obec = ocb[0]
        cast = ocb[1] if len(ocb) > 1 else ""
        blizsi = ocb[2] if len(ocb) > 2 else ""

        nazevLong = ",".join([obecLong, cast, blizsi]).rstrip(",")
        nazev = ",".join([obec, cast, blizsi]).rstrip(",")
        # Find the town name in stop list
        townStopsIdx = foundStopTownNames.get(obec)
        if not townStopsIdx:
            namesInfo[fullName] = townNode
            continue

        townStopNames = [foundStopNames[i] for i in townStopsIdx]
        townStopNodes = [foundStopNodes[i] for i in townStopsIdx]

        # High accuracy for the stop name
        closestStopName = difflib.get_close_matches(nazev, townStopNames, cutoff=0.9)
        if not closestStopName:
            closestStopName = difflib.get_close_matches(nazevLong, townStopNames, cutoff=0.9)
        if closestStopName:
            closestStopName = closestStopName[0]
            closestStopRelativeIdx = townStopNames.index(closestStopName)
            closestStopNode = townStopNodes[closestStopRelativeIdx]
            namesInfo[fullName] = closestStopNode

        else:
            # This will fail if the town has no stop nodes: in that case, just get center of the town
            namesInfo[fullName] = townNode

    stopInfos = [
        {"name": name, "info":
            {'id': stop.id, 'lat': float(stop.lat), 'lon': float(stop.lon), 'tags': stop.tags}
            if stop else None}
        for name, stop in namesInfo.items()]
    if outputFile:
        dirName = os.path.dirname(outputFile)
        if dirName and not os.path.exists(dirName):
            os.makedirs(dirName, exist_ok=True)
        with open(outputFile, "w+", encoding="utf-8") as f:
            jsonDump = json.dumps(stopInfos, indent=4, ensure_ascii=False)
            f.write(jsonDump)

    return {si["name"]: si["info"] for si in stopInfos}
