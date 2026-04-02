import pandas as pd
import os

all_data = []

base_path = "data/player_data"

for root, dirs, files in os.walk(base_path):
    for file in files:
        if file.endswith(".nakama-0"):   # only read data files
            path = os.path.join(root, file)
            df = pd.read_parquet(path, engine="pyarrow")
            all_data.append(df)

# Combine all players
final_df = pd.concat(all_data)

# Decode event column
final_df["event"] = final_df["event"].apply(lambda x: x.decode("utf-8"))

print("TOTAL ROWS:", len(final_df))
print("\nEVENT TYPES:", final_df["event"].unique())
print("\nMAPS:", final_df["map_id"].unique())