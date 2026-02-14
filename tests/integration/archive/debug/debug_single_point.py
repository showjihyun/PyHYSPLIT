"""단일 포인트 상세 디버깅"""
import netCDF4
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pyhysplit.models import StartLocation, SimulationConfig, MetData
from pyhysplit.engine import TrajectoryEngine
from pyhysplit.interpolator import Interpolator

# GFS 데이터 로드
ds = netCDF4.Dataset('tests/integration/gfs_cache/gfs_eastasia_24h_real.nc')

u_data = np.array(ds.variables['u'][:])
v_data = np.array(ds.variables['v'][:])
omega_data = np.array(ds.variables['w'][:])  # Pa/s
t_data = np.array(ds.variables['t'][:])

lat_grid = np.array(ds.variables['latitude'][:])
lon_grid = np.array(ds.variables['longitude'][:])
lev_grid = np.array(ds.variables['level'][:])  # hPa
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
w_data = omega_data / 100.0  # Pa/s → hPa/s

met_data = MetData(
    u=u_data, v=v_data, w=w_data, t_field=t_data,
    lat_grid=lat_grid, lon_grid=lon_grid,
    z_grid=lev_grid, t_grid=time_grid,
    z_type="pressure", source="GFS_NC"
)

print("="*80)
print("  서울 시작점 상세 분석")
print("="*80)

# 서울 시작점
lat, lon, height = 37.5, 127.0, 850.0  # hPa

print(f"\n시작 위치: {lat}°N, {lon}°E, {height} hPa")

# 보간기 생성
interp = Interpolator(met_data)

# t=0에서의 풍속 보간
t = 0.0
u, v, w = interp.interpolate_4d(lon, lat, height, t)

print(f"\n보간된 풍속 (t=0):")
print(f"  u: {u:.6f} m/s (동서 방향)")
print(f"  v: {v:.6f} m/s (남북 방향)")
print(f"  w: {w:.6f} hPa/s (수직 방향, 압력 좌표)")

# 수평 속도
horizontal_speed = np.sqrt(u**2 + v**2)
print(f"  수평 속도: {horizontal_speed:.6f} m/s ({horizontal_speed * 3.6:.2f} km/h)")

# 방향
if abs(u) > abs(v):
    direction = "동쪽" if u > 0 else "서쪽"
else:
    direction = "북쪽" if v > 0 else "남쪽"
print(f"  주요 방향: {direction}")

# 수직 운동
if w > 0:
    vertical_motion = "하강 (압력 증가)"
elif w < 0:
    vertical_motion = "상승 (압력 감소)"
else:
    vertical_motion = "정체"
print(f"  수직 운동: {vertical_motion}")

# 1시간 후 예상 위치 (간단한 Euler 방법)
dt = -3600.0  # backward 1 hour
EARTH_RADIUS = 6371000.0

lat_rad = np.deg2rad(lat)
dlat_rad = (v * dt) / EARTH_RADIUS
dlon_rad = (u * dt) / (EARTH_RADIUS * np.cos(lat_rad))

new_lon = lon + np.rad2deg(dlon_rad)
new_lat = lat + np.rad2deg(dlat_rad)
new_height = height + w * dt  # hPa

print(f"\n1시간 후 예상 위치 (Euler):")
print(f"  위치: {new_lat:.3f}°N, {new_lon:.3f}°E, {new_height:.1f} hPa")

# HYSPLIT Web 결과와 비교
print(f"\nHYSPLIT Web 1시간 후 (tdump 파일):")
print(f"  위치: 37.447°N, 126.763°E, 874.3 hPa")

# 차이 계산
from math import radians, sin, cos, sqrt, atan2

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1_rad, lat2_rad = radians(lat1), radians(lat2)
    dlon = radians(lon2 - lon1)
    dlat = lat2_rad - lat1_rad
    
    a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

hysplit_lat, hysplit_lon, hysplit_height = 37.447, 126.763, 874.3

horizontal_error = haversine(new_lat, new_lon, hysplit_lat, hysplit_lon)
vertical_error = abs(new_height - hysplit_height)

print(f"\n오차:")
print(f"  수평: {horizontal_error:.2f} km")
print(f"  수직: {vertical_error:.1f} hPa")

# PyHYSPLIT 실제 실행
print(f"\n" + "="*80)
print("  PyHYSPLIT 실제 실행 (Heun 적분)")
print("="*80)

start_time = datetime(2026, 2, 14, 0, 0)
start_loc = StartLocation(lat=lat, lon=lon, height=height)

config = SimulationConfig(
    start_time=start_time,
    num_start_locations=1,
    start_locations=[start_loc],
    total_run_hours=-1,  # 1시간만
    vertical_motion=0,
    model_top=10000.0,
    met_files=[],
    turbulence_on=False,
    dt_max=15.0,
    scale_height=8430.0,
    tratio=0.75
)

engine = TrajectoryEngine(config, met_data)
trajectory = engine.run(output_interval_s=3600.0)[0]

print(f"\n궤적 포인트 수: {len(trajectory)}")
for i, pt in enumerate(trajectory):
    t_sec, lon_val, lat_val, height_val = pt
    print(f"  Point {i}: t={t_sec/3600:.1f}h, {lat_val:.3f}°N, {lon_val:.3f}°E, {height_val:.1f} hPa")

if len(trajectory) >= 2:
    final_pt = trajectory[-1]
    t_sec, lon_val, lat_val, height_val = final_pt
    
    horizontal_error = haversine(lat_val, lon_val, hysplit_lat, hysplit_lon)
    vertical_error = abs(height_val - hysplit_height)
    
    print(f"\nPyHYSPLIT vs HYSPLIT Web:")
    print(f"  수평 오차: {horizontal_error:.2f} km")
    print(f"  수직 오차: {vertical_error:.1f} hPa")
