import os
import sys
import pandas as pd
from collections import Counter

if __name__ == "__main__":

    start = sys.argv[1]

    problem_files = []

    not_actually_a_problem = []

    for root, dirs, files in os.walk(start):
        for file in files:
            print file
            full = ""
            with open(os.path.join(root, file), "rU") as input:
                for line in input:
                    if "subregion" in line and "rank" not in line:
                        problem_files.append(file[:5])
                    full += line
            if 8 <= int(file[3:5]) <= 13:
                if "lowest ranked" in full:
                    not_actually_a_problem.append(file[:5])



    count = Counter(problem_files)

    # uncomment this to filter out instances where
    # there is at least the "lowest ranked" comment
    # for x in not_actually_a_problem:
    #     del count[x]

    data = zip(count.keys(), count.values())
    df = pd.DataFrame(data, columns=["file", "num_problem_region_coms"])

    df.to_csv("files_with_unranked_subregions.csv", index=False)