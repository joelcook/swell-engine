import json

import numpy as np
import pandas as pd
from global_land_mask import globe
from scipy.spatial import cKDTree

# --- CONFIGURATION ---
SPOTS_FILE = "surf_spots.json"
BUOYS_FILE = "all_noaa_buoys.json"
OUTPUT_FILE = "master_surf_spots.json"


def calculate_beach_angle(lat, lon, radius_km=5.0, num_points=36):
    """Calculates coastline facing angle (0=North, 90=East)"""
    angles = np.linspace(0, 2 * np.pi, num_points, endpoint=False)
    delta_deg = radius_km / 111.0

    sample_lats = lat + delta_deg * np.cos(angles)
    sample_lons = lon + delta_deg * np.sin(angles)

    is_water = globe.is_ocean(sample_lats, sample_lons)

    if np.all(is_water) or not np.any(is_water):
        return -1

    water_angles = angles[is_water]
    avg_north = np.sum(np.cos(water_angles))
    avg_east = np.sum(np.sin(water_angles))

    return np.degrees(np.arctan2(avg_east, avg_north)) % 360


def process_spots():
    print("🔌 Loading Data...")
    try:
        buoys_df = pd.read_json(BUOYS_FILE)
        spots_df = pd.read_json(SPOTS_FILE)
    except ValueError:
        return

    spots_df["lat"] = pd.to_numeric(spots_df["lat"], errors="coerce")
    spots_df["lng"] = pd.to_numeric(spots_df["lng"], errors="coerce")
    spots_df = spots_df.dropna(subset=["lat", "lng"])

    print(f"🔗 Dual-Linking {len(spots_df)} spots with Sensor Diversity...")

    # --- SEARCH 1: FIND BEST SWELL SOURCE (Numeric IDs only) ---
    wave_buoys = buoys_df[buoys_df["station_id"].str.match(r"^\d+$")].copy()
    wave_tree = cKDTree(wave_buoys[["lat", "lon"]].values)

    dists_wave, idxs_wave = wave_tree.query(spots_df[["lat", "lng"]].values, k=1)

    # Store the Swell ID
    swell_ids = wave_buoys.iloc[idxs_wave]["station_id"].values
    spots_df["primary_buoy_id"] = swell_ids

    # --- SEARCH 2: FIND BEST WIND SOURCE (Sensor Diversity) ---
    # We query the closest TWO stations (k=2)
    wind_tree = cKDTree(buoys_df[["lat", "lon"]].values)
    dists_wind, idxs_wind = wind_tree.query(spots_df[["lat", "lng"]].values, k=2)

    final_wind_ids = []

    for i, (nearest_indices, nearest_dists) in enumerate(zip(idxs_wind, dists_wind)):
        swell_id = swell_ids[i]

        # Candidate 1 (Closest)
        cand1_idx = nearest_indices[0]
        cand1_id = buoys_df.iloc[cand1_idx]["station_id"]

        # Candidate 2 (Second Closest)
        cand2_idx = nearest_indices[1]
        cand2_id = buoys_df.iloc[cand2_idx]["station_id"]

        # LOGIC: If the closest wind station is the SAME as the swell buoy,
        # skip it and take the second closest. This forces "Land Station" preference.
        if cand1_id == swell_id:
            final_wind_ids.append(cand2_id)
        else:
            final_wind_ids.append(cand1_id)

    spots_df["wind_station_id"] = final_wind_ids

    # ---------------------------

    print(f"📐 Calculating beach angles...")
    spots_df["beach_facing_deg"] = spots_df.apply(
        lambda row: calculate_beach_angle(row["lat"], row["lng"]), axis=1
    )

    spots_df.to_json(OUTPUT_FILE, orient="records", indent=2)
    print(f"✅ Saved to {OUTPUT_FILE}")

    # Verification
    print("\n🔍 Verification (Ft Pierce):")
    match = spots_df[spots_df["name"].str.contains("Pierce", case=False)]
    if not match.empty:
        print(match[["name", "primary_buoy_id", "wind_station_id"]].head(1))


if __name__ == "__main__":
    process_spots()
