# 🌊 Swell.AI - Sensor Fusion Backend

A high-performance Python surf forecasting engine that uses **Spatial Indexing (KD-Trees)** and **Vector Physics** to generate real-time surf scores.

Unlike standard weather apps that just show "Wind Speed," this engine calculates the **Dot Product** between the wind vector and the beach's specific facing angle to determine the true quality of the wave (Offshore vs. Onshore).

## ⚡ Architecture

1.  **Ingest:** Scrapes 1,000+ NOAA Buoys and C-MAN Stations.
2.  **Link (ETL):** Uses `cKDTree` to map every surf spot to:
    * The nearest **Swell Buoy** (Wave Height/Period).
    * The nearest **Land Station** (Wind Speed/Direction).
3.  **Core:** A shared physics library (`core.py`) that calculates scores.
4.  **Serve:** Exposes data via a **FastAPI** microservice and a CLI tool.

---

## 🛠️ Setup & Installation

### 1. Prerequisites
* Python 3.9+
* Pip

### 2. Install Dependencies
```bash
pip install fastapi uvicorn pandas numpy scipy requests global-land-mask
```
3. Initialize the Data Pipeline (Run Once)

You must run these scripts in order to build the "Smart Database."

Bash
# Step 1: Download raw NOAA station data
```bash
python ingest_buoys.py
```

# Step 2: Link surf spots to sensors & calculate beach angles
```bash
python link_and_orient.py
```
Output: Generates master_surf_spots.json.

🚀 Usage
Option A: The CLI Tool (Quick Check)

Run the engine directly in your terminal for any spot.

```bash
python main.py "Fort Pierce"
```
Option B: The API Server (Production)

Start the FastAPI server to power the Frontend.

```bash
uvicorn api:app --reload
```
API URL: http://127.0.0.1:8000

Swagger Documentation: http://127.0.0.1:8000/docs

Option C: The Global Scanner

Find the top 20 spots in the world right now (filters out broken sensors).

```bash
python scan.py
```
🔌 API Endpoints
GET /search

Fuzzy search for surf spots.

Query: ?q=Pipe

Response: JSON list of matching spots.

GET /live/{spot_name}

Runs the physics engine for a specific spot.

Example: /live/Fort%20Pierce%20North%20Jetty

Response:

JSON
{
  "name": "Fort Pierce North Jetty",
  "score": 61.9,
  "conditions": {
    "swell": "4.3ft @ 13s",
    "wind": "11.7kts"
  }
}
📐 The Physics Engine
The score (0-100) is calculated in core.py using Vector Algebra:

Beach Normal: Converts the beach angle to a unit vector (x,y).

Wind Vector: Converts live wind direction to a unit vector.

Dot Product: Calculates alignment.

100 (Perfect): Wind is directly opposing the waves (Offshore).

0 (Bad): Wind is blowing with the waves (Onshore).

Penalties:

Deductions for Choppiness (Gusts > 5kts over sustained speed).

Bonuses for "Glassy" conditions (< 5kts).

📂 Project Structure
api.py - FastAPI server entry point.

core.py - Shared logic library (Fetching & Math).

main.py - CLI tool.

link_and_orient.py - Spatial linking algorithm.

ingest_buoys.py - Data scraper.

master_surf_spots.json - The database (Generated).
