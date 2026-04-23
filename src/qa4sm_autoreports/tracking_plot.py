import xarray as xr
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

ds = xr.open_dataset("/data-read/USERS/wpreimes/qa4sm_smos_report/02-SmosL2-vs-Era5Land-abs/e95eeaeb-1d2f-43c4-b019-b7f3b3dbd29e.nc")
stats = ds["R_between_0-SMOS_L2_and_1-ERA5_LAND"].isel(tsw=0).to_pandas().dropna().describe()
stats['start_date'] = "2024-07-01"
stats['end_date'] = "2024-09-30"
stats = stats.to_frame().T

df = pd.DataFrame(index=[f'Epoch-{i}' if i != 0 else "Current" for i in range(0, 12) ], columns=stats.columns.values, data=np.nan)
df['start_date'] = df['start_date'].astype(str)
df['end_date'] = df['end_date'].astype(str)
df.loc['Current', :] = stats.iloc[0]


df = df.iloc[:12]  # ensure at most 12 epochs
df = df.iloc[::-1]  # reverse so Epoch-0 is last

stats_list = []

for epoch, row in df.iterrows():
    # If stats are all NaN -> keep empty slot
    if row[['25%', '50%', '75%', 'min', 'max']].isna().all():
        stats_list.append(None)
        continue

    stats = {
        'label': epoch,
        'med': row['50%'],
        'q1': row['25%'],
        'q3': row['75%'],
        'whislo': row['min'],
        'whishi': row['max'],
        'fliers': []
    }
    stats_list.append(stats)


fig, ax = plt.subplots(figsize=(6, 4))

positions = np.arange(len(stats_list)) + 1  # 1-based positions
valid_stats = [s for s in stats_list if s is not None]
valid_positions = [pos for pos, s in zip(positions, stats_list) if s is not None]

# Draw only valid boxes
ax.bxp(valid_stats, positions=valid_positions, showfliers=True)

# Label every position (even empty ones)
ax.set_xticks(positions)
ax.set_xticklabels(df.index, rotation=90, ha='right')

ax.set_title("R tracking")
ax.set_ylabel("R [-]")

plt.tight_layout()
plt.show()

