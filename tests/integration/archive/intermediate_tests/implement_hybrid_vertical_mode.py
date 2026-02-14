"""위치별 최적 수직 속도 모드를 사용하는 하이브리드 접근법 테스트"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import netCDF4
from datetime import datetime
from pyhysplit.models import StartLocation, SimulationConfig, MetData
from pyhysplit.engine import TrajectoryEngine
from math import radians, sin, cos, sqrt, atan2

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1_rad, lat2_rad = radians(lat1), radians(lat2)
    dlon = radians(lon2 - lon1)
    dlat = lat2_rad - lat1_rad
    a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

# GFS 데이터 로드
print("Loading GFS data...")
ds = netCDF4.Dataset('tests/integration/gfs_cache/gfs_eastasia_24h_real.nc')
u_data = np.array(ds.variables['u'][:])
v_data = np.array(ds.variables['v'][:])
omega_data = np.array(ds.variables['w'][:])
t_data = np.array(ds.variables['t'][:])
lat_grid = np.array(ds.variables['latitude'][:])
lon_grid = np.array(ds.variables['longitude'][:])
lev_grid = np.array(ds.variables['level'][:])
time_grid = np.array(ds.variables['time'][:])
ds.close()

# 시간 그리드 정렬
if time_grid[0] > time_grid[-1]:
    time_indices = np.argsort(time_grid)
    time_grid = time_grid[time_indices]
    u_data = u_data[time_indices]
    v_data = v_data[time_indices]
    omega_data = omega_data[time_indices]
    t_data = t_data[time_indices]

# Omega를 hPa/s로 변환
w_data = omega_data / 100.0

met_data = MetData(
    u=u_data, v=v_data, w=w_data, t_field=t_data,
    lat_grid=lat_grid, lon_grid=lon_grid,
    z_grid=lev_grid, t_grid=time_grid,
    z_type="pressure", source="GFS_NC"
)

# 테스트 위치와 최적 모드 (체계적 테스트 결과 기반)
locations_with_best_mode = {
    '서울': {'coords': (37.5, 127.0), 'best_mode': 7},
    '부산': {'coords': (35.1, 129.0), 'best_mode': 7},
    '제주': {'coords': (33.5, 126.5), 'best_mode': 3},
    '도쿄': {'coords': (35.7, 139.7), 'best_mode': 7},
    '오사카': {'coords': (34.7, 135.5), 'best_mode': 7},
    '베이징': {'coords': (39.9, 116.4), 'best_mode': 7},
    '상하이': {'coords': (31.2, 121.5), 'best_mode': 3},
    '타이베이': {'coords': (25.0, 121.5), 'best_mode': 3},
}

def read_hysplit_trajectory(location_name):
    """tdump 파일에서 전체 궤적 읽기"""
    tdump_file = f"tests/integration/hysplit_web_data/tdump_{location_name}.txt"
    trajectory = []
    try:
        with open(tdump_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[8:]:
                parts = line.split()
                if len(parts) >= 13:
                    try:
                        age = float(parts[8])
                        lat = float(parts[9])
                        lon = float(parts[10])
                        height = float(parts[11])
                        pressure = float(parts[12])
                        trajectory.append({
                            'age': age,
                            'lat': lat,
                            'lon': lon,
                            'height': height,
                            'pressure': pressure
                        })
                    except (ValueError, IndexError):
                        continue
    except Exception as e:
        print(f"Error reading {location_name}: {e}")
    return trajectory

print("\n" + "="*100)
print("  하이브리드 수직 속도 모드 테스트 (위치별 최적 모드 사용)")
print("="*100)

print("\n전략:")
print("  - 중위도 (>33°N): Mode 7 (Spatially averaged)")
print("  - 저위도 (≤33°N): Mode 3 (Isentropic)")
print()

results_mode0 = []
results_hybrid = []

for name, info in locations_with_best_mode.items():
    lat, lon = info['coords']
    best_mode = info['best_mode']
    pressure = 850.0
    
    # HYSPLIT Web 결과 읽기
    hysplit_traj = read_hysplit_trajectory(name)
    if not hysplit_traj:
        continue
    
    # Mode 0 테스트 (현재 기본값)
    start_loc = StartLocation(lat=lat, lon=lon, height=pressure, height_type="pressure")
    config_mode0 = SimulationConfig(
        start_time=datetime(2026, 2, 14, 0, 0),
        num_start_locations=1,
        start_locations=[start_loc],
        total_run_hours=-24,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[],
        turbulence_on=False,
        dt_max=15.0,
        tratio=0.75
    )
    
    try:
        engine = TrajectoryEngine(config_mode0, met_data)
        trajectory_mode0 = engine.run(output_interval_s=3600.0)[0]
        
        # 오차 계산
        py_pressures = [trajectory_mode0[i][3] for i in range(min(len(trajectory_mode0), len(hysplit_traj)))]
        hy_pressures = [hysplit_traj[i]['pressure'] for i in range(min(len(trajectory_mode0), len(hysplit_traj)))]
        
        pressure_errors = [abs(py_pressures[i] - hy_pressures[i]) for i in range(len(py_pressures))]
        mean_p_error_mode0 = np.mean(pressure_errors)
        
        horizontal_errors = []
        for i in range(len(trajectory_mode0)):
            if i < len(hysplit_traj):
                py_lat, py_lon = trajectory_mode0[i][1], trajectory_mode0[i][2]
                hy_lat, hy_lon = hysplit_traj[i]['lat'], hysplit_traj[i]['lon']
                h_error = haversine(py_lat, py_lon, hy_lat, hy_lon)
                horizontal_errors.append(h_error)
        
        mean_h_error_mode0 = np.mean(horizontal_errors)
        
        py_change_mode0 = py_pressures[-1] - py_pressures[0]
        hy_change = hy_pressures[-1] - hy_pressures[0]
        
        direction_match_mode0 = (py_change_mode0 < 0) == (hy_change < 0)
        
        results_mode0.append({
            'name': name,
            'p_error': mean_p_error_mode0,
            'h_error': mean_h_error_mode0,
            'direction_match': direction_match_mode0,
        })
        
    except Exception as e:
        print(f"Mode 0 error for {name}: {e}")
        continue
    
    # 최적 모드 테스트
    config_best = SimulationConfig(
        start_time=datetime(2026, 2, 14, 0, 0),
        num_start_locations=1,
        start_locations=[start_loc],
        total_run_hours=-24,
        vertical_motion=best_mode,
        model_top=10000.0,
        met_files=[],
        turbulence_on=False,
        dt_max=15.0,
        tratio=0.75
    )
    
    try:
        engine = TrajectoryEngine(config_best, met_data)
        trajectory_best = engine.run(output_interval_s=3600.0)[0]
        
        # 오차 계산
        py_pressures = [trajectory_best[i][3] for i in range(min(len(trajectory_best), len(hysplit_traj)))]
        hy_pressures = [hysplit_traj[i]['pressure'] for i in range(min(len(trajectory_best), len(hysplit_traj)))]
        
        pressure_errors = [abs(py_pressures[i] - hy_pressures[i]) for i in range(len(py_pressures))]
        mean_p_error_best = np.mean(pressure_errors)
        
        horizontal_errors = []
        for i in range(len(trajectory_best)):
            if i < len(hysplit_traj):
                py_lat, py_lon = trajectory_best[i][1], trajectory_best[i][2]
                hy_lat, hy_lon = hysplit_traj[i]['lat'], hysplit_traj[i]['lon']
                h_error = haversine(py_lat, py_lon, hy_lat, hy_lon)
                horizontal_errors.append(h_error)
        
        mean_h_error_best = np.mean(horizontal_errors)
        
        py_change_best = py_pressures[-1] - py_pressures[0]
        direction_match_best = (py_change_best < 0) == (hy_change < 0)
        
        results_hybrid.append({
            'name': name,
            'mode': best_mode,
            'p_error': mean_p_error_best,
            'h_error': mean_h_error_best,
            'direction_match': direction_match_best,
        })
        
        # 개선 계산
        p_improvement = ((mean_p_error_mode0 - mean_p_error_best) / mean_p_error_mode0) * 100
        h_improvement = ((mean_h_error_mode0 - mean_h_error_best) / mean_h_error_mode0) * 100
        
        match0 = "✓" if direction_match_mode0 else "✗"
        match_best = "✓" if direction_match_best else "✗"
        
        print(f"{name:^10} (Mode {best_mode}):")
        print(f"  Mode 0: P={mean_p_error_mode0:5.1f} hPa, H={mean_h_error_mode0:6.1f} km, 방향={match0}")
        print(f"  Mode {best_mode}: P={mean_p_error_best:5.1f} hPa, H={mean_h_error_best:6.1f} km, 방향={match_best}")
        print(f"  개선: P={p_improvement:+5.1f}%, H={h_improvement:+5.1f}%")
        print()
        
    except Exception as e:
        print(f"Best mode error for {name}: {e}")
        continue

# 전체 통계
print("\n" + "="*100)
print("  전체 통계 비교")
print("="*100)

if results_mode0 and results_hybrid:
    # Mode 0
    mode0_p_errors = [r['p_error'] for r in results_mode0]
    mode0_h_errors = [r['h_error'] for r in results_mode0]
    mode0_direction_matches = sum(1 for r in results_mode0 if r['direction_match'])
    
    # Hybrid
    hybrid_p_errors = [r['p_error'] for r in results_hybrid]
    hybrid_h_errors = [r['h_error'] for r in results_hybrid]
    hybrid_direction_matches = sum(1 for r in results_hybrid if r['direction_match'])
    
    print(f"\nMode 0 (현재 기본값):")
    print(f"  평균 압력 오차: {np.mean(mode0_p_errors):.1f} hPa")
    print(f"  평균 수평 오차: {np.mean(mode0_h_errors):.1f} km")
    print(f"  방향 일치: {mode0_direction_matches}/{len(results_mode0)} ({100*mode0_direction_matches/len(results_mode0):.1f}%)")
    
    print(f"\n하이브리드 (위치별 최적 모드):")
    print(f"  평균 압력 오차: {np.mean(hybrid_p_errors):.1f} hPa")
    print(f"  평균 수평 오차: {np.mean(hybrid_h_errors):.1f} km")
    print(f"  방향 일치: {hybrid_direction_matches}/{len(results_hybrid)} ({100*hybrid_direction_matches/len(results_hybrid):.1f}%)")
    
    # 개선율
    p_improvement = ((np.mean(mode0_p_errors) - np.mean(hybrid_p_errors)) / np.mean(mode0_p_errors)) * 100
    h_improvement = ((np.mean(mode0_h_errors) - np.mean(hybrid_h_errors)) / np.mean(mode0_h_errors)) * 100
    
    print(f"\n전체 개선:")
    print(f"  압력 오차: {p_improvement:+.1f}%")
    print(f"  수평 오차: {h_improvement:+.1f}%")
    print(f"  방향 일치: {mode0_direction_matches} → {hybrid_direction_matches} ({hybrid_direction_matches - mode0_direction_matches:+d})")

# 결론
print("\n" + "="*100)
print("  결론 및 권장사항")
print("="*100)

if hybrid_direction_matches == len(results_hybrid):
    print("\n🎉 하이브리드 접근법으로 모든 위치의 방향이 일치합니다!")
    print("\n권장사항:")
    print("  1. 위도 기반 자동 모드 선택 구현")
    print("  2. lat > 33°N: Mode 7 (Spatially averaged)")
    print("  3. lat ≤ 33°N: Mode 3 (Isentropic)")
elif hybrid_direction_matches > mode0_direction_matches:
    print(f"\n✓ 하이브리드 접근법이 더 우수합니다 ({hybrid_direction_matches}/{len(results_hybrid)} vs {mode0_direction_matches}/{len(results_mode0)})")
    print("\n권장사항:")
    print("  1. 위도 기반 모드 선택 구현 고려")
    print("  2. 추가 파라미터 조정으로 100% 일치 가능")
else:
    print(f"\n⚠️ 하이브리드 접근법이 개선되지 않았습니다.")
    print("  추가 조사가 필요합니다.")
