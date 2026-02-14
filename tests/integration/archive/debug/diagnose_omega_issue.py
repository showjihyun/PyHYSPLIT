"""Omega 변환 문제 진단"""
import netCDF4
import numpy as np
from pyhysplit.met_reader import convert_omega_to_w

# GFS 데이터 로드
ds = netCDF4.Dataset('tests/integration/gfs_cache/gfs_eastasia_24h_real.nc')

omega = np.array(ds.variables['w'][:])
t = np.array(ds.variables['t'][:])
levels = np.array(ds.variables['level'][:])

print("="*80)
print("  Omega 변환 진단")
print("="*80)

# 샘플 포인트 선택 (서울 근처, 850 hPa, 첫 시간)
lat_idx = 60  # ~37.5N
lon_idx = 80  # ~127E
lev_idx = 13  # 850 hPa
time_idx = 0

omega_sample = omega[time_idx, lev_idx, lat_idx, lon_idx]
t_sample = t[time_idx, lev_idx, lat_idx, lon_idx]
p_sample = levels[lev_idx] * 100.0  # hPa → Pa

print(f"\n샘플 포인트 (서울 근처, 850 hPa, t=0):")
print(f"  Omega: {omega_sample:.6f} Pa/s")
print(f"  Temperature: {t_sample:.2f} K")
print(f"  Pressure: {p_sample:.0f} Pa ({levels[lev_idx]:.0f} hPa)")

# 변환 공식 적용
Rd = 287.05  # J/(kg·K)
g = 9.80665  # m/s²

w_converted = convert_omega_to_w(
    np.array([omega_sample]),
    np.array([t_sample]),
    np.array([p_sample])
)[0]

print(f"\n변환 결과:")
print(f"  W (converted): {w_converted:.6f} m/s")

# 수동 계산으로 검증
w_manual = -omega_sample * Rd * t_sample / (g * p_sample)
print(f"  W (manual): {w_manual:.6f} m/s")

# 전체 데이터 통계
print(f"\n전체 omega 통계:")
print(f"  Min: {np.min(omega):.6f} Pa/s")
print(f"  Max: {np.max(omega):.6f} Pa/s")
print(f"  Mean: {np.mean(omega):.6f} Pa/s")
print(f"  Std: {np.std(omega):.6f} Pa/s")

# 변환 후 w 통계
nt, nz, ny, nx = omega.shape
P_4d = levels[np.newaxis, :, np.newaxis, np.newaxis] * 100.0
P_4d = np.broadcast_to(P_4d, omega.shape)

w_all = convert_omega_to_w(omega, t, P_4d)

print(f"\n변환 후 w 통계:")
print(f"  Min: {np.min(w_all):.6f} m/s")
print(f"  Max: {np.max(w_all):.6f} m/s")
print(f"  Mean: {np.mean(w_all):.6f} m/s")
print(f"  Std: {np.std(w_all):.6f} m/s")

print("\n분석:")
print("  - 일반적인 대기 omega: -1 ~ +1 Pa/s")
print("  - 일반적인 대기 w: -1 ~ +1 m/s")
print("  - 현재 GFS omega: -15 ~ +9 Pa/s (비정상적으로 큼)")
print("  - 변환 후 w 범위 확인 필요")

# HYSPLIT이 기대하는 값 범위
print("\nHYSPLIT 기대값:")
print("  - Vertical velocity (w): 일반적으로 -10 ~ +10 m/s")
print("  - 850 hPa에서 전형적인 w: -0.5 ~ +0.5 m/s")

ds.close()
