"""
HUMEX -- Human Movement in an Exhibition
========================================
Interactive browser for visitor trajectories recorded in a museum gallery (2022).
"""

import glob
import zipfile
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent / "data"
ZIP_GLOB = str(DATA_DIR / "humex_trajectories_*.zip")
FLOOR_IMG_PATH = DATA_DIR / "floor_overlay.png"
LABELS_PATH = DATA_DIR / "floor_overlay_labels.csv"
STARTS_PATH = DATA_DIR / "recording_start.csv"

# Floor plan is 6480 x 3496 px, 1 px = 3.175 mm. Reconstructed positions reach
# outside the plan near walls and at the margins of camera coverage, so the
# view is deliberately wider than the plan -- see the README.
UNIT_MM = 3.175
PLAN_W, PLAN_H = 6480, 3496
VIEW = (-950, 6550, -80, 4600)

REPO_URL = "https://github.com/wisions/humex_data"
REPORT_URL = "https://github.com/wisions/humex_data/blob/main/REPORT.md"
OSF_URL = "https://osf.io/7f5du"

TYPE_LABELS = {
    "AB": "entrance -> exit",
    "BA": "exit -> entrance",
    "AA": "return at entrance",
    "BB": "return at exit",
}

TYPE_COLORS = {
    "AB": "#0072B2",
    "BA": "#D55E00",
    "AA": "#009E73",
    "BB": "#785EF0",
}

# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Indexing trajectory archives...")
def load_index():
    """Index every trajectory across the monthly archives, without reading bodies."""
    records = []
    for zp in sorted(glob.glob(ZIP_GLOB)):
        with zipfile.ZipFile(zp) as zf:
            for name in zf.namelist():
                if not name.endswith(".csv"):
                    continue
                parts = name.split("/")[-1][:-4].split("_")
                records.append(
                    {
                        "archive": zp,
                        "zip_path": name,
                        "date": pd.to_datetime(parts[0], format="%Y%m%d").date(),
                        "track_id": int(parts[2]),
                        "type": parts[3],
                    }
                )
    if not records:
        return pd.DataFrame(columns=["archive", "zip_path", "date", "track_id", "type"])
    return pd.DataFrame(records).sort_values(["date", "track_id"]).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_track(archive: str, zip_path: str) -> pd.DataFrame:
    with zipfile.ZipFile(archive) as zf:
        with zf.open(zip_path) as f:
            return pd.read_csv(f)


@st.cache_data(show_spinner="Loading tracks for the selected day...")
def load_tracks_for_day(date_str: str, index_df: pd.DataFrame) -> dict:
    subset = index_df[index_df["date"].astype(str) == date_str]
    tracks = {}
    for archive, grp in subset.groupby("archive"):
        with zipfile.ZipFile(archive) as zf:
            for _, row in grp.iterrows():
                with zf.open(row["zip_path"]) as f:
                    tracks[row["zip_path"]] = pd.read_csv(f)
    return tracks


@st.cache_data(show_spinner=False)
def load_floor_plan():
    return np.flipud(np.array(Image.open(FLOOR_IMG_PATH)))


@st.cache_data(show_spinner=False)
def load_labels():
    return pd.read_csv(LABELS_PATH) if LABELS_PATH.exists() else None


@st.cache_data(show_spinner=False)
def load_recording_starts():
    """day -> seconds since midnight at which time_s == 0 on that day."""
    if not STARTS_PATH.exists():
        return {}
    df = pd.read_csv(STARTS_PATH)
    return {str(r.day): int(r.recording_start_s) for r in df.itertuples()}


def clock(time_s: float, day: str, starts: dict) -> str:
    """Render a time_s value as local wall-clock time, when the offset is known."""
    off = starts.get(day.replace("-", ""))
    if off is None:
        return "n/a"
    t = int(time_s + off)
    return f"{t // 3600:02d}:{(t % 3600) // 60:02d}:{t % 60:02d}"


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def _draw_floor(ax, floor_img, labels_df, show_labels):
    ax.imshow(floor_img, extent=[0, PLAN_W, 0, PLAN_H], origin="lower",
              aspect="equal", alpha=0.6, zorder=1)
    if show_labels and labels_df is not None:
        for _, r in labels_df.iterrows():
            if r["name"].startswith("wall_"):
                continue
            ax.text(r["x"] + r["width"] / 2, r["y"] + r["height"] / 2, r["name"],
                    ha="center", va="center", fontsize=7, color="white",
                    fontweight="bold", zorder=6,
                    bbox=dict(boxstyle="round,pad=0.2", fc="black", alpha=0.5))
    ax.set_xlim(VIEW[0], VIEW[1])
    ax.set_ylim(VIEW[2], VIEW[3])
    ax.set_xlabel("x (floor-plan units, 1 unit = 3.175 mm)")
    ax.set_ylabel("y (floor-plan units)")


def plot_tracks_on_floor(floor_img, tracks, index_df, labels_df=None,
                         highlight_zip=None, show_labels=True, alpha=0.5):
    fig, ax = plt.subplots(figsize=(12, 7))
    _draw_floor(ax, floor_img, labels_df, show_labels)
    for zip_path, tdf in tracks.items():
        row = index_df[index_df["zip_path"] == zip_path].iloc[0]
        color = TYPE_COLORS.get(row["type"], "gray")
        lw, a = (2.5, 1.0) if highlight_zip == zip_path else (0.5, alpha * 0.4)
        ax.plot(tdf["x"], tdf["y"], color=color, linewidth=lw, alpha=a, zorder=4)
    fig.tight_layout()
    return fig


