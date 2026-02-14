"""베이징 압력 오차 진단"""
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

# 베이징 테스트
lat, lon, pressure = 39.9, 116.4, 850.0

# HYSPLIT Web 결과 읽기
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

hysplit_traj = read_hysplit_trajectory('베이징')

print("="*90)
print("  베이징 압력 오차 진단")
print("="*90)

print(f"\n시작 위치: {lat}°N, {lon}°E, {pressure} hPa")
print(f"HYSPLIT Web 시작 압력: {hysplit_traj[0]['pressure']:.1f} hPa")

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

print(f"\n{'Hour':>6} {'PyHYSPLIT P':>13} {'HYSPLIT P':>13} {'Δ P':>10} {'PyHYSPLIT H':>13} {'HYSPLIT H':>13} {'Δ H':>10}")
print("-"*90)

pressure_errors = []
height_errors = []

for i, hysplit in enumerate(hysplit_traj):
    if i < len(trajectory):
        pyhysplit = trajectory[i]
        age = pyhysplit[0] / 3600.0
        py_p = pyhysplit[3]
        py_h = pyhysplit[4] if len(pyhysplit) > 4 else 0
        hy_p = hysplit['pressure']
        hy_h = hysplit['height']
        
        delta_p = py_p - hy_p
        delta_h = py_h - hy_h
        
        pressure_errors.append(abs(delta_p))
        height_errors.append(abs(delta_h))
        
        print(f"{age:>6.0f} {py_p:>13.1f} {hy_p:>13.1f} {delta_p:>10.1f} {py_h:>13.1f} {hy_h:>13.1f} {delta_h:>10.1f}")

print(f"\n{'='*90}")
print("  오차 분석")
print(f"{'='*90}")

print(f"\n압력 오차:")
print(f"  평균: {np.mean(pressure_errors):.1f} hPa")
print(f"  최대: {np.max(pressure_errors):.1f} hPa")
print(f"  최소: {np.min(pressure_errors):.1f} hPa")
print(f"  표준편차: {np.std(pressure_errors):.1f} hPa")

print(f"\n고도 오차:")
print(f"  평균: {np.mean(height_errors):.1f} m")
print(f"  최대: {np.max(height_errors):.1f} m")

# 압력 변화 패턴 분석
print(f"\n{'='*90}")
print("  압력 변화 패턴")
print(f"{'='*90}")

py_pressures = [trajectory[i][3] for i in range(min(len(trajectory), len(hysplit_traj)))]
hy_pressures = [hysplit_traj[i]['pressure'] for i in range(min(len(trajectory), len(hysplit_traj)))]

py_change = py_pressures[-1] - py_pressures[0]
hy_change = hy_pressures[-1] - hy_pressures[0]

print(f"\nPyHYSPLIT:")
print(f"  시작: {py_pressures[0]:.1f} hPa")
print(f"  종료: {py_pressures[-1]:.1f} hPa")
print(f"  변화: {py_change:+.1f} hPa")

print(f"\nHYSPLIT Web:")
print(f"  시작: {hy_pressures[0]:.1f} hPa")
print(f"  종료: {hy_pressures[-1]:.1f} hPa")
print(f"  변화: {hy_change:+.1f} hPa")

print(f"\n차이:")
print(f"  시작 압력 차이: {py_pressures[0] - hy_pressures[0]:+.1f} hPa")
print(f"  종료 압력 차이: {py_pressures[-1] - hy_pressures[-1]:+.1f} hPa")
print(f"  변화량 차이: {py_change - hy_change:+.1f} hPa")

# 진단
print(f"\n{'='*90}")
print("  진단")
print(f"{'='*90}")

if abs(py_pressures[0] - hy_pressures[0]) > 50:
    print(f"\n⚠️ 시작 압력 차이가 큼: {abs(py_pressures[0] - hy_pressures[0]):.1f} hPa")
    print(f"   → 압력 레벨 변환 문제")
    print(f"   → 베이징의 실제 오프셋: {hy_pressures[0] - 850:.1f} hPa")
    print(f"   → 현재 사용 중인 오프셋: {py_pressures[0] - 850:.1f} hPa")

if abs(py_change - hy_change) > 50:
    print(f"\n⚠️ 압력 변화량 차이가 큼: {abs(py_change - hy_change):.1f} hPa")
    print(f"   → 수직 속도 처리 문제")
    print(f"   → PyHYSPLIT이 {'더 많이' if abs(py_change) > abs(hy_change) else '덜'} 하강/상승")

# 베이징 위치의 GFS 데이터 확인
lat_idx = np.argmin(np.abs(lat_grid - lat))
lon_idx = np.argmin(np.abs(lon_grid - lon))
lev_850_idx = np.argmin(np.abs(lev_grid - 850))

print(f"\n{'='*90}")
print("  GFS 데이터 확인 (베이징 위치)")
print(f"{'='*90}")

print(f"\n그리드 위치:")
print(f"  Latitude: {lat_grid[lat_idx]:.2f}°N (요청: {lat}°N)")
print(f"  Longitude: {lon_grid[lon_idx]:.2f}°E (요청: {lon}°E)")
print(f"  Level: {lev_grid[lev_850_idx]:.1f} hPa (요청: 850 hPa)")

print(f"\n850 hPa 레벨 데이터 (시작 시간):")
u_850 = u_data[0, lev_850_idx, lat_idx, lon_idx]
v_850 = v_data[0, lev_850_idx, lat_idx, lon_idx]
w_850 = w_data[0, lev_850_idx, lat_idx, lon_idx]
t_850 = t_data[0, lev_850_idx, lat_idx, lon_idx]

print(f"  U: {u_850:.2f} m/s")
print(f"  V: {v_850:.2f} m/s")
print(f"  W: {w_850:.6f} hPa/s")
print(f"  T: {t_850:.1f} K ({t_850-273.15:.1f}°C)")
