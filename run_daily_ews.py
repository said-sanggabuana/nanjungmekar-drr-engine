import whitebox
import os
import datetime
import random
import subprocess

print("--- INITIATING 28-DAY AUTOMATED EWS ENGINE ---")

# ==========================================
# 1. CONFIGURATION
# ==========================================
catchment_mapping = {
    510123511: 1,  # Cikeruh Reach -> Subbasin 1
    510116631: 2   # Cimande Reach -> Subbasin 2
}

wbt = whitebox.WhiteboxTools()
wbt.set_working_dir(os.getcwd())
wbt.verbose = False  # Turned off so the terminal doesn't get flooded

# ==========================================
# 2. MOCK DATA FETCH (Temporary for Phase 1)
# ==========================================
def fetch_mock_forecast(reach_id, day_offset):
    """Simulates a flood wave peaking at Day 0 (Today)."""
    base_flow = 85.2 if reach_id == 510123511 else 120.5
    surge = (15 - abs(day_offset)) * (1.5 if reach_id == 510123511 else 2.0)
    return base_flow + surge + random.uniform(-2, 2)

# ==========================================
# 3. THE TEMPORAL LOOP (-14 to +14 days)
# ==========================================
today = datetime.date.today()
day_offsets = list(range(-14, 15)) 

print("Executing spatial math for 29 days... Grab a coffee.")

for offset in day_offsets:
    target_date = today + datetime.timedelta(days=offset)
    date_str = target_date.strftime("%Y%m%d")
    offset_label = f"minus{abs(offset)}" if offset < 0 else f"plus{offset}" if offset > 0 else "today"
    
    print(f" -> Processing: Day {offset} ({date_str})")

    # A. Get Data & Calibrate Rating Curve
    flow_sub1 = fetch_mock_forecast(510123511, offset)
    flow_sub2 = fetch_mock_forecast(510116631, offset)
    
    stage_sub1 = flow_sub1 * 0.060 
    stage_sub2 = flow_sub2 * 0.025
    
    # B. Float-Point Safe Reclass
    reclass_string = f"{stage_sub1};0.9;1.1;{stage_sub2};1.9;2.1"
    
    # C. Run Spatial Physics
    wbt.reclass(i="7_catchments.tif", output="temp_levels.tif", reclass_vals=reclass_string)
    wbt.subtract("temp_levels.tif", "5_hand.tif", "temp_raw_risk.tif")
    
    # D. Masking
    raw_output = f"raw_flood_{date_str}_{offset_label}.tif"
    wbt.greater_than("temp_raw_risk.tif", 0.0, "temp_mask.tif")
    wbt.multiply("temp_raw_risk.tif", "temp_mask.tif", raw_output)
    
    # E. Reproject to WGS84 and Convert to Cloud Optimized GeoTIFF (COG)
    final_cog_name = f"cog_flood_{date_str}_{offset_label}.tif"
    
    # THE WGS84 FIX: Swapped gdal_translate for gdalwarp and injected -t_srs EPSG:4326
    subprocess.run(
        f"gdalwarp -t_srs EPSG:4326 {raw_output} {final_cog_name} -co TILED=YES -co COMPRESS=DEFLATE", 
        shell=True, 
        capture_output=True
    )
    
    # F. Clean up all temporary files for this day
    for f in ["temp_levels.tif", "temp_raw_risk.tif", "temp_mask.tif", raw_output]:
        if os.path.exists(f): 
            os.remove(f)

print("\nSUCCESS: 29 Cloud Optimized GeoTIFFs have been generated in WGS84.")