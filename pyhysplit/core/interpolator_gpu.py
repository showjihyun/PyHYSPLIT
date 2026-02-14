"""GPU-accelerated interpolation with batch processing.

Phase 3+ optimization: GPU-native interpolation kernels and batch processing
for maximum performance.

Expected speedup: 50-100x for large batches (1000+ particles)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from pyhysplit.core.models import MetData

from pyhysplit.core.interpolator_optimized import CachedInterpolator
from pyhysplit.core.models import BoundaryError

logger = logging.getLogger(__name__)

# Try to import CuPy for GPU acceleration
try:
    import cupy as cp
    GPU_AVAILABLE = True
except ImportError:
    cp = None
    GPU_AVAILABLE = False

# Try to import Numba for JIT compilation
try:
    from numba import cuda, jit
    CUDA_AVAILABLE = cuda.is_available() if GPU_AVAILABLE else False
except ImportError:
    cuda = None
    CUDA_AVAILABLE = False


class BatchInterpolator(CachedInterpolator):
    """Batch interpolator with GPU acceleration.
    
    Processes multiple interpolation points simultaneously using vectorized
    operations and optional GPU acceleration.
    
    Parameters
    ----------
    met : MetData
        Meteorological data.
    use_gpu : bool, optional
        Use GPU if available. Default is auto-detect.
    
    Attributes
    ----------
    use_gpu : bool
        Whether GPU is being used.
    backend : module
        NumPy or CuPy depending on GPU usage.
    """
    
    def __init__(self, met: MetData, use_gpu: bool | None = None) -> None:
        super().__init__(met)
        
        # Decide on GPU usage
        if use_gpu is None:
            use_gpu = GPU_AVAILABLE
        elif use_gpu and not GPU_AVAILABLE:
            logger.warning("GPU requested but CuPy not available, using CPU")
            use_gpu = False
        
        self.use_gpu = use_gpu
        self.backend = cp if use_gpu else np
        
        # Transfer met data to GPU if needed
        if use_gpu:
            self._transfer_to_gpu()
        
        logger.info(f"BatchInterpolator initialized (GPU: {use_gpu})")
    
    def _transfer_to_gpu(self) -> None:
        """Transfer meteorological data to GPU memory."""
        if not self.use_gpu:
            return
        
        logger.info("Transferring met data to GPU...")
        
        # Transfer wind fields
        self.met_gpu = type('MetDataGPU', (), {})()
        self.met_gpu.u = cp.asarray(self.met.u)
        self.met_gpu.v = cp.asarray(self.met.v)
        self.met_gpu.w = cp.asarray(self.met.w)
        
        # Transfer grids
        self.met_gpu.lon_grid = cp.asarray(self.met.lon_grid)
        self.met_gpu.lat_grid = cp.asarray(self.met.lat_grid)
        self.met_gpu.z_grid = cp.asarray(self.met.z_grid)
        self.met_gpu.t_grid = cp.asarray(self.met.t_grid)
        
        logger.info("Met data transferred to GPU")
    
    def interpolate_batch(
        self,
        lons: np.ndarray,
        lats: np.ndarray,
        zs: np.ndarray,
        t: float
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Interpolate wind for multiple points simultaneously.
        
        This is the key optimization: process all points in parallel instead
        of looping through them one by one.
        
        Parameters
        ----------
        lons : np.ndarray
            Longitudes, shape (n,).
        lats : np.ndarray
            Latitudes, shape (n,).
        zs : np.ndarray
            Vertical coordinates, shape (n,).
        t : float
            Time in seconds.
        
        Returns
        -------
        tuple[np.ndarray, np.ndarray, np.ndarray]
            (u, v, w) wind components for each point, shape (n,).
        """
        n = len(lons)
        
        if self.use_gpu:
            return self._interpolate_batch_gpu(lons, lats, zs, t)
        else:
            return self._interpolate_batch_cpu(lons, lats, zs, t)
    
    def _interpolate_batch_cpu(
        self,
        lons: np.ndarray,
        lats: np.ndarray,
        zs: np.ndarray,
        t: float
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """CPU batch interpolation using vectorized NumPy operations."""
        n = len(lons)
        
        # Find time indices (same for all points)
        t_grid = self.met.t_grid
        if t < t_grid[0] or t > t_grid[-1]:
            raise BoundaryError(f"Time {t} outside range")
        
        it = int(np.searchsorted(t_grid, t, side="right")) - 1
        it = min(it, len(t_grid) - 2)
        dt_frac = (t - t_grid[it]) / (t_grid[it + 1] - t_grid[it])
        
        # Get time slices
        u_t0 = self.met.u[it]
        u_t1 = self.met.u[it + 1]
        v_t0 = self.met.v[it]
        v_t1 = self.met.v[it + 1]
        w_t0 = self.met.w[it]
        w_t1 = self.met.w[it + 1]
        
        # Find spatial indices for all points (vectorized)
        lon_grid = self.met.lon_grid
        lat_grid = self.met.lat_grid
        z_grid = self.met.z_grid
        
        # Boundary check
        valid = (
            (lons >= lon_grid[0]) & (lons <= lon_grid[-1]) &
            (lats >= lat_grid[0]) & (lats <= lat_grid[-1]) &
            (zs >= z_grid[0]) & (zs <= z_grid[-1])
        )
        
        if not np.all(valid):
            raise BoundaryError("Some points outside grid")
        
        # Find grid cell indices (vectorized searchsorted)
        i_indices = np.searchsorted(lon_grid, lons, side="right") - 1
        j_indices = np.searchsorted(lat_grid, lats, side="right") - 1
        k_indices = np.searchsorted(z_grid, zs, side="right") - 1
        
        # Clamp to valid range
        i_indices = np.clip(i_indices, 0, len(lon_grid) - 2)
        j_indices = np.clip(j_indices, 0, len(lat_grid) - 2)
        k_indices = np.clip(k_indices, 0, len(z_grid) - 2)
        
        # Compute fractional distances (vectorized)
        xd = (lons - lon_grid[i_indices]) / (lon_grid[i_indices + 1] - lon_grid[i_indices])
        yd = (lats - lat_grid[j_indices]) / (lat_grid[j_indices + 1] - lat_grid[j_indices])
        zd = (zs - z_grid[k_indices]) / (z_grid[k_indices + 1] - z_grid[k_indices])
        
        # Batch trilinear interpolation
        u_t0_interp = self._trilinear_batch_cpu(u_t0, i_indices, j_indices, k_indices, xd, yd, zd)
        u_t1_interp = self._trilinear_batch_cpu(u_t1, i_indices, j_indices, k_indices, xd, yd, zd)
        v_t0_interp = self._trilinear_batch_cpu(v_t0, i_indices, j_indices, k_indices, xd, yd, zd)
        v_t1_interp = self._trilinear_batch_cpu(v_t1, i_indices, j_indices, k_indices, xd, yd, zd)
        w_t0_interp = self._trilinear_batch_cpu(w_t0, i_indices, j_indices, k_indices, xd, yd, zd)
        w_t1_interp = self._trilinear_batch_cpu(w_t1, i_indices, j_indices, k_indices, xd, yd, zd)
        
        # Temporal interpolation
        u = u_t0_interp * (1 - dt_frac) + u_t1_interp * dt_frac
        v = v_t0_interp * (1 - dt_frac) + v_t1_interp * dt_frac
        w = w_t0_interp * (1 - dt_frac) + w_t1_interp * dt_frac
        
        return u, v, w
    
    def _trilinear_batch_cpu(
        self,
        var_3d: np.ndarray,
        i_indices: np.ndarray,
        j_indices: np.ndarray,
        k_indices: np.ndarray,
        xd: np.ndarray,
        yd: np.ndarray,
        zd: np.ndarray
    ) -> np.ndarray:
        """Vectorized trilinear interpolation for multiple points.
        
        This is much faster than looping through points one by one.
        """
        # Extract corner values (vectorized indexing)
        c000 = var_3d[k_indices,     j_indices,     i_indices]
        c001 = var_3d[k_indices,     j_indices,     i_indices + 1]
        c010 = var_3d[k_indices,     j_indices + 1, i_indices]
        c011 = var_3d[k_indices,     j_indices + 1, i_indices + 1]
        c100 = var_3d[k_indices + 1, j_indices,     i_indices]
        c101 = var_3d[k_indices + 1, j_indices,     i_indices + 1]
        c110 = var_3d[k_indices + 1, j_indices + 1, i_indices]
        c111 = var_3d[k_indices + 1, j_indices + 1, i_indices + 1]
        
        # Trilinear interpolation (vectorized)
        c00 = c000 * (1 - xd) + c001 * xd
        c01 = c010 * (1 - xd) + c011 * xd
        c10 = c100 * (1 - xd) + c101 * xd
        c11 = c110 * (1 - xd) + c111 * xd
        
        c0 = c00 * (1 - yd) + c01 * yd
        c1 = c10 * (1 - yd) + c11 * yd
        
        result = c0 * (1 - zd) + c1 * zd
        
        return result
    
    def _interpolate_batch_gpu(
        self,
        lons: np.ndarray,
        lats: np.ndarray,
        zs: np.ndarray,
        t: float
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """GPU batch interpolation using CuPy."""
        # Transfer to GPU
        lons_gpu = cp.asarray(lons)
        lats_gpu = cp.asarray(lats)
        zs_gpu = cp.asarray(zs)
        
        # Find time indices
        t_grid = self.met_gpu.t_grid
        t_cpu = float(t)
        
        if t_cpu < float(t_grid[0]) or t_cpu > float(t_grid[-1]):
            raise BoundaryError(f"Time {t} outside range")
        
        it = int(cp.searchsorted(t_grid, t_cpu, side="right")) - 1
        it = min(it, len(t_grid) - 2)
        dt_frac = (t_cpu - float(t_grid[it])) / (float(t_grid[it + 1]) - float(t_grid[it]))
        
        # Get time slices (already on GPU)
        u_t0 = self.met_gpu.u[it]
        u_t1 = self.met_gpu.u[it + 1]
        v_t0 = self.met_gpu.v[it]
        v_t1 = self.met_gpu.v[it + 1]
        w_t0 = self.met_gpu.w[it]
        w_t1 = self.met_gpu.w[it + 1]
        
        # Find spatial indices (GPU operations)
        lon_grid = self.met_gpu.lon_grid
        lat_grid = self.met_gpu.lat_grid
        z_grid = self.met_gpu.z_grid
        
        # Boundary check
        valid = (
            (lons_gpu >= lon_grid[0]) & (lons_gpu <= lon_grid[-1]) &
            (lats_gpu >= lat_grid[0]) & (lats_gpu <= lat_grid[-1]) &
            (zs_gpu >= z_grid[0]) & (zs_gpu <= z_grid[-1])
        )
        
        if not cp.all(valid):
            raise BoundaryError("Some points outside grid")
        
        # Find grid cell indices (GPU searchsorted)
        i_indices = cp.searchsorted(lon_grid, lons_gpu, side="right") - 1
        j_indices = cp.searchsorted(lat_grid, lats_gpu, side="right") - 1
        k_indices = cp.searchsorted(z_grid, zs_gpu, side="right") - 1
        
        # Clamp to valid range
        i_indices = cp.clip(i_indices, 0, len(lon_grid) - 2)
        j_indices = cp.clip(j_indices, 0, len(lat_grid) - 2)
        k_indices = cp.clip(k_indices, 0, len(z_grid) - 2)
        
        # Compute fractional distances (GPU operations)
        xd = (lons_gpu - lon_grid[i_indices]) / (lon_grid[i_indices + 1] - lon_grid[i_indices])
        yd = (lats_gpu - lat_grid[j_indices]) / (lat_grid[j_indices + 1] - lat_grid[j_indices])
        zd = (zs_gpu - z_grid[k_indices]) / (z_grid[k_indices + 1] - z_grid[k_indices])
        
        # Batch trilinear interpolation (GPU)
        u_t0_interp = self._trilinear_batch_gpu(u_t0, i_indices, j_indices, k_indices, xd, yd, zd)
        u_t1_interp = self._trilinear_batch_gpu(u_t1, i_indices, j_indices, k_indices, xd, yd, zd)
        v_t0_interp = self._trilinear_batch_gpu(v_t0, i_indices, j_indices, k_indices, xd, yd, zd)
        v_t1_interp = self._trilinear_batch_gpu(v_t1, i_indices, j_indices, k_indices, xd, yd, zd)
        w_t0_interp = self._trilinear_batch_gpu(w_t0, i_indices, j_indices, k_indices, xd, yd, zd)
        w_t1_interp = self._trilinear_batch_gpu(w_t1, i_indices, j_indices, k_indices, xd, yd, zd)
        
        # Temporal interpolation (GPU)
        u_gpu = u_t0_interp * (1 - dt_frac) + u_t1_interp * dt_frac
        v_gpu = v_t0_interp * (1 - dt_frac) + v_t1_interp * dt_frac
        w_gpu = w_t0_interp * (1 - dt_frac) + w_t1_interp * dt_frac
        
        # Transfer back to CPU
        u = cp.asnumpy(u_gpu)
        v = cp.asnumpy(v_gpu)
        w = cp.asnumpy(w_gpu)
        
        return u, v, w
    
    def _trilinear_batch_gpu(
        self,
        var_3d: cp.ndarray,
        i_indices: cp.ndarray,
        j_indices: cp.ndarray,
        k_indices: cp.ndarray,
        xd: cp.ndarray,
        yd: cp.ndarray,
        zd: cp.ndarray
    ) -> cp.ndarray:
        """GPU-accelerated vectorized trilinear interpolation."""
        # Extract corner values (GPU indexing)
        c000 = var_3d[k_indices,     j_indices,     i_indices]
        c001 = var_3d[k_indices,     j_indices,     i_indices + 1]
        c010 = var_3d[k_indices,     j_indices + 1, i_indices]
        c011 = var_3d[k_indices,     j_indices + 1, i_indices + 1]
        c100 = var_3d[k_indices + 1, j_indices,     i_indices]
        c101 = var_3d[k_indices + 1, j_indices,     i_indices + 1]
        c110 = var_3d[k_indices + 1, j_indices + 1, i_indices]
        c111 = var_3d[k_indices + 1, j_indices + 1, i_indices + 1]
        
        # Trilinear interpolation (GPU operations)
        c00 = c000 * (1 - xd) + c001 * xd
        c01 = c010 * (1 - xd) + c011 * xd
        c10 = c100 * (1 - xd) + c101 * xd
        c11 = c110 * (1 - xd) + c111 * xd
        
        c0 = c00 * (1 - yd) + c01 * yd
        c1 = c10 * (1 - yd) + c11 * yd
        
        result = c0 * (1 - zd) + c1 * zd
        
        return result


def create_batch_interpolator(
    met: MetData,
    use_gpu: bool | None = None,
    min_batch_size: int = 10
) -> BatchInterpolator | CachedInterpolator:
    """Factory function to create appropriate interpolator.
    
    Parameters
    ----------
    met : MetData
        Meteorological data.
    use_gpu : bool, optional
        Force GPU usage. If None, auto-detect.
    min_batch_size : int
        Minimum batch size to use BatchInterpolator.
    
    Returns
    -------
    BatchInterpolator or CachedInterpolator
        Appropriate interpolator for the use case.
    """
    if use_gpu or (use_gpu is None and GPU_AVAILABLE):
        return BatchInterpolator(met, use_gpu=True)
    else:
        return BatchInterpolator(met, use_gpu=False)
