import pyclan as pc
import csv
import re
import sys
import signal
import os.path
from multiprocessing import Pool, Manager
import pdb
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


# '''
# Step 2:
#     Sort the output, a list of tuples, from the pull_regions function.
#     The sorting has two keys, primary key is the timestamp, ascending
#     secondary sorting key is rank specified in keyword rank.
#     The purpose of the secondary key is to ensure that when two entries
#     have the same timestamp, certain sorting order is still maintained.
# '''
def sequence_minimal_error_sorting(sequence):
    sequence = sorted(sequence, key=lambda k: (k[1], keyword_rank[k[0]]))
    return sequence

def sequence_missing_repetition_entry_alert(sequence):
    """
    Step 3:
        Basic error checking. It first builds the following map:
        region_map = {
            'subregion': {'starts': [list 1], 'ends': [list 2]},
            'silence': {'starts': [list 1], 'ends': [list 2]},
            ....
        }
        where list 1 and list 2 are the starting and ending timestamps for that particular type of region.
        The checking makes sure that both the beginning and end remarks are present for each region identified.
    """

    region_map = {x:{'starts':[], 'ends': []} for x in keyword_list}
    error_list = []
    for entry in sequence:
        region_map[entry[0].split()[0]][entry[0].split()[1]].append(entry[1])
    for item in keyword_list:
        if len(region_map[item]['starts']) == 0:
            continue
        if len(region_map[item]['ends']) == 0:
            continue
        # Checking for duplicate starts and ends. Length of set will be shorter if there are duplicates.
        if len(set(region_map[item]['ends'])) < len(region_map[item]['ends']):
            error_list.append(item + ' ends repetition')
        if len(set(region_map[item]['starts'])) < len(region_map[item]['starts']):
            error_list.append(item + ' starts repetition')
        start_list = sorted(set(region_map[item]['starts']))
        end_list = sorted(set(region_map[item]['ends']))
        i, j = 0, 0
        pe = 0

        # Added code to check for nesting of same type (skips within skips, fully or partially, which is not handled by default!)
        while i<len(start_list) and j<len(end_list):
            if start_list[i] < pe:
                print('Found a nesting! {0} end at {1} is nested between {0} start at {2} and {0} end at {3}'.format(item, pe, start_list[i], end_list[j]))
                print(item, pe)
                error_list.append('Found a nesting! {0} end at {1} is nested between {0} start at {2} and {0} end at {3}'.format(item, pe, start_list[i], end_list[j]))
            pe = end_list[j]
            if start_list[i]<=end_list[j]:
                i += 1
                j += 1
            else: # rstart_list[i]>end_list[j]: eversal, indicating that there is a missing start
                error_list.append(item + ' starts missing for end at ' + str(end_list[j]))
                j += 1
        if i<len(start_list):
            error_list.extend([item + 'ends missing for start at ' + str(start_list[s]) for s in range(i, len(start_list))])
        if j<len(end_list):
            error_list.extend([item + 'starts missing for end at ' + str(end_list[s]) for s in range(i, len(start_list))])
    return error_list, region_map

