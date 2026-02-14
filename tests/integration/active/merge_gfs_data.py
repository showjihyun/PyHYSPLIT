"""Merge western extension with existing GFS data to create complete coverage.

Merges:
- Western extension: 95-105°E (new)
- Existing data: 105-150°E (old)
Result: 95-150°E (complete)
"""

import logging
from pathlib import Path

import numpy as np
import xarray as xr

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def merge_gfs_data():
    """Merge western extension with existing GFS data."""
    
    cache_dir = Path("tests/integration/gfs_cache")
    
    # Input files
    west_file = cache_dir / "gfs_west_extension_24h.nc"
    east_file = cache_dir / "gfs_eastasia_24h_extended.nc"
    
    # Output file
    output_file = cache_dir / "gfs_eastasia_24h_very_wide.nc"
    
    if not west_file.exists():
        logger.error(f"Western extension file not found: {west_file}")
        logger.error("Run: python tests/integration/download_gfs_west_extension.py")
        return None
    
    if not east_file.exists():
        logger.error(f"Eastern data file not found: {east_file}")
        return None
    
    if output_file.exists():
        logger.info(f"Merged file already exists: {output_file}")
        response = input("Delete and re-merge? (y/n): ")
        if response.lower() != 'y':
            return output_file
        output_file.unlink()
    
    logger.info("Loading datasets...")
    
    # Load datasets (both with decode_times=False for consistency)
    ds_west = xr.open_dataset(west_file, decode_times=False)
    ds_east = xr.open_dataset(east_file, decode_times=False)
    
    logger.info(f"Western data: {ds_west.lon.min().values:.1f}-{ds_west.lon.max().values:.1f}°E")
    logger.info(f"Eastern data: {ds_east.longitude.min().values:.1f}-{ds_east.longitude.max().values:.1f}°E")
    
    # Rename coordinates in eastern dataset to match western dataset
    logger.info("Standardizing coordinate names...")
    ds_east = ds_east.rename({
        'longitude': 'lon',
        'latitude': 'lat',
        'level': 'lev'
    })
    
    # Rename variables to match
    var_mapping = {
        'u': 'ugrdprs',
        'v': 'vgrdprs',
        'w': 'vvelprs',
        't': 'tmpprs',
        'hgt': 'hgtprs'
    }
    
    for old_name, new_name in var_mapping.items():
        if old_name in ds_east.data_vars:
            ds_east = ds_east.rename({old_name: new_name})
    
    logger.info("Merging datasets...")
    
    # Concatenate along longitude dimension
    ds_merged = xr.concat([ds_west, ds_east], dim='lon')
    
    # Remove duplicate longitude points at the boundary (105°E)
    _, unique_indices = np.unique(ds_merged.lon.values, return_index=True)
    ds_merged = ds_merged.isel(lon=sorted(unique_indices))
    
    logger.info(f"Merged dataset:")
    logger.info(f"  Longitude: {ds_merged.lon.min().values:.1f}-{ds_merged.lon.max().values:.1f}°E")
    logger.info(f"  Latitude: {ds_merged.lat.min().values:.1f}-{ds_merged.lat.max().values:.1f}°N")
    logger.info(f"  Width: {ds_merged.lon.max().values - ds_merged.lon.min().values:.1f}°")
    logger.info(f"  Longitude points: {len(ds_merged.lon)}")
    logger.info(f"  Time steps: {len(ds_merged.time)}")
    logger.info(f"  Pressure levels: {len(ds_merged.lev)}")
    
    # Save merged dataset
    logger.info(f"Saving to: {output_file}")
    ds_merged.to_netcdf(output_file)
    
    file_size = output_file.stat().st_size / (1024 * 1024)
    logger.info(f"✅ Merge complete! File size: {file_size:.1f} MB")
    
    # Close datasets
    ds_west.close()
    ds_east.close()
    ds_merged.close()
    
    return output_file


if __name__ == "__main__":
    try:
        output_file = merge_gfs_data()
        
        if output_file:
            print("\n" + "="*60)
            print("SUCCESS!")
            print("="*60)
            print(f"Merged GFS data: {output_file}")
            print(f"Coverage: 95-150°E, 20-50°N (55° × 30°)")
            print("\nThis should eliminate ALL boundary errors!")
            print("\nNext step: Test with all locations")
            print("  python tests/integration/test_all_locations_very_wide.py")
            print("="*60)
        
    except Exception as e:
        print("\n" + "="*60)
        print("FAILED!")
        print("="*60)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print("="*60)
