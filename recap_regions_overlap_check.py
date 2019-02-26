import pyclan as pc
import csv
import re
import sys
import os.path
import pandas as pd

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


subr_regx = re.compile('subregion (\d*) ?of (\d*)') # There are some cases where the numbering is missing
keyword_list = ["subregion", "silence", "skip", "makeup", "extra"]
keyword_rank = {"subregion": 1, "silence": 2, "skip": 3, "makeup": 4, "extra": 5}

def pull_regions(path):
    cf = pc.ClanFile(path)

    comments = cf.get_user_comments()
    comments.sort(key = lambda x: x.offset)
    #print comments

    sequence = []
    for cline in comments:
        line = cline.line
        if 'subregion' in line:
            if 'starts' in line:
                sequence.append(('subregion starts', cline.offset))
            if 'ends' in line:
                sequence.append(('subregion ends', cline.offset))
        elif 'extra' in line:
            if 'begin' in line:
                sequence.append(('extra starts', cline.offset))
            if 'end' in line:
                sequence.append(('extra ends', cline.offset))
        elif 'silence' in line:
            if 'start' in line:
                sequence.append(('silence starts', cline.offset))
            if 'end' in line:
                sequence.append(('silence ends', cline.offset))
        elif 'skip' in line:
            if 'begin' in line:
                sequence.append(('skip starts', cline.offset))
            if 'end' in line:
                sequence.append(('skip ends', cline.offset))
        elif 'makeup' in line or 'make-up' in line or 'make up' in line:
            if 'begin' in line:
                sequence.append(('makeup starts', cline.offset))
            if 'end' in line:
                sequence.append(('makeup ends', cline.offset))
        # if len(sequence)>1 and sequence[-2][1]==cline.offset:
        #     print(bcolors.WARNING + "Special case" + bcolors.ENDC)
    return sequence

def sequence_minimal_error_sorting(sequence):
    def swap(i, j, seq):
        k = seq[i]
        seq[i] = seq[j]
        seq[j] = k
    for i in range(len(sequence)-1):
        x1 = sequence[i]
        x2 = sequence[i+1]
        if x1[1]==x2[1]:
            if x1[0].split()[1]=='starts' and x2[0].split()[1]=='ends':
                swap(i, i+1, sequence)
            elif x1[0].split()[1]=='starts' and x2[0].split()[1]=='starts':
                if keyword_rank[x1[0].split()[0]] > keyword_rank[x2[0].split()[0]]:
                    swap(i, i+1, sequence)
            elif x1[0].split()[1]=='ends' and x2[0].split()[1]=='ends':
                if keyword_rank[x1[0].split()[0]] < keyword_rank[x2[0].split()[0]]:
                    swap(i, i+1, sequence)
    return sequence

def sequence_missing_repetition_entry_alert(sequence):
    region_map = {x:{'starts':[], 'ends': []} for x in keyword_list}
    error_list = []
    for entry in sequence:
        region_map[entry[0].split()[0]][entry[0].split()[1]].append(entry[1])
    for item in keyword_list:
        # if len(set(region_map[item]['starts'])) < len(set(region_map[item]['ends'])):
        #     error_list.append(item + ' starts missing')
        # elif len(set(region_map[item]['starts'])) > len(set(region_map[item]['ends'])):
        #     error_list.append(item + ' ends missing')
        if len(set(region_map[item]['ends'])) < len(region_map[item]['ends']):
            error_list.append(item + ' ends repetition')
        if len(set(region_map[item]['starts'])) < len(region_map[item]['starts']):
            error_list.append(item + ' starts repetition')
        start_list = sorted(set(region_map[item]['starts']))
        end_list = sorted(set(region_map[item]['ends']))
        if len(start_list)==len(end_list):
            continue
        i, j = 0, 0
        while i<len(start_list) and j<len(end_list):
            if start_list[i]<=end_list[j]:
                i += 1
                j += 1
                continue
            if start_list[i]>end_list[j]: # reversal, indicating that there is a missing start
                error_list.append(item + ' starts missing for end at ' + str(end_list[j]))
                j += 1
                continue
            if i+1 < len(start_list) and start_list[i+1]<end_list[j]:
                error_list.append(item + ' ends missing for start at ' + str(start_list[i]))
                i += 1
                continue
        if i<len(start_list):
            error_list.append(item + ' ends missing for start at ' + str(start_list[i]))
        if j<len(end_list):
            error_list.append(item + ' starts missing for end at ' + str(end_list[j]))
    return error_list

if __name__ == "__main__":
    path_file = sys.argv[1]
    files = []
    with open(path_file) as f:
        for folder in f.readlines():
            folder = folder.strip()
            try:
                files.extend([os.path.join(folder, x) for x in os.listdir(folder) if x.endswith(".cha")])
            except:
                pass
    print("Found {} cha files".format(len(files)))
    #cha_dir = sys.argv[1]
    #files = sorted([os.path.join(cha_dir, x) for x in os.listdir(cha_dir) if x.endswith(".cha")])
    file_with_error = []
    for file in files:
        print("Checking {}".format(os.path.basename(file)))
        try:
            sequence = pull_regions(file)
        except:
            print(bcolors.FAIL + "Error opening file: {}".format(file) + bcolors.ENDC)
            continue
        sequence_minimal_error_sorting(sequence)
        error_list = sequence_missing_repetition_entry_alert(sequence)
        with open('../output/'+os.path.basename(file)+'.txt', 'w') as f:
            f.write('\n'.join([x[0] + '   ' + str(x[1]) for x in sequence]))
            f.write('\n')
            f.write('\n')
            f.write('\n')
            f.write('\n'.join(error_list))
        if error_list:
            print(bcolors.WARNING + "Finished {}".format(os.path.basename(file)) + bcolors.ENDC)
            file_with_error.append((os.path.basename(file), error_list))
        else:
            print("Finished {}".format(os.path.basename(file)))
        with open('../output/summary.txt', 'w') as f:
            for entry in file_with_error:
                f.write(entry[0]+'\n')
                for error in entry[1]:
                    f.write('\t\t\t\t'+error+'\n')
                f.write('\n')
