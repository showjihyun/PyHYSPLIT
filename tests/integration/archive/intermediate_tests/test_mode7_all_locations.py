"""Test Mode 7 (Spatially averaged) for all locations.

Current state uses:
- Mode 7 for mid-latitude (>33.5°N): 15.6 hPa avg error
- Mode 3 for low-latitude (≤33.5°N): 34.9 hPa avg error

This test checks if Mode 7 works better for low-latitude locations too.

If successful, we can simplify to use Mode 7 everywhere.
"""

import json
from datetime import datetime
from pathlib import Path

from pyhysplit.models import StartLocation, SimulationConfig
from pyhysplit.engine import TrajectoryEngine
from pyhysplit.met_reader import NetCDFReader


def load_hysplit_web_data(location_name: str):
    """Load HYSPLIT Web comparison data if available."""
    tdump_file = Path(f"tests/integration/hysplit_web_data/tdump_{location_name}.txt")
    if not tdump_file.exists():
        return None
    
    # Parse tdump file (simplified)
    points = []
    with open(tdump_file, 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                parts = line.split()
                if len(parts) >= 11:
                    try:
                        points.append({
                            'hour': float(parts[0]),
                            'lat': float(parts[9]),
                            'lon': float(parts[10]),
                            'height': float(parts[11])
                        })
                    except (ValueError, IndexError):
                        continue
    
    return points


def calculate_errors(pyhysplit_traj, hysplit_web_data):
    """Calculate errors between PyHYSPLIT and HYSPLIT Web."""
    if not hysplit_web_data:
        return None
    
    errors = []
    for i, py_point in enumerate(pyhysplit_traj):
        if i >= len(hysplit_web_data):
            break
        
        hy_point = hysplit_web_data[i]
        
        # Calculate horizontal distance (Haversine)
        import numpy as np
        lat1, lon1 = np.radians(py_point['lat']), np.radians(py_point['lon'])
        lat2, lon2 = np.radians(hy_point['lat']), np.radians(hy_point['lon'])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        horizontal_error = 6371.0 * c  # Earth radius in km
        
        # Height error (convert to pressure if needed)
        # For now, use direct difference
        height_error = abs(py_point.get('height', 0) - hy_point['height'])
        
        errors.append({
            'hour': py_point.get('hour', i),
            'horizontal_km': horizontal_error,
            'height_m': height_error
        })
    
    return errors


def test_mode7_all_locations():
    """Test Mode 7 for all 8 locations."""
    
    print("=" * 80)
    print("Testing Mode 7 (Spatially Averaged) for All Locations")
    print("=" * 80)
    print()
    
    # Load GFS data
    print("Loading GFS data...")
    gfs_file = Path("tests/integration/gfs_cache/gfs_eastasia_24h_real.nc")
    if not gfs_file.exists():
        print("❌ GFS data not found. Run download_gfs_real_eastasia.py first.")
        return
    
    met_reader = NetCDFReader()
    met_data = met_reader.read(str(gfs_file))
    print(f"✓ Loaded GFS data: {len(met_data.t_grid)} time steps")
    print()
    
    # Test locations
    locations = [
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
    
    for loc in locations:
        print(f"Testing {loc['name']} ({loc['lat']:.1f}°N, {loc['lon']:.1f}°E)...")
        
        # Create config with Mode 7 (no auto mode)
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
            vertical_motion=7,  # Force Mode 7
            model_top=10000.0,
            met_files=[("tests/integration/gfs_cache", "gfs_eastasia_24h_real.nc")],
            auto_vertical_mode=False,  # Disable auto selection
            dt_max=15.0,
            tratio=0.75,
        )
        
        try:
            # Run trajectory
            engine = TrajectoryEngine(config, met_data)
            all_trajectories = engine.run()
            
            # Extract trajectory points from first (and only) start location
            traj_points = []
            if all_trajectories and len(all_trajectories) > 0:
                trajectory = all_trajectories[0]  # First start location
                for i, point_tuple in enumerate(trajectory):
                    # point_tuple is (t, lon, lat, z)
                    t, lon, lat, z = point_tuple
                    # Convert time to hours (negative for backward)
                    hour = -t / 3600.0 if config.total_run_hours < 0 else t / 3600.0
                    traj_points.append({
                        'hour': hour,
                        'lat': lat,
                        'lon': lon,
                        'height': z,  # This is in pressure coordinates (hPa)
                        'pressure': z  # Same as height for pressure coordinates
                    })
            else:
                print(f"  ⚠️ No trajectory data returned")
                traj_points = []
            
            # Load HYSPLIT Web data if available
            hysplit_data = load_hysplit_web_data(loc['name'])
            
            # Calculate errors
            errors = None
            if hysplit_data:
                errors = calculate_errors(traj_points, hysplit_data)
            
            results[loc['name']] = {
                'lat': loc['lat'],
                'lon': loc['lon'],
                'mode': 7,
                'points': len(traj_points),
                'trajectory': traj_points,
                'errors': errors,
                'success': True
            }
            
            print(f"  ✓ Completed: {len(traj_points)} points")
            
            if errors:
                avg_h_error = sum(e['horizontal_km'] for e in errors) / len(errors)
                avg_height_error = sum(e['height_m'] for e in errors) / len(errors)
                print(f"  Horizontal error: {avg_h_error:.2f} km")
                print(f"  Height error: {avg_height_error:.2f} m")
            
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            results[loc['name']] = {
                'lat': loc['lat'],
                'lon': loc['lon'],
                'mode': 7,
                'success': False,
                'error': str(e)
            }
        
        print()
    
    # Save results
    output_file = Path("tests/integration/mode7_all_locations_results.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Results saved to {output_file}")
    print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY - Mode 7 for All Locations")
    print("=" * 80)
    print()
    
    successful = sum(1 for r in results.values() if r.get('success', False))
    print(f"Success rate: {successful}/{len(locations)} ({successful/len(locations)*100:.1f}%)")
    print()
    
    # Group by latitude
    high_lat = [r for r in results.values() if r.get('lat', 0) > 33.5]
    low_lat = [r for r in results.values() if r.get('lat', 0) <= 33.5]
    
    print(f"High latitude (>33.5°N): {len(high_lat)} locations")
    print(f"  - Previously used Mode 7 (no change)")
    print()
    
    print(f"Low latitude (≤33.5°N): {len(low_lat)} locations")
    print(f"  - Previously used Mode 3")
    print(f"  - Now testing Mode 7")
    print()
    
    # Compare with previous results if available
    prev_file = Path("tests/integration/multi_location_24h_results.json")
    if prev_file.exists():
        print("Comparison with previous results (auto_vertical_mode):")
        print()
        
        with open(prev_file, 'r', encoding='utf-8') as f:
            prev_results = json.load(f)
        
        print(f"{'Location':<12} {'Lat':>6} {'Prev Mode':>10} {'New Mode':>10} {'Change':>10}")
        print("-" * 80)
        
        for loc_name, new_data in results.items():
            if not new_data.get('success'):
                continue
            
            prev_data = prev_results.get(loc_name, {})
            prev_mode = "Mode 7" if new_data['lat'] > 33.5 else "Mode 3"
            new_mode = "Mode 7"
            change = "Same" if prev_mode == new_mode else "Changed"
            
            print(f"{loc_name:<12} {new_data['lat']:>6.1f} {prev_mode:>10} "
                  f"{new_mode:>10} {change:>10}")
    
    print()
    print("=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print()
    print("1. If HYSPLIT Web data is available:")
    print("   - Compare errors with previous auto_vertical_mode results")
    print("   - Check if Mode 7 improves low-latitude pressure errors")
    print()
    print("2. If Mode 7 is better for low latitudes:")
    print("   - Update engine.py to use Mode 7 for all latitudes")
    print("   - Simplify code by removing latitude-based selection")
    print()
    print("3. If Mode 7 is worse for low latitudes:")
    print("   - Keep current auto_vertical_mode implementation")
    print("   - Focus on other improvements (wind field, interpolation)")
    print()
    print("To compare with HYSPLIT Web:")
    print("  python tests/integration/compare_mode7_results.py")
    print("=" * 80)


if __name__ == "__main__":
    test_mode7_all_locations()
