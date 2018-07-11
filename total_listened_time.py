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
    begin_skip = []
    end_skip = []
    begin_subreg = []
    end_subreg = []
    begin_sil = []
    end_sil = []

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
            elif "begin skip" in line:
                ts = get_last_timestamp(lines)
                begin_skip.append(ts)
            elif "end skip" in line:
                ts = get_last_timestamp(lines)
                end_skip.append(ts)
            elif "subregion" in line and "starts" in line:
                ts = get_last_timestamp(lines)
                begin_subreg.append(ts)
            elif "subregion" in line and "ends" in line:
                ts = get_last_timestamp(lines)
                end_subreg.append(ts)
            elif "silence" in line and "starts" in line:
                ts = get_last_timestamp(lines)
                begin_sil.append(ts)
            elif "silence" in line and "ends" in line:
                ts = get_last_timestamp(lines)
                end_sil.append(ts)
            else:
                lines.append(line)

    if len(begin_extras) != len(end_extras):
        raise Exception("EXTRA: begin count does not match end count")
    elif len(begin_makeup) != len(end_makeup):
        raise Exception("MAKEUP: begin count does not match end count")
    elif len(begin_skip) != len(end_skip):
        raise Exception("SKIP: begin count does not match end count")
    elif len(begin_sil) != len(end_sil):
        raise Exception("SILENCE: begin count does not match end count")
    else:
        return begin_extras, end_extras, begin_makeup, \
               end_makeup, begin_skip, end_skip,\
               begin_subreg, end_subreg, begin_sil,\
               end_sil


def get_last_timestamp(lines):
    for line in reversed(lines):
        m = interval_regx.findall(line)
        if m and len(m) == 1:
            return int(m[0].split("_")[1])
    return 0

def sum_regions(begins, ends):
    joined = zip(begins, ends)
    total = 0
    for x in joined:
        if x[1] < x[0]:
            raise Exception("begin is after end: begin: {}  end: {}".format(x[0], x[1]))
        total += x[1] - x[0]
    return total

def sil_subr_overlap_sum(month,
                         b_sil, e_sil,
                         b_sub, e_sub,
                         b_mak, e_mak):

    """
    sum of all silence +subregion overlap time
    :param month:
    :param b_sil: silence onsets
    :param e_sil: silence offsets
    :param b_sub: subregion onsets
    :param e_sub: subregion offsets
    :param b_mak: makeup onsets
    :param e_mak: makeup offsets
    :return: total silence overlap time
    """
    subregs = zip(b_sub, e_sub)
    sils = zip(b_sil, e_sil)
    makeups = zip(b_mak, e_mak)

    for silreg in sils:
        region_overlap(silreg, subregs)

def region_overlap(sil, subregs):
    for reg in subregs:
        if reg[0] < sil[0] < reg[1]:
            if reg[0] < sil[1] < reg[1]:
                print



if __name__ == "__main__":

    input = sys.argv[1]
    # subregs = sys.argv[2]

    files = [os.path.join(input, x) for x in os.listdir(input)]

    results = []


    for file in files:
        fname = os.path.basename(file)

        extra_sum = 0
        makeup_sum = 0
        skip_sum = 0
        try:
            b_extra, e_extra, b_makup, e_makup, \
            b_skip, e_skip, b_subr, e_subr, b_sil, \
            e_sil  = pull_regions(file)
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
            if b_skip:
                try:
                    skip_sum = sum_regions(b_skip, e_skip)
                except Exception as e:
                    print fname
                    print e
                    print
            if b_sil:
                try:
                    overlap_sum = sil_subr_overlap_sum(int(fname[3:5]),
                                                       b_sil, e_sil,
                                                       b_subr, e_subr,
                                                       b_makup, e_makup)
                except:
                    print

            results.append((os.path.basename(file)[:5], extra_sum, makeup_sum, skip_sum))

        except Exception as e:
            print fname
            print e
            print



    df = pd.DataFrame(results, columns=["file", "extra", "makeup", "skip"])
    df.to_csv("total_listened_time.csv", index=False)