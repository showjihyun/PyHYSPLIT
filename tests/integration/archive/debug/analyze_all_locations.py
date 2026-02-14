"""모든 위치의 압력 오차 패턴 분석"""
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

# 테스트 위치
locations = {
    '서울': (37.5, 127.0),
    '부산': (35.1, 129.0),
    '제주': (33.5, 126.5),
    '도쿄': (35.7, 139.7),
    '오사카': (34.7, 135.5),
    '베이징': (39.9, 116.4),
    '상하이': (31.2, 121.5),
    '타이베이': (25.0, 121.5),
}

def read_hysplit_trajectory(location_name):
    """tdump 파일에서 전체 궤적 읽기"""
    tdump_file = f"tests/integration/hysplit_web_data/tdump_{location_name}.txt"
    trajectory = []
    try:
        with open(tdump_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[8:]:  # 9번째 줄부터 데이터
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
print("  모든 위치 압력 오차 패턴 분석")
print("="*100)

results = []

for name, (lat, lon) in locations.items():
    pressure = 850.0
    
    # HYSPLIT Web 결과 읽기
    hysplit_traj = read_hysplit_trajectory(name)
    if not hysplit_traj:
        continue
    
    # PyHYSPLIT 계산
    start_loc = StartLocation(lat=lat, lon=lon, height=pressure, height_type="pressure")
    config = SimulationConfig(
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
    
    engine = TrajectoryEngine(config, met_data)
    trajectory = engine.run(output_interval_s=3600.0)[0]
    
    # 압력 변화 분석
    py_pressures = [trajectory[i][3] for i in range(min(len(trajectory), len(hysplit_traj)))]
    hy_pressures = [hysplit_traj[i]['pressure'] for i in range(min(len(trajectory), len(hysplit_traj)))]
    
    py_start = py_pressures[0]
    py_end = py_pressures[-1]
    py_change = py_end - py_start
    
    hy_start = hy_pressures[0]
    hy_end = hy_pressures[-1]
    hy_change = hy_end - hy_start
    
    # 오차 계산
    pressure_errors = [abs(py_pressures[i] - hy_pressures[i]) for i in range(len(py_pressures))]
    mean_error = np.mean(pressure_errors)
    max_error = np.max(pressure_errors)
    
    # 수평 오차 계산
    horizontal_errors = []
    for i in range(len(trajectory)):
        if i < len(hysplit_traj):
            py_lat, py_lon = trajectory[i][1], trajectory[i][2]
            hy_lat, hy_lon = hysplit_traj[i]['lat'], hysplit_traj[i]['lon']
            h_error = haversine(py_lat, py_lon, hy_lat, hy_lon)
            horizontal_errors.append(h_error)
    
    mean_h_error = np.mean(horizontal_errors)
    
    results.append({
        'name': name,
        'lat': lat,
        'lon': lon,
        'py_start': py_start,
        'py_end': py_end,
        'py_change': py_change,
        'hy_start': hy_start,
        'hy_end': hy_end,
        'hy_change': hy_change,
        'start_diff': py_start - hy_start,
        'change_diff': py_change - hy_change,
        'mean_p_error': mean_error,
        'max_p_error': max_error,
        'mean_h_error': mean_h_error,
    })

# 결과 출력
print(f"\n{'위치':^10} {'시작 차이':>10} {'변화 차이':>10} {'평균 P 오차':>12} {'평균 H 오차':>12} {'PyΔP':>10} {'HyΔP':>10}")
print("-"*100)

for r in sorted(results, key=lambda x: x['mean_p_error'], reverse=True):
    print(f"{r['name']:^10} {r['start_diff']:>10.1f} {r['change_diff']:>10.1f} "
          f"{r['mean_p_error']:>12.1f} {r['mean_h_error']:>12.1f} "
          f"{r['py_change']:>10.1f} {r['hy_change']:>10.1f}")

# 패턴 분석
print("\n" + "="*100)
print("  패턴 분석")
print("="*100)

# 시작 압력 차이와 오차의 상관관계
start_diffs = [r['start_diff'] for r in results]
p_errors = [r['mean_p_error'] for r in results]
change_diffs = [abs(r['change_diff']) for r in results]

print(f"\n시작 압력 차이:")
print(f"  평균: {np.mean(start_diffs):.1f} hPa")
print(f"  표준편차: {np.std(start_diffs):.1f} hPa")
print(f"  범위: {np.min(start_diffs):.1f} ~ {np.max(start_diffs):.1f} hPa")

print(f"\n압력 변화량 차이:")
print(f"  평균: {np.mean(change_diffs):.1f} hPa")
print(f"  표준편차: {np.std(change_diffs):.1f} hPa")
print(f"  범위: {np.min(change_diffs):.1f} ~ {np.max(change_diffs):.1f} hPa")

print(f"\n압력 오차:")
print(f"  평균: {np.mean(p_errors):.1f} hPa")
print(f"  표준편차: {np.std(p_errors):.1f} hPa")
print(f"  범위: {np.min(p_errors):.1f} ~ {np.max(p_errors):.1f} hPa")

# 상관관계
corr_start = np.corrcoef(start_diffs, p_errors)[0, 1]
corr_change = np.corrcoef(change_diffs, p_errors)[0, 1]

print(f"\n상관관계:")
print(f"  시작 압력 차이 vs 압력 오차: {corr_start:.3f}")
print(f"  변화량 차이 vs 압력 오차: {corr_change:.3f}")

# 압력 변화 방향 분석
print(f"\n압력 변화 방향:")
for r in results:
    py_dir = "하강" if r['py_change'] < 0 else "상승"
    hy_dir = "하강" if r['hy_change'] < 0 else "상승"
    match = "✓" if py_dir == hy_dir else "✗"
    print(f"  {r['name']:^10}: PyHYSPLIT {py_dir:^4} ({r['py_change']:+7.1f} hPa), "
          f"HYSPLIT {hy_dir:^4} ({r['hy_change']:+7.1f} hPa) {match}")
