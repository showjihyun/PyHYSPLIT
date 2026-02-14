"""Core data models and custom exceptions for pyhysplit.

Defines dataclasses for simulation configuration, meteorological data,
particle state, and all custom exception types used throughout the package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class PyHysplitError(Exception):
    """Base exception for all pyhysplit errors."""


class BoundaryError(PyHysplitError):
    """Raised when a position is outside the meteorological grid bounds."""


class ConfigParseError(PyHysplitError):
    """Raised when a CONTROL or SETUP.CFG file has format errors.

    Attributes:
        line_number: The line number where the error was detected.
        expected: Description of the expected format.
    """

    def __init__(self, message: str, line_number: int | None = None,
                 expected: str | None = None):
        self.line_number = line_number
        self.expected = expected
        parts = [message]
        if line_number is not None:
            parts.append(f"line {line_number}")
        if expected is not None:
            parts.append(f"expected: {expected}")
        super().__init__(" | ".join(parts))


class MetFileNotFoundError(PyHysplitError):
    """Raised when a meteorological data file cannot be found."""


class MetFormatError(PyHysplitError):
    """Raised when a meteorological data file has a corrupted or unsupported format."""


class InvalidCoordinateError(PyHysplitError):
    """Raised when coordinate values are out of valid range."""


class MassDepletedError(PyHysplitError):
    """Raised when a particle's mass drops below the depletion threshold."""


class MaxAgeExceededError(PyHysplitError):
    """Raised when a particle exceeds its maximum allowed age."""


class NumericalInstabilityError(PyHysplitError):
    """Raised when NaN or Inf values are detected during computation."""


class GPUMemoryError(PyHysplitError):
    """Raised when GPU memory is insufficient for the requested operation."""


class GPUNotAvailableError(PyHysplitError):
    """Raised when GPU hardware or drivers are not available."""


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class StartLocation:
    """A single trajectory start point.
    
    Attributes
    ----------
    lat : float
        Latitude in degrees.
    lon : float
        Longitude in degrees.
    height : float
        Starting height. Interpretation depends on height_type:
        - If height_type="meters_agl": height in meters above ground level
        - If height_type="pressure": pressure level in hPa
    height_type : str
        Type of height specification. Options:
        - "meters_agl" (default): height is in meters AGL
        - "pressure": height is a pressure level in hPa
    """
    lat: float        # degrees
    lon: float        # degrees
    height: float     # metres AGL or hPa (depending on height_type)
    height_type: str = "meters_agl"  # "meters_agl" or "pressure"


@dataclass
class ConcentrationGridConfig:
    """Configuration for a 3-D concentration output grid."""
    center_lat: float
    center_lon: float
    spacing_lat: float
    spacing_lon: float
    span_lat: float
    span_lon: float
    levels: list[float]          # vertical levels (m)
    sampling_start: datetime
    sampling_end: datetime
    averaging_period: int        # hours


@dataclass
class SimulationConfig:
    """Complete simulation configuration parsed from CONTROL + SETUP.CFG."""
    start_time: datetime
    num_start_locations: int
    start_locations: list[StartLocation]
    total_run_hours: int         # positive = forward, negative = backward
    vertical_motion: int         # 0=data, 1=isodensity, 2=isobaric, 3=isentropic, 4=isosigma
    model_top: float             # metres AGL
    met_files: list[tuple[str, str]]  # (directory, filename) pairs
    concentration_grids: list[ConcentrationGridConfig] = field(default_factory=list)
    # SETUP.CFG parameters
    num_particles: int = 2500
    max_particles: int = 10000
    kmixd: int = 0               # mixed-layer depth calculation method
    kmix0: int = 250             # minimum mixed-layer depth (m)
    mgmin: int = 10              # minimum grid spacing (km)
    khmax: float = 9999.0        # maximum horizontal diffusion coefficient
    dt_max: float = 3600.0       # maximum time step (s)
    sigma: float = 0.0           # simple turbulence σ (0 = disabled)
    dry_deposition: bool = False
    wet_deposition: bool = False
    turbulence_on: bool = True
    # Advanced tuning parameters for HYSPLIT matching
    vertical_damping: float = 1.0  # Vertical velocity damping multiplier (Mode 8, 1.0 = no extra damping)
    scale_height: float = 8430.0      # Scale height for pressure-height conversion (m)
    tratio: float = 0.75              # CFL ratio (fraction of grid cell per time step)
    auto_vertical_mode: bool = False  # Automatically select vertical motion mode based on latitude
    enable_dynamic_subgrid: bool = False  # Enable HYSPLIT-style dynamic subgrid expansion


