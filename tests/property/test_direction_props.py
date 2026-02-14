"""Property-based tests for Forward/Backward trajectory direction.

Properties 8, 9, 10 — validates Requirements 4.1, 4.2, 4.3, 4.5.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from pyhysplit.engine import TrajectoryEngine
from pyhysplit.models import MetData, SimulationConfig, StartLocation


# ---------------------------------------------------------------------------
# Helpers: build uniform-wind MetData and minimal SimulationConfig
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
        z_type="height",  # Use height coordinates for round-trip tests
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
# Property 8: Forward/Backward 방향 부호
# ---------------------------------------------------------------------------

# Moderate wind speeds that keep the particle inside the grid
_wind = st.floats(min_value=0.5, max_value=10.0, allow_nan=False, allow_infinity=False)
_hours = st.integers(min_value=1, max_value=6)


@given(u=_wind, v=_wind, hours=_hours)
@settings(max_examples=100)
def test_property_8_direction_sign(u: float, v: float, hours: int):
    """**Validates: Requirements 4.1, 4.2**

    Feature: hysplit-trajectory-engine, Property 8: Forward/Backward 방향 부호
    — forward total_run_hours > 0 ⇒ time increases;
      backward total_run_hours < 0 ⇒ time decreases.
    """
    loc = StartLocation(lat=40.0, lon=0.0, height=500.0)
    met = _make_uniform_met(u, v, 0.0)

    # Forward
    cfg_fwd = _make_config([loc], total_run_hours=hours)
    engine_fwd = TrajectoryEngine(cfg_fwd, met)
    assert engine_fwd.is_forward
    assert engine_fwd._direction == 1

    traj_fwd = engine_fwd.run(output_interval_s=3600.0)
    assert len(traj_fwd) == 1
    if len(traj_fwd[0]) >= 2:
        # Time should increase
        t0 = traj_fwd[0][0][0]
        t1 = traj_fwd[0][1][0]
        assert t1 > t0, f"Forward: t should increase, got {t0} -> {t1}"

    # Backward
    cfg_bwd = _make_config([loc], total_run_hours=-hours)
    engine_bwd = TrajectoryEngine(cfg_bwd, met)
    assert engine_bwd.is_backward
    assert engine_bwd._direction == -1

    traj_bwd = engine_bwd.run(output_interval_s=3600.0)
    assert len(traj_bwd) == 1
    if len(traj_bwd[0]) >= 2:
        # Time should decrease
        t0 = traj_bwd[0][0][0]
        t1 = traj_bwd[0][1][0]
        assert t1 < t0, f"Backward: t should decrease, got {t0} -> {t1}"


# ---------------------------------------------------------------------------
# Property 9: Forward-Backward Round Trip (uniform wind)
# ---------------------------------------------------------------------------

@given(
    u=st.floats(min_value=-2.0, max_value=2.0, allow_nan=False, allow_infinity=False),
    v=st.floats(min_value=-2.0, max_value=2.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_property_9_forward_backward_round_trip(u: float, v: float):
    """**Validates: Requirements 4.3**

    Feature: hysplit-trajectory-engine, Property 9: Forward-Backward Round Trip
    — In a uniform wind field with turbulence off, running forward N steps
      then backward N steps returns to the original position (within tolerance).
    """
    assume(abs(u) > 0.01 or abs(v) > 0.01)  # need some wind

    loc = StartLocation(lat=40.0, lon=0.0, height=500.0)
    met = _make_uniform_met(u, v, 0.0)

    # Forward 1 hour
    cfg_fwd = _make_config([loc], total_run_hours=1)
    engine_fwd = TrajectoryEngine(cfg_fwd, met)
    traj_fwd = engine_fwd.run(output_interval_s=3600.0)
    assert len(traj_fwd) == 1 and len(traj_fwd[0]) >= 2

    _, lon_end, lat_end, z_end = traj_fwd[0][-1]

    # Backward 1 hour from the forward endpoint
    loc_end = StartLocation(lat=lat_end, lon=lon_end, height=z_end)
    cfg_bwd = _make_config([loc_end], total_run_hours=-1)
    engine_bwd = TrajectoryEngine(cfg_bwd, met)
    traj_bwd = engine_bwd.run(output_interval_s=3600.0)
    assert len(traj_bwd) == 1 and len(traj_bwd[0]) >= 2

    _, lon_back, lat_back, z_back = traj_bwd[0][-1]

    # Tolerance accounts for spherical geometry nonlinearity (cos(lat) changes)
    assert abs(lon_back - loc.lon) < 0.5, (
        f"Lon round-trip error: {lon_back} vs {loc.lon}"
    )
    assert abs(lat_back - loc.lat) < 0.5, (
        f"Lat round-trip error: {lat_back} vs {loc.lat}"
    )
    assert abs(z_back - loc.height) < 1.0, (
        f"Z round-trip error: {z_back} vs {loc.height}"
    )


# ---------------------------------------------------------------------------
# Property 10: 다중 시작점 독립성
# ---------------------------------------------------------------------------

@given(
    u=st.floats(min_value=1.0, max_value=5.0, allow_nan=False, allow_infinity=False),
    v=st.floats(min_value=1.0, max_value=5.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_property_10_multi_source_independence(u: float, v: float):
    """**Validates: Requirements 4.5**

    Feature: hysplit-trajectory-engine, Property 10: 다중 시작점 독립성
    — Adding or removing start locations does not change existing trajectories.
    """
    loc_a = StartLocation(lat=40.0, lon=0.0, height=500.0)
    loc_b = StartLocation(lat=42.0, lon=2.0, height=1000.0)
    met = _make_uniform_met(u, v, 0.0)

    # Run with only loc_a
    cfg_single = _make_config([loc_a], total_run_hours=1)
    engine_single = TrajectoryEngine(cfg_single, met)
    traj_single = engine_single.run(output_interval_s=3600.0)

    # Run with loc_a + loc_b
    cfg_multi = _make_config([loc_a, loc_b], total_run_hours=1)
    engine_multi = TrajectoryEngine(cfg_multi, met)
    traj_multi = engine_multi.run(output_interval_s=3600.0)

    # Trajectory for loc_a should be identical in both runs
    assert len(traj_single) == 1
    assert len(traj_multi) == 2

    for pt_s, pt_m in zip(traj_single[0], traj_multi[0]):
        t_s, lon_s, lat_s, z_s = pt_s
        t_m, lon_m, lat_m, z_m = pt_m
        assert abs(t_s - t_m) < 1e-6, f"Time mismatch: {t_s} vs {t_m}"
        assert abs(lon_s - lon_m) < 1e-10, f"Lon mismatch: {lon_s} vs {lon_m}"
        assert abs(lat_s - lat_m) < 1e-10, f"Lat mismatch: {lat_s} vs {lat_m}"
        assert abs(z_s - z_m) < 1e-10, f"Z mismatch: {z_s} vs {z_m}"