# '''
# Step 4:
#     Compute the total listen time. Several transformations or filterings are done before computing the total listen time.
# '''
def total_listen_time(cf, region_map, subregions, month67 = False):
    # '''
    # Subruotine 1:
    #     Remove all the regions that are completely nested within the skip regions.
    #     If a region is partially overlap with a skip region, remove only the overlapping portion by adjusting the boundary of the region.
    # '''
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
                        print("removed {} {} {}".format(region_type, region_start_times[j], region_end_times[j]))
                        del region_end_times[j]
                        del region_start_times[j]
                        if region_type == 'subregion':
                            del subregions[j]
                    elif skip_start_times[i]<=region_start_times[j] and skip_end_times[i]<=region_end_times[j] and skip_end_times[i] >= region_start_times[j]:
                        skip_start_times[i] = region_start_times[j]
                    elif skip_start_times[i]>=region_start_times[j] and skip_end_times[i]>=region_end_times[j] and skip_start_times[i] <= region_end_times[j]:
                        skip_end_times[i] = region_end_times[j]
    '''
        TODO:
        Assumption: if a subregion has nested makeup region, that means there should not be any other annotations outside the nested makeup region
                    but inside the subregion (i.e. the subregion could be discounted)

        This assumption needs to be verified
    '''
    # '''
    # Subroutine 2:
    #     Remove all the subregions that has a makeup region or surplus region inside. This is because only the makeup/surplus region listen time
    #     needs to be summed.
    # '''
    def remove_subregions_with_nested_makeup():
        subregion_start_times = region_map['subregion']['starts']
        subregion_end_times = region_map['subregion']['ends']
        makeup_start_times = region_map['makeup']['starts']
        makeup_end_times = region_map['makeup']['ends']
        surplus_start_times = region_map['surplus']['starts']
        surplus_end_times = region_map['surplus']['ends']
        for i in range(len(subregion_start_times)-1, -1, -1):
            remove = False
            for j in range(len(makeup_start_times)):
                if subregion_start_times[i]<=makeup_start_times[j] and subregion_end_times[i]>=makeup_end_times[j]:
                    remove = True
                    break
            for j in range(len(surplus_start_times)):
                if subregion_start_times[i]<=surplus_start_times[j] and subregion_end_times[i]>=surplus_end_times[j]:
                    remove = True
                    break
            if remove:
                print("nested makeup or surplus ",subregion_start_times[i], subregion_end_times[i])
                del subregion_start_times[i]
                del subregion_end_times[i]
                del subregions[i]
        #print(subregion_start_times)

    # '''
    # Subroutine 3:
    #     Remove all subregions that does not have any annotations. Those regions should be ignored since they do not consists
    #     of any listened content.
    # '''
    def remove_subregions_without_annotations():
        subregion_start_times = region_map['subregion']['starts']
        subregion_end_times = region_map['subregion']['ends']
        for i in range(len(subregion_start_times)-1, -1, -1):
            remove = True
            lines = cf.get_within_time(begin=subregion_start_times[i], end=subregion_end_times[i]).line_map
            for line in lines:
                annot = code_regx.findall(line.line)
                if annot:
                    remove = False
                    break
            if remove:
                print("no annot", subregion_start_times[i])
                del subregion_start_times[i]
                del subregion_end_times[i]
                del subregions[i]
        #print(subregion_start_times)

    # '''
    # Subroutine 4:
    #     Remove subregions that are completely nested in silent or surplus regions. Partial nesting does not count. 
    # '''
    def remove_subregions_nested_in_silence_regions():
        silence_start_times = region_map['silence']['starts']
        silence_end_times = region_map['silence']['ends']
        subregion_start_times = region_map['subregion']['starts']
        subregion_end_times = region_map['subregion']['ends']
        surplus_start_times = region_map['surplus']['starts']
        surplus_end_times = region_map['surplus']['ends']
        for i in range(len(subregion_start_times)-1, -1, -1):
            remove = False
            for j in range(len(silence_start_times)):
                if subregion_start_times[i]>=silence_start_times[j] and subregion_end_times[i]<=silence_end_times[j]:
                    remove = True
                    break
            for j in range(len(surplus_start_times)):
                if subregion_start_times[i]>=surplus_start_times[j] and subregion_end_times[i]<=surplus_end_times[j]:
                    remove = True
                    break
            if remove:
                print("in silence or in surplus", subregion_start_times[i])
                del subregion_start_times[i]
                del subregion_end_times[i]
                del subregion[i]
        #print(subregion_start_times)

    # '''
    # Subroutine 5:
    #     If a silent region partially overlaps with a subregion, remove the NON-OVERLAPPING portion of that silent region (since we don't subtract that part in our calculation.
    #     Otherwise, if the silent region does not overlap with the subregion at all, completely remove it! 
    # '''
    def remove_silence_regions_outside_subregions():
        silence_start_times = region_map['silence']['starts']
        silence_end_times = region_map['silence']['ends']
        subregion_start_times = region_map['subregion']['starts']
        subregion_end_times = region_map['subregion']['ends']
        i = len(silence_start_times) - 1
        while i>=0:
            remove = True
            for j in range(len(subregion_start_times)):
                # If the silent region i start time is between start and end of subregion j
                if silence_start_times[i]>=subregion_start_times[j] and silence_start_times[i]<=subregion_end_times[j]:
                    # If there is not a complete nesting of the silent region within the subregion! 
                    if silence_end_times[i]>subregion_end_times[j]:
                        silence_end_times.append(silence_end_times[i])
                        silence_start_times.append(subregion_end_times[j]+1)
                        silence_end_times[i] = subregion_end_times[j]
                        i += 2
                        silence_start_times.sort()
                        silence_end_times.sort()
                    remove = False
                    break
                if silence_end_times[i]>=subregion_start_times[j] and silence_end_times[i]<=subregion_end_times[j]:
                    silence_start_times[i] = max(subregion_start_times[j], silence_start_times[i])
                    remove = False
                    break
            if remove:
                del silence_start_times[i]
                del silence_end_times[i]
            i -= 1

    def remove_subregions_with_surplus():
        subregion_start_times = region_map['subregion']['starts']
        subregion_end_times = region_map['subregion']['ends']
        surplus_start_times = region_map['surplus']['starts']
        surplus_end_times = region_map['surplus']['ends']
        for i in range(len(subregion_start_times)-1, -1, -1):
            remove = False
            for j in range(len(surplus_start_times)):
                # If surplus start or end is inside the subregion (e.g. there is any kind of overlap)
                if (subregion_start_times[i]<=surplus_start_times[j] and subregion_end_times[i]>=surplus_start_times[j]) \
                or (subregion_start_times[i]<=surplus_end_times[j] and subregion_end_times[i]>=surplus_end_times[j]):
                    remove = True
                    break
            if remove:
                print("overlap surplus ",subregion_start_times[i], subregion_end_times[i])
                del subregion_start_times[i]
                del subregion_end_times[i]
                del subregions[i]

    def skip_silence_overlap_time():
        ''' This is only used for month 6 and 7.
            The total time where skip and silence regions overlap are computed so as to be subtracted from silence time computed later.
        '''
    # Only used for month 6 and 7

        skip_start_times = region_map['skip']['starts']
        skip_end_times = region_map['skip']['ends']
        silence_start_times = region_map['silence']['starts']
        silence_end_times = region_map['silence']['ends']
        overlap_time = 0
        for i in range(len(skip_start_times)):
            for j in range(len(silence_start_times)):
                if skip_start_times[i]>=silence_start_times[j] and skip_start_times[i]<=silence_end_times[j]:
                    overlap_time += min(silence_end_times[j], skip_end_times[i]) - skip_start_times[i]
                elif skip_end_times[i]>=silence_start_times[j] and skip_end_times[i]<=silence_end_times[j]:
                    overlap_time += skip_end_times[i] - max(silence_start_times[j], skip_start_times[i])
        return overlap_time

    def annotated_subregion_time():
        start_times = region_map['subregion']['starts']
        end_times = region_map['subregion']['ends']
        total_time = 0
        num_subregion_with_annot = 0
        for i in range(len(start_times)):
            num_subregion_with_annot += 1
            total_time += end_times[i] - start_times[i] # +1?
        return total_time, num_subregion_with_annot

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
        return total_time, len(start_times)

    def makeup_region_time():
        start_times = region_map['makeup']['starts']
        end_times = region_map['makeup']['ends']
        total_time = 0
        for i in range(len(start_times)):
            total_time += end_times[i] - start_times[i]
        return total_time, len(start_times)

    def surplus_region_time():
        start_times = region_map['surplus']['starts']
        end_times = region_map['surplus']['ends']
        total_time = 0
        for i in range(len(start_times)):
            total_time += end_times[i] - start_times[i]
        return total_time, len(start_times)

    result = {}

    # Here we add the raw totals for skip and subregion to the result dictionary. By raw, we mean that the preprocessing steps below are not done. These items are for diagnostic purposes. 

    result['silence_raw_hour'] = ms2hr(silence_region_time())
    shour, snum = annotated_subregion_time()
    result['num_raw_subregion'], result['subregion_raw_hour'] = snum, ms2hr(shour)

    if not month67:
        # Preprocessing
        remove_subregions_with_surplus()
        remove_regions_nested_in_skip()
        remove_subregions_with_nested_makeup()
        remove_subregions_without_annotations()
        remove_subregions_nested_in_silence_regions()
        remove_silence_regions_outside_subregions()
        result['skip_silence_overlap_hour'] = 0
                      
    else:
        # Preprocessing
        skip_silence_time = skip_silence_overlap_time()
        skip_time = skip_region_time()
        silence_time = silence_region_time()
        result['skip_silence_overlap_hour'] = ms2hr(skip_silence_time)
        
    subregion_time, num_subregion_with_annot = annotated_subregion_time()
    result['subregion_time'] = subregion_time
    result['num_subregion_with_annot'] = num_subregion_with_annot
    result['subregion_time_hour'] = ms2hr(subregion_time)

    skip_time = skip_region_time()
    result['skip_time'] = skip_time
    result['skip_time_hour'] = ms2hr(skip_time)

    silence_time = silence_region_time()
    result['silence_time'] = silence_time
    result['silence_time_hour'] = ms2hr(silence_time)

    extra_time, num_extra_region = extra_region_time()
    result['extra_time'] = extra_time
    result['num_extra_region'] = num_extra_region     
    result['extra_time_hour'] = ms2hr(extra_time)

    makeup_time, num_makeup_region = makeup_region_time()
    result['makeup_time'] = makeup_time
    result['num_makeup_region'] = num_makeup_region          
    result['makeup_time_hour'] = ms2hr(makeup_time)

    surplus_time, num_surplus_region = surplus_region_time()
    result['surplus_time'] = surplus_time
    result['num_surplus_region'] = num_surplus_region
    result['surplus_time_hour'] = ms2hr(surplus_time)

    print(subregion_time, skip_time, silence_time)


    # If the file is not a 6 or 7 month file, we add/subtract regions to get total time.
    if not month67:
        total_time = subregion_time + extra_time + makeup_time + surplus_time - silence_time - skip_time

    # Otherwise, we assume that the entire file was listened to, so we do not touch anything. 
    else:
        total_time = cf.line_map[-1].offset - (skip_time + silence_time - skip_silence_time)
        print('{} - ({} + {} - {}) == {}'.format(cf.line_map[-1].offset, skip_time, silence_time, skip_silence_time, total_time))
        print(cf.line_map[-1].offset - (skip_time + silence_time - skip_silence_time) == total_time)
        
    result['total_listen_time'] = total_time

    result['end_time_hour'] = ms2hr(cf.line_map[-1].offset)

    result['total_listen_time_hour'] = ms2hr(total_time)
    return result

