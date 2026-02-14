"""GPU/CPU compute backend abstraction for vectorised particle operations.

Provides a unified interface for batch trilinear interpolation and Heun
integration that can run on either CPU (NumPy) or GPU (CuPy / Numba CUDA).

References:
    Requirements 15.1-15.5 (GPU acceleration).
"""

from __future__ import annotations

import logging
import warnings
from abc import ABC, abstractmethod

import numpy as np

from pyhysplit.core.interpolator import EARTH_RADIUS
from pyhysplit.core.models import MetData

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class ComputeBackend(ABC):
    """Abstract compute backend for batch particle operations."""

    @abstractmethod
    def trilinear_batch(
        self,
        var_3d: np.ndarray,
        lons: np.ndarray,
        lats: np.ndarray,
        zs: np.ndarray,
        lon_grid: np.ndarray,
        lat_grid: np.ndarray,
        z_grid: np.ndarray,
    ) -> np.ndarray:
        """Vectorised trilinear interpolation for *N* particles.

        Parameters
        ----------
        var_3d : ndarray (nz, nlat, nlon)
        lons, lats, zs : ndarray (N,)
        lon_grid, lat_grid, z_grid : 1-D grid arrays

        Returns
        -------
        ndarray (N,)  — interpolated values.
        """
        ...


    @abstractmethod
    def heun_step_batch(
        self,
        lons: np.ndarray,
        lats: np.ndarray,
        zs: np.ndarray,
        t: float,
        dt: float,
        met: MetData,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Vectorised Heun (Predictor-Corrector) step for *N* particles.

        Parameters
        ----------
        lons, lats, zs : ndarray (N,)
        t : float  — current time (seconds since reference).
        dt : float — time step (seconds, may be negative).
        met : MetData

        Returns
        -------
        tuple of ndarray (N,) — new (lons, lats, zs).
        """
        ...


# ---------------------------------------------------------------------------
# NumPy (CPU) backend
# ---------------------------------------------------------------------------

class NumpyBackend(ComputeBackend):
    """CPU backend using pure NumPy vectorised operations."""

    # ---- trilinear batch --------------------------------------------------

    def trilinear_batch(
        self,
        var_3d: np.ndarray,
        lons: np.ndarray,
        lats: np.ndarray,
        zs: np.ndarray,
        lon_grid: np.ndarray,
        lat_grid: np.ndarray,
        z_grid: np.ndarray,
    ) -> np.ndarray:
        lons = np.asarray(lons, dtype=np.float64)
        lats = np.asarray(lats, dtype=np.float64)
        zs = np.asarray(zs, dtype=np.float64)

        # Cell indices (searchsorted side='right' then -1)
        i = np.searchsorted(lon_grid, lons, side="right").astype(np.intp) - 1
        j = np.searchsorted(lat_grid, lats, side="right").astype(np.intp) - 1
        k = np.searchsorted(z_grid, zs, side="right").astype(np.intp) - 1

        # Clamp to valid cell range
        np.clip(i, 0, len(lon_grid) - 2, out=i)
        np.clip(j, 0, len(lat_grid) - 2, out=j)
        np.clip(k, 0, len(z_grid) - 2, out=k)

        # Fractional distances
        xd = (lons - lon_grid[i]) / (lon_grid[i + 1] - lon_grid[i])
        yd = (lats - lat_grid[j]) / (lat_grid[j + 1] - lat_grid[j])
        zd = (zs - z_grid[k]) / (z_grid[k + 1] - z_grid[k])

        # x-direction (4 pairs)
        c00 = var_3d[k,   j,   i] * (1 - xd) + var_3d[k,   j,   i + 1] * xd
        c01 = var_3d[k,   j + 1, i] * (1 - xd) + var_3d[k,   j + 1, i + 1] * xd
        c10 = var_3d[k + 1, j,   i] * (1 - xd) + var_3d[k + 1, j,   i + 1] * xd
        c11 = var_3d[k + 1, j + 1, i] * (1 - xd) + var_3d[k + 1, j + 1, i + 1] * xd

        # y-direction (2 pairs)
        c0 = c00 * (1 - yd) + c01 * yd
        c1 = c10 * (1 - yd) + c11 * yd

        # z-direction
        return c0 * (1 - zd) + c1 * zd

    # ---- heun step batch --------------------------------------------------

    def heun_step_batch(
        self,
        lons: np.ndarray,
        lats: np.ndarray,
        zs: np.ndarray,
        t: float,
        dt: float,
        met: MetData,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        lons = np.asarray(lons, dtype=np.float64)
        lats = np.asarray(lats, dtype=np.float64)
        zs = np.asarray(zs, dtype=np.float64)

        lon_grid = met.lon_grid
        lat_grid = met.lat_grid
        z_grid = met.z_grid
        t_grid = met.t_grid

        # --- helper: 4D batch interpolation (spatial + temporal) ---
        def _interp_4d_batch(
            lo: np.ndarray, la: np.ndarray, z_: np.ndarray, time: float,
        ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
            it = int(np.searchsorted(t_grid, time, side="right")) - 1
            it = min(max(it, 0), len(t_grid) - 2)
            dt_frac = (time - t_grid[it]) / (t_grid[it + 1] - t_grid[it])

            u = (self.trilinear_batch(met.u[it], lo, la, z_, lon_grid, lat_grid, z_grid) * (1 - dt_frac)
                 + self.trilinear_batch(met.u[it + 1], lo, la, z_, lon_grid, lat_grid, z_grid) * dt_frac)
            v = (self.trilinear_batch(met.v[it], lo, la, z_, lon_grid, lat_grid, z_grid) * (1 - dt_frac)
                 + self.trilinear_batch(met.v[it + 1], lo, la, z_, lon_grid, lat_grid, z_grid) * dt_frac)
            w = (self.trilinear_batch(met.w[it], lo, la, z_, lon_grid, lat_grid, z_grid) * (1 - dt_frac)
                 + self.trilinear_batch(met.w[it + 1], lo, la, z_, lon_grid, lat_grid, z_grid) * dt_frac)
            return u, v, w

        # --- helper: spherical advection (vectorised) ---
        def _advect(lo, la, u, v, dt_):
            lat_rad = np.deg2rad(la)
            cos_lat = np.cos(lat_rad)
            cos_lat = np.where(np.abs(cos_lat) < 1e-10, 1e-10, cos_lat)
            dlat_rad = (v * dt_) / EARTH_RADIUS
            dlon_rad = (u * dt_) / (EARTH_RADIUS * cos_lat)
            return lo + np.rad2deg(dlon_rad), la + np.rad2deg(dlat_rad)

        # Predictor
        u1, v1, w1 = _interp_4d_batch(lons, lats, zs, t)
        lon_p, lat_p = _advect(lons, lats, u1, v1, dt)
        z_p = zs + w1 * dt

        # Corrector
        u2, v2, w2 = _interp_4d_batch(lon_p, lat_p, z_p, t + dt)

        # Average
        u_avg = 0.5 * (u1 + u2)
        v_avg = 0.5 * (v1 + v2)
        w_avg = 0.5 * (w1 + w2)

        lon_new, lat_new = _advect(lons, lats, u_avg, v_avg, dt)
        z_new = zs + w_avg * dt

        return lon_new, lat_new, z_new



# ---------------------------------------------------------------------------
# CuPy (GPU) backend
# ---------------------------------------------------------------------------

class CuPyBackend(ComputeBackend):
    """GPU backend using CuPy array operations.

    Falls back gracefully if CuPy is not installed.
    Handles GPU memory limits by splitting batches.
    """

    def __init__(self, max_batch: int = 100_000) -> None:
        try:
            import cupy as cp  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "CuPy is required for GPU acceleration. "
                "Install with: pip install cupy-cuda12x"
            ) from exc
        self.cp = cp
        self.max_batch = max_batch

    # ---- trilinear batch --------------------------------------------------

    def trilinear_batch(
        self,
        var_3d: np.ndarray,
        lons: np.ndarray,
        lats: np.ndarray,
        zs: np.ndarray,
        lon_grid: np.ndarray,
        lat_grid: np.ndarray,
        z_grid: np.ndarray,
    ) -> np.ndarray:
        cp = self.cp
        N = len(lons)

        # Split into sub-batches if needed for GPU memory
        if N > self.max_batch:
            results = []
            for start in range(0, N, self.max_batch):
                end = min(start + self.max_batch, N)
                results.append(
                    self.trilinear_batch(
                        var_3d, lons[start:end], lats[start:end],
                        zs[start:end], lon_grid, lat_grid, z_grid,
                    )
                )
            return np.concatenate(results)

        # Transfer to GPU
        d_var = cp.asarray(var_3d)
        d_lons = cp.asarray(lons, dtype=cp.float64)
        d_lats = cp.asarray(lats, dtype=cp.float64)
        d_zs = cp.asarray(zs, dtype=cp.float64)
        d_lon_grid = cp.asarray(lon_grid)
        d_lat_grid = cp.asarray(lat_grid)
        d_z_grid = cp.asarray(z_grid)

        i = cp.searchsorted(d_lon_grid, d_lons, side="right").astype(cp.intp) - 1
        j = cp.searchsorted(d_lat_grid, d_lats, side="right").astype(cp.intp) - 1
        k = cp.searchsorted(d_z_grid, d_zs, side="right").astype(cp.intp) - 1

        cp.clip(i, 0, len(lon_grid) - 2, out=i)
        cp.clip(j, 0, len(lat_grid) - 2, out=j)
        cp.clip(k, 0, len(z_grid) - 2, out=k)

        xd = (d_lons - d_lon_grid[i]) / (d_lon_grid[i + 1] - d_lon_grid[i])
        yd = (d_lats - d_lat_grid[j]) / (d_lat_grid[j + 1] - d_lat_grid[j])
        zd = (d_zs - d_z_grid[k]) / (d_z_grid[k + 1] - d_z_grid[k])

        c00 = d_var[k,   j,   i] * (1 - xd) + d_var[k,   j,   i + 1] * xd
        c01 = d_var[k,   j + 1, i] * (1 - xd) + d_var[k,   j + 1, i + 1] * xd
        c10 = d_var[k + 1, j,   i] * (1 - xd) + d_var[k + 1, j,   i + 1] * xd
        c11 = d_var[k + 1, j + 1, i] * (1 - xd) + d_var[k + 1, j + 1, i + 1] * xd

        c0 = c00 * (1 - yd) + c01 * yd
        c1 = c10 * (1 - yd) + c11 * yd

        result = c0 * (1 - zd) + c1 * zd
        return cp.asnumpy(result)

    # ---- heun step batch --------------------------------------------------

    def heun_step_batch(
        self,
        lons: np.ndarray,
        lats: np.ndarray,
        zs: np.ndarray,
        t: float,
        dt: float,
        met: MetData,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        cp = self.cp
        N = len(lons)

        if N > self.max_batch:
            res_lon, res_lat, res_z = [], [], []
            for start in range(0, N, self.max_batch):
                end = min(start + self.max_batch, N)
                lo, la, z_ = self.heun_step_batch(
                    lons[start:end], lats[start:end], zs[start:end],
                    t, dt, met,
                )
                res_lon.append(lo)
                res_lat.append(la)
                res_z.append(z_)
            return np.concatenate(res_lon), np.concatenate(res_lat), np.concatenate(res_z)

        lon_grid = met.lon_grid
        lat_grid = met.lat_grid
        z_grid = met.z_grid
        t_grid = met.t_grid

        def _interp_4d_gpu(d_lo, d_la, d_z, time):
            it = int(np.searchsorted(t_grid, time, side="right")) - 1
            it = min(max(it, 0), len(t_grid) - 2)
            dt_frac = (time - t_grid[it]) / (t_grid[it + 1] - t_grid[it])

            d_lon_g = cp.asarray(lon_grid)
            d_lat_g = cp.asarray(lat_grid)
            d_z_g = cp.asarray(z_grid)

            def _tri(var_3d):
                d_var = cp.asarray(var_3d)
                i = cp.searchsorted(d_lon_g, d_lo, side="right").astype(cp.intp) - 1
                j = cp.searchsorted(d_lat_g, d_la, side="right").astype(cp.intp) - 1
                k = cp.searchsorted(d_z_g, d_z, side="right").astype(cp.intp) - 1
                cp.clip(i, 0, len(lon_grid) - 2, out=i)
                cp.clip(j, 0, len(lat_grid) - 2, out=j)
                cp.clip(k, 0, len(z_grid) - 2, out=k)
                xd = (d_lo - d_lon_g[i]) / (d_lon_g[i + 1] - d_lon_g[i])
                yd = (d_la - d_lat_g[j]) / (d_lat_g[j + 1] - d_lat_g[j])
                zd = (d_z - d_z_g[k]) / (d_z_g[k + 1] - d_z_g[k])
                c00 = d_var[k, j, i] * (1 - xd) + d_var[k, j, i + 1] * xd
                c01 = d_var[k, j + 1, i] * (1 - xd) + d_var[k, j + 1, i + 1] * xd
                c10 = d_var[k + 1, j, i] * (1 - xd) + d_var[k + 1, j, i + 1] * xd
                c11 = d_var[k + 1, j + 1, i] * (1 - xd) + d_var[k + 1, j + 1, i + 1] * xd
                c0 = c00 * (1 - yd) + c01 * yd
                c1 = c10 * (1 - yd) + c11 * yd
                return c0 * (1 - zd) + c1 * zd

            u = _tri(met.u[it]) * (1 - dt_frac) + _tri(met.u[it + 1]) * dt_frac
            v = _tri(met.v[it]) * (1 - dt_frac) + _tri(met.v[it + 1]) * dt_frac
            w = _tri(met.w[it]) * (1 - dt_frac) + _tri(met.w[it + 1]) * dt_frac
            return u, v, w

        def _advect_gpu(d_lo, d_la, d_u, d_v, dt_):
            lat_rad = d_la * (cp.pi / 180.0)
            cos_lat = cp.cos(lat_rad)
            cos_lat = cp.where(cp.abs(cos_lat) < 1e-10, 1e-10, cos_lat)
            dlat_rad = (d_v * dt_) / EARTH_RADIUS
            dlon_rad = (d_u * dt_) / (EARTH_RADIUS * cos_lat)
            return d_lo + dlon_rad * (180.0 / cp.pi), d_la + dlat_rad * (180.0 / cp.pi)

        d_lons = cp.asarray(lons, dtype=cp.float64)
        d_lats = cp.asarray(lats, dtype=cp.float64)
        d_zs = cp.asarray(zs, dtype=cp.float64)

        # Predictor
        u1, v1, w1 = _interp_4d_gpu(d_lons, d_lats, d_zs, t)
        lon_p, lat_p = _advect_gpu(d_lons, d_lats, u1, v1, dt)
        z_p = d_zs + w1 * dt

        # Corrector
        u2, v2, w2 = _interp_4d_gpu(lon_p, lat_p, z_p, t + dt)

        u_avg = 0.5 * (u1 + u2)
        v_avg = 0.5 * (v1 + v2)
        w_avg = 0.5 * (w1 + w2)

        lon_new, lat_new = _advect_gpu(d_lons, d_lats, u_avg, v_avg, dt)
        z_new = d_zs + w_avg * dt

        return cp.asnumpy(lon_new), cp.asnumpy(lat_new), cp.asnumpy(z_new)



# ---------------------------------------------------------------------------
# Numba CUDA backend
# ---------------------------------------------------------------------------

class NumbaGPUBackend(ComputeBackend):
    """GPU backend using Numba CUDA kernels.

    Falls back gracefully if numba.cuda is not available.
    """

    def __init__(self, max_batch: int = 100_000) -> None:
        try:
            from numba import cuda  # type: ignore[import-untyped]
            if not cuda.is_available():
                raise RuntimeError("CUDA device not available")
        except (ImportError, RuntimeError) as exc:
            raise ImportError(
                "Numba with CUDA support is required. "
                "Install with: pip install numba"
            ) from exc
        from numba import cuda
        self.cuda = cuda
        self.max_batch = max_batch
        self._compile_kernels()

    def _compile_kernels(self) -> None:
        """Pre-compile CUDA kernels for trilinear interpolation."""
        from numba import cuda as _cuda

        @_cuda.jit
        def _trilinear_kernel(
            var_3d, lons, lats, zs,
            lon_grid, lat_grid, z_grid,
            n_lon, n_lat, n_z, out,
        ):
            idx = _cuda.grid(1)
            if idx >= lons.shape[0]:
                return

            lo = lons[idx]
            la = lats[idx]
            z = zs[idx]

            # searchsorted equivalent (linear scan — grids are small)
            i = 0
            for ii in range(n_lon - 1):
                if lon_grid[ii + 1] >= lo:
                    i = ii
                    break
            j = 0
            for jj in range(n_lat - 1):
                if lat_grid[jj + 1] >= la:
                    j = jj
                    break
            k = 0
            for kk in range(n_z - 1):
                if z_grid[kk + 1] >= z:
                    k = kk
                    break

            xd = (lo - lon_grid[i]) / (lon_grid[i + 1] - lon_grid[i])
            yd = (la - lat_grid[j]) / (lat_grid[j + 1] - lat_grid[j])
            zd = (z - z_grid[k]) / (z_grid[k + 1] - z_grid[k])

            c00 = var_3d[k, j, i] * (1 - xd) + var_3d[k, j, i + 1] * xd
            c01 = var_3d[k, j + 1, i] * (1 - xd) + var_3d[k, j + 1, i + 1] * xd
            c10 = var_3d[k + 1, j, i] * (1 - xd) + var_3d[k + 1, j, i + 1] * xd
            c11 = var_3d[k + 1, j + 1, i] * (1 - xd) + var_3d[k + 1, j + 1, i + 1] * xd

            c0 = c00 * (1 - yd) + c01 * yd
            c1 = c10 * (1 - yd) + c11 * yd

            out[idx] = c0 * (1 - zd) + c1 * zd

        self._trilinear_kernel = _trilinear_kernel

    def trilinear_batch(
        self,
        var_3d: np.ndarray,
        lons: np.ndarray,
        lats: np.ndarray,
        zs: np.ndarray,
        lon_grid: np.ndarray,
        lat_grid: np.ndarray,
        z_grid: np.ndarray,
    ) -> np.ndarray:
        cuda = self.cuda
        N = len(lons)

        if N > self.max_batch:
            results = []
            for start in range(0, N, self.max_batch):
                end = min(start + self.max_batch, N)
                results.append(
                    self.trilinear_batch(
                        var_3d, lons[start:end], lats[start:end],
                        zs[start:end], lon_grid, lat_grid, z_grid,
                    )
                )
            return np.concatenate(results)

        d_var = cuda.to_device(np.ascontiguousarray(var_3d, dtype=np.float64))
        d_lons = cuda.to_device(np.ascontiguousarray(lons, dtype=np.float64))
        d_lats = cuda.to_device(np.ascontiguousarray(lats, dtype=np.float64))
        d_zs = cuda.to_device(np.ascontiguousarray(zs, dtype=np.float64))
        d_lon_g = cuda.to_device(np.ascontiguousarray(lon_grid, dtype=np.float64))
        d_lat_g = cuda.to_device(np.ascontiguousarray(lat_grid, dtype=np.float64))
        d_z_g = cuda.to_device(np.ascontiguousarray(z_grid, dtype=np.float64))
        d_out = cuda.device_array(N, dtype=np.float64)

        threads = 256
        blocks = (N + threads - 1) // threads
        self._trilinear_kernel[blocks, threads](
            d_var, d_lons, d_lats, d_zs,
            d_lon_g, d_lat_g, d_z_g,
            len(lon_grid), len(lat_grid), len(z_grid),
            d_out,
        )
        return d_out.copy_to_host()

    def heun_step_batch(
        self,
        lons: np.ndarray,
        lats: np.ndarray,
        zs: np.ndarray,
        t: float,
        dt: float,
        met: MetData,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Heun step using Numba CUDA kernels for interpolation,
        with NumPy for the advection arithmetic."""
        lon_grid = met.lon_grid
        lat_grid = met.lat_grid
        z_grid = met.z_grid
        t_grid = met.t_grid

        def _interp_4d(lo, la, z_, time):
            it = int(np.searchsorted(t_grid, time, side="right")) - 1
            it = min(max(it, 0), len(t_grid) - 2)
            dt_frac = (time - t_grid[it]) / (t_grid[it + 1] - t_grid[it])
            u = (self.trilinear_batch(met.u[it], lo, la, z_, lon_grid, lat_grid, z_grid) * (1 - dt_frac)
                 + self.trilinear_batch(met.u[it + 1], lo, la, z_, lon_grid, lat_grid, z_grid) * dt_frac)
            v = (self.trilinear_batch(met.v[it], lo, la, z_, lon_grid, lat_grid, z_grid) * (1 - dt_frac)
                 + self.trilinear_batch(met.v[it + 1], lo, la, z_, lon_grid, lat_grid, z_grid) * dt_frac)
            w = (self.trilinear_batch(met.w[it], lo, la, z_, lon_grid, lat_grid, z_grid) * (1 - dt_frac)
                 + self.trilinear_batch(met.w[it + 1], lo, la, z_, lon_grid, lat_grid, z_grid) * dt_frac)
            return u, v, w

        def _advect(lo, la, u, v, dt_):
            lat_rad = np.deg2rad(la)
            cos_lat = np.cos(lat_rad)
            cos_lat = np.where(np.abs(cos_lat) < 1e-10, 1e-10, cos_lat)
            dlat_rad = (v * dt_) / EARTH_RADIUS
            dlon_rad = (u * dt_) / (EARTH_RADIUS * cos_lat)
            return lo + np.rad2deg(dlon_rad), la + np.rad2deg(dlat_rad)

        # Predictor
        u1, v1, w1 = _interp_4d(lons, lats, zs, t)
        lon_p, lat_p = _advect(lons, lats, u1, v1, dt)
        z_p = zs + w1 * dt

        # Corrector
        u2, v2, w2 = _interp_4d(lon_p, lat_p, z_p, t + dt)

        u_avg = 0.5 * (u1 + u2)
        v_avg = 0.5 * (v1 + v2)
        w_avg = 0.5 * (w1 + w2)

        lon_new, lat_new = _advect(lons, lats, u_avg, v_avg, dt)
        z_new = zs + w_avg * dt

        return lon_new, lat_new, z_new


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_backend(prefer_gpu: bool = True) -> ComputeBackend:
    """Return the best available compute backend.

    Selection order when *prefer_gpu* is True:
        1. CuPyBackend  (requires ``cupy``)
        2. NumbaGPUBackend  (requires ``numba`` + CUDA device)
        3. NumpyBackend  (always available)

    When *prefer_gpu* is False, returns NumpyBackend directly.
    """
    if prefer_gpu:
        try:
            backend = CuPyBackend()
            logger.info("Using CuPy GPU backend")
            return backend
        except (ImportError, Exception):
            pass
        try:
            backend = NumbaGPUBackend()
            logger.info("Using Numba CUDA GPU backend")
            return backend
        except (ImportError, Exception):
            pass
        warnings.warn(
            "GPU not available — falling back to CPU (NumPy) backend.",
            stacklevel=2,
        )
    logger.info("Using NumPy CPU backend")
    return NumpyBackend()
