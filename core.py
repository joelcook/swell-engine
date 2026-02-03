import numpy as np
import pandas as pd

# --- CONFIGURATION ---
SPOTS_FILE = "master_surf_spots.json"


def fetch_single_station_data(station_id):
    """
    Fetches live data for a single station ID from NOAA.
    Used by: main.py, api.py
    """
    url = f"https://www.ndbc.noaa.gov/data/realtime2/{station_id}.txt"
    try:
        df = pd.read_csv(url, sep=r"\s+", skiprows=[1], na_values="MM")
        df = df.rename(
            columns={
                "WDIR": "WindDir",
                "WSPD": "WindSpeed",
                "GST": "WindGust",
                "WVHT": "SwellHeight",
                "DPD": "SwellPeriod",
            }
        )
        # Convert Units
        df["WindSpeed"] *= 1.94384  # m/s -> knots
        df["WindGust"] *= 1.94384
        df["SwellHeight"] *= 3.28084  # m -> ft

        return df.iloc[0].copy()
    except Exception:
        return None


def calculate_physics_score(
    beach_facing_deg, wind_dir, wind_speed, wind_gust, swell_height, swell_period
):
    """
    The Universal Physics Engine.
    Magic: This works for a SINGLE number (float) OR an entire COLUMN (pandas Series).
    """
    # 1. Geometry (Vector Math)
    beach_rad = np.radians(90 - beach_facing_deg)
    wind_rad = np.radians(90 - wind_dir)

    # Dot Product (Element-wise multiplication allows this to work on Arrays too)
    dot = (np.cos(beach_rad) * np.cos(wind_rad)) + (
        np.sin(beach_rad) * np.sin(wind_rad)
    )

    # Wind Quality Score (100 = Offshore, 0 = Onshore)
    wind_score = ((dot * -1) + 1) / 2 * 100

    # 2. Penalties using np.where (Safe for Arrays and Scalars)
    # Glassy Bonus: If wind < 5, force score to 100
    wind_score = np.where(wind_speed < 5.0, 100.0, wind_score)

    # Gust Penalty
    gust_diff = wind_gust - wind_speed
    penalty = (gust_diff - 5.0) * 2.0
    penalty = np.where(penalty < 0, 0, penalty)  # Clamp at 0

    # Apply penalty only if gust_diff > 5
    wind_score = np.where(gust_diff > 5.0, wind_score - penalty, wind_score)

    # FIX: Corrected variable name from wind_scores -> wind_score
    wind_score = (
        np.clip(wind_score, 0, 100)
        if isinstance(wind_score, np.ndarray)
        else max(0, min(100, wind_score))
    )

    # 3. Swell Power Score
    power = (swell_height**2) * swell_period
    power_score = (power / 300.0) * 100.0
    power_score = (
        np.clip(power_score, 0, 100)
        if isinstance(power_score, np.ndarray)
        else min(power_score, 100)
    )

    # 4. Final Weighted Score
    final = (wind_score * 0.6) + (power_score * 0.4)

    return final
