"""Vectorized trajectory engine for batch particle processing.

Phase 3 optimization: Process multiple particles simultaneously using
vectorized operations and optional GPU acceleration.

Expected speedup: 10-100x for large batches (100+ particles)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from pyhysplit.core.models import MetData, SimulationConfig

from pyhysplit.core.interpolator_optimized import CachedInterpolator
from pyhysplit.core.models import BoundaryError

logger = logging.getLogger(__name__)

# Try to import CuPy for GPU acceleration
try:
    import cupy as cp
    GPU_AVAILABLE = True
except ImportError:
    cp = np
    GPU_AVAILABLE = False


class VectorizedEngine:
    """Vectorized trajectory engine for batch particle processing.
    
    Processes multiple particles simultaneously using vectorized operations.
    Automatically uses GPU if available and beneficial.
    
    Parameters
    ----------
    config : SimulationConfig
        Simulation configuration.
    met : MetData
        Meteorological data.
    use_gpu : bool, optional
        Force GPU usage. If None, automatically decides based on problem size.
    
    Attributes
    ----------
    backend : module
        NumPy or CuPy depending on GPU availability and selection.
    """
    
    def __init__(
        self,
        config: SimulationConfig,
        met: MetData,
        use_gpu: bool | None = None
    ) -> None:
        self.config = config
        self.met = met
        self.interpolator = CachedInterpolator(met)
        
        # Decide on GPU usage
        if use_gpu is None:
            # Auto-decide: use GPU for large batches if available
            n_particles = config.num_start_locations
            use_gpu = GPU_AVAILABLE and n_particles >= 10
        elif use_gpu and not GPU_AVAILABLE:
            logger.warning("GPU requested but not available, falling back to CPU")
            use_gpu = False
        
        self.use_gpu = use_gpu
        self.backend = cp if use_gpu else np
        
        if use_gpu:
            logger.info(f"Using GPU acceleration for {config.num_start_locations} particles")
        else:
            logger.info(f"Using CPU for {config.num_start_locations} particles")
    
    def run_batch(
        self,
        start_lons: np.ndarray,
        start_lats: np.ndarray,
        start_zs: np.ndarray,
        dt: float = 60.0,
        output_interval_s: float = 3600.0
    ) -> list[list[tuple[float, float, float, float]]]:
        """Run trajectories for multiple particles simultaneously.
        
        Parameters
        ----------
        start_lons : np.ndarray
            Starting longitudes, shape (n_particles,).
        start_lats : np.ndarray
            Starting latitudes, shape (n_particles,).
        start_zs : np.ndarray
            Starting vertical coordinates, shape (n_particles,).
        dt : float
            Integration time step in seconds.
        output_interval_s : float
            Output interval in seconds.
        
        Returns
        -------
        list[list[tuple[float, float, float, float]]]
            List of trajectories, one per particle.
            Each trajectory is a list of (time, lon, lat, z) tuples.
        """
        n_particles = len(start_lons)
        
        # Transfer to GPU if needed
        if self.use_gpu:
            lons = cp.array(start_lons)
            lats = cp.array(start_lats)
            zs = cp.array(start_zs)
        else:
            lons = start_lons.copy()
            lats = start_lats.copy()
            zs = start_zs.copy()
        
        # Initialize trajectories
        trajectories = [[] for _ in range(n_particles)]
        
        # Time parameters
        total_seconds = abs(self.config.total_run_hours * 3600.0)
        direction = -1 if self.config.total_run_hours < 0 else 1
        dt_signed = dt * direction
        
        # Active particle mask
        active = self.backend.ones(n_particles, dtype=bool)
        
        # Main integration loop
        t = 0.0
        next_output = 0.0
        step = 0
        
        while t < total_seconds and self.backend.any(active):
            # Output current positions
            if t >= next_output:
                self._output_positions(trajectories, t * direction, lons, lats, zs, active)
                next_output += output_interval_s
            
            # Integrate active particles
            if self.backend.any(active):
                try:
                    lons, lats, zs, active = self._step_batch(
                        lons, lats, zs, t * direction, dt_signed, active
                    )
                except BoundaryError:
                    # Some particles hit boundary
                    pass
            
            t += dt
            step += 1
        
        # Final output
        self._output_positions(trajectories, t * direction, lons, lats, zs, active)
        
        logger.info(f"Completed {n_particles} trajectories in {step} steps")
        
        return trajectories
    
    def _step_batch(
        self,
        lons: np.ndarray,
        lats: np.ndarray,
        zs: np.ndarray,
        t: float,
        dt: float,
        active: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Perform one integration step for all active particles.
        
        Uses Heun's method (RK2) for integration.
        
        Returns
        -------
        tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]
            Updated (lons, lats, zs, active).
        """
        # Get active indices
        active_idx = self.backend.where(active)[0]
        
        if len(active_idx) == 0:
            return lons, lats, zs, active
        
        # Extract active particles
        lons_active = lons[active_idx]
        lats_active = lats[active_idx]
        zs_active = zs[active_idx]
        
        # Heun's method (RK2)
        # Step 1: Euler predictor
        try:
            u1, v1, w1 = self._interpolate_batch(lons_active, lats_active, zs_active, t)
            
            # Convert to position changes
            dlons1, dlats1, dzs1 = self._wind_to_displacement(
                u1, v1, w1, lats_active, dt
            )
            
            # Predicted positions
            lons_pred = lons_active + dlons1
            lats_pred = lats_active + dlats1
            zs_pred = zs_active + dzs1
            
            # Step 2: Corrector
            u2, v2, w2 = self._interpolate_batch(lons_pred, lats_pred, zs_pred, t + dt)
            
            dlons2, dlats2, dzs2 = self._wind_to_displacement(
                u2, v2, w2, lats_pred, dt
            )
            
            # Average slopes
            dlons_avg = (dlons1 + dlons2) / 2.0
            dlats_avg = (dlats1 + dlats2) / 2.0
            dzs_avg = (dzs1 + dzs2) / 2.0
            
            # Update positions
            lons_new = lons_active + dlons_avg
            lats_new = lats_active + dlats_avg
            zs_new = zs_active + dzs_avg
            
            # Check boundaries
            valid = self._check_boundaries(lons_new, lats_new, zs_new)
            
            # Update only valid particles
            lons[active_idx[valid]] = lons_new[valid]
            lats[active_idx[valid]] = lats_new[valid]
            zs[active_idx[valid]] = zs_new[valid]
            
            # Deactivate invalid particles
            active[active_idx[~valid]] = False
            
        except BoundaryError:
            # Deactivate all active particles
            active[active_idx] = False
        
        return lons, lats, zs, active
    
    def _interpolate_batch(
        self,
        lons: np.ndarray,
        lats: np.ndarray,
        zs: np.ndarray,
        t: float
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Interpolate wind for multiple particles.
        
        Returns
        -------
        tuple[np.ndarray, np.ndarray, np.ndarray]
            (u, v, w) wind components for each particle.
        """
        n = len(lons)
        u = self.backend.zeros(n)
        v = self.backend.zeros(n)
        w = self.backend.zeros(n)
        
        # Transfer to CPU for interpolation (CachedInterpolator is CPU-only)
        if self.use_gpu:
            lons_cpu = cp.asnumpy(lons)
            lats_cpu = cp.asnumpy(lats)
            zs_cpu = cp.asnumpy(zs)
        else:
            lons_cpu = lons
            lats_cpu = lats
            zs_cpu = zs
        
        # Interpolate each particle
        for i in range(n):
            try:
                u_i, v_i, w_i = self.interpolator.interpolate_4d(
                    float(lons_cpu[i]),
                    float(lats_cpu[i]),
                    float(zs_cpu[i]),
                    t
                )
                u[i] = u_i
                v[i] = v_i
                w[i] = w_i
            except BoundaryError:
                # Particle outside domain
                u[i] = 0.0
                v[i] = 0.0
                w[i] = 0.0
        
        return u, v, w
    
    def _wind_to_displacement(
        self,
        u: np.ndarray,
        v: np.ndarray,
        w: np.ndarray,
        lats: np.ndarray,
        dt: float
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Convert wind components to position displacements.
        
        Returns
        -------
        tuple[np.ndarray, np.ndarray, np.ndarray]
            (dlon, dlat, dz) displacements.
        """
        # Earth radius
        R = 6_371_000.0
        
        # Convert u, v (m/s) to degrees
        dlon = u * dt / (R * self.backend.cos(self.backend.radians(lats))) * 180.0 / self.backend.pi
        dlat = v * dt / R * 180.0 / self.backend.pi
        
        # Vertical displacement (pressure or height)
        if self.met.z_type == "pressure":
            # w is in hPa/s, convert to hPa
            dz = w * dt
        else:
            # w is in m/s, convert to m
            dz = w * dt
        
        return dlon, dlat, dz
    
    def _check_boundaries(
        self,
        lons: np.ndarray,
        lats: np.ndarray,
        zs: np.ndarray
    ) -> np.ndarray:
        """Check if particles are within domain boundaries.
        
        Returns
        -------
        np.ndarray
            Boolean mask of valid particles.
        """
        lon_min, lon_max = self.met.lon_grid[0], self.met.lon_grid[-1]
        lat_min, lat_max = self.met.lat_grid[0], self.met.lat_grid[-1]
        z_min, z_max = self.met.z_grid[0], self.met.z_grid[-1]
        
        valid = (
            (lons >= lon_min) & (lons <= lon_max) &
            (lats >= lat_min) & (lats <= lat_max) &
            (zs >= z_min) & (zs <= z_max)
        )
        
        return valid
    
    def _output_positions(
        self,
        trajectories: list[list[tuple[float, float, float, float]]],
        t: float,
        lons: np.ndarray,
        lats: np.ndarray,
        zs: np.ndarray,
        active: np.ndarray
    ) -> None:
        """Output current positions to trajectories.
        
        Parameters
        ----------
        trajectories : list[list[tuple]]
            List of trajectories to append to.
        t : float
            Current time.
        lons, lats, zs : np.ndarray
            Current positions.
        active : np.ndarray
            Active particle mask.
        """
        # Transfer from GPU if needed
        if self.use_gpu:
            lons_cpu = cp.asnumpy(lons)
            lats_cpu = cp.asnumpy(lats)
            zs_cpu = cp.asnumpy(zs)
            active_cpu = cp.asnumpy(active)
        else:
            lons_cpu = lons
            lats_cpu = lats
            zs_cpu = zs
            active_cpu = active
        
        # Append to trajectories
        for i, traj in enumerate(trajectories):
            if active_cpu[i]:
                traj.append((t, float(lons_cpu[i]), float(lats_cpu[i]), float(zs_cpu[i])))
