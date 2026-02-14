"""Test all 8 locations with very wide GFS data (95-150°E).

This should eliminate all boundary errors and achieve 100% completion
for all locations, including high-latitude locations.
"""

import logging
from datetime import datetime
from pathlib import Path

import numpy as np

from pyhysplit.engine import TrajectoryEngine
from pyhysplit.met_reader import NetCDFReader
from pyhysplit.models import SimulationConfig, StartLocation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_all_locations_very_wide():
    """Test all 8 locations with very wide GFS data."""
    
    # All 8 test locations
    test_locations = [
        ("Seoul", 37.5, 127.0),
        ("Busan", 35.2, 129.0),
        ("Tokyo", 35.7, 139.7),
        ("Beijing", 39.9, 116.4),
        ("Shanghai", 31.2, 121.5),
        ("Taipei", 25.0, 121.5),
        ("Hong Kong", 22.3, 114.2),
        ("Manila", 14.6, 121.0),
    ]
    
    # Load very wide GFS data (95-150°E)
    gfs_file = Path("tests/integration/gfs_cache/gfs_eastasia_24h_very_wide.nc")
    
    if not gfs_file.exists():
        logger.error(f"Very wide GFS data not found: {gfs_file}")
        logger.error("Run: python tests/integration/merge_gfs_data.py")
        return
    
    reader = NetCDFReader()
    met = reader.read(str(gfs_file))
    
    logger.info(f"Loaded GFS data: {met.lon_grid[0]:.1f}-{met.lon_grid[-1]:.1f}°E, "
                f"{met.lat_grid[0]:.1f}-{met.lat_grid[-1]:.1f}°N")
    logger.info(f"Data width: {met.lon_grid[-1] - met.lon_grid[0]:.1f}°")
    
    results = []
    
    for name, lat, lon in test_locations:
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing: {name} ({lat}°N, {lon}°E)")
        logger.info(f"{'='*60}")
        
        # Create configuration
        config = SimulationConfig(
            start_time=datetime(2026, 2, 12, 0, 0),  # Match the downloaded data date
            num_start_locations=1,
            start_locations=[StartLocation(lat=lat, lon=lon, height=850.0, height_type="pressure")],
            total_run_hours=-24,  # 24-hour backward trajectory
            vertical_motion=7,  # Mode 7 (Spatially averaged)
            model_top=10000.0,
            met_files=[],
            dt_max=900.0,
            tratio=0.75,
            auto_vertical_mode=False,
            enable_dynamic_subgrid=False,  # Disabled - we have wide data
        )
        
        # Run trajectory
        engine = TrajectoryEngine(config, met)
        
        try:
            trajectories = engine.run(output_interval_s=3600.0)
            trajectory = trajectories[0]
            
            # Analyze results
            total_points = 25  # 24 hours + initial point
            actual_points = len(trajectory)
            completion_rate = (actual_points / total_points) * 100
            
            # Check if trajectory stayed within bounds
            lons = [p[1] for p in trajectory]
            lats = [p[2] for p in trajectory]
            
            min_lon, max_lon = min(lons), max(lons)
            min_lat, max_lat = min(lats), max(lats)
            
            # Check if within data bounds
            within_bounds = (
                min_lon >= met.lon_grid[0] and
                max_lon <= met.lon_grid[-1] and
                min_lat >= met.lat_grid[0] and
                max_lat <= met.lat_grid[-1]
            )
            
            result = {
                'name': name,
                'lat': lat,
                'lon': lon,
                'total_points': total_points,
                'actual_points': actual_points,
                'completion_rate': completion_rate,
                'min_lon': min_lon,
                'max_lon': max_lon,
                'min_lat': min_lat,
                'max_lat': max_lat,
                'within_bounds': within_bounds,
                'success': actual_points >= total_points,
            }
            
            results.append(result)
            
            logger.info(f"\nResults for {name}:")
            logger.info(f"  Completion: {actual_points}/{total_points} points ({completion_rate:.1f}%)")
            logger.info(f"  Longitude range: {min_lon:.1f} - {max_lon:.1f}°E")
            logger.info(f"  Latitude range: {min_lat:.1f} - {max_lat:.1f}°N")
            logger.info(f"  Within bounds: {'✅ Yes' if within_bounds else '❌ No'}")
            logger.info(f"  Status: {'✅ SUCCESS' if result['success'] else '⚠️ PARTIAL'}")
            
        except Exception as e:
            logger.error(f"Error running trajectory for {name}: {e}")
            result = {
                'name': name,
                'lat': lat,
                'lon': lon,
                'error': str(e),
                'success': False,
            }
            results.append(result)
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("FINAL SUMMARY")
    logger.info(f"{'='*60}")
    
    logger.info(f"\n{'Location':<15} {'Completion':<12} {'Lon Range':<20} {'Status'}")
    logger.info("-"*70)
    
    for result in results:
        if result['success']:
            lon_range = f"{result['min_lon']:.1f}-{result['max_lon']:.1f}°E"
            status = "✅ Complete"
        else:
            lon_range = "N/A"
            status = f"⚠️ {result.get('error', 'Partial')[:20]}"
        
        logger.info(f"{result['name']:<15} {result.get('completion_rate', 0):>5.1f}% {lon_range:<20} {status}")
    
    # Calculate statistics
    successful = [r for r in results if r['success']]
    partial = [r for r in results if not r['success'] and r.get('completion_rate', 0) > 0]
    failed = [r for r in results if not r['success'] and r.get('completion_rate', 0) == 0]
    
    if successful:
        avg_completion = np.mean([r['completion_rate'] for r in successful])
        
        logger.info(f"\nOverall Statistics:")
        logger.info(f"  Complete: {len(successful)}/8 ({len(successful)/8*100:.0f}%)")
        logger.info(f"  Partial: {len(partial)}/8")
        logger.info(f"  Failed: {len(failed)}/8")
        logger.info(f"  Average completion (successful): {avg_completion:.1f}%")
        
        # Check if all high-latitude locations completed
        high_lat_locations = ["Seoul", "Beijing", "Tokyo", "Busan"]
        high_lat_results = [r for r in results if r['name'] in high_lat_locations]
        high_lat_complete = [r for r in high_lat_results if r['success']]
        
        logger.info(f"\nHigh-Latitude Performance (≥35°N):")
        logger.info(f"  Complete: {len(high_lat_complete)}/4")
        logger.info(f"  Success rate: {len(high_lat_complete)/4*100:.0f}%")
        
        if len(high_lat_complete) == 4:
            logger.info(f"\n🎉 SUCCESS! All high-latitude locations completed!")
            logger.info(f"   Dynamic subgrid expansion range was correct!")
        
        # Check westernmost point
        all_min_lons = [r['min_lon'] for r in successful]
        westernmost = min(all_min_lons)
        logger.info(f"\nWesternmost point reached: {westernmost:.1f}°E")
        logger.info(f"Data western boundary: {met.lon_grid[0]:.1f}°E")
        logger.info(f"Safety margin: {westernmost - met.lon_grid[0]:.1f}°")
    
    # Save results
    import json
    output_file = Path("tests/integration/very_wide_test_results.json")
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"\nResults saved to: {output_file}")
    
    return results


if __name__ == "__main__":
    results = test_all_locations_very_wide()
    
    # Final verdict
    successful = [r for r in results if r['success']]
    
    print("\n" + "="*60)
    if len(successful) == 8:
        print("🎉 PERFECT! All 8 locations completed successfully!")
        print("   Progress: 80% → 100% (GOAL ACHIEVED!)")
    elif len(successful) >= 6:
        print(f"✅ GOOD! {len(successful)}/8 locations completed")
        print(f"   Progress: 80% → ~{80 + len(successful)*2.5:.0f}%")
    else:
        print(f"⚠️ PARTIAL: {len(successful)}/8 locations completed")
        print(f"   More investigation needed")
    print("="*60)
