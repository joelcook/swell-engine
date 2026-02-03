import difflib

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from core import SPOTS_FILE, calculate_physics_score, fetch_single_station_data

app = FastAPI(title="Swell AI API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load DB
try:
    spots_df = pd.read_json(SPOTS_FILE)
    print(f"✅ Loaded {len(spots_df)} spots.")
except Exception:
    spots_df = pd.DataFrame()


@app.get("/search")
def search_spots(q: str):
    if spots_df.empty:
        return []
    results = spots_df[spots_df["name"].str.contains(q, case=False, na=False)]
    if results.empty:
        matches = difflib.get_close_matches(
            q, spots_df["name"].tolist(), n=5, cutoff=0.6
        )
        results = spots_df[spots_df["name"].isin(matches)]
    return results[["name", "country", "lat", "lng"]].to_dict(orient="records")


@app.get("/live/{spot_name}")
def get_live_report(spot_name: str):
    # 1. Find Spot
    match = spots_df[spots_df["name"].str.lower() == spot_name.lower()]
    if match.empty:
        raise HTTPException(404, "Spot not found")
    spot = match.iloc[0]

    # 2. Fetch Data (Using Core)
    swell_data = fetch_single_station_data(str(spot["primary_buoy_id"]))
    wind_data = fetch_single_station_data(str(spot["wind_station_id"]))

    if swell_data is None and wind_data is None:
        raise HTTPException(503, "Offline")

    # Merge Logic
    data = swell_data if swell_data is not None else pd.Series(dtype=float)
    if wind_data is not None:
        data["WindSpeed"] = wind_data["WindSpeed"]
        data["WindGust"] = wind_data["WindGust"]
        data["WindDir"] = wind_data["WindDir"]
    data = data.fillna(0.0)

    # 3. Calculate Score (Using Core)
    score = calculate_physics_score(
        spot["beach_facing_deg"],
        data["WindDir"],
        data["WindSpeed"],
        data["WindGust"],
        data["SwellHeight"],
        data["SwellPeriod"],
    )

    return {
        "name": spot["name"],
        "score": round(score, 1),
        "conditions": {
            "swell": f"{data['SwellHeight']:.1f}ft @ {data['SwellPeriod']:.0f}s",
            "wind": f"{data['WindSpeed']:.1f}kts",
        },
    }
