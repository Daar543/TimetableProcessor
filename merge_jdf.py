import sys
import os
import pathlib

from JDF_Conversion import Timetable_Calculations
import argparse


def main():
    argv = sys.argv[1:]
    print(argv)
    parser = argparse.ArgumentParser(description='Merge JDF batches into one')
    parser.add_argument('input',nargs='+',
                        help='input folders')
    parser.add_argument('output', nargs=1,
                        help='output folder')
    args = parser.parse_args(argv)
    print(args)
    outputFolder = pathlib.Path(args.output[0])
    os.makedirs(outputFolder,exist_ok=True)
    inputPaths = [pathlib.Path(p) for p in args.input]
    jdfProcessor = Timetable_Calculations.ParseMultipleFolders([str(p) for p in inputPaths])
    if not jdfProcessor:
        print('Error while parsing JDF data')
        return 1
    jdfProcessor.SerializeOut(outputFolder)
    print('Success!')
    return 0

if __name__ == "__main__":
    sys.exit(main())

