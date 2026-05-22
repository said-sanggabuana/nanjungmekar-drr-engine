import whitebox
import os
import datetime
import subprocess
import requests # NEW: For fetching live data

print("--- INITIATING 28-DAY AUTOMATED EWS ENGINE (LIVE DATA MODE) ---")

# ==========================================
# 1. CONFIGURATION
# ==========================================
wbt = whitebox.WhiteboxTools()
wbt.set_working_dir(os.getcwd())
wbt.verbose = False 

# Force the engine to use WIB (UTC+7)
wib_timezone = datetime.timezone(datetime.timedelta(hours=7))
today = datetime.datetime.now(wib_timezone).date()

# ==========================================
# 2. FETCH REAL-TIME METEOROLOGICAL DATA
# ==========================================
def fetch_live_rainfall():
    """
    Pulls 14 days past and 14 days future rainfall data (in mm) for the Cicalengka basin.
    """
    print("Fetching live atmospheric data for Cicalengka...")
    LAT = -6.97
    LON = 107.82
    
    # Open-Meteo API: Free, no auth required, perfectly matches our -14 to +14 timeline
    url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&daily=precipitation_sum&past_days=14&forecast_days=15&timezone=Asia%2FJakarta"
    
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"API Fetch Failed: {response.status_code}")
        
    data = response.json()
    dates = data['daily']['time']
    rain_sums = data['daily']['precipitation_sum']
    
    # Create a dictionary mapping the date string (YYYY-MM-DD) to the rainfall in mm
    # If a value is None, default it to 0.0
    return {date: (rain if rain is not None else 0.0) for date, rain in zip(dates, rain_sums)}

# Execute the fetch
rainfall_data = fetch_live_rainfall()

# ==========================================
# 3. THE TEMPORAL LOOP (-14 to +14 days)
# ==========================================
day_offsets = list(range(-14, 15)) 

print("Executing spatial math for 29 days based on live telemetry...")

for offset in day_offsets:
    target_date = today + datetime.timedelta(days=offset)
    
    # Format dates to match the API key (YYYY-MM-DD) and our file outputs (YYYYMMDD)
    api_date_key = target_date.strftime("%Y-%m-%d")
    file_date_str = target_date.strftime("%Y%m%d")
    
    offset_label = f"minus{abs(offset)}" if offset < 0 else f"plus{offset}" if offset > 0 else "today"
    
    # Extract today's actual rainfall from the API payload
    daily_rain_mm = rainfall_data.get(api_date_key, 0.0)
    
    print(f" -> Processing: Day {offset} ({file_date_str}) | Live Rain: {daily_rain_mm} mm")

    # A. Calibrate Rating Curve using REAL Rainfall
    # Base flow (dry day) + (Rainfall * Runoff Multiplier)
    # You will tweak these multipliers based on how the basin actually reacts today!
    flow_sub1 = 85.2 + (daily_rain_mm * 2.5)  # Cikeruh Reach
    flow_sub2 = 120.5 + (daily_rain_mm * 3.0) # Cimande Reach
    
    stage_sub1 = flow_sub1 * 0.060 
    stage_sub2 = flow_sub2 * 0.025
    
    # B. Float-Point Safe Reclass
    reclass_string = f"{stage_sub1};0.9;1.1;{stage_sub2};1.9;2.1"
    
    # C. Run Spatial Physics
    wbt.reclass(i="7_catchments.tif", output="temp_levels.tif", reclass_vals=reclass_string)
    wbt.subtract("temp_levels.tif", "5_hand.tif", "temp_raw_risk.tif")
    
    # D. Masking
    raw_output = f"raw_flood_{file_date_str}_{offset_label}.tif"
    wbt.greater_than("temp_raw_risk.tif", 0.0, "temp_mask.tif")
    wbt.multiply("temp_raw_risk.tif", "temp_mask.tif", raw_output)
    
    # E. Reproject to WGS84 and Convert to COG
    final_cog_name = f"cog_flood_{file_date_str}_{offset_label}.tif"
    
    subprocess.run(
        f"gdalwarp -overwrite -s_srs EPSG:32748 -t_srs EPSG:4326 {raw_output} {final_cog_name} -co TILED=YES -co COMPRESS=DEFLATE", 
        shell=True, 
        check=True
    )
    
    # F. Clean up temporary files
    for f in ["temp_levels.tif", "temp_raw_risk.tif", "temp_mask.tif", raw_output]:
        if os.path.exists(f): 
            os.remove(f)

print("\nSUCCESS: Live telemetry processed. 29 Cloud Optimized GeoTIFFs generated.")