"""
HUMEX -- Human Movement in an Exhibition
==========================================
Interactive browser for visitor trajectories
recorded in a museum exhibition space (2022).
"""

import io
import zipfile
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from matplotlib.image import imread
from PIL import Image

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent / "data"
ZIP_PATH = DATA_DIR / "selection_export.zip"
FLOOR_IMG_PATH = DATA_DIR / "floor_overlay.png"
LABELS_PATH = DATA_DIR / "floor_overlay_labels.csv"

TYPE_LABELS = {
    "AA": "Inside -> Inside",
    "AB": "Inside -> Outside",
    "BA": "Outside -> Inside",
    "BB": "Outside -> Outside",
}

TYPE_COLORS = {
    "AA": "#1f77b4",
    "AB": "#ff7f0e",
    "BA": "#2ca02c",
    "BB": "#d62728",
}

# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Loading track index from ZIP...")
def load_index():
    """Build an index of all tracks in the ZIP without reading CSV bodies."""
    records = []
    with zipfile.ZipFile(ZIP_PATH) as zf:
        for name in zf.namelist():
            if not name.endswith(".csv"):
                continue
            fname = name.split("/")[-1]
            parts = fname.replace(".csv", "").split("_")
            # YYYYMMDD_track_NNNNN_TT
            date_str = parts[0]
            track_id = int(parts[2])
            ttype = parts[3]
            records.append(
                {
                    "zip_path": name,
                    "date": pd.to_datetime(date_str, format="%Y%m%d").date(),
                    "track_id": track_id,
                    "type": ttype,
                }
            )
    df = pd.DataFrame(records).sort_values(["date", "track_id"]).reset_index(drop=True)
    return df


@st.cache_data(show_spinner="Reading track CSV...")
def load_track(zip_path: str) -> pd.DataFrame:
    """Read a single track CSV from inside the ZIP."""
    with zipfile.ZipFile(ZIP_PATH) as zf:
        with zf.open(zip_path) as f:
            return pd.read_csv(f)


@st.cache_data(show_spinner="Loading tracks for selected day...")
def load_tracks_for_day(date_str: str, index_df: pd.DataFrame) -> dict:
    """Load all tracks for a given date. Returns {zip_path: DataFrame}."""
    subset = index_df[index_df["date"].astype(str) == date_str]
    tracks = {}
    with zipfile.ZipFile(ZIP_PATH) as zf:
        for _, row in subset.iterrows():
            with zf.open(row["zip_path"]) as f:
                tracks[row["zip_path"]] = pd.read_csv(f)
    return tracks


@st.cache_data(show_spinner="Loading floor plan...")
def load_floor_plan():
    img = Image.open(FLOOR_IMG_PATH)
    return np.flipud(np.array(img))


@st.cache_data(show_spinner="Loading region labels...")
def load_labels():
    return pd.read_csv(LABELS_PATH)


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

def plot_tracks_on_floor(
    floor_img,
    tracks: dict,
    index_df: pd.DataFrame,
    labels_df: pd.DataFrame | None = None,
    highlight_zip: str | None = None,
    show_labels: bool = True,
    alpha: float = 0.5,
):
    """Render tracks over the floor plan image."""
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.imshow(floor_img, extent=[0, 6500, 0, 3500], origin="lower", aspect="equal", alpha=0.6)

    for zip_path, tdf in tracks.items():
        row = index_df[index_df["zip_path"] == zip_path].iloc[0]
        color = TYPE_COLORS.get(row["type"], "gray")
        lw = 0.5
        a = alpha * 0.4
        if highlight_zip and zip_path == highlight_zip:
            lw = 2.5
            a = 1.0
        ax.plot(tdf["x"], tdf["y"], color=color, linewidth=lw, alpha=a)

    # Region labels
    if show_labels and labels_df is not None:
        for _, r in labels_df.iterrows():
            if r["name"].startswith("wall_"):
                continue
            cx = r["x"] + r["width"] / 2
            cy = r["y"] + r["height"] / 2
            ax.text(
                cx, cy, r["name"],
                ha="center", va="center", fontsize=7,
                color="white", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="black", alpha=0.5),
            )

    ax.set_xlim(0, 6500)
    ax.set_ylim(0, 3500)
    ax.set_xlabel("X (world units)")
    ax.set_ylabel("Y (world units)")
    ax.set_title("")
    fig.tight_layout()
    return fig


def plot_single_track(floor_img, tdf, ttype, labels_df=None, show_labels=True):
    """Plot one track coloured by time."""
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.imshow(floor_img, extent=[0, 6500, 0, 3500], origin="lower", aspect="equal", alpha=0.6)

    sc = ax.scatter(
        tdf["x"], tdf["y"],
        c=tdf["time_s"], cmap="viridis", s=2, zorder=3,
    )
    ax.plot(tdf["x"], tdf["y"], color="white", linewidth=0.5, alpha=0.4, zorder=2)
    plt.colorbar(sc, ax=ax, label="time_s (seconds since midnight)", shrink=0.8)

    # Start / end markers
    ax.plot(tdf["x"].iloc[0], tdf["y"].iloc[0], "go", ms=10, label="start", zorder=4)
    ax.plot(tdf["x"].iloc[-1], tdf["y"].iloc[-1], "rs", ms=10, label="end", zorder=4)

    if show_labels and labels_df is not None:
        for _, r in labels_df.iterrows():
            if r["name"].startswith("wall_"):
                continue
            cx = r["x"] + r["width"] / 2
            cy = r["y"] + r["height"] / 2
            ax.text(
                cx, cy, r["name"],
                ha="center", va="center", fontsize=7,
                color="white", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="black", alpha=0.5),
            )

    ax.set_xlim(0, 6500)
    ax.set_ylim(0, 3500)
    ax.set_xlabel("X (world units)")
    ax.set_ylabel("Y (world units)")
    ax.legend(loc="upper right")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

