"""Performance profiling script for PyHYSPLIT.

Identifies bottlenecks and optimization opportunities.
"""

from __future__ import annotations

import cProfile
import pstats
import time
from datetime import datetime
from io import StringIO

import numpy as np

from pyhysplit.core.engine import TrajectoryEngine
from pyhysplit.core.models import MetData, SimulationConfig, StartLocation


def create_test_data():
    """Create test meteorological data."""
    # Medium-sized grid
    lon_grid = np.linspace(95.0, 150.0, 111)  # 0.5° resolution
    lat_grid = np.linspace(20.0, 50.0, 61)
    z_grid = np.array([1000.0, 925.0, 850.0, 700.0, 500.0, 300.0, 200.0])
    t_grid = np.arange(0.0, 86400.0, 3600.0)  # 24 hours
    
    nt, nz, nlat, nlon = len(t_grid), len(z_grid), len(lat_grid), len(lon_grid)
    
    # Realistic wind field
    u = np.random.randn(nt, nz, nlat, nlon) * 5 + 15
    v = np.random.randn(nt, nz, nlat, nlon) * 5 + 5
    w = np.random.randn(nt, nz, nlat, nlon) * 0.1
    
    return MetData(
        u=u, v=v, w=w,
        lon_grid=lon_grid,
        lat_grid=lat_grid,
        z_grid=z_grid,
        t_grid=t_grid,
        z_type="pressure",
    )


def create_test_config(num_sources: int = 1):
    """Create test configuration."""
    start_locations = [
        StartLocation(lat=37.5, lon=127.0, height=850.0, height_type="pressure")
        for _ in range(num_sources)
    ]
    
    return SimulationConfig(
        start_time=datetime(2026, 2, 12, 0, 0),
        num_start_locations=num_sources,
        start_locations=start_locations,
        total_run_hours=-24,
        vertical_motion=7,
        model_top=10000.0,
        met_files=[],
    )


def profile_single_trajectory():
    """Profile single trajectory computation."""
    import logging
    logging.getLogger('pyhysplit').setLevel(logging.ERROR)
    
    print("=" * 80)
    print("Profiling Single Trajectory")
    print("=" * 80)
    
    met = create_test_data()
    config = create_test_config(num_sources=1)
    engine = TrajectoryEngine(config, met)
    
    # Profile
    profiler = cProfile.Profile()
    profiler.enable()
    
    results = engine.run(output_interval_s=3600.0)
    
    profiler.disable()
    
    # Print stats
    s = StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
    ps.print_stats(30)  # Top 30 functions
    
    print(s.getvalue())
    print(f"\nTrajectory points: {len(results[0])}")


def profile_multiple_trajectories():
    """Profile multiple trajectory computation."""
    import logging
    logging.getLogger('pyhysplit').setLevel(logging.ERROR)
    
    print("\n" + "=" * 80)
    print("Profiling Multiple Trajectories (10 sources)")
    print("=" * 80)
    
    met = create_test_data()
    config = create_test_config(num_sources=10)
    engine = TrajectoryEngine(config, met)
    
    # Profile
    profiler = cProfile.Profile()
    profiler.enable()
    
    results = engine.run(output_interval_s=3600.0)
    
    profiler.disable()
    
    # Print stats
    s = StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
    ps.print_stats(30)
    
    print(s.getvalue())
    print(f"\nTotal trajectories: {len(results)}")


def analyze_hotspots():
    """Analyze specific hotspots."""
    print("\n" + "=" * 80)
    print("Hotspot Analysis")
    print("=" * 80)
    
    import logging
    logging.getLogger('pyhysplit').setLevel(logging.ERROR)  # Reduce logging
    
    met = create_test_data()
    config = create_test_config(num_sources=1)
    
    # Time individual components
    from pyhysplit.core.interpolator import Interpolator
    from pyhysplit.core.integrator import HeunIntegrator
    
    interpolator = Interpolator(met)
    integrator = HeunIntegrator(interpolator, met)
    
    # Test interpolation
    lon, lat, z, t = 127.0, 37.5, 850.0, 3600.0  # Use valid time
    
    print("\n1. Interpolation Performance:")
    start = time.time()
    for _ in range(1000):
        try:
            u, v, w = interpolator.interpolate_4d(lon, lat, z, t)
        except Exception:
            pass
    elapsed = time.time() - start
    print(f"   1000 interpolations: {elapsed:.3f}s ({elapsed/1000*1e6:.1f} µs/call)")
    
    # Test integration
    print("\n2. Integration Performance:")
    start = time.time()
    for _ in range(1000):
        try:
            lon_new, lat_new, z_new = integrator.step(lon, lat, z, t, 60.0)
        except Exception:
            pass
    elapsed = time.time() - start
    print(f"   1000 integration steps: {elapsed:.3f}s ({elapsed/1000*1e6:.1f} µs/call)")
    
    # Test boundary handling
    from pyhysplit.physics.boundary import BoundaryHandler
    boundary = BoundaryHandler(met, config)
    
    print("\n3. Boundary Handling Performance:")
    start = time.time()
    for _ in range(10000):
        lon_new, lat_new, z_new, active = boundary.apply(lon, lat, z, 0.0)
    elapsed = time.time() - start
    print(f"   10000 boundary checks: {elapsed:.3f}s ({elapsed/10000*1e6:.1f} µs/call)")
    
    # Test vertical motion
    from pyhysplit.physics.vertical_motion import VerticalMotionHandler
    vm_handler = VerticalMotionHandler(met, config)
    
    print("\n4. Vertical Motion Performance:")
    u, v, w = 10.0, 5.0, 0.1
    start = time.time()
    for _ in range(1000):
        try:
            w_adj = vm_handler.compute_vertical_velocity(lon, lat, z, t, u, v, w)
        except Exception:
            pass
    elapsed = time.time() - start
    print(f"   1000 vertical motion calcs: {elapsed:.3f}s ({elapsed/1000*1e6:.1f} µs/call)")


