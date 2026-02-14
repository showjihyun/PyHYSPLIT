"""Property-based tests for parallel processing.

Property 31 — validates Requirements 14.1, 14.5.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from pyhysplit.engine import TrajectoryEngine
from pyhysplit.models import MetData, SimulationConfig, StartLocation
from pyhysplit.parallel import ParallelExecutor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_uniform_met(
    u: float, v: float, w: float,
    nx: int = 5, ny: int = 5, nz: int = 3, nt: int = 4,
    lon_range: tuple[float, float] = (-10.0, 10.0),
    lat_range: tuple[float, float] = (30.0, 50.0),
    z_range: tuple[float, float] = (0.0, 5000.0),
    t_span_s: float = 48 * 3600.0,
) -> MetData:
    """Create MetData with spatially and temporally uniform wind."""
    lon_grid = np.linspace(lon_range[0], lon_range[1], nx)
    lat_grid = np.linspace(lat_range[0], lat_range[1], ny)
    z_grid = np.linspace(z_range[0], z_range[1], nz)
    t_grid = np.linspace(0.0, t_span_s, nt)

    shape = (nt, nz, ny, nx)
    return MetData(
        u=np.full(shape, u, dtype=np.float64),
        v=np.full(shape, v, dtype=np.float64),
        w=np.full(shape, w, dtype=np.float64),
        lon_grid=lon_grid,
        lat_grid=lat_grid,
        z_grid=z_grid,
        t_grid=t_grid,
        terrain=np.zeros((ny, nx), dtype=np.float64),
    )


def _make_config(
    start_locations: list[StartLocation],
    total_run_hours: int,
    model_top: float = 10000.0,
) -> SimulationConfig:
    """Create a minimal SimulationConfig with turbulence off."""
    return SimulationConfig(
        start_time=datetime(2024, 1, 1, 0, 0),
        num_start_locations=len(start_locations),
        start_locations=start_locations,
        total_run_hours=total_run_hours,
        vertical_motion=0,
        model_top=model_top,
        met_files=[],
        turbulence_on=False,
        sigma=0.0,
    )


# ---------------------------------------------------------------------------
# Property 31: 병렬/순차 결과 동일성
# ---------------------------------------------------------------------------

@given(
    u=st.floats(min_value=0.5, max_value=5.0, allow_nan=False, allow_infinity=False),
    v=st.floats(min_value=0.5, max_value=5.0, allow_nan=False, allow_infinity=False),
    n_sources=st.integers(min_value=2, max_value=4),
)
@settings(max_examples=100)
def test_property_31_parallel_sequential_equivalence(
    u: float, v: float, n_sources: int,
):
    """**Validates: Requirements 14.1, 14.5**

    Feature: hysplit-trajectory-engine, Property 31: 병렬/순차 결과 동일성
    — Parallel processing (multiprocessing Pool) results must equal
      sequential processing results. Merged results after batch splitting
      must match the original order.
    """
    # Build multiple start locations spread across the grid interior
    locs = [
        StartLocation(lat=35.0 + i * 2.0, lon=-5.0 + i * 2.0, height=500.0)
        for i in range(n_sources)
    ]
    met = _make_uniform_met(u, v, 0.0)
    config = _make_config(locs, total_run_hours=1)

    # Sequential run
    engine = TrajectoryEngine(config, met)
    traj_seq = engine.run(output_interval_s=3600.0)

    # Parallel run (force 2 workers to exercise parallelism)
    executor = ParallelExecutor(num_workers=2)
    traj_par = executor.run_trajectories_parallel(
        config, met, output_interval_s=3600.0,
    )

    # Same number of trajectories
    assert len(traj_seq) == len(traj_par), (
        f"Trajectory count mismatch: seq={len(traj_seq)}, par={len(traj_par)}"
    )

    # Each trajectory must match point-by-point
    for src_idx in range(len(traj_seq)):
        seq = traj_seq[src_idx]
        par = traj_par[src_idx]
        assert len(seq) == len(par), (
            f"Source {src_idx}: point count mismatch seq={len(seq)}, par={len(par)}"
        )
        for pt_idx, (pt_s, pt_p) in enumerate(zip(seq, par)):
            t_s, lon_s, lat_s, z_s = pt_s
            t_p, lon_p, lat_p, z_p = pt_p
            assert abs(t_s - t_p) < 1e-6, (
                f"Source {src_idx}, pt {pt_idx}: time {t_s} vs {t_p}"
            )
            assert abs(lon_s - lon_p) < 1e-10, (
                f"Source {src_idx}, pt {pt_idx}: lon {lon_s} vs {lon_p}"
            )
            assert abs(lat_s - lat_p) < 1e-10, (
                f"Source {src_idx}, pt {pt_idx}: lat {lat_s} vs {lat_p}"
            )
            assert abs(z_s - z_p) < 1e-10, (
                f"Source {src_idx}, pt {pt_idx}: z {z_s} vs {z_p}"
            )



# ---------------------------------------------------------------------------
# Property 32: GPU/CPU 결과 동등성
# ---------------------------------------------------------------------------

from pyhysplit.gpu_backend import NumpyBackend, get_backend
from pyhysplit.interpolator import Interpolator
from pyhysplit.integrator import HeunIntegrator


def _make_random_met(seed: int, nx: int = 5, ny: int = 5, nz: int = 3, nt: int = 3) -> MetData:
    """Create MetData with random but smooth wind fields."""
    rng = np.random.default_rng(seed)
    lon_grid = np.linspace(-10.0, 10.0, nx)
    lat_grid = np.linspace(30.0, 50.0, ny)
    z_grid = np.linspace(0.0, 5000.0, nz)
    t_grid = np.linspace(0.0, 24 * 3600.0, nt)

    shape = (nt, nz, ny, nx)
    return MetData(
        u=rng.uniform(-5, 5, shape).astype(np.float64),
        v=rng.uniform(-5, 5, shape).astype(np.float64),
        w=rng.uniform(-0.5, 0.5, shape).astype(np.float64),
        lon_grid=lon_grid,
        lat_grid=lat_grid,
        z_grid=z_grid,
        t_grid=t_grid,
        terrain=np.zeros((ny, nx), dtype=np.float64),
    )


@given(
    n_particles=st.integers(min_value=1, max_value=20),
    seed=st.integers(min_value=0, max_value=10000),
)
@settings(max_examples=100)
def test_property_32_gpu_cpu_equivalence_trilinear(
    n_particles: int, seed: int,
):
    """**Validates: Requirements 15.1, 15.2, 15.5**

    Feature: hysplit-trajectory-engine, Property 32: GPU/CPU 결과 동등성
    — The NumpyBackend (CPU fallback) trilinear_batch must produce results
      matching the scalar Interpolator.trilinear within 1e-6 tolerance.
    """
    met = _make_random_met(seed)
    rng = np.random.default_rng(seed + 1)

    # Generate random positions inside the grid
    lons = rng.uniform(met.lon_grid[0], met.lon_grid[-1], n_particles)
    lats = rng.uniform(met.lat_grid[0], met.lat_grid[-1], n_particles)
    zs = rng.uniform(met.z_grid[0], met.z_grid[-1], n_particles)

    backend = NumpyBackend()
    interp = Interpolator(met)

    # Test against first time snapshot of u field
    var_3d = met.u[0]
    batch_result = backend.trilinear_batch(
        var_3d, lons, lats, zs,
        met.lon_grid, met.lat_grid, met.z_grid,
    )

    for i in range(n_particles):
        scalar_result = interp.trilinear(var_3d, lons[i], lats[i], zs[i])
        assert abs(batch_result[i] - scalar_result) < 1e-6, (
            f"Particle {i}: batch={batch_result[i]}, scalar={scalar_result}"
        )


@given(
    n_particles=st.integers(min_value=1, max_value=10),
    seed=st.integers(min_value=0, max_value=10000),
    dt=st.floats(min_value=60.0, max_value=600.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_property_32_gpu_cpu_equivalence_heun(
    n_particles: int, seed: int, dt: float,
):
    """**Validates: Requirements 15.1, 15.2, 15.5**

    Feature: hysplit-trajectory-engine, Property 32: GPU/CPU 결과 동등성
    — The NumpyBackend (CPU fallback) heun_step_batch must produce results
      matching the scalar HeunIntegrator.step within 1e-6 tolerance.
    """
    met = _make_random_met(seed)
    rng = np.random.default_rng(seed + 2)

    # Positions well inside the grid to avoid boundary issues after advection
    margin_lon = 0.3 * (met.lon_grid[-1] - met.lon_grid[0])
    margin_lat = 0.3 * (met.lat_grid[-1] - met.lat_grid[0])
    margin_z = 0.3 * (met.z_grid[-1] - met.z_grid[0])

    lons = rng.uniform(met.lon_grid[0] + margin_lon, met.lon_grid[-1] - margin_lon, n_particles)
    lats = rng.uniform(met.lat_grid[0] + margin_lat, met.lat_grid[-1] - margin_lat, n_particles)
    zs = rng.uniform(met.z_grid[0] + margin_z, met.z_grid[-1] - margin_z, n_particles)

    t = met.t_grid[0] + 0.5 * (met.t_grid[1] - met.t_grid[0])

    backend = NumpyBackend()
    interp = Interpolator(met)
    heun = HeunIntegrator(interp)

    batch_lons, batch_lats, batch_zs = backend.heun_step_batch(
        lons, lats, zs, t, dt, met,
    )

    for i in range(n_particles):
        s_lon, s_lat, s_z = heun.step(lons[i], lats[i], zs[i], t, dt)
        assert abs(batch_lons[i] - s_lon) < 1e-6, (
            f"Particle {i}: batch lon={batch_lons[i]}, scalar lon={s_lon}"
        )
        assert abs(batch_lats[i] - s_lat) < 1e-6, (
            f"Particle {i}: batch lat={batch_lats[i]}, scalar lat={s_lat}"
        )
        assert abs(batch_zs[i] - s_z) < 1e-6, (
            f"Particle {i}: batch z={batch_zs[i]}, scalar z={s_z}"
        )
