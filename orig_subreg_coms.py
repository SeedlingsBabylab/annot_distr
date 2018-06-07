import pandas as pd


# set path to clancomments.csv
df = pd.read_csv("../clancomments/clancomments.csv")


all_regions = []

for i, f in df.groupby('file'):
    curr_reg = []
    regions = []
    for j, r in f.iterrows():
        if all(x in r.comment for x in ["subregion", "start"]):
            if len(curr_reg) > 0:
                print("problem : {}".format(i))
                curr_reg = [r.onset]
            curr_reg = [r.onset]
        if all(x in r.comment for x in ["subregion", "end"]):
            if len(curr_reg) < 1:
                print("problem : {}".format(i))
                curr_reg = []
            else:
                curr_reg.append(r.onset)
                regions.append([i] + curr_reg)
                curr_reg = []

    all_regions.extend(regions)

regs = pd.DataFrame(all_regions, columns=["file", "onset", "offset"])

regs.to_csv("orig_subreg_comments.csv", index=False)



