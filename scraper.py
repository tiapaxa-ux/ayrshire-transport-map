import os
import sys
import json
import requests
import xml.etree.ElementTree as ET

print("--- Starting Ayrshire Transport Scraper ---")

# 1. SECURELY LOAD YOUR API KEY
BODS_API_KEY = os.environ.get("BODS_API_KEY")

if not BODS_API_KEY:
    print("CRITICAL ERROR: BODS_API_KEY is missing from GitHub Secrets.")
    sys.exit(1)

# 2. DEFINE NORTH AYRSHIRE BOUNDARIES (approximate rectangle, includes Arran/Cumbrae)
MIN_LAT = 55.45
MAX_LAT = 55.90
MIN_LON = -5.40
MAX_LON = -4.55

print("System initialised. North Ayrshire coordinate boundaries locked.")


def xml_text(node, path, default, ns):
    """Return the text of a child element, or a default if missing/empty."""
    el = node.find(path, ns)
    return el.text if el is not None and el.text else default


# 3. FETCH LIVE BUS TRACKING DATA FROM BODS API (SIRI-VM XML)
print("Connecting to UK Bus Open Data Service...")
BODS_URL = "https://data.bus-data.dft.gov.uk/api/v1/datafeed/"
bods_params = {
    "api_key": BODS_API_KEY,
    # order: minLon, minLat, maxLon, maxLat
    "boundingBox": f"{MIN_LON},{MIN_LAT},{MAX_LON},{MAX_LAT}",
}

try:
    response = requests.get(BODS_URL, params=bods_params, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    print("Successfully downloaded latest bus location feed.")
except Exception as e:
    # type(e).__name__ avoids printing a URL that contains the API key
    print(f"ERROR: Failed to get BODS data. Reason: {type(e).__name__}")
    sys.exit(1)

# 4. FILTER BUSES EXCLUSIVELY FOR NORTH AYRSHIRE
SIRI = {"s": "http://www.siri.org.uk/siri"}
ayrshire_buses = []

for activity in root.iterfind(".//s:VehicleActivity", SIRI):
    journey = activity.find("s:MonitoredVehicleJourney", SIRI)
    if journey is None:
        continue

    lat_txt = xml_text(journey, "s:VehicleLocation/s:Latitude", None, SIRI)
    lon_txt = xml_text(journey, "s:VehicleLocation/s:Longitude", None, SIRI)
    if lat_txt is None or lon_txt is None:
        continue

    try:
        lat = float(lat_txt)
        lon = float(lon_txt)
    except ValueError:
        continue

    if (MIN_LAT <= lat <= MAX_LAT) and (MIN_LON <= lon <= MAX_LON):
        ayrshire_buses.append({
            "operator": xml_text(journey, "s:OperatorRef", "Unknown Operator", SIRI),
            "line_name": xml_text(
                journey, "s:PublishedLineName",
                xml_text(journey, "s:LineRef", "N/A", SIRI), SIRI),
            "destination": xml_text(journey, "s:DestinationName", "Unknown Destination", SIRI),
            "latitude": lat,
            "longitude": lon,
            "vehicle_id": xml_text(journey, "s:VehicleRef", "Unknown ID", SIRI),
        })

print(f"Filtering complete. Found {len(ayrshire_buses)} active buses inside North Ayrshire.")

# 5. SAVE LIVE BUS DATA FOR NEOCITIES
with open("buses.json", "w") as f:
    json.dump(ayrshire_buses, f, indent=4)
print("Saved fresh tracking data to 'buses.json' successfully.")


# 6. FETCH ROADWORKS FROM THE SCOTTISH ROAD WORKS REGISTER
# NOTE: set SRWR_URL (e.g. as a GitHub secret/variable) to a real JSON endpoint.
# Until it is set, this section is skipped and roadworks.json is left untouched.
SRWR_URL = os.environ.get("SRWR_URL")

# Optional: converts British National Grid eastings/northings to lat/lon.
# Add `pip install pyproj` to your workflow if your data uses them.
try:
    from pyproj import Transformer
    BNG_TO_WGS84 = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
except ImportError:
    BNG_TO_WGS84 = None


def get_coords(work):
    """Return (lat, lon) from a roadworks record, or None if unavailable."""
    try:
        if "latitude" in work and "longitude" in work:
            return float(work["latitude"]), float(work["longitude"])
        if BNG_TO_WGS84 and "easting" in work and "northing" in work:
            lon, lat = BNG_TO_WGS84.transform(float(work["easting"]), float(work["northing"]))
            return lat, lon
    except (ValueError, TypeError):
        pass
    return None


if not SRWR_URL:
    print("SRWR_URL not set. Skipping roadworks update (existing roadworks.json kept).")
else:
    print("Connecting to Scottish Road Works Register Open Data portal...")
    try:
        response = requests.get(SRWR_URL, timeout=30)
        response.raise_for_status()
        roadworks_data = response.json()
        print("Successfully downloaded latest national roadworks dataset.")
    except Exception as e:
        print(f"WARNING: Could not get SRWR data: {type(e).__name__}. Keeping previous roadworks.json.")
        roadworks_data = None

    if roadworks_data is not None:
        # Accept either {"data": [...]} or a bare list
        records = roadworks_data.get("data", []) if isinstance(roadworks_data, dict) else roadworks_data

        ayrshire_works = []
        for work in records:
            coords = get_coords(work)
            if coords is None:
                continue
            lat, lon = coords

            if (MIN_LAT <= lat <= MAX_LAT) and (MIN_LON <= lon <= MAX_LON):
                ayrshire_works.append({
                    "title": work.get("location_description", "Roadworks"),
                    "description": work.get("work_description", "General maintenance"),
                    "status": work.get("status_description", "Active"),
                    "start_date": work.get("start_date", "Unknown"),
                    "end_date": work.get("end_date", "Unknown"),
                    "latitude": lat,
                    "longitude": lon,
                })

        print(f"Filtering complete. Found {len(ayrshire_works)} roadwork sites in North Ayrshire.")

        # 7. SAVE ROADWORKS DATA FOR NEOCITIES
        with open("roadworks.json", "w") as f:
            json.dump(ayrshire_works, f, indent=4)
        print("Saved fresh disruption data to 'roadworks.json' successfully.")

print("--- Scraper Engine Finished Cleanly ---")
