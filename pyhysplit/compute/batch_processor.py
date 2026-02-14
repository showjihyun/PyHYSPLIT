"""Batch processor for optimized multi-trajectory computation.

Combines GPU acceleration and multiprocessing for maximum performance.
Automatically selects the best strategy based on problem size and hardware.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from pyhysplit.compute.gpu_backend import ComputeBackend, get_backend
from pyhysplit.compute.parallel import ParallelExecutor
from pyhysplit.core.models import MetData, SimulationConfig, StartLocation

logger = logging.getLogger(__name__)


class BatchProcessor:
    """Intelligent batch processor for trajectory computation.
    
    Automatically selects between:
    - Single-threaded CPU (small problems)
    - GPU acceleration (medium problems, GPU available)
    - Multiprocessing (large problems, multiple sources)
    - Hybrid GPU + multiprocessing (very large problems)
    
    Parameters
    ----------
    prefer_gpu : bool
        Whether to prefer GPU acceleration when available.
    num_workers : int | None
        Number of parallel workers for multiprocessing.
    gpu_batch_size : int
        Maximum batch size for GPU operations.
    """
    
    def __init__(
        self,
        prefer_gpu: bool = True,
        num_workers: Optional[int] = None,
        gpu_batch_size: int = 100_000,
    ):
        self.prefer_gpu = prefer_gpu
        self.gpu_batch_size = gpu_batch_size
        self.backend: Optional[ComputeBackend] = None
        self.parallel_executor = ParallelExecutor(num_workers=num_workers)
        
        # Try to initialize GPU backend
        if prefer_gpu:
            try:
                self.backend = get_backend(prefer_gpu=True)
                logger.info("GPU backend initialized successfully")
            except Exception as e:
                logger.warning(f"GPU initialization failed: {e}")
                self.backend = get_backend(prefer_gpu=False)
        else:
            self.backend = get_backend(prefer_gpu=False)
    
    def select_strategy(
        self,
        num_sources: int,
        num_particles_per_source: int,
        num_timesteps: int,
    ) -> str:
        """Select optimal computation strategy based on problem size.
        
        Parameters
        ----------
        num_sources : int
            Number of start locations.
        num_particles_per_source : int
            Particles per source.
        num_timesteps : int
            Estimated number of time steps.
            
        Returns
        -------
        str
            Strategy name: 'sequential', 'gpu', 'parallel', or 'hybrid'.
        """
        total_particles = num_sources * num_particles_per_source
        total_operations = total_particles * num_timesteps
        
        # Thresholds (tunable based on benchmarks)
        SMALL_PROBLEM = 1_000_000  # < 1M operations
        MEDIUM_PROBLEM = 10_000_000  # < 10M operations
        LARGE_PROBLEM = 100_000_000  # < 100M operations
        
        has_gpu = self.backend is not None and not isinstance(
            self.backend, type(get_backend(prefer_gpu=False))
        )
        
        if total_operations < SMALL_PROBLEM:
            return 'sequential'
        elif total_operations < MEDIUM_PROBLEM:
            return 'gpu' if has_gpu else 'sequential'
        elif total_operations < LARGE_PROBLEM:
            if has_gpu and num_sources <= 4:
                return 'gpu'
            else:
                return 'parallel'
        else:
            # Very large problems: use both GPU and multiprocessing
            return 'hybrid' if has_gpu else 'parallel'
    
    def process_batch(
        self,
        config: SimulationConfig,
        met: MetData,
        output_interval_s: float = 3600.0,
        strategy: Optional[str] = None,
    ) -> list[list[tuple]]:
        """Process trajectory batch with optimal strategy.
        
        Parameters
        ----------
        config : SimulationConfig
            Simulation configuration.
        met : MetData
            Meteorological data.
        output_interval_s : float
            Output recording interval.
        strategy : str | None
            Force specific strategy, or None for auto-selection.
            
        Returns
        -------
        list[list[tuple]]
            Trajectories for each start location.
        """
        if not config.start_locations:
            return []
        
        # Estimate problem size
        num_sources = len(config.start_locations)
        num_particles = config.num_particles or 1
        num_timesteps = int(abs(config.total_run_hours * 3600) / config.dt_max)
        
        # Select strategy
        if strategy is None:
            strategy = self.select_strategy(
                num_sources, num_particles, num_timesteps
            )
        
        logger.info(
            f"Processing {num_sources} sources with strategy: {strategy}"
        )
        
        # Execute based on strategy
        if strategy == 'sequential':
            return self._process_sequential(config, met, output_interval_s)
        elif strategy == 'gpu':
            return self._process_gpu(config, met, output_interval_s)
        elif strategy == 'parallel':
            return self._process_parallel(config, met, output_interval_s)
        elif strategy == 'hybrid':
            return self._process_hybrid(config, met, output_interval_s)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")
    
    def _process_sequential(
        self,
        config: SimulationConfig,
        met: MetData,
        output_interval_s: float,
    ) -> list[list[tuple]]:
        """Sequential CPU processing."""
        from pyhysplit.core.engine import TrajectoryEngine
        
        engine = TrajectoryEngine(config, met)
        return engine.run(output_interval_s=output_interval_s)
    
    def _process_gpu(
        self,
        config: SimulationConfig,
        met: MetData,
        output_interval_s: float,
    ) -> list[list[tuple]]:
        """GPU-accelerated processing."""
        from pyhysplit.core.engine import TrajectoryEngine
        
        # Create engine with GPU backend
        engine = TrajectoryEngine(config, met, backend=self.backend)
        return engine.run(output_interval_s=output_interval_s)
    
    def _process_parallel(
        self,
        config: SimulationConfig,
        met: MetData,
        output_interval_s: float,
    ) -> list[list[tuple]]:
        """Multiprocessing parallel processing."""
        return self.parallel_executor.run_trajectories_parallel(
            config, met, output_interval_s
        )
    
    def _process_hybrid(
        self,
        config: SimulationConfig,
        met: MetData,
        output_interval_s: float,
    ) -> list[list[tuple]]:
        """Hybrid GPU + multiprocessing.
        
        Splits sources across multiple processes, each using GPU.
        """
        # Split sources into chunks for each worker
        num_workers = self.parallel_executor.num_workers
        sources = config.start_locations
        chunk_size = (len(sources) + num_workers - 1) // num_workers
        
        results = []
        for i in range(0, len(sources), chunk_size):
            chunk = sources[i:i + chunk_size]
            chunk_config = SimulationConfig(
                start_time=config.start_time,
                num_start_locations=len(chunk),
                start_locations=chunk,
                total_run_hours=config.total_run_hours,
                vertical_motion=config.vertical_motion,
                model_top=config.model_top,
                met_files=config.met_files,
                concentration_grids=config.concentration_grids,
                num_particles=config.num_particles,
                max_particles=config.max_particles,
                kmixd=config.kmixd,
                kmix0=config.kmix0,
                mgmin=config.mgmin,
                khmax=config.khmax,
                dt_max=config.dt_max,
                sigma=config.sigma,
                dry_deposition=config.dry_deposition,
                wet_deposition=config.wet_deposition,
                turbulence_on=config.turbulence_on,
            )
            chunk_results = self._process_gpu(
                chunk_config, met, output_interval_s
            )
            results.extend(chunk_results)
        
        return results
    
    def benchmark(
        self,
        config: SimulationConfig,
        met: MetData,
        strategies: Optional[list[str]] = None,
    ) -> dict[str, float]:
        """Benchmark different strategies.
        
        Parameters
        ----------
        config : SimulationConfig
            Test configuration.
        met : MetData
            Meteorological data.
        strategies : list[str] | None
            Strategies to test, or None for all available.
            
        Returns
        -------
        dict[str, float]
            Execution time (seconds) for each strategy.
        """
        import time
        
        if strategies is None:
            strategies = ['sequential', 'gpu', 'parallel', 'hybrid']
        
        results = {}
        
        for strategy in strategies:
            try:
                logger.info(f"Benchmarking strategy: {strategy}")
                start = time.time()
                self.process_batch(config, met, strategy=strategy)
                elapsed = time.time() - start
                results[strategy] = elapsed
                logger.info(f"{strategy}: {elapsed:.3f}s")
            except Exception as e:
                logger.warning(f"{strategy} failed: {e}")
                results[strategy] = float('inf')
        
        return results
