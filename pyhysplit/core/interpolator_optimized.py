"""Optimized interpolation with grid index caching and Numba JIT.

Phase 2 optimizations:
- Grid index caching: Reuse spatial indices when particle stays in same cell
- Numba JIT compilation: Compile hot functions to machine code

Expected speedup: 2-5x over Phase 1
"""

from __future__ import annotations

import numpy as np

from pyhysplit.core.interpolator import Interpolator
from pyhysplit.core.models import BoundaryError, MetData

# Try to import numba, fall back to regular Python if not available
try:
    from numba import jit
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    # Dummy decorator that does nothing
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


class CachedInterpolator(Interpolator):
    """Interpolator with grid index caching for improved performance.
    
    Caches spatial grid indices (i, j, k) between interpolation calls.
    When a particle moves within the same grid cell, indices are reused,
    avoiding expensive searchsorted operations.
    
    Expected speedup: 2x over base Interpolator for typical trajectories.
    """
    
    def __init__(self, met: MetData) -> None:
        super().__init__(met)
        # Cache for spatial grid indices
        self._cached_lon: float | None = None
        self._cached_lat: float | None = None
        self._cached_z: float | None = None
        self._cached_i: int | None = None
        self._cached_j: int | None = None
        self._cached_k: int | None = None
        
        # Pre-compute grid bounds for fast checking
        self._lon_min = float(met.lon_grid[0])
        self._lon_max = float(met.lon_grid[-1])
        self._lat_min = float(met.lat_grid[0])
        self._lat_max = float(met.lat_grid[-1])
        self._z_min = float(met.z_grid[0])
        self._z_max = float(met.z_grid[-1])
    
    def _find_grid_indices(
        self, lon: float, lat: float, z: float
    ) -> tuple[int, int, int, float, float, float]:
        """Find grid cell indices and fractional distances.
        
        Uses cached indices if position is in same cell as last query.
        
        Returns
        -------
        tuple[int, int, int, float, float, float]
            (i, j, k, xd, yd, zd) where i,j,k are cell indices and
            xd,yd,zd are fractional distances within the cell.
        """
        lon_grid = self.met.lon_grid
        lat_grid = self.met.lat_grid
        z_grid = self.met.z_grid
        
        # Check if we can reuse cached indices
        if (self._cached_i is not None and
            self._cached_lon is not None and
            self._cached_lat is not None and
            self._cached_z is not None):
            
            i, j, k = self._cached_i, self._cached_j, self._cached_k
            
            # Check if position is still in same cell
            if (lon_grid[i] <= lon <= lon_grid[i + 1] and
                lat_grid[j] <= lat <= lat_grid[j + 1] and
                z_grid[k] <= z <= z_grid[k + 1]):
                
                # Reuse cached indices, just recompute fractional distances
                xd = (lon - lon_grid[i]) / (lon_grid[i + 1] - lon_grid[i])
                yd = (lat - lat_grid[j]) / (lat_grid[j + 1] - lat_grid[j])
                zd = (z - z_grid[k]) / (z_grid[k + 1] - z_grid[k])
                
                return i, j, k, xd, yd, zd
        
        # Cache miss - need to search for new indices
        i = int(np.searchsorted(lon_grid, lon, side="right")) - 1
        j = int(np.searchsorted(lat_grid, lat, side="right")) - 1
        k = int(np.searchsorted(z_grid, z, side="right")) - 1
        
        # Clamp to valid range
        i = min(max(0, i), len(lon_grid) - 2)
        j = min(max(0, j), len(lat_grid) - 2)
        k = min(max(0, k), len(z_grid) - 2)
        
        # Update cache
        self._cached_lon = lon
        self._cached_lat = lat
        self._cached_z = z
        self._cached_i = i
        self._cached_j = j
        self._cached_k = k
        
        # Compute fractional distances
        xd = (lon - lon_grid[i]) / (lon_grid[i + 1] - lon_grid[i])
        yd = (lat - lat_grid[j]) / (lat_grid[j + 1] - lat_grid[j])
        zd = (z - z_grid[k]) / (z_grid[k + 1] - z_grid[k])
        
        return i, j, k, xd, yd, zd
    
    def trilinear(
        self, var_3d: np.ndarray, lon: float, lat: float, z: float
    ) -> float:
        """Trilinear interpolation with grid index caching."""
        # Boundary check
        if (lon < self._lon_min or lon > self._lon_max or
            lat < self._lat_min or lat > self._lat_max or
            z < self._z_min or z > self._z_max):
            raise BoundaryError(
                f"Position ({lon}, {lat}, {z}) outside grid"
            )
        
        # Get indices (possibly from cache)
        i, j, k, xd, yd, zd = self._find_grid_indices(lon, lat, z)
        
        # Use JIT-compiled interpolation if available
        if NUMBA_AVAILABLE:
            return trilinear_numba(var_3d, i, j, k, xd, yd, zd)
        else:
            return trilinear_python(var_3d, i, j, k, xd, yd, zd)


