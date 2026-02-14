"""Inspect GFS data to check wind values."""

import sys
import netCDF4
import numpy as np

sys.path.insert(0, '/workspaces/pyhysplit')

from pyhysplit.met_reader import NetCDFReader

def main():
    """Inspect GFS data."""
    
    gfs_file = "tests/integration/gfs_cache/gfs_20260213_37.5_127.0_1h.nc"
    
    print(f"\n=== Inspecting {gfs_file} ===\n")
    
    # Read with netCDF4
    ds = netCDF4.Dataset(gfs_file)
    
    print("Variables:")
    for var in ds.variables:
        print(f"  {var}: {ds.variables[var].shape}")
    
    print("\nDimensions:")
    for dim in ds.dimensions:
        print(f"  {dim}: {len(ds.dimensions[dim])}")
    
    # Check data values
    u_data = np.array(ds.variables["u"][:])
    v_data = np.array(ds.variables["v"][:])
    w_data = np.array(ds.variables["w"][:])
    
    print(f"\nU wind:")
    print(f"  Shape: {u_data.shape}")
    print(f"  Range: {u_data.min():.3f} to {u_data.max():.3f}")
    print(f"  Mean: {u_data.mean():.3f}")
    print(f"  Std: {u_data.std():.3f}")
    
    print(f"\nV wind:")
    print(f"  Shape: {v_data.shape}")
    print(f"  Range: {v_data.min():.3f} to {v_data.max():.3f}")
    print(f"  Mean: {v_data.mean():.3f}")
    print(f"  Std: {v_data.std():.3f}")
    
    print(f"\nW wind:")
    print(f"  Shape: {w_data.shape}")
    print(f"  Range: {w_data.min():.6f} to {w_data.max():.6f}")
    print(f"  Mean: {w_data.mean():.6f}")
    print(f"  Std: {w_data.std():.6f}")
    
    # Check at specific location (37.5, 127.0, 850 hPa, t=46800)
    lat_grid = np.array(ds.variables["lat"][:])
    lon_grid = np.array(ds.variables["lon"][:])
    lev_grid = np.array(ds.variables["lev"][:])
    t_grid = np.array(ds.variables["time"][:])
    
    print(f"\nCoordinates:")
    print(f"  Lat: {lat_grid}")
    print(f"  Lon: {lon_grid}")
    print(f"  Lev: {lev_grid}")
    print(f"  Time: {t_grid}")
    
    # Find nearest indices
    lat_idx = np.argmin(np.abs(lat_grid - 37.5))
    lon_idx = np.argmin(np.abs(lon_grid - 127.0))
    lev_idx = np.argmin(np.abs(lev_grid - 850.0))
    t_idx = np.argmin(np.abs(t_grid - 46800.0))
    
    print(f"\nNearest indices for (37.5°N, 127.0°E, 850 hPa, t=46800s):")
    print(f"  lat_idx={lat_idx} (lat={lat_grid[lat_idx]})")
    print(f"  lon_idx={lon_idx} (lon={lon_grid[lon_idx]})")
    print(f"  lev_idx={lev_idx} (lev={lev_grid[lev_idx]})")
    print(f"  t_idx={t_idx} (t={t_grid[t_idx]})")
    
    u_val = u_data[t_idx, lev_idx, lat_idx, lon_idx]
    v_val = v_data[t_idx, lev_idx, lat_idx, lon_idx]
    w_val = w_data[t_idx, lev_idx, lat_idx, lon_idx]
    
    print(f"\nWind at this location:")
    print(f"  U = {u_val:.3f} m/s")
    print(f"  V = {v_val:.3f} m/s")
    print(f"  W = {w_val:.6f} m/s")
    
    ds.close()
    
    # Now read with NetCDFReader
    print(f"\n=== Reading with NetCDFReader ===\n")
    reader = NetCDFReader()
    met = reader.read(gfs_file)
    
    print(f"MetData:")
    print(f"  u shape: {met.u.shape}")
    print(f"  v shape: {met.v.shape}")
    print(f"  w shape: {met.w.shape}")
    print(f"  lat_grid: {met.lat_grid}")
    print(f"  lon_grid: {met.lon_grid}")
    print(f"  z_grid: {met.z_grid}")
    print(f"  t_grid: {met.t_grid}")
    print(f"  z_type: {met.z_type}")
    
    # Check same location
    lat_idx = np.argmin(np.abs(met.lat_grid - 37.5))
    lon_idx = np.argmin(np.abs(met.lon_grid - 127.0))
    lev_idx = np.argmin(np.abs(met.z_grid - 850.0))
    t_idx = np.argmin(np.abs(met.t_grid - 46800.0))
    
    u_val = met.u[t_idx, lev_idx, lat_idx, lon_idx]
    v_val = met.v[t_idx, lev_idx, lat_idx, lon_idx]
    w_val = met.w[t_idx, lev_idx, lat_idx, lon_idx]
    
    print(f"\nWind at (37.5°N, 127.0°E, 850 hPa, t=46800s):")
    print(f"  U = {u_val:.3f} m/s")
    print(f"  V = {v_val:.3f} m/s")
    print(f"  W = {w_val:.6f} m/s")

if __name__ == "__main__":
    main()
