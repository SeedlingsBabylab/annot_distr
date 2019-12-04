import pyclan as pc
from settings import *

# '''
# Step 1:
#     Parse file by pyclan and extract comments from the file.
#     Go through each comment, if it marks the beginning or ending of the regions,
#     mark it down to a list of tuples that looks like:
#     [(subregion starts, timestamp),  (silence starts, timestamp), (silence ends, timestamp)....]
# '''


def pull_regions(path):
    cf = pc.ClanFile(path)

    subregions = []

    comments = cf.get_user_comments()
    comments.sort(key = lambda x: x.offset)

    sequence = []
    for cline in comments:
        line = cline.line

        # Pulling subregion information from the line. 

        if 'subregion' in line:
            sub_pos = "N/A"
            sub_rank = "N/A"
            try:
                sub_pos = subr_regx.search(line).group(1)
                sub_rank = rank_regx.search(line).group(1)
            except AttributeError:
                print(bcolors.FAIL + 'Subregion time does not exist/is not correct' + bcolors.ENDC)
                print(bcolors.FAIL + path + bcolors.ENDC)

            offset = subr_time_regx.findall(line)
            try:
                offset = int(offset[0])
            except:
                print(bcolors.FAIL + 'Unable to grab time' + bcolors.ENDC)
            if 'starts' in line:
                sequence.append(('subregion starts', offset))
            # Only adding after ends in order to not add the position and rank info twice to the subregions list. 
            elif 'ends' in line:
                sequence.append(('subregion ends', offset))
                subregions.append('Position: {}, Rank: {}'.format(sub_pos, sub_rank))
        elif 'extra' in line:
            if 'begin' in line:
                sequence.append(('extra starts', cline.offset))
            elif 'end' in line:
                sequence.append(('extra ends', cline.offset))
        elif 'silence' in line:
            if 'start' in line:
                sequence.append(('silence starts', cline.offset))
            elif 'end' in line:
                sequence.append(('silence ends', cline.offset))
        elif 'skip' in line:
            if 'begin' in line:
                sequence.append(('skip starts', cline.offset))
            elif 'end' in line:
                sequence.append(('skip ends', cline.offset))
        elif 'makeup' in line or 'make-up' in line or 'make up' in line:
            if 'begin' in line:
                sequence.append(('makeup starts', cline.offset))
            elif 'end' in line:
                sequence.append(('makeup ends', cline.offset))
        elif 'surplus' in line:
            if 'begin' in line:
                sequence.append(('surplus starts', cline.offset))
            elif 'end' in line:
                sequence.append(('surplus ends', cline.offset))
        # if len(sequence)>1 and sequence[-2][1]==cline.offset:
        #     print(bcolors.WARNING + "Special case" + bcolors.ENDC)
    print subregions
    return sequence, cf, subregions


