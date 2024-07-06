#!/usr/bin/env python3

import datetime
import os

import prettytable

import sys
import argparse

import Timetable_Calculations
import Table_Export


def main_with_args():
    """
    Possible arguments:
    - Single JDF
    - Bundling JDF
        - Filter by stops
        - Filter by companies (regex)
    - Calculate distances
    - Interactive mode for trips
    - List all trips for date range
    - Where to output
    """

    argv = sys.argv
    parser = argparse.ArgumentParser(description="JDF Parser")

    parser.add_argument("-s", "--single", help="Select a folder with single JDF", action="store")
    parser.add_argument("-S", "--select", help="Select multiple folders with JDF", action="store", nargs="+")
    parser.add_argument("-b", "--bundle", help="Select folder with multiple JDF folders (non-recursive) and combine",
                        action="store")

    parser.add_argument("-o", "--output-folder", help="Select an output folder", action="store")
    parser.add_argument("-O", "--output-file", help="Select an output file (relative to chosen folder)", action="store")

    parser.add_argument("-z", "--filter-stop", help="Chooses only JDF which contain this stop", action="store")
    parser.add_argument("-c", "--filter-company", help="Chooses only JDF which contain this company", action="store")
    parser.add_argument("-l", "--filter-line", help="Chooses only JDF which contain this line", action="store")

    parser.add_argument("-L", "--list", help="List all trips for specified dates", action="store", nargs="+")
    parser.add_argument("-r", "--range", help="List all trips for dates in a range", action="store", nargs=2)

    parser.add_argument("-f", "--full", help="Print the trips with all intermediate stops", action="store_true")

    parser.add_argument("-d", "--distances-terminals", help="Calculate distances between terminal stops.",
                        action="store_true")
    parser.add_argument("-D", "--distances-all", help="Calculate distances between all stops", action="store_true")

    parser.add_argument("-i", "--interactive", help="Interactive querying of dates", action="store_true")  # default

    parser.add_argument("-q", "--quiet", help="Do not write trips on console unless prompted", action="store_false")

    args = parser.parse_args(argv[1:])

    if args.single:
        jdfProcesser = Timetable_Calculations.ParseSingleFolder(args.single)
    elif args.select:
        jdfProcesser = Timetable_Calculations.ParseMultipleFolders(args.select, True)
    elif args.bundle:
        rootdir = args.bundle
        subfolders = [f.path for f in os.scandir(rootdir) if f.is_dir()]
        if args.filter_stop or args.filter_company or args.filter_line:
            subfolders = Timetable_Calculations.FilterJdfFolders(subfolders, stop=args.filter_stop,
                                                                 company=args.filter_company,
                                                                 line=args.filter_line)
        jdfProcesser = Timetable_Calculations.ParseMultipleFolders(subfolders, False)
    else:
        parser.print_help()
        print("Not selected method for JDF selection")
        return

    if not jdfProcesser:
        parser.print_help()
        print("No JDF selected/found")
        return

    if args.distances_terminals or args.distances_all:

        writeToFile = args.output_folder or args.output_file

        # Creation of folder is done before the calculation so we can crash sooner
        if writeToFile:
            if args.output_folder and args.output_file:
                vystup = os.path.join(args.output_folder, args.output_file)
            elif args.output_folder:
                vystup = os.path.join(args.output_folder, "distances_terminals.tsv")
            elif args.output_file:
                vystup = args.output_file
            else:
                raise RuntimeError("Control flow error")
            # Create the corresponding folder in canonical way
            os.makedirs(os.path.dirname(vystup), exist_ok=True)

        if args.distances_terminals:
            zastavky, matica = jdfProcesser.GetDeadheadMatrixByTT(jdfProcesser.GetTerminalStops())
        elif args.distances_all:
            zastavky, matica = jdfProcesser.GetAllStopMatrixByTT()

        # JdfProcesser.CalculateTimeMatrix(matica)

        if writeToFile:
            with open(vystup, "w+", encoding=Timetable_Calculations.PROJECT_ENCODING) as f:
                f.write("Stops")
                for za in zastavky:
                    f.write("\t" + za.GetName())
                f.write("\n")
                for i in range(len(zastavky)):
                    f.write(zastavky[i].GetName())
                    for w in matica[i]:
                        f.write("\t" + str(w))
                    f.write("\n")
            print("Written succesfully")
        else:
            tbl = prettytable.PrettyTable()
            tbl.field_names = ["Stops"] + [f"({i})" for i in
                                           range(len(zastavky))]  # Reducing the column width so it fits on console
            for i in range(len(zastavky)):
                tbl.add_row([f"{zastavky[i].GetName()} ({i})"] + matica[i])
            # tbl._max_width={za.GetName():3 for za in zastavky}
            print(tbl)

    if args.list:
        for date in args.list:
            jdfProcesser.testDateByUserInput(args.quiet, "XX", args.full, args.output_folder, date)

    if args.range:
        startDate, endDate = args.range[0], args.range[1]
        parsed = False
        try:
            startDate = datetime.datetime.strptime(startDate, "%Y-%m-%d")
            endDate = datetime.datetime.strptime(endDate, "%Y-%m-%d")
            parsed = True
        except ValueError:
            print(f"Invalid date format, should be YYYY-MM-DD \n input: {startDate} - {endDate}")
        if parsed:
            currDate = startDate
            while currDate <= endDate:
                jdfProcesser.testDateByUserInput(args.quiet, "XX", args.full, args.output_folder,
                                                 currDate.strftime("%d.%m.%Y"))
                currDate += datetime.timedelta(days=1)

    if args.interactive:
        keep_asking = True
        while keep_asking:
            keep_asking = jdfProcesser.testDateByUserInput(True, "XX", args.full, args.output_folder)

    return


