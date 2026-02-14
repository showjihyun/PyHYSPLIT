"""Turbulence diffusion module for pyhysplit.

Implements PBL-based vertical diffusion (Kz) with separate parameterisations
for convective (CBL) and stable (SBL) boundary layers, Richardson-law
horizontal diffusion (Kh), and Gaussian turbulent velocity perturbations.

References:
    Stein, A.F. et al. (2015) BAMS, Section 2c.
    Draxler, R.R. & Hess, G.D. (1998).
"""

from __future__ import annotations

import numpy as np

from pyhysplit.core.models import MetData, SimulationConfig

# Von Kármán constant
KAPPA = 0.4

# Background (free-atmosphere) diffusion coefficient (m²/s)
KZ_BACKGROUND = 0.01


class TurbulenceModule:
    """Atmospheric boundary-layer turbulence parameterisation.

    Parameters
    ----------
    met : MetData
        Meteorological data (used for PBL height look-up when available).
    config : SimulationConfig
        Simulation configuration (turbulence_on, sigma, khmax, mgmin …).
    """

    def __init__(self, met: MetData, config: SimulationConfig) -> None:
        self.met = met
        self.config = config

    # ------------------------------------------------------------------
    # Vertical diffusion coefficient
    # ------------------------------------------------------------------

    @staticmethod
    def compute_kz(
        z: float, pbl_h: float, ustar: float, L: float
    ) -> float:
        """Compute vertical diffusion coefficient Kz.

        Uses convective (L < 0) or stable (L > 0) parameterisation
        depending on the Monin-Obukhov length.

        Parameters
        ----------
        z : float
            Height above ground (m).
        pbl_h : float
            Planetary boundary-layer height (m).
        ustar : float
            Friction velocity (m/s).
        L : float
            Monin-Obukhov length (m).  Negative → unstable, positive → stable.

        Returns
        -------
        float
            Kz in m²/s, always ≥ KZ_BACKGROUND (0.01).
        """
        if pbl_h <= 0:
            return KZ_BACKGROUND

        # Above PBL → free-atmosphere background only
        if z > pbl_h:
            return KZ_BACKGROUND

        zn = z / pbl_h  # normalised height

        if L < 0:
            # Convective boundary layer (CBL)
            # Combined mechanical + convective contribution so that Kz
            # is always at least as large as the neutral/stable value.
            wstar = ustar * (-pbl_h / (KAPPA * L)) ** (1.0 / 3.0)
            kz_conv = KAPPA * wstar * z * (1.0 - zn) ** 2
            kz_mech = KAPPA * ustar * z * (1.0 - zn) ** 2
            kz = max(kz_conv, kz_mech)
        else:
            # Stable boundary layer (SBL)  — L > 0 or neutral (L == 0)
            phi_m = 1.0 + 5.0 * z / L if L > 0 else 1.0
            kz = KAPPA * ustar * z / phi_m * (1.0 - zn) ** 2

        return max(kz, KZ_BACKGROUND)

    # ------------------------------------------------------------------
    # Horizontal diffusion coefficient
    # ------------------------------------------------------------------

    @staticmethod
    def compute_kh(dx_m: float, khmax: float = 9999.0) -> float:
        """Compute horizontal diffusion coefficient Kh.

        Uses the Richardson 4/3-power law:  Kh = 0.0001 · Δx^(4/3),
        capped at *khmax*.

        Parameters
        ----------
        dx_m : float
            Grid spacing in metres.
        khmax : float
            Maximum allowed Kh (m²/s).

        Returns
        -------
        float
            Kh in m²/s.
        """
        return min(0.0001 * dx_m ** (4.0 / 3.0), khmax)

    # ------------------------------------------------------------------
    # Turbulent velocity perturbation
    # ------------------------------------------------------------------

    def get_perturbation(
        self,
        lon: float,
        lat: float,
        z: float,
        t: float,
        dt: float,
    ) -> tuple[float, float, float]:
        """Compute turbulent velocity perturbation (du, dv, dw).

        Two modes are supported:

        * **σ mode** — when ``config.sigma > 0``, isotropic Gaussian
          perturbations with standard deviation σ are returned.
        * **PBL mode** — when ``config.sigma == 0``, perturbations are
          derived from Kz/Kh using ``σ = sqrt(2K / |Δt|)``.

        If turbulence is disabled (``config.turbulence_on is False``),
        returns ``(0.0, 0.0, 0.0)``.

        Parameters
        ----------
        lon, lat, z, t : float
            Current particle position and time.
        dt : float
            Current integration time step (s).

        Returns
        -------
        tuple[float, float, float]
            (du, dv, dw) perturbation velocities in m/s.
        """
        if not self.config.turbulence_on:
            return 0.0, 0.0, 0.0

        # σ mode (simple isotropic turbulence)
        if self.config.sigma > 0:
            s = self.config.sigma
            return (
                np.random.normal(0.0, s),
                np.random.normal(0.0, s),
                np.random.normal(0.0, s),
            )

        # PBL-based mode
        pbl_h = self._get_pbl_height(lon, lat, t)
        ustar = self._get_ustar(lon, lat, t)
        L = self._get_monin_obukhov_length(lon, lat, t)

        kz = self.compute_kz(z, pbl_h, ustar, L)
        kh = self.compute_kh(self.config.mgmin * 1000.0, self.config.khmax)

        abs_dt = max(abs(dt), 1.0)
        sigma_h = np.sqrt(2.0 * kh / abs_dt)
        sigma_w = np.sqrt(2.0 * kz / abs_dt)

        return (
            np.random.normal(0.0, sigma_h),
            np.random.normal(0.0, sigma_h),
            np.random.normal(0.0, sigma_w),
        )

    # ------------------------------------------------------------------
    # Internal helpers — PBL diagnostics from met data
    # ------------------------------------------------------------------

    def _get_pbl_height(self, lon: float, lat: float, t: float) -> float:
        """Look up PBL height from met data, or return default."""
        if self.met.pbl_height is not None and self.met.pbl_height.size > 0:
            return self._interp_surface(self.met.pbl_height, lon, lat, t)
        return max(float(self.config.kmix0), 250.0)

    def _get_ustar(self, lon: float, lat: float, t: float) -> float:
        """Return friction velocity.  Placeholder — defaults to 0.3 m/s."""
        return 0.3

    def _get_monin_obukhov_length(
        self, lon: float, lat: float, t: float
    ) -> float:
        """Return Monin-Obukhov length.  Placeholder — defaults to -100 m (unstable)."""
        return -100.0

    def _interp_surface(
        self, field_3d: np.ndarray, lon: float, lat: float, t: float
    ) -> float:
        """Simple nearest-neighbour look-up on a (t, lat, lon) surface field."""
        lon_grid = self.met.lon_grid
        lat_grid = self.met.lat_grid
        t_grid = self.met.t_grid

        i = int(np.argmin(np.abs(lon_grid - lon)))
        j = int(np.argmin(np.abs(lat_grid - lat)))
        k = int(np.argmin(np.abs(t_grid - t)))

        return float(field_3d[k, j, i])
