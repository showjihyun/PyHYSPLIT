import netCDF4
import numpy as np

ds = netCDF4.Dataset('tests/integration/gfs_cache/gfs_20260213_37.5_127.0_1h.nc')
w = np.array(ds.variables['w'][:])
lev = np.array(ds.variables['lev'][:])

print(f'W at 13:00 (t=7), 850hPa region:')
print(f'  Shape: {w.shape}')
print(f'  Levels: {lev}')
print(f'  Time index 7 (13:00): mean={w[7,:,:,:].mean():.3f}, std={w[7,:,:,:].std():.3f}')
print(f'\n  Sample values at 13:00, different levels:')
for i in range(min(10, w.shape[1])):
    print(f'    Level {i} ({lev[i]:.0f} hPa): {w[7,i,w.shape[2]//2,w.shape[3]//2]:.3f}')

# 850 hPa 근처 찾기
lev_850_idx = np.argmin(np.abs(lev - 850))
print(f'\n  Closest to 850 hPa: level {lev_850_idx} ({lev[lev_850_idx]:.0f} hPa)')
print(f'    W value: {w[7, lev_850_idx, w.shape[2]//2, w.shape[3]//2]:.3f}')

ds.close()
