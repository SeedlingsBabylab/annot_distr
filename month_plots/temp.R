library(tidyverse)
library(stringr)

# Read in the csv file of Listen Time summaries
listened_time <- read_csv("../output/Total_Listen_Time_Summary.csv")

# Add column for months
(listened_time_with_months <- listened_time %>% mutate(month = str_match(filename, "_(\\d{2})_")[,2]) %>% select(Filename, month, everything()))


six_seven <- listened_time_with_months %>% filter(month %in% c("06", "07"))
assume16 <- six_seven %>% transmute()
