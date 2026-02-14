"""Dynamic subgrid management for HYSPLIT-style trajectory calculations.

This module implements HYSPLIT's dynamic subgrid expansion feature, which
automatically expands the meteorological data domain when particles move
rapidly (e.g., in jet streams) to prevent boundary errors.

Reference:
    HYSPLIT User's Guide S621 - Sub-grid Size and Vertical Coordinate
    https://www.ready.noaa.gov/hysplitusersguide/S621.htm
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class DynamicSubgrid:
    """Manages dynamic expansion of meteorological data subgrid.
    
    HYSPLIT automatically expands the meteorological data domain during
    trajectory calculations based on particle position and wind speed.
    This prevents boundary errors when particles move rapidly (e.g., in
    jet streams).
    
    Parameters
    ----------
    initial_bounds : tuple
        Initial subgrid bounds (lon_min, lon_max, lat_min, lat_max) in degrees.
    mgmin : int, optional
        Minimum subgrid size in grid units (default: 10).
        This is the HYSPLIT MGMIN parameter.
    grid_spacing : float, optional
        Grid spacing in degrees (default: 0.25 for GFS 0.25°).
    safety_factor : float, optional
        Safety factor for expansion calculation (default: 2.0).
        Larger values expand more aggressively.
    expansion_threshold : float, optional
        Distance threshold in degrees for triggering expansion (default: 5.0).
        Expansion occurs when particle is within this distance of boundary.
    """
    
    def __init__(
        self,
        initial_bounds: Tuple[float, float, float, float],
        mgmin: int = 10,
        grid_spacing: float = 0.25,
        safety_factor: float = 2.0,
        expansion_threshold: float = 5.0,
    ):
        self.bounds = initial_bounds  # (lon_min, lon_max, lat_min, lat_max)
        self.mgmin = mgmin
        self.grid_spacing = grid_spacing
        self.safety_factor = safety_factor
        self.expansion_threshold = expansion_threshold
        
        # Track expansion history
        self.expansion_count = 0
        self.expansion_history = []
        
        logger.info(f"DynamicSubgrid initialized: bounds={initial_bounds}, "
                   f"mgmin={mgmin}, threshold={expansion_threshold}°")
    
    def check_and_expand(
        self,
        lon: float,
        lat: float,
        wind_speed: float,
        dt: float,
    ) -> bool:
        """Check if subgrid expansion is needed and expand if necessary.
        
        Parameters
        ----------
        lon, lat : float
            Current particle position in degrees.
        wind_speed : float
            Current horizontal wind speed in m/s.
        dt : float
            Time step in seconds.
        
        Returns
        -------
        bool
            True if expansion occurred, False otherwise.
        """
        # Calculate predicted movement distance
        predicted_distance_m = wind_speed * dt * self.safety_factor
        predicted_distance_deg = predicted_distance_m / 111000.0  # m to degrees
        
        # Check if expansion is needed
        if not self._needs_expansion(lon, lat, predicted_distance_deg):
            return False
        
        # Calculate new bounds
        new_bounds = self._calculate_new_bounds(
            lon, lat, predicted_distance_deg
        )
        
        # Log expansion
        self.expansion_count += 1
        self.expansion_history.append({
            'count': self.expansion_count,
            'position': (lon, lat),
            'wind_speed': wind_speed,
            'old_bounds': self.bounds,
            'new_bounds': new_bounds,
        })
        
        logger.info(f"Subgrid expansion #{self.expansion_count}: "
                   f"({lon:.2f}, {lat:.2f}), wind={wind_speed:.1f} m/s")
        logger.info(f"  Old bounds: {self.bounds}")
        logger.info(f"  New bounds: {new_bounds}")
        
        self.bounds = new_bounds
        return True
    
    def _needs_expansion(
        self,
        lon: float,
        lat: float,
        predicted_distance: float,
    ) -> bool:
        """Check if expansion is needed based on position and predicted movement.
        
        Parameters
        ----------
        lon, lat : float
            Current position in degrees.
        predicted_distance : float
            Predicted movement distance in degrees.
        
        Returns
        -------
        bool
            True if expansion is needed.
        """
        lon_min, lon_max, lat_min, lat_max = self.bounds
        
        # Calculate distance to each boundary
        dist_to_west = lon - lon_min
        dist_to_east = lon_max - lon
        dist_to_south = lat - lat_min
        dist_to_north = lat_max - lat
        
        # Effective threshold includes predicted movement
        effective_threshold = self.expansion_threshold + predicted_distance
        
        # Check if any boundary is too close
        if (dist_to_west < effective_threshold or
            dist_to_east < effective_threshold or
            dist_to_south < effective_threshold or
            dist_to_north < effective_threshold):
            return True
        
        return False
    
    def _calculate_new_bounds(
        self,
        lon: float,
        lat: float,
        predicted_distance: float,
    ) -> Tuple[float, float, float, float]:
        """Calculate new subgrid bounds after expansion.
        
        Parameters
        ----------
        lon, lat : float
            Current position in degrees.
        predicted_distance : float
            Predicted movement distance in degrees.
        
        Returns
        -------
        tuple
            New bounds (lon_min, lon_max, lat_min, lat_max).
        """
        lon_min, lon_max, lat_min, lat_max = self.bounds
        
        # Calculate minimum expansion based on MGMIN
        min_expansion = self.mgmin * self.grid_spacing
        
        # Calculate expansion based on predicted movement
        movement_expansion = predicted_distance * self.safety_factor
        
        # Use larger of the two
        expansion = max(min_expansion, movement_expansion)
        
        # Determine which boundaries to expand
        dist_to_west = lon - lon_min
        dist_to_east = lon_max - lon
        dist_to_south = lat - lat_min
        dist_to_north = lat_max - lat
        
        # Expand boundaries that are close
        new_lon_min = lon_min
        new_lon_max = lon_max
        new_lat_min = lat_min
        new_lat_max = lat_max
        
        if dist_to_west < self.expansion_threshold + predicted_distance:
            new_lon_min = lon_min - expansion
            logger.debug(f"  Expanding west: {lon_min:.2f} → {new_lon_min:.2f}")
        
        if dist_to_east < self.expansion_threshold + predicted_distance:
            new_lon_max = lon_max + expansion
            logger.debug(f"  Expanding east: {lon_max:.2f} → {new_lon_max:.2f}")
        
        if dist_to_south < self.expansion_threshold + predicted_distance:
            new_lat_min = lat_min - expansion
            logger.debug(f"  Expanding south: {lat_min:.2f} → {new_lat_min:.2f}")
        
        if dist_to_north < self.expansion_threshold + predicted_distance:
            new_lat_max = lat_max + expansion
            logger.debug(f"  Expanding north: {lat_max:.2f} → {new_lat_max:.2f}")
        
        # Apply reasonable limits (global coverage)
        new_lon_min = max(new_lon_min, -180.0)
        new_lon_max = min(new_lon_max, 180.0)
        new_lat_min = max(new_lat_min, -90.0)
        new_lat_max = min(new_lat_max, 90.0)
        
        return (new_lon_min, new_lon_max, new_lat_min, new_lat_max)
    
    def get_bounds(self) -> Tuple[float, float, float, float]:
        """Get current subgrid bounds.
        
        Returns
        -------
        tuple
            Current bounds (lon_min, lon_max, lat_min, lat_max).
        """
        return self.bounds
    
    def get_expansion_stats(self) -> dict:
        """Get statistics about subgrid expansions.
        
        Returns
        -------
        dict
            Statistics including expansion count and history.
        """
        return {
            'expansion_count': self.expansion_count,
            'current_bounds': self.bounds,
            'expansion_history': self.expansion_history,
        }
    
    def is_inside(self, lon: float, lat: float) -> bool:
        """Check if a position is inside the current subgrid.
        
        Parameters
        ----------
        lon, lat : float
            Position to check in degrees.
        
        Returns
        -------
        bool
            True if position is inside subgrid.
        """
        lon_min, lon_max, lat_min, lat_max = self.bounds
        return (lon_min <= lon <= lon_max and
                lat_min <= lat <= lat_max)
