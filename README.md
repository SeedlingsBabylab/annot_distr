### recap_regions.py
This script outputs csv files specifying different regions of all cha files in the input directory. recap_regions.csv is the output csv, regions_issue.csv is the file for errors.  
```
python recap_regions.py path/to/cha/directory
```

### recap_regions_overlap_check.py
This script outputs a bunch of txt files (to the "../output/"), and a summary txt file. They show the structure of each cha file and detects potential issues with the comments that mark the begin or end of a region.
```
python recap_regions_overlap_check.py file_containing_paths_to_cha_files
```

### recap_regions_listen_time_compute.py
This script outputs a bunch of txt files that are exactly the same as those produced by the previous script, and in addition produces a csv file that summaries the total listen time for **each cha file that is error free** (it will skip those with errors).
```
python recap_regions_listen_time_compute.py file_containing_paths_to_cha_files
```
There are a few points to note for the processing logic:  
* each remark (i.e. subregion, skip, makeup, etc) is given a rank relative to others, so that when sorted, we make sure that they are correctly bracketed within one another
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
