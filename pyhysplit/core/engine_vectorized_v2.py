"""Improved vectorized engine with batch interpolation.

Phase 3+ optimization: Uses BatchInterpolator for true vectorization.

Expected speedup: 50-100x for large batches with GPU
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from pyhysplit.core.models import MetData, SimulationConfig

from pyhysplit.core.interpolator_gpu import BatchInterpolator, GPU_AVAILABLE
from pyhysplit.core.models import BoundaryError

logger = logging.getLogger(__name__)


class VectorizedEngineV2:
    """Improved vectorized trajectory engine with batch interpolation.
    
    Key improvements over V1:
    - Uses BatchInterpolator for true vectorized interpolation
    - Eliminates per-particle interpolation loop
    - Full GPU acceleration when available
    
    Expected speedup: 10-20x (CPU), 50-100x (GPU) for large batches
    
    Parameters
    ----------
    config : SimulationConfig
        Simulation configuration.
    met : MetData
        Meteorological data.
    use_gpu : bool, optional
        Force GPU usage. If None, automatically decides.
    """
    
    def __init__(
        self,
        config: SimulationConfig,
        met: MetData,
        use_gpu: bool | None = None
    ) -> None:
        self.config = config
        self.met = met
        
        # Decide on GPU usage
        if use_gpu is None:
            n_particles = config.num_start_locations
            use_gpu = GPU_AVAILABLE and n_particles >= 50
        elif use_gpu and not GPU_AVAILABLE:
            logger.warning("GPU requested but not available, falling back to CPU")
            use_gpu = False
        
        self.use_gpu = use_gpu
        
        # Create batch interpolator
        self.interpolator = BatchInterpolator(met, use_gpu=use_gpu)
        
        if use_gpu:
            logger.info(f"VectorizedEngineV2 using GPU for {config.num_start_locations} particles")
        else:
            logger.info(f"VectorizedEngineV2 using CPU for {config.num_start_locations} particles")
    
    def run_batch(
        self,
        start_lons: np.ndarray,
        start_lats: np.ndarray,
        start_zs: np.ndarray,
        dt: float = 60.0,
        output_interval_s: float = 3600.0
    ) -> list[list[tuple[float, float, float, float]]]:
        """Run trajectories for multiple particles with batch interpolation.
        
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
        """
        n_particles = len(start_lons)
        
        # Initialize positions
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
        active = np.ones(n_particles, dtype=bool)
        
        # Main integration loop
        t = 0.0
        next_output = 0.0
        step = 0
        
        while t < total_seconds and np.any(active):
            # Output current positions
            if t >= next_output:
                self._output_positions(trajectories, t * direction, lons, lats, zs, active)
                next_output += output_interval_s
            
            # Integrate active particles using batch interpolation
            if np.any(active):
                try:
                    lons, lats, zs, active = self._step_batch(
                        lons, lats, zs, t * direction, dt_signed, active
                    )
                except BoundaryError:
                    # Some particles hit boundary
                    pass
            
            t += dt
            step += 1
            
            # Progress logging
            if step % 100 == 0 and logger.isEnabledFor(logging.INFO):
                n_active = np.sum(active)
                logger.info(f"Step {step}: {n_active}/{n_particles} particles active")
        
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
        """Perform one integration step using batch interpolation.
        
        This is the key optimization: interpolate all active particles at once
        instead of looping through them.
        """
        # Get active indices
        active_idx = np.where(active)[0]
        
        if len(active_idx) == 0:
            return lons, lats, zs, active
        
        # Extract active particles
        lons_active = lons[active_idx]
        lats_active = lats[active_idx]
        zs_active = zs[active_idx]
        
        try:
            # Heun's method (RK2) with batch interpolation
            # Step 1: Euler predictor
            u1, v1, w1 = self.interpolator.interpolate_batch(
                lons_active, lats_active, zs_active, t
            )
            
            # Convert to position changes
            dlons1, dlats1, dzs1 = self._wind_to_displacement(
                u1, v1, w1, lats_active, dt
            )
            
            # Predicted positions
            lons_pred = lons_active + dlons1
            lats_pred = lats_active + dlats1
            zs_pred = zs_active + dzs1
            
            # Step 2: Corrector (batch interpolation)
            u2, v2, w2 = self.interpolator.interpolate_batch(
                lons_pred, lats_pred, zs_pred, t + dt
            )
            
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
    
    def _wind_to_displacement(
        self,
        u: np.ndarray,
        v: np.ndarray,
        w: np.ndarray,
        lats: np.ndarray,
        dt: float
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Convert wind components to position displacements."""
        R = 6_371_000.0  # Earth radius
        
        # Convert u, v (m/s) to degrees
        dlon = u * dt / (R * np.cos(np.radians(lats))) * 180.0 / np.pi
        dlat = v * dt / R * 180.0 / np.pi
        
        # Vertical displacement
        if self.met.z_type == "pressure":
            dz = w * dt  # w in hPa/s
        else:
            dz = w * dt  # w in m/s
        
        return dlon, dlat, dz
    
    def _check_boundaries(
        self,
        lons: np.ndarray,
        lats: np.ndarray,
        zs: np.ndarray
    ) -> np.ndarray:
        """Check if particles are within domain boundaries."""
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
        """Output current positions to trajectories."""
        for i, traj in enumerate(trajectories):
            if active[i]:
                traj.append((t, float(lons[i]), float(lats[i]), float(zs[i])))