@dataclass
class MetData:
    """Unified internal representation of meteorological data.

    All wind arrays use SI units (m/s) and share the dimension order
    ``(t, z, lat, lon)``.

    Attributes
    ----------
    u : np.ndarray
        East-west wind component (m/s), shape (t, z, lat, lon)
    v : np.ndarray
        North-south wind component (m/s), shape (t, z, lat, lon)
    w : np.ndarray
        Vertical velocity (m/s), shape (t, z, lat, lon)
    t_field : np.ndarray, optional
        Temperature (K), shape (t, z, lat, lon)
    rh : np.ndarray, optional
        Relative humidity (%), shape (t, z, lat, lon)
    hgt : np.ndarray, optional
        Geopotential height (m), shape (t, z, lat, lon)
    precip : np.ndarray, optional
        Precipitation rate (mm/h), shape (t, lat, lon)
    pbl_height : np.ndarray, optional
        Planetary boundary layer height (m), shape (t, lat, lon)
    terrain : np.ndarray, optional
        Terrain height (m), shape (lat, lon)
    lon_grid : np.ndarray
        1-D array of longitude values (degrees)
    lat_grid : np.ndarray
        1-D array of latitude values (degrees)
    z_grid : np.ndarray
        1-D array of vertical coordinate values. Units and interpretation depend
        on ``z_type``:
        - If ``z_type == "pressure"``: values are in hPa (hectopascals)
        - If ``z_type == "height"``: values are in meters (m)
    t_grid : np.ndarray
        1-D array of time values (seconds since reference time)
    z_type : str
        Vertical coordinate system type. Determines interpretation of ``z_grid``:
        - ``"pressure"``: z_grid contains pressure levels in hPa
        - ``"height"``: z_grid contains height levels in meters
    source : str
        Data source identifier (e.g., "ARL", "GDAS_NC", "GFS_NC", "ERA5", "WRF", "NAM")
    """
    u: np.ndarray              # (t, z, lat, lon) east-west wind (m/s)
    v: np.ndarray              # (t, z, lat, lon) north-south wind (m/s)
    w: np.ndarray              # (t, z, lat, lon) vertical velocity (m/s)
    t_field: Optional[np.ndarray] = None   # (t, z, lat, lon) temperature (K)
    rh: Optional[np.ndarray] = None        # (t, z, lat, lon) relative humidity (%)
    hgt: Optional[np.ndarray] = None       # (t, z, lat, lon) geopotential height (m)
    precip: Optional[np.ndarray] = None    # (t, lat, lon) precipitation rate (mm/h)
    pbl_height: Optional[np.ndarray] = None  # (t, lat, lon) PBL height (m)
    terrain: Optional[np.ndarray] = None   # (lat, lon) terrain height (m)
    lon_grid: np.ndarray = field(default_factory=lambda: np.array([]))  # 1-D longitude
    lat_grid: np.ndarray = field(default_factory=lambda: np.array([]))  # 1-D latitude
    z_grid: np.ndarray = field(default_factory=lambda: np.array([]))    # 1-D vertical
    t_grid: np.ndarray = field(default_factory=lambda: np.array([]))    # 1-D time (seconds)
    z_type: str = "pressure"   # "pressure" or "height"
    source: str = "ARL"        # "ARL", "GDAS_NC", "GFS_NC", "ERA5", "WRF", "NAM"


@dataclass
class ParticleState:
    """Vectorised state of all particles in the simulation."""
    lon: np.ndarray        # (N,) longitude (degrees)
    lat: np.ndarray        # (N,) latitude (degrees)
    z: np.ndarray          # (N,) altitude (m AGL)
    mass: np.ndarray       # (N,) mass (kg)
    age: np.ndarray        # (N,) age since release (seconds)
    active: np.ndarray     # (N,) bool — active flag
    species_id: np.ndarray # (N,) int — pollutant species ID
