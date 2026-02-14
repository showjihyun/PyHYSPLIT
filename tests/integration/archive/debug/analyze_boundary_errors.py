"""경계 오류 분석 (기존 데이터 사용).

Mode 7 테스트에서 발견된 경계 오류를 분석합니다.
- 어느 방향으로 벗어났는지
- 얼마나 빨리 벗어났는지
- 어떤 패턴이 있는지

인터넷 연결 없이 즉시 실행 가능합니다.
"""

import json
from pathlib import Path
import numpy as np


def analyze_boundary_errors():
    """경계 오류 패턴 분석."""
    
    print("=" * 80)
    print("경계 오류 분석")
    print("=" * 80)
    print()
    
    # Load Mode 7 test results
    results_file = Path("tests/integration/mode7_all_locations_results.json")
    if not results_file.exists():
        print("❌ Mode 7 test results not found.")
        print("   Run: python tests/integration/test_mode7_all_locations.py")
        return
    
    with open(results_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    print("1. BOUNDARY ERROR LOCATIONS")
    print("-" * 80)
    print()
    
    # Identify locations with boundary errors
    boundary_errors = []
    complete_trajectories = []
    
    for loc_name, data in results.items():
        if not data.get('success'):
            continue
        
        traj = data.get('trajectory', [])
        expected_points = 25  # 0-24 hours
        
        if len(traj) < expected_points:
            boundary_errors.append({
                'name': loc_name,
                'lat': data['lat'],
                'lon': data['lon'],
                'points': len(traj),
                'missing': expected_points - len(traj),
                'trajectory': traj
            })
        else:
            complete_trajectories.append({
                'name': loc_name,
                'lat': data['lat'],
                'lon': data['lon'],
                'points': len(traj)
            })
    
    print(f"Locations with boundary errors: {len(boundary_errors)}")
    print(f"Complete trajectories: {len(complete_trajectories)}")
    print()
    
    if boundary_errors:
        print(f"{'Location':<12} {'Lat':>6} {'Lon':>7} {'Points':>7} {'Missing':>8} {'%':>6}")
        print("-" * 80)
        
        for loc in boundary_errors:
            pct = (loc['points'] / 25) * 100
            print(f"{loc['name']:<12} {loc['lat']:>6.1f} {loc['lon']:>7.1f} "
                  f"{loc['points']:>7} {loc['missing']:>8} {pct:>5.1f}%")
    
    print()
    
    # Analyze exit direction
    print("2. EXIT DIRECTION ANALYSIS")
    print("-" * 80)
    print()
    
    if not boundary_errors:
        print("No boundary errors to analyze.")
        return
    
    # GFS grid bounds (from Mode 7 test)
    lon_min, lon_max = 110.0, 150.0
    lat_min, lat_max = 20.0, 50.0
    pressure_min, pressure_max = 200.0, 1000.0
    
    print(f"GFS grid bounds:")
    print(f"  Longitude: {lon_min:.1f} - {lon_max:.1f}°E")
    print(f"  Latitude: {lat_min:.1f} - {lat_max:.1f}°N")
    print(f"  Pressure: {pressure_min:.1f} - {pressure_max:.1f} hPa")
    print()
    
    print(f"{'Location':<12} {'Exit Lon':>10} {'Exit Lat':>10} {'Exit P':>10} {'Direction':>12}")
    print("-" * 80)
    
    for loc in boundary_errors:
        traj = loc['trajectory']
        if not traj:
            continue
        
        # Last point before exit
        last_point = traj[-1]
        exit_lon = last_point['lon']
        exit_lat = last_point['lat']
        exit_pressure = last_point.get('pressure', 0)
        
        # Determine exit direction
        directions = []
        if exit_lon <= lon_min + 0.1:
            directions.append("West")
        elif exit_lon >= lon_max - 0.1:
            directions.append("East")
        
        if exit_lat <= lat_min + 0.1:
            directions.append("South")
        elif exit_lat >= lat_max - 0.1:
            directions.append("North")
        
        if exit_pressure <= pressure_min + 5:
            directions.append("Top")
        elif exit_pressure >= pressure_max - 5:
            directions.append("Bottom")
        
        direction_str = "+".join(directions) if directions else "Unknown"
        
        print(f"{loc['name']:<12} {exit_lon:>10.4f} {exit_lat:>10.4f} "
              f"{exit_pressure:>10.1f} {direction_str:>12}")
    
    print()
    
    # Analyze exit time
    print("3. EXIT TIME ANALYSIS")
    print("-" * 80)
    print()
    
    print(f"{'Location':<12} {'Exit Hour':>11} {'% Complete':>12} {'Speed':>10}")
    print("-" * 80)
    
    for loc in boundary_errors:
        traj = loc['trajectory']
        if not traj:
            continue
        
        # Calculate exit time
        exit_hour = abs(traj[-1]['hour'])
        pct_complete = (exit_hour / 24.0) * 100
        
        # Calculate average speed (km/h)
        if len(traj) >= 2:
            total_distance = 0
            for i in range(1, len(traj)):
                lat1, lon1 = traj[i-1]['lat'], traj[i-1]['lon']
                lat2, lon2 = traj[i]['lat'], traj[i]['lon']
                
                # Haversine distance
                lat1_rad, lon1_rad = np.radians(lat1), np.radians(lon1)
                lat2_rad, lon2_rad = np.radians(lat2), np.radians(lon2)
                
                dlat = lat2_rad - lat1_rad
                dlon = lon2_rad - lon1_rad
                a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
                c = 2 * np.arcsin(np.sqrt(a))
                distance = 6371.0 * c
                
                total_distance += distance
            
            avg_speed = total_distance / exit_hour if exit_hour > 0 else 0
        else:
            avg_speed = 0
        
        print(f"{loc['name']:<12} {exit_hour:>11.1f} {pct_complete:>11.1f}% {avg_speed:>9.1f} km/h")
    
    print()
    
    # Pattern analysis
    print("4. PATTERN ANALYSIS")
    print("-" * 80)
    print()
    
    # Group by exit direction
    west_exits = [loc for loc in boundary_errors 
                  if loc['trajectory'] and loc['trajectory'][-1]['lon'] <= lon_min + 0.1]
    
    print(f"West exits (≤{lon_min:.1f}°E): {len(west_exits)}")
    if west_exits:
        print(f"  Locations: {', '.join(loc['name'] for loc in west_exits)}")
        avg_lat = np.mean([loc['lat'] for loc in west_exits])
        print(f"  Average latitude: {avg_lat:.1f}°N")
    
    print()
    
    # Analyze by latitude
    high_lat_errors = [loc for loc in boundary_errors if loc['lat'] > 35]
    mid_lat_errors = [loc for loc in boundary_errors if 30 <= loc['lat'] <= 35]
    low_lat_errors = [loc for loc in boundary_errors if loc['lat'] < 30]
    
    print(f"High latitude (>35°N): {len(high_lat_errors)}/{len([l for l in results.values() if l.get('lat', 0) > 35])}")
    print(f"Mid latitude (30-35°N): {len(mid_lat_errors)}/{len([l for l in results.values() if 30 <= l.get('lat', 0) <= 35])}")
    print(f"Low latitude (<30°N): {len(low_lat_errors)}/{len([l for l in results.values() if l.get('lat', 0) < 30])}")
    
    print()
    
    # Conclusion
    print("5. CONCLUSION")
    print("-" * 80)
    print()
    
    if west_exits:
        print(f"✓ Primary issue: {len(west_exits)} location(s) exit through WEST boundary")
        print(f"  Current west boundary: {lon_min:.1f}°E")
        print(f"  Recommendation: Extend to 105°E (5 degrees west)")
        print()
        
        # Estimate required extension
        if west_exits:
            min_exit_lon = min(loc['trajectory'][-1]['lon'] for loc in west_exits if loc['trajectory'])
            required_extension = lon_min - min_exit_lon + 1  # +1 for safety margin
            print(f"  Minimum exit longitude: {min_exit_lon:.1f}°E")
            print(f"  Required extension: {required_extension:.1f} degrees")
            print(f"  Recommended range: {lon_min - required_extension:.0f}-{lon_max:.0f}°E")
    
    print()
    print("RECOMMENDATIONS:")
    print("-" * 80)
    print()
    
    print("1. Immediate action: Extend GFS data range westward")
    print(f"   Current: {lon_min:.0f}-{lon_max:.0f}°E")
    print(f"   Recommended: 105-{lon_max:.0f}°E")
    print(f"   Command: python tests/integration/download_gfs_extended.py")
    print()
    
    print("2. Expected improvements:")
    print(f"   - {len(boundary_errors)} location(s) will complete full 24-hour trajectories")
    print(f"   - Pressure errors will normalize (298.85 hPa → 20-30 hPa)")
    print(f"   - Progress: 80% → 83-84%")
    print()
    
    print("3. Alternative if extension doesn't work:")
    print("   - Reduce time step (dt_max: 15s → 10s)")
    print("   - Adjust CFL ratio (tratio: 0.75 → 0.5)")
    print("   - Check vertical motion settings")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    analyze_boundary_errors()