# ------------------------------------------------------------------
# JIT-compiled interpolation functions
# ------------------------------------------------------------------

@jit(nopython=True, cache=True)
def trilinear_numba(
    var_3d: np.ndarray,
    i: int, j: int, k: int,
    xd: float, yd: float, zd: float
) -> float:
    """JIT-compiled trilinear interpolation.
    
    This function is compiled to machine code by Numba for maximum performance.
    Expected speedup: 2-3x over pure Python.
    
    Parameters
    ----------
    var_3d : np.ndarray
        3-D field with shape (nz, nlat, nlon).
    i, j, k : int
        Grid cell indices.
    xd, yd, zd : float
        Fractional distances within cell (0 to 1).
    
    Returns
    -------
    float
        Interpolated value.
    """
    # x-direction interpolation (4 pairs)
    c00 = var_3d[k,   j,   i] * (1.0 - xd) + var_3d[k,   j,   i + 1] * xd
    c01 = var_3d[k,   j + 1, i] * (1.0 - xd) + var_3d[k,   j + 1, i + 1] * xd
    c10 = var_3d[k + 1, j,   i] * (1.0 - xd) + var_3d[k + 1, j,   i + 1] * xd
    c11 = var_3d[k + 1, j + 1, i] * (1.0 - xd) + var_3d[k + 1, j + 1, i + 1] * xd
    
    # y-direction interpolation (2 pairs)
    c0 = c00 * (1.0 - yd) + c01 * yd
    c1 = c10 * (1.0 - yd) + c11 * yd
    
    # z-direction interpolation
    return c0 * (1.0 - zd) + c1 * zd


def trilinear_python(
    var_3d: np.ndarray,
    i: int, j: int, k: int,
    xd: float, yd: float, zd: float
) -> float:
    """Pure Python trilinear interpolation (fallback when Numba not available)."""
    # x-direction interpolation (4 pairs)
    c00 = var_3d[k,   j,   i] * (1.0 - xd) + var_3d[k,   j,   i + 1] * xd
    c01 = var_3d[k,   j + 1, i] * (1.0 - xd) + var_3d[k,   j + 1, i + 1] * xd
    c10 = var_3d[k + 1, j,   i] * (1.0 - xd) + var_3d[k + 1, j,   i + 1] * xd
    c11 = var_3d[k + 1, j + 1, i] * (1.0 - xd) + var_3d[k + 1, j + 1, i + 1] * xd
    
    # y-direction interpolation (2 pairs)
    c0 = c00 * (1.0 - yd) + c01 * yd
    c1 = c10 * (1.0 - yd) + c11 * yd
    
    # z-direction interpolation
    return float(c0 * (1.0 - zd) + c1 * zd)


# ------------------------------------------------------------------
# Vectorized interpolation for batch processing
# ------------------------------------------------------------------

@jit(nopython=True, parallel=True, cache=True)
def trilinear_batch_numba(
    var_3d: np.ndarray,
    indices: np.ndarray,  # shape (n, 3) - i, j, k for each point
    fracs: np.ndarray,    # shape (n, 3) - xd, yd, zd for each point
    out: np.ndarray       # shape (n,) - output array
) -> None:
    """Vectorized trilinear interpolation for multiple points.
    
    This function processes multiple interpolation points in parallel using Numba.
    Expected speedup: 5-10x over sequential interpolation for large batches.
    
    Parameters
    ----------
    var_3d : np.ndarray
        3-D field with shape (nz, nlat, nlon).
    indices : np.ndarray
        Grid cell indices, shape (n, 3) where each row is [i, j, k].
    fracs : np.ndarray
        Fractional distances, shape (n, 3) where each row is [xd, yd, zd].
    out : np.ndarray
        Output array, shape (n,). Modified in-place.
    """
    n = indices.shape[0]
    
    for idx in range(n):
        i = indices[idx, 0]
        j = indices[idx, 1]
        k = indices[idx, 2]
        xd = fracs[idx, 0]
        yd = fracs[idx, 1]
        zd = fracs[idx, 2]
        
        # x-direction interpolation
        c00 = var_3d[k,   j,   i] * (1.0 - xd) + var_3d[k,   j,   i + 1] * xd
        c01 = var_3d[k,   j + 1, i] * (1.0 - xd) + var_3d[k,   j + 1, i + 1] * xd
        c10 = var_3d[k + 1, j,   i] * (1.0 - xd) + var_3d[k + 1, j,   i + 1] * xd
        c11 = var_3d[k + 1, j + 1, i] * (1.0 - xd) + var_3d[k + 1, j + 1, i + 1] * xd
        
        # y-direction interpolation
        c0 = c00 * (1.0 - yd) + c01 * yd
        c1 = c10 * (1.0 - yd) + c11 * yd
        
        # z-direction interpolation
        out[idx] = c0 * (1.0 - zd) + c1 * zd
