"""확장된 GFS 범위로 테스트 (105-150°E).

경계 오류가 발생했던 5개 위치를 재테스트합니다:
- 서울, 부산, 도쿄, 오사카, 베이징

목표: 경계 오류 제거 및 압력 오차 정상화
"""

import json
from datetime import datetime
from pathlib import Path

from pyhysplit.models import StartLocation, SimulationConfig
from pyhysplit.engine import TrajectoryEngine
from pyhysplit.met_reader import NetCDFReader


def test_extended_range():
    """확장된 범위로 경계 오류 위치 재테스트."""
    
    print("=" * 80)
    print("확장된 GFS 범위 테스트 (105-150°E)")
    print("=" * 80)
    print()
    
    # 확장된 GFS 데이터 로드
    print("Loading extended GFS data...")
    gfs_file = Path("tests/integration/gfs_cache/gfs_eastasia_24h_extended.nc")
    
    if not gfs_file.exists():
        print("❌ Extended GFS data not found.")
        print("   Run: python tests/integration/download_gfs_extended.py")
        return
    
    met_reader = NetCDFReader()
    met_data = met_reader.read(str(gfs_file))
    print(f"✓ Loaded GFS data: {len(met_data.t_grid)} time steps")
    print(f"  Longitude range: {met_data.lon_grid[0]:.1f} - {met_data.lon_grid[-1]:.1f}°E")
    print(f"  Latitude range: {met_data.lat_grid[0]:.1f} - {met_data.lat_grid[-1]:.1f}°N")
    print()
    
    # 경계 오류가 발생했던 위치들
    boundary_error_locations = [
        {"name": "서울", "lat": 37.5, "lon": 127.0},
        {"name": "부산", "lat": 35.1, "lon": 129.0},
        {"name": "도쿄", "lat": 35.7, "lon": 139.7},
        {"name": "오사카", "lat": 34.7, "lon": 135.5},
        {"name": "베이징", "lat": 39.9, "lon": 116.4},
    ]
    
    results = {}
    
    for loc in boundary_error_locations:
        print(f"Testing {loc['name']} ({loc['lat']:.1f}°N, {loc['lon']:.1f}°E)...")
        
        # Create config with auto_vertical_mode
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
            vertical_motion=0,  # Will be overridden by auto_vertical_mode
            model_top=10000.0,
            met_files=[("tests/integration/gfs_cache", "gfs_eastasia_24h_extended.nc")],
            auto_vertical_mode=True,  # Use automatic mode selection
            dt_max=15.0,
            tratio=0.75,
        )
        
        try:
            # Run trajectory
            engine = TrajectoryEngine(config, met_data)
            all_trajectories = engine.run()
            
            # Extract trajectory points
            traj_points = []
            boundary_error = False
            
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
                
                # Check if trajectory completed full 24 hours
                if len(traj_points) < 25:  # Should have 25 points (0-24 hours)
                    boundary_error = True
                    print(f"  ⚠️ Trajectory incomplete: {len(traj_points)} points (expected 25)")
                else:
                    print(f"  ✓ Completed: {len(traj_points)} points (full 24 hours!)")
            
            results[loc['name']] = {
                'lat': loc['lat'],
                'lon': loc['lon'],
                'points': len(traj_points),
                'boundary_error': boundary_error,
                'trajectory': traj_points,
                'success': True
            }
            
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
    output_file = Path("tests/integration/extended_range_results.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Results saved to {output_file}")
    print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY - Extended Range Test")
    print("=" * 80)
    print()
    
    successful = sum(1 for r in results.values() if r.get('success', False))
    no_boundary_error = sum(1 for r in results.values() 
                           if r.get('success', False) and not r.get('boundary_error', True))
    
    print(f"Success rate: {successful}/{len(boundary_error_locations)} "
          f"({successful/len(boundary_error_locations)*100:.1f}%)")
    print(f"No boundary errors: {no_boundary_error}/{len(boundary_error_locations)} "
          f"({no_boundary_error/len(boundary_error_locations)*100:.1f}%)")
    print()
    
    print(f"{'Location':<12} {'Points':>7} {'Status':>15}")
    print("-" * 80)
    
    for loc_name, data in results.items():
        if not data.get('success'):
            status = "Failed"
        elif data.get('boundary_error'):
            status = "Boundary Error"
        else:
            status = "Complete ✓"
        
        points = data.get('points', 0)
        print(f"{loc_name:<12} {points:>7} {status:>15}")
    
    print()
    
    # Comparison with previous results
    print("COMPARISON WITH PREVIOUS TEST (110-150°E)")
    print("-" * 80)
    print()
    
    # Previous results (from Mode 7 test)
    previous_results = {
        "서울": 16,
        "부산": 22,
        "도쿄": 24,
        "오사카": 25,
        "베이징": 11,
    }
    
    print(f"{'Location':<12} {'Previous':>10} {'Extended':>10} {'Change':>10}")
    print("-" * 80)
    
    for loc_name in boundary_error_locations:
        loc_name_str = loc_name['name']
        prev_points = previous_results.get(loc_name_str, 0)
        new_points = results[loc_name_str].get('points', 0)
        change = new_points - prev_points
        change_str = f"+{change}" if change > 0 else str(change)
        
        print(f"{loc_name_str:<12} {prev_points:>10} {new_points:>10} {change_str:>10}")
    
    print()
    
    # Conclusion
    print("=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print()
    
    if no_boundary_error == len(boundary_error_locations):
        print("✅ SUCCESS! All boundary errors resolved!")
        print()
        print("Results:")
        print(f"  - All {len(boundary_error_locations)} locations completed full 24-hour trajectories")
        print(f"  - No boundary errors detected")
        print(f"  - Extended range (105-150°E) is sufficient")
        print()
        print("Next steps:")
        print("  1. Update default GFS data to use extended range")
        print("  2. Re-run full comparison with HYSPLIT Web")
        print("  3. Verify pressure errors are normalized")
        print()
        print("Expected improvements:")
        print("  - Pressure error: 298.85 hPa → 20-30 hPa")
        print("  - Progress: 80% → 83-84%")
    else:
        errors = len(boundary_error_locations) - no_boundary_error
        print(f"⚠️ PARTIAL SUCCESS: {errors} location(s) still have boundary errors")
        print()
        print("Possible causes:")
        print("  - Need even wider range (e.g., 100-150°E)")
        print("  - Vertical motion issues")
        print("  - Time step too large")
        print()
        print("Recommendations:")
        print("  1. Analyze trajectories that still fail")
        print("  2. Consider expanding range further west")
        print("  3. Check vertical motion settings")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    test_extended_range()
