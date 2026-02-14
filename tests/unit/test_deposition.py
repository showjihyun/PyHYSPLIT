"""Unit tests for deposition module."""

import numpy as np
import pytest

from pyhysplit.core.models import SimulationConfig, StartLocation
from pyhysplit.physics.deposition import DepositionModule
from datetime import datetime


def _make_config(dry_dep=True, wet_dep=True):
    """Create a minimal SimulationConfig for testing."""
    return SimulationConfig(
        start_time=datetime(2024, 1, 1),
        num_start_locations=1,
        start_locations=[StartLocation(lat=37.0, lon=127.0, height=500.0)],
        total_run_hours=24,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[],
        dry_deposition=dry_dep,
        wet_deposition=wet_dep,
    )


def test_gravitational_settling():
    """Test Stokes settling velocity calculation."""
    config = _make_config()
    depo = DepositionModule(config, particle_diameter=1e-5, particle_density=1000.0)
    
    # Calculate settling velocity
    v_g = depo.gravitational_settling(1e-5, 1000.0)
    
    # Should be positive (downward)
    assert v_g > 0
    
    # Larger particles settle faster
    v_g_large = depo.gravitational_settling(1e-4, 1000.0)
    assert v_g_large > v_g


def test_dry_deposition_velocity():
    """Test 3-resistance dry deposition velocity."""
    config = _make_config()
    depo = DepositionModule(config)
    
    r_a = 10.0  # s/m
    r_b = 5.0   # s/m
    r_s = 100.0 # s/m
    v_g = 0.01  # m/s
    
    v_d = depo.dry_deposition_velocity(r_a, r_b, r_s, v_g)
    
    # Should be at least v_g
    assert v_d >= v_g
    
    # Should be positive
    assert v_d > 0


def test_below_cloud_scavenging():
    """Test below-cloud scavenging coefficient."""
    config = _make_config()
    depo = DepositionModule(config)
    
    # No precipitation
    lambda_0 = depo.below_cloud_scavenging(0.0)
    assert lambda_0 == 0.0
    
    # With precipitation
    lambda_1 = depo.below_cloud_scavenging(1.0)  # 1 mm/h
    lambda_10 = depo.below_cloud_scavenging(10.0)  # 10 mm/h
    
    # Should be positive
    assert lambda_1 > 0
    assert lambda_10 > 0
    
    # Higher precipitation → higher scavenging
    assert lambda_10 > lambda_1


def test_in_cloud_scavenging():
    """Test in-cloud scavenging coefficient."""
    config = _make_config()
    depo = DepositionModule(config)
    
    cloud_base = 1000.0  # m
    cloud_top = 3000.0   # m
    precip_rate = 5.0    # mm/h
    
    # Below cloud
    lambda_below = depo.in_cloud_scavenging(precip_rate, cloud_base, cloud_top, 500.0)
    assert lambda_below == 0.0
    
    # In cloud
    lambda_in = depo.in_cloud_scavenging(precip_rate, cloud_base, cloud_top, 2000.0)
    assert lambda_in > 0.0
    
    # Above cloud
    lambda_above = depo.in_cloud_scavenging(precip_rate, cloud_base, cloud_top, 4000.0)
    assert lambda_above == 0.0


def test_apply_deposition():
    """Test mass decay from deposition."""
    config = _make_config()
    depo = DepositionModule(config)
    
    mass = 1.0  # kg
    v_d = 0.01  # m/s
    dz = 100.0  # m
    scav_coeff = 1e-5  # s^-1
    dt = 3600.0  # 1 hour
    
    new_mass = depo.apply_deposition(mass, v_d, dz, scav_coeff, dt)
    
    # Mass should decrease
    assert new_mass < mass
    
    # Mass should be positive
    assert new_mass > 0


def test_gaseous_dry_deposition_velocity():
    """Test gaseous dry deposition using Henry's law."""
    config = _make_config()
    depo = DepositionModule(config, henry_constant=1000.0)
    
    r_a = 10.0
    r_b = 5.0
    henry_const = 1000.0  # Highly soluble
    
    v_d = depo.gaseous_dry_deposition_velocity(henry_const, r_a, r_b)
    
    # Should be positive
    assert v_d > 0
    
    # Higher Henry's constant → higher deposition velocity
    v_d_low = depo.gaseous_dry_deposition_velocity(10.0, r_a, r_b)
    assert v_d > v_d_low


def test_apply_deposition_step_no_deposition():
    """Test that no deposition occurs when disabled."""
    config = _make_config(dry_dep=False, wet_dep=False)
    depo = DepositionModule(config)
    
    mass = 1.0
    z = 500.0
    precip_rate = 5.0
    cloud_base = 1000.0
    cloud_top = 3000.0
    ustar = 0.3
    dt = 3600.0
    
    new_mass, dz = depo.apply_deposition_step(
        mass, z, precip_rate, cloud_base, cloud_top, ustar, dt
    )
    
    # Mass should be unchanged
    assert new_mass == mass
    
    # No vertical displacement
    assert dz == 0.0


