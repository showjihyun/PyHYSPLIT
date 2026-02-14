"""Property-based tests for the AdaptiveDtController module.

Properties 6-7 from the HYSPLIT Trajectory Engine design document.
Uses hypothesis for automated input generation (min 100 examples each).
"""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings, assume, strategies as st

from pyhysplit.interpolator import EARTH_RADIUS
from pyhysplit.integrator import AdaptiveDtController
from pyhysplit.models import MetData, SimulationConfig

from datetime import datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_met(
    nx: int = 5, ny: int = 5, nz: int = 4, nt: int = 3,
    lon_range: tuple[float, float] = (100.0, 110.0),
    lat_range: tuple[float, float] = (30.0, 40.0),
    z_range: tuple[float, float] = (0.0, 3000.0),
    t_range: tuple[float, float] = (0.0, 10800.0),
) -> MetData:
    lon_grid = np.linspace(lon_range[0], lon_range[1], nx)
    lat_grid = np.linspace(lat_range[0], lat_range[1], ny)
    z_grid = np.linspace(z_range[0], z_range[1], nz)
    t_grid = np.linspace(t_range[0], t_range[1], nt)
    shape = (nt, nz, ny, nx)
    rng = np.random.default_rng(42)
    return MetData(
        u=rng.uniform(-20, 20, shape),
        v=rng.uniform(-20, 20, shape),
        w=rng.uniform(-5, 5, shape),
        lon_grid=lon_grid, lat_grid=lat_grid,
        z_grid=z_grid, t_grid=t_grid,
    )


def _make_config(dt_max: float = 3600.0) -> SimulationConfig:
    return SimulationConfig(
        start_time=datetime(2024, 1, 1),
        num_start_locations=1,
        start_locations=[],
        total_run_hours=48,
        vertical_motion=0,
        model_top=25000.0,
        met_files=[],
        dt_max=dt_max,
    )


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

wind_component = st.floats(min_value=-100.0, max_value=100.0,
                           allow_nan=False, allow_infinity=False)
vert_wind = st.floats(min_value=-10.0, max_value=10.0,
                      allow_nan=False, allow_infinity=False)
dt_max_st = st.floats(min_value=60.0, max_value=7200.0,
                      allow_nan=False, allow_infinity=False)


# ---------------------------------------------------------------------------
# Property 6: CFL 조건 불변량 (CFL Invariant)
# Validates: Requirements 3.1, 3.3, 3.6
# ---------------------------------------------------------------------------

@given(u=wind_component, v=wind_component, w=vert_wind, dt_max=dt_max_st)
@settings(max_examples=100)
def test_property_6_cfl_invariant(u, v, w, dt_max):
    """**Validates: Requirements 3.1, 3.3, 3.6**

    Feature: hysplit-trajectory-engine, Property 6: CFL 조건 불변량
    compute_dt must return Δt ≤ min(Δx/|u|, Δy/|v|, Δz/|w|, dt_max).
    Even when wind is near zero, Δt must be finite.
    """
    met = _make_met()
    config = _make_config(dt_max=dt_max)
    ctrl = AdaptiveDtController(met, config)

    t = 100.0  # safely inside time range
    dt = ctrl.compute_dt(u, v, w, t)

    # dt must be positive and finite
    assert dt > 0
    assert np.isfinite(dt)

    # dt must not exceed dt_max
    assert dt <= dt_max + 1e-10

    # CFL: dt ≤ dx / max(|u|, 0.001)
    dx, dy = ctrl._dx, ctrl._dy
    speed_u = max(abs(u), 0.001)
    speed_v = max(abs(v), 0.001)
    assert dt <= dx / speed_u + 1e-10
    assert dt <= dy / speed_v + 1e-10

    # Vertical CFL
    if abs(w) > 0.001 and len(met.z_grid) > 1:
        dz = abs(met.z_grid[1] - met.z_grid[0])
        assert dt <= dz / abs(w) + 1e-10


# ---------------------------------------------------------------------------
# Property 7: 시간 경계 클리핑 (Time Boundary Clipping)
# Validates: Requirements 3.4
# ---------------------------------------------------------------------------

@given(
    frac=st.floats(min_value=0.01, max_value=0.99,
                   allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_property_7_time_boundary_clipping(frac):
    """**Validates: Requirements 3.4**

    Feature: hysplit-trajectory-engine, Property 7: 시간 경계 클리핑
    compute_dt must not exceed the distance to the next met-data time
    boundary. t + dt ≤ t_grid[it+1].
    """
    met = _make_met()
    config = _make_config(dt_max=99999.0)  # large dt_max so clipping is the binding constraint
    ctrl = AdaptiveDtController(met, config)

    # Place t between the first two time grid points
    t = met.t_grid[0] + frac * (met.t_grid[1] - met.t_grid[0])

    # Use very small wind so CFL doesn't bind before the time boundary
    dt = ctrl.compute_dt(0.0001, 0.0001, 0.0001, t)

    # dt must not push past the next time boundary
    dt_to_boundary = met.t_grid[1] - t
    assert dt <= dt_to_boundary + 1e-10
