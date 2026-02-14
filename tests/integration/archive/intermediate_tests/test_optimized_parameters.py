"""최적화된 파라미터로 테스트.

시간 스텝 및 CFL 조정:
- dt_max: 3600.0s → 10.0s (더 작은 최대 시간 스텝)
- tratio: 0.75 → 0.5 (더 보수적인 CFL)

목표: 수평 오차 10-15% 개선
"""

import json
from datetime import datetime
from pathlib import Path
import time

from pyhysplit.models import StartLocation, SimulationConfig
from pyhysplit.engine import TrajectoryEngine
from pyhysplit.met_reader import NetCDFReader


def test_optimized_parameters():
    """최적화된 파라미터로 테스트."""
    
    print("=" * 80)
    print("최적화된 파라미터 테스트")
    print("=" * 80)
    print()
    
    print("파라미터 변경:")
    print("  dt_max: 3600.0s → 10.0s (더 작은 최대 시간 스텝)")
    print("  tratio: 0.75 → 0.5 (더 보수적인 CFL)")
    print()
    print("예상 효과:")
    print("  - 수평 오차: 10-15% 개선")
    print("  - 계산 시간: 약 50% 증가")
    print()
    
    # Load GFS data
    print("Loading GFS data...")
    gfs_file = Path("tests/integration/gfs_cache/gfs_eastasia_24h_real.nc")
    
    if not gfs_file.exists():
        print("❌ GFS data not found.")
        print("   Run: python tests/integration/download_gfs_real_eastasia.py")
        return
    
    met_reader = NetCDFReader()
    met_data = met_reader.read(str(gfs_file))
    print(f"✓ Loaded GFS data: {len(met_data.t_grid)} time steps")
    print()
    
    # Test locations (subset for quick test)
    test_locations = [
        {"name": "서울", "lat": 37.5, "lon": 127.0},
        {"name": "제주", "lat": 33.5, "lon": 126.5},
        {"name": "오사카", "lat": 34.7, "lon": 135.5},
    ]
    
    results_baseline = {}
    results_optimized = {}
    
    print("=" * 80)
    print("BASELINE TEST (dt_max=15.0, tratio=0.75)")
    print("=" * 80)
    print()
    
    for loc in test_locations:
        print(f"Testing {loc['name']} ({loc['lat']:.1f}°N, {loc['lon']:.1f}°E)...")
        
        # Baseline config
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
            met_files=[("tests/integration/gfs_cache", "gfs_eastasia_24h_real.nc")],
            auto_vertical_mode=True,
            dt_max=15.0,  # Baseline
            tratio=0.75,  # Baseline
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
            
            results_baseline[loc['name']] = {
                'lat': loc['lat'],
                'lon': loc['lon'],
                'points': len(traj_points),
                'trajectory': traj_points,
                'time': elapsed_time,
                'success': True
            }
            
            print(f"  ✓ Completed: {len(traj_points)} points in {elapsed_time:.2f}s")
            
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            results_baseline[loc['name']] = {
                'lat': loc['lat'],
                'lon': loc['lon'],
                'success': False,
                'error': str(e)
            }
        
        print()
    
    print("=" * 80)
    print("OPTIMIZED TEST (dt_max=10.0, tratio=0.5)")
    print("=" * 80)
    print()
    
    for loc in test_locations:
        print(f"Testing {loc['name']} ({loc['lat']:.1f}°N, {loc['lon']:.1f}°E)...")
        
        # Optimized config
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
            met_files=[("tests/integration/gfs_cache", "gfs_eastasia_24h_real.nc")],
            auto_vertical_mode=True,
            dt_max=10.0,  # Optimized
            tratio=0.5,   # Optimized
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
            
            results_optimized[loc['name']] = {
                'lat': loc['lat'],
                'lon': loc['lon'],
                'points': len(traj_points),
                'trajectory': traj_points,
                'time': elapsed_time,
                'success': True
            }
            
            print(f"  ✓ Completed: {len(traj_points)} points in {elapsed_time:.2f}s")
            
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            results_optimized[loc['name']] = {
                'lat': loc['lat'],
                'lon': loc['lon'],
                'success': False,
                'error': str(e)
            }
        
        print()
    
    # Save results
    output_file = Path("tests/integration/optimized_parameters_results.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'baseline': results_baseline,
            'optimized': results_optimized
        }, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Results saved to {output_file}")
    print()
    
    # Comparison
    print("=" * 80)
    print("COMPARISON")
    print("=" * 80)
    print()
    
    print(f"{'Location':<12} {'Baseline':>10} {'Optimized':>10} {'Time Δ':>10} {'Points Δ':>10}")
    print("-" * 80)
    
    for loc_name in test_locations:
        name = loc_name['name']
        
        if name not in results_baseline or name not in results_optimized:
            continue
        
        baseline = results_baseline[name]
        optimized = results_optimized[name]
        
        if not baseline.get('success') or not optimized.get('success'):
            continue
        
        time_baseline = baseline['time']
        time_optimized = optimized['time']
        time_delta = ((time_optimized - time_baseline) / time_baseline) * 100
        
        points_baseline = baseline['points']
        points_optimized = optimized['points']
        points_delta = points_optimized - points_baseline
        
        print(f"{name:<12} {time_baseline:>9.2f}s {time_optimized:>9.2f}s "
              f"{time_delta:>8.1f}% {points_delta:>+10}")
    
    print()
    
    # Calculate trajectory differences
    print("TRAJECTORY DIFFERENCES")
    print("-" * 80)
    print()
    
    import numpy as np
    
    for loc_name in test_locations:
        name = loc_name['name']
        
        if name not in results_baseline or name not in results_optimized:
            continue
        
        baseline = results_baseline[name]
        optimized = results_optimized[name]
        
        if not baseline.get('success') or not optimized.get('success'):
            continue
        
        traj_baseline = baseline['trajectory']
        traj_optimized = optimized['trajectory']
        
        # Calculate differences at each time step
        n_points = min(len(traj_baseline), len(traj_optimized))
        
        if n_points == 0:
            continue
        
        differences = []
        for i in range(n_points):
            lat1, lon1 = traj_baseline[i]['lat'], traj_baseline[i]['lon']
            lat2, lon2 = traj_optimized[i]['lat'], traj_optimized[i]['lon']
            
            # Haversine distance
            lat1_rad, lon1_rad = np.radians(lat1), np.radians(lon1)
            lat2_rad, lon2_rad = np.radians(lat2), np.radians(lon2)
            
            dlat = lat2_rad - lat1_rad
            dlon = lon2_rad - lon1_rad
            a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
            c = 2 * np.arcsin(np.sqrt(a))
            distance = 6371.0 * c
            
            differences.append(distance)
        
        avg_diff = np.mean(differences)
        max_diff = np.max(differences)
        
        print(f"{name}:")
        print(f"  Average difference: {avg_diff:.2f} km")
        print(f"  Maximum difference: {max_diff:.2f} km")
        print(f"  Points compared: {n_points}")
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    
    # Calculate average time increase
    time_increases = []
    for loc_name in test_locations:
        name = loc_name['name']
        if name in results_baseline and name in results_optimized:
            baseline = results_baseline[name]
            optimized = results_optimized[name]
            if baseline.get('success') and optimized.get('success'):
                increase = ((optimized['time'] - baseline['time']) / baseline['time']) * 100
                time_increases.append(increase)
    
    if time_increases:
        avg_time_increase = np.mean(time_increases)
        print(f"Average computation time increase: {avg_time_increase:.1f}%")
    
    print()
    print("Parameter changes:")
    print("  dt_max: 15.0s → 10.0s (33% reduction)")
    print("  tratio: 0.75 → 0.5 (33% reduction)")
    print()
    
    print("Observations:")
    print("  - Trajectories are slightly different (expected)")
    print("  - Computation time increased (expected)")
    print("  - More conservative integration (smaller steps)")
    print()
    
    print("Next steps:")
    print("  1. Compare with HYSPLIT Web data (if available)")
    print("  2. Measure actual accuracy improvement")
    print("  3. Decide if trade-off is acceptable")
    print()
    
    print("To compare with HYSPLIT Web:")
    print("  - Need tdump files in tests/integration/hysplit_web_data/")
    print("  - Run: python tests/integration/compare_optimized_with_hysplit.py")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    test_optimized_parameters()
