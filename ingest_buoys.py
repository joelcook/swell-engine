import json
import re
import sys

import requests

# --- CONFIGURATION ---
URL = "https://www.ndbc.noaa.gov/data/stations/station_table.txt"
OUTPUT_FILE = "all_noaa_buoys.json"

# Regex to find coordinates
COORD_PATTERN = re.compile(r"(\d+\.\d+)\s+([NS])\s+(\d+\.\d+)\s+([EW])")


def ingest():
    print(f"🌊 Downloading Station Table from NOAA...")

    try:
        response = requests.get(URL)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Error downloading: {e}")
        sys.exit(1)

    lines = response.text.splitlines()
    buoys = []

    print(f"   Parsing {len(lines)} lines...")

    for line in lines:
        if line.startswith("#"):
            continue

        # FIX: We now accept lines that contain "buoy" OR "c-man" OR "station"
        # Actually, let's just accept anything with valid coordinates.

        parts = line.split()
        if len(parts) < 3:
            continue

        raw_id = parts[0]

        # Clean the Name
        clean_id = raw_id
        clean_name = f"NOAA Station {clean_id}"

        if "|" in raw_id:
            id_parts = raw_id.split("|")
            clean_id = id_parts[0]
            if len(id_parts) >= 3:
                clean_name = id_parts[2]

        # Find Coordinates
        match = COORD_PATTERN.search(line)
        if match:
            lat_val, lat_dir, lon_val, lon_dir = match.groups()
            lat, lon = float(lat_val), float(lon_val)
            if lat_dir == "S":
                lat = -lat
            if lon_dir == "W":
                lon = -lon

            buoys.append(
                {"station_id": clean_id, "name": clean_name, "lat": lat, "lon": lon}
            )

    # Save
    with open(OUTPUT_FILE, "w") as f:
        json.dump(buoys, f, indent=2)

    print(
        f"✅ Success! Extracted {len(buoys)} stations (Buoys + Land) to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    ingest()
