# HUMEX — Human Movement in an Exhibition

HUMEX is a dataset of visitor trajectories recorded in a single gallery of a museum exhibition space.

**5,459 trajectories · 53 recording days · 25 August – 30 October 2022 · ~15.8 million position samples**

Each trajectory is one visitor's path across the room, sampled at 30 Hz as time and two-dimensional floor position. Ten overhead cameras covered the gallery; positions were recovered by pose estimation, projected into a shared floor-plane frame, and merged across cameras into continuous paths.

| | |
|---|---|
| **Browse the data online** | https://humex-data.streamlit.app |
| **Technical report** | [REPORT.md](REPORT.md) — what is in the release, how it was produced, how to read it |
| **Project page** | https://osf.io/7f5du |
| **This repository** | https://github.com/wisions/humex_data |

## Contents

| File | Size | Contents |
|---|---:|---|
| `data/humex_trajectories_202208.zip` | 14.6 MB | 617 trajectories, 7 days |
| `data/humex_trajectories_202209.zip` | 78.4 MB | 3,323 trajectories, 28 days |
| `data/humex_trajectories_202210.zip` | 41.4 MB | 1,519 trajectories, 18 days |
| `data/trajectory_index.csv` | 0.5 MB | one row per trajectory with its shape features |
| `data/recording_start.csv` | 2 KB | per day, the clock time at which `time_s = 0` |
| `data/floor_overlay.png` | 98 KB | gallery floor plan, 6480 × 3496 px |
| `data/floor_overlay_labels.csv` | 1.5 KB | 19 named regions with bounding boxes |
| `REPORT.md` | — | technical report: contents, format, composition, method |

Trajectories are archived one zip per calendar month. Each is an independent, ordinary zip — not a binary fragment — so unpack whichever months you need:

```bash
unzip -q 'data/humex_trajectories_2022*.zip' -d tracks/
ls tracks/ | wc -l        # 5459
```

Filenames carry the full date, so months can be unpacked into one directory without collision.

## Trajectory format

One CSV per visitor, three columns, uniformly sampled at 30 Hz:

```csv
time_s,x,y
27340.667,815.98,779.65
27340.700,816.52,780.75
```

Filenames are `YYYYMMDD_track_NNNNN_TT.csv`. The track number is a **per-day index** — combine it with the date to key a trajectory uniquely.

### Coordinates

Pixels of `floor_overlay.png`, mapping 1:1. Origin at the **bottom-left**, **y increases upward**. **One unit = 3.175 mm**, so multiply by `0.003175` for meters. The gallery interior is about 17.4 × 7.9 m.

Reconstructed positions reach outside the nominal plan — x from −837 to 6,392 and y from 208 to 5,323 — mostly near walls and at the margins of camera coverage. About 2 % of samples fall outside the 6480 × 3496 box. Plots with axes fixed to the plan will hide them.

### Time

`time_s` is **seconds since that day's recording began**, not since midnight. Recording started between 09:59 and 11:02 depending on the day, so `time_s = 0` is a different clock time on different days. Add the day's offset from `recording_start.csv` for wall-clock time:

```python
starts = pd.read_csv("data/recording_start.csv").set_index("day")["recording_start_s"]
clock = track["time_s"] + starts[20220913]     # seconds since midnight, local
```

Comparing time of day across days without this correction introduces an offset of up to an hour.

### Trajectory classes

`TT` records the zone where the trajectory began and ended. **Zone A** is the entrance corner (`x < 1000, y < 1500`), **Zone B** the exit corner (`x > 5000, y > 2500`). Both lie inside the gallery — the codes say which **end of the room**, not inside versus outside.

| Code | Meaning | Count |
|---|---|---:|
| `AB` | entrance → exit, a full crossing | 1,431 |
| `BA` | exit → entrance, the reverse crossing | 2,087 |
| `AA` | entered and returned at the entrance end | 1,061 |
| `BB` | entered and returned at the exit end | 880 |

Full crossings are 64.4 % of the set.

## Interactive browser

A deployed copy runs at **https://humex-data.streamlit.app** — nothing to install. `app.py` is its source: trajectories on the floor plan, all tracks for a day, single tracks colored by time, and per-day statistics. To run it locally:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Notes for use

- **Convert units and time first.** Coordinates × 3.175 mm for meters; add the day's recording offset for wall-clock time.
- **Samples mix observed and interpolated positions.** The released CSVs do not distinguish them.
- **Expect occasional discontinuities** where averaging transfers between camera fragments. A peak-speed check around 3 m/s flags most of them.
- **The set is selected, not exhaustive.** It is not every visitor who entered the gallery, and class proportions reflect that selection rather than visitor behavior.
- **The gallery was closed on Wednesdays**, which accounts for the thinnest days.
- **Nothing identifies anyone.** Only anonymous floor positions were retained; no images, faces or identities are in the dataset or were kept at any stage.

## License

CC-BY 4.0.
