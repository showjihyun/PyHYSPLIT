"""Omega 부호 테스트"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import netCDF4

# GFS 데이터 로드
ds = netCDF4.Dataset('tests/integration/gfs_cache/gfs_eastasia_24h_real.nc')

omega_data = np.array(ds.variables['w'][:])
lat_grid = np.array(ds.variables['latitude'][:])
lon_grid = np.array(ds.variables['longitude'][:])
lev_grid = np.array(ds.variables['level'][:])

ds.close()

print("="*80)
print("  Omega 부호 규칙 분석")
print("="*80)

# 서울 근처 (37.5N, 127E, 850 hPa)
lat_idx = np.argmin(np.abs(lat_grid - 37.5))
lon_idx = np.argmin(np.abs(lon_grid - 127.0))
lev_idx = np.argmin(np.abs(lev_grid - 850.0))

omega_val = omega_data[0, lev_idx, lat_idx, lon_idx]

print(f"\n서울 근처 (t=0, 850 hPa):")
print(f"  Omega: {omega_val:.6f} Pa/s")
print(f"  Omega / 100: {omega_val/100:.6f} hPa/s")

print(f"\nHYSPLIT 부호 규칙:")
print(f"  압력 좌표계에서:")
print(f"    - Omega > 0: 하강 (압력 증가, dP/dt > 0)")
print(f"    - Omega < 0: 상승 (압력 감소, dP/dt < 0)")
print(f"  ")
print(f"  Backward trajectory에서:")
print(f"    - dt < 0 (음수)")
print(f"    - dP = omega * dt")
print(f"    - Omega > 0, dt < 0 → dP < 0 (압력 감소)")
print(f"    - Omega < 0, dt < 0 → dP > 0 (압력 증가)")

print(f"\n현재 서울 케이스:")
print(f"  Omega = {omega_val:.6f} Pa/s (양수 = 하강)")
print(f"  dt = -3600 s (backward)")
print(f"  dP = {omega_val/100:.6f} * (-3600) = {omega_val/100 * -3600:.1f} hPa")
print(f"  ")
print(f"  시작: 850 hPa")
print(f"  1시간 후: 850 + {omega_val/100 * -3600:.1f} = {850 + omega_val/100 * -3600:.1f} hPa")

print(f"\nHYSPLIT Web 결과:")
print(f"  시작: 850 hPa")
print(f"  1시간 후: 874.3 hPa (압력 증가 = 하강)")
print(f"  dP = +24.3 hPa")

print(f"\n차이 분석:")
py_dp = omega_val/100 * -3600
hy_dp = 874.3 - 850.0
print(f"  PyHYSPLIT dP: {py_dp:.1f} hPa")
print(f"  HYSPLIT Web dP: {hy_dp:.1f} hPa")
print(f"  차이: {abs(py_dp - hy_dp):.1f} hPa")

print(f"\n가능한 원인:")
print(f"  1. Omega 값이 너무 작음 (0.000065 hPa/s)")
print(f"  2. HYSPLIT이 다른 수직 속도 사용 (Mode 8 damping?)")
print(f"  3. 시간 평균 효과 (여러 작은 스텝)")
print(f"  4. 온도 기반 변환 필요?")
