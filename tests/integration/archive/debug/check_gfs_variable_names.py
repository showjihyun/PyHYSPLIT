"""GFS 변수명 확인"""
import netCDF4

ds = netCDF4.Dataset('tests/integration/gfs_cache/gfs_eastasia_24h_real.nc')

print("="*80)
print("  GFS NetCDF 변수 목록")
print("="*80)

print("\n모든 변수:")
for var_name in ds.variables.keys():
    var = ds.variables[var_name]
    print(f"  {var_name}: {var.dimensions}, shape={var.shape}")

print("\n'w' 변수 상세:")
w_var = ds.variables['w']
print(f"  Dimensions: {w_var.dimensions}")
print(f"  Shape: {w_var.shape}")
print(f"  Dtype: {w_var.dtype}")

print("\n'w' 변수 속성:")
for attr in w_var.ncattrs():
    print(f"  {attr}: {w_var.getncattr(attr)}")

# GRIB 변수명 확인
if 'GRIB_paramId' in w_var.ncattrs():
    print(f"\n  GRIB Parameter ID: {w_var.getncattr('GRIB_paramId')}")
if 'GRIB_shortName' in w_var.ncattrs():
    print(f"  GRIB Short Name: {w_var.getncattr('GRIB_shortName')}")
if 'GRIB_name' in w_var.ncattrs():
    print(f"  GRIB Name: {w_var.getncattr('GRIB_name')}")

print("\n분석:")
print("  - GFS 0.25도 모델은 sigma-pressure hybrid 좌표계 사용")
print("  - WWND는 수직 속도 (vertical velocity)")
print("  - 단위가 Pa/s라면 omega (압력 변화율)")
print("  - 단위가 m/s라면 w (기하학적 수직 속도)")

ds.close()
