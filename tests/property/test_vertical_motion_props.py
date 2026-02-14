"""Property-based tests for the VerticalMotionHandler module.

Properties 34-35 from the HYSPLIT Trajectory Engine design document.
"""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings, strategies as st

from pyhysplit.interpolator import Interpolator
from pyhysplit.models import MetData
from pyhysplit.vertical_motion import VerticalMotionHandler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_met(
    nx: int = 5, ny: int = 5, nz: int = 4, nt: int = 3,
    lon_range: tuple[float, float] = (100.0, 110.0),
    lat_range: tuple[float, float] = (30.0, 40.0),
    z_range: tuple[float, float] = (0.0, 3000.0),
    t_range: tuple[float, float] = (0.0, 10800.0),
    fill_value: float | None = None,
    include_temperature: bool = False,
) -> MetData:
    """Create a small MetData for testing."""
    lon_grid = np.linspace(lon_range[0], lon_range[1], nx)
    lat_grid = np.linspace(lat_range[0], lat_range[1], ny)
    z_grid = np.linspace(z_range[0], z_range[1], nz)
    t_grid = np.linspace(t_range[0], t_range[1], nt)

    shape = (nt, nz, ny, nx)
    rng = np.random.default_rng(42)

    if fill_value is not None:
        u = np.full(shape, fill_value)
        v = np.full(shape, fill_value)
        w = np.full(shape, fill_value)
    else:
        u = rng.uniform(-20, 20, shape)
        v = rng.uniform(-20, 20, shape)
        w = rng.uniform(-20, 20, shape)

    t_field = None
    if include_temperature:
        # Temperature decreasing with height (lapse rate ~6.5 K/km)
        t_field = np.zeros(shape)
        for k in range(nz):
            t_field[:, k, :, :] = 288.0 - 6.5e-3 * z_grid[k]

    return MetData(
        u=u, v=v, w=w,
        t_field=t_field,
        lon_grid=lon_grid, lat_grid=lat_grid,
        z_grid=z_grid, t_grid=t_grid,
    )


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Fractional position inside the grid interior
frac = st.floats(min_value=0.1, max_value=0.9,
                 allow_nan=False, allow_infinity=False)

# Time fraction within the met data time range
t_frac = st.floats(min_value=0.05, max_value=0.95,
                   allow_nan=False, allow_infinity=False)


# ---------------------------------------------------------------------------
# Property 34: 등압면 수직 속도 영 (Isobaric Zero Vertical Velocity)
# Validates: Requirements 17.3
# ---------------------------------------------------------------------------

@given(fx=frac, fy=frac, fz=frac, ft=t_frac)
@settings(max_examples=100)
def test_property_34_isobaric_zero_vertical_velocity(fx, fy, fz, ft):
    """**Validates: Requirements 17.3**

    Feature: hysplit-trajectory-engine, Property 34: 등압면 수직 속도 영
    When vertical motion mode is 2 (isobaric), get_vertical_velocity
    must return exactly 0.0 for any position and time.
    """
    met = _make_met()
    interp = Interpolator(met)
    handler = VerticalMotionHandler(mode=2, interpolator=interp)

    lon = met.lon_grid[0] + fx * (met.lon_grid[-1] - met.lon_grid[0])
    lat = met.lat_grid[0] + fy * (met.lat_grid[-1] - met.lat_grid[0])
    z = met.z_grid[0] + fz * (met.z_grid[-1] - met.z_grid[0])
    t = met.t_grid[0] + ft * (met.t_grid[-1] - met.t_grid[0])

    w = handler.get_vertical_velocity(lon, lat, z, t)

    assert w == 0.0, f"Isobaric mode should return w=0, got {w}"


# ---------------------------------------------------------------------------
# Property 35: 등온위면 온위 보존 (Isentropic θ Conservation)
# Validates: Requirements 17.4
# ---------------------------------------------------------------------------

@given(fx=frac, fy=frac, fz=frac, ft=t_frac)
@settings(max_examples=100)
def test_property_35_isentropic_theta_conservation(fx, fy, fz, ft):
    """**Validates: Requirements 17.4**

    Feature: hysplit-trajectory-engine, Property 35: 등온위면 온위 보존
    In isentropic mode (mode=3), the vertical velocity returned should
    be such that potential temperature is conserved. In the absence of
    diabatic forcing, this means w = 0 on an isentropic surface.
    """
    met = _make_met(include_temperature=True)
    interp = Interpolator(met)
    handler = VerticalMotionHandler(mode=3, interpolator=interp)

    lon = met.lon_grid[0] + fx * (met.lon_grid[-1] - met.lon_grid[0])
    lat = met.lat_grid[0] + fy * (met.lat_grid[-1] - met.lat_grid[0])
    z = met.z_grid[0] + fz * (met.z_grid[-1] - met.z_grid[0])
    t = met.t_grid[0] + ft * (met.t_grid[-1] - met.t_grid[0])

    w = handler.get_vertical_velocity(lon, lat, z, t)

    # In the adiabatic case (no diabatic heating), isentropic w = 0
    # because θ is already conserved without vertical displacement.
    assert w == 0.0, (
        f"Isentropic mode without diabatic forcing should return w=0, got {w}"
    )
