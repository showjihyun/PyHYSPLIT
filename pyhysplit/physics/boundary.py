"""Boundary handling for particle positions.

Implements date-line crossing, pole traversal, surface/top reflection,
and horizontal grid-extent checks as specified in HYSPLIT (Draxler 1999,
Chapter 2).

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5
"""

from __future__ import annotations

import numpy as np

from pyhysplit.core.models import MetData, SimulationConfig


class BoundaryHandler:
    """Applies boundary corrections to particle positions.

    Parameters
    ----------
    met : MetData
        Meteorological data (used for horizontal grid extent).
    config : SimulationConfig
        Simulation configuration (used for model_top).
    """

    def __init__(self, met: MetData, config: SimulationConfig) -> None:
        self.met = met
        self.model_top = config.model_top
        self.z_type = met.z_type

    def apply(
        self,
        lon: float,
        lat: float,
        z: float,
        terrain_h: float = 0.0,
    ) -> tuple[float, float, float, bool]:
        """Apply all boundary corrections to a particle position.

        Processing order:
        1. Date-line wrapping (lon → [-180, 180])
        2. Pole traversal (lat → [-90, 90] with lon flip)
        3. Horizontal grid-extent check → deactivate if outside
        4. Surface reflection (z ≥ terrain_h)
        5. Model-top reflection (z ≤ model_top)

        Parameters
        ----------
        lon, lat, z : float
            Current particle position.
        terrain_h : float
            Local terrain height (m AGL reference, default 0).

        Returns
        -------
        tuple[float, float, float, bool]
            Corrected (lon, lat, z, is_active).
        """
        active = True

        # --- 1. Date-line wrapping (Req 13.3) ---
        lon = _normalize_lon(lon)

        # --- 2. Pole traversal (Req 13.5) ---
        lon, lat = _normalize_lat(lon, lat)

        # --- 3. Horizontal grid-extent check (Req 13.4) ---
        if not self._inside_horizontal_grid(lon, lat):
            active = False

        # --- 4 & 5. Vertical reflection between surface and model top ---
        if self.z_type == "pressure":
            # For pressure coordinates: z_min (e.g., 200 hPa) is top, z_max (e.g., 1000 hPa) is bottom
            z_min = self.met.z_grid[0]  # Top (low pressure)
            z_max = self.met.z_grid[-1]  # Bottom (high pressure)
            z = _reflect_vertical_pressure(z, z_min, z_max)
        else:
            # For height coordinates: use terrain_h and model_top
            z = _reflect_vertical(z, terrain_h, self.model_top)

        return lon, lat, z, active

    def _inside_horizontal_grid(self, lon: float, lat: float) -> bool:
        """Check whether (lon, lat) is within the met-data grid extent."""
        return (
            self.met.lon_grid[0] <= lon <= self.met.lon_grid[-1]
            and self.met.lat_grid[0] <= lat <= self.met.lat_grid[-1]
        )


# -----------------------------------------------------------------------
# Pure helper functions (easy to test independently)
# -----------------------------------------------------------------------

def _normalize_lon(lon: float) -> float:
    """Wrap longitude into [-180, 180]."""
    # Use modular arithmetic: shift to [0, 360) then back.
    lon = ((lon + 180.0) % 360.0) - 180.0
    # Python's % can return -180 for exactly 180; fix that edge.
    if lon == -180.0:
        lon = 180.0
    return lon


def _normalize_lat(lon: float, lat: float) -> tuple[float, float]:
    """Handle pole crossing so that lat stays in [-90, 90].

    When a particle crosses a pole the latitude is reflected and the
    longitude is flipped by 180°.
    """
    # Reduce lat into [-180, 180) first via wrapping.
    lat = ((lat + 180.0) % 360.0) - 180.0

    if lat > 90.0:
        lat = 180.0 - lat
        lon = _flip_lon(lon)
    elif lat < -90.0:
        lat = -180.0 - lat
        lon = _flip_lon(lon)

    # Re-normalise lon after potential flip.
    lon = _normalize_lon(lon)
    return lon, lat


def _flip_lon(lon: float) -> float:
    """Flip longitude by 180°."""
    return lon + 180.0 if lon <= 0.0 else lon - 180.0


def _reflect_vertical(z: float, terrain_h: float, model_top: float) -> float:
    """Reflect altitude between terrain_h and model_top (Req 13.1, 13.2).

    Repeatedly bounces the altitude off the surface and model top until
    it lies within [terrain_h, model_top].  This handles cases where a
    single reflection overshoots the opposite boundary.
    """
    span = model_top - terrain_h
    if span <= 0:
        return terrain_h

    # Shift so that the valid range is [0, span].
    z_shifted = z - terrain_h

    # Use modular "triangle wave" reflection.
    # Period = 2 * span.  Within one period:
    #   [0, span]        → z_shifted (ascending)
    #   (span, 2*span)   → 2*span - z_shifted (descending / reflected)
    period = 2.0 * span
    z_mod = z_shifted % period
    if z_mod < 0:
        z_mod += period  # ensure positive modulus
    if z_mod <= span:
        return terrain_h + z_mod
    else:
        return terrain_h + (period - z_mod)


def _reflect_vertical_pressure(p: float, p_min: float, p_max: float) -> float:
    """Reflect pressure between p_min (top) and p_max (bottom).

    For pressure coordinates:
    - p_min (e.g., 200 hPa) is the top of the atmosphere (low pressure)
    - p_max (e.g., 1000 hPa) is the bottom/surface (high pressure)

    Parameters
    ----------
    p : float
        Current pressure (hPa).
    p_min : float
        Minimum pressure / top boundary (hPa).
    p_max : float
        Maximum pressure / bottom boundary (hPa).

    Returns
    -------
    float
        Reflected pressure within [p_min, p_max].
    """
    span = p_max - p_min
    if span <= 0:
        return p_min

    # Shift so that the valid range is [0, span].
    p_shifted = p - p_min

    # Use modular "triangle wave" reflection.
    period = 2.0 * span
    p_mod = p_shifted % period
    if p_mod < 0:
        p_mod += period  # ensure positive modulus
    if p_mod <= span:
        return p_min + p_mod
    else:
        return p_min + (period - p_mod)
