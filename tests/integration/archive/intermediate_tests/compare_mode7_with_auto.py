"""Compare Mode 7 (all locations) with auto_vertical_mode results.

This script compares:
1. Mode 7 for all locations (just tested)
2. Auto vertical mode (Mode 7 for mid-lat, Mode 3 for low-lat)

Goal: Determine if Mode 7 is better than Mode 3 for low-latitude locations.
"""

import json
from pathlib import Path

def load_hysplit_web_data(location_name: str):
    """Load HYSPLIT Web comparison data if available."""
    tdump_file = Path(f"tests/integration/hysplit_web_data/tdump_{location_name}.txt")
    if not tdump_file.exists():
        return None
    
    # Parse tdump file (simplified)
    points = []
    with open(tdump_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    # Skip header lines
    data_started = False
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        # HYSPLIT tdump format varies, try to parse
        parts = line.split()
        if len(parts) >= 12:
            try:
                # Typical format: num year month day hour forecast_hour age lat lon height
                hour_idx = parts[0]
                lat = float(parts[9])
                lon = float(parts[10])
                height = float(parts[11])
                
                points.append({
                    'lat': lat,
                    'lon': lon,
                    'height': height
                })
            except (ValueError, IndexError):
                continue
    
    return points


def calculate_errors(pyhysplit_traj, hysplit_web_data):
    """Calculate errors between PyHYSPLIT and HYSPLIT Web."""
    if not hysplit_web_data or not pyhysplit_traj:
        return None
    
    import numpy as np
    
    errors = []
    n_points = min(len(pyhysplit_traj), len(hysplit_web_data))
    
    for i in range(n_points):
        py_point = pyhysplit_traj[i]
        hy_point = hysplit_web_data[i]
        
        # Calculate horizontal distance (Haversine)
        lat1, lon1 = np.radians(py_point['lat']), np.radians(py_point['lon'])
        lat2, lon2 = np.radians(hy_point['lat']), np.radians(hy_point['lon'])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        horizontal_error = 6371.0 * c  # Earth radius in km
        
        # Pressure error (both should be in hPa)
        pressure_error = abs(py_point.get('pressure', 0) - hy_point['height'])
        
        errors.append({
            'horizontal_km': horizontal_error,
            'pressure_hPa': pressure_error
        })
    
    return errors


def compare_results():
    """Compare Mode 7 results with auto_vertical_mode results."""
    
    print("=" * 80)
    print("Comparing Mode 7 (All Locations) vs Auto Vertical Mode")
    print("=" * 80)
    print()
    
    # Load Mode 7 results
    mode7_file = Path("tests/integration/mode7_all_locations_results.json")
    if not mode7_file.exists():
        print("❌ Mode 7 results not found. Run test_mode7_all_locations.py first.")
        return
    
    with open(mode7_file, 'r', encoding='utf-8') as f:
        mode7_results = json.load(f)
    
    # Load auto mode results (if available)
    auto_file = Path("tests/integration/multi_location_24h_results.json")
    auto_results = {}
    if auto_file.exists():
        with open(auto_file, 'r', encoding='utf-8') as f:
            auto_results = json.load(f)
    
    # Analyze by latitude group
    print("1. LATITUDE GROUP ANALYSIS")
    print("-" * 80)
    print()
    
    high_lat_locs = []
    low_lat_locs = []
    
    for loc_name, mode7_data in mode7_results.items():
        if not mode7_data.get('success'):
            continue
        
        lat = mode7_data['lat']
        if lat > 33.5:
            high_lat_locs.append(loc_name)
        else:
            low_lat_locs.append(loc_name)
    
    print(f"High latitude (>33.5°N): {len(high_lat_locs)} locations")
    print(f"  {', '.join(high_lat_locs)}")
    print(f"  Previous mode: Mode 7")
    print(f"  New mode: Mode 7")
    print(f"  Change: None (control group)")
    print()
    
    print(f"Low latitude (≤33.5°N): {len(low_lat_locs)} locations")
    print(f"  {', '.join(low_lat_locs)}")
    print(f"  Previous mode: Mode 3")
    print(f"  New mode: Mode 7")
    print(f"  Change: Mode 3 → Mode 7 (test group)")
    print()
    
    # Compare with HYSPLIT Web data if available
    print("2. COMPARISON WITH HYSPLIT WEB (if available)")
    print("-" * 80)
    print()
    
    has_hysplit_data = False
    mode7_errors = {}
    
    for loc_name, mode7_data in mode7_results.items():
        if not mode7_data.get('success'):
            continue
        
        # Load HYSPLIT Web data
        hysplit_data = load_hysplit_web_data(loc_name)
        if not hysplit_data:
            continue
        
        has_hysplit_data = True
        
        # Calculate errors
        errors = calculate_errors(mode7_data['trajectory'], hysplit_data)
        if errors:
            avg_h_error = sum(e['horizontal_km'] for e in errors) / len(errors)
            avg_p_error = sum(e['pressure_hPa'] for e in errors) / len(errors)
            
            mode7_errors[loc_name] = {
                'horizontal_km': avg_h_error,
                'pressure_hPa': avg_p_error,
                'lat': mode7_data['lat']
            }
    
    if not has_hysplit_data:
        print("⚠️ No HYSPLIT Web data available for comparison.")
        print("   To get HYSPLIT Web data:")
        print("   1. Visit https://www.ready.noaa.gov/HYSPLIT_traj.php")
        print("   2. Run trajectories for each location")
        print("   3. Save tdump files to tests/integration/hysplit_web_data/")
        print()
    else:
        print(f"{'Location':<12} {'Lat':>6} {'Mode':>6} {'H Error':>10} {'P Error':>10}")
        print("-" * 80)
        
        for loc_name, errors in mode7_errors.items():
            mode = "Mode 7"
            print(f"{loc_name:<12} {errors['lat']:>6.1f} {mode:>6} "
                  f"{errors['horizontal_km']:>9.2f} km {errors['pressure_hPa']:>9.2f} hPa")
        
        print()
        
        # Group statistics
        high_lat_errors = [e for loc, e in mode7_errors.items() if e['lat'] > 33.5]
        low_lat_errors = [e for loc, e in mode7_errors.items() if e['lat'] <= 33.5]
        
        if high_lat_errors:
            avg_h_high = sum(e['horizontal_km'] for e in high_lat_errors) / len(high_lat_errors)
            avg_p_high = sum(e['pressure_hPa'] for e in high_lat_errors) / len(high_lat_errors)
            print(f"High latitude average: {avg_h_high:.2f} km, {avg_p_high:.2f} hPa")
        
        if low_lat_errors:
            avg_h_low = sum(e['horizontal_km'] for e in low_lat_errors) / len(low_lat_errors)
            avg_p_low = sum(e['pressure_hPa'] for e in low_lat_errors) / len(low_lat_errors)
            print(f"Low latitude average: {avg_h_low:.2f} km, {avg_p_low:.2f} hPa")
        
        print()
    
    # Summary and recommendation
    print("3. SUMMARY AND RECOMMENDATION")
    print("-" * 80)
    print()
    
    print("Test completed successfully!")
    print()
    print(f"Locations tested: {len(mode7_results)}")
    print(f"  High latitude (Mode 7 → Mode 7): {len(high_lat_locs)}")
    print(f"  Low latitude (Mode 3 → Mode 7): {len(low_lat_locs)}")
    print()
    
    if has_hysplit_data and low_lat_errors:
        print("Low-latitude results with Mode 7:")
        print(f"  Average horizontal error: {avg_h_low:.2f} km")
        print(f"  Average pressure error: {avg_p_low:.2f} hPa")
        print()
        
        # Compare with previous Mode 3 results (from documentation)
        mode3_avg_pressure = 34.9  # From previous analysis
        
        print("Comparison with previous Mode 3:")
        print(f"  Mode 3 pressure error: {mode3_avg_pressure:.1f} hPa")
        print(f"  Mode 7 pressure error: {avg_p_low:.1f} hPa")
        
        if avg_p_low < mode3_avg_pressure:
            improvement = (mode3_avg_pressure - avg_p_low) / mode3_avg_pressure * 100
            print(f"  Improvement: {improvement:.1f}% ✅")
            print()
            print("✅ RECOMMENDATION: Use Mode 7 for all latitudes")
            print("   - Mode 7 performs better than Mode 3 for low latitudes")
            print("   - Simplifies code (no latitude-based selection needed)")
            print("   - Consistent behavior across all locations")
            print()
            print("Next step:")
            print("  Update pyhysplit/engine.py to use Mode 7 for all latitudes")
        else:
            degradation = (avg_p_low - mode3_avg_pressure) / mode3_avg_pressure * 100
            print(f"  Degradation: {degradation:.1f}% ❌")
            print()
            print("❌ RECOMMENDATION: Keep current auto_vertical_mode")
            print("   - Mode 3 still performs better for low latitudes")
            print("   - Continue using latitude-based mode selection")
            print("   - Focus on other improvements (wind field, interpolation)")
    else:
        print("⚠️ Cannot make recommendation without HYSPLIT Web data")
        print()
        print("To complete the analysis:")
        print("  1. Get HYSPLIT Web data for all 8 locations")
        print("  2. Run this script again")
        print("  3. Compare Mode 7 vs Mode 3 for low latitudes")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    compare_results()
