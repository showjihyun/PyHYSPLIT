"""Complete PySPlit workflow with HYSPLIT-compatible output.

This example demonstrates:
1. Loading meteorological data
2. Configuring trajectory and concentration calculations
3. Running the simulation
4. Writing HYSPLIT-compatible output files (tdump and cdump)
"""

from datetime import datetime
from pathlib import Path

from pyhysplit.core.engine import TrajectoryEngine
from pyhysplit.core.models import (
    SimulationConfig,
    StartLocation,
    ConcentrationGridConfig,
)
from pyhysplit.data.met_reader import NetCDFReader
from pyhysplit.io import TdumpWriter, CdumpWriter


def main():
    """Run complete workflow with output generation."""
    
    # ========================================================================
    # 1. Load Meteorological Data
    # ========================================================================
    print("Loading meteorological data...")
    reader = NetCDFReader()
    met = reader.read("path/to/gfs_data.nc")  # Replace with actual path
    print(f"✓ Loaded met data: {met.source}")
    print(f"  Grid: {len(met.lon_grid)}×{len(met.lat_grid)}×{len(met.z_grid)}")
    print(f"  Time steps: {len(met.t_grid)}")
    
    # ========================================================================
    # 2. Configure Simulation
    # ========================================================================
    print("\nConfiguring simulation...")
    
    # Define concentration grid
    grid_config = ConcentrationGridConfig(
        center_lat=37.5,
        center_lon=127.0,
        spacing_lat=0.1,
        spacing_lon=0.1,
        span_lat=2.0,
        span_lon=2.0,
        levels=[0, 100, 500, 1000, 2000],
        sampling_start=datetime(2024, 1, 15, 0, 0),
        sampling_end=datetime(2024, 1, 16, 0, 0),
        averaging_period=24,
    )
    
    # Simulation configuration
    config = SimulationConfig(
        start_time=datetime(2024, 1, 15, 12, 0),
        num_start_locations=1,
        start_locations=[
            StartLocation(lat=37.5, lon=127.0, height=500.0)
        ],
        total_run_hours=-24,  # 24-hour backward trajectory
        vertical_motion=7,     # Mode 7: Spatially averaged
        model_top=10000.0,
        met_files=[],
        concentration_grids=[grid_config],
        # Enable physics
        dry_deposition=True,
        wet_deposition=True,
        turbulence_on=True,
    )
    
    print(f"✓ Configuration:")
    print(f"  Start: {config.start_time}")
    print(f"  Duration: {config.total_run_hours} hours")
    print(f"  Locations: {config.num_start_locations}")
    print(f"  Concentration grids: {len(config.concentration_grids)}")
    
    # ========================================================================
    # 3. Run Simulation
    # ========================================================================
    print("\nRunning simulation...")
    engine = TrajectoryEngine(config, met)
    
    # Run with concentration calculation
    trajectories, grids = engine.run_with_concentration(
        output_interval_s=3600.0,  # 1-hour intervals
        initial_mass=1.0,           # 1 kg initial mass
    )
    
    print(f"✓ Simulation complete:")
    print(f"  Trajectories: {len(trajectories)}")
    print(f"  Trajectory points: {len(trajectories[0])}")
    print(f"  Concentration grids: {len(grids)}")
    
    # ========================================================================
    # 4. Write Trajectory Output (tdump)
    # ========================================================================
    print("\nWriting trajectory output...")
    
    # Create output directory
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # Initialize tdump writer
    tdump_writer = TdumpWriter(
        config,
        met_model_id="GFS",
        diagnostic_vars=["PRESSURE", "THETA", "AIR_TEMP", "RAINFALL"],
    )
    
    # Generate filename
    tdump_filename = TdumpWriter.generate_filename(
        start_time=config.start_time,
        location_name="seoul"
    )
    tdump_path = output_dir / tdump_filename
    
    # Write trajectory file
    tdump_writer.write(tdump_path, trajectories)
    
    print(f"✓ Trajectory output written:")
    print(f"  File: {tdump_path}")
    print(f"  Size: {tdump_path.stat().st_size / 1024:.1f} KB")
    print(f"  Format: HYSPLIT tdump (ASCII)")
    
    # ========================================================================
    # 5. Write Concentration Output (cdump)
    # ========================================================================
    print("\nWriting concentration output...")
    
    # Initialize cdump writer
    cdump_writer = CdumpWriter(
        config,
        met_model_id="GFS",
        packing=True,  # Use packed format for smaller files
    )
    
    # Generate filename
    cdump_filename = CdumpWriter.generate_filename(
        start_time=config.start_time,
        location_name="seoul"
    )
    cdump_path = output_dir / (cdump_filename + ".bin")
    
    # Write concentration file
    cdump_writer.write(
        cdump_path,
        grids,
        pollutant_ids=["PM25"]
    )
    
    print(f"✓ Concentration output written:")
    print(f"  File: {cdump_path}")
    print(f"  Size: {cdump_path.stat().st_size / 1024:.1f} KB")
    print(f"  Format: HYSPLIT cdump (binary, packed)")
    
    # ========================================================================
    # 6. Summary
    # ========================================================================
    print("\n" + "="*70)
    print("WORKFLOW COMPLETE")
    print("="*70)
    print(f"\nOutput files:")
    print(f"  1. {tdump_path}")
    print(f"  2. {cdump_path}")
    print(f"\nThese files are HYSPLIT-compatible and can be used with:")
    print(f"  - trajplot (trajectory visualization)")
    print(f"  - concplot (concentration visualization)")
    print(f"  - HYSPLIT GUI")
    print(f"  - Third-party tools (PySPLIT, openair, etc.)")
    print("\n" + "="*70)
    
    # ========================================================================
    # 7. Optional: Print Statistics
    # ========================================================================
    print("\nSimulation Statistics:")
    print(f"  Final position: {trajectories[0][-1][1]:.2f}°E, {trajectories[0][-1][2]:.2f}°N")
    print(f"  Final height: {trajectories[0][-1][3]:.1f} m")
    
    if grids:
        grid = grids[0]
        max_conc = grid.concentration.max()
        print(f"  Maximum concentration: {max_conc:.2e} kg/m³")
        print(f"  Grid size: {len(grid.lat_grid)}×{len(grid.lon_grid)}×{len(grid.z_grid)}")


if __name__ == "__main__":
    main()