def plot_single_track(floor_img, tdf, labels_df=None, show_labels=True):
    fig, ax = plt.subplots(figsize=(12, 7))
    _draw_floor(ax, floor_img, labels_df, show_labels)
    sc = ax.scatter(tdf["x"], tdf["y"], c=tdf["time_s"], cmap="viridis", s=2, zorder=5)
    ax.plot(tdf["x"], tdf["y"], color="white", linewidth=0.5, alpha=0.4, zorder=4)
    plt.colorbar(sc, ax=ax, label="time_s (seconds since recording start)", shrink=0.8)
    ax.plot(tdf["x"].iloc[0], tdf["y"].iloc[0], "o", color="#00a070", ms=10,
            label="start", zorder=7)
    ax.plot(tdf["x"].iloc[-1], tdf["y"].iloc[-1], "s", color="#d02020", ms=10,
            label="end", zorder=7)
    ax.legend(loc="upper right")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.set_page_config(page_title="HUMEX Data Browser", layout="wide")
st.title("HUMEX -- Human Movement in an Exhibition")

if not glob.glob(ZIP_GLOB):
    st.error(
        f"No trajectory archives found in `{DATA_DIR}`.\n\n"
        "Expected one or more `humex_trajectories_YYYYMM.zip` files."
    )
    st.stop()
if not FLOOR_IMG_PATH.exists():
    st.error(f"Floor plan not found: `{FLOOR_IMG_PATH}`")
    st.stop()

index_df = load_index()
floor_img = load_floor_plan()
labels_df = load_labels()
starts = load_recording_starts()

st.sidebar.header("Filters")
dates = sorted(index_df["date"].unique())
selected_date = st.sidebar.selectbox("Recording date", [str(d) for d in dates], index=0)
day_df = index_df[index_df["date"].astype(str) == selected_date]

types_available = sorted(day_df["type"].unique())
selected_types = st.sidebar.multiselect(
    "Trajectory type", types_available, default=types_available,
    format_func=lambda t: f"{t} -- {TYPE_LABELS.get(t, t)}",
)
show_labels = st.sidebar.checkbox("Show region labels", value=True)
filtered = day_df[day_df["type"].isin(selected_types)]

st.sidebar.markdown("---")
st.sidebar.markdown(
    f"**{len(filtered)}** tracks on {selected_date}  \n"
    f"**{len(index_df):,}** tracks total across {len(dates)} days"
)
if starts.get(selected_date.replace("-", "")) is not None:
    st.sidebar.caption(
        f"Recording that day began at "
        f"{clock(0, selected_date, starts)} local time."
    )

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**About HUMEX**  \n"
    "[Technical report](%s)  \n"
    "[Data and source on GitHub](%s)  \n"
    "[Project page on OSF](%s)" % (REPORT_URL, REPO_URL, OSF_URL)
)
st.sidebar.caption("Released under CC-BY 4.0.")

st.caption(
    "Type legend: "
    + " | ".join(f"**{c}** {TYPE_LABELS[c]}" for c in ["AB", "BA", "AA", "BB"])
    + ". Zone A is the entrance corner, zone B the exit corner; both are inside the gallery."
)

tab_all, tab_single, tab_stats = st.tabs(["All tracks", "Single track", "Day statistics"])

with tab_all:
    if len(filtered) == 0:
        st.info("No tracks match the current filters.")
    else:
        tracks = load_tracks_for_day(selected_date, filtered)
        fig = plot_tracks_on_floor(floor_img, tracks, filtered, labels_df,
                                   show_labels=show_labels)
        st.pyplot(fig)
        plt.close(fig)

with tab_single:
    if len(filtered) == 0:
        st.info("No tracks match the current filters.")
    else:
        options = [f"{r['track_id']:05d} ({r['type']})" for _, r in filtered.iterrows()]
        sel = st.selectbox("Select track", range(len(options)),
                           format_func=lambda i: options[i])
        row = filtered.iloc[sel]
        tdf = load_track(row["archive"], row["zip_path"])

        duration = tdf["time_s"].iloc[-1] - tdf["time_s"].iloc[0]
        path_m = float(np.hypot(np.diff(tdf["x"]), np.diff(tdf["y"])).sum()) * UNIT_MM / 1000
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Duration", f"{duration:.1f} s")
        c2.metric("Path length", f"{path_m:.1f} m")
        c3.metric("Type", f"{row['type']} -- {TYPE_LABELS[row['type']]}")
        c4.metric("Starts at", clock(tdf["time_s"].iloc[0], selected_date, starts))

        fig = plot_single_track(floor_img, tdf, labels_df, show_labels=show_labels)
        st.pyplot(fig)
        plt.close(fig)

        with st.expander("Raw data"):
            st.dataframe(tdf, use_container_width=True)

with tab_stats:
    st.subheader(f"Statistics for {selected_date}")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Tracks by type**")
        st.bar_chart(day_df["type"].value_counts().sort_index())
    with col2:
        st.markdown("**Tracks per day (full dataset)**")
        per_day = index_df.groupby("date").size().reset_index(name="tracks")
        per_day["date"] = pd.to_datetime(per_day["date"])
        st.line_chart(per_day.set_index("date"))

    st.markdown("**Duration distribution (selected day)**")
    if len(filtered) > 0:
        tracks_day = load_tracks_for_day(selected_date, filtered)
        durations = [t["time_s"].iloc[-1] - t["time_s"].iloc[0] for t in tracks_day.values()]
        fig_hist, ax_hist = plt.subplots(figsize=(8, 3))
        ax_hist.hist(durations, bins=30, edgecolor="white")
        ax_hist.set_xlabel("Duration (s)")
        ax_hist.set_ylabel("Count")
        fig_hist.tight_layout()
        st.pyplot(fig_hist)
        plt.close(fig_hist)
