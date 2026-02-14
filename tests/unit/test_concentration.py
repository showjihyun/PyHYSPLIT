"""Unit tests for concentration calculation module."""

from datetime import datetime, timedelta

import numpy as np
import pytest

from pyhysplit.core.models import ConcentrationGridConfig, ParticleState
from pyhysplit.physics.concentration import ConcentrationCalculator, ConcentrationGrid


def test_concentration_grid_initialization():
    """Test that concentration grid is properly initialized."""
    config = ConcentrationGridConfig(
        center_lat=37.5,
        center_lon=127.0,
        spacing_lat=0.1,
        spacing_lon=0.1,
        span_lat=1.0,
        span_lon=1.0,
        levels=[0.0, 100.0, 500.0, 1000.0],
        sampling_start=datetime(2024, 1, 1, 0, 0),
        sampling_end=datetime(2024, 1, 1, 6, 0),
        averaging_period=6,
    )
    
    calc = ConcentrationCalculator(config)
    
    # Check grid dimensions
    assert len(calc.lat_grid) == 11  # 1.0 / 0.1 + 1
    assert len(calc.lon_grid) == 11
    assert len(calc.z_grid) == 4
    
    # Check grid bounds
    assert calc.lat_grid[0] == pytest.approx(37.0)
    assert calc.lat_grid[-1] == pytest.approx(38.0)
    assert calc.lon_grid[0] == pytest.approx(126.5)
    assert calc.lon_grid[-1] == pytest.approx(127.5)
    
    # Check accumulation arrays are initialized to zero
    assert np.all(calc.mass_accumulated == 0.0)
    assert np.all(calc.sample_count == 0)


def test_top_hat_mass_distribution():
    """Test top-hat kernel mass distribution."""
    config = ConcentrationGridConfig(
        center_lat=37.5,
        center_lon=127.0,
        spacing_lat=0.1,
        spacing_lon=0.1,
        span_lat=1.0,
        span_lon=1.0,
        levels=[0.0, 500.0, 1000.0],
        sampling_start=datetime(2024, 1, 1, 0, 0),
        sampling_end=datetime(2024, 1, 1, 6, 0),
        averaging_period=6,
    )
    
    calc = ConcentrationCalculator(config, kernel_type="top_hat", kernel_width=1.0)
    
    # Place a particle at grid center
    lon, lat, z = 127.0, 37.5, 500.0
    mass = 1.0  # 1 kg
    
    calc._distribute_mass(lon, lat, z, mass)
    
    # Check that mass was distributed
    assert np.sum(calc.mass_accumulated) == pytest.approx(mass)
    
    # For kernel_width=1.0, mass should be in single cell
    assert np.max(calc.mass_accumulated) == pytest.approx(mass)


def test_gaussian_mass_distribution():
    """Test Gaussian kernel mass distribution."""
    config = ConcentrationGridConfig(
        center_lat=37.5,
        center_lon=127.0,
        spacing_lat=0.1,
        spacing_lon=0.1,
        span_lat=1.0,
        span_lon=1.0,
        levels=[0.0, 500.0, 1000.0],
        sampling_start=datetime(2024, 1, 1, 0, 0),
        sampling_end=datetime(2024, 1, 1, 6, 0),
        averaging_period=6,
    )
    
    calc = ConcentrationCalculator(config, kernel_type="gaussian", kernel_width=2.0)
    
    # Place a particle at grid center
    lon, lat, z = 127.0, 37.5, 500.0
    mass = 1.0  # 1 kg
    
    calc._distribute_mass(lon, lat, z, mass)
    
    # Check that total mass is conserved
    assert np.sum(calc.mass_accumulated) == pytest.approx(mass, rel=1e-3)
    
    # Gaussian should distribute mass to multiple cells
    nonzero_cells = np.count_nonzero(calc.mass_accumulated)
    assert nonzero_cells > 1