def process_single_file(file, file_path=cha_structure_path):

    print("Checking {}".format(os.path.basename(file)))
    try:
        sequence, cf, subregions = pull_regions(file)
    except Exception as e:
        print(bcolors.FAIL + "Error opening file: {}".format(file) + bcolors.ENDC)
        print sys.exc_info()
        return
    sequence = sequence_minimal_error_sorting(sequence)
    error_list, region_map = sequence_missing_repetition_entry_alert(sequence)
    with open(os.path.join(file_path, os.path.basename(file)+'.txt'), 'w') as f:
        f.write('\n'.join([x[0] + '   ' + str(x[1]) for x in sequence]))
        f.write('\n')
        f.write('\n')
        f.write('\n')
        f.write('\n'.join(error_list))

        if error_list:
            print(bcolors.WARNING + "Finished {0} with errors! Listen time cannot be calculated due to missing starts or ends!\nCheck the {0}.txt file for errors!".format(os.path.basename(file)) + bcolors.ENDC)
            file_with_error.append((os.path.basename(file), error_list))
        
        # If the file with error has a missing start or end error, we cannot correctly process it! So return!
        for item in error_list:
            if 'missing' in item:
                return

        if os.path.basename(file)[3:5] in ['06', '07']:
            listen_time = total_listen_time(cf, region_map, subregions, month67 = True)
        else:
            listen_time = total_listen_time(cf, region_map, subregions)

        f.write('\n')
        f.write('\n'.join(subregions))
            
        listen_time['filename'] = os.path.basename(file)
        listen_time_summary.append(listen_time)
        print("Finished {}".format(os.path.basename(file)) + '\nTotal Listen Time: ' + bcolors.OKGREEN + str(listen_time['total_listen_time_hour'])+bcolors.ENDC)
        print subregions

