"""수직 운동 감쇠 테스트.

목적: 고위도 위치의 빠른 상승을 억제하여 제트 기류 진입 지연
방법: vertical_damping 파라미터 조정 (1.0 → 0.3)

예상 효과:
- 상승 속도 감소 → 제트 기류 진입 지연
- 수평 이동 속도 감소
- 고위도 위치 경계 오류 감소

사용법:
    python tests/integration/test_vertical_damping.py
"""

import json
from datetime import datetime
from pathlib import Path
import time

from pyhysplit.models import StartLocation, SimulationConfig
from pyhysplit.engine import TrajectoryEngine
from pyhysplit.met_reader import NetCDFReader


def test_vertical_damping():
    """수직 운동 감쇠 테스트."""
    
    print("=" * 80)
    print("수직 운동 감쇠 테스트")
    print("=" * 80)
    print()
    
    print("목적: 고위도 위치의 빠른 상승 억제")
    print("방법: vertical_damping 파라미터 조정")
    print()
    print("파라미터:")
    print("  Baseline: vertical_damping = 1.0 (기본값, 감쇠 없음)")
    print("  Test 1: vertical_damping = 0.5 (50% 감쇠)")
    print("  Test 2: vertical_damping = 0.3 (70% 감쇠)")
    print()
    print("예상 효과:")
    print("  - 상승 속도 감소")
    print("  - 제트 기류 진입 지연")
    print("  - 수평 이동 속도 감소")
    print("  - 경계 오류 감소")
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
    print()
    
    # Test locations (high latitude only - where boundary errors occur)
    test_locations = [
        {"name": "서울", "lat": 37.5, "lon": 127.0},
        {"name": "부산", "lat": 35.1, "lon": 129.0},
        {"name": "도쿄", "lat": 35.7, "lon": 139.7},
        {"name": "베이징", "lat": 39.9, "lon": 116.4},
    ]
    
    # Test different damping values
    damping_values = [1.0, 0.5, 0.3]
    
    all_results = {}
    
    for damping in damping_values:
        print("=" * 80)
        print(f"TEST: vertical_damping = {damping}")
        print("=" * 80)
        print()
        
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
                vertical_damping=damping,  # Apply damping
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
                    hours = len(traj_points) - 1
                    print(f"  ⚠️ Trajectory incomplete: {len(traj_points)} points ({hours}h)")
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
        
        all_results[f"damping_{damping}"] = results
    
    # Save results
    output_file = Path("tests/integration/vertical_damping_results.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Results saved to {output_file}")
    print()
    
    # Comparison
    print("=" * 80)
    print("COMPARISON")
    print("=" * 80)
    print()
    
    print(f"{'Location':<12} {'Baseline':>10} {'Damp 0.5':>10} {'Damp 0.3':>10}")
    print("-" * 80)
    
    for loc in test_locations:
        name = loc['name']
        
        baseline = all_results['damping_1.0'].get(name, {})
        damp_05 = all_results['damping_0.5'].get(name, {})
        damp_03 = all_results['damping_0.3'].get(name, {})
        
        baseline_pts = baseline.get('points', 0) if baseline.get('success') else 0
        damp_05_pts = damp_05.get('points', 0) if damp_05.get('success') else 0
        damp_03_pts = damp_03.get('points', 0) if damp_03.get('success') else 0
        
        print(f"{name:<12} {baseline_pts:>10} {damp_05_pts:>10} {damp_03_pts:>10}")
    
    print()
    
    # Calculate improvement
    print("IMPROVEMENT")
    print("-" * 80)
    print()
    
    for damping_key in ['damping_0.5', 'damping_0.3']:
        damping_val = damping_key.split('_')[1]
        results = all_results[damping_key]
        
        complete_count = sum(1 for r in results.values() 
                            if r.get('success', False) and not r.get('boundary_error', True))
        total_points = sum(r.get('points', 0) for r in results.values() if r.get('success', False))
        
        print(f"Damping {damping_val}:")
        print(f"  Complete: {complete_count}/{len(test_locations)} ({complete_count/len(test_locations)*100:.1f}%)")
        print(f"  Total points: {total_points}/{len(test_locations)*25} ({total_points/(len(test_locations)*25)*100:.1f}%)")
        print()
    
    # Analyze vertical motion
    print("=" * 80)
    print("VERTICAL MOTION ANALYSIS")
    print("=" * 80)
    print()
    
    import numpy as np
    
    for loc in test_locations:
        name = loc['name']
        print(f"{name}:")
        
        for damping_key in ['damping_1.0', 'damping_0.5', 'damping_0.3']:
            damping_val = damping_key.split('_')[1]
            result = all_results[damping_key].get(name, {})
            
            if not result.get('success'):
                continue
            
            traj = result.get('trajectory', [])
            if len(traj) < 2:
                continue
            
            # Calculate pressure change rate
            pressures = [p['pressure'] for p in traj]
            start_p = pressures[0]
            end_p = pressures[-1]
            hours = len(traj) - 1
            
            pressure_change = start_p - end_p  # Positive = ascent
            avg_rate = pressure_change / hours if hours > 0 else 0
            
            print(f"  Damping {damping_val}: {start_p:.1f} → {end_p:.1f} hPa "
                  f"({pressure_change:+.1f} hPa, {avg_rate:+.1f} hPa/h)")
        
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    
    baseline_results = all_results['damping_1.0']
    baseline_complete = sum(1 for r in baseline_results.values() 
                           if r.get('success', False) and not r.get('boundary_error', True))
    
    print(f"Baseline (damping=1.0): {baseline_complete}/{len(test_locations)} complete")
    
    for damping_key in ['damping_0.5', 'damping_0.3']:
        damping_val = damping_key.split('_')[1]
        results = all_results[damping_key]
        
        complete_count = sum(1 for r in results.values() 
                            if r.get('success', False) and not r.get('boundary_error', True))
        improvement = complete_count - baseline_complete
        
        print(f"Damping {damping_val}: {complete_count}/{len(test_locations)} complete "
              f"({improvement:+d} improvement)")
    
    print()
    
    # Recommendations
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print()
    
    best_damping = None
    best_complete = baseline_complete
    
    for damping_key in ['damping_0.5', 'damping_0.3']:
        damping_val = float(damping_key.split('_')[1])
        results = all_results[damping_key]
        
        complete_count = sum(1 for r in results.values() 
                            if r.get('success', False) and not r.get('boundary_error', True))
        
        if complete_count > best_complete:
            best_complete = complete_count
            best_damping = damping_val
    
    if best_damping is not None:
        print(f"✅ RECOMMENDED: vertical_damping = {best_damping}")
        print(f"   Improvement: {baseline_complete}/{len(test_locations)} → "
              f"{best_complete}/{len(test_locations)} complete")
        print()
        print("To apply:")
        print(f"  config = SimulationConfig(")
        print(f"      # ...")
        print(f"      vertical_damping={best_damping},")
        print(f"  )")
    else:
        print("⚠️ No improvement found with tested damping values")
        print("   Consider:")
        print("   1. Testing more aggressive damping (0.1, 0.2)")
        print("   2. Different approach (further GFS extension)")
        print("   3. Accepting current state")
    
    print()
    print("Next steps:")
    print("  1. Test all 8 locations with optimal damping")
    print("  2. Measure pressure and horizontal errors")
    print("  3. Compare with HYSPLIT Web (if available)")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    test_vertical_damping()
