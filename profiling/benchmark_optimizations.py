"""Benchmark Phase 1 optimizations."""

from __future__ import annotations

import time
from datetime import datetime

import numpy as np

from pyhysplit.core.engine import TrajectoryEngine
from pyhysplit.core.interpolator import Interpolator
from pyhysplit.core.models import MetData, SimulationConfig, StartLocation


def create_test_met_data():
    """Create test meteorological data."""
    lon_grid = np.linspace(120.0, 130.0, 21)
    lat_grid = np.linspace(30.0, 40.0, 21)
    z_grid = np.array([200.0, 300.0, 500.0, 700.0, 850.0, 1000.0])
    t_grid = np.array([0.0, 3600.0, 7200.0, 10800.0])
    
    nt, nz, nlat, nlon = len(t_grid), len(z_grid), len(lat_grid), len(lon_grid)
    
    u = np.ones((nt, nz, nlat, nlon)) * 10.0
    v = np.ones((nt, nz, nlat, nlon)) * 5.0
    w = np.zeros((nt, nz, nlat, nlon))
    
    return MetData(
        u=u, v=v, w=w,
        lon_grid=lon_grid,
        lat_grid=lat_grid,
        z_grid=z_grid,
        t_grid=t_grid,
        z_type="pressure",
    )


def benchmark_interpolation():
    """Benchmark interpolation performance."""
    print("\n" + "="*80)
    print("Interpolation Benchmark")
    print("="*80)
    
    met = create_test_met_data()
    interpolator = Interpolator(met)
    
    # Warm up
    for _ in range(10):
        interpolator.interpolate_4d(125.0, 35.0, 850.0, 3600.0)
    
    # Benchmark: same time (cache hit)
    n_iterations = 10000
    start = time.time()
    for i in range(n_iterations):
        lon = 125.0 + (i % 100) * 0.01
        lat = 35.0 + (i % 100) * 0.01
        u, v, w = interpolator.interpolate_4d(lon, lat, 850.0, 3600.0)
    elapsed_cached = time.time() - start
    
    # Benchmark: different times (cache miss)
    start = time.time()
    for i in range(n_iterations):
        lon = 125.0 + (i % 100) * 0.01
        lat = 35.0 + (i % 100) * 0.01
        t = 3600.0 + (i % 100) * 10.0
        u, v, w = interpolator.interpolate_4d(lon, lat, 850.0, t)
    elapsed_uncached = time.time() - start
    
    per_call_cached = elapsed_cached / n_iterations * 1e6
    per_call_uncached = elapsed_uncached / n_iterations * 1e6
    
    print(f"Cached (same time):     {per_call_cached:.2f} µs/call")
    print(f"Uncached (diff times):  {per_call_uncached:.2f} µs/call")
    print(f"Cache benefit:          {per_call_uncached / per_call_cached:.2f}x")
    
    return per_call_cached, per_call_uncached


def benchmark_trajectory():
    """Benchmark full trajectory computation."""
    print("\n" + "="*80)
    print("Trajectory Benchmark")
    print("="*80)
    
    met = create_test_met_data()
    
    # Single trajectory
    config = SimulationConfig(
        start_time=datetime(2026, 2, 12, 0, 0),
        num_start_locations=1,
        start_locations=[
            StartLocation(lat=35.0, lon=125.0, height=850.0, height_type="pressure")
        ],
        total_run_hours=-3,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[],
    )
    
    # Warm up
    engine = TrajectoryEngine(config, met)
    engine.run(output_interval_s=3600.0)
    
    # Benchmark single trajectory
    n_runs = 100
    start = time.time()
    for _ in range(n_runs):
        engine = TrajectoryEngine(config, met)
        results = engine.run(output_interval_s=3600.0)
    elapsed_single = time.time() - start
    
    # Multiple trajectories
    config_multi = SimulationConfig(
        start_time=datetime(2026, 2, 12, 0, 0),
        num_start_locations=10,
        start_locations=[
            StartLocation(
                lat=35.0 + i * 0.5,
                lon=125.0 + i * 0.5,
                height=850.0,
                height_type="pressure"
            )
            for i in range(10)
        ],
        total_run_hours=-3,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[],
    )
    
    # Benchmark multiple trajectories
    n_runs_multi = 10
    start = time.time()
    for _ in range(n_runs_multi):
        engine = TrajectoryEngine(config_multi, met)
        results = engine.run(output_interval_s=3600.0)
    elapsed_multi = time.time() - start
    
    per_traj_single = elapsed_single / n_runs * 1000
    per_traj_multi = elapsed_multi / n_runs_multi * 1000
    
    print(f"Single trajectory:      {per_traj_single:.2f} ms")
    print(f"10 trajectories:        {per_traj_multi:.2f} ms")
    print(f"Per trajectory (multi): {per_traj_multi / 10:.2f} ms")
    
    return per_traj_single, per_traj_multi


