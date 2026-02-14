"""HYSPLIT Web과 동일한 시작 압력 사용 테스트"""
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

# 서울 테스트
lat, lon = 37.5, 127.0

# HYSPLIT Web 결과
hysplit_results = [
    {'age': 0.0, 'lat': 37.500, 'lon': 127.000, 'pressure': 906.3},
    {'age': -1.0, 'lat': 37.447, 'lon': 126.763, 'pressure': 909.1},
    {'age': -2.0, 'lat': 37.358, 'lon': 126.530, 'pressure': 914.2},
    {'age': -3.0, 'lat': 37.246, 'lon': 126.313, 'pressure': 917.4},
    {'age': -4.0, 'lat': 37.129, 'lon': 126.100, 'pressure': 920.9},
    {'age': -5.0, 'lat': 37.004, 'lon': 125.887, 'pressure': 923.6},
    {'age': -6.0, 'lat': 36.859, 'lon': 125.681, 'pressure': 924.1},
    {'age': -7.0, 'lat': 36.687, 'lon': 125.490, 'pressure': 926.5},
    {'age': -8.0, 'lat': 36.491, 'lon': 125.300, 'pressure': 931.9},
]

print("="*90)
print("  HYSPLIT Web과 동일한 시작 압력 사용 테스트")
print("="*90)

# HYSPLIT Web의 시작 압력 사용
hysplit_start_pressure = hysplit_results[0]['pressure']

print(f"\n시작 위치: {lat}°N, {lon}°E")
print(f"HYSPLIT Web 시작 압력: {hysplit_start_pressure} hPa")
print(f"PyHYSPLIT 시작 압력: {hysplit_start_pressure} hPa (동일하게 설정)")

start_loc = StartLocation(lat=lat, lon=lon, height=hysplit_start_pressure, height_type="pressure")

config = SimulationConfig(
    start_time=datetime(2026, 2, 14, 0, 0),
    num_start_locations=1,
    start_locations=[start_loc],
    total_run_hours=-8,
    vertical_motion=0,
    model_top=10000.0,
    met_files=[],
    turbulence_on=False,
    dt_max=15.0,
    tratio=0.75
)

engine = TrajectoryEngine(config, met_data)
trajectory = engine.run(output_interval_s=3600.0)[0]

print(f"\n{'Hour':>6} {'PyHYSPLIT Lat':>15} {'HYSPLIT Lat':>15} {'Δ Lat':>10} "
      f"{'PyHYSPLIT Lon':>15} {'HYSPLIT Lon':>15} {'Δ Lon':>10} "
      f"{'PyHYSPLIT P':>13} {'HYSPLIT P':>13} {'Δ P':>10} {'H_Err(km)':>12}")
print("-"*90)

cumulative_h_errors = []
cumulative_p_errors = []

for i, hysplit in enumerate(hysplit_results):
    if i < len(trajectory):
        pyhysplit = trajectory[i]
        age = pyhysplit[0] / 3600.0
        py_lat, py_lon, py_p = pyhysplit[2], pyhysplit[1], pyhysplit[3]
        hy_lat, hy_lon, hy_p = hysplit['lat'], hysplit['lon'], hysplit['pressure']
        
        delta_lat = py_lat - hy_lat
        delta_lon = py_lon - hy_lon
        delta_p = py_p - hy_p
        h_error = haversine(py_lat, py_lon, hy_lat, hy_lon)
        
        cumulative_h_errors.append(h_error)
        cumulative_p_errors.append(abs(delta_p))
        
        print(f"{age:>6.0f} {py_lat:>15.3f} {hy_lat:>15.3f} {delta_lat:>10.3f} "
              f"{py_lon:>15.3f} {hy_lon:>15.3f} {delta_lon:>10.3f} "
              f"{py_p:>13.1f} {hy_p:>13.1f} {delta_p:>10.1f} {h_error:>12.2f}")

print(f"\n{'='*90}")
print("  오차 통계")
print(f"{'='*90}")

print(f"\n수평 오차:")
print(f"  평균: {np.mean(cumulative_h_errors):.2f} km")
print(f"  최대: {np.max(cumulative_h_errors):.2f} km")
print(f"  최소: {np.min(cumulative_h_errors):.2f} km")

print(f"\n압력 오차:")
print(f"  평균: {np.mean(cumulative_p_errors):.1f} hPa")
print(f"  최대: {np.max(cumulative_p_errors):.1f} hPa")
print(f"  최소: {np.min(cumulative_p_errors):.1f} hPa")

print(f"\n초기 오차 (0시간):")
print(f"  수평: {cumulative_h_errors[0]:.2f} km")
print(f"  압력: {cumulative_p_errors[0]:.1f} hPa")

# 이전 결과와 비교
print(f"\n{'='*90}")
print("  개선 효과")
print(f"{'='*90}")
print(f"\n850 hPa 시작 (이전):")
print(f"  초기 압력 오차: 56.3 hPa")
print(f"  8시간 후 수평 오차: 185.14 km")
print(f"  8시간 후 압력 오차: 68.9 hPa")

print(f"\n{hysplit_start_pressure} hPa 시작 (현재):")
print(f"  초기 압력 오차: {cumulative_p_errors[0]:.1f} hPa")
print(f"  8시간 후 수평 오차: {cumulative_h_errors[-1]:.2f} km")
print(f"  8시간 후 압력 오차: {cumulative_p_errors[-1]:.1f} hPa")

if len(cumulative_h_errors) > 0:
    h_improvement = 185.14 - cumulative_h_errors[-1]
    p_improvement = 68.9 - cumulative_p_errors[-1]
    print(f"\n개선:")
    print(f"  수평 오차: {h_improvement:+.2f} km ({h_improvement/185.14*100:+.1f}%)")
    print(f"  압력 오차: {p_improvement:+.1f} hPa ({p_improvement/68.9*100:+.1f}%)")
