"""Unit tests for the Interpolator module.

Covers specific examples, edge cases, and the 4-D (spatial + temporal)
interpolation paths.
"""

from __future__ import annotations

import numpy as np
import pytest

from pyhysplit.core.interpolator import Interpolator
from pyhysplit.core.models import BoundaryError, MetData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _simple_met(fill: float | None = None) -> MetData:
    """3×3×2 spatial grid, 2 time steps."""
    lon_grid = np.array([0.0, 1.0, 2.0])
    lat_grid = np.array([0.0, 1.0, 2.0])
    z_grid = np.array([0.0, 1000.0])
    t_grid = np.array([0.0, 3600.0])

    shape = (2, 2, 3, 3)
    if fill is not None:
        u = np.full(shape, fill)
        v = np.full(shape, fill)
        w = np.full(shape, fill)
    else:
        rng = np.random.default_rng(7)
        u = rng.uniform(-10, 10, shape)
        v = rng.uniform(-10, 10, shape)
        w = rng.uniform(-5, 5, shape)

    return MetData(u=u, v=v, w=w,
                   lon_grid=lon_grid, lat_grid=lat_grid,
                   z_grid=z_grid, t_grid=t_grid)


# ---------------------------------------------------------------------------
# trilinear
# ---------------------------------------------------------------------------

class TestTrilinear:
    def test_grid_node_returns_exact_value(self):
        met = _simple_met()
        interp = Interpolator(met)
        val = interp.trilinear(met.u[0], 0.0, 0.0, 0.0)
        assert val == pytest.approx(float(met.u[0, 0, 0, 0]))

    def test_midpoint_of_uniform_field(self):
        met = _simple_met(fill=5.0)
        interp = Interpolator(met)
        val = interp.trilinear(met.u[0], 0.5, 0.5, 500.0)
        assert val == pytest.approx(5.0)

    def test_boundary_error_lon_above(self):
        met = _simple_met()
        interp = Interpolator(met)
        with pytest.raises(BoundaryError):
            interp.trilinear(met.u[0], 2.1, 1.0, 500.0)

    def test_boundary_error_z_below(self):
        met = _simple_met()
        interp = Interpolator(met)
        with pytest.raises(BoundaryError):
            interp.trilinear(met.u[0], 1.0, 1.0, -1.0)


# ---------------------------------------------------------------------------
# interpolate_4d
# ---------------------------------------------------------------------------

class TestInterpolate4D:
    def test_uniform_field_returns_constant(self):
        met = _simple_met(fill=3.0)
        interp = Interpolator(met)
        u, v, w = interp.interpolate_4d(0.5, 0.5, 500.0, 1800.0)
        assert u == pytest.approx(3.0)
        assert v == pytest.approx(3.0)
        assert w == pytest.approx(3.0)

    def test_time_boundary_error(self):
        met = _simple_met()
        interp = Interpolator(met)
        with pytest.raises(BoundaryError):
            interp.interpolate_4d(0.5, 0.5, 500.0, -1.0)

    def test_time_interpolation_midpoint(self):
        """At t = midpoint, result should be average of two snapshots."""
        met = _simple_met()
        interp = Interpolator(met)
        lon, lat, z = 0.0, 0.0, 0.0
        t_mid = 1800.0  # halfway

        u, _, _ = interp.interpolate_4d(lon, lat, z, t_mid)
        expected = 0.5 * (float(met.u[0, 0, 0, 0]) + float(met.u[1, 0, 0, 0]))
        assert u == pytest.approx(expected)


# ---------------------------------------------------------------------------
# interpolate_scalar
# ---------------------------------------------------------------------------

class TestInterpolateScalar:
    def test_uniform_scalar(self):
        met = _simple_met(fill=7.0)
        interp = Interpolator(met)
        val = interp.interpolate_scalar(met.u, 0.5, 0.5, 500.0, 1800.0)
        assert val == pytest.approx(7.0)

    def test_scalar_time_boundary_error(self):
        met = _simple_met()
        interp = Interpolator(met)
        with pytest.raises(BoundaryError):
            interp.interpolate_scalar(met.u, 0.5, 0.5, 500.0, 5000.0)
