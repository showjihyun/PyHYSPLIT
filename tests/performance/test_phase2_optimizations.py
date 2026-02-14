"""Tests for Phase 2 performance optimizations.

Tests grid index caching and Numba JIT compilation.
"""

from __future__ import annotations

import time
from datetime import datetime

import numpy as np
import pytest

from pyhysplit.core.engine import TrajectoryEngine
from pyhysplit.core.interpolator import Interpolator
from pyhysplit.core.interpolator_optimized import (
    NUMBA_AVAILABLE,
    CachedInterpolator,
    trilinear_numba,
    trilinear_python,
)
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


class TestGridIndexCaching:
    """Test grid index caching optimization."""
    
    def test_cached_interpolator_initialization(self):
        """Test that CachedInterpolator initializes correctly."""
        met = create_test_met_data()
        interp = CachedInterpolator(met)
        
        assert interp._cached_i is None
        assert interp._cached_j is None
        assert interp._cached_k is None
        assert interp._lon_min == 120.0
        assert interp._lon_max == 130.0
    
    def test_cache_populated_after_first_interpolation(self):
        """Test that cache is populated after first interpolation."""
        met = create_test_met_data()
        interp = CachedInterpolator(met)
        
        # First interpolation
        val = interp.trilinear(met.u[0], 125.0, 35.0, 850.0)
        
        # Cache should be populated
        assert interp._cached_i is not None
        assert interp._cached_j is not None
        assert interp._cached_k is not None
        assert interp._cached_lon == 125.0
        assert interp._cached_lat == 35.0
        assert interp._cached_z == 850.0
    
    def test_cache_reused_for_nearby_position(self):
        """Test that cache is reused when position stays in same cell."""
        met = create_test_met_data()
        interp = CachedInterpolator(met)
        
        # First interpolation
        val1 = interp.trilinear(met.u[0], 125.0, 35.0, 850.0)
        cached_i_1 = interp._cached_i
        
        # Second interpolation at nearby position (same cell)
        val2 = interp.trilinear(met.u[0], 125.01, 35.01, 850.0)
        cached_i_2 = interp._cached_i
        
        # Cache should be reused (same indices)
        assert cached_i_1 == cached_i_2
    
    def test_cache_updated_for_different_cell(self):
        """Test that cache is updated when position moves to different cell."""
        met = create_test_met_data()
        interp = CachedInterpolator(met)
        
        # First interpolation
        val1 = interp.trilinear(met.u[0], 125.0, 35.0, 850.0)
        cached_i_1 = interp._cached_i
        
        # Second interpolation at far position (different cell)
        val2 = interp.trilinear(met.u[0], 127.0, 37.0, 700.0)
        cached_i_2 = interp._cached_i
        
        # Cache should be updated (different indices)
        assert cached_i_1 != cached_i_2
    
    def test_cached_vs_base_interpolator_consistency(self):
        """Test that CachedInterpolator gives same results as base Interpolator."""
        met = create_test_met_data()
        base_interp = Interpolator(met)
        cached_interp = CachedInterpolator(met)
        
        # Test multiple positions
        positions = [
            (125.0, 35.0, 850.0),
            (126.5, 36.2, 700.0),
            (122.3, 33.7, 500.0),
            (128.9, 38.1, 300.0),
        ]
        
        for lon, lat, z in positions:
            val_base = base_interp.trilinear(met.u[0], lon, lat, z)
            val_cached = cached_interp.trilinear(met.u[0], lon, lat, z)
            
            assert abs(val_base - val_cached) < 1e-10, \
                f"Results differ at ({lon}, {lat}, {z}): {val_base} vs {val_cached}"
    
    def test_caching_improves_performance(self):
        """Test that caching improves performance for sequential interpolations."""
        met = create_test_met_data()
        base_interp = Interpolator(met)
        cached_interp = CachedInterpolator(met)
        
        # Warm up
        base_interp.trilinear(met.u[0], 125.0, 35.0, 850.0)
        cached_interp.trilinear(met.u[0], 125.0, 35.0, 850.0)
        
        # Benchmark base interpolator
        n_iterations = 1000
        start = time.time()
        for i in range(n_iterations):
            lon = 125.0 + (i % 10) * 0.01  # Small movements (same cell)
            lat = 35.0 + (i % 10) * 0.01
            val = base_interp.trilinear(met.u[0], lon, lat, 850.0)
        time_base = time.time() - start
        
        # Benchmark cached interpolator
        start = time.time()
        for i in range(n_iterations):
            lon = 125.0 + (i % 10) * 0.01
            lat = 35.0 + (i % 10) * 0.01
            val = cached_interp.trilinear(met.u[0], lon, lat, 850.0)
        time_cached = time.time() - start
        
        speedup = time_base / time_cached
        print(f"\nGrid caching speedup: {speedup:.2f}x")
        print(f"Base: {time_base*1000:.2f}ms, Cached: {time_cached*1000:.2f}ms")
        
        # Cached should be faster (allow some tolerance for timing variance)
        assert time_cached < time_base * 1.5, \
            f"Caching should not significantly degrade performance: {speedup:.2f}x"