def test_accumulate_particles():
    """Test particle accumulation over time."""
    config = ConcentrationGridConfig(
        center_lat=37.5,
        center_lon=127.0,
        spacing_lat=0.1,
        spacing_lon=0.1,
        span_lat=1.0,
        span_lon=1.0,
        levels=[0.0, 500.0, 1000.0],
        sampling_start=datetime(2024, 1, 1, 0, 0),
        sampling_end=datetime(2024, 1, 1, 6, 0),
        averaging_period=6,
    )
    
    calc = ConcentrationCalculator(config, kernel_type="top_hat")
    
    # Create particle state with 3 particles
    particles = ParticleState(
        lon=np.array([127.0, 127.1, 127.2]),
        lat=np.array([37.5, 37.6, 37.7]),
        z=np.array([500.0, 500.0, 500.0]),
        mass=np.array([1.0, 2.0, 3.0]),
        age=np.array([0.0, 0.0, 0.0]),
        active=np.array([True, True, True]),
        species_id=np.array([0, 0, 0]),
    )
    
    # Accumulate at time within sampling period
    current_time = datetime(2024, 1, 1, 3, 0)
    calc.accumulate_particles(particles, current_time)
    
    # Check that total mass was accumulated
    assert np.sum(calc.mass_accumulated) == pytest.approx(6.0)  # 1 + 2 + 3


def test_accumulate_particles_outside_sampling_period():
    """Test that particles outside sampling period are not accumulated."""
    config = ConcentrationGridConfig(
        center_lat=37.5,
        center_lon=127.0,
        spacing_lat=0.1,
        spacing_lon=0.1,
        span_lat=1.0,
        span_lon=1.0,
        levels=[0.0, 500.0, 1000.0],
        sampling_start=datetime(2024, 1, 1, 0, 0),
        sampling_end=datetime(2024, 1, 1, 6, 0),
        averaging_period=6,
    )
    
    calc = ConcentrationCalculator(config)
    
    particles = ParticleState(
        lon=np.array([127.0]),
        lat=np.array([37.5]),
        z=np.array([500.0]),
        mass=np.array([1.0]),
        age=np.array([0.0]),
        active=np.array([True]),
        species_id=np.array([0]),
    )
    
    # Try to accumulate before sampling period
    current_time = datetime(2023, 12, 31, 23, 0)
    calc.accumulate_particles(particles, current_time)
    
    # No mass should be accumulated
    assert np.sum(calc.mass_accumulated) == 0.0


def test_accumulate_inactive_particles():
    """Test that inactive particles are not accumulated."""
    config = ConcentrationGridConfig(
        center_lat=37.5,
        center_lon=127.0,
        spacing_lat=0.1,
        spacing_lon=0.1,
        span_lat=1.0,
        span_lon=1.0,
        levels=[0.0, 500.0, 1000.0],
        sampling_start=datetime(2024, 1, 1, 0, 0),
        sampling_end=datetime(2024, 1, 1, 6, 0),
        averaging_period=6,
    )
    
    calc = ConcentrationCalculator(config)
    
    particles = ParticleState(
        lon=np.array([127.0, 127.1]),
        lat=np.array([37.5, 37.6]),
        z=np.array([500.0, 500.0]),
        mass=np.array([1.0, 2.0]),
        age=np.array([0.0, 0.0]),
        active=np.array([True, False]),  # Second particle inactive
        species_id=np.array([0, 0]),
    )
    
    current_time = datetime(2024, 1, 1, 3, 0)
    calc.accumulate_particles(particles, current_time)
    
    # Only active particle (mass=1.0) should be accumulated
    assert np.sum(calc.mass_accumulated) == pytest.approx(1.0)


def test_compute_concentration():
    """Test concentration computation from accumulated mass."""
    config = ConcentrationGridConfig(
        center_lat=37.5,
        center_lon=127.0,
        spacing_lat=0.1,
        spacing_lon=0.1,
        span_lat=1.0,
        span_lon=1.0,
        levels=[0.0, 500.0, 1000.0],
        sampling_start=datetime(2024, 1, 1, 0, 0),
        sampling_end=datetime(2024, 1, 1, 6, 0),
        averaging_period=6,
    )
    
    calc = ConcentrationCalculator(config)
    
    # Manually set some accumulated mass
    calc.mass_accumulated[1, 5, 5] = 1.0  # 1 kg at center
    calc.sample_count[1, 5, 5] = 10  # 10 samples
    
    # Compute concentration
    grid = calc.compute_concentration()
    
    # Check grid metadata
    assert grid.start_time == config.sampling_start
    assert grid.end_time == config.sampling_end
    assert len(grid.lat_grid) == len(calc.lat_grid)
    
    # Check concentration is positive where mass was accumulated
    assert grid.concentration[1, 5, 5] > 0.0
    
    # Check concentration units (mass/volume/samples)
    # Should be less than original mass since divided by volume and samples
    assert grid.concentration[1, 5, 5] < 1.0


