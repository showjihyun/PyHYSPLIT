"""수직 속도 처리를 디버깅하는 스크립트."""

import netCDF4
import numpy as np
from pathlib import Path

# GFS 데이터 로드
cache_file = Path("tests/integration/gfs_cache/gfs_20260213_37.5_127.0_1h.nc")
ds = netCDF4.Dataset(str(cache_file))

lat_grid = np.array(ds.variables["lat"][:])
lon_grid = np.array(ds.variables["lon"][:])
lev_grid = np.array(ds.variables["lev"][:])
t_grid = np.array(ds.variables["time"][:])

omega_data = np.array(ds.variables["w"][:])  # Pa/s
t_data = np.array(ds.variables["t"][:])

ds.close()

# 13:00 UTC (t_grid index 7), 850 hPa 근처
t_idx = 7  # 13:00 UTC
lev_850_idx = np.argmin(np.abs(lev_grid - 850))
lat_center = len(lat_grid) // 2
lon_center = len(lon_grid) // 2

print("=" * 80)
print("수직 속도 디버깅")
print("=" * 80)
print(f"\n시간: {t_grid[t_idx] / 3600:.1f} hours (13:00 UTC)")
print(f"압력 레벨: {lev_grid[lev_850_idx]:.0f} hPa")
print(f"위치: lat={lat_grid[lat_center]:.2f}, lon={lon_grid[lon_center]:.2f}")

# Omega 값
omega = omega_data[t_idx, lev_850_idx, lat_center, lon_center]
T = t_data[t_idx, lev_850_idx, lat_center, lon_center]
P_pa = lev_grid[lev_850_idx] * 100.0

print(f"\nOmega (원본): {omega:.3f} Pa/s")
print(f"온도: {T:.2f} K")
print(f"압력: {P_pa:.0f} Pa ({lev_grid[lev_850_idx]:.0f} hPa)")

# NCL 공식으로 w 계산
RD = 287.0
GRAVITY = 9.81
w_ms = -omega * (RD * T) / (P_pa * GRAVITY)

print(f"\nNCL 공식: w = -omega * (Rd * T) / (p * g)")
print(f"  w = -{omega:.3f} * ({RD} * {T:.2f}) / ({P_pa:.0f} * {GRAVITY})")
print(f"  w = {w_ms:.6f} m/s")

# 역방향 궤적에서 10분 동안의 압력 변화
dt = -600  # 10분 backward
dP_dt = -w_ms * P_pa * GRAVITY / (RD * T)  # Pa/s
dP = dP_dt * dt  # Pa

print(f"\n역방향 궤적 (10분):")
print(f"  dP/dt = {dP_dt:.6f} Pa/s = {dP_dt/100:.6f} hPa/s")
print(f"  dt = {dt} s")
print(f"  dP = {dP:.3f} Pa = {dP/100:.3f} hPa")
print(f"  새 압력 = {P_pa + dP:.0f} Pa = {(P_pa + dP)/100:.1f} hPa")

# 고도 변화 추정
from pyhysplit.coordinate_converter import CoordinateConverter
z_initial = CoordinateConverter.pressure_to_height_hypsometric(
    np.array([P_pa]), np.array([T])
)[0]
z_final = CoordinateConverter.pressure_to_height_hypsometric(
    np.array([P_pa + dP]), np.array([T])
)[0]

print(f"\n고도 변화:")
print(f"  초기 고도: {z_initial:.1f} m")
print(f"  최종 고도: {z_final:.1f} m")
print(f"  고도 변화: {z_final - z_initial:.1f} m")

# 여러 레벨에서 확인
print(f"\n다양한 압력 레벨에서의 omega와 w:")
print(f"{'Level':<10} {'Pressure':<12} {'Omega':<12} {'W':<12} {'dP/10min':<12}")
print("-" * 60)
for k in range(len(lev_grid)):
    omega_k = omega_data[t_idx, k, lat_center, lon_center]
    T_k = t_data[t_idx, k, lat_center, lon_center]
    P_k = lev_grid[k] * 100.0
    w_k = -omega_k * (RD * T_k) / (P_k * GRAVITY)
    dP_k = -w_k * P_k * GRAVITY / (RD * T_k) * dt
    print(f"{k:<10} {lev_grid[k]:<12.0f} {omega_k:<12.3f} {w_k:<12.6f} {dP_k/100:<12.3f}")