st.set_page_config(page_title="HUMEX Data Browser", layout="wide")
st.title("HUMEX -- Human Movement in an Exhibition")

# Check that data files exist
if not ZIP_PATH.exists():
    st.error(
        f"Data file not found: `{ZIP_PATH}`\n\n"
        "Place `selection_export.zip` in the `data/` subfolder next to this script."
    )
    st.stop()
if not FLOOR_IMG_PATH.exists():
    st.error(
        f"Floor plan not found: `{FLOOR_IMG_PATH}`\n\n"
        "Place `floor_overlay.png` in the `data/` subfolder next to this script."
    )
    st.stop()

# Load resources
index_df = load_index()
floor_img = load_floor_plan()
labels_df = load_labels() if LABELS_PATH.exists() else None

# ---- Sidebar filters ----
st.sidebar.header("Filters")

dates = sorted(index_df["date"].unique())
date_labels = [str(d) for d in dates]
selected_date = st.sidebar.selectbox(
    "Recording date",
    date_labels,
    index=0,
)

day_df = index_df[index_df["date"].astype(str) == selected_date]

types_available = sorted(day_df["type"].unique())
selected_types = st.sidebar.multiselect(
    "Trajectory type",
    types_available,
    default=types_available,
    format_func=lambda t: f"{t} -- {TYPE_LABELS.get(t, t)}",
)

show_labels = st.sidebar.checkbox("Show region labels", value=True)

filtered = day_df[day_df["type"].isin(selected_types)]

st.sidebar.markdown("---")
st.sidebar.markdown(
    f"**{len(filtered)}** tracks on {selected_date}  \n"
    f"**{len(index_df)}** tracks total across {len(dates)} days"
)

# ---- Legend ----
legend_md = " | ".join(
    f"**{code}** {TYPE_LABELS[code]}" for code in ["AA", "AB", "BA", "BB"]
)
st.caption(f"Type legend: {legend_md}")

# ---- Main view tabs ----
tab_all, tab_single, tab_stats = st.tabs(["All tracks", "Single track", "Day statistics"])

with tab_all:
    if len(filtered) == 0:
        st.info("No tracks match the current filters.")
    else:
        tracks = load_tracks_for_day(selected_date, filtered)
        fig = plot_tracks_on_floor(floor_img, tracks, filtered, labels_df, show_labels=show_labels)
        st.pyplot(fig)
        plt.close(fig)

with tab_single:
    if len(filtered) == 0:
        st.info("No tracks match the current filters.")
    else:
        track_options = [
            f"{r['track_id']:05d} ({r['type']})"
            for _, r in filtered.iterrows()
        ]
        sel_idx = st.selectbox("Select track", range(len(track_options)), format_func=lambda i: track_options[i])
        row = filtered.iloc[sel_idx]
        tdf = load_track(row["zip_path"])

        duration = tdf["time_s"].iloc[-1] - tdf["time_s"].iloc[0]
        n_points = len(tdf)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Duration", f"{duration:.1f} s")
        col2.metric("Points", f"{n_points:,}")
        col3.metric("Type", f"{row['type']} -- {TYPE_LABELS[row['type']]}")
        col4.metric("Track ID", f"{row['track_id']:05d}")

        fig = plot_single_track(floor_img, tdf, row["type"], labels_df, show_labels=show_labels)
        st.pyplot(fig)
        plt.close(fig)

        with st.expander("Raw data"):
            st.dataframe(tdf, use_container_width=True)

with tab_stats:
    st.subheader(f"Statistics for {selected_date}")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Tracks by type**")
        type_counts = day_df["type"].value_counts().sort_index()
        st.bar_chart(type_counts)

    with col2:
        st.markdown("**Tracks per day (full dataset)**")
        per_day = index_df.groupby("date").size().reset_index(name="tracks")
        per_day["date"] = pd.to_datetime(per_day["date"])
        chart_df = per_day.set_index("date")
        st.line_chart(chart_df)

    st.markdown("**Duration distribution (selected day)**")
    if len(filtered) > 0:
        tracks_day = load_tracks_for_day(selected_date, filtered)
        durations = []
        for zp, tdf in tracks_day.items():
            durations.append(tdf["time_s"].iloc[-1] - tdf["time_s"].iloc[0])
        fig_hist, ax_hist = plt.subplots(figsize=(8, 3))
        ax_hist.hist(durations, bins=30, edgecolor="white")
        ax_hist.set_xlabel("Duration (s)")
        ax_hist.set_ylabel("Count")
        fig_hist.tight_layout()
        st.pyplot(fig_hist)
        plt.close(fig_hist)
