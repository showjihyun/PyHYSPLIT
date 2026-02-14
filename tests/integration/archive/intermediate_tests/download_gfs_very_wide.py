"""Download very wide GFS data range (90-150°E) for dynamic subgrid validation.

This downloads a much wider longitude range to eliminate boundary errors
and validate that the dynamic subgrid correctly predicts the needed range.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import xarray as xr

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def download_gfs_very_wide():
    """Download GFS data with very wide longitude range (90-150°E)."""
    
    # Target date: 2024-01-15 00:00 UTC
    target_date = datetime(2024, 1, 15, 0, 0)
    
    # Very wide range: 90-150°E (60° width)
    # This should cover all expansion needs identified by dynamic subgrid
    lon_min, lon_max = 90, 150
    lat_min, lat_max = 20, 50
    
    # Pressure levels (hPa)
    pressure_levels = [200, 250, 300, 400, 500, 700, 850, 925, 1000]
    
    logger.info(f"Downloading GFS data for {target_date}")
    logger.info(f"Longitude range: {lon_min}-{lon_max}°E (60° width)")
    logger.info(f"Latitude range: {lat_min}-{lat_max}°N")
    logger.info(f"Pressure levels: {pressure_levels}")
    
    # Create cache directory
    cache_dir = Path("tests/integration/gfs_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = cache_dir / "gfs_eastasia_24h_very_wide.nc"
    
    if output_file.exists():
        logger.info(f"File already exists: {output_file}")
        logger.info("Delete it if you want to re-download")
        return output_file
    
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
        logger.info(f"Available variables: {list(ds.data_vars)}")
        
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
        logger.info("Downloading data... (this may take several minutes)")
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
        
        # Verify data
        logger.info("\nVerifying data...")
        ds_verify = xr.open_dataset(output_file)
        
        logger.info(f"Verification:")
        logger.info(f"  Longitude: {ds_verify.lon.min().values:.1f}-{ds_verify.lon.max().values:.1f}°E")
        logger.info(f"  Latitude: {ds_verify.lat.min().values:.1f}-{ds_verify.lat.max().values:.1f}°N")
        logger.info(f"  Time steps: {len(ds_verify.time)}")
        logger.info(f"  Pressure levels: {len(ds_verify.lev)}")
        logger.info(f"  Variables: {list(ds_verify.data_vars)}")
        
        ds_verify.close()
        
        return output_file
        
    except Exception as e:
        logger.error(f"Error downloading GFS data: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        
        # Try alternative approach: download in chunks
        logger.info("\nTrying alternative approach: downloading in chunks...")
        
        try:
            return download_in_chunks(
                target_date, lon_min, lon_max, lat_min, lat_max, 
                pressure_levels, output_file
            )
        except Exception as e2:
            logger.error(f"Alternative approach also failed: {e2}")
            raise


def download_in_chunks(target_date, lon_min, lon_max, lat_min, lat_max, 
                       pressure_levels, output_file):
    """Download GFS data in smaller chunks and combine."""
    
    logger.info("Downloading in 3 longitude chunks...")
    
    # Split into 3 chunks: 90-110, 110-130, 130-150
    lon_chunks = [(90, 110), (110, 130), (130, 150)]
    
    chunk_datasets = []
    
    for i, (lon_start, lon_end) in enumerate(lon_chunks, 1):
        logger.info(f"\nChunk {i}/3: {lon_start}-{lon_end}°E")
        
        date_str = target_date.strftime("%Y%m%d")
        hour_str = target_date.strftime("%H")
        base_url = f"https://nomads.ncep.noaa.gov/dods/gfs_0p25/gfs{date_str}/gfs_0p25_{hour_str}z"
        
        ds = xr.open_dataset(base_url)
        
        ds_chunk = ds.sel(
            lon=slice(lon_start, lon_end),
            lat=slice(lat_min, lat_max),
            lev=pressure_levels,
            time=slice(target_date, target_date + timedelta(hours=24))
        )
        
        variables = ['ugrdprs', 'vgrdprs', 'vvelprs', 'tmpprs', 'hgtprs']
        ds_chunk = ds_chunk[variables].load()
        
        chunk_datasets.append(ds_chunk)
        
        logger.info(f"  Downloaded chunk {i}: {len(ds_chunk.lon)} lon points")
    
    # Combine chunks
    logger.info("\nCombining chunks...")
    ds_combined = xr.concat(chunk_datasets, dim='lon')
    
    # Remove duplicate longitude points at boundaries
    _, unique_indices = np.unique(ds_combined.lon.values, return_index=True)
    ds_combined = ds_combined.isel(lon=sorted(unique_indices))
    
    logger.info(f"Combined dataset: {len(ds_combined.lon)} lon points")
    
    # Save
    logger.info(f"Saving to: {output_file}")
    ds_combined.to_netcdf(output_file)
    
    logger.info("✅ Download complete!")
    
    return output_file


if __name__ == "__main__":
    try:
        output_file = download_gfs_very_wide()
        
        print("\n" + "="*60)
        print("SUCCESS!")
        print("="*60)
        print(f"Downloaded GFS data: {output_file}")
        print(f"Range: 90-150°E, 20-50°N (60° × 30°)")
        print(f"This should eliminate all boundary errors!")
        print("\nNext step:")
        print("  python tests/integration/test_all_locations_very_wide.py")
        print("="*60)
        
    except Exception as e:
        print("\n" + "="*60)
        print("FAILED!")
        print("="*60)
        print(f"Error: {e}")
        print("\nPossible solutions:")
        print("1. Check internet connection")
        print("2. Verify NOAA server is accessible")
        print("3. Try again later (server may be busy)")
        print("="*60)
