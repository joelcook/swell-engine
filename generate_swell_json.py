import datetime
import json
import os
import sys

import numpy as np
import requests
import xarray as xr

# --- CONFIG ---
OUTPUT_FILE = "public/swell-global.json"
TEMP_GRIB = "temp_swell.grib2"


def download_latest_grib():
    # Try today, then yesterday
    for delta in [0, 1]:
        d = datetime.date.today() - datetime.timedelta(days=delta)
        d_str = d.strftime("%Y%m%d")

        print(f"🌊 Checking NOAA GFSwave for date: {d_str}...")

        # --- THE MODERN URL STRUCTURE ---
        # Base Filter Script
        base_url = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfswave.pl"

        # Directory: /gfs.YYYYMMDD/00/wave/gridded
        # (Note: %2F is encoded '/')
        dir_path = f"%2Fgfs.{d_str}%2F00%2Fwave%2Fgridded"

        # File: gfswave.t00z.global.0p25.f000.grib2
        # (Global 0.25 degree resolution, Forecast Hour 000)
        file_name = "gfswave.t00z.global.0p25.f000.grib2"

        # Full URL with Filters
        # var_HTSGW = Significant Wave Height
        # var_DIRPW = Primary Wave Direction
        filter_url = (
            f"{base_url}?"
            f"file={file_name}&"
            f"dir={dir_path}&"
            f"var_HTSGW=on&var_DIRPW=on&"
            f"all_lev=on&subregion=&leftlon=0&rightlon=360&toplat=90&bottomlat=-90"
        )

        try:
            r = requests.get(filter_url, stream=True)
            if r.status_code == 200:
                # Check for "Error" text in the first few bytes (NOAA sometimes returns 200 OK with "File not found" text)
                first_chunk = next(r.iter_content(chunk_size=128))
                if b"Error" in first_chunk or b"DOCTYPE" in first_chunk:
                    print(f"   ❌ File not ready yet.")
                    continue

                with open(TEMP_GRIB, "wb") as f:
                    f.write(first_chunk)  # Write the chunk we peeked at
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

                # Check file size (valid GRIBs are > 1MB)
                if os.path.getsize(TEMP_GRIB) < 10000:
                    print("   ❌ Downloaded file too small (Invalid)")
                    continue

                print(f"✅ Download successful ({d_str}).")
                return True
            else:
                print(f"   ❌ HTTP {r.status_code}")
        except Exception as e:
            print(f"   ❌ Connection failed: {e}")

    return False


def process_grib():
    print("⚙️  Processing GRIB2 data...")

    try:
        # Open with cfgrib (requires eccodes)
        ds = xr.open_dataset(TEMP_GRIB, engine="cfgrib")
    except Exception as e:
        print(f"❌ Failed to read GRIB. Error: {e}")
        return

    # --- VARIABLE MAPPING ---
    # GFSwave uses specific names:
    # Height: 'swh' (Significant Wave Height)
    # Direction: 'dirpw' (Primary Wave Direction) or 'perpw'

    # Inspect keys if unsure
    keys = list(ds.keys())
    # print(f"   Found variables: {keys}")

    h_key = next((k for k in keys if k in ["swh", "htsgw"]), None)
    d_key = next((k for k in keys if k in ["dirpw", "perpw", "mwd", "wvdir"]), None)

    if not h_key or not d_key:
        print(f"❌ Missing Wave Data. Found: {keys}")
        return

    height = ds[h_key].values
    direction = ds[d_key].values

    # Math: Convert Direction/Height to U/V Vectors
    rads = np.radians(direction)

    # U = -speed * sin(rad)
    # V = -speed * cos(rad)
    u_comp = -height * np.sin(rads)
    v_comp = -height * np.cos(rads)

    # Cleanup NaNs
    u_comp = np.nan_to_num(u_comp, nan=0.0)
    v_comp = np.nan_to_num(v_comp, nan=0.0)

    # Coords
    lat = ds["latitude"].values
    lon = ds["longitude"].values

    # Format for Leaflet-Velocity
    output = [
        {
            "header": {
                "parameterUnit": "m.s-1",
                "parameterNumber": 2,
                "parameterNumberName": "Eastward Swell",
                "dx": float(abs(lon[1] - lon[0])),
                "dy": float(abs(lat[1] - lat[0])),
                "nx": len(lon),
                "ny": len(lat),
                "lo1": float(lon[0]),
                "la1": float(lat[0]),
                "lo2": float(lon[-1]),
                "la2": float(lat[-1]),
                "refTime": datetime.datetime.now().isoformat(),
            },
            "data": u_comp.flatten().tolist(),
        },
        {
            "header": {
                "parameterUnit": "m.s-1",
                "parameterNumber": 3,
                "parameterNumberName": "Northward Swell",
                "dx": float(abs(lon[1] - lon[0])),
                "dy": float(abs(lat[1] - lat[0])),
                "nx": len(lon),
                "ny": len(lat),
                "lo1": float(lon[0]),
                "la1": float(lat[0]),
                "lo2": float(lon[-1]),
                "la2": float(lat[-1]),
                "refTime": datetime.datetime.now().isoformat(),
            },
            "data": v_comp.flatten().tolist(),
        },
    ]

    os.makedirs("public", exist_ok=True)

    print("💾 Saving JSON...")
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f)

    print(f"🎉 Success! Swell data saved to {OUTPUT_FILE}")

    # Cleanup
    if os.path.exists(TEMP_GRIB):
        os.remove(TEMP_GRIB)
    # Remove index file created by cfgrib
    if os.path.exists(TEMP_GRIB + ".idx"):
        os.remove(TEMP_GRIB + ".idx")


if __name__ == "__main__":
    if download_latest_grib():
        process_grib()
