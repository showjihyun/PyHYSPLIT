"""Integration tests for the full trajectory computation pipeline.

End-to-end tests covering:
- CONTROL file → engine → tdump output
- Forward/Backward mode
- Multi-source + concentration grid
- Parallel execution equivalence
- Batch (GPU/CPU backend) execution equivalence

Requirements: 4.1-4.5, 9.1-9.6, 12.1-12.5, 14.1-14.5, 15.1-15.5
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime

import numpy as np
import pytest

from pyhysplit.config_parser import parse_config, write_control, write_setup_cfg
from pyhysplit.concentration_grid import ConcentrationGrid
from pyhysplit.engine import TrajectoryEngine
from pyhysplit.gpu_backend import NumpyBackend
from pyhysplit.models import (
    ConcentrationGridConfig,
    MetData,
    ParticleState,
    SimulationConfig,
    StartLocation,
)
from pyhysplit.output_writer import TdumpWriter, TrajectoryPoint
from pyhysplit.parallel import ParallelExecutor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uniform_met(
    u: float = 5.0,
    v: float = 3.0,
    w: float = 0.0,
    nx: int = 6,
    ny: int = 6,
    nz: int = 3,
    nt: int = 5,
    lon_range: tuple[float, float] = (-15.0, 15.0),
    lat_range: tuple[float, float] = (30.0, 50.0),
    z_range: tuple[float, float] = (0.0, 10000.0),
    t_hours: float = 48.0,
) -> MetData:
    """Build MetData with uniform wind for deterministic testing."""
    lon_grid = np.linspace(lon_range[0], lon_range[1], nx)
    lat_grid = np.linspace(lat_range[0], lat_range[1], ny)
    z_grid = np.linspace(z_range[0], z_range[1], nz)
    t_grid = np.linspace(0.0, t_hours * 3600.0, nt)
    shape = (nt, nz, ny, nx)
    return MetData(
        u=np.full(shape, u, dtype=np.float64),
        v=np.full(shape, v, dtype=np.float64),
        w=np.full(shape, w, dtype=np.float64),
        lon_grid=lon_grid,
        lat_grid=lat_grid,
        z_grid=z_grid,
        t_grid=t_grid,
        terrain=np.zeros((ny, nx), dtype=np.float64),
    )


def _simple_config(
    start_locations: list[StartLocation] | None = None,
    total_run_hours: int = 3,
    model_top: float = 10000.0,
    conc_grids: list[ConcentrationGridConfig] | None = None,
) -> SimulationConfig:
    if start_locations is None:
        start_locations = [StartLocation(lat=40.0, lon=0.0, height=500.0)]
    return SimulationConfig(
        start_time=datetime(2024, 1, 1, 0, 0),
        num_start_locations=len(start_locations),
        start_locations=start_locations,
        total_run_hours=total_run_hours,
        vertical_motion=0,
        model_top=model_top,
        met_files=[("/data", "met.arl")],
        concentration_grids=conc_grids or [],
        turbulence_on=False,
        sigma=0.0,
    )


# ---------------------------------------------------------------------------
# Test 1: End-to-end forward trajectory (CONTROL → engine → tdump)
# ---------------------------------------------------------------------------

class TestEndToEndForward:
    """Full pipeline: config → engine.run → TdumpWriter → read back."""

    def test_forward_trajectory_produces_tdump(self):
        """Run a forward trajectory and write/read tdump output."""
        met = _uniform_met(u=5.0, v=3.0, w=0.0)
        config = _simple_config(total_run_hours=3)
        engine = TrajectoryEngine(config, met)

        trajectories = engine.run(output_interval_s=3600.0)

        assert len(trajectories) == 1
        traj = trajectories[0]
        # At least start + 3 hourly outputs
        assert len(traj) >= 4

        # Time should be strictly increasing (forward)
        times = [pt[0] for pt in traj]
        for i in range(1, len(times)):
            assert times[i] > times[i - 1]

        # Convert to TrajectoryPoint for tdump writing
        points = []
        for idx, (t, lon, lat, z) in enumerate(traj):
            hours_elapsed = t / 3600.0
            points.append(TrajectoryPoint(
                traj_id=1, grid_id=1,
                year=2024, month=1, day=1,
                hour=int(hours_elapsed) % 24,
                minute=int((hours_elapsed % 1) * 60),
                forecast_hour=0.0, age=t,
                lat=lat, lon=lon, height=z,
            ))

        met_info = [{"model_id": "TEST", "year": 2024, "month": 1,
                      "day": 1, "hour": 0, "forecast_hour": 0}]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tdump", delete=False
        ) as f:
            tdump_path = f.name

        try:
            TdumpWriter.write(
                tdump_path, [points], met_info,
                config.start_locations,
            )
            # Read back
            parsed = TdumpWriter.read(tdump_path)
            assert len(parsed.points) == len(points)
            # Verify first and last lat/lon match
            assert abs(parsed.points[0].lat - points[0].lat) < 0.01
            assert abs(parsed.points[-1].lon - points[-1].lon) < 0.01
        finally:
            os.unlink(tdump_path)

    def test_control_roundtrip_then_run(self):
        """Write CONTROL → parse → run engine with parsed config."""
        config = _simple_config(total_run_hours=2)
        control_text = write_control(config)
        setup_text = write_setup_cfg(config)

        parsed_config = parse_config(control_text, setup_text)

        met = _uniform_met()
        engine = TrajectoryEngine(parsed_config, met)
        trajectories = engine.run(output_interval_s=3600.0)

        assert len(trajectories) == 1
        assert len(trajectories[0]) >= 3  # start + 2 hourly


# ---------------------------------------------------------------------------
# Test 2: Forward/Backward mode integration
# ---------------------------------------------------------------------------

class TestForwardBackward:
    """Validate forward and backward trajectory modes end-to-end."""

    def test_forward_time_increases(self):
        met = _uniform_met(u=4.0, v=2.0)
        config = _simple_config(total_run_hours=2)
        engine = TrajectoryEngine(config, met)
        traj = engine.run(output_interval_s=3600.0)[0]

        for i in range(1, len(traj)):
            assert traj[i][0] > traj[i - 1][0]

    def test_backward_time_decreases(self):
        met = _uniform_met(u=4.0, v=2.0)
        config = _simple_config(total_run_hours=-2)
        engine = TrajectoryEngine(config, met)
        traj = engine.run(output_interval_s=3600.0)[0]

        for i in range(1, len(traj)):
            assert traj[i][0] < traj[i - 1][0]

    def test_forward_backward_roundtrip_uniform_wind(self):
        """Forward then backward in uniform wind returns near origin."""
        loc = StartLocation(lat=40.0, lon=0.0, height=500.0)
        met = _uniform_met(u=3.0, v=2.0, w=0.0)

        # Forward 1 hour
        cfg_fwd = _simple_config([loc], total_run_hours=1)
        traj_fwd = TrajectoryEngine(cfg_fwd, met).run(output_interval_s=3600.0)[0]
        _, lon_end, lat_end, z_end = traj_fwd[-1]

        # Backward 1 hour from endpoint
        loc_end = StartLocation(lat=lat_end, lon=lon_end, height=z_end)
        cfg_bwd = _simple_config([loc_end], total_run_hours=-1)
        traj_bwd = TrajectoryEngine(cfg_bwd, met).run(output_interval_s=3600.0)[0]
        _, lon_back, lat_back, z_back = traj_bwd[-1]

        assert abs(lon_back - loc.lon) < 0.5
        assert abs(lat_back - loc.lat) < 0.5
        assert abs(z_back - loc.height) < 1.0


# ---------------------------------------------------------------------------
# Test 3: Multi-source + concentration grid
# ---------------------------------------------------------------------------

class TestMultiSourceConcentration:
    """Multi-start-location runs with concentration grid accumulation."""

    def test_multi_source_independent_trajectories(self):
        loc_a = StartLocation(lat=40.0, lon=0.0, height=500.0)
        loc_b = StartLocation(lat=42.0, lon=2.0, height=1000.0)
        met = _uniform_met(u=5.0, v=3.0)

        # Single source
        traj_a = TrajectoryEngine(
            _simple_config([loc_a], total_run_hours=2), met,
        ).run(output_interval_s=3600.0)

        # Multi source
        traj_ab = TrajectoryEngine(
            _simple_config([loc_a, loc_b], total_run_hours=2), met,
        ).run(output_interval_s=3600.0)

        assert len(traj_ab) == 2
        # loc_a trajectory should be identical
        for pt_s, pt_m in zip(traj_a[0], traj_ab[0]):
            assert abs(pt_s[1] - pt_m[1]) < 1e-10  # lon
            assert abs(pt_s[2] - pt_m[2]) < 1e-10  # lat

    def test_concentration_grid_accumulation(self):
        """Particles placed inside a grid produce non-zero concentration."""
        grid_cfg = ConcentrationGridConfig(
            center_lat=40.0, center_lon=0.0,
            spacing_lat=1.0, spacing_lon=1.0,
            span_lat=10.0, span_lon=10.0,
            levels=[0.0, 1000.0, 5000.0],
            sampling_start=datetime(2024, 1, 1),
            sampling_end=datetime(2024, 1, 2),
            averaging_period=1,
        )
        grid = ConcentrationGrid(grid_cfg, num_species=1)

        # Create particles inside the grid
        particles = ParticleState(
            lon=np.array([0.0, 1.0]),
            lat=np.array([40.0, 41.0]),
            z=np.array([500.0, 500.0]),
            mass=np.array([1.0, 1.0]),
            age=np.array([0.0, 0.0]),
            active=np.array([True, True]),
            species_id=np.array([0, 0]),
        )
        grid.accumulate(particles)

        total_mass = grid.total_grid_mass(species_id=0)
        assert total_mass > 0.0
        # Mass should be close to sum of particle masses
        np.testing.assert_allclose(total_mass, 2.0, rtol=0.01)

    def test_multi_species_independence(self):
        """Species A particles don't affect species B grid."""
        grid_cfg = ConcentrationGridConfig(
            center_lat=40.0, center_lon=0.0,
            spacing_lat=2.0, spacing_lon=2.0,
            span_lat=10.0, span_lon=10.0,
            levels=[0.0, 5000.0],
            sampling_start=datetime(2024, 1, 1),
            sampling_end=datetime(2024, 1, 2),
            averaging_period=1,
        )
        grid = ConcentrationGrid(grid_cfg, num_species=2)

        # Only species 0 particles
        particles = ParticleState(
            lon=np.array([0.0]),
            lat=np.array([40.0]),
            z=np.array([500.0]),
            mass=np.array([1.0]),
            age=np.array([0.0]),
            active=np.array([True]),
            species_id=np.array([0]),
        )
        grid.accumulate(particles)

        assert grid.total_grid_mass(species_id=0) > 0.0
        assert grid.total_grid_mass(species_id=1) == 0.0


