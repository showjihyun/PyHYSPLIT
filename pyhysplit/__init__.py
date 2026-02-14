"""pyhysplit - Python implementation of the HYSPLIT trajectory and dispersion model.

This package provides a Python implementation of NOAA's HYSPLIT model for
atmospheric trajectory and dispersion calculations.

Package Structure:
    core/       - Core trajectory engine and models
    physics/    - Physics modules (vertical motion, turbulence, deposition, boundary)
    data/       - Data I/O (met readers, config parser, output writer)
    utils/      - Utilities (coordinate converter, dynamic subgrid, verification)
    analysis/   - Analysis tools (cluster analysis, concentration grid)
    compute/    - Compute backends (GPU, parallel, particle manager)
"""

__version__ = "0.1.0"

# Core
from pyhysplit.core.engine import TrajectoryEngine
from pyhysplit.core.integrator import AdaptiveDtController, HeunIntegrator
from pyhysplit.core.interpolator import EARTH_RADIUS, Interpolator
from pyhysplit.core.models import (
    BoundaryError,
    ConfigParseError,
    ConcentrationGridConfig,
    GPUMemoryError,
    GPUNotAvailableError,
    InvalidCoordinateError,
    MassDepletedError,
    MaxAgeExceededError,
    MetData,
    MetFileNotFoundError,
    MetFormatError,
    NumericalInstabilityError,
    ParticleState,
    PyHysplitError,
    SimulationConfig,
    StartLocation,
)

# Data I/O
from pyhysplit.data.config_parser import parse_config, parse_control, write_setup_cfg
from pyhysplit.data.met_reader import ARLReader, NetCDFReader
from pyhysplit.data.output_writer import TdumpWriter, TrajectoryPoint

# Physics
from pyhysplit.physics.boundary import BoundaryHandler
from pyhysplit.physics.deposition import DepositionModule
from pyhysplit.physics.turbulence import TurbulenceModule
from pyhysplit.physics.vertical_motion import VerticalMotionHandler

# Utils
from pyhysplit.utils.coordinate_converter import CoordinateConverter
from pyhysplit.utils.dynamic_subgrid import DynamicSubgrid

# Compute
from pyhysplit.compute.gpu_backend import ComputeBackend, NumpyBackend, get_backend
from pyhysplit.compute.parallel import ParallelExecutor
from pyhysplit.compute.particle_manager import ParticleManager

# Analysis
from pyhysplit.analysis.cluster_analysis import TrajectoryClusterAnalysis
from pyhysplit.analysis.concentration_grid import ConcentrationGrid

__all__ = [
    # Core - Engine
    'TrajectoryEngine',
    # Core - Integrator
    'AdaptiveDtController',
    'HeunIntegrator',
    # Core - Interpolator
    'EARTH_RADIUS',
    'Interpolator',
    # Core - Models
    'ConcentrationGridConfig',
    'MetData',
    'ParticleState',
    'SimulationConfig',
    'StartLocation',
    # Core - Exceptions
    'BoundaryError',
    'ConfigParseError',
    'GPUMemoryError',
    'GPUNotAvailableError',
    'InvalidCoordinateError',
    'MassDepletedError',
    'MaxAgeExceededError',
    'MetFileNotFoundError',
    'MetFormatError',
    'NumericalInstabilityError',
    'PyHysplitError',
    # Data I/O
    'ARLReader',
    'NetCDFReader',
    'TdumpWriter',
    'TrajectoryPoint',
    'parse_config',
    'parse_control',
    'write_setup_cfg',
    # Physics
    'BoundaryHandler',
    'DepositionModule',
    'TurbulenceModule',
    'VerticalMotionHandler',
    # Utils
    'CoordinateConverter',
    'DynamicSubgrid',
    # Compute
    'ComputeBackend',
    'NumpyBackend',
    'ParallelExecutor',
    'ParticleManager',
    'get_backend',
    # Analysis
    'ConcentrationGrid',
    'TrajectoryClusterAnalysis',
]
