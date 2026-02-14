"""Debug script to identify why PyHYSPLIT engine terminates early."""

import logging
import sys
from datetime import datetime, timedelta

import numpy as np

# Add parent directory to path
sys.path.insert(0, '/workspaces/pyhysplit')

from pyhysplit.engine import TrajectoryEngine
from pyhysplit.met_reader import NetCDFReader
from pyhysplit.models import SimulationConfig, StartLocation

# Enable DEBUG logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Run PyHYSPLIT with detailed debug logging."""
    
    # Configuration matching HYSPLIT Web
    start_loc = StartLocation(lat=37.5, lon=127.0, height=850.0)  # 850m AGL
    
    config = SimulationConfig(
        start_time=datetime(2026, 2, 13, 13, 0),  # 13:00 UTC
        num_start_locations=1,
        start_locations=[start_loc],
        total_run_hours=-7,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[],
        turbulence_on=False
    )
    
    print("\n=== Configuration ===")
    print(f"Start: {config.start_locations[0]}")
    print(f"Total run hours: {config.total_run_hours}")
    print(f"Direction: {'backward' if config.total_run_hours < 0 else 'forward'}")
    
    # Load GFS data
    gfs_file = "tests/integration/gfs_cache/gfs_20260213_37.5_127.0_1h.nc"
    reader = NetCDFReader()
    met = reader.read(gfs_file)
    
    print(f"\n=== Met Data ===")
    print(f"Time range: {met.t_grid[0]} to {met.t_grid[-1]}")
    print(f"Time steps: {len(met.t_grid)}")
    print(f"Lon range: {met.lon_grid.min()} to {met.lon_grid.max()}")
    print(f"Lat range: {met.lat_grid.min()} to {met.lat_grid.max()}")
    print(f"Z levels: {met.z_grid}")
    
    # Create engine
    engine = TrajectoryEngine(config, met)
    
    print(f"\n=== Engine Settings ===")
    print(f"Direction: {engine._direction}")
    print(f"Total seconds: {engine._total_seconds}")
    print(f"Is backward: {engine.is_backward}")
    
    # Run with 1-hour output interval
    print("\n=== Running Simulation ===")
    trajectories = engine.run(output_interval_s=3600.0)
    
    print(f"\n=== Results ===")
    print(f"Number of trajectories: {len(trajectories)}")
    
    if trajectories:
        traj = trajectories[0]
        print(f"Number of points: {len(traj)}")
        print("\nTrajectory points:")
        for i, (t, lon, lat, z) in enumerate(traj):
            dt = datetime(1970, 1, 1) + timedelta(seconds=t)
            print(f"  {i}: t={t:.1f}s ({dt}), lon={lon:.4f}, lat={lat:.4f}, z={z:.1f}m")

if __name__ == "__main__":
    main()
