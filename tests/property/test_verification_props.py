"""Property-based test for deterministic reproducibility.

Property 33 — validates Requirement 16.2.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from pyhysplit.engine import TrajectoryEngine
from pyhysplit.models import MetData, SimulationConfig, StartLocation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_met(
    u: float, v: float, w: float,
    nx: int = 5, ny: int = 5, nz: int = 3, nt: int = 4,
) -> MetData:
    """Create MetData with uniform wind."""
    lon_grid = np.linspace(-10.0, 10.0, nx)
    lat_grid = np.linspace(30.0, 50.0, ny)
    z_grid = np.linspace(0.0, 5000.0, nz)
    t_grid = np.linspace(0.0, 48 * 3600.0, nt)

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
) -> SimulationConfig:
    return SimulationConfig(
        start_time=datetime(2024, 1, 1, 0, 0),
        num_start_locations=len(start_locations),
        start_locations=start_locations,
        total_run_hours=total_run_hours,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[],
        turbulence_on=False,
        sigma=0.0,
    )


# ---------------------------------------------------------------------------
# Property 33: 결정론적 재현성
# ---------------------------------------------------------------------------

@given(
    u=st.floats(min_value=-5.0, max_value=5.0, allow_nan=False, allow_infinity=False),
    v=st.floats(min_value=-5.0, max_value=5.0, allow_nan=False, allow_infinity=False),
    w=st.floats(min_value=-0.1, max_value=0.1, allow_nan=False, allow_infinity=False),
    hours=st.integers(min_value=1, max_value=6),
)
@settings(max_examples=100)
def test_property_33_deterministic_reproducibility(
    u: float, v: float, w: float, hours: int,
):
    """**Validates: Requirements 16.2**

    Feature: hysplit-trajectory-engine, Property 33: 결정론적 재현성
    — With identical inputs and turbulence off, two runs produce
      exactly identical trajectories.
    """
    assume(abs(u) > 0.01 or abs(v) > 0.01)

    loc = StartLocation(lat=40.0, lon=0.0, height=500.0)
    met = _make_met(u, v, w)
    cfg = _make_config([loc], total_run_hours=hours)

    # Run 1
    engine1 = TrajectoryEngine(cfg, met)
    traj1 = engine1.run(output_interval_s=3600.0)

    # Run 2 — fresh engine, same inputs
    engine2 = TrajectoryEngine(cfg, met)
    traj2 = engine2.run(output_interval_s=3600.0)

    # Must be identical
    assert len(traj1) == len(traj2)
    for t1_list, t2_list in zip(traj1, traj2):
        assert len(t1_list) == len(t2_list), (
            f"Trajectory length mismatch: {len(t1_list)} vs {len(t2_list)}"
        )
        for pt1, pt2 in zip(t1_list, t2_list):
            t1, lon1, lat1, z1 = pt1
            t2, lon2, lat2, z2 = pt2
            assert t1 == t2, f"Time mismatch: {t1} vs {t2}"
            assert lon1 == lon2, f"Lon mismatch: {lon1} vs {lon2}"
            assert lat1 == lat2, f"Lat mismatch: {lat1} vs {lat2}"
            assert z1 == z2, f"Z mismatch: {z1} vs {z2}"