# Convert milliseconds to hours!
def ms2hr(ms):
    return round(ms / 3600000.0, PRECISION)

# This function replaced redundant chunks of code below in main!
def output(file_with_error, listen_time_summary):
    with open(os.path.join(output_path, 'Error_Summary.txt'), 'w') as f:
        for entry in file_with_error:
            f.write(entry[0]+'\n')
            for error in entry[1]:
                f.write('\t\t\t\t'+error+'\n')
            f.write('\n')

    # Writing to the total listen time summary file
    with open(os.path.join(output_path, 'Total_Listen_Time_Summary.csv'), 'wb') as f:
        writer = csv.DictWriter(f, fieldnames=FIELD_NAMES)
        writer.writeheader()
        listen_time_summary = list(listen_time_summary)
        listen_time_summary.sort(key = lambda k: k['filename'])
        writer.writerows(listen_time_summary)

if __name__ == "__main__":
    path_file = sys.argv[1]
    files = []
    with open(path_file) as f:
        for path in f.readlines():
            path = path.strip()
            files.append(path)
    print("Expected to process {} cha files".format(len(files)))
    # Create output folder if it does not exist
    try:
        output_path = sys.argv[2]
        if output_path.startswith('--'):
            output_path = 'output'
    except:
        output_path = 'output'
    if not os.path.isdir(output_path):
        os.mkdir(output_path)
    if not os.path.isdir(os.path.join(output_path, 'cha_structures')):
        os.mkdir(os.path.join(output_path, 'cha_structures'))
    cha_structure_path = os.path.join(output_path, 'cha_structures')

    if '--fast' in sys.argv:
        global manager
        manager = Manager()
        file_with_error = manager.list()
        listen_time_summary = manager.list()
        original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        p = Pool(6)
	signal.signal(signal.SIGINT, original_sigint_handler)
        try:
            res = p.map(process_single_file, files)
        except KeyboardInterrupt:
            print("Caught KeyboardInterrupt, terminating workers")
            p.terminate()
        else:
            print("Normal termination")
            p.close()
        p.join()

    else:
        file_with_error = []
        listen_time_summary = []

        for file in files:
            process_single_file(file, cha_structure_path)
        
    # We output the findings.
    output(file_with_error, listen_time_summary)

