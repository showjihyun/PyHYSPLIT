"""Omega 부호 확인"""
import netCDF4
import numpy as np

ds = netCDF4.Dataset('tests/integration/gfs_cache/gfs_eastasia_24h_real.nc')

omega = np.array(ds.variables['w'][:])
levels = np.array(ds.variables['level'][:])

print("="*80)
print("  Omega 부호 분석")
print("="*80)

# 서울 근처 샘플
lat_idx = 60  # ~37.5N
lon_idx = 80  # ~127E
time_idx = 0

print("\n서울 근처 수직 프로파일 (t=0):")
print(f"{'Level (hPa)':>12} {'Omega (Pa/s)':>15} {'해석':>20}")
print("-" * 50)

for lev_idx in range(len(levels)):
    omega_val = omega[time_idx, lev_idx, lat_idx, lon_idx]
    level = levels[lev_idx]
    
    if omega_val > 0:
        interpretation = "하강 (압력 증가)"
    elif omega_val < 0:
        interpretation = "상승 (압력 감소)"
    else:
        interpretation = "정체"
    
    print(f"{level:>12.0f} {omega_val:>15.6f} {interpretation:>20}")

print("\n전체 통계:")
print(f"  Positive omega (하강): {np.sum(omega > 0)} 포인트")
print(f"  Negative omega (상승): {np.sum(omega < 0)} 포인트")
print(f"  Zero omega: {np.sum(omega == 0)} 포인트")

print("\nHYSPLIT 부호 규칙:")
print("  - Omega > 0: 하강 (압력 증가, 고도 감소)")
print("  - Omega < 0: 상승 (압력 감소, 고도 증가)")
print("  - 압력 좌표계에서 dz/dt = -omega * (R*T)/(g*P)")
print("  - 즉, omega를 그대로 사용하면 압력 변화율")

ds.close()
