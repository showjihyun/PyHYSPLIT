"""Test all vertical motion modes"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import netCDF4
from datetime import datetime
from pyhysplit.models import StartLocation, SimulationConfig, MetData
from pyhysplit.engine import TrajectoryEngine
from math import radians, sin, cos, sqrt, atan2

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1_rad, lat2_rad = radians(lat1), radians(lat2)
    dlon = radians(lon2 - lon1)
    dlat = lat2_rad - lat1_rad
    a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

# Load GFS data
ds = netCDF4.Dataset('tests/integration/gfs_cache/gfs_eastasia_24h_real.nc')
u_data = np.array(ds.variables['u'][:])
v_data = np.array(ds.variables['v'][:])
omega_data = np.array(ds.variables['w'][:])
t_data = np.array(ds.variables['t'][:])
lat_grid = np.array(ds.variables['latitude'][:])
lon_grid = np.array(ds.variables['longitude'][:])
lev_grid = np.array(ds.variables['level'][:])
time_grid = np.array(ds.variables['time'][:])
ds.close()

# Sort time grid
if time_grid[0] > time_grid[-1]:
    time_indices = np.argsort(time_grid)
    time_grid = time_grid[time_indices]
    u_data = u_data[time_indices]
    v_data = v_data[time_indices]
    omega_data = omega_data[time_indices]
    t_data = t_data[time_indices]

# Convert omega to hPa/s
w_data = omega_data / 100.0

met_data = MetData(
    u=u_data, v=v_data, w=w_data, t_field=t_data,
    lat_grid=lat_grid, lon_grid=lon_grid,
    z_grid=lev_grid, t_grid=time_grid,
    z_type="pressure", source="GFS_NC"
)

# Test location
lat, lon, pressure = 37.5, 127.0, 850.0

# HYSPLIT Web reference
hysplit_final = {'lat': 36.491, 'lon': 125.300, 'pressure': 931.9}

print("="*70)
print("Vertical Motion Mode Comparison")
print("="*70)
print(f"Start: {lat}N, {lon}E, {pressure} hPa")
print(f"HYSPLIT Web 8h: {hysplit_final['lat']}N, {hysplit_final['lon']}E, {hysplit_final['pressure']} hPa")
print("="*70)

modes = [0, 1, 3, 7, 8]
results = []

for mode in modes:
    start_loc = StartLocation(lat=lat, lon=lon, height=pressure, height_type="pressure")
    
    config = SimulationConfig(
        start_time=datetime(2026, 2, 14, 0, 0),
        num_start_locations=1,
        start_locations=[start_loc],
        total_run_hours=-8,
        vertical_motion=mode,
        model_top=10000.0,
        met_files=[],
        turbulence_on=False,
        dt_max=15.0,
        tratio=0.75
    )
    
    engine = TrajectoryEngine(config, met_data)
    trajectory = engine.run(output_interval_s=3600.0)[0]
    
    if len(trajectory) >= 9:
        final = trajectory[8]
        h_error = haversine(final[2], final[1], hysplit_final['lat'], hysplit_final['lon'])
        p_error = abs(final[3] - hysplit_final['pressure'])
        
        results.append({
            'mode': mode,
            'lat': final[2],
            'lon': final[1],
            'pressure': final[3],
            'h_error': h_error,
            'p_error': p_error
        })

print(f"\n{'Mode':>6} {'Lat':>8} {'Lon':>9} {'Pressure':>10} {'H_Err(km)':>12} {'P_Err(hPa)':>12}")
print("-"*70)
for r in results:
    print(f"{r['mode']:>6} {r['lat']:>8.3f} {r['lon']:>9.3f} {r['pressure']:>10.1f} {r['h_error']:>12.2f} {r['p_error']:>12.1f}")

best = min(results, key=lambda x: x['p_error'])
print(f"\nBest pressure accuracy: Mode {best['mode']} with {best['p_error']:.1f} hPa error")
