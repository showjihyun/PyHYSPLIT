"""베이징 omega 값 추적 디버깅"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import netCDF4
from datetime import datetime
from pyhysplit.models import StartLocation, SimulationConfig, MetData
from pyhysplit.engine import TrajectoryEngine

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

# 엔진 생성 및 인터폴레이터 접근
engine = TrajectoryEngine(config, met_data)

print("\n베이징 궤적 omega 값 추적")
print("="*100)
print(f"{'Hour':>6} {'Lon':>10} {'Lat':>10} {'P (hPa)':>10} {'Omega (raw)':>15} {'dP/dt':>15} {'dt':>10} {'ΔP':>10}")
print("-"*100)

# 초기 위치
current_lon = lon
current_lat = lat
current_p = pressure + 57.3  # 압력 오프셋 적용
current_t = 0.0
dt = -3600.0  # 1시간 backward

for hour in range(9):
    # 현재 위치에서 omega 보간
    u, v, omega_raw = engine.integrator.interp.interpolate_4d(
        current_lon, current_lat, current_p, current_t
    )
    
    # integrator의 _convert_w_to_dz_dt 호출하여 실제 사용되는 dP/dt 확인
    dP_dt = engine.integrator._convert_w_to_dz_dt(
        omega_raw, current_p, current_t, current_lon, current_lat, dt
    )
    
    # 압력 변화 계산
    delta_p = dP_dt * dt
    
    print(f"{-hour:>6} {current_lon:>10.2f} {current_lat:>10.2f} {current_p:>10.1f} "
          f"{omega_raw:>15.6f} {dP_dt:>15.6f} {dt:>10.1f} {delta_p:>10.1f}")
    
    # 다음 위치로 이동 (간단한 Euler 방식으로 근사)
    if hour < 8:
        # Heun step 수행
        new_lon, new_lat, new_p = engine.integrator.step(
            current_lon, current_lat, current_p, current_t, dt
        )
        current_lon = new_lon
        current_lat = new_lat
        current_p = new_p
        current_t += dt

print("\n분석:")
print("- Omega (raw): GFS 데이터에서 보간된 원시 omega 값 (hPa/s)")
print("- dP/dt: integrator가 실제 사용하는 압력 변화율 (backward trajectory에서 부호 반전)")
print("- dt: 시간 스텝 (backward이므로 음수)")
print("- ΔP: 실제 압력 변화량 = dP/dt * dt")
print("\n예상 동작:")
print("- Omega > 0 (하강): backward에서 dP/dt < 0 (부호 반전) → ΔP > 0 (상승)")
print("- Omega < 0 (상승): backward에서 dP/dt > 0 (부호 반전) → ΔP < 0 (하강)")
