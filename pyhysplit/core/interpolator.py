"""4D meteorological field interpolation (x→y→z→t order).

Implements HYSPLIT-compatible trilinear spatial interpolation followed by
temporal linear interpolation.  The interpolation order x(lon)→y(lat)→z(alt)
is critical — changing the order produces numerically different results.

References:
    Draxler, R.R. (1999) HYSPLIT-4 User's Guide, Chapter 3.
    Stein, A.F. et al. (2015) BAMS, Section 2a.
"""

from __future__ import annotations

import numpy as np

from pyhysplit.core.models import BoundaryError, MetData

EARTH_RADIUS = 6_371_000.0  # metres


class Interpolator:
    """Performs 4-D interpolation on meteorological fields.

    Parameters
    ----------
    met : MetData
        Meteorological data with gridded wind and scalar fields.
    """

    def __init__(self, met: MetData) -> None:
        self.met = met
        # Cache for time slices to avoid repeated array indexing
        self._cached_time_idx: int | None = None
        self._cached_u_slices: tuple[np.ndarray, np.ndarray] | None = None
        self._cached_v_slices: tuple[np.ndarray, np.ndarray] | None = None
        self._cached_w_slices: tuple[np.ndarray, np.ndarray] | None = None

    # ------------------------------------------------------------------
    # 3-D spatial interpolation (x → y → z)
    # ------------------------------------------------------------------

    def trilinear(
        self, var_3d: np.ndarray, lon: float, lat: float, z: float
    ) -> float:
        """Trilinear interpolation in x→y→z order.

        Parameters
        ----------
        var_3d : np.ndarray
            3-D field with shape ``(nz, nlat, nlon)``.
        lon : float
            Longitude in degrees.
        lat : float
            Latitude in degrees.
        z : float
            Vertical coordinate in MetData coordinate system. Must match the
            coordinate system of MetData.z_grid (pressure in hPa if z_type is
            "pressure", height in meters if z_type is "height").

        Returns
        -------
        float
            Interpolated value.

        Raises
        ------
        BoundaryError
            If the query position is outside the grid domain.
        """
        lon_grid = self.met.lon_grid
        lat_grid = self.met.lat_grid
        z_grid = self.met.z_grid

        # --- strict range check first ---
        if (lon < lon_grid[0] or lon > lon_grid[-1]
                or lat < lat_grid[0] or lat > lat_grid[-1]
                or z < z_grid[0] or z > z_grid[-1]):
            raise BoundaryError(
                f"Position ({lon}, {lat}, {z}) outside grid"
            )

        # --- locate enclosing cell indices ---
        # side='right' so that grid[0] maps to index 1 → cell 0 after -1.
        i = int(np.searchsorted(lon_grid, lon, side="right")) - 1
        j = int(np.searchsorted(lat_grid, lat, side="right")) - 1
        k = int(np.searchsorted(z_grid, z, side="right")) - 1

        # Clamp: a query exactly on the last grid node gets pulled into the
        # last cell (fractional distance = 1.0, which is fine for lerp).
        i = min(i, len(lon_grid) - 2)
        j = min(j, len(lat_grid) - 2)
        k = min(k, len(z_grid) - 2)

        # --- fractional distances (handles non-uniform grids) ---
        xd = (lon - lon_grid[i]) / (lon_grid[i + 1] - lon_grid[i])
        yd = (lat - lat_grid[j]) / (lat_grid[j + 1] - lat_grid[j])
        zd = (z - z_grid[k]) / (z_grid[k + 1] - z_grid[k])

        # --- x-direction interpolation (4 pairs) ---
        c00 = var_3d[k,   j,   i] * (1 - xd) + var_3d[k,   j,   i + 1] * xd
        c01 = var_3d[k,   j + 1, i] * (1 - xd) + var_3d[k,   j + 1, i + 1] * xd
        c10 = var_3d[k + 1, j,   i] * (1 - xd) + var_3d[k + 1, j,   i + 1] * xd
        c11 = var_3d[k + 1, j + 1, i] * (1 - xd) + var_3d[k + 1, j + 1, i + 1] * xd

        # --- y-direction interpolation (2 pairs) ---
        c0 = c00 * (1 - yd) + c01 * yd
        c1 = c10 * (1 - yd) + c11 * yd

        # --- z-direction interpolation ---
        return float(c0 * (1 - zd) + c1 * zd)

    # ------------------------------------------------------------------
    # 4-D wind interpolation (spatial then temporal)
    # ------------------------------------------------------------------

    def interpolate_4d(
        self, lon: float, lat: float, z: float, t: float
    ) -> tuple[float, float, float]:
        """Interpolate wind vector (u, v, w) at an arbitrary 4-D point.

        Spatial interpolation is performed at each bounding time snapshot,
        then the two results are linearly interpolated in time.

        Parameters
        ----------
        lon : float
            Longitude in degrees.
        lat : float
            Latitude in degrees.
        z : float
            Vertical coordinate in MetData coordinate system. If MetData.z_type
            is "pressure", this should be pressure in hPa. If MetData.z_type is
            "height", this should be height in meters. The caller is responsible
            for converting from other coordinate systems (e.g., meters AGL) to
            the MetData coordinate system before calling this method.
        t : float
            Time in seconds since reference.

        Returns
        -------
        tuple[float, float, float]
            Interpolated (u, v, w) wind components in m/s.

        Raises
        ------
        BoundaryError
            If the query is outside the spatial or temporal grid.
        """
        t_grid = self.met.t_grid

        # Range check
        if t < t_grid[0] or t > t_grid[-1]:
            raise BoundaryError(
                f"Time {t} outside range [{t_grid[0]}, {t_grid[-1]}]"
            )

        # Use side='right' so that t_grid[0] maps to index 1 → cell 0.
        it = int(np.searchsorted(t_grid, t, side="right")) - 1
        # Clamp to last valid cell for exact last grid point.
        it = min(it, len(t_grid) - 2)

        dt_frac = (t - t_grid[it]) / (t_grid[it + 1] - t_grid[it])

        # Check cache and update if needed
        if it != self._cached_time_idx:
            self._cached_time_idx = it
            self._cached_u_slices = (self.met.u[it], self.met.u[it + 1])
            self._cached_v_slices = (self.met.v[it], self.met.v[it + 1])
            self._cached_w_slices = (self.met.w[it], self.met.w[it + 1])

        # Use cached slices for spatial interpolation
        u_slice_0, u_slice_1 = self._cached_u_slices
        v_slice_0, v_slice_1 = self._cached_v_slices
        w_slice_0, w_slice_1 = self._cached_w_slices

        # Spatial interpolation at each time snapshot, then temporal lerp
        u = (self.trilinear(u_slice_0, lon, lat, z) * (1 - dt_frac)
             + self.trilinear(u_slice_1, lon, lat, z) * dt_frac)
        v = (self.trilinear(v_slice_0, lon, lat, z) * (1 - dt_frac)
             + self.trilinear(v_slice_1, lon, lat, z) * dt_frac)
        w = (self.trilinear(w_slice_0, lon, lat, z) * (1 - dt_frac)
             + self.trilinear(w_slice_1, lon, lat, z) * dt_frac)

        return u, v, w

    # ------------------------------------------------------------------
    # 4-D scalar interpolation
    # ------------------------------------------------------------------

    def interpolate_scalar(
        self, var_4d: np.ndarray, lon: float, lat: float, z: float, t: float
    ) -> float:
        """Interpolate an arbitrary scalar variable at a 4-D point.

        Parameters
        ----------
        var_4d : np.ndarray
            4-D field with shape ``(nt, nz, nlat, nlon)``.
        lon : float
            Longitude in degrees.
        lat : float
            Latitude in degrees.
        z : float
            Vertical coordinate in MetData coordinate system. Must match the
            coordinate system of MetData.z_grid (pressure in hPa if z_type is
            "pressure", height in meters if z_type is "height").
        t : float
            Time in seconds since reference.

        Returns
        -------
        float
            Interpolated scalar value.

        Raises
        ------
        BoundaryError
            If the query is outside the grid domain.
        """
        t_grid = self.met.t_grid

        if t < t_grid[0] or t > t_grid[-1]:
            raise BoundaryError(
                f"Time {t} outside range [{t_grid[0]}, {t_grid[-1]}]"
            )

        it = int(np.searchsorted(t_grid, t, side="right")) - 1
        it = min(it, len(t_grid) - 2)

        dt_frac = (t - t_grid[it]) / (t_grid[it + 1] - t_grid[it])

        return (self.trilinear(var_4d[it], lon, lat, z) * (1 - dt_frac)
                + self.trilinear(var_4d[it + 1], lon, lat, z) * dt_frac)
