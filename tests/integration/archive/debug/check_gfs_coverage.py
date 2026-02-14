"""Check GFS data coverage and compare with dynamic subgrid expansion needs."""

import xarray as xr
from pathlib import Path
import json

# Load existing GFS data
gfs_file = Path("tests/integration/gfs_cache/gfs_eastasia_24h_extended.nc")

print("="*60)
print("GFS Data Coverage Analysis")
print("="*60)

ds = xr.open_dataset(gfs_file, decode_times=False)

print(f"\nDataset dimensions: {list(ds.dims.keys())}")
print(f"Dataset coordinates: {list(ds.coords.keys())}")

# Find longitude and latitude coordinate names
lon_name = None
lat_name = None
for coord in ds.coords:
    if 'lon' in coord.lower():
        lon_name = coord
    if 'lat' in coord.lower():
        lat_name = coord

if not lon_name or not lat_name:
    print(f"\nAvailable coordinates: {list(ds.coords.keys())}")
    print(f"Available variables: {list(ds.data_vars.keys())}")
    ds.close()
    exit(1)

print(f"\nCurrent GFS Data Range:")
print(f"  Longitude ({lon_name}): {ds[lon_name].min().values:.1f} - {ds[lon_name].max().values:.1f}°E")
print(f"  Latitude ({lat_name}): {ds[lat_name].min().values:.1f} - {ds[lat_name].max().values:.1f}°N")
print(f"  Width: {ds[lon_name].max().values - ds[lon_name].min().values:.1f}°")

# Load dynamic subgrid test results
results_file = Path("tests/integration/dynamic_subgrid_results.json")
if results_file.exists():
    with open(results_file) as f:
        results = json.load(f)
    
    print(f"\nDynamic Subgrid Expansion Analysis:")
    print(f"{'Location':<15} {'Completion':<12} {'Expansions':<12} {'Status'}")
    print("-"*60)
    
    for r in results:
        status = "✅ OK" if r.get('completion_rate', 0) == 100 else "⚠️ Needs expansion"
        print(f"{r['name']:<15} {r.get('completion_rate', 0):>5.1f}% {r.get('expansion_count', 0):>6} {status:>20}")
    
    # Calculate required expansion
    print(f"\nExpansion Requirements:")
    print(f"  Current western boundary: {ds[lon_name].min().values:.1f}°E")
    print(f"  Dynamic subgrid detected expansions to: ~97.5°E")
    print(f"  Additional expansion needed: {ds[lon_name].min().values - 97.5:.1f}°")
    
    # Check if we need to download more data
    if ds[lon_name].min().values > 97.5:
        print(f"\n⚠️ WARNING: Current data range is insufficient!")
        print(f"  Recommendation: Expand western boundary to 95°E (safety margin)")
        print(f"  Required download: 95-{ds[lon_name].min().values:.0f}°E")
    else:
        print(f"\n✅ Current data range should be sufficient!")
        print(f"  All detected expansions are within current range")

else:
    print(f"\n⚠️ Dynamic subgrid results not found")
    print(f"  Run: python tests/integration/test_dynamic_subgrid.py")

ds.close()

print("="*60)
