import sys
import os
import csv
import argparse

JDF_ENCODING = "cp1250"

def main():
    parser = argparse.ArgumentParser(description="Fix stop names in Zastavky.txt")
    parser.add_argument("-c","--city",
                        help="Name of the central city in urban transport",action="store",
                        )
    parser.add_argument("-e","--exclude",
                        help="Do not add central city name to stops starting with this name (in case of suburban transport)",
                        action="append",
                        )
    parser.add_argument("-d","--district",
                        help="Name of nearby city (add only when blank)",
                        action="store",
                        )
    parser.add_argument("-p","--move-place",
                        help="Move place name to the end of stop name if possible",
                        action="store_true",
                        default=False
                        )
    parser.add_argument("folders",help="Folders containing Zastavky.txt",nargs="+")

    argv = sys.argv[1:]
    args = parser.parse_args(argv)

    townName = args.city
    exclude = args.exclude
    districtName = args.district
    folderNames = args.folders
    movePlace = args.move_place

    #12 fields, 2 3 4 are for stop name
    #Concatenate the field names with comma and then try to fix

    for folderName in folderNames:
        try:
            data = []
            with open(os.path.join(folderName,"Zastavky.txt"),"r",newline="",encoding=JDF_ENCODING) as f:
                reader = csv.reader(f,delimiter=",",quoting=csv.QUOTE_ALL,lineterminator=";")
                for line in reader:
                    data.append(line)
            for i,ln in enumerate(data):
                #Fixing error with semicolon at the end of line when parsing, will be returned at output
                if ln[-1][-1] == ";": 
                    ln[-1] = ln[-1][:-1]
                print(ln)
                joinLn = ",".join((ln[1],ln[2],ln[3]))
                splitLn = joinLn.split(",")
                initialTownName = splitLn[0]
                if (townName and
                    initialTownName not in exclude and
                    initialTownName != townName):
                        splitLn.insert(0,townName)
                if (movePlace and
                    not splitLn[2] and
                    splitLn[1]):
                        splitLn[2] = splitLn[1]
                        splitLn[1] = ""
                ln[1],ln[2],ln[3] = splitLn[0],splitLn[1],splitLn[2]
                #Add district name if not present
                if districtName and ln[4] == "": 
                    ln[4] = districtName
                data[i] = ln
                print(ln)
            with open(os.path.join(folderName,"Zastavky.txt"),"w",newline="",encoding=JDF_ENCODING) as f:
                writer = csv.writer(f,delimiter=",",quoting=csv.QUOTE_ALL,lineterminator=";\r\n")
                writer.writerows(data)
        except FileNotFoundError:
            print("File could not be found: "+folderName)
            continue
            
if __name__ == "__main__":
    sys.exit(main())

    
