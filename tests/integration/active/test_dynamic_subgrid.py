"""Test dynamic subgrid expansion for high-latitude trajectories.

This test verifies that the dynamic subgrid feature correctly identifies
when particles are approaching boundaries and would benefit from data expansion.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from pyhysplit.engine import TrajectoryEngine
from pyhysplit.met_reader import NetCDFReader
from pyhysplit.models import SimulationConfig, StartLocation

# Configure logging to see dynamic subgrid messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_dynamic_subgrid_high_latitude():
    """Test dynamic subgrid with high-latitude locations (Seoul, Beijing)."""
    
    # Test locations that experience boundary errors
    test_locations = [
        ("Seoul", 37.5, 127.0),
        ("Beijing", 39.9, 116.4),
        ("Tokyo", 35.7, 139.7),
        ("Busan", 35.2, 129.0),
    ]
    
    # Load GFS data (extended range)
    gfs_file = Path("tests/integration/gfs_cache/gfs_eastasia_24h_extended.nc")
    if not gfs_file.exists():
        logger.error(f"GFS data file not found: {gfs_file}")
        logger.error("Please run: python tests/integration/download_gfs_extended.py")
        return
    
    reader = NetCDFReader()
    met = reader.read(str(gfs_file))
    
    logger.info(f"Loaded GFS data: {met.lon_grid[0]:.1f}-{met.lon_grid[-1]:.1f}°E, "
                f"{met.lat_grid[0]:.1f}-{met.lat_grid[-1]:.1f}°N")
    
    results = []
    
    for name, lat, lon in test_locations:
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing: {name} ({lat}°N, {lon}°E)")
        logger.info(f"{'='*60}")
        
        # Create configuration with dynamic subgrid enabled
        config = SimulationConfig(
            start_time=datetime(2024, 1, 15, 0, 0),
            num_start_locations=1,
            start_locations=[StartLocation(lat=lat, lon=lon, height=850.0, height_type="pressure")],
            total_run_hours=-24,  # 24-hour backward trajectory
            vertical_motion=7,  # Mode 7 (Spatially averaged)
            model_top=10000.0,
            met_files=[],
            dt_max=900.0,
            tratio=0.75,
            auto_vertical_mode=False,
            enable_dynamic_subgrid=True,  # Enable dynamic subgrid
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
            
            # Get expansion statistics
            if engine.dynamic_subgrid is not None:
                stats = engine.dynamic_subgrid.get_expansion_stats()
                expansion_count = stats['expansion_count']
                expansion_history = stats['expansion_history']
            else:
                expansion_count = 0
                expansion_history = []
            
            result = {
                'name': name,
                'lat': lat,
                'lon': lon,
                'total_points': total_points,
                'actual_points': actual_points,
                'completion_rate': completion_rate,
                'expansion_count': expansion_count,
                'expansion_history': expansion_history,
                'success': actual_points >= total_points,
            }
            
            results.append(result)
            
            logger.info(f"\nResults for {name}:")
            logger.info(f"  Completion: {actual_points}/{total_points} points ({completion_rate:.1f}%)")
            logger.info(f"  Expansions: {expansion_count}")
            
            if expansion_count > 0:
                logger.info(f"\n  Expansion history:")
                for exp in expansion_history:
                    logger.info(f"    #{exp['count']}: pos=({exp['position'][0]:.2f}, {exp['position'][1]:.2f}), "
                              f"wind={exp['wind_speed']:.1f} m/s")
                    logger.info(f"      Old bounds: {exp['old_bounds']}")
                    logger.info(f"      New bounds: {exp['new_bounds']}")
            
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
    logger.info("SUMMARY")
    logger.info(f"{'='*60}")
    
    for result in results:
        if result['success']:
            logger.info(f"{result['name']:15s}: {result['completion_rate']:5.1f}% complete, "
                       f"{result['expansion_count']} expansions")
        else:
            logger.info(f"{result['name']:15s}: FAILED - {result.get('error', 'Unknown error')}")
    
    # Calculate statistics
    successful = [r for r in results if r['success']]
    if successful:
        avg_completion = np.mean([r['completion_rate'] for r in successful])
        total_expansions = sum([r['expansion_count'] for r in successful])
        
        logger.info(f"\nOverall Statistics:")
        logger.info(f"  Average completion: {avg_completion:.1f}%")
        logger.info(f"  Total expansions: {total_expansions}")
        logger.info(f"  Successful runs: {len(successful)}/{len(results)}")
    
    return results


if __name__ == "__main__":
    results = test_dynamic_subgrid_high_latitude()
    
    # Save results
    import json
    output_file = Path("tests/integration/dynamic_subgrid_results.json")
    with open(output_file, 'w') as f:
        # Convert numpy types to Python types for JSON serialization
        json_results = []
        for r in results:
            json_r = {k: v for k, v in r.items() if k != 'expansion_history'}
            if 'expansion_history' in r:
                json_r['expansion_count'] = r['expansion_count']
            json_results.append(json_r)
        json.dump(json_results, f, indent=2)
    
    logger.info(f"\nResults saved to: {output_file}")
