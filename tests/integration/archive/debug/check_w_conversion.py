"""Omega → w 변환 검증."""

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

# 변환 상수
RD = 287.0
GRAVITY = 9.81

print("=" * 80)
print("Omega → W 변환 검증")
print("=" * 80)

# 13:00 UTC, 850 hPa 근처, 중심 위치
t_idx = 7
lev_850_idx = np.argmin(np.abs(lev_grid - 850))
lat_center = len(lat_grid) // 2
lon_center = len(lon_grid) // 2

omega = omega_data[t_idx, lev_850_idx, lat_center, lon_center]
T = t_data[t_idx, lev_850_idx, lat_center, lon_center]
P_pa = lev_grid[lev_850_idx] * 100.0

print(f"\n13:00 UTC, 850 hPa, 중심 위치:")
print(f"  Omega: {omega:.3f} Pa/s")
print(f"  T: {T:.2f} K")
print(f"  P: {P_pa:.0f} Pa")

# NCL 공식
w_ncl = -omega * (RD * T) / (P_pa * GRAVITY)
print(f"\nNCL 공식: w = -omega * (Rd * T) / (p * g)")
print(f"  w = {w_ncl:.6f} m/s")

# 역변환 확인
omega_check = -w_ncl * P_pa * GRAVITY / (RD * T)
print(f"\n역변환 확인: omega = -w * p * g / (Rd * T)")
print(f"  omega = {omega_check:.3f} Pa/s (원본: {omega:.3f} Pa/s)")

# 실제 변환된 데이터 확인
print(f"\n실제 load_cached_gfs_data에서 변환된 w:")
w_converted = -omega * (RD * T) / (P_pa * GRAVITY)
print(f"  w = {w_converted:.6f} m/s")

# 이 w로 10분 동안 이동하면?
dt = 600  # 10분
dz = w_converted * dt
print(f"\n10분 동안 이동:")
print(f"  dz = {dz:.1f} m")

# 1시간 동안 이동하면?
dt_hour = 3600
dz_hour = w_converted * dt_hour
print(f"\n1시간 동안 이동:")
print(f"  dz = {dz_hour:.1f} m")

print(f"\n하지만 HYSPLIT Web은 1시간에 약 -36m 하강했습니다.")
print(f"PyHYSPLIT은 1시간에 약 +582m 상승했습니다.")
print(f"\n문제: w 값이 너무 큽니다!")
print(f"  예상: ~-0.01 m/s")
print(f"  실제: {w_converted:.6f} m/s")
print(f"  비율: {abs(w_converted / -0.01):.1f}배")
