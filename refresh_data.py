import json
import math

import pandas as pd

# --- CONFIG ---
DATA_URL = "https://www.ndbc.noaa.gov/data/latest_obs/latest_obs.txt"
BUOYS_FILE = "all_noaa_buoys.json"  # We'll keep this as the "Swell" source of truth
SPOTS_FILE = "master_surf_spots.json"


def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(
        math.radians(lat1)
    ) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) * math.sin(dlon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def refresh():
    print("🌊 Downloading Active NOAA Data...")

    # 1. READ RAW DATA
    try:
        df = pd.read_csv(DATA_URL, sep=r"\s+", na_values="MM")
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return

    # Drop rows with no location
    df = df.dropna(subset=["LAT", "LON"])

    # 2. CREATE TWO LISTS
    # List A: Active SWELL Stations (Must have Wave Height)
    swell_df = df.dropna(subset=["WVHT"]).copy()

    # List B: Active WIND Stations (Must have Wind Speed)
    # Note: This list will be much larger (includes piers, airports, C-MAN)
    wind_df = df.dropna(subset=["WSPD"]).copy()

    print(f"    - Raw Stations: {len(df)}")
    print(f"    - Active Swell Sources: {len(swell_df)}")
    print(f"    - Active Wind Sources:  {len(wind_df)}")

    # Helper to convert DataFrame to List of Dicts
    def df_to_list(dataframe):
        stations = []
        for _, row in dataframe.iterrows():
            stations.append(
                {
                    "id": str(row["#STN"]),
                    "lat": float(row["LAT"]),
                    "lon": float(row["LON"]),
                }
            )
        return stations

    swell_stations = df_to_list(swell_df)
    wind_stations = df_to_list(wind_df)

    # Save just the swell stations to the JSON file (for the API to use if needed)
    with open(BUOYS_FILE, "w") as f:
        json.dump(swell_stations, f, indent=2)

    # 3. RELINK SPOTS (Dual-Channel)
    print(f"🔗 Optimizing Spot Connections...")

    with open(SPOTS_FILE, "r") as f:
        spots = json.load(f)

    swell_updates = 0
    wind_updates = 0

    for spot in spots:
        target_lat = spot["lat"]
        target_lon = spot["lng"]

        # --- A. Find Best SWELL Source ---
        best_swell_id = None
        min_swell_dist = float("inf")

        for s in swell_stations:
            dist = haversine(target_lat, target_lon, s["lat"], s["lon"])
            if dist < min_swell_dist:
                min_swell_dist = dist
                best_swell_id = s["id"]

        if best_swell_id and spot.get("primary_buoy_id") != best_swell_id:
            spot["primary_buoy_id"] = best_swell_id
            swell_updates += 1

        # --- B. Find Best WIND Source ---
        best_wind_id = None
        min_wind_dist = float("inf")

        for s in wind_stations:
            dist = haversine(target_lat, target_lon, s["lat"], s["lon"])
            if dist < min_wind_dist:
                min_wind_dist = dist
                best_wind_id = s["id"]

        if best_wind_id and spot.get("wind_station_id") != best_wind_id:
            spot["wind_station_id"] = best_wind_id
            wind_updates += 1

    # 4. SAVE
    with open(SPOTS_FILE, "w") as f:
        json.dump(spots, f, indent=2)

    print(f"✅ Database Optimized.")
    print(f"    - Re-routed {swell_updates} swell connections.")
    print(f"    - Re-routed {wind_updates} wind connections.")
    print("⚡️ RESTART YOUR API NOW.")


if __name__ == "__main__":
    refresh()
