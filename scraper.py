import os
import sys
import json
import requests

print("--- Starting Ayrshire Transport Scraper ---")

# 1. SECURELY LOAD YOUR API KEY
BODS_API_KEY = os.environ.get("BODS_API_KEY")

if not BODS_API_KEY:
    print("CRITICAL ERROR: BODS_API_KEY is missing from GitHub Secrets.")
    print("Please add it to your Repository Settings -> Secrets -> Actions.")
    sys.exit(1)

# 2. DEFINE NORTH AYRSHIRE BOUNDARIES
MIN_LAT = 55.45   # Southern border
MAX_LAT = 55.88   # Northern border
MIN_LON = -5.00   # Western border
MAX_LON = -4.55   # Eastern border

print("System initialised. North Ayrshire coordinate boundaries locked.")

# 3. FETCH LIVE BUS TRACKING DATA FROM BODS API
print("Connecting to UK Bus Open Data Service...")
bods_url = f"https://bus-data.gov.uk{BODS_API_KEY}"

try:
    response = requests.get(bods_url, timeout=15)
    response.raise_for_status()
    bus_data = response.json()
    print("Successfully downloaded latest national bus location feed.")
except Exception as e:
    print(f"ERROR: Failed to connect to BODS API. Reason: {e}")
    sys.exit(1)

# 4. FILTER BUSES EXCLUSIVELY FOR NORTH AYRSHIRE
ayrshire_buses = []

for vehicle in bus_data.get('lines', []):
    if 'latitude' not in vehicle or 'longitude' not in vehicle:
        continue
        
    lat = float(vehicle['latitude'])
    lon = float(vehicle['longitude'])
    
    if (MIN_LAT <= lat <= MAX_LAT) and (MIN_LON <= lon <= MAX_LON):
        bus_info = {
            "operator": vehicle.get("operator_ref", "Unknown Operator"),
            "line_name": vehicle.get("line_name", "N/A"),
            "destination": vehicle.get("destination_name", "Unknown Destination"),
            "latitude": lat,
            "longitude": lon,
            "vehicle_id": vehicle.get("vehicle_id", "Unknown ID")
        }
        ayrshire_buses.append(bus_info)

print(f"Filtering complete. Found {len(ayrshire_buses)} active buses inside North Ayrshire.")

# 5. SAVE LIVE BUS DATA FOR NEOCITIES
with open("buses.json", "w") as f:
    json.dump(ayrshire_buses, f, indent=4)
print("Saved fresh tracking data to 'buses.json' successfully.")


# 6. FETCH LIVE ROADWORKS FROM THE SCOTTISH ROAD WORKS REGISTER
print("Connecting to Scottish Road Works Register Open Data portal...")
srwr_url = "https://roadworks.scot" 

try:
    response = requests.get(srwr_url, timeout=20)
    response.raise_for_status()
    roadworks_data = response.json()
    print("Successfully downloaded latest national roadworks dataset.")
except Exception as e:
    print(f"WARNING: Could not connect to SRWR server: {e}. Skipping roadworks update.")
    roadworks_data = {}

ayrshire_works = []

for work in roadworks_data.get('data', []):
    if 'latitude' not in work or 'longitude' not in work:
        continue
        
    lat = float(work['latitude'])
    lon = float(work['longitude'])
    
    if (MIN_LAT <= lat <= MAX_LAT) and (MIN_LON <= lon <= MAX_LON):
        work_info = {
            "title": work.get("location_description", "Roadworks"),
            "description": work.get("work_description", "General maintenance"),
            "status": work.get("status_description", "Active"),
            "start_date": work.get("start_date", "Unknown"),
            "end_date": work.get("end_date", "Unknown"),
            "latitude": lat,
            "longitude": lon
        }
        ayrshire_works.append(work_info)

print(f"Filtering complete. Found {len(ayrshire_works)} roadwork sites in North Ayrshire.")

# 7. SAVE ROADWORKS DATA FOR NEOCITIES
with open("roadworks.json", "w") as f:
    json.dump(ayrshire_works, f, indent=4)
print("Saved fresh disruption data to 'roadworks.json' successfully.")
print("--- Scraper Engine Finished Cleanly ---")