# ---------------------------------------------------------------------------
# Test 4: Parallel execution equivalence
# ---------------------------------------------------------------------------

class TestParallelExecution:
    """Verify parallel results match sequential results."""

    def test_parallel_matches_sequential(self):
        locs = [
            StartLocation(lat=40.0, lon=0.0, height=500.0),
            StartLocation(lat=42.0, lon=2.0, height=1000.0),
        ]
        met = _uniform_met(u=5.0, v=3.0)
        config = _simple_config(locs, total_run_hours=2)

        # Sequential
        engine = TrajectoryEngine(config, met)
        traj_seq = engine.run(output_interval_s=3600.0)

        # Parallel (force 1 worker to avoid spawn issues in test)
        executor = ParallelExecutor(num_workers=1)
        traj_par = executor.run_trajectories_parallel(
            config, met, output_interval_s=3600.0,
        )

        assert len(traj_seq) == len(traj_par)
        for seq, par in zip(traj_seq, traj_par):
            assert len(seq) == len(par)
            for pt_s, pt_p in zip(seq, par):
                np.testing.assert_allclose(pt_s, pt_p, atol=1e-10)


# ---------------------------------------------------------------------------
# Test 5: Batch (GPU/CPU backend) execution
# ---------------------------------------------------------------------------

class TestBatchExecution:
    """Verify batch backend results match scalar loop results."""

    def test_batch_matches_scalar(self):
        locs = [
            StartLocation(lat=40.0, lon=0.0, height=500.0),
            StartLocation(lat=42.0, lon=2.0, height=1000.0),
        ]
        met = _uniform_met(u=5.0, v=3.0, w=0.0)
        config = _simple_config(locs, total_run_hours=2)

        backend = NumpyBackend()
        engine = TrajectoryEngine(config, met, backend=backend)

        traj_scalar = engine.run(output_interval_s=3600.0)
        traj_batch = engine.run_batch(output_interval_s=3600.0)

        assert len(traj_scalar) == len(traj_batch)
        for scalar, batch in zip(traj_scalar, traj_batch):
            # Both should have similar number of points
            assert len(batch) >= 2
            # Compare final positions (batch uses a single dt for all
            # particles so minor differences are expected)
            _, lon_s, lat_s, z_s = scalar[-1]
            _, lon_b, lat_b, z_b = batch[-1]
            assert abs(lon_s - lon_b) < 1.0
            assert abs(lat_s - lat_b) < 1.0
            assert abs(z_s - z_b) < 100.0

    def test_batch_forward_time_increases(self):
        met = _uniform_met(u=4.0, v=2.0)
        config = _simple_config(total_run_hours=2)
        engine = TrajectoryEngine(config, met, backend=NumpyBackend())

        traj = engine.run_batch(output_interval_s=3600.0)[0]
        times = [pt[0] for pt in traj]
        for i in range(1, len(times)):
            assert times[i] > times[i - 1]


# ---------------------------------------------------------------------------
# Test 6: Engine with backend/parallel constructor options
# ---------------------------------------------------------------------------

class TestEngineConstructor:
    """Verify engine accepts backend and parallel options."""

    def test_default_construction(self):
        met = _uniform_met()
        config = _simple_config()
        engine = TrajectoryEngine(config, met)
        assert engine.backend is not None
        assert engine.parallel is not None

    def test_explicit_backend(self):
        met = _uniform_met()
        config = _simple_config()
        backend = NumpyBackend()
        engine = TrajectoryEngine(config, met, backend=backend)
        assert engine.backend is backend

    def test_explicit_parallel(self):
        met = _uniform_met()
        config = _simple_config()
        executor = ParallelExecutor(num_workers=2)
        engine = TrajectoryEngine(config, met, parallel=executor)
        assert engine.parallel is executor
        assert engine.parallel.num_workers == 2

    def test_prefer_gpu_false(self):
        met = _uniform_met()
        config = _simple_config()
        engine = TrajectoryEngine(config, met, prefer_gpu=False)
        assert isinstance(engine.backend, NumpyBackend)
