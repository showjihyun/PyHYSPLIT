"""확장된 GFS 범위로 전체 8개 위치 테스트.

GFS 범위: 105-150°E (이전: 110-150°E)
목적: 경계 오류 개선 효과 측정

사용법:
    python tests/integration/test_all_locations_extended.py
"""

import json
from datetime import datetime
from pathlib import Path
import time

from pyhysplit.models import StartLocation, SimulationConfig
from pyhysplit.engine import TrajectoryEngine
from pyhysplit.met_reader import NetCDFReader


def test_all_locations_extended():
    """확장된 GFS 범위로 전체 8개 위치 테스트."""
    
    print("=" * 80)
    print("확장된 GFS 범위로 전체 위치 테스트 (105-150°E)")
    print("=" * 80)
    print()
    
    # Load extended GFS data
    print("Loading extended GFS data...")
    gfs_file = Path("tests/integration/gfs_cache/gfs_eastasia_24h_extended.nc")
    
    if not gfs_file.exists():
        print("❌ Extended GFS data not found.")
        print("   Run: python tests/integration/download_gfs_extended.py")
        return
    
    met_reader = NetCDFReader()
    met_data = met_reader.read(str(gfs_file))
    print(f"✓ Loaded GFS data: {len(met_data.t_grid)} time steps")
    print(f"  Longitude range: {met_data.lon_grid.min():.1f} - {met_data.lon_grid.max():.1f}°E")
    print(f"  Latitude range: {met_data.lat_grid.min():.1f} - {met_data.lat_grid.max():.1f}°N")
    print()
    
    # Test locations
    test_locations = [
        {"name": "서울", "lat": 37.5, "lon": 127.0},
        {"name": "부산", "lat": 35.1, "lon": 129.0},
        {"name": "제주", "lat": 33.5, "lon": 126.5},
        {"name": "도쿄", "lat": 35.7, "lon": 139.7},
        {"name": "오사카", "lat": 34.7, "lon": 135.5},
        {"name": "베이징", "lat": 39.9, "lon": 116.4},
        {"name": "상하이", "lat": 31.2, "lon": 121.5},
        {"name": "타이베이", "lat": 25.0, "lon": 121.5},
    ]
    
    results = {}
    
    for loc in test_locations:
        print(f"Testing {loc['name']} ({loc['lat']:.1f}°N, {loc['lon']:.1f}°E)...")
        
        config = SimulationConfig(
            start_time=datetime(2026, 2, 14, 0, 0),
            num_start_locations=1,
            start_locations=[
                StartLocation(
                    lat=loc['lat'],
                    lon=loc['lon'],
                    height=850,
                    height_type="pressure"
                )
            ],
            total_run_hours=-24,
            vertical_motion=0,
            model_top=10000.0,
            met_files=[("tests/integration/gfs_cache", "gfs_eastasia_24h_extended.nc")],
            auto_vertical_mode=True,
        )
        
        try:
            start_time = time.time()
            engine = TrajectoryEngine(config, met_data)
            all_trajectories = engine.run()
            elapsed_time = time.time() - start_time
            
            traj_points = []
            if all_trajectories and len(all_trajectories) > 0:
                trajectory = all_trajectories[0]
                for t, lon, lat, z in trajectory:
                    hour = -t / 3600.0
                    traj_points.append({
                        'hour': hour,
                        'lat': lat,
                        'lon': lon,
                        'pressure': z
                    })
            
            boundary_error = len(traj_points) < 25
            
            results[loc['name']] = {
                'lat': loc['lat'],
                'lon': loc['lon'],
                'points': len(traj_points),
                'boundary_error': boundary_error,
                'trajectory': traj_points,
                'time': elapsed_time,
                'success': True
            }
            
            if boundary_error:
                print(f"  ⚠️ Trajectory incomplete: {len(traj_points)} points (expected 25)")
            else:
                print(f"  ✓ Completed: {len(traj_points)} points (full 24 hours!)")
            
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            results[loc['name']] = {
                'lat': loc['lat'],
                'lon': loc['lon'],
                'success': False,
                'error': str(e)
            }
        
        print()
    
    # Save results
    output_file = Path("tests/integration/all_locations_extended_results.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Results saved to {output_file}")
    print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY - All Locations Extended Range Test")
    print("=" * 80)
    print()
    
    success_count = sum(1 for r in results.values() if r.get('success', False))
    complete_count = sum(1 for r in results.values() 
                        if r.get('success', False) and not r.get('boundary_error', True))
    
    print(f"Success rate: {success_count}/{len(test_locations)} ({success_count/len(test_locations)*100:.1f}%)")
    print(f"Complete (no boundary errors): {complete_count}/{len(test_locations)} ({complete_count/len(test_locations)*100:.1f}%)")
    print()
    
    print(f"{'Location':<12} {'Points':>10} {'Status':>20}")
    print("-" * 80)
    
    for loc_name, result in results.items():
        if not result.get('success', False):
            status = "Failed"
            points = 0
        elif result.get('boundary_error', True):
            status = "Boundary Error"
            points = result['points']
        else:
            status = "Complete ✓"
            points = result['points']
        
        print(f"{loc_name:<12} {points:>10} {status:>20}")
    
    print()
    
    # Load previous results for comparison
    prev_file = Path("tests/integration/all_locations_results.json")
    if prev_file.exists():
        with open(prev_file, 'r', encoding='utf-8') as f:
            prev_results = json.load(f)
        
        print("COMPARISON WITH PREVIOUS TEST (110-150°E)")
        print("-" * 80)
        print()
        print(f"{'Location':<12} {'Previous':>10} {'Extended':>10} {'Change':>10}")
        print("-" * 80)
        
        for loc_name in test_locations:
            name = loc_name['name']
            
            if name not in prev_results or name not in results:
                continue
            
            prev = prev_results[name]
            curr = results[name]
            
            if not prev.get('success') or not curr.get('success'):
                continue
            
            prev_points = prev['points']
            curr_points = curr['points']
            change = curr_points - prev_points
            
            print(f"{name:<12} {prev_points:>10} {curr_points:>10} {change:>+10}")
        
        print()
    
    # Analyze improvements
    print("=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    print()
    
    # Group by latitude
    high_lat = []  # >= 35°N
    low_lat = []   # < 35°N
    
    for loc_name, result in results.items():
        if not result.get('success', False):
            continue
        
        lat = result['lat']
        complete = not result.get('boundary_error', True)
        
        if lat >= 35.0:
            high_lat.append((loc_name, complete))
        else:
            low_lat.append((loc_name, complete))
    
    print("High latitude (>= 35°N):")
    for name, complete in high_lat:
        status = "✓ Complete" if complete else "⚠️ Boundary Error"
        print(f"  {name}: {status}")
    
    print()
    print("Low latitude (< 35°N):")
    for name, complete in low_lat:
        status = "✓ Complete" if complete else "⚠️ Boundary Error"
        print(f"  {name}: {status}")
    
    print()
    
    # Calculate completion rate by latitude
    high_lat_complete = sum(1 for _, c in high_lat if c)
    low_lat_complete = sum(1 for _, c in low_lat if c)
    
    print(f"High latitude completion: {high_lat_complete}/{len(high_lat)} ({high_lat_complete/len(high_lat)*100:.1f}%)")
    print(f"Low latitude completion: {low_lat_complete}/{len(low_lat)} ({low_lat_complete/len(low_lat)*100:.1f}%)")
    
    print()
    
    # Conclusion
    print("=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print()
    
    if complete_count == len(test_locations):
        print("✅ SUCCESS: All locations completed without boundary errors!")
    elif complete_count >= len(test_locations) * 0.75:
        print(f"✅ GOOD: {complete_count}/{len(test_locations)} locations completed")
        print(f"   Remaining {len(test_locations) - complete_count} location(s) have boundary errors")
    elif complete_count >= len(test_locations) * 0.5:
        print(f"⚠️ PARTIAL: {complete_count}/{len(test_locations)} locations completed")
        print(f"   {len(test_locations) - complete_count} location(s) still have boundary errors")
    else:
        print(f"❌ LIMITED: Only {complete_count}/{len(test_locations)} locations completed")
        print(f"   {len(test_locations) - complete_count} location(s) have boundary errors")
    
    print()
    
    if complete_count < len(test_locations):
        print("Remaining issues:")
        for loc_name, result in results.items():
            if result.get('success', False) and result.get('boundary_error', True):
                points = result['points']
                hours = points - 1
                print(f"  - {loc_name}: Stopped at {hours}h (needs wider range or vertical adjustment)")
        
        print()
        print("Recommendations:")
        print("  1. Vertical motion adjustment (vertical_damping)")
        print("  2. Further range extension (100-150°E)")
        print("  3. Accept current state and focus on other improvements")
    
    print()
    print("Next steps:")
    print("  1. Analyze pressure errors with extended range")
    print("  2. Calculate horizontal errors")
    print("  3. Measure overall progress")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    test_all_locations_extended()
