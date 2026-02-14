import netCDF4
import numpy as np

ds = netCDF4.Dataset('tests/integration/gfs_cache/gfs_20260213_37.5_127.0.nc')
print(f'lat range: {np.array(ds.variables["lat"][[0,-1]])}')
print(f'lon range: {np.array(ds.variables["lon"][[0,-1]])}')
print(f'lev range: {np.array(ds.variables["lev"][[0,-1]])}')
print(f'time range: {np.array(ds.variables["time"][[0,-1]])}')
print(f'u shape: {ds.variables["u"].shape}')
print(f'v shape: {ds.variables["v"].shape}')
print(f'w shape: {ds.variables["w"].shape}')
print(f't shape: {ds.variables["t"].shape}')
ds.close()
