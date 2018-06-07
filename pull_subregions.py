import os
import sys
import re

import pandas as pd
import pyclan as pc

subr_regx = re.compile('subregion (\d+) of (\d+)')


regions = []

def process_file(path):
    results = {}
    cf = pc.ClanFile(path)
    pfx = cf.filename[:5]
    subrs = filter(lambda x: "subregion" in x.line, cf.get_user_comments())
    subrs.sort(key=lambda x: x.offset)
    if len(subrs) % 2 != 0:
        raise Exception

    for x in subrs:
        m = subr_regx.findall(x.line)
        if len(m) > 1:
            raise Exception
        m=m[0]
        if m[0] not in results:
            results[m[0]] = [x.offset]
        else:
            results[m[0]].append(x.offset)

    results = [[pfx, int(key), val[0], val[1]] for key, val in results.items()]
    results.sort(key=lambda x: x[1])
    regions.extend(results)




if __name__ == "__main__":

    cha_dir = sys.argv[1]
    files = [os.path.join(cha_dir, x) for x in os.listdir(cha_dir) if x.endswith(".cha")]
    # print files
    for file in files:
        try:
            process_file(file)
        except Exception as e:
            print os.path.basename(file)
            print e

    df = pd.DataFrame(regions, columns=['file', 'reg_num', 'onset', 'offset'])
    df.to_csv("subregions_poop2.csv", index=False)

