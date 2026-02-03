import numpy as np
import pandas as pd

# --- CONFIGURATION ---
SPOTS_FILE = "master_surf_spots.json"
NOAA_MASTER_URL = "https://www.ndbc.noaa.gov/data/latest_obs/latest_obs.txt"


def scan_the_world():
    print("🌍 1. Loading Surf Spots...")
    try:
        spots_df = pd.read_json(SPOTS_FILE)
    except ValueError:
        print("❌ Error: Run link_and_orient.py first.")
        return

    print("📡 2. Downloading Live Buoy Data...")
    try:
        # Load data, turning 'MM' into NaN
        raw_buoys = pd.read_csv(
            NOAA_MASTER_URL, sep=r"\s+", skiprows=[1], na_values="MM"
        )
    except Exception as e:
        print(f"❌ API Error: {e}")
        return

    # Clean & Rename
    raw_buoys = raw_buoys.rename(
        columns={
            "#STN": "station_id",
            "WDIR": "WindDir",
            "WSPD": "WindSpeed",
            "GST": "WindGust",
            "WVHT": "SwellHeight",
            "DPD": "SwellPeriod",
        }
    )

    # Convert Units
    raw_buoys["WindSpeed"] *= 1.94384
    raw_buoys["WindGust"] *= 1.94384
    raw_buoys["SwellHeight"] *= 3.28084

    # Prep for Merge
    buoy_data = raw_buoys.copy()
    buoy_data["station_id"] = buoy_data["station_id"].astype(str)
    spots_df["primary_buoy_id"] = spots_df["primary_buoy_id"].astype(str)
    spots_df["wind_station_id"] = spots_df["wind_station_id"].astype(str)

    # 3. MERGE
    print("🔗 3. Linking Data...")

    # Merge Swell (Left Join - keep spot even if swell is missing for now)
    df = pd.merge(
        spots_df,
        buoy_data[["station_id", "SwellHeight", "SwellPeriod"]],
        left_on="primary_buoy_id",
        right_on="station_id",
        how="left",
    )

    # Merge Wind (Left Join)
    wind_source = buoy_data[["station_id", "WindSpeed", "WindDir", "WindGust"]]
    df = pd.merge(
        df,
        wind_source,
        left_on="wind_station_id",
        right_on="station_id",
        suffixes=("", "_land"),
        how="left",
    )

    # 4. FILTER GHOSTS (The Fix)
    # We drop spots where WindSpeed is NaN (Missing).
    # This removes Waverider buoys that have no wind sensor.
    initial_count = len(df)

    df = df.dropna(subset=["WindSpeed"])  # <--- THE MAGIC LINE

    print(
        f"   👻 Dropped {initial_count - len(df)} spots with missing/broken wind sensors."
    )
    print(f"   ⚡ Scorable Spots: {len(df)}")

    # Fill remaining NaNs (only Gusts can be 0 if missing)
    df["WindGust"] = df["WindGust"].fillna(0)
    df = df.fillna(0)  # Safety net

    # 5. VECTOR SCORING
    beach_rad = np.radians(90 - df["beach_facing_deg"])
    wind_rad = np.radians(90 - df["WindDir"])

    dot = (np.cos(beach_rad) * np.cos(wind_rad)) + (
        np.sin(beach_rad) * np.sin(wind_rad)
    )

    wind_scores = ((dot * -1) + 1) / 2 * 100

    # Glassy Bonus (Real glassy, not fake glassy)
    wind_scores = np.where(df["WindSpeed"] < 5.0, 100.0, wind_scores)

    # Gust Penalty
    gust_diff = df["WindGust"] - df["WindSpeed"]
    wind_scores = np.where(
        gust_diff > 5.0, wind_scores - (gust_diff - 5.0) * 2, wind_scores
    )
    wind_scores = np.clip(wind_scores, 0, 100)

    # Swell Score
    power = (df["SwellHeight"] ** 2) * df["SwellPeriod"]
    power_scores = np.clip((power / 300.0) * 100.0, 0, 100)

    df["final_score"] = (wind_scores * 0.6) + (power_scores * 0.4)

    # 6. REPORT
    # Filter for significant swell (> 2ft)
    df = df[df["SwellHeight"] > 2.0]

    top_spots = df.sort_values(by="final_score", ascending=False).head(20)

    print("\n🏆 TOP 20 SURF SPOTS (VERIFIED WIND ONLY) 🏆")
    print("-" * 90)
    print(f"{'SCORE':<8} {'NAME':<30} {'SWELL':<18} {'WIND':<15} {'SOURCE'}")
    print("-" * 90)

    for _, row in top_spots.iterrows():
        swell_str = f"{row['SwellHeight']:.1f}ft @ {row['SwellPeriod']:.0f}s"
        wind_str = f"{row['WindSpeed']:.1f}kts"
        sources = f"{row['primary_buoy_id']} + {row['wind_station_id']}"
        print(
            f"{row['final_score']:<8.1f} {row['name']:<30} {swell_str:<18} {wind_str:<15} {sources}"
        )


if __name__ == "__main__":
    scan_the_world()