def test_apply_deposition_step_dry_only():
    """Test dry deposition only."""
    config = _make_config(dry_dep=True, wet_dep=False)
    depo = DepositionModule(config, particle_diameter=1e-5, particle_density=1000.0)
    
    mass = 1.0
    z = 500.0
    precip_rate = 0.0  # No precipitation
    cloud_base = 1000.0
    cloud_top = 3000.0
    ustar = 0.3
    dt = 3600.0
    
    new_mass, dz = depo.apply_deposition_step(
        mass, z, precip_rate, cloud_base, cloud_top, ustar, dt
    )
    
    # Mass should decrease due to dry deposition
    assert new_mass < mass
    
    # Should have vertical displacement due to settling
    assert dz < 0  # Negative = downward


def test_apply_deposition_step_wet_only():
    """Test wet deposition only."""
    config = _make_config(dry_dep=False, wet_dep=True)
    depo = DepositionModule(config)
    
    mass = 1.0
    z = 2000.0  # In cloud
    precip_rate = 5.0
    cloud_base = 1000.0
    cloud_top = 3000.0
    ustar = 0.3
    dt = 3600.0
    
    new_mass, dz = depo.apply_deposition_step(
        mass, z, precip_rate, cloud_base, cloud_top, ustar, dt
    )
    
    # Mass should decrease due to wet deposition
    assert new_mass < mass


def test_apply_deposition_step_both():
    """Test combined dry and wet deposition."""
    config = _make_config(dry_dep=True, wet_dep=True)
    depo = DepositionModule(config, particle_diameter=1e-5, particle_density=1000.0)
    
    mass = 1.0
    z = 2000.0  # In cloud
    precip_rate = 5.0
    cloud_base = 1000.0
    cloud_top = 3000.0
    ustar = 0.3
    dt = 3600.0
    
    new_mass, dz = depo.apply_deposition_step(
        mass, z, precip_rate, cloud_base, cloud_top, ustar, dt
    )
    
    # Mass should decrease due to both processes
    assert new_mass < mass
    
    # Should have vertical displacement
    assert dz < 0


def test_apply_deposition_step_gaseous():
    """Test gaseous species deposition."""
    config = _make_config(dry_dep=True, wet_dep=False)
    depo = DepositionModule(config, henry_constant=1000.0)
    
    mass = 1.0
    z = 500.0
    precip_rate = 0.0
    cloud_base = 1000.0
    cloud_top = 3000.0
    ustar = 0.3
    dt = 3600.0
    
    new_mass, dz = depo.apply_deposition_step(
        mass, z, precip_rate, cloud_base, cloud_top, ustar, dt,
        is_gaseous=True
    )
    
    # Mass should decrease
    assert new_mass < mass
    
    # No settling for gases
    assert dz == 0.0


def test_aerodynamic_resistance():
    """Test aerodynamic resistance calculation."""
    config = _make_config()
    depo = DepositionModule(config)
    
    z = 100.0  # m
    ustar = 0.3  # m/s
    
    r_a = depo._aerodynamic_resistance(z, ustar)
    
    # Should be positive
    assert r_a > 0
    
    # Higher friction velocity → lower resistance
    r_a_high = depo._aerodynamic_resistance(z, 0.6)
    assert r_a_high < r_a


def test_quasi_laminar_resistance():
    """Test quasi-laminar resistance calculation."""
    config = _make_config()
    depo = DepositionModule(config)
    
    ustar = 0.3
    r_b = depo._quasi_laminar_resistance(ustar)
    
    # Should be positive
    assert r_b > 0
    
    # Higher friction velocity → lower resistance
    r_b_high = depo._quasi_laminar_resistance(0.6)
    assert r_b_high < r_b


def test_surface_resistance():
    """Test surface resistance calculation."""
    config = _make_config()
    depo = DepositionModule(config)
    
    r_s = depo._surface_resistance()
    
    # Should be positive
    assert r_s > 0


def test_depletion_threshold():
    """Test depletion threshold calculation."""
    config = _make_config()
    depo = DepositionModule(config)
    
    initial_mass = 1.0
    threshold = depo.get_depletion_threshold(initial_mass)
    
    # Should be 1% of initial mass
    assert threshold == pytest.approx(0.01)
    
    # Test with different initial mass
    threshold_10 = depo.get_depletion_threshold(10.0)
    assert threshold_10 == pytest.approx(0.1)


def test_mass_conservation_property():
    """Property test: mass should always decrease or stay same."""
    config = _make_config()
    depo = DepositionModule(config)
    
    for _ in range(100):
        mass = np.random.uniform(0.1, 10.0)
        v_d = np.random.uniform(0.0, 0.1)
        dz = np.random.uniform(10.0, 1000.0)
        scav_coeff = np.random.uniform(0.0, 1e-4)
        dt = np.random.uniform(60.0, 3600.0)
        
        new_mass = depo.apply_deposition(mass, v_d, dz, scav_coeff, dt)
        
        # Mass should never increase
        assert new_mass <= mass
        
        # Mass should always be positive
        assert new_mass > 0
