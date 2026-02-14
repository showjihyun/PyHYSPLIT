"""GFS 좌표계 확인"""
import netCDF4

ds = netCDF4.Dataset('tests/integration/gfs_cache/gfs_eastasia_24h_real.nc')

print("="*80)
print("  GFS 데이터 좌표계 분석")
print("="*80)

print("\n변수 목록:")
for var_name in ds.variables.keys():
    var = ds.variables[var_name]
    print(f"  {var_name}: {var.dimensions}, shape={var.shape}")

print("\nlevel 변수 상세:")
lev = ds.variables['level']
print(f"  Values: {lev[:]}")
print(f"  Units: {lev.units if hasattr(lev, 'units') else 'N/A'}")

print("\n전역 속성:")
for attr in ds.ncattrs():
    print(f"  {attr}: {ds.getncattr(attr)}")

print("\n분석:")
print("  - level 단위가 hPa/mb이면: 순수 압력 좌표계")
print("  - hybrid coefficient (A, B)가 있으면: sigma-pressure hybrid")
print("  - level 값이 0-1 범위면: sigma 좌표계")

ds.close()
