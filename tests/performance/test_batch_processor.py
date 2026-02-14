"""Tests for BatchProcessor and performance optimization."""

from __future__ import annotations

import time
from datetime import datetime

import numpy as np
import pytest

from pyhysplit.compute.batch_processor import BatchProcessor
from pyhysplit.core.models import MetData, SimulationConfig, StartLocation


def _gpu_available() -> bool:
    """Check if GPU is available."""
    try:
        import cupy as cp
        cp.cuda.Device(0).compute_capability
        return True
    except Exception:
        pass
    
    try:
        from numba import cuda
        return cuda.is_available()
    except Exception:
        pass
    
    return False


@pytest.fixture
def sample_met_data():
    """Create sample meteorological data for testing."""
    # Small grid for fast testing
    lon_grid = np.linspace(120.0, 130.0, 11)
    lat_grid = np.linspace(30.0, 40.0, 11)
    z_grid = np.array([1000.0, 850.0, 700.0, 500.0, 300.0])
    t_grid = np.array([0.0, 3600.0, 7200.0])
    
    nt, nz, nlat, nlon = len(t_grid), len(z_grid), len(lat_grid), len(lon_grid)
    
    # Simple wind field
    u = np.ones((nt, nz, nlat, nlon)) * 10.0  # 10 m/s eastward
    v = np.ones((nt, nz, nlat, nlon)) * 5.0   # 5 m/s northward
    w = np.zeros((nt, nz, nlat, nlon))        # No vertical motion
    
    return MetData(
        u=u, v=v, w=w,
        lon_grid=lon_grid,
        lat_grid=lat_grid,
        z_grid=z_grid,
        t_grid=t_grid,
        z_type="pressure",
    )


@pytest.fixture
def sample_config():
    """Create sample simulation configuration."""
    return SimulationConfig(
        start_time=datetime(2026, 2, 12, 0, 0),
        num_start_locations=1,
        start_locations=[
            StartLocation(lat=35.0, lon=125.0, height=850.0, height_type="pressure")
        ],
        total_run_hours=-6,  # 6 hour backward
        vertical_motion=0,
        model_top=10000.0,
        met_files=[],
    )


class TestBatchProcessor:
    """Test BatchProcessor functionality."""
    
    def test_initialization(self):
        """Test BatchProcessor initialization."""
        # CPU only
        processor = BatchProcessor(prefer_gpu=False)
        assert processor.backend is not None
        assert processor.parallel_executor is not None
        
        # Try GPU (may fall back to CPU)
        processor_gpu = BatchProcessor(prefer_gpu=True)
        assert processor_gpu.backend is not None
    
    def test_strategy_selection_small(self):
        """Test strategy selection for small problems."""
        processor = BatchProcessor(prefer_gpu=False)
        
        # Small problem: 1 source, 1 particle, 100 steps = 100 operations
        strategy = processor.select_strategy(
            num_sources=1,
            num_particles_per_source=1,
            num_timesteps=100,
        )
        assert strategy == 'sequential'
    
    def test_strategy_selection_medium(self):
        """Test strategy selection for medium problems."""
        processor = BatchProcessor(prefer_gpu=False)
        
        # Medium problem: 10 sources, 100 particles, 1000 steps = 1M operations
        strategy = processor.select_strategy(
            num_sources=10,
            num_particles_per_source=100,
            num_timesteps=1000,
        )
        assert strategy in ['sequential', 'gpu']
    
    def test_strategy_selection_large(self):
        """Test strategy selection for large problems."""
        processor = BatchProcessor(prefer_gpu=False)
        
        # Large problem: 100 sources, 1000 particles, 1000 steps = 100M operations
        strategy = processor.select_strategy(
            num_sources=100,
            num_particles_per_source=1000,
            num_timesteps=1000,
        )
        assert strategy in ['parallel', 'gpu', 'hybrid']
    
    def test_sequential_processing(self, sample_config, sample_met_data):
        """Test sequential processing."""
        processor = BatchProcessor(prefer_gpu=False)
        
        results = processor.process_batch(
            sample_config,
            sample_met_data,
            output_interval_s=3600.0,
            strategy='sequential',
        )
        
        assert len(results) == 1
        assert len(results[0]) > 0
        
        # Check trajectory format
        for point in results[0]:
            assert len(point) == 4  # (t, lon, lat, z)
            t, lon, lat, z = point
            assert isinstance(t, (int, float))
            assert isinstance(lon, (int, float))
            assert isinstance(lat, (int, float))
            assert isinstance(z, (int, float))
    
    def test_parallel_processing(self, sample_met_data):
        """Test parallel processing with multiple sources."""
        processor = BatchProcessor(prefer_gpu=False, num_workers=2)
        
        # Multiple sources
        config = SimulationConfig(
            start_time=datetime(2026, 2, 12, 0, 0),
            num_start_locations=4,
            start_locations=[
                StartLocation(lat=35.0, lon=125.0, height=850.0),
                StartLocation(lat=36.0, lon=126.0, height=850.0),
                StartLocation(lat=37.0, lon=127.0, height=850.0),
                StartLocation(lat=38.0, lon=128.0, height=850.0),
            ],
            total_run_hours=-3,
            vertical_motion=0,
            model_top=10000.0,
            met_files=[],
        )
        
        results = processor.process_batch(
            config,
            sample_met_data,
            output_interval_s=3600.0,
            strategy='parallel',
        )
        
        assert len(results) == 4
        for traj in results:
            assert len(traj) > 0
    
    def test_auto_strategy_selection(self, sample_config, sample_met_data):
        """Test automatic strategy selection."""
        processor = BatchProcessor(prefer_gpu=False)
        
        # Let processor choose strategy
        results = processor.process_batch(
            sample_config,
            sample_met_data,
            output_interval_s=3600.0,
            strategy=None,  # Auto-select
        )
        
        assert len(results) == 1
        assert len(results[0]) > 0
    
    @pytest.mark.skipif(
        not _gpu_available(),
        reason="GPU not available"
    )
    def test_gpu_processing(self, sample_config, sample_met_data):
        """Test GPU processing if available."""
        processor = BatchProcessor(prefer_gpu=True)
        
        results = processor.process_batch(
            sample_config,
            sample_met_data,
            output_interval_s=3600.0,
            strategy='gpu',
        )
        
        assert len(results) == 1
        assert len(results[0]) > 0
    
    def test_empty_config(self, sample_met_data):
        """Test handling of empty configuration."""
        processor = BatchProcessor(prefer_gpu=False)
        
        config = SimulationConfig(
            start_time=datetime(2026, 2, 12, 0, 0),
            num_start_locations=0,
            start_locations=[],
            total_run_hours=-6,
            vertical_motion=0,
            model_top=10000.0,
            met_files=[],
        )
        
        results = processor.process_batch(
            config,
            sample_met_data,
            output_interval_s=3600.0,
        )
        
        assert len(results) == 0


