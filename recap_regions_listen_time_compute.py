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
code_regx = re.compile('([a-zA-Z][a-z+]*)( +)(&=)([A-Za-z]{1})(_)([A-Za-z]{1})(_)([A-Z]{1}[A-Z0-9]{2})(_)?(0x[a-z0-9]{6})?', re.IGNORECASE | re.DOTALL) # Annotation regex
keyword_list = ["subregion", "silence", "skip", "makeup", "extra"]
keyword_rank = {"subregion": 1, "skip": 2, "silence": 3, "makeup": 4, "extra": 5}

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
    return sequence, cf

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

def sequence_missing_repetition_entry_alert(sequence):
    region_map = {x:{'starts':[], 'ends': []} for x in keyword_list}
    error_list = []
    for entry in sequence:
        region_map[entry[0].split()[0]][entry[0].split()[1]].append(entry[1])
    for item in keyword_list:
        if len(set(region_map[item]['starts'])) < len(set(region_map[item]['ends'])):
            error_list.append(item + ' starts missing')
        elif len(set(region_map[item]['starts'])) > len(set(region_map[item]['ends'])):
            error_list.append(item + ' ends missing')
        if len(set(region_map[item]['ends'])) < len(region_map[item]['ends']):
            error_list.append(item + ' ends repetition')
        if len(set(region_map[item]['starts'])) < len(region_map[item]['starts']):
            error_list.append(item + ' starts repetition')
    return error_list, region_map

def total_listen_time(cf, region_map):
    def remove_regions_nested_in_skip():
        skip_start_times = region_map['skip']['starts']
        skip_end_times = region_map['skip']['ends']
        assert(len(skip_start_times)==len(skip_end_times))
        for region_type in ['makeup', 'silence', 'subregion', 'extra']:
            region_start_times = region_map[region_type]['starts']
            region_end_times = region_map[region_type]['ends']
            assert(len(region_start_times)==len(region_end_times))
            for i in range(len(skip_start_times)):
                for j in range(len(region_start_times)-1, -1, -1):
                    if skip_start_times[i]<=region_start_times[j] and skip_end_times[i]>=region_end_times[j]:
                        #print("removed {} {} {}".format(region_type, region_start_times[j], region_end_times[j]))
                        del region_end_times[j]
                        del region_start_times[j]

    def remove_silence_regions_outside_subregions():
        silence_start_times = region_map['silence']['starts']
        silence_end_times = region_map['silence']['ends']
        subregion_start_times = region_map['subregion']['starts']
        subregion_end_times = region_map['subregion']['ends']
        for i in range(len(silence_start_times)-1, -1, -1):
            remove = True
            for j in range(len(subregion_start_times)):
                if subregion_start_times[j]<=silence_start_times[i] and subregion_end_times[j]>=silence_end_times[i]:
                    remove = False
                    break
            if remove:
                del silence_start_times[i]
                del silence_end_times[i]

    '''
        TODO:
        Assumption: if a subregion has nested makeup region, that means there should not be any other annotations outside the nested makeup region
                    but inside the subregion (i.e. the subregion could be discounted)

        This assumption needs to be verified
    '''
    def remove_subregions_with_nested_makeup():
        subregion_start_times = region_map['subregion']['starts']
        subregion_end_times = region_map['subregion']['ends']
        makeup_start_times = region_map['makeup']['starts']
        makeup_end_times = region_map['makeup']['ends']
        for i in range(len(subregion_start_times)-1, -1, -1):
            remove = False
            for j in range(len(makeup_start_times)):
                if subregion_start_times[i]<=makeup_start_times[j] and subregion_end_times[i]>=makeup_end_times[j]:
                    remove = True
                    break
            if remove:
                del subregion_start_times[i]
                del subregion_end_times[i]

    def annotated_subregion_time():
        start_times = region_map['subregion']['starts']
        end_times = region_map['subregion']['ends']
        total_time = 0
        for i in range(len(start_times)):
            lines = cf.get_within_time(begin=start_times[i], end=end_times[i]).line_map
            for line in lines:
                annot = code_regx.findall(line.line)
                if annot:
                    total_time += end_times[i] - start_times[i] # +1?
                    break
        return total_time
    
    # I have those functions all separated in case we need to make modifications to the way we compute listen time for each region
    def skip_region_time():
        start_times = region_map['skip']['starts']
        end_times = region_map['skip']['ends']
        total_time = 0
        for i in range(len(start_times)):
            total_time += end_times[i] - start_times[i]
        return total_time

    def silence_region_time():
        start_times = region_map['silence']['starts']
        end_times = region_map['silence']['ends']
        total_time = 0
        for i in range(len(start_times)):
            total_time += end_times[i] - start_times[i]
        return total_time

    def extra_region_time():
        start_times = region_map['extra']['starts']
        end_times = region_map['extra']['ends']
        total_time = 0
        for i in range(len(start_times)):
            total_time += end_times[i] - start_times[i]
        return total_time

    def makeup_region_time():
        start_times = region_map['makeup']['starts']
        end_times = region_map['makeup']['ends']
        total_time = 0
        for i in range(len(start_times)):
            total_time += end_times[i] - start_times[i]
        return total_time


    # Preprocessing
    remove_regions_nested_in_skip()
    remove_silence_regions_outside_subregions()
    remove_subregions_with_nested_makeup()

    subregion_time = annotated_subregion_time()
    skip_time = skip_region_time()
    silence_time = silence_region_time()
    extra_time = extra_region_time()
    makeup_time = makeup_region_time()

    print(subregion_time+makeup_time+extra_time-silence_time-skip_time)

if __name__ == "__main__":
    cha_dir = sys.argv[1]
    #files = sorted([os.path.join(cha_dir, x) for x in os.listdir(cha_dir) if x.endswith(".cha")])
    files = ['../all_cha/03_12_sparse_code.cha']
    file_with_error = []
    for file in files:
        print("Checking {}".format(os.path.basename(file)))
        sequence, cf = pull_regions(file)
        sequence_minimal_error_sorting(sequence)
        error_list, region_map = sequence_missing_repetition_entry_alert(sequence)
        total_listen_time(cf, region_map)
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
