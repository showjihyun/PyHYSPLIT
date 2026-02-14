"""GFS 데이터의 omega 단위 확인"""
import netCDF4
import numpy as np

ds = netCDF4.Dataset('tests/integration/gfs_cache/gfs_eastasia_24h_real.nc')

print("="*80)
print("  GFS 데이터 omega 변수 분석")
print("="*80)

print("\nw 변수 정보:")
print(ds.variables['w'])

print("\nw 변수 속성:")
for attr in ds.variables['w'].ncattrs():
    print(f"  {attr}: {ds.variables['w'].getncattr(attr)}")

print("\nw 데이터 통계:")
w_data = ds.variables['w'][:]
print(f"  Shape: {w_data.shape}")
print(f"  Min: {np.min(w_data):.6f}")
print(f"  Max: {np.max(w_data):.6f}")
print(f"  Mean: {np.mean(w_data):.6f}")
print(f"  Std: {np.std(w_data):.6f}")

print("\nt (온도) 변수 정보:")
print(ds.variables['t'])

print("\nt 변수 속성:")
for attr in ds.variables['t'].ncattrs():
    print(f"  {attr}: {ds.variables['t'].getncattr(attr)}")

print("\nlevel (압력) 변수:")
print(f"  Levels: {ds.variables['level'][:]}")

ds.close()

print("\n분석:")
print("  - omega가 Pa/s 단위라면 일반적으로 -1 ~ +1 범위")
print("  - omega가 hPa/s 단위라면 -0.01 ~ +0.01 범위")
print("  - w가 m/s 단위라면 -10 ~ +10 범위")
