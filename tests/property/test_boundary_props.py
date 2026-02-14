"""Property-based tests for the BoundaryHandler.

Properties 29-30 from the HYSPLIT Trajectory Engine design document.
"""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings, assume, strategies as st

from pyhysplit.boundary import BoundaryHandler, _normalize_lon, _normalize_lat
from pyhysplit.models import MetData, SimulationConfig, StartLocation
from datetime import datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_handler(
    lon_range: tuple[float, float] = (-180.0, 180.0),
    lat_range: tuple[float, float] = (-90.0, 90.0),
    model_top: float = 25000.0,
) -> BoundaryHandler:
    """Create a BoundaryHandler with a simple met grid."""
    met = MetData(
        u=np.zeros((2, 2, 2, 2)),
        v=np.zeros((2, 2, 2, 2)),
        w=np.zeros((2, 2, 2, 2)),
        lon_grid=np.array([lon_range[0], lon_range[1]]),
        lat_grid=np.array([lat_range[0], lat_range[1]]),
        z_grid=np.array([0.0, model_top]),
        t_grid=np.array([0.0, 3600.0]),
    )
    config = SimulationConfig(
        start_time=datetime(2024, 1, 1),
        num_start_locations=1,
        start_locations=[StartLocation(0.0, 0.0, 500.0)],
        total_run_hours=24,
        vertical_motion=0,
        model_top=model_top,
        met_files=[(".", "dummy.arl")],
    )
    return BoundaryHandler(met, config)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

any_lon = st.floats(min_value=-1000.0, max_value=1000.0,
                    allow_nan=False, allow_infinity=False)
any_lat = st.floats(min_value=-1000.0, max_value=1000.0,
                    allow_nan=False, allow_infinity=False)
any_z = st.floats(min_value=-5000.0, max_value=100000.0,
                  allow_nan=False, allow_infinity=False)
terrain_h = st.floats(min_value=0.0, max_value=5000.0,
                      allow_nan=False, allow_infinity=False)
model_top_st = st.floats(min_value=5000.0, max_value=50000.0,
                         allow_nan=False, allow_infinity=False)


# ---------------------------------------------------------------------------
# Property 29: 수직 경계 반사 불변량
# Validates: Requirements 13.1, 13.2
# ---------------------------------------------------------------------------

@given(z=any_z, th=terrain_h, mt=model_top_st)
@settings(max_examples=200)
def test_property_29_vertical_boundary_reflection_invariant(z, th, mt):
    """**Validates: Requirements 13.1, 13.2**

    Feature: hysplit-trajectory-engine, Property 29: 수직 경계 반사 불변량
    After BoundaryHandler.apply, the resulting altitude must satisfy
    terrain_h <= z_new <= model_top.
    """
    assume(th < mt)  # terrain must be below model top

    handler = _make_handler(model_top=mt)
    _, _, z_new, _ = handler.apply(0.0, 0.0, z, terrain_h=th)

    assert z_new >= th, (
        f"z_new={z_new} < terrain_h={th} (input z={z})"
    )
    assert z_new <= mt, (
        f"z_new={z_new} > model_top={mt} (input z={z})"
    )


# ---------------------------------------------------------------------------
# Property 30: 수평 좌표 정규화
# Validates: Requirements 13.3, 13.5
# ---------------------------------------------------------------------------

@given(lon=any_lon, lat=any_lat)
@settings(max_examples=200)
def test_property_30_horizontal_coordinate_normalization(lon, lat):
    """**Validates: Requirements 13.3, 13.5**

    Feature: hysplit-trajectory-engine, Property 30: 수평 좌표 정규화
    After BoundaryHandler.apply, -180 <= lon <= 180 and -90 <= lat <= 90.
    """
    handler = _make_handler()
    lon_new, lat_new, _, _ = handler.apply(lon, lat, 500.0)

    assert -180.0 <= lon_new <= 180.0, (
        f"lon_new={lon_new} out of [-180, 180] (input lon={lon})"
    )
    assert -90.0 <= lat_new <= 90.0, (
        f"lat_new={lat_new} out of [-90, 90] (input lat={lat})"
    )
