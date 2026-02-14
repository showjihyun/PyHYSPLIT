"""Heun (Modified Euler) integrator and adaptive Δt controller.

Implements the HYSPLIT-compatible Predictor-Corrector time integration
and CFL-based adaptive time step control.

References:
    Stein, A.F. et al. (2015) BAMS, Section 2a.
    Draxler, R.R. & Hess, G.D. (1998).
    Draxler, R.R. (1999) HYSPLIT-4 User's Guide, Chapter 2.
"""

from __future__ import annotations

import numpy as np

from pyhysplit.core.interpolator import EARTH_RADIUS, Interpolator
from pyhysplit.core.models import MetData, SimulationConfig

# Physical constants for pressure coordinate conversion
RD = 287.05       # Specific gas constant for dry air (J/(kg·K))
GRAVITY = 9.80665  # Standard gravitational acceleration (m/s²)


class HeunIntegrator:
    """Heun (Modified Euler) Predictor-Corrector integrator.

    Computes particle advection using the two-stage Heun method:
        P(t+Δt) = P(t) + 0.5 * [V(P(t), t) + V(P'(t+Δt), t+Δt)] * Δt

    Parameters
    ----------
    interpolator : Interpolator
        4-D wind field interpolator.
    turbulence : object, optional
        Turbulence module providing ``get_perturbation(lon, lat, z, t, dt)``.
    """

    def __init__(
        self,
        interpolator: Interpolator,
        turbulence: object | None = None,
        vertical_motion: object | None = None,
    ) -> None:
        self.interp = interpolator
        self.turbulence = turbulence
        self.vertical_motion = vertical_motion

    @staticmethod
    def advect_lonlat(
        lon: float, lat: float, u: float, v: float, dt: float,
    ) -> tuple[float, float]:
        """Compute new lon/lat after advection on a sphere.

        Uses the HYSPLIT spherical advection formulae:
            Δlat = (v * dt) / R
            Δlon = (u * dt) / (R * cos(lat))

        Parameters
        ----------
        lon, lat : float
            Current position in degrees.
        u, v : float
            East-west and north-south wind components (m/s).
        dt : float
            Time step (seconds). Can be negative for backward trajectories.

        Returns
        -------
        tuple[float, float]
            New (lon, lat) in degrees.
        """
        lat_rad = np.deg2rad(lat)
        cos_lat = np.cos(lat_rad)

        # Guard against division by zero at poles
        if abs(cos_lat) < 1e-10:
            cos_lat = 1e-10 * np.sign(cos_lat) if cos_lat != 0 else 1e-10

        dlat_rad = (v * dt) / EARTH_RADIUS
        dlon_rad = (u * dt) / (EARTH_RADIUS * cos_lat)

        new_lon = lon + np.rad2deg(dlon_rad)
        new_lat = lat + np.rad2deg(dlat_rad)

        return new_lon, new_lat

    def step(
        self,
        lon: float,
        lat: float,
        z: float,
        t: float,
        dt: float,
    ) -> tuple[float, float, float]:
        """Perform one Heun integration step.

        P(t+dt) = P(t) + 0.5 * (V1 + V2) * dt

        where V1 = V(P, t) and V2 = V(P', t+dt) with P' = P + V1*dt.

        Parameters
        ----------
        lon, lat, z : float
            Current particle position (degrees, degrees, vertical coordinate).
            For pressure coordinates, z is in hPa. For height coordinates, z is in metres.
        t : float
            Current time (seconds since reference).
        dt : float
            Time step (seconds). Negative for backward trajectories.

        Returns
        -------
        tuple[float, float, float]
            New (lon, lat, z) after one Heun step.
        """
        # Determine if this is a backward trajectory
        is_backward = dt < 0
        
        # --- Predictor stage ---
        # Use vertical_motion handler if available, otherwise use direct interpolation
        if self.vertical_motion is not None:
            u1, v1, _ = self.interp.interpolate_4d(lon, lat, z, t)
            w1 = self.vertical_motion.get_vertical_velocity(lon, lat, z, t)
        else:
            u1, v1, w1 = self.interp.interpolate_4d(lon, lat, z, t)
            
        if self.turbulence is not None:
            du, dv, dw = self.turbulence.get_perturbation(lon, lat, z, t, dt)
            u1 += du
            v1 += dv
            w1 += dw

        # For backward trajectories, the wind field represents forward motion
        # but we're integrating backward, so we need to reverse the wind direction
        # However, u and v are already handled correctly by the negative dt
        # For w, we need to be careful with the coordinate system conversion
        
        # Convert w (m/s) to dz/dt in the appropriate coordinate system
        dz_dt1 = self._convert_w_to_dz_dt(w1, z, t, lon, lat, dt)

        lon_p, lat_p = self.advect_lonlat(lon, lat, u1, v1, dt)
        z_p = z + dz_dt1 * dt

        # Clamp z_p to valid range to prevent boundary errors in corrector stage
        met = self.interp.met
        if met.z_type == "pressure":
            z_min, z_max = met.z_grid[0], met.z_grid[-1]
            z_p = max(z_min, min(z_max, z_p))
        else:
            # For height coordinates, clamp to grid range
            z_min, z_max = met.z_grid[0], met.z_grid[-1]
            z_p = max(z_min, min(z_max, z_p))

        # --- Corrector stage ---
        # Use vertical_motion handler if available, otherwise use direct interpolation
        if self.vertical_motion is not None:
            u2, v2, _ = self.interp.interpolate_4d(lon_p, lat_p, z_p, t + dt)
            w2 = self.vertical_motion.get_vertical_velocity(lon_p, lat_p, z_p, t + dt)
        else:
            u2, v2, w2 = self.interp.interpolate_4d(lon_p, lat_p, z_p, t + dt)
            
        if self.turbulence is not None:
            du, dv, dw = self.turbulence.get_perturbation(
                lon_p, lat_p, z_p, t + dt, dt,
            )
            u2 += du
            v2 += dv
            w2 += dw

        # Convert w (m/s) to dz/dt in the appropriate coordinate system
        dz_dt2 = self._convert_w_to_dz_dt(w2, z_p, t + dt, lon_p, lat_p, dt)

        # --- Average and final position ---
        u_avg = 0.5 * (u1 + u2)
        v_avg = 0.5 * (v1 + v2)
        dz_dt_avg = 0.5 * (dz_dt1 + dz_dt2)

        lon_new, lat_new = self.advect_lonlat(lon, lat, u_avg, v_avg, dt)
        z_new = z + dz_dt_avg * dt

        return lon_new, lat_new, z_new

    def _convert_w_to_dz_dt(
        self, w: float, z: float, t: float, lon: float, lat: float, dt: float
    ) -> float:
        """Convert vertical velocity to dz/dt in the MetData coordinate system.

        For pressure coordinates with omega input (hPa/s):
        - omega > 0 means descending (pressure increasing) in forward time
        - omega < 0 means ascending (pressure decreasing) in forward time
        - For backward trajectories (dt < 0), the negative dt naturally reverses direction
          * omega > 0 with dt < 0 → ΔP < 0 (ascending in backward time)
          * omega < 0 with dt < 0 → ΔP > 0 (descending in backward time)
        - NO sign reversal needed! The physics is handled by dt sign.

        For height coordinates:
        - w is dz/dt in m/s, used directly regardless of trajectory direction

        Parameters
        ----------
        w : float
            Vertical velocity. For pressure coords: omega in hPa/s.
            For height coords: w in m/s.
        z : float
            Current vertical coordinate (hPa for pressure, m for height).
        t : float
            Current time (seconds).
        lon, lat : float
            Current horizontal position (degrees).
        dt : float
            Time step (seconds). Negative for backward trajectories.

        Returns
        -------
        float
            Rate of change of z in the MetData coordinate system.
            For pressure: dP/dt in hPa/s (omega value directly).
            For height: dz/dt in m/s (positive = ascending).
        """
        met = self.interp.met

        if met.z_type == "pressure":
            # Pressure coordinates: w is omega (hPa/s)
            # Use omega directly - dt sign handles backward trajectory direction
            return w
        else:
            # Height coordinates: w is dz/dt in m/s
            return w



