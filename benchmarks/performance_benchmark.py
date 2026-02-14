"""Performance benchmark for PyHYSPLIT compute backends.

Compares CPU, GPU, and parallel processing performance across different
problem sizes.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import numpy as np

from pyhysplit.compute.batch_processor import BatchProcessor
from pyhysplit.core.models import MetData, SimulationConfig, StartLocation


def create_test_met_data(size: str = "medium") -> MetData:
    """Create test meteorological data.
    
    Parameters
    ----------
    size : str
        'small', 'medium', or 'large'
    """
    if size == "small":
        lon_grid = np.linspace(120.0, 130.0, 21)
        lat_grid = np.linspace(30.0, 40.0, 21)
        z_grid = np.array([1000.0, 850.0, 700.0, 500.0, 300.0])
        t_grid = np.array([0.0, 3600.0, 7200.0, 10800.0])
    elif size == "medium":
        lon_grid = np.linspace(95.0, 150.0, 111)  # 0.5° resolution
        lat_grid = np.linspace(20.0, 50.0, 61)
        z_grid = np.array([1000.0, 925.0, 850.0, 700.0, 500.0, 300.0, 200.0])
        t_grid = np.arange(0.0, 86400.0, 3600.0)  # 24 hours
    else:  # large
        lon_grid = np.linspace(95.0, 150.0, 221)  # 0.25° resolution
        lat_grid = np.linspace(20.0, 50.0, 121)
        z_grid = np.array([1000.0, 925.0, 850.0, 700.0, 600.0, 500.0, 400.0, 300.0, 200.0])
        t_grid = np.arange(0.0, 172800.0, 3600.0)  # 48 hours
    
    nt, nz, nlat, nlon = len(t_grid), len(z_grid), len(lat_grid), len(lon_grid)
    
    # Realistic wind field with variation
    u = np.random.randn(nt, nz, nlat, nlon) * 5 + 15  # Mean 15 m/s
    v = np.random.randn(nt, nz, nlat, nlon) * 5 + 5   # Mean 5 m/s
    w = np.random.randn(nt, nz, nlat, nlon) * 0.1     # Small vertical
    
    return MetData(
        u=u, v=v, w=w,
        lon_grid=lon_grid,
        lat_grid=lat_grid,
        z_grid=z_grid,
        t_grid=t_grid,
        z_type="pressure",
    )


def create_test_config(num_sources: int, run_hours: int = -24) -> SimulationConfig:
    """Create test configuration.
    
    Parameters
    ----------
    num_sources : int
        Number of start locations.
    run_hours : int
        Total run hours (negative for backward).
    """
    # Distribute sources across East Asia
    lats = np.linspace(25.0, 45.0, num_sources)
    lons = np.linspace(110.0, 140.0, num_sources)
    
    start_locations = [
        StartLocation(lat=float(lat), lon=float(lon), height=850.0, height_type="pressure")
        for lat, lon in zip(lats, lons)
    ]
    
    return SimulationConfig(
        start_time=datetime(2026, 2, 12, 0, 0),
        num_start_locations=num_sources,
        start_locations=start_locations,
        total_run_hours=run_hours,
        vertical_motion=7,
        model_top=10000.0,
        met_files=[],
    )


def benchmark_strategy(
    processor: BatchProcessor,
    config: SimulationConfig,
    met: MetData,
    strategy: str,
    num_runs: int = 3,
) -> dict:
    """Benchmark a specific strategy.
    
    Returns
    -------
    dict
        Statistics including mean, min, max time.
    """
    times = []
    
    for i in range(num_runs):
        print(f"  Run {i+1}/{num_runs}...", end=" ", flush=True)
        start = time.time()
        
        try:
            results = processor.process_batch(
                config, met, output_interval_s=3600.0, strategy=strategy
            )
            elapsed = time.time() - start
            times.append(elapsed)
            print(f"{elapsed:.3f}s")
            
            # Verify results
            assert len(results) == config.num_start_locations
            
        except Exception as e:
            print(f"FAILED: {e}")
            return {"error": str(e)}
    
    return {
        "mean": np.mean(times),
        "min": np.min(times),
        "max": np.max(times),
        "std": np.std(times),
        "times": times,
    }


def run_benchmark_suite():
    """Run comprehensive benchmark suite."""
    print("=" * 80)
    print("PyHYSPLIT Performance Benchmark")
    print("=" * 80)
    print()
    
    # Test configurations
    test_cases = [
        ("Small (1 source, 6h)", "small", 1, -6),
        ("Medium (4 sources, 24h)", "medium", 4, -24),
        ("Large (16 sources, 24h)", "medium", 16, -24),
        ("Very Large (64 sources, 24h)", "medium", 64, -24),
    ]
    
    strategies = ["sequential", "parallel", "gpu"]
    
    results = {}
    
    for test_name, met_size, num_sources, run_hours in test_cases:
        print(f"\n{'=' * 80}")
        print(f"Test Case: {test_name}")
        print(f"{'=' * 80}")
        
        # Create test data
        print(f"Creating {met_size} meteorological data...")
        met = create_test_met_data(met_size)
        print(f"  Grid: {len(met.lon_grid)}x{len(met.lat_grid)}x{len(met.z_grid)}")
        print(f"  Time steps: {len(met.t_grid)}")
        
        print(f"Creating configuration with {num_sources} sources...")
        config = create_test_config(num_sources, run_hours)
        
        # Initialize processor
        processor = BatchProcessor(prefer_gpu=True, num_workers=4)
        
        # Benchmark each strategy
        test_results = {}
        
        for strategy in strategies:
            print(f"\nBenchmarking {strategy}...")
            
            try:
                stats = benchmark_strategy(
                    processor, config, met, strategy, num_runs=3
                )
                test_results[strategy] = stats
                
                if "error" not in stats:
                    print(f"  Mean: {stats['mean']:.3f}s ± {stats['std']:.3f}s")
                    print(f"  Range: [{stats['min']:.3f}s, {stats['max']:.3f}s]")
                
            except Exception as e:
                print(f"  ERROR: {e}")
                test_results[strategy] = {"error": str(e)}
        
        results[test_name] = test_results
        
        # Calculate speedups
        if "sequential" in test_results and "error" not in test_results["sequential"]:
            seq_time = test_results["sequential"]["mean"]
            print(f"\nSpeedups (vs sequential):")
            
            for strategy in strategies:
                if strategy == "sequential":
                    continue
                if strategy in test_results and "error" not in test_results[strategy]:
                    speedup = seq_time / test_results[strategy]["mean"]
                    print(f"  {strategy}: {speedup:.2f}x")
    
    # Summary
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    
    for test_name, test_results in results.items():
        print(f"\n{test_name}:")
        for strategy, stats in test_results.items():
            if "error" in stats:
                print(f"  {strategy}: FAILED ({stats['error']})")
            else:
                print(f"  {strategy}: {stats['mean']:.3f}s")
    
    return results


def save_results(results: dict, output_file: str = "benchmark_results.txt"):
    """Save benchmark results to file."""
    with open(output_file, "w") as f:
        f.write("PyHYSPLIT Performance Benchmark Results\n")
        f.write("=" * 80 + "\n\n")
        
        for test_name, test_results in results.items():
            f.write(f"{test_name}:\n")
            for strategy, stats in test_results.items():
                if "error" in stats:
                    f.write(f"  {strategy}: FAILED\n")
                else:
                    f.write(f"  {strategy}: {stats['mean']:.3f}s ± {stats['std']:.3f}s\n")
            f.write("\n")
    
    print(f"\nResults saved to {output_file}")


if __name__ == "__main__":
    results = run_benchmark_suite()
    save_results(results)
