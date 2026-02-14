"""Compute backends and performance optimization."""

from pyhysplit.compute.batch_processor import BatchProcessor
from pyhysplit.compute.gpu_backend import ComputeBackend, NumpyBackend, get_backend
from pyhysplit.compute.parallel import ParallelExecutor
from pyhysplit.compute.particle_manager import ParticleManager

__all__ = [
    'BatchProcessor',
    'ComputeBackend',
    'NumpyBackend',
    'ParallelExecutor',
    'ParticleManager',
    'get_backend',
]
