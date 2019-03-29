### recap_regions.py
This script outputs csv files specifying different regions of all cha files in the input directory. recap_regions.csv is the output csv, regions_issue.csv is the file for errors.  
```
python recap_regions.py path/to/cha/directory
```

### recap_regions_overlap_check.py
This script outputs a bunch of txt files and a summary txt file. They show the structure of each cha file and detects potential issues with the comments that mark the begin or end of a region.
```
python recap_regions_overlap_check.py file_containing_paths_to_cha_files [path_to_output_folder]
```
The last parameter is output path and it is optional. By default, the output path will be the current folder/output. If the folder does not exist, it will be created automatically.  

The processing steps:  
1. The script goes through the whole cha file to look for the following types of remarks:  
    * subregion starts, subregion ends
    * makeup begin, makeup end
    * skip begin, skip end
    * silence start, silence end
    * extra begin, extra end  

    as well as the timestamp associated with all of the above remarks. 
2. The script sort the remarks according to their timestamps and assigned ranks (explained below) in case that two remarks have the same timestamp.
3. The script builds two lists for each type of remark, one for the list of starting times and one for the list of ending times. It then goes through the lists to check whether the length of the two lists match (if not, either region start or region end remarks are missing). When a missing remark is detected, it will attempt to guess which begin or end remark has a missing corresponding end or begin remark. The errors will then be written out to the summary of errors.
### recap_regions_listen_time_compute.py
This script outputs a bunch of txt files that are exactly the same as those produced by the previous script, and in addition produces a csv file that summaries the total listen time for **each cha file that is error free** (it will skip those with errors).
```
python recap_regions_listen_time_compute.py file_containing_paths_to_cha_files [path_to_output_folder] [-fast]
```

The last parameter is output path and it is optional. By default, the output path will be the current folder/output. If the folder does not exist, it will be created automatically.  

If the **-fast** option is used, the script will attempt to process multiple files concurrently. It may or may not work depending on the computer setup. Recommended procedure is to add the **-fast** option at the end since it speeds up the computation 6 folds. If the scripts throw an error, the fall back to running without **-fast**

The processing steps:  
1. The script goes through the whole cha file to look for the following types of remarks:  
    * subregion starts, subregion ends
    * makeup begin, makeup end
    * skip begin, skip end
    * silence start, silence end
    * extra begin, extra end  

    as well as the timestamp associated with all of the above remarks. 
2. The script sort the remarks according to their timestamps and assigned ranks (explained below) in case that two remarks have the same timestamp.
3. The script builds two lists for each type of remark, one for the list of starting times and one for the list of ending times. It then goes through the lists to check whether the length of the two lists match (if not, either region start or region end remarks are missing). It is noted as error, and the script will notify the error and stop further processing this script.
4. If no error is found, the script will start computing the total listen time. For month 6 and 7 cha files, the processing steps are different. The more detailed steps are found here (note that all operations are done on the lists created earlier and the original cha files are not modified at all):  
    (If Not Month 6 or Month 7)  
    * Remove all the regions that is completely enclosed in a skip region. (ie. if there is a subregion that is completely inside a skip region, it will be removed and its listen tiime is not computed)
    * If a skip region partially overlaps with any region, only the overlapping part of the skip region is taken into account (this is done by adjusting the start or end time of the skip region). (ie. if the first half of a subregion overlaps with a skip region, then the non-overlapping part of the skip region is discounted)

There are a few points to note for the processing logic:  
* each remark (i.e. subregion, skip, makeup, etc) is given a rank relative to others, so when sorted, we make sure that they are correctly bracketed within one another
* there are a few preprocessing steps before the extraction of total time, and the order in which those steps are preformed cannot be arbitrarily altered

Specifically, the preprocessing steps are:
1. Remove any region that is nested in a skip region, so that we don't tally listen for those regions
2. Remove silence regions that is outside any subregion
3. Remove subregion with nested makeup. When a subregion has makeup region resides within, there should not be any annotations inside the subregion that is outside the makeup region. There will be a separate script to check for outliers


### recap_regions_outside_annotations_check.py
This script outputs a bunch of txt files that are exactly the same as those produced by the previous scripts, and in addition produces a txt that contains a list of cha files that has annotations outside the expected regions (except those before month 8). 
```
python recap_regions_outside_annotations_check.py file_containing_paths_to_cha_files
```
