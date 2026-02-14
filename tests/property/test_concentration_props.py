"""Property-based tests for the ConcentrationGrid.

Properties 24-25 from the HYSPLIT Trajectory Engine design document.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
from hypothesis import given, settings, assume, strategies as st

from pyhysplit.models import (
    ConcentrationGridConfig,
    ParticleState,
)
from pyhysplit.concentration_grid import ConcentrationGrid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_grid_config(
    center_lat: float = 40.0,
    center_lon: float = -100.0,
    spacing_lat: float = 1.0,
    spacing_lon: float = 1.0,
    span_lat: float = 10.0,
    span_lon: float = 10.0,
    levels: list[float] | None = None,
) -> ConcentrationGridConfig:
    if levels is None:
        levels = [0.0, 500.0, 1000.0, 5000.0]
    return ConcentrationGridConfig(
        center_lat=center_lat,
        center_lon=center_lon,
        spacing_lat=spacing_lat,
        spacing_lon=spacing_lon,
        span_lat=span_lat,
        span_lon=span_lon,
        levels=levels,
        sampling_start=datetime(2024, 1, 1),
        sampling_end=datetime(2024, 1, 2),
        averaging_period=1,
    )


def _make_particles_in_grid(
    n: int,
    grid: ConcentrationGrid,
    species_id: int = 0,
    mass: float = 1.0,
) -> ParticleState:
    """Create *n* active particles randomly placed inside the grid bounds."""
    rng = np.random.default_rng(42)
    lon_min, lon_max = grid.lon_edges[0], grid.lon_edges[-1]
    lat_min, lat_max = grid.lat_edges[0], grid.lat_edges[-1]
    z_min, z_max = grid.z_edges[0], grid.z_edges[-1]

    # Keep particles strictly inside edges
    eps = 1e-6
    lons = rng.uniform(lon_min + eps, lon_max - eps, n)
    lats = rng.uniform(lat_min + eps, lat_max - eps, n)
    zs = rng.uniform(z_min + eps, z_max - eps, n)

    return ParticleState(
        lon=lons,
        lat=lats,
        z=zs,
        mass=np.full(n, mass, dtype=np.float64),
        age=np.zeros(n, dtype=np.float64),
        active=np.ones(n, dtype=bool),
        species_id=np.full(n, species_id, dtype=np.int32),
    )


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

n_particles_st = st.integers(min_value=1, max_value=50)
mass_st = st.floats(min_value=1e-6, max_value=1e6,
                    allow_nan=False, allow_infinity=False)


# ---------------------------------------------------------------------------
# Property 24: 농도 질량 보존 (Concentration Mass Conservation)
# Validates: Requirements 9.2
# ---------------------------------------------------------------------------

@given(n=n_particles_st, mass=mass_st)
@settings(max_examples=200)
def test_property_24_concentration_mass_conservation(n, mass):
    """**Validates: Requirements 9.2**

    Feature: hysplit-trajectory-engine, Property 24: 농도 질량 보존
    Σ(C·V) over all grid cells must equal Σm of active particles.
    """
    cfg = _make_grid_config()
    grid = ConcentrationGrid(cfg, num_species=1)
    particles = _make_particles_in_grid(n, grid, species_id=0, mass=mass)

    grid.accumulate(particles)

    total_grid_mass = grid.total_grid_mass(species_id=0)
    total_particle_mass = float(np.sum(particles.mass[particles.active]))

    assert abs(total_grid_mass - total_particle_mass) < 1e-6 * max(total_particle_mass, 1e-30), (
        f"Mass not conserved: grid={total_grid_mass}, particles={total_particle_mass}"
    )


# ---------------------------------------------------------------------------
# Property 25: 다중 오염 종 격자 독립성 (Species Grid Independence)
# Validates: Requirements 9.5
# ---------------------------------------------------------------------------

@given(n_a=st.integers(min_value=1, max_value=30),
       n_b=st.integers(min_value=1, max_value=30),
       mass_a=mass_st, mass_b=mass_st)
@settings(max_examples=200)
def test_property_25_species_grid_independence(n_a, n_b, mass_a, mass_b):
    """**Validates: Requirements 9.5**

    Feature: hysplit-trajectory-engine, Property 25: 다중 종 격자 독립성
    Adding species-A particles must not change species-B concentration grid.
    """
    cfg = _make_grid_config()
    grid = ConcentrationGrid(cfg, num_species=2)

    # First accumulate species B only and snapshot its grid
    particles_b = _make_particles_in_grid(n_b, grid, species_id=1, mass=mass_b)
    grid.accumulate(particles_b)
    grid_b_before = grid.grids[1].copy()

    # Now accumulate species A particles
    particles_a = _make_particles_in_grid(n_a, grid, species_id=0, mass=mass_a)
    grid.accumulate(particles_a)
    grid_b_after = grid.grids[1].copy()

    # Species B grid must be unchanged by species A accumulation
    np.testing.assert_array_equal(
        grid_b_before, grid_b_after,
        err_msg="Species B grid changed after adding species A particles",
    )
