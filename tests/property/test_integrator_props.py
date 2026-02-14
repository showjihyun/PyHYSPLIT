"""Property-based tests for the HeunIntegrator module.

Properties 4-5 from the HYSPLIT Trajectory Engine design document.
Uses hypothesis for automated input generation (min 100 examples each).
"""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings, assume, strategies as st

from pyhysplit.interpolator import EARTH_RADIUS, Interpolator
from pyhysplit.integrator import HeunIntegrator
from pyhysplit.models import MetData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_uniform_met(
    u_val: float, v_val: float, w_val: float,
    nx: int = 5, ny: int = 5, nz: int = 4, nt: int = 3,
    lon_range: tuple[float, float] = (100.0, 110.0),
    lat_range: tuple[float, float] = (30.0, 40.0),
    z_range: tuple[float, float] = (0.0, 3000.0),
    t_range: tuple[float, float] = (0.0, 10800.0),
) -> MetData:
    """Create MetData with spatiotemporally uniform wind field."""
    lon_grid = np.linspace(lon_range[0], lon_range[1], nx)
    lat_grid = np.linspace(lat_range[0], lat_range[1], ny)
    z_grid = np.linspace(z_range[0], z_range[1], nz)
    t_grid = np.linspace(t_range[0], t_range[1], nt)

    shape = (nt, nz, ny, nx)
    return MetData(
        u=np.full(shape, u_val),
        v=np.full(shape, v_val),
        w=np.full(shape, w_val),
        lon_grid=lon_grid, lat_grid=lat_grid,
        
        z_grid=z_grid, t_grid=t_grid,
    )


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Wind components — moderate range to keep positions inside the grid
wind_component = st.floats(min_value=-20.0, max_value=20.0,
                           allow_nan=False, allow_infinity=False)

# Small dt so the particle stays inside the grid
small_dt = st.floats(min_value=1.0, max_value=300.0,
                     allow_nan=False, allow_infinity=False)


# ---------------------------------------------------------------------------
# Property 4: 균일 풍속장 Heun 정확성 (Heun Uniform Wind Exactness)
# Validates: Requirements 2.1, 2.2
# ---------------------------------------------------------------------------

@given(
    u_val=wind_component,
    v_val=wind_component,
    w_val=st.floats(min_value=-5.0, max_value=5.0,
                    allow_nan=False, allow_infinity=False),
    dt=small_dt,
)
@settings(max_examples=100)
def test_property_4_heun_uniform_wind_exactness(u_val, v_val, w_val, dt):
    """**Validates: Requirements 2.1, 2.2**

    Feature: hysplit-trajectory-engine, Property 4: 균일 풍속장 Heun 정확성
    In a spatiotemporally uniform wind field, Heun integration must equal
    simple Euler integration because V1 == V2, so avg == V1.
    """
    # Skip near-zero wind to avoid trivial cases
    assume(abs(u_val) > 0.01 or abs(v_val) > 0.01 or abs(w_val) > 0.01)

    met = _make_uniform_met(u_val, v_val, w_val)
    interp = Interpolator(met)
    integrator = HeunIntegrator(interp, turbulence=None)

    # Start at grid centre to stay well inside bounds
    lon0 = float(np.mean(met.lon_grid))
    lat0 = float(np.mean(met.lat_grid))
    z0 = float(np.mean(met.z_grid))
    t0 = float(met.t_grid[0]) + 100.0  # safely inside time range

    # Ensure t0 + dt is within time range
    assume(t0 + dt < met.t_grid[-1])

    # Heun step
    lon_h, lat_h, z_h = integrator.step(lon0, lat0, z0, t0, dt)

    # Euler step (direct formula)
    lon_e, lat_e = HeunIntegrator.advect_lonlat(lon0, lat0, u_val, v_val, dt)
    z_e = z0 + w_val * dt

    np.testing.assert_allclose(lon_h, lon_e, atol=1e-10)
    np.testing.assert_allclose(lat_h, lat_e, atol=1e-10)
    np.testing.assert_allclose(z_h, z_e, atol=1e-10)


# ---------------------------------------------------------------------------
# Property 5: 지구 곡률 이동 공식 (Spherical Advection Formula)
# Validates: Requirements 2.3, 2.4
# ---------------------------------------------------------------------------

@given(
    lon=st.floats(min_value=-170.0, max_value=170.0,
                  allow_nan=False, allow_infinity=False),
    lat=st.floats(min_value=-80.0, max_value=80.0,
                  allow_nan=False, allow_infinity=False),
    u=wind_component,
    v=wind_component,
    dt=small_dt,
)
@settings(max_examples=100)
def test_property_5_spherical_advection_formula(lon, lat, u, v, dt):
    """**Validates: Requirements 2.3, 2.4**

    Feature: hysplit-trajectory-engine, Property 5: 지구 곡률 이동 공식
    advect_lonlat must apply:
        Δlat = (v * dt) / R
        Δlon = (u * dt) / (R * cos(lat))
    Higher latitudes must produce larger |Δlon| for the same u.
    """
    new_lon, new_lat = HeunIntegrator.advect_lonlat(lon, lat, u, v, dt)

    # Verify the formula directly
    lat_rad = np.deg2rad(lat)
    cos_lat = np.cos(lat_rad)
    if abs(cos_lat) < 1e-10:
        cos_lat = 1e-10

    expected_dlat = np.rad2deg((v * dt) / EARTH_RADIUS)
    expected_dlon = np.rad2deg((u * dt) / (EARTH_RADIUS * cos_lat))

    np.testing.assert_allclose(new_lat - lat, expected_dlat, atol=1e-10)
    np.testing.assert_allclose(new_lon - lon, expected_dlon, atol=1e-10)


@given(
    u=st.floats(min_value=1.0, max_value=20.0,
                allow_nan=False, allow_infinity=False),
    dt=small_dt,
)
@settings(max_examples=100)
def test_property_5_higher_latitude_larger_dlon(u, dt):
    """**Validates: Requirements 2.3, 2.4**

    Feature: hysplit-trajectory-engine, Property 5: 지구 곡률 이동 공식
    For the same eastward wind u > 0, higher latitude produces larger |Δlon|.
    """
    lat_low = 10.0
    lat_high = 60.0

    _, _ = HeunIntegrator.advect_lonlat(0.0, lat_low, u, 0.0, dt)
    dlon_low = HeunIntegrator.advect_lonlat(0.0, lat_low, u, 0.0, dt)[0]

    dlon_high = HeunIntegrator.advect_lonlat(0.0, lat_high, u, 0.0, dt)[0]

    # Higher latitude → larger Δlon (cos(lat) is smaller)
    assert abs(dlon_high) > abs(dlon_low)