class AdaptiveDtController:
    """CFL-based adaptive time step controller.

    Computes Δt such that a particle does not cross more than one grid
    cell per step, with upper-bound clamping and met-data time-boundary
    clipping.

    Parameters
    ----------
    met : MetData
        Meteorological data (used for grid spacing and time grid).
    config : SimulationConfig
        Simulation configuration (provides dt_max).
    """

    def __init__(self, met: MetData, config: SimulationConfig) -> None:
        self.met = met
        self.config = config
        self._dx, self._dy = self._compute_grid_spacing()

    def _compute_grid_spacing(self) -> tuple[float, float]:
        """Compute horizontal grid spacing in metres.

        Uses the mid-latitude of the grid for the cos(lat) correction.

        Returns
        -------
        tuple[float, float]
            (dx, dy) in metres.
        """
        dlon = abs(self.met.lon_grid[1] - self.met.lon_grid[0])
        dlat = abs(self.met.lat_grid[1] - self.met.lat_grid[0])
        mid_lat = float(np.mean(self.met.lat_grid))

        dx = dlon * np.deg2rad(1.0) * EARTH_RADIUS * np.cos(np.deg2rad(mid_lat))
        dy = dlat * np.deg2rad(1.0) * EARTH_RADIUS

        return dx, dy

    def compute_dt(
        self, u: float, v: float, w: float, t: float,
    ) -> float:
        """Compute adaptive Δt satisfying CFL conditions.

        HYSPLIT uses TRATIO (configurable, default 0.75), meaning a particle can
        transit TRATIO fraction of a grid cell per time step. This is the CFL condition:
        Δt ≤ TRATIO * min(Δx/|u|, Δy/|v|, Δz/|w|, dt_max)

        Parameters
        ----------
        u, v, w : float
            Wind components (m/s).
        t : float
            Current time (seconds since reference).

        Returns
        -------
        float
            Adaptive time step in seconds (always positive).
        """
        dx, dy = self._dx, self._dy
        
        # HYSPLIT TRATIO parameter (configurable via config)
        # Defines the fraction of a grid cell that a particle is permitted
        # to transit in one advection time step
        TRATIO = self.config.tratio

        # Minimum wind speed to prevent infinite Δt
        speed_u = max(abs(u), 0.001)
        speed_v = max(abs(v), 0.001)

        dt_x = TRATIO * dx / speed_u
        dt_y = TRATIO * dy / speed_v
        dt = min(dt_x, dt_y, self.config.dt_max)

        # Note: HYSPLIT does not apply vertical CFL in the same way
        # The vertical motion is handled through the vertical motion modes
        # and damping factors, not through time step restriction

        # Met-data time boundary clipping
        t_grid = self.met.t_grid
        it = int(np.searchsorted(t_grid, t, side="right")) - 1
        if 0 <= it < len(t_grid) - 1:
            dt_to_boundary = t_grid[it + 1] - t
            if 0 < dt_to_boundary < dt:
                dt = dt_to_boundary

        return dt
