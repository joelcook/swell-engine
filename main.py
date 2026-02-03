import difflib
import sys

import pandas as pd

from core import SPOTS_FILE, calculate_physics_score, fetch_single_station_data


def get_dual_data(spot):
    # Reuse the same fetching logic
    s_id, w_id = str(spot["primary_buoy_id"]), str(spot["wind_station_id"])
    print(f"   🌊 Swell: {s_id} | 💨 Wind: {w_id}")

    s_data = fetch_single_station_data(s_id)
    w_data = fetch_single_station_data(w_id)

    if s_data is None and w_data is None:
        return None

    merged = s_data if s_data is not None else pd.Series(dtype=float)
    if w_data is not None:
        merged["WindSpeed"] = w_data["WindSpeed"]
        merged["WindGust"] = w_data["WindGust"]
        merged["WindDir"] = w_data["WindDir"]

    return merged.fillna(0.0)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(0)

    try:
        df = pd.read_json(SPOTS_FILE)
    except:
        sys.exit(1)

    # Fuzzy Find
    query = sys.argv[1]
    match = df[df["name"].str.lower() == query.lower()]
    if match.empty:
        closest = difflib.get_close_matches(query, df["name"].tolist(), n=1)
        if closest:
            print(f"🔎 Using: {closest[0]}")
            spot = df[df["name"] == closest[0]].iloc[0]
        else:
            sys.exit(1)
    else:
        spot = match.iloc[0]

    # Run Engine
    print(f"\n🏄‍♂️ REPORT: {spot['name'].upper()}")
    data = get_dual_data(spot)

    if data is not None:
        score = calculate_physics_score(
            spot["beach_facing_deg"],
            data["WindDir"],
            data["WindSpeed"],
            data["WindGust"],
            data["SwellHeight"],
            data["SwellPeriod"],
        )
        print(f"⭐ SCORE: {score:.1f}/100")
        print(
            f"🌊 Swell: {data['SwellHeight']:.1f}ft | 💨 Wind: {data['WindSpeed']:.1f}kts"
        )
