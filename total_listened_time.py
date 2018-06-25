import os
import sys
import re
import pandas as pd


interval_regx = re.compile("\\x15(\d+_\d+)\\x15")


def pull_regions(path):
    begin_extras = []
    end_extras = []
    begin_makeup = []
    end_makeup = []

    with open(path, "rU") as input:
        lines = []
        for line in input:
            if "begin extra time" in line:
                ts = get_last_timestamp(lines)
                begin_extras.append(ts)
            elif "end extra time" in line:
                ts = get_last_timestamp(lines)
                end_extras.append(ts)
            elif "begin makeup region" in line:
                ts = get_last_timestamp(lines)
                begin_makeup.append(ts)
            elif "end makeup region" in line:
                ts = get_last_timestamp(lines)
                end_makeup.append(ts)
            else:
                lines.append(line)

    if len(begin_extras) != len(end_extras):
        raise Exception("EXTRA: begin count does not match end count")
    elif len(begin_makeup) != len(end_makeup):
        raise Exception("MAKEUP: begin count does not match end count")
    else:
        return begin_extras, end_extras, begin_makeup, end_makeup


def get_last_timestamp(lines):
    for line in reversed(lines):
        m = interval_regx.findall(line)
        if m and len(m) == 1:
            return int(m[0].split("_")[1])

def sum_regions(begins, ends):
    joined = zip(begins, ends)
    total = 0
    for x in joined:
        if x[1] < x[0]:
            raise Exception("begin is after end: begin: {}  end: {}".format(x[0], x[1]))
        total += x[1] - x[0]
    return total

if __name__ == "__main__":

    input = sys.argv[1]
    # subregs = sys.argv[2]

    files = [os.path.join(input, x) for x in os.listdir(input)]

    results = []



    for file in files:
        fname = os.path.basename(file)
        extra_sum = 0
        makeup_sum = 0
        try:
            b_extra, e_extra, b_makup, e_makup = pull_regions(file)
            if b_extra:
                try:
                    extra_sum = sum_regions(b_extra, e_extra)
                except Exception as e:
                    print fname
                    print e
                    print
            if b_makup:
                try:
                    makeup_sum = sum_regions(b_makup, e_makup)
                except Exception as e:
                    print fname
                    print e
                    print

            # print "extra: {}      makeup: {}".format(extra_sum, makeup_sum)
            results.append((os.path.basename(file)[:5], extra_sum, makeup_sum))
        except Exception as e:
            print fname
            print e
            print



    df = pd.DataFrame(results, columns=["file", "extra", "makeup"])
    df.to_csv("total_listened_time.csv", index=False)