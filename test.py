import pandas as pd


df = pd.read_csv("all_cha_top5_subregions.csv")



df['onset'] = df.orig_index *5*60*1000
df['offset'] = df.onset+3600000

df.to_csv("all_cha_top5_subregions.csv", index=False)
print