def test_cell_volume_calculation():
    """Test that cell volumes are calculated correctly."""
    config = ConcentrationGridConfig(
        center_lat=37.5,
        center_lon=127.0,
        spacing_lat=0.1,
        spacing_lon=0.1,
        span_lat=1.0,
        span_lon=1.0,
        levels=[0.0, 500.0, 1000.0],
        sampling_start=datetime(2024, 1, 1, 0, 0),
        sampling_end=datetime(2024, 1, 1, 6, 0),
        averaging_period=6,
    )
    
    calc = ConcentrationCalculator(config)
    volumes = calc._calculate_cell_volumes()
    
    # Check shape
    assert volumes.shape == (3, 11, 11)  # (nz, ny, nx)
    
    # All volumes should be positive
    assert np.all(volumes > 0)
    
    # Volumes should vary with latitude (smaller at higher latitudes)
    # due to cos(lat) factor
    assert volumes[0, 0, 0] > volumes[0, -1, 0]


def test_reset():
    """Test that reset clears accumulation arrays."""
    config = ConcentrationGridConfig(
        center_lat=37.5,
        center_lon=127.0,
        spacing_lat=0.1,
        spacing_lon=0.1,
        span_lat=1.0,
        span_lon=1.0,
        levels=[0.0, 500.0, 1000.0],
        sampling_start=datetime(2024, 1, 1, 0, 0),
        sampling_end=datetime(2024, 1, 1, 6, 0),
        averaging_period=6,
    )
    
    calc = ConcentrationCalculator(config)
    
    # Add some mass
    calc.mass_accumulated[1, 5, 5] = 1.0
    calc.sample_count[1, 5, 5] = 10
    
    # Reset
    calc.reset()
    
    # Check arrays are cleared
    assert np.all(calc.mass_accumulated == 0.0)
    assert np.all(calc.sample_count == 0)


def test_get_concentration_at_point():
    """Test interpolation of concentration at arbitrary point."""
    config = ConcentrationGridConfig(
        center_lat=37.5,
        center_lon=127.0,
        spacing_lat=0.1,
        spacing_lon=0.1,
        span_lat=1.0,
        span_lon=1.0,
        levels=[0.0, 500.0, 1000.0],
        sampling_start=datetime(2024, 1, 1, 0, 0),
        sampling_end=datetime(2024, 1, 1, 6, 0),
        averaging_period=6,
    )
    
    calc = ConcentrationCalculator(config)
    
    # Set up a simple concentration field
    calc.mass_accumulated[1, 5, 5] = 1.0
    calc.sample_count[1, 5, 5] = 1
    
    grid = calc.compute_concentration()
    
    # Query at grid point (should return exact value)
    conc = calc.get_concentration_at_point(127.0, 37.5, 500.0, grid)
    assert conc == pytest.approx(grid.concentration[1, 5, 5])
    
    # Query at point between grid points (should interpolate)
    conc_interp = calc.get_concentration_at_point(127.05, 37.55, 500.0, grid)
    assert conc_interp >= 0.0


def test_mass_conservation():
    """Test that total mass is conserved during distribution."""
    config = ConcentrationGridConfig(
        center_lat=37.5,
        center_lon=127.0,
        spacing_lat=0.1,
        spacing_lon=0.1,
        span_lat=1.0,
        span_lon=1.0,
        levels=[0.0, 500.0, 1000.0],
        sampling_start=datetime(2024, 1, 1, 0, 0),
        sampling_end=datetime(2024, 1, 1, 6, 0),
        averaging_period=6,
    )
    
    # Test both kernel types
    for kernel_type in ["top_hat", "gaussian"]:
        calc = ConcentrationCalculator(config, kernel_type=kernel_type)
        
        total_mass = 0.0
        for _ in range(10):
            lon = 127.0 + np.random.uniform(-0.3, 0.3)
            lat = 37.5 + np.random.uniform(-0.3, 0.3)
            z = 500.0
            mass = np.random.uniform(0.1, 1.0)
            
            calc._distribute_mass(lon, lat, z, mass)
            total_mass += mass
        
        # Check mass conservation
        accumulated_mass = np.sum(calc.mass_accumulated)
        assert accumulated_mass == pytest.approx(total_mass, rel=1e-2)
