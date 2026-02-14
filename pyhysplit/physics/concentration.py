"""Concentration calculation module for pyhysplit.

Implements 3D concentration grid calculation using Lagrangian particle
mass distribution. This is the core dispersion modeling capability that
distinguishes HYSPLIT from simple trajectory models.

The concentration calculation follows HYSPLIT's approach:
1. Define a 3D Eulerian grid (lat, lon, height)
2. Distribute particle mass to grid cells using kernel functions
3. Accumulate mass over time with temporal averaging
4. Convert mass to concentration (mass/volume)

References:
    - Stein et al. (2015) BAMS, Section 2e: "Concentration Calculations"
    - Draxler & Hess (1998): "Dispersion and Deposition"
    - HYSPLIT User's Guide: Chapter 4 "Concentration Grid"

Requirements: 9.1-9.8 (Concentration Grid Implementation)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

from pyhysplit.core.models import ConcentrationGridConfig, ParticleState


@dataclass
class ConcentrationGrid:
    """3D Eulerian concentration grid.
    
    Attributes
    ----------
    lat_grid : np.ndarray
        1D array of latitude values (degrees), shape (ny,)
    lon_grid : np.ndarray
        1D array of longitude values (degrees), shape (nx,)
    z_grid : np.ndarray
        1D array of height values (m AGL), shape (nz,)
    concentration : np.ndarray
        3D concentration array (mass/m³), shape (nz, ny, nx)
    mass_accumulated : np.ndarray
        3D accumulated mass array (kg), shape (nz, ny, nx)
    sample_count : np.ndarray
        3D sample count array (number of time steps), shape (nz, ny, nx)
    start_time : datetime
        Start of sampling period
    end_time : datetime
        End of sampling period
    """
    lat_grid: np.ndarray
    lon_grid: np.ndarray
    z_grid: np.ndarray
    concentration: np.ndarray
    mass_accumulated: np.ndarray
    sample_count: np.ndarray
    start_time: datetime
    end_time: datetime


class ConcentrationCalculator:
    """Calculate 3D concentration fields from Lagrangian particles.
    
    This class implements HYSPLIT's concentration calculation algorithm:
    - Mass distribution using kernel functions (top-hat or Gaussian)
    - Temporal averaging over sampling periods
    - Conversion from accumulated mass to concentration
    
    Parameters
    ----------
    config : ConcentrationGridConfig
        Grid configuration (center, spacing, span, levels, sampling period)
    kernel_type : str
        Mass distribution kernel: "top_hat" (default) or "gaussian"
    kernel_width : float
        Kernel width multiplier (default: 1.0)
        For top_hat: width = kernel_width * grid_spacing
        For gaussian: sigma = kernel_width * grid_spacing / 2.355
    """
    
    def __init__(
        self,
        config: ConcentrationGridConfig,
        kernel_type: str = "top_hat",
        kernel_width: float = 1.0,
    ) -> None:
        self.config = config
        self.kernel_type = kernel_type
        self.kernel_width = kernel_width
        
        # Build grid arrays
        self.lat_grid, self.lon_grid, self.z_grid = self._build_grid()
        
        # Initialize accumulation arrays
        nz, ny, nx = len(self.z_grid), len(self.lat_grid), len(self.lon_grid)
        self.mass_accumulated = np.zeros((nz, ny, nx), dtype=np.float64)
        self.sample_count = np.zeros((nz, ny, nx), dtype=np.int32)
        
    def _build_grid(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Build 3D grid arrays from configuration.
        
        Returns
        -------
        tuple[np.ndarray, np.ndarray, np.ndarray]
            (lat_grid, lon_grid, z_grid) arrays
        """
        # Latitude grid
        lat_min = self.config.center_lat - self.config.span_lat / 2
        lat_max = self.config.center_lat + self.config.span_lat / 2
        n_lat = int(self.config.span_lat / self.config.spacing_lat) + 1
        lat_grid = np.linspace(lat_min, lat_max, n_lat)
        
        # Longitude grid
        lon_min = self.config.center_lon - self.config.span_lon / 2
        lon_max = self.config.center_lon + self.config.span_lon / 2
        n_lon = int(self.config.span_lon / self.config.spacing_lon) + 1
        lon_grid = np.linspace(lon_min, lon_max, n_lon)
        
        # Vertical grid (from config levels)
        z_grid = np.array(self.config.levels, dtype=np.float64)
        
        return lat_grid, lon_grid, z_grid
    
    def accumulate_particles(
        self,
        particles: ParticleState,
        current_time: datetime,
    ) -> None:
        """Accumulate particle mass to grid cells.
        
        This method distributes each particle's mass to nearby grid cells
        using the configured kernel function. Called at each time step
        during the sampling period.
        
        Parameters
        ----------
        particles : ParticleState
            Current state of all particles
        current_time : datetime
            Current simulation time
        """
        # Check if within sampling period
        if not (self.config.sampling_start <= current_time <= self.config.sampling_end):
            return
        
        # Only process active particles
        active_mask = particles.active
        if not np.any(active_mask):
            return
        
        lons = particles.lon[active_mask]
        lats = particles.lat[active_mask]
        zs = particles.z[active_mask]
        masses = particles.mass[active_mask]
        
        # Distribute each particle's mass to grid
        for lon, lat, z, mass in zip(lons, lats, zs, masses):
            self._distribute_mass(lon, lat, z, mass)
    
    def _distribute_mass(
        self,
        lon: float,
        lat: float,
        z: float,
        mass: float,
    ) -> None:
        """Distribute a single particle's mass to grid cells.
        
        Parameters
        ----------
        lon, lat, z : float
            Particle position
        mass : float
            Particle mass (kg)
        """
        if self.kernel_type == "top_hat":
            self._distribute_top_hat(lon, lat, z, mass)
        elif self.kernel_type == "gaussian":
            self._distribute_gaussian(lon, lat, z, mass)
        else:
            raise ValueError(f"Unknown kernel type: {self.kernel_type}")
    
    def _distribute_top_hat(
        self,
        lon: float,
        lat: float,
        z: float,
        mass: float,
    ) -> None:
        """Distribute mass using top-hat (uniform) kernel.
        
        Mass is distributed uniformly to all grid cells within
        kernel_width * grid_spacing of the particle.
        
        This is HYSPLIT's default method for concentration calculation.
        """
        # Find grid cell containing particle
        i_lon = np.searchsorted(self.lon_grid, lon)
        i_lat = np.searchsorted(self.lat_grid, lat)
        i_z = np.searchsorted(self.z_grid, z)
        
        # Check bounds
        if i_lon <= 0 or i_lon >= len(self.lon_grid):
            return
        if i_lat <= 0 or i_lat >= len(self.lat_grid):
            return
        if i_z <= 0 or i_z >= len(self.z_grid):
            return
        
        # Determine kernel extent (number of cells in each direction)
        # For top-hat, kernel_width=1.0 means distribute to nearest cell only
        # kernel_width > 1.0 means distribute to multiple cells
        if self.kernel_width <= 1.0:
            # Single cell distribution
            self.mass_accumulated[i_z, i_lat, i_lon] += mass
            self.sample_count[i_z, i_lat, i_lon] += 1
        else:
            # Multi-cell distribution
            n_cells = int(self.kernel_width)
            
            # Distribute mass uniformly to cells within kernel
            total_cells = 0
            for di in range(-n_cells, n_cells + 1):
                for dj in range(-n_cells, n_cells + 1):
                    for dk in range(-n_cells, n_cells + 1):
                        i = i_lon + di
                        j = i_lat + dj
                        k = i_z + dk
                        
                        # Check bounds
                        if 0 <= i < len(self.lon_grid) and \
                           0 <= j < len(self.lat_grid) and \
                           0 <= k < len(self.z_grid):
                            total_cells += 1
            
            # Distribute mass equally to all cells
            if total_cells > 0:
                mass_per_cell = mass / total_cells
                
                for di in range(-n_cells, n_cells + 1):
                    for dj in range(-n_cells, n_cells + 1):
                        for dk in range(-n_cells, n_cells + 1):
                            i = i_lon + di
                            j = i_lat + dj
                            k = i_z + dk
                            
                            if 0 <= i < len(self.lon_grid) and \
                               0 <= j < len(self.lat_grid) and \
                               0 <= k < len(self.z_grid):
                                self.mass_accumulated[k, j, i] += mass_per_cell
                                self.sample_count[k, j, i] += 1
    
    def _distribute_gaussian(
        self,
        lon: float,
        lat: float,
        z: float,
        mass: float,
    ) -> None:
        """Distribute mass using Gaussian kernel.
        
        Mass is distributed with Gaussian weights centered on the particle.
        This provides smoother concentration fields than top-hat.
        
        sigma = kernel_width * grid_spacing / 2.355
        (2.355 = 2 * sqrt(2 * ln(2)), FWHM to sigma conversion)
        """
        # Calculate sigma for Gaussian
        sigma_lon = self.kernel_width * self.config.spacing_lon / 2.355
        sigma_lat = self.kernel_width * self.config.spacing_lat / 2.355
        
        # For vertical, use average layer thickness
        if len(self.z_grid) > 1:
            dz_avg = np.mean(np.diff(self.z_grid))
            sigma_z = self.kernel_width * dz_avg / 2.355
        else:
            sigma_z = 100.0  # Default 100m
        
        # Determine extent (3-sigma rule: 99.7% of mass within 3*sigma)
        extent_lon = 3 * sigma_lon
        extent_lat = 3 * sigma_lat
        extent_z = 3 * sigma_z
        
        # Find grid cells within extent
        lon_mask = np.abs(self.lon_grid - lon) <= extent_lon
        lat_mask = np.abs(self.lat_grid - lat) <= extent_lat
        z_mask = np.abs(self.z_grid - z) <= extent_z
        
        # Calculate Gaussian weights
        total_weight = 0.0
        weights = []
        indices = []
        
        for k, z_grid in enumerate(self.z_grid[z_mask]):
            for j, lat_grid in enumerate(self.lat_grid[lat_mask]):
                for i, lon_grid in enumerate(self.lon_grid[lon_mask]):
                    # Gaussian weight
                    w = np.exp(-0.5 * (
                        ((lon_grid - lon) / sigma_lon) ** 2 +
                        ((lat_grid - lat) / sigma_lat) ** 2 +
                        ((z_grid - z) / sigma_z) ** 2
                    ))
                    
                    if w > 1e-10:  # Threshold to avoid numerical issues
                        weights.append(w)
                        indices.append((k, j, i))
                        total_weight += w
        
        # Normalize and distribute mass
        if total_weight > 0:
            for w, (k, j, i) in zip(weights, indices):
                mass_fraction = (w / total_weight) * mass
                self.mass_accumulated[k, j, i] += mass_fraction
                self.sample_count[k, j, i] += 1
    
    def compute_concentration(self) -> ConcentrationGrid:
        """Compute final concentration field from accumulated mass.
        
        Converts accumulated mass to concentration (mass/volume) by:
        1. Dividing by grid cell volume
        2. Averaging over sampling period
        
        Returns
        -------
        ConcentrationGrid
            Final concentration grid with metadata
        """
        # Calculate grid cell volumes (m³)
        volumes = self._calculate_cell_volumes()
        
        # Convert accumulated mass to concentration
        # concentration = mass / volume / n_samples
        concentration = np.zeros_like(self.mass_accumulated)
        
        # Avoid division by zero
        valid_mask = (self.sample_count > 0) & (volumes > 0)
        
        concentration[valid_mask] = (
            self.mass_accumulated[valid_mask] /
            volumes[valid_mask] /
            self.sample_count[valid_mask]
        )
        
        return ConcentrationGrid(
            lat_grid=self.lat_grid,
            lon_grid=self.lon_grid,
            z_grid=self.z_grid,
            concentration=concentration,
            mass_accumulated=self.mass_accumulated.copy(),
            sample_count=self.sample_count.copy(),
            start_time=self.config.sampling_start,
            end_time=self.config.sampling_end,
        )
    
    def _calculate_cell_volumes(self) -> np.ndarray:
        """Calculate volume of each grid cell.
        
        Returns
        -------
        np.ndarray
            3D array of cell volumes (m³), shape (nz, ny, nx)
        """
        # Earth radius for spherical geometry
        R = 6371000.0  # meters
        
        # Calculate horizontal area for each cell (m²)
        # Using spherical geometry: dA = R² * cos(lat) * dlat * dlon
        dlat = np.deg2rad(self.config.spacing_lat)
        dlon = np.deg2rad(self.config.spacing_lon)
        
        # Area varies with latitude
        areas = np.zeros((len(self.lat_grid), len(self.lon_grid)))
        for j, lat in enumerate(self.lat_grid):
            lat_rad = np.deg2rad(lat)
            area = R ** 2 * np.cos(lat_rad) * dlat * dlon
            areas[j, :] = area
        
        # Calculate layer thicknesses (m)
        if len(self.z_grid) > 1:
            dz = np.diff(self.z_grid)
            # Extend to match grid size (use last dz for top layer)
            dz = np.append(dz, dz[-1])
        else:
            dz = np.array([100.0])  # Default 100m for single layer
        
        # Calculate volumes: V = area * dz
        volumes = np.zeros((len(self.z_grid), len(self.lat_grid), len(self.lon_grid)))
        for k in range(len(self.z_grid)):
            volumes[k, :, :] = areas * dz[k]
        
        return volumes
    
    def reset(self) -> None:
        """Reset accumulation arrays for new sampling period."""
        self.mass_accumulated.fill(0.0)
        self.sample_count.fill(0)
    
    def get_concentration_at_point(
        self,
        lon: float,
        lat: float,
        z: float,
        grid: Optional[ConcentrationGrid] = None,
    ) -> float:
        """Get concentration at a specific point using interpolation.
        
        Parameters
        ----------
        lon, lat, z : float
            Query point coordinates
        grid : ConcentrationGrid, optional
            Concentration grid to query. If None, uses current accumulated data.
        
        Returns
        -------
        float
            Interpolated concentration (mass/m³)
        """
        if grid is None:
            # Use current accumulated data
            grid = self.compute_concentration()
        
        # Trilinear interpolation
        i_lon = np.searchsorted(grid.lon_grid, lon)
        i_lat = np.searchsorted(grid.lat_grid, lat)
        i_z = np.searchsorted(grid.z_grid, z)
        
        # Check bounds
        if i_lon <= 0 or i_lon >= len(grid.lon_grid):
            return 0.0
        if i_lat <= 0 or i_lat >= len(grid.lat_grid):
            return 0.0
        if i_z <= 0 or i_z >= len(grid.z_grid):
            return 0.0
        
        # Fractional distances
        xd = (lon - grid.lon_grid[i_lon - 1]) / (grid.lon_grid[i_lon] - grid.lon_grid[i_lon - 1])
        yd = (lat - grid.lat_grid[i_lat - 1]) / (grid.lat_grid[i_lat] - grid.lat_grid[i_lat - 1])
        zd = (z - grid.z_grid[i_z - 1]) / (grid.z_grid[i_z] - grid.z_grid[i_z - 1])
        
        # Get 8 corner values
        c = grid.concentration
        c000 = c[i_z - 1, i_lat - 1, i_lon - 1]
        c001 = c[i_z - 1, i_lat - 1, i_lon]
        c010 = c[i_z - 1, i_lat, i_lon - 1]
        c011 = c[i_z - 1, i_lat, i_lon]
        c100 = c[i_z, i_lat - 1, i_lon - 1]
        c101 = c[i_z, i_lat - 1, i_lon]
        c110 = c[i_z, i_lat, i_lon - 1]
        c111 = c[i_z, i_lat, i_lon]
        
        # Trilinear interpolation
        c00 = c000 * (1 - xd) + c001 * xd
        c01 = c010 * (1 - xd) + c011 * xd
        c10 = c100 * (1 - xd) + c101 * xd
        c11 = c110 * (1 - xd) + c111 * xd
        
        c0 = c00 * (1 - yd) + c01 * yd
        c1 = c10 * (1 - yd) + c11 * yd
        
        return c0 * (1 - zd) + c1 * zd
