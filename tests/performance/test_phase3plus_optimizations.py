"""Tests for Phase 3+ optimizations: Batch interpolation and GPU kernels.

Tests the final optimization layer for maximum performance.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from pyhysplit.core.interpolator_gpu import (
    GPU_AVAILABLE,
    BatchInterpolator,
    create_batch_interpolator,
)
from pyhysplit.core.engine_vectorized_v2 import VectorizedEngineV2
from pyhysplit.core.models import MetData, SimulationConfig


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


class TestBatchInterpolator:
    """Test batch interpolation."""
    
    def test_initialization_cpu(self):
        """Test BatchInterpolator initialization on CPU."""
        met = create_test_met_data()
        interp = BatchInterpolator(met, use_gpu=False)
        
        assert not interp.use_gpu
        assert interp.backend.__name__ == "numpy"
    
    @pytest.mark.skipif(not GPU_AVAILABLE, reason="GPU not available")
    def test_initialization_gpu(self):
        """Test BatchInterpolator initialization on GPU."""
        met = create_test_met_data()
        interp = BatchInterpolator(met, use_gpu=True)
        
        assert interp.use_gpu
        assert interp.backend.__name__ == "cupy"
    
    def test_batch_interpolation_single_point(self):
        """Test batch interpolation with single point."""
        met = create_test_met_data()
        interp = BatchInterpolator(met, use_gpu=False)
        
        lons = np.array([125.0])
        lats = np.array([35.0])
        zs = np.array([850.0])
        
        u, v, w = interp.interpolate_batch(lons, lats, zs, 3600.0)
        
        assert len(u) == 1
        assert len(v) == 1
        assert len(w) == 1
        assert 0 < u[0] < 20
        assert 0 < v[0] < 10
    
    def test_batch_interpolation_multiple_points(self):
        """Test batch interpolation with multiple points."""
        met = create_test_met_data()
        interp = BatchInterpolator(met, use_gpu=False)
        
        n = 100
        lons = np.linspace(124.0, 126.0, n)
        lats = np.linspace(34.0, 36.0, n)
        zs = np.full(n, 850.0)
        
        u, v, w = interp.interpolate_batch(lons, lats, zs, 3600.0)
        
        assert len(u) == n
        assert len(v) == n
        assert len(w) == n
        assert np.all((u > 0) & (u < 20))
        assert np.all((v > 0) & (v < 10))
    
    def test_batch_vs_sequential_consistency(self):
        """Test that batch gives same results as sequential."""
        met = create_test_met_data()
        interp = BatchInterpolator(met, use_gpu=False)
        
        # Test points
        lons = np.array([125.0, 125.5, 126.0])
        lats = np.array([35.0, 35.5, 36.0])
        zs = np.array([850.0, 850.0, 850.0])
        
        # Batch interpolation
        u_batch, v_batch, w_batch = interp.interpolate_batch(lons, lats, zs, 3600.0)
        
        # Sequential interpolation
        u_seq = []
        v_seq = []
        w_seq = []
        for lon, lat, z in zip(lons, lats, zs):
            u_i, v_i, w_i = interp.interpolate_4d(lon, lat, z, 3600.0)
            u_seq.append(u_i)
            v_seq.append(v_i)
            w_seq.append(w_i)
        
        u_seq = np.array(u_seq)
        v_seq = np.array(v_seq)
        w_seq = np.array(w_seq)
        
        # Should be identical
        np.testing.assert_allclose(u_batch, u_seq, rtol=1e-10)
        np.testing.assert_allclose(v_batch, v_seq, rtol=1e-10)
        np.testing.assert_allclose(w_batch, w_seq, rtol=1e-10)
    
    def test_batch_interpolation_performance(self):
        """Test that batch interpolation is faster than sequential."""
        met = create_test_met_data()
        interp = BatchInterpolator(met, use_gpu=False)
        
        n = 1000
        lons = np.random.uniform(124.0, 126.0, n)
        lats = np.random.uniform(34.0, 36.0, n)
        zs = np.full(n, 850.0)
        
        # Warm up
        interp.interpolate_batch(lons[:10], lats[:10], zs[:10], 3600.0)
        
        # Batch interpolation (multiple runs for accurate timing)
        n_runs = 10
        start = time.time()
        for _ in range(n_runs):
            u_batch, v_batch, w_batch = interp.interpolate_batch(lons, lats, zs, 3600.0)
        time_batch = (time.time() - start) / n_runs
        
        # Sequential interpolation (multiple runs)
        start = time.time()
        for _ in range(n_runs):
            for i in range(n):
                u, v, w = interp.interpolate_4d(lons[i], lats[i], zs[i], 3600.0)
        time_sequential = (time.time() - start) / n_runs
        
        speedup = time_sequential / time_batch if time_batch > 0 else float('inf')
        print(f"\nBatch interpolation speedup ({n} points): {speedup:.2f}x")
        print(f"Sequential: {time_sequential*1000:.0f}ms, Batch: {time_batch*1000:.0f}ms")
        
        # Batch should be significantly faster
        assert speedup > 2.0, f"Batch should be much faster: {speedup:.2f}x"
    
    @pytest.mark.skipif(not GPU_AVAILABLE, reason="GPU not available")
    def test_gpu_vs_cpu_consistency(self):
        """Test that GPU gives same results as CPU."""
        met = create_test_met_data()
        interp_cpu = BatchInterpolator(met, use_gpu=False)
        interp_gpu = BatchInterpolator(met, use_gpu=True)
        
        n = 100
        lons = np.linspace(124.0, 126.0, n)
        lats = np.linspace(34.0, 36.0, n)
        zs = np.full(n, 850.0)
        
        # CPU interpolation
        u_cpu, v_cpu, w_cpu = interp_cpu.interpolate_batch(lons, lats, zs, 3600.0)
        
        # GPU interpolation
        u_gpu, v_gpu, w_gpu = interp_gpu.interpolate_batch(lons, lats, zs, 3600.0)
        
        # Should be very close
        np.testing.assert_allclose(u_cpu, u_gpu, rtol=1e-5)
        np.testing.assert_allclose(v_cpu, v_gpu, rtol=1e-5)
        np.testing.assert_allclose(w_cpu, w_gpu, rtol=1e-5)
    
    @pytest.mark.skipif(not GPU_AVAILABLE, reason="GPU not available")
    def test_gpu_performance(self):
        """Test GPU performance for large batches."""
        met = create_test_met_data()
        interp_cpu = BatchInterpolator(met, use_gpu=False)
        interp_gpu = BatchInterpolator(met, use_gpu=True)
        
        n = 10000
        lons = np.random.uniform(124.0, 126.0, n)
        lats = np.random.uniform(34.0, 36.0, n)
        zs = np.full(n, 850.0)
        
        # Warm up
        interp_cpu.interpolate_batch(lons[:10], lats[:10], zs[:10], 3600.0)
        interp_gpu.interpolate_batch(lons[:10], lats[:10], zs[:10], 3600.0)
        
        # CPU benchmark
        start = time.time()
        u_cpu, v_cpu, w_cpu = interp_cpu.interpolate_batch(lons, lats, zs, 3600.0)
        time_cpu = time.time() - start
        
        # GPU benchmark
        start = time.time()
        u_gpu, v_gpu, w_gpu = interp_gpu.interpolate_batch(lons, lats, zs, 3600.0)
        time_gpu = time.time() - start
        
        speedup = time_cpu / time_gpu
        print(f"\nGPU interpolation speedup ({n} points): {speedup:.2f}x")
        print(f"CPU: {time_cpu*1000:.0f}ms, GPU: {time_gpu*1000:.0f}ms")
        
        # GPU should be faster for large batches
        print(f"GPU speedup: {speedup:.2f}x")


class TestVectorizedEngineV2:
    """Test improved vectorized engine."""
    
    def test_initialization(self):
        """Test VectorizedEngineV2 initialization."""
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
        
        engine = VectorizedEngineV2(config, met, use_gpu=False)
        
        assert engine.config == config
        assert engine.met == met
        assert not engine.use_gpu
    
    def test_batch_trajectory_computation(self):
        """Test trajectory computation with batch interpolation."""
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
        
        engine = VectorizedEngineV2(config, met, use_gpu=False)
        
        trajectories = engine.run_batch(
            np.linspace(124.0, 126.0, 10),
            np.linspace(34.0, 36.0, 10),
            np.full(10, 850.0),
            dt=60.0,
            output_interval_s=3600.0
        )
        
        assert len(trajectories) == 10
        for traj in trajectories:
            assert len(traj) > 0
    
    def test_v2_vs_v1_performance(self):
        """Compare V2 (batch) vs V1 (sequential) performance."""
        from pyhysplit.core.engine_vectorized import VectorizedEngine
        
        met = create_test_met_data()
        n_particles = 50
        
        config = SimulationConfig(
            start_time=None,
            num_start_locations=n_particles,
            start_locations=[],
            total_run_hours=-1,
            vertical_motion=0,
            model_top=10000.0,
            met_files=[],
        )
        
        # V1 engine (sequential interpolation)
        engine_v1 = VectorizedEngine(config, met, use_gpu=False)
        
        start = time.time()
        results_v1 = engine_v1.run_batch(
            np.full(n_particles, 125.0),
            np.full(n_particles, 35.0),
            np.full(n_particles, 850.0),
            dt=60.0,
            output_interval_s=3600.0
        )
        time_v1 = time.time() - start
        
        # V2 engine (batch interpolation)
        engine_v2 = VectorizedEngineV2(config, met, use_gpu=False)
        
        start = time.time()
        results_v2 = engine_v2.run_batch(
            np.full(n_particles, 125.0),
            np.full(n_particles, 35.0),
            np.full(n_particles, 850.0),
            dt=60.0,
            output_interval_s=3600.0
        )
        time_v2 = time.time() - start
        
        speedup = time_v1 / time_v2 if time_v2 > 0 else float('inf')
        print(f"\nV2 vs V1 speedup ({n_particles} particles): {speedup:.2f}x")
        print(f"V1: {time_v1*1000:.0f}ms, V2: {time_v2*1000:.0f}ms")
        
        # V2 should be faster (or at least not much slower)
        assert time_v2 < time_v1 * 2.0, f"V2 should not be much slower: {speedup:.2f}x"


class TestFactoryFunction:
    """Test interpolator factory function."""
    
    def test_create_batch_interpolator_cpu(self):
        """Test factory creates CPU interpolator."""
        met = create_test_met_data()
        interp = create_batch_interpolator(met, use_gpu=False)
        
        assert isinstance(interp, BatchInterpolator)
        assert not interp.use_gpu
    
    @pytest.mark.skipif(not GPU_AVAILABLE, reason="GPU not available")
    def test_create_batch_interpolator_gpu(self):
        """Test factory creates GPU interpolator."""
        met = create_test_met_data()
        interp = create_batch_interpolator(met, use_gpu=True)
        
        assert isinstance(interp, BatchInterpolator)
        assert interp.use_gpu


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