def memory_analysis():
    """Analyze memory usage."""
    print("\n" + "=" * 80)
    print("Memory Analysis")
    print("=" * 80)
    
    import sys
    
    met = create_test_data()
    config = create_test_config(num_sources=1)
    
    # Calculate memory usage
    u_size = met.u.nbytes / 1024 / 1024  # MB
    v_size = met.v.nbytes / 1024 / 1024
    w_size = met.w.nbytes / 1024 / 1024
    total_met = u_size + v_size + w_size
    
    print(f"\nMetData memory usage:")
    print(f"  u: {u_size:.2f} MB")
    print(f"  v: {v_size:.2f} MB")
    print(f"  w: {w_size:.2f} MB")
    print(f"  Total: {total_met:.2f} MB")
    
    print(f"\nGrid dimensions:")
    print(f"  lon: {len(met.lon_grid)}")
    print(f"  lat: {len(met.lat_grid)}")
    print(f"  z: {len(met.z_grid)}")
    print(f"  t: {len(met.t_grid)}")
    print(f"  Total points: {met.u.size:,}")


def identify_optimization_opportunities():
    """Identify specific optimization opportunities."""
    print("\n" + "=" * 80)
    print("Optimization Opportunities")
    print("=" * 80)
    
    opportunities = [
        {
            "area": "Interpolation",
            "current": "4D interpolation with searchsorted",
            "opportunity": "Cache grid indices, use Cython/Numba",
            "expected_gain": "2-5x",
        },
        {
            "area": "Integration",
            "current": "Heun method with 2 interpolations",
            "opportunity": "Vectorize multiple particles, GPU",
            "expected_gain": "10-100x",
        },
        {
            "area": "Boundary Handling",
            "current": "Per-step checks",
            "opportunity": "Batch checks, early termination",
            "expected_gain": "1.5-2x",
        },
        {
            "area": "Vertical Motion",
            "current": "Mode 7 with spatial averaging",
            "opportunity": "Pre-compute averages, cache",
            "expected_gain": "2-3x",
        },
        {
            "area": "Memory Access",
            "current": "Random access to 4D arrays",
            "opportunity": "Improve cache locality, use views",
            "expected_gain": "1.5-2x",
        },
        {
            "area": "Logging",
            "current": "Many debug/info logs in loop",
            "opportunity": "Reduce logging, use lazy evaluation",
            "expected_gain": "1.2-1.5x",
        },
    ]
    
    print("\n{:<20} {:<30} {:<30} {:<15}".format(
        "Area", "Current", "Opportunity", "Expected Gain"
    ))
    print("-" * 95)
    
    for opp in opportunities:
        print("{:<20} {:<30} {:<30} {:<15}".format(
            opp["area"],
            opp["current"][:28],
            opp["opportunity"][:28],
            opp["expected_gain"],
        ))
    
    print("\n" + "=" * 80)
    print("Priority Recommendations:")
    print("=" * 80)
    print("\n1. HIGH PRIORITY - Vectorize Integration")
    print("   - Implement batch processing for multiple particles")
    print("   - Use GPU for large batches")
    print("   - Expected: 10-100x speedup")
    
    print("\n2. MEDIUM PRIORITY - Optimize Interpolation")
    print("   - Cache grid indices between steps")
    print("   - Use Cython or Numba for hot loops")
    print("   - Expected: 2-5x speedup")
    
    print("\n3. MEDIUM PRIORITY - Reduce Memory Access")
    print("   - Improve cache locality")
    print("   - Use array views instead of copies")
    print("   - Expected: 1.5-2x speedup")
    
    print("\n4. LOW PRIORITY - Optimize Logging")
    print("   - Reduce logging in hot loops")
    print("   - Use lazy string formatting")
    print("   - Expected: 1.2-1.5x speedup")


def main():
    """Run all profiling analyses."""
    print("\n" + "=" * 80)
    print("PyHYSPLIT Performance Profiling")
    print("=" * 80)
    print()
    
    # Run analyses
    profile_single_trajectory()
    profile_multiple_trajectories()
    analyze_hotspots()
    memory_analysis()
    identify_optimization_opportunities()
    
    print("\n" + "=" * 80)
    print("Profiling Complete")
    print("=" * 80)


if __name__ == "__main__":
    main()
