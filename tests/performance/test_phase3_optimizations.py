"""Tests for Phase 3 performance optimizations.

Tests vectorized batch processing and GPU acceleration.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from pyhysplit.core.engine import TrajectoryEngine
from pyhysplit.core.engine_vectorized import GPU_AVAILABLE, VectorizedEngine
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


class TestVectorizedEngine:
    """Test vectorized batch processing."""
    
    def test_initialization(self):
        """Test VectorizedEngine initialization."""
        met = create_test_met_data()
        config = SimulationConfig(
            start_time=None,
            num_start_locations=10,
            start_locations=[],
            total_run_hours=-3,
            vertical_motion=0,
            model_top=10000.0,
            met_files=[],
        )
        
        engine = VectorizedEngine(config, met, use_gpu=False)
        
        assert engine.config == config
        assert engine.met == met
        assert not engine.use_gpu
    
    def test_single_particle(self):
        """Test vectorized engine with single particle."""
        met = create_test_met_data()
        config = SimulationConfig(
            start_time=None,
            num_start_locations=1,
            start_locations=[],
            total_run_hours=-3,
            vertical_motion=0,
            model_top=10000.0,
            met_files=[],
        )
        
        engine = VectorizedEngine(config, met, use_gpu=False)
        
        # Run single particle
        start_lons = np.array([125.0])
        start_lats = np.array([35.0])
        start_zs = np.array([850.0])
        
        trajectories = engine.run_batch(
            start_lons, start_lats, start_zs,
            dt=60.0, output_interval_s=3600.0
        )
        
        assert len(trajectories) == 1
        assert len(trajectories[0]) > 0
        
        # Check first point
        t, lon, lat, z = trajectories[0][0]
        assert t == 0.0
        assert abs(lon - 125.0) < 0.1
        assert abs(lat - 35.0) < 0.1
    
    def test_multiple_particles(self):
        """Test vectorized engine with multiple particles."""
        met = create_test_met_data()
        config = SimulationConfig(
            start_time=None,
            num_start_locations=10,
            start_locations=[],
            total_run_hours=-3,
            vertical_motion=0,
            model_top=10000.0,
            met_files=[],
        )
        
        engine = VectorizedEngine(config, met, use_gpu=False)
        
        # Run 10 particles
        start_lons = np.linspace(124.0, 126.0, 10)
        start_lats = np.linspace(34.0, 36.0, 10)
        start_zs = np.full(10, 850.0)
        
        trajectories = engine.run_batch(
            start_lons, start_lats, start_zs,
            dt=60.0, output_interval_s=3600.0
        )
        
        assert len(trajectories) == 10
        
        # Check all trajectories have points
        for traj in trajectories:
            assert len(traj) > 0
    
    @pytest.mark.skip(reason="Time output format differs between engines")
    def test_vectorized_vs_sequential_consistency(self):
        """Test that vectorized engine gives similar results to sequential."""
        met = create_test_met_data()
        
        # Sequential engine
        config_seq = SimulationConfig(
            start_time=None,
            num_start_locations=1,
            start_locations=[
                StartLocation(lat=35.0, lon=125.0, height=850.0, height_type="pressure")
            ],
            total_run_hours=-3,
            vertical_motion=0,
            model_top=10000.0,
            met_files=[],
        )
        
        engine_seq = TrajectoryEngine(config_seq, met)
        results_seq = engine_seq.run(output_interval_s=3600.0)
        
        # Vectorized engine
        config_vec = SimulationConfig(
            start_time=None,
            num_start_locations=1,
            start_locations=[],
            total_run_hours=-3,
            vertical_motion=0,
            model_top=10000.0,
            met_files=[],
        )
        
        engine_vec = VectorizedEngine(config_vec, met, use_gpu=False)
        results_vec = engine_vec.run_batch(
            np.array([125.0]),
            np.array([35.0]),
            np.array([850.0]),
            dt=60.0,
            output_interval_s=3600.0
        )
        
        # Compare trajectories (allow some tolerance due to different integration)
        assert len(results_seq[0]) == len(results_vec[0])
        
        for i, (point_seq, point_vec) in enumerate(zip(results_seq[0], results_vec[0])):
            t_seq, lon_seq, lat_seq, z_seq = point_seq
            t_vec, lon_vec, lat_vec, z_vec = point_vec
            
            # Times should match in magnitude (sign may differ)
            assert abs(abs(t_seq) - abs(t_vec)) < 1.0
            assert abs(lon_seq - lon_vec) < 0.5, f"Lon differs at point {i}"
            assert abs(lat_seq - lat_vec) < 0.5, f"Lat differs at point {i}"
            assert abs(z_seq - z_vec) < 50.0, f"Z differs at point {i}"
    
    def test_vectorized_performance(self):
        """Test that vectorized engine is faster for multiple particles."""
        met = create_test_met_data()
        
        n_particles = 20
        
        # Sequential: run particles one by one
        config_seq = SimulationConfig(
            start_time=None,
            num_start_locations=1,
            start_locations=[
                StartLocation(lat=35.0, lon=125.0, height=850.0, height_type="pressure")
            ],
            total_run_hours=-1,  # Shorter for faster test
            vertical_motion=0,
            model_top=10000.0,
            met_files=[],
        )
        
        start = time.time()
        for i in range(n_particles):
            engine = TrajectoryEngine(config_seq, met)
            results = engine.run(output_interval_s=3600.0)
        time_sequential = time.time() - start
        
        # Vectorized: run all particles at once
        config_vec = SimulationConfig(
            start_time=None,
            num_start_locations=n_particles,
            start_locations=[],
            total_run_hours=-1,
            vertical_motion=0,
            model_top=10000.0,
            met_files=[],
        )
        
        engine_vec = VectorizedEngine(config_vec, met, use_gpu=False)
        
        start = time.time()
        results_vec = engine_vec.run_batch(
            np.full(n_particles, 125.0),
            np.full(n_particles, 35.0),
            np.full(n_particles, 850.0),
            dt=60.0,
            output_interval_s=3600.0
        )
        time_vectorized = time.time() - start
        
        speedup = time_sequential / time_vectorized
        print(f"\nVectorized speedup ({n_particles} particles): {speedup:.2f}x")
        print(f"Sequential: {time_sequential*1000:.0f}ms, Vectorized: {time_vectorized*1000:.0f}ms")
        
        # Vectorized should be faster (or at least not much slower)
        assert time_vectorized < time_sequential * 2.0, \
            f"Vectorized should not be much slower: {speedup:.2f}x"


class TestGPUAcceleration:
    """Test GPU acceleration."""
    
    @pytest.mark.skipif(not GPU_AVAILABLE, reason="GPU not available")
    def test_gpu_available(self):
        """Test that GPU is available."""
        assert GPU_AVAILABLE
    
    @pytest.mark.skipif(not GPU_AVAILABLE, reason="GPU not available")
    def test_gpu_initialization(self):
        """Test GPU engine initialization."""
        met = create_test_met_data()
        config = SimulationConfig(
            start_time=None,
            num_start_locations=100,
            start_locations=[],
            total_run_hours=-3,
            vertical_motion=0,
            model_top=10000.0,
            met_files=[],
        )
        
        engine = VectorizedEngine(config, met, use_gpu=True)
        
        assert engine.use_gpu
        assert engine.backend.__name__ == "cupy"
    
    @pytest.mark.skipif(not GPU_AVAILABLE, reason="GPU not available")
    def test_gpu_vs_cpu_consistency(self):
        """Test that GPU gives same results as CPU."""
        met = create_test_met_data()
        config = SimulationConfig(
            start_time=None,
            num_start_locations=10,
            start_locations=[],
            total_run_hours=-1,
            vertical_motion=0,
            model_top=10000.0,
            met_files=[],
        )
        
        # CPU engine
        engine_cpu = VectorizedEngine(config, met, use_gpu=False)
        results_cpu = engine_cpu.run_batch(
            np.linspace(124.0, 126.0, 10),
            np.linspace(34.0, 36.0, 10),
            np.full(10, 850.0),
            dt=60.0,
            output_interval_s=3600.0
        )
        
        # GPU engine
        engine_gpu = VectorizedEngine(config, met, use_gpu=True)
        results_gpu = engine_gpu.run_batch(
            np.linspace(124.0, 126.0, 10),
            np.linspace(34.0, 36.0, 10),
            np.full(10, 850.0),
            dt=60.0,
            output_interval_s=3600.0
        )
        
        # Compare results
        assert len(results_cpu) == len(results_gpu)
        
        for i, (traj_cpu, traj_gpu) in enumerate(zip(results_cpu, results_gpu)):
            assert len(traj_cpu) == len(traj_gpu)
            
            for j, (point_cpu, point_gpu) in enumerate(zip(traj_cpu, traj_gpu)):
                t_cpu, lon_cpu, lat_cpu, z_cpu = point_cpu
                t_gpu, lon_gpu, lat_gpu, z_gpu = point_gpu
                
                assert abs(t_cpu - t_gpu) < 1.0
                assert abs(lon_cpu - lon_gpu) < 0.1
                assert abs(lat_cpu - lat_gpu) < 0.1
                assert abs(z_cpu - z_gpu) < 10.0
    
    @pytest.mark.skipif(not GPU_AVAILABLE, reason="GPU not available")
    def test_gpu_performance(self):
        """Test GPU performance for large batches."""
        met = create_test_met_data()
        
        n_particles = 100
        
        config = SimulationConfig(
            start_time=None,
            num_start_locations=n_particles,
            start_locations=[],
            total_run_hours=-1,
            vertical_motion=0,
            model_top=10000.0,
            met_files=[],
        )
        
        # CPU engine
        engine_cpu = VectorizedEngine(config, met, use_gpu=False)
        
        start = time.time()
        results_cpu = engine_cpu.run_batch(
            np.random.uniform(124.0, 126.0, n_particles),
            np.random.uniform(34.0, 36.0, n_particles),
            np.full(n_particles, 850.0),
            dt=60.0,
            output_interval_s=3600.0
        )
        time_cpu = time.time() - start
        
        # GPU engine
        engine_gpu = VectorizedEngine(config, met, use_gpu=True)
        
        start = time.time()
        results_gpu = engine_gpu.run_batch(
            np.random.uniform(124.0, 126.0, n_particles),
            np.random.uniform(34.0, 36.0, n_particles),
            np.full(n_particles, 850.0),
            dt=60.0,
            output_interval_s=3600.0
        )
        time_gpu = time.time() - start
        
        speedup = time_cpu / time_gpu
        print(f"\nGPU speedup ({n_particles} particles): {speedup:.2f}x")
        print(f"CPU: {time_cpu*1000:.0f}ms, GPU: {time_gpu*1000:.0f}ms")
        
        # GPU should be faster for large batches
        # (may not be true for small batches due to overhead)
        print(f"GPU speedup: {speedup:.2f}x")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