def benchmark_memory_layout():
    """Benchmark memory layout optimization."""
    print("\n" + "="*80)
    print("Memory Layout Benchmark")
    print("="*80)
    
    # Non-contiguous array
    arr_non_contig = np.random.randn(100, 100, 100).T
    
    # Contiguous array
    arr_contig = np.ascontiguousarray(arr_non_contig)
    
    n_iterations = 100000
    
    # Benchmark non-contiguous
    start = time.time()
    for _ in range(n_iterations):
        _ = arr_non_contig[50, 50, 50]
    elapsed_non_contig = time.time() - start
    
    # Benchmark contiguous
    start = time.time()
    for _ in range(n_iterations):
        _ = arr_contig[50, 50, 50]
    elapsed_contig = time.time() - start
    
    per_access_non_contig = elapsed_non_contig / n_iterations * 1e9
    per_access_contig = elapsed_contig / n_iterations * 1e9
    
    print(f"Non-contiguous array:   {per_access_non_contig:.2f} ns/access")
    print(f"Contiguous array:       {per_access_contig:.2f} ns/access")
    print(f"Speedup:                {per_access_non_contig / per_access_contig:.2f}x")
    
    return per_access_non_contig, per_access_contig


def main():
    """Run all benchmarks."""
    print("\n" + "="*80)
    print("PyHYSPLIT Phase 1 Optimization Benchmarks")
    print("="*80)
    print("\nOptimizations:")
    print("  1. Memory layout (C-contiguous arrays)")
    print("  2. Time slice caching")
    print("  3. Conditional logging")
    
    # Run benchmarks
    interp_cached, interp_uncached = benchmark_interpolation()
    traj_single, traj_multi = benchmark_trajectory()
    mem_non_contig, mem_contig = benchmark_memory_layout()
    
    # Summary
    print("\n" + "="*80)
    print("Summary")
    print("="*80)
    print(f"\nInterpolation (cached):     {interp_cached:.2f} µs/call")
    print(f"Interpolation (uncached):   {interp_uncached:.2f} µs/call")
    print(f"Cache benefit:              {interp_uncached / interp_cached:.2f}x")
    print(f"\nSingle trajectory:          {traj_single:.2f} ms")
    print(f"10 trajectories:            {traj_multi:.2f} ms")
    print(f"Per trajectory (multi):     {traj_multi / 10:.2f} ms")
    print(f"\nMemory access (contiguous): {mem_contig:.2f} ns")
    print(f"Memory access (non-contig): {mem_non_contig:.2f} ns")
    print(f"Memory speedup:             {mem_non_contig / mem_contig:.2f}x")
    
    print("\n" + "="*80)
    print("Phase 1 Optimizations Complete!")
    print("="*80)
    print("\nExpected improvements:")
    print("  - Memory layout:    1.3x")
    print("  - Time caching:     1.5x")
    print("  - Conditional log:  1.2x")
    print("  - Combined:         2-3x")
    print("\nNext steps: Phase 2 (Grid index caching, Numba JIT)")


if __name__ == "__main__":
    main()
