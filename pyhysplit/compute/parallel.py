"""ParallelExecutor — multiprocessing/multithreading parallel processing.

Provides CPU-parallel trajectory computation via multiprocessing Pool,
I/O-parallel meteorological file loading via ThreadPoolExecutor, and
shared memory management for meteorological data arrays.

References:
    Requirements 14.1, 14.2, 14.3, 14.4, 14.5
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import os
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import shared_memory
from typing import Any, Callable

import numpy as np

from pyhysplit.core.models import MetData, ParticleState, SimulationConfig, StartLocation

logger = logging.getLogger(__name__)


def _run_source_worker(
    args: tuple[StartLocation, SimulationConfig, MetData, float],
) -> list[tuple]:
    """Worker function for parallel trajectory computation.

    Runs a single-source trajectory in a child process. Imports
    TrajectoryEngine lazily to avoid pickling issues.

    Parameters
    ----------
    args : tuple
        (start_location, config, met_data, output_interval_s)

    Returns
    -------
    list[tuple]
        Trajectory as list of (t, lon, lat, z).
    """
    loc, config, met, output_interval_s = args

    # Replace config start_locations with just this one source
    from pyhysplit.core.engine import TrajectoryEngine

    single_config = SimulationConfig(
        start_time=config.start_time,
        num_start_locations=1,
        start_locations=[loc],
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

    engine = TrajectoryEngine(single_config, met)
    results = engine.run(output_interval_s=output_interval_s)
    return results[0] if results else []


class ParallelExecutor:
    """Manages parallel trajectory computation and I/O.

    Parameters
    ----------
    num_workers : int or None
        Number of parallel workers. Defaults to ``os.cpu_count()``.
    """

    def __init__(self, num_workers: int | None = None) -> None:
        self.num_workers = num_workers or os.cpu_count() or 1

    def run_trajectories_parallel(
        self,
        config: SimulationConfig,
        met: MetData,
        output_interval_s: float = 3600.0,
    ) -> list[list[tuple]]:
        """Run trajectory computation in parallel using multiprocessing Pool.

        Each start location is computed independently in a separate worker
        process. Results are returned in the same order as
        ``config.start_locations``.

        Parameters
        ----------
        config : SimulationConfig
            Full simulation configuration (with multiple start locations).
        met : MetData
            Pre-loaded meteorological data shared across workers.
        output_interval_s : float
            Output recording interval in seconds.

        Returns
        -------
        list[list[tuple]]
            Per-start-location trajectories, same order as input.
        """
        if not config.start_locations:
            return []

        # For a single source or single worker, skip multiprocessing overhead
        if len(config.start_locations) == 1 or self.num_workers <= 1:
            return self._run_sequential(config, met, output_interval_s)

        # Build work items — one per start location
        work_items = [
            (loc, config, met, output_interval_s)
            for loc in config.start_locations
        ]

        # Use 'spawn' context for cross-platform safety
        ctx = mp.get_context("spawn")
        effective_workers = min(self.num_workers, len(work_items))

        logger.info(
            "Running %d trajectories with %d workers",
            len(work_items),
            effective_workers,
        )

        with ctx.Pool(processes=effective_workers) as pool:
            results = pool.map(_run_source_worker, work_items)

        return list(results)

    def _run_sequential(
        self,
        config: SimulationConfig,
        met: MetData,
        output_interval_s: float,
    ) -> list[list[tuple]]:
        """Fallback: run all sources sequentially."""
        from pyhysplit.core.engine import TrajectoryEngine

        engine = TrajectoryEngine(config, met)
        return engine.run(output_interval_s=output_interval_s)

    def load_met_files_parallel(
        self,
        filepaths: list[str],
        reader_factory: Callable[[str], MetData],
    ) -> list[MetData]:
        """Load meteorological files in parallel using ThreadPoolExecutor.

        I/O-bound work benefits from threading rather than multiprocessing.

        Parameters
        ----------
        filepaths : list[str]
            Paths to meteorological data files.
        reader_factory : callable
            A callable that takes a filepath and returns MetData.

        Returns
        -------
        list[MetData]
            Loaded MetData objects in the same order as input filepaths.
        """
        if not filepaths:
            return []

        effective_workers = min(self.num_workers, len(filepaths))

        logger.info(
            "Loading %d met files with %d threads",
            len(filepaths),
            effective_workers,
        )

        with ThreadPoolExecutor(max_workers=effective_workers) as executor:
            results = list(executor.map(reader_factory, filepaths))

        return results

    def setup_shared_memory(
        self,
        met: MetData,
    ) -> dict[str, shared_memory.SharedMemory]:
        """Place meteorological arrays into shared memory.

        Creates shared memory blocks for the main wind arrays (u, v, w)
        and grid arrays, allowing child processes to access them without
        copying.

        Parameters
        ----------
        met : MetData
            Meteorological data whose arrays will be shared.

        Returns
        -------
        dict[str, SharedMemory]
            Mapping of field name to SharedMemory handle. Caller is
            responsible for calling ``cleanup_shared_memory`` when done.
        """
        shm_handles: dict[str, shared_memory.SharedMemory] = {}

        arrays_to_share = {
            "u": met.u,
            "v": met.v,
            "w": met.w,
            "lon_grid": met.lon_grid,
            "lat_grid": met.lat_grid,
            "z_grid": met.z_grid,
            "t_grid": met.t_grid,
        }

        for name, arr in arrays_to_share.items():
            if arr is None or arr.size == 0:
                continue
            shm = shared_memory.SharedMemory(create=True, size=arr.nbytes)
            shared_arr = np.ndarray(arr.shape, dtype=arr.dtype, buffer=shm.buf)
            shared_arr[:] = arr[:]
            shm_handles[name] = shm
            logger.debug("Shared memory '%s': %d bytes", name, arr.nbytes)

        return shm_handles

    @staticmethod
    def cleanup_shared_memory(
        shm_handles: dict[str, shared_memory.SharedMemory],
    ) -> None:
        """Release and unlink shared memory blocks.

        Parameters
        ----------
        shm_handles : dict
            Handles returned by ``setup_shared_memory``.
        """
        for name, shm in shm_handles.items():
            try:
                shm.close()
                shm.unlink()
            except Exception:
                logger.warning("Failed to clean up shared memory '%s'", name)