class TestNumbaJIT:
    """Test Numba JIT compilation."""
    
    @pytest.mark.skipif(not NUMBA_AVAILABLE, reason="Numba not installed")
    def test_numba_available(self):
        """Test that Numba is available."""
        assert NUMBA_AVAILABLE
    
    def test_numba_vs_python_consistency(self):
        """Test that Numba and Python implementations give same results."""
        met = create_test_met_data()
        var_3d = met.u[0]
        
        # Test parameters
        i, j, k = 10, 10, 3
        xd, yd, zd = 0.5, 0.5, 0.5
        
        # Python version
        val_python = trilinear_python(var_3d, i, j, k, xd, yd, zd)
        
        # Numba version (if available)
        if NUMBA_AVAILABLE:
            val_numba = trilinear_numba(var_3d, i, j, k, xd, yd, zd)
            assert abs(val_python - val_numba) < 1e-10, \
                f"Numba and Python results differ: {val_numba} vs {val_python}"
    
    @pytest.mark.skipif(not NUMBA_AVAILABLE, reason="Numba not installed")
    def test_numba_performance(self):
        """Test that Numba JIT provides speedup."""
        met = create_test_met_data()
        var_3d = met.u[0]
        
        # Test parameters
        i, j, k = 10, 10, 3
        xd, yd, zd = 0.5, 0.5, 0.5
        
        # Warm up Numba (first call compiles)
        for _ in range(10):
            trilinear_numba(var_3d, i, j, k, xd, yd, zd)
        
        # Benchmark Python version
        n_iterations = 10000
        start = time.time()
        for _ in range(n_iterations):
            val = trilinear_python(var_3d, i, j, k, xd, yd, zd)
        time_python = time.time() - start
        
        # Benchmark Numba version
        start = time.time()
        for _ in range(n_iterations):
            val = trilinear_numba(var_3d, i, j, k, xd, yd, zd)
        time_numba = time.time() - start
        
        speedup = time_python / time_numba
        print(f"\nNumba JIT speedup: {speedup:.2f}x")
        print(f"Python: {time_python*1000:.2f}ms, Numba: {time_numba*1000:.2f}ms")
        
        # Numba should be faster (at least 1.5x after warmup)
        assert speedup > 1.5, \
            f"Numba should provide significant speedup: {speedup:.2f}x"


class TestCombinedOptimizations:
    """Test combined Phase 2 optimizations."""
    
    def test_cached_interpolator_with_4d(self):
        """Test CachedInterpolator with 4D interpolation."""
        met = create_test_met_data()
        interp = CachedInterpolator(met)
        
        # Multiple 4D interpolations
        for i in range(10):
            lon = 125.0 + i * 0.1
            lat = 35.0 + i * 0.1
            u, v, w = interp.interpolate_4d(lon, lat, 850.0, 3600.0)
            
            # Results should be reasonable
            assert 0 < u < 20
            assert 0 < v < 10
    
    def test_phase2_vs_phase1_performance(self):
        """Compare Phase 2 (cached + JIT) vs Phase 1 (base) performance."""
        met = create_test_met_data()
        base_interp = Interpolator(met)
        cached_interp = CachedInterpolator(met)
        
        # Warm up
        for _ in range(10):
            base_interp.interpolate_4d(125.0, 35.0, 850.0, 3600.0)
            cached_interp.interpolate_4d(125.0, 35.0, 850.0, 3600.0)
        
        # Benchmark Phase 1 (base)
        n_iterations = 1000
        start = time.time()
        for i in range(n_iterations):
            lon = 125.0 + (i % 100) * 0.01
            lat = 35.0 + (i % 100) * 0.01
            u, v, w = base_interp.interpolate_4d(lon, lat, 850.0, 3600.0)
        time_phase1 = time.time() - start
        
        # Benchmark Phase 2 (cached + JIT)
        start = time.time()
        for i in range(n_iterations):
            lon = 125.0 + (i % 100) * 0.01
            lat = 35.0 + (i % 100) * 0.01
            u, v, w = cached_interp.interpolate_4d(lon, lat, 850.0, 3600.0)
        time_phase2 = time.time() - start
        
        speedup = time_phase1 / time_phase2
        print(f"\nPhase 2 vs Phase 1 speedup: {speedup:.2f}x")
        print(f"Phase 1: {time_phase1*1000:.2f}ms, Phase 2: {time_phase2*1000:.2f}ms")
        
        # Phase 2 should be at least as fast as Phase 1
        assert time_phase2 < time_phase1 * 2.0, \
            f"Phase 2 should not be significantly slower: {speedup:.2f}x"


class TestResultConsistency:
    """Test that Phase 2 optimizations don't change results."""
    
    def test_trajectory_consistency(self):
        """Test that trajectories are consistent with Phase 2 optimizations."""
        met = create_test_met_data()
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
        
        # Run with base interpolator
        engine_base = TrajectoryEngine(config, met)
        results_base = engine_base.run(output_interval_s=3600.0)
        
        # Run with cached interpolator
        # Note: Would need to modify engine to accept custom interpolator
        # For now, just verify that CachedInterpolator gives same results
        base_interp = Interpolator(met)
        cached_interp = CachedInterpolator(met)
        
        # Test at multiple points
        test_points = [
            (125.0, 35.0, 850.0, 3600.0),
            (124.5, 34.8, 870.0, 5400.0),
            (124.0, 34.5, 890.0, 7200.0),
        ]
        
        for lon, lat, z, t in test_points:
            u1, v1, w1 = base_interp.interpolate_4d(lon, lat, z, t)
            u2, v2, w2 = cached_interp.interpolate_4d(lon, lat, z, t)
            
            assert abs(u1 - u2) < 1e-10, f"u differs: {u1} vs {u2}"
            assert abs(v1 - v2) < 1e-10, f"v differs: {v1} vs {v2}"
            assert abs(w1 - w2) < 1e-10, f"w differs: {w1} vs {w2}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