# Utilizes only the Timetable_Calculations API with
def main_prompts():
    state = "folders"
    outFolder = "."
    while state != "exit":
        if state == "folders":
            print("Select JDF folder(s) to be processed")
            print("1) Single folder")
            print("2) Multiple folders in one root folder")
            print("3) Exit")
            state = input("Select option: ")
            if state == "1":
                folder = input("Enter folder path: ")
                jdfProcesser = Timetable_Calculations.ParseSingleFolder(folder)
                state = "main"
            elif state == "2":
                folder = input("Enter folder path: ")
                stops_regex = input("Enter stop filter regex: ")
                company_regex = input("Enter company filter regex: ")
                line_regex = input("Enter line filter regex: ")
                subfolders = [f.path for f in os.scandir(folder) if f.is_dir()]
                subfolders = Timetable_Calculations.FilterJdfFolders(subfolders, stops_regex, company_regex, line_regex)
                jdfProcesser = Timetable_Calculations.ParseMultipleFolders(subfolders, False)
                state = "main"
            elif state == "3":
                state = "exit"
            else:
                print("Invalid option")
        elif state == "main":
            print("1) List all trips for specified date (10 to include intermediate stops)")
            print("2) List all trips for dates in a range (20 to include intermediate stops)")
            print("3) Calculate distances between terminal stops")
            print("4) Calculate distances between all stops")
            print("5) Exit")
            state = input("Select option: ")
            if state == "5":
                state = "exit"
                continue
            output = input("Output to file? (Y/n): ")
            if output == "y" or output == "Y" or output == "":
                output = True
            else:
                output = False
            if output:
                output = input("Enter output DIRECTORY path (keep blank for previous input): ")
                if output != "":
                    outFolder = output
            if state == "1" or state == "10":
                date = input("Enter date in format DD.MM.YYYY: ")
                jdfProcesser.testDateByUserInput(True, "XX", state=="10", outFolder, date)
            elif state == "2" or state=="20":
                startDate = input("Enter start date in format DD.MM.YYYY: ")
                endDate = input("Enter end date in format DD.MM.YYYY: ")
                parsed = False
                try:
                    startDate = datetime.datetime.strptime(startDate, "%d.%m.%Y")
                    endDate = datetime.datetime.strptime(endDate, "%d.%m.%Y")
                    parsed = True
                except ValueError:
                    print(f"Invalid date format, should be DD.MM.YYYY \n input: {startDate} - {endDate}")
                if parsed:
                    currDate = startDate
                    while currDate <= endDate:
                        jdfProcesser.testDateByUserInput(True, "XX", state=="20", outFolder, currDate.strftime("%d.%m.%Y"))
                        currDate += datetime.timedelta(days=1)
            elif state == "3":
                terminals, matrix = jdfProcesser.GetDeadheadMatrixByTT(jdfProcesser.GetTerminalStops())
                if outFolder:
                    os.makedirs(outFolder, exist_ok=True)
                    with open(os.path.join(outFolder, "distances_terminals.tsv"), "w+",
                              encoding=Timetable_Calculations.PROJECT_ENCODING) as f:
                        jdfProcesser.WriteStopMatrix(f, terminals, matrix)

                    print("Written succesfully")
                else:
                    tbl = prettytable.PrettyTable()
                    tbl.field_names = ["Stops"] + [f"({i})" for i in
                                                   range(len(terminals))]
                    for i in range(len(terminals)):
                        tbl.add_row([f"{terminals[i].GetName()} ({i})"] + matrix[i])
                    print(tbl)

            elif state == "4":
                stops, matrix = jdfProcesser.GetAllStopMatrixByTT()
                if outFolder:
                    os.makedirs(outFolder, exist_ok=True)
                    with open(os.path.join(outFolder, "distances_all.tsv"), "w+",
                              encoding=Timetable_Calculations.PROJECT_ENCODING) as f:
                        jdfProcesser.WriteStopMatrix(f, stops, matrix)
                    print("Written succesfully")
                else:
                    tbl = prettytable.PrettyTable()
                    tbl.field_names = ["Stops"] + [f"({i})" for i in
                                                   range(len(stops))]
                    for i in range(len(stops)):
                        tbl.add_row([f"{stops[i].GetName()} ({i})"] + matrix[i])
                    print(tbl)
            else:
                print("Invalid option")
            if state != "exit":
                state = "main"