class TestPerformanceComparison:
    """Performance comparison tests."""
    
    def test_sequential_vs_parallel_speedup(self, sample_met_data):
        """Compare sequential vs parallel performance."""
        # Create config with multiple sources
        config = SimulationConfig(
            start_time=datetime(2026, 2, 12, 0, 0),
            num_start_locations=8,
            start_locations=[
                StartLocation(lat=35.0 + i, lon=125.0 + i, height=850.0)
                for i in range(8)
            ],
            total_run_hours=-3,
            vertical_motion=0,
            model_top=10000.0,
            met_files=[],
        )
        
        processor = BatchProcessor(prefer_gpu=False, num_workers=4)
        
        # Sequential
        start = time.time()
        results_seq = processor.process_batch(
            config, sample_met_data, strategy='sequential'
        )
        time_seq = time.time() - start
        
        # Parallel
        start = time.time()
        results_par = processor.process_batch(
            config, sample_met_data, strategy='parallel'
        )
        time_par = time.time() - start
        
        # Check results are consistent
        assert len(results_seq) == len(results_par) == 8
        
        # For small problems, parallel may have overhead
        # Just check that both complete successfully
        speedup = time_seq / time_par if time_par > 0 else 0
        print(f"Speedup: {speedup:.2f}x (seq: {time_seq:.3f}s, par: {time_par:.3f}s)")
        
        # Both should complete in reasonable time
        assert time_seq < 10.0, "Sequential too slow"
        assert time_par < 10.0, "Parallel too slow"
    
    def test_benchmark_all_strategies(self, sample_config, sample_met_data):
        """Benchmark all available strategies."""
        processor = BatchProcessor(prefer_gpu=False, num_workers=2)
        
        # Only test CPU strategies
        strategies = ['sequential', 'parallel']
        
        results = processor.benchmark(
            sample_config,
            sample_met_data,
            strategies=strategies,
        )
        
        assert len(results) == len(strategies)
        for strategy in strategies:
            assert strategy in results
            # Check that time is either positive or inf (failed)
            assert results[strategy] >= 0 or results[strategy] == float('inf')


class TestGPUBackend:
    """Test GPU backend functionality."""
    
    @pytest.mark.skipif(
        not _gpu_available(),
        reason="GPU not available"
    )
    def test_gpu_vs_cpu_consistency(self, sample_config, sample_met_data):
        """Test that GPU and CPU produce consistent results."""
        # CPU
        processor_cpu = BatchProcessor(prefer_gpu=False)
        results_cpu = processor_cpu.process_batch(
            sample_config, sample_met_data, strategy='sequential'
        )
        
        # GPU
        processor_gpu = BatchProcessor(prefer_gpu=True)
        results_gpu = processor_gpu.process_batch(
            sample_config, sample_met_data, strategy='gpu'
        )
        
        # Compare results
        assert len(results_cpu) == len(results_gpu)
        
        for traj_cpu, traj_gpu in zip(results_cpu, results_gpu):
            assert len(traj_cpu) == len(traj_gpu)
            
            for point_cpu, point_gpu in zip(traj_cpu, traj_gpu):
                t_cpu, lon_cpu, lat_cpu, z_cpu = point_cpu
                t_gpu, lon_gpu, lat_gpu, z_gpu = point_gpu
                
                # Allow small numerical differences
                assert abs(t_cpu - t_gpu) < 1e-6
                assert abs(lon_cpu - lon_gpu) < 1e-4
                assert abs(lat_cpu - lat_gpu) < 1e-4
                assert abs(z_cpu - z_gpu) < 1e-2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
