import os
import pandas as pd
import sys


def process(subreg, unranked):
    print


if __name__ == "__main__":

    subregs = pd.read_csv(sys.argv[1])
    unranked = pd.read_csv(sys.argv[2])


    for idx, entries in subregs.groupby("file"):
        process(entries, unranked)