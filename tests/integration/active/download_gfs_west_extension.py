"""Download western extension of GFS data (95-105°E) to complete coverage.

This downloads the missing western portion to extend coverage from 105°E to 95°E,
which should eliminate all boundary errors detected by dynamic subgrid analysis.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import xarray as xr

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def download_latest_gfs_west():
    """Download latest GFS data for western extension (95-105°E)."""
    
    # Use recent date (within last 10 days)
    # GFS data is typically available for the last 10 days
    target_date = datetime.utcnow() - timedelta(days=2)
    target_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Western extension: 95-105°E
    lon_min, lon_max = 95, 105
    lat_min, lat_max = 20, 50
    
    # Pressure levels (hPa)
    pressure_levels = [200, 250, 300, 400, 500, 700, 850, 925, 1000]
    
    logger.info(f"Downloading GFS data for {target_date}")
    logger.info(f"Longitude range: {lon_min}-{lon_max}°E (western extension)")
    logger.info(f"Latitude range: {lat_min}-{lat_max}°N")
    logger.info(f"Pressure levels: {pressure_levels}")
    
    # Create cache directory
    cache_dir = Path("tests/integration/gfs_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = cache_dir / "gfs_west_extension_24h.nc"
    
    if output_file.exists():
        logger.info(f"File already exists: {output_file}")
        response = input("Delete and re-download? (y/n): ")
        if response.lower() != 'y':
            return output_file
        output_file.unlink()
    
    try:
        # Build GFS URL for 0.25° resolution
        date_str = target_date.strftime("%Y%m%d")
        hour_str = target_date.strftime("%H")
        
        # GFS 0.25° data URL
        base_url = f"https://nomads.ncep.noaa.gov/dods/gfs_0p25/gfs{date_str}/gfs_0p25_{hour_str}z"
        
        logger.info(f"Connecting to: {base_url}")
        
        # Open dataset
        ds = xr.open_dataset(base_url)
        
        logger.info("Dataset opened successfully")
        
        # Select region and levels
        ds_subset = ds.sel(
            lon=slice(lon_min, lon_max),
            lat=slice(lat_min, lat_max),
            lev=pressure_levels,
            time=slice(target_date, target_date + timedelta(hours=24))
        )
        
        logger.info(f"Selected subset:")
        logger.info(f"  Time: {len(ds_subset.time)} steps")
        logger.info(f"  Lon: {len(ds_subset.lon)} points ({ds_subset.lon.min().values:.1f}-{ds_subset.lon.max().values:.1f}°E)")
        logger.info(f"  Lat: {len(ds_subset.lat)} points ({ds_subset.lat.min().values:.1f}-{ds_subset.lat.max().values:.1f}°N)")
        logger.info(f"  Lev: {len(ds_subset.lev)} levels")
        
        # Select required variables
        variables = ['ugrdprs', 'vgrdprs', 'vvelprs', 'tmpprs', 'hgtprs']
        
        logger.info(f"Downloading variables: {variables}")
        
        ds_download = ds_subset[variables]
        
        # Load data (this triggers the download)
        logger.info("Downloading data... (this may take a few minutes)")
        ds_download = ds_download.load()
        
        # Calculate data size
        total_size = sum(
            ds_download[var].nbytes 
            for var in ds_download.data_vars
        ) / (1024 * 1024)  # Convert to MB
        
        logger.info(f"Downloaded {total_size:.1f} MB")
        
        # Save to NetCDF
        logger.info(f"Saving to: {output_file}")
        ds_download.to_netcdf(output_file)
        
        logger.info("✅ Download complete!")
        logger.info(f"File size: {output_file.stat().st_size / (1024*1024):.1f} MB")
        
        return output_file
        
    except Exception as e:
        logger.error(f"Error downloading GFS data: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        
        # Try previous day
        logger.info("\nTrying previous day...")
        target_date = target_date - timedelta(days=1)
        date_str = target_date.strftime("%Y%m%d")
        hour_str = target_date.strftime("%H")
        base_url = f"https://nomads.ncep.noaa.gov/dods/gfs_0p25/gfs{date_str}/gfs_0p25_{hour_str}z"
        
        try:
            logger.info(f"Connecting to: {base_url}")
            ds = xr.open_dataset(base_url)
            
            ds_subset = ds.sel(
                lon=slice(lon_min, lon_max),
                lat=slice(lat_min, lat_max),
                lev=pressure_levels,
                time=slice(target_date, target_date + timedelta(hours=24))
            )
            
            ds_download = ds_subset[variables].load()
            ds_download.to_netcdf(output_file)
            
            logger.info("✅ Download complete (previous day)!")
            return output_file
            
        except Exception as e2:
            logger.error(f"Previous day also failed: {e2}")
            raise


if __name__ == "__main__":
    try:
        output_file = download_latest_gfs_west()
        
        print("\n" + "="*60)
        print("SUCCESS!")
        print("="*60)
        print(f"Downloaded western extension: {output_file}")
        print(f"Range: 95-105°E, 20-50°N")
        print("\nNext step: Merge with existing data")
        print("  python tests/integration/merge_gfs_data.py")
        print("="*60)
        
    except Exception as e:
        print("\n" + "="*60)
        print("FAILED!")
        print("="*60)
        print(f"Error: {e}")
        print("\nNote: GFS data older than 10 days is not available")
        print("Alternative: Use existing extended data (105-150°E)")
        print("  and accept partial completion for high-latitude locations")
        print("="*60)
