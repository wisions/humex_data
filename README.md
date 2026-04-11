# HUMEX -- Human Movement in an Exhibition

HUMEX is a dataset of spatiotemporal trajectories and interaction events derived from video recordings of human movement in an exhibition environment.

The dataset spans **53 recording days** (August 25 -- October 30, 2022) and contains **4,246 visitor trajectories** sampled at ~30 fps.

## Interactive Browser

This repository hosts a Streamlit app for exploring the dataset:

- Browse all tracks for a given day on the exhibition floor plan
- Inspect individual trajectories colour-coded by time
- View per-day statistics and duration distributions

## Data Format

Each trajectory is a CSV file with three columns:

| Column | Description | Units |
|--------|-------------|-------|
| `time_s` | Timestamp | Seconds since midnight |
| `x` | X position | World units (~mm) |
| `y` | Y position | World units (~mm) |

Filenames follow the pattern `YYYYMMDD_track_NNNNN_TT.csv`, where `TT` encodes trajectory type:

| Code | Meaning |
|------|---------|
| AA | Starts and ends inside exhibition |
| AB | Starts inside, ends outside |
| BA | Starts outside, ends inside |
| BB | Starts and ends outside exhibition |

## Running Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## License

CC-BY 4.0
