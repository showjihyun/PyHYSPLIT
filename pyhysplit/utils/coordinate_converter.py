"""Vertical coordinate system conversions.

Converts between sigma, pressure, height, and hybrid coordinate systems
as used by various meteorological data sources. HYSPLIT internally uses
terrain-following sigma coordinates and converts input data accordingly.

References:
    Draxler, R.R. & Hess, G.D. (1998).
    Draxler, R.R. (1999) HYSPLIT-4 User's Guide, Chapter 3.
"""

from __future__ import annotations

import numpy as np


class CoordinateConverter:
    """Static methods for vertical coordinate transformations."""

    @staticmethod
    def sigma_to_pressure(
        sigma: np.ndarray,
        p_sfc: np.ndarray,
        p_top: float = 0.0,
    ) -> np.ndarray:
        """Convert sigma coordinate to pressure.

        P = sigma * (P_sfc - P_top) + P_top

        Parameters
        ----------
        sigma : np.ndarray
            Sigma values in [0, 1].
        p_sfc : np.ndarray
            Surface pressure (Pa).
        p_top : float
            Model top pressure (Pa), default 0.

        Returns
        -------
        np.ndarray
            Pressure values (Pa).
        """
        return sigma * (p_sfc - p_top) + p_top

    @staticmethod
    def pressure_to_sigma(
        pressure: np.ndarray,
        p_sfc: np.ndarray,
        p_top: float = 0.0,
    ) -> np.ndarray:
        """Convert pressure to sigma coordinate.

        sigma = (P - P_top) / (P_sfc - P_top)

        Parameters
        ----------
        pressure : np.ndarray
            Pressure values (Pa).
        p_sfc : np.ndarray
            Surface pressure (Pa).
        p_top : float
            Model top pressure (Pa), default 0.

        Returns
        -------
        np.ndarray
            Sigma values.
        """
        return (pressure - p_top) / (p_sfc - p_top)

    @staticmethod
    def pressure_to_height(
        P: np.ndarray,
        hgt: np.ndarray | None = None,
        P0: float = 101325.0,
        H: float = 8500.0,
    ) -> np.ndarray:
        """Convert pressure to height.

        Uses geopotential height if available, otherwise standard
        atmosphere approximation: Z = -H * ln(P / P0).
        
        The standard atmosphere approximation assumes an exponential
        pressure decrease with height, which is a reasonable approximation
        for the troposphere. This is the inverse of the height-to-pressure
        conversion formula P = P0 * exp(-z / H).
        
        The default parameters (P0=101325 Pa, H=8500 m) represent:
        - P0: Standard sea-level pressure (1013.25 hPa)
        - H: Atmospheric scale height (the height at which pressure
          decreases by a factor of e ≈ 2.718)

        Parameters
        ----------
        P : np.ndarray
            Pressure values (Pa).
        hgt : np.ndarray or None
            Geopotential height field. If provided, returned directly.
        P0 : float
            Reference surface pressure (Pa), default 101325.
        H : float
            Scale height (m), default 8500.

        Returns
        -------
        np.ndarray
            Height values (m).
        """
        if hgt is not None:
            return hgt
        return -H * np.log(np.asarray(P, dtype=float) / P0)

    @staticmethod
    def pressure_to_height_hypsometric(
        P: np.ndarray,
        T: np.ndarray,
        P_ref: float = 101325.0,
        z_ref: float = 0.0,
    ) -> np.ndarray:
        """Convert pressure to height using hypsometric equation.

        This is the most accurate method when temperature is known.
        Uses the hypsometric (thickness) equation:
        
        z2 - z1 = (Rd * T_mean / g) * ln(P1 / P2)
        
        where T_mean is the mean virtual temperature between the two levels.

        Parameters
        ----------
        P : np.ndarray
            Pressure values (Pa).
        T : np.ndarray
            Temperature values (K) at the pressure levels.
        P_ref : float
            Reference pressure (Pa), default 101325 (sea level).
        z_ref : float
            Reference height (m), default 0 (sea level).

        Returns
        -------
        np.ndarray
            Height values (m).
        """
        from pyhysplit.met_reader import RD, GRAVITY
        
        P = np.asarray(P, dtype=float)
        T = np.asarray(T, dtype=float)
        
        # Hypsometric equation: Δz = (Rd * T_mean / g) * ln(P1 / P2)
        # z = z_ref + (Rd * T / g) * ln(P_ref / P)
        return z_ref + (RD * T / GRAVITY) * np.log(P_ref / P)

    @staticmethod
    def height_to_pressure(
        z: np.ndarray,
        P0: float = 101325.0,
        H: float = 8500.0,
    ) -> np.ndarray:
        """Convert height to pressure using standard atmosphere approximation.

        P = P0 * exp(-z / H)
        
        This formula is based on the barometric formula for an isothermal
        atmosphere, which assumes that pressure decreases exponentially
        with height. While this is a simplification of the actual atmosphere
        (which has temperature variations), it provides a reasonable
        approximation for the troposphere.
        
        The standard atmosphere approximation is commonly used in trajectory
        modeling to convert between height coordinates (meters AGL/ASL) and
        pressure coordinates (hPa) used in meteorological data. The default
        parameters represent:
        - P0 = 101325 Pa (1013.25 hPa): Standard sea-level pressure
        - H = 8500 m: Atmospheric scale height (the height at which
          pressure decreases by a factor of e ≈ 2.718)
        
        Example conversions with default parameters:
        - 0 m → 101325 Pa (1013.25 hPa)
        - 850 m → 91680 Pa (916.8 hPa)
        - 1500 m → 84800 Pa (848.0 hPa)
        - 8500 m → 37280 Pa (372.8 hPa)

        Parameters
        ----------
        z : np.ndarray
            Height values (m).
        P0 : float
            Reference surface pressure (Pa), default 101325.
        H : float
            Scale height (m), default 8500.

        Returns
        -------
        np.ndarray
            Pressure values (Pa).
        """
        return P0 * np.exp(-np.asarray(z, dtype=float) / H)

    @staticmethod
    def hybrid_to_pressure(
        A: np.ndarray,
        B: np.ndarray,
        p_sfc: np.ndarray,
    ) -> np.ndarray:
        """Convert hybrid (sigma-pressure) coordinates to pressure.

        P = A(k) + B(k) * P_sfc

        Parameters
        ----------
        A : np.ndarray
            Hybrid A coefficients, shape (nlevels,).
        B : np.ndarray
            Hybrid B coefficients, shape (nlevels,).
        p_sfc : np.ndarray
            Surface pressure (Pa), shape (nlat, nlon) or scalar.

        Returns
        -------
        np.ndarray
            Pressure at each level. Shape depends on inputs.
        """
        A = np.asarray(A, dtype=float)
        B = np.asarray(B, dtype=float)
        p_sfc = np.asarray(p_sfc, dtype=float)

        if p_sfc.ndim == 0:
            # scalar surface pressure
            return A + B * p_sfc
        # 2-D surface pressure → broadcast over levels
        return A[:, None, None] + B[:, None, None] * p_sfc[None, :, :]

    @staticmethod
    def terrain_correction(
        z_agl: np.ndarray,
        terrain_height: np.ndarray,
    ) -> np.ndarray:
        """Convert AGL (above ground level) to ASL (above sea level).

        ASL = z_agl + terrain_height

        Parameters
        ----------
        z_agl : np.ndarray
            Height above ground level (m).
        terrain_height : np.ndarray
            Terrain elevation (m ASL).

        Returns
        -------
        np.ndarray
            Height above sea level (m).
        """
        return np.asarray(z_agl, dtype=float) + np.asarray(terrain_height, dtype=float)