def main_test():
    inf = "online_files/CSADUH"  # input("Write input folder")
    jdfProcesser = Timetable_Calculations.ParseSingleFolder(inf)
    timetable = Table_Export.MakeTimetable(jdfProcesser,(802365,1),False)
    Table_Export.CompleteTimetableMetadata(jdfProcesser,timetable,(802365,1), False)
    Table_Export.AddTimetableKilometrage(jdfProcesser,timetable,(802365,1), False)
    # print as pretty table
    tbl = prettytable.PrettyTable()
    tbl.field_names = [i for i,e in enumerate(timetable[2])]
    tbl.header=False
    for r in timetable:
        tbl.add_row(r)
    print(tbl)

    #print as csv
    filename = "online_files/temp/802365_1_Z.csv"
    with open(filename,"w+",encoding="utf-8") as f:
        Table_Export.WriteAsCsv(f,timetable)


def main_test_bundle():
    inf = "../SharedData/JDF_Data/JDF_2023"
    filterLines = "80500."
    filterStops = ""
    filterCompanies = "www.csaduh.cz"
    subfolders = [f.path for f in os.scandir(inf) if f.is_dir()]
    subfolders = Timetable_Calculations.FilterJdfFolders(subfolders
                                                         ,stop=filterStops
                                                         ,company=filterCompanies
                                                         ,line=filterLines
                                                         )
    jdfProcesser = Timetable_Calculations.ParseMultipleFolders(subfolders, False)
    target = "online_files/MHDUH"
    os.makedirs(target,exist_ok=True)
    jdfProcesser.SerializeOut(target)


if __name__ == "__main__":
    main_test()
