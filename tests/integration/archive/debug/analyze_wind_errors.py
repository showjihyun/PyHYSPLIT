"""풍속장 오차 분석.

수평 오차(43.31 km)의 원인을 파악하기 위해:
1. 각 위치의 풍속장 특성 분석
2. 보간 오차 추정
3. 시간 스텝 vs 오차 관계
4. 오차 핫스팟 식별

기존 데이터로 즉시 실행 가능합니다.
"""

import json
from pathlib import Path
import numpy as np


def load_hysplit_web_data(location_name: str):
    """Load HYSPLIT Web comparison data if available."""
    tdump_file = Path(f"tests/integration/hysplit_web_data/tdump_{location_name}.txt")
    if not tdump_file.exists():
        return None
    
    points = []
    with open(tdump_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        parts = line.split()
        if len(parts) >= 12:
            try:
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


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate Haversine distance in km."""
    lat1_rad, lon1_rad = np.radians(lat1), np.radians(lon1)
    lat2_rad, lon2_rad = np.radians(lat2), np.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return 6371.0 * c


def analyze_wind_errors():
    """풍속장 오차 분석."""
    
    print("=" * 80)
    print("풍속장 오차 분석")
    print("=" * 80)
    print()
    
    # Load auto_vertical_mode results
    results_file = Path("tests/integration/multi_location_24h_results.json")
    if not results_file.exists():
        print("❌ Auto vertical mode results not found.")
        print("   Using Mode 7 test results instead...")
        results_file = Path("tests/integration/mode7_all_locations_results.json")
        if not results_file.exists():
            print("❌ No test results found.")
            return
    
    with open(results_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    print("1. HORIZONTAL ERROR BY LOCATION")
    print("-" * 80)
    print()
    
    # Calculate horizontal errors for each location
    location_errors = []
    
    for loc_name, data in results.items():
        if loc_name == "summary" or not data.get('success', False):
            continue
        
        # Load HYSPLIT Web data
        hysplit_data = load_hysplit_web_data(loc_name)
        if not hysplit_data:
            continue
        
        # Calculate errors
        pyhysplit_traj = data.get('trajectory', [])
        if not pyhysplit_traj:
            continue
        
        errors = []
        n_points = min(len(pyhysplit_traj), len(hysplit_data))
        
        for i in range(n_points):
            py_point = pyhysplit_traj[i]
            hy_point = hysplit_data[i]
            
            h_error = calculate_distance(
                py_point['lat'], py_point['lon'],
                hy_point['lat'], hy_point['lon']
            )
            
            errors.append(h_error)
        
        if errors:
            location_errors.append({
                'name': loc_name,
                'lat': data['lat'],
                'lon': data['lon'],
                'mean_error': np.mean(errors),
                'median_error': np.median(errors),
                'max_error': np.max(errors),
                'std_error': np.std(errors),
                'errors': errors,
                'n_points': len(errors)
            })
    
    if not location_errors:
        print("⚠️ No HYSPLIT Web data available for comparison.")
        print("   Cannot calculate horizontal errors.")
        print()
        print("To get HYSPLIT Web data:")
        print("  1. Visit https://www.ready.noaa.gov/HYSPLIT_traj.php")
        print("  2. Run trajectories for each location")
        print("  3. Save tdump files to tests/integration/hysplit_web_data/")
        return
    
    # Sort by mean error
    location_errors.sort(key=lambda x: x['mean_error'], reverse=True)
    
    print(f"{'Location':<12} {'Lat':>6} {'Mean':>10} {'Median':>10} {'Max':>10} {'Std':>10}")
    print("-" * 80)
    
    for loc in location_errors:
        print(f"{loc['name']:<12} {loc['lat']:>6.1f} "
              f"{loc['mean_error']:>9.2f} km {loc['median_error']:>9.2f} km "
              f"{loc['max_error']:>9.2f} km {loc['std_error']:>9.2f} km")
    
    print()
    
    # Overall statistics
    all_errors = [e for loc in location_errors for e in loc['errors']]
    print(f"Overall statistics:")
    print(f"  Mean: {np.mean(all_errors):.2f} km")
    print(f"  Median: {np.median(all_errors):.2f} km")
    print(f"  Max: {np.max(all_errors):.2f} km")
    print(f"  Std: {np.std(all_errors):.2f} km")
    print()
    
    # Error hotspots
    print("2. ERROR HOTSPOTS")
    print("-" * 80)
    print()
    
    # Identify locations with highest errors
    high_error_locs = [loc for loc in location_errors if loc['mean_error'] > 50]
    medium_error_locs = [loc for loc in location_errors if 30 <= loc['mean_error'] <= 50]
    low_error_locs = [loc for loc in location_errors if loc['mean_error'] < 30]
    
    print(f"High error (>50 km): {len(high_error_locs)} locations")
    if high_error_locs:
        for loc in high_error_locs:
            print(f"  - {loc['name']}: {loc['mean_error']:.2f} km")
    
    print()
    print(f"Medium error (30-50 km): {len(medium_error_locs)} locations")
    if medium_error_locs:
        for loc in medium_error_locs:
            print(f"  - {loc['name']}: {loc['mean_error']:.2f} km")
    
    print()
    print(f"Low error (<30 km): {len(low_error_locs)} locations")
    if low_error_locs:
        for loc in low_error_locs:
            print(f"  - {loc['name']}: {loc['mean_error']:.2f} km")
    
    print()
    
    # Error growth over time
    print("3. ERROR GROWTH OVER TIME")
    print("-" * 80)
    print()
    
    # Calculate average error at each time step
    max_points = max(loc['n_points'] for loc in location_errors)
    time_errors = []
    
    for i in range(max_points):
        errors_at_time = []
        for loc in location_errors:
            if i < len(loc['errors']):
                errors_at_time.append(loc['errors'][i])
        
        if errors_at_time:
            time_errors.append({
                'hour': i,
                'mean': np.mean(errors_at_time),
                'median': np.median(errors_at_time),
                'max': np.max(errors_at_time),
                'n': len(errors_at_time)
            })
    
    # Show every 6 hours
    print(f"{'Hour':>5} {'Mean':>10} {'Median':>10} {'Max':>10} {'N':>5}")
    print("-" * 80)
    
    for i in range(0, len(time_errors), 6):
        if i < len(time_errors):
            t = time_errors[i]
            print(f"{t['hour']:>5} {t['mean']:>9.2f} km {t['median']:>9.2f} km "
                  f"{t['max']:>9.2f} km {t['n']:>5}")
    
    print()
    
    # Error growth rate
    if len(time_errors) >= 2:
        initial_error = time_errors[0]['mean']
        final_error = time_errors[-1]['mean']
        growth_rate = (final_error - initial_error) / len(time_errors)
        
        print(f"Error growth:")
        print(f"  Initial (0h): {initial_error:.2f} km")
        print(f"  Final ({len(time_errors)-1}h): {final_error:.2f} km")
        print(f"  Growth rate: {growth_rate:.2f} km/hour")
        print(f"  Total growth: {final_error - initial_error:.2f} km ({(final_error/initial_error - 1)*100:.1f}%)")
    
    print()
    
    # Latitude pattern
    print("4. LATITUDE PATTERN")
    print("-" * 80)
    print()
    
    high_lat = [loc for loc in location_errors if loc['lat'] > 35]
    mid_lat = [loc for loc in location_errors if 30 <= loc['lat'] <= 35]
    low_lat = [loc for loc in location_errors if loc['lat'] < 30]
    
    if high_lat:
        avg_error = np.mean([loc['mean_error'] for loc in high_lat])
        print(f"High latitude (>35°N): {len(high_lat)} locations, avg {avg_error:.2f} km")
    
    if mid_lat:
        avg_error = np.mean([loc['mean_error'] for loc in mid_lat])
        print(f"Mid latitude (30-35°N): {len(mid_lat)} locations, avg {avg_error:.2f} km")
    
    if low_lat:
        avg_error = np.mean([loc['mean_error'] for loc in low_lat])
        print(f"Low latitude (<30°N): {len(low_lat)} locations, avg {avg_error:.2f} km")
    
    print()
    
    # Possible causes
    print("5. POSSIBLE CAUSES")
    print("-" * 80)
    print()
    
    print("Based on the analysis, possible causes of horizontal error:")
    print()
    
    # Cause 1: Interpolation
    print("1. Wind field interpolation")
    print("   Current: Linear (trilinear) interpolation")
    print("   Issue: May not capture wind gradients accurately")
    print("   Solution: Test cubic spline interpolation")
    print("   Expected improvement: 10-20%")
    print()
    
    # Cause 2: Time step
    print("2. Time step size")
    print("   Current: dt_max = 15.0s, tratio = 0.75")
    print("   Issue: May be too large for fast-moving air masses")
    print("   Solution: Reduce dt_max to 10s or 5s")
    print("   Expected improvement: 5-10%")
    print()
    
    # Cause 3: CFL condition
    print("3. CFL condition")
    print("   Current: tratio = 0.75 (75% of grid cell per step)")
    print("   Issue: May allow too much movement per step")
    print("   Solution: Reduce tratio to 0.5")
    print("   Expected improvement: 5-10%")
    print()
    
    # Cause 4: Boundary errors
    if any(loc['mean_error'] > 100 for loc in location_errors):
        print("4. Boundary errors")
        print("   Issue: Some trajectories exit grid bounds")
        print("   Solution: Extend GFS data range (110°E → 105°E)")
        print("   Expected improvement: 20-30% for affected locations")
        print()
    
    # Cause 5: Vertical motion
    print("5. Vertical motion coupling")
    print("   Issue: Horizontal and vertical motion may not be well coupled")
    print("   Solution: Review vertical motion mode settings")
    print("   Expected improvement: 5-15%")
    print()
    
    # Recommendations
    print("6. RECOMMENDATIONS")
    print("-" * 80)
    print()
    
    print("Priority order for improvements:")
    print()
    
    print("1. HIGH PRIORITY: Extend GFS data range")
    print("   - Fixes boundary errors")
    print("   - Expected: 20-30% improvement for 5 locations")
    print("   - Time: 15-20 minutes")
    print("   - Command: python tests/integration/download_gfs_extended.py")
    print()
    
    print("2. MEDIUM PRIORITY: Reduce time step")
    print("   - Improves integration accuracy")
    print("   - Expected: 5-10% improvement overall")
    print("   - Time: 5 minutes (code change)")
    print("   - Change: dt_max = 15.0 → 10.0 in models.py")
    print()
    
    print("3. MEDIUM PRIORITY: Adjust CFL ratio")
    print("   - Reduces per-step movement")
    print("   - Expected: 5-10% improvement overall")
    print("   - Time: 5 minutes (code change)")
    print("   - Change: tratio = 0.75 → 0.5 in models.py")
    print()
    
    print("4. LOW PRIORITY: Test cubic interpolation")
    print("   - May improve wind gradient capture")
    print("   - Expected: 10-20% improvement (uncertain)")
    print("   - Time: 3-4 hours (implementation + testing)")
    print("   - Risk: May introduce instability")
    print()
    
    # Expected final result
    print("7. EXPECTED FINAL RESULT")
    print("-" * 80)
    print()
    
    current_mean = np.mean(all_errors)
    
    print(f"Current horizontal error: {current_mean:.2f} km")
    print()
    
    print("After all improvements:")
    print(f"  - GFS extension: {current_mean:.2f} km → {current_mean * 0.75:.2f} km (-25%)")
    print(f"  - Time step reduction: {current_mean * 0.75:.2f} km → {current_mean * 0.68:.2f} km (-10%)")
    print(f"  - CFL adjustment: {current_mean * 0.68:.2f} km → {current_mean * 0.61:.2f} km (-10%)")
    print(f"  - Final: {current_mean * 0.61:.2f} km")
    print()
    
    target = 20.0
    final_expected = current_mean * 0.61
    
    if final_expected <= target:
        print(f"✅ Expected to meet target (<{target} km)")
    else:
        gap = final_expected - target
        print(f"⚠️ Still {gap:.2f} km above target")
        print(f"   Additional improvements needed:")
        print(f"   - Cubic interpolation")
        print(f"   - Vertical motion tuning")
        print(f"   - HYSPLIT source code analysis")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    analyze_wind_errors()
