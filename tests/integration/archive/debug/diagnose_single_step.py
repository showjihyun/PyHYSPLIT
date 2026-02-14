"""단일 스텝 상세 진단 - HYSPLIT Web과 PyHYSPLIT 비교"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import netCDF4
from datetime import datetime, timedelta
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
print("  서울 단일 스텝 상세 진단")
print("="*80)

# 서울 시작점 (HYSPLIT Web과 동일)
lat, lon, pressure = 37.5, 127.0, 850.0  # hPa

# HYSPLIT Web 1시간 후 결과 (tdump 파일에서)
hysplit_1h = {
    'lat': 37.447,
    'lon': 126.763,
    'pressure': 874.3
}

print(f"\n시작점: {lat}°N, {lon}°E, {pressure} hPa")
print(f"HYSPLIT Web 1시간 후: {hysplit_1h['lat']}°N, {hysplit_1h['lon']}°E, {hysplit_1h['pressure']} hPa")

# 보간기로 풍속 확인
interp = Interpolator(met_data)
t = 0.0

u, v, w = interp.interpolate_4d(lon, lat, pressure, t)

print(f"\n보간된 풍속 (t=0):")
print(f"  u: {u:.6f} m/s")
print(f"  v: {v:.6f} m/s")
print(f"  w: {w:.6f} hPa/s")

# 수동 Euler 스텝 (1시간)
dt = -3600.0  # backward
EARTH_RADIUS = 6371000.0

lat_rad = np.deg2rad(lat)
dlat_rad = (v * dt) / EARTH_RADIUS
dlon_rad = (u * dt) / (EARTH_RADIUS * np.cos(lat_rad))

euler_lon = lon + np.rad2deg(dlon_rad)
euler_lat = lat + np.rad2deg(dlat_rad)
euler_pressure = pressure + w * dt  # hPa

print(f"\nEuler 방법 (1시간):")
print(f"  위치: {euler_lat:.3f}°N, {euler_lon:.3f}°E, {euler_pressure:.1f} hPa")

# Heun 방법 (predictor-corrector)
# Predictor
lon_p = euler_lon
lat_p = euler_lat
pressure_p = euler_pressure

# Corrector
u2, v2, w2 = interp.interpolate_4d(lon_p, lat_p, pressure_p, t + dt)

lat_rad2 = np.deg2rad(lat_p)
dlat_rad2 = (v2 * dt) / EARTH_RADIUS
dlon_rad2 = (u2 * dt) / (EARTH_RADIUS * np.cos(lat_rad2))

# Average
u_avg = 0.5 * (u + u2)
v_avg = 0.5 * (v + v2)
w_avg = 0.5 * (w + w2)

lat_rad_avg = np.deg2rad(lat)
dlat_rad_avg = (v_avg * dt) / EARTH_RADIUS
dlon_rad_avg = (u_avg * dt) / (EARTH_RADIUS * np.cos(lat_rad_avg))

heun_lon = lon + np.rad2deg(dlon_rad_avg)
heun_lat = lat + np.rad2deg(dlat_rad_avg)
heun_pressure = pressure + w_avg * dt

print(f"\nHeun 방법 (1시간):")
print(f"  위치: {heun_lat:.3f}°N, {heun_lon:.3f}°E, {heun_pressure:.1f} hPa")

# PyHYSPLIT 엔진 실행
start_loc = StartLocation(lat=lat, lon=lon, height=pressure, height_type="pressure")

config = SimulationConfig(
    start_time=datetime(2026, 2, 14, 0, 0),
    num_start_locations=1,
    start_locations=[start_loc],
    total_run_hours=-1,
    vertical_motion=0,
    model_top=10000.0,
    met_files=[],
    turbulence_on=False,
    dt_max=15.0,
    tratio=0.75
)

engine = TrajectoryEngine(config, met_data)
trajectory = engine.run(output_interval_s=3600.0)[0]

if len(trajectory) >= 2:
    py_1h = trajectory[1]
    print(f"\nPyHYSPLIT (1시간):")
    print(f"  위치: {py_1h[2]:.3f}°N, {py_1h[1]:.3f}°E, {py_1h[3]:.1f} hPa")

# 오차 계산
from math import radians, sin, cos, sqrt, atan2

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1_rad, lat2_rad = radians(lat1), radians(lat2)
    dlon = radians(lon2 - lon1)
    dlat = lat2_rad - lat1_rad
    a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

print(f"\n" + "="*80)
print("  오차 분석")
print("="*80)

methods = [
    ("Euler", euler_lat, euler_lon, euler_pressure),
    ("Heun", heun_lat, heun_lon, heun_pressure),
]

if len(trajectory) >= 2:
    methods.append(("PyHYSPLIT", py_1h[2], py_1h[1], py_1h[3]))

for name, lat_val, lon_val, pressure_val in methods:
    h_error = haversine(lat_val, lon_val, hysplit_1h['lat'], hysplit_1h['lon'])
    p_error = abs(pressure_val - hysplit_1h['pressure'])
    print(f"\n{name}:")
    print(f"  수평 오차: {h_error:.2f} km")
    print(f"  압력 오차: {p_error:.1f} hPa")

print(f"\n분석:")
print(f"  - Euler vs Heun: Heun이 더 정확해야 함")
print(f"  - PyHYSPLIT은 여러 작은 스텝으로 나누어 계산")
print(f"  - HYSPLIT Web도 작은 스텝 사용 (정확한 dt 불명)")
