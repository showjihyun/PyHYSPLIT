"""Property-based tests for the CoordinateConverter module.

Properties 13-15 from the HYSPLIT Trajectory Engine design document.
Property 1 from the Trajectory Engine Early Termination Bugfix design document.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings, assume, strategies as st

from pyhysplit.coordinate_converter import CoordinateConverter


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Sigma in (0, 1) — valid range
valid_sigma = st.floats(min_value=0.01, max_value=0.99,
                        allow_nan=False, allow_infinity=False)

# Surface pressure: realistic range 800-1100 hPa in Pa
valid_p_sfc = st.floats(min_value=80000.0, max_value=110000.0,
                        allow_nan=False, allow_infinity=False)

# Model top pressure: small positive value
valid_p_top = st.floats(min_value=0.0, max_value=5000.0,
                        allow_nan=False, allow_infinity=False)

# Pressure for height conversion: 1 Pa to 110000 Pa
valid_pressure = st.floats(min_value=1.0, max_value=110000.0,
                           allow_nan=False, allow_infinity=False)

# Height: 0 to 50 km
valid_height = st.floats(min_value=0.0, max_value=50000.0,
                         allow_nan=False, allow_infinity=False)

# AGL height and terrain height (non-negative)
valid_z_agl = st.floats(min_value=0.0, max_value=30000.0,
                        allow_nan=False, allow_infinity=False)
valid_terrain = st.floats(min_value=0.0, max_value=9000.0,
                          allow_nan=False, allow_infinity=False)

# Hybrid coefficients: A >= 0, 0 <= B <= 1
valid_A_coeff = st.floats(min_value=0.0, max_value=50000.0,
                          allow_nan=False, allow_infinity=False)
valid_B_coeff = st.floats(min_value=0.0, max_value=1.0,
                          allow_nan=False, allow_infinity=False)


# ---------------------------------------------------------------------------
# Property 1: Height to Pressure Conversion Correctness
# Validates: Requirements 1.2, 1.4
# ---------------------------------------------------------------------------

@given(height=valid_height)
@settings(max_examples=20)
def test_property_1_height_to_pressure_conversion_correctness(height):
    """**Validates: Requirements 1.2, 1.4**

    Feature: trajectory-engine-early-termination-bugfix, Property 1: Height to Pressure Conversion Correctness
    For any height value in meters, when converted to pressure using the standard
    atmosphere approximation, the result should satisfy P = P0 * exp(-z / H)
    where P0=101325 Pa and H=8500 m.
    """
    z = np.array([height])
    P0 = 101325.0  # Pa
    H = 8500.0     # m
    
    # Convert height to pressure using the CoordinateConverter
    pressure = CoordinateConverter.height_to_pressure(z, P0=P0, H=H)
    
    # Verify the result matches the formula P = P0 * exp(-z / H)
    expected_pressure = P0 * np.exp(-z / H)
    
    np.testing.assert_allclose(pressure, expected_pressure, rtol=1e-12)
    
    # Additional validation: pressure should be positive and less than P0
    assert np.all(pressure > 0), f"Pressure must be positive, got {pressure}"
    assert np.all(pressure <= P0), f"Pressure must be <= P0={P0}, got {pressure}"


# ---------------------------------------------------------------------------
# Property 13: 좌표 변환 Round Trip
# Validates: Requirements 6.1, 6.2
# ---------------------------------------------------------------------------

@given(sigma=valid_sigma, p_sfc=valid_p_sfc, p_top=valid_p_top)
@settings(max_examples=20)
def test_property_13_sigma_pressure_round_trip(sigma, p_sfc, p_top):
    """**Validates: Requirements 6.1, 6.2**

    Feature: hysplit-trajectory-engine, Property 13: 좌표 변환 Round Trip
    sigma -> pressure -> sigma must recover the original sigma value.
    """
    assume(p_sfc > p_top)

    s = np.array([sigma])
    ps = np.array([p_sfc])

    pressure = CoordinateConverter.sigma_to_pressure(s, ps, p_top)
    sigma_back = CoordinateConverter.pressure_to_sigma(pressure, ps, p_top)

    np.testing.assert_allclose(sigma_back, s, atol=1e-12)


@given(pressure=valid_pressure)
@settings(max_examples=20)
def test_property_13_pressure_height_round_trip(pressure):
    """**Validates: Requirements 6.1, 6.2**

    Feature: hysplit-trajectory-engine, Property 13: 좌표 변환 Round Trip
    pressure -> height -> pressure (standard atmosphere) must recover
    the original pressure value.
    """
    P = np.array([pressure])

    height = CoordinateConverter.pressure_to_height(P)
    P_back = CoordinateConverter.height_to_pressure(height)

    np.testing.assert_allclose(P_back, P, rtol=1e-12)


# ---------------------------------------------------------------------------
# Property 14: Hybrid 좌표 양수 기압
# Validates: Requirements 6.3
# ---------------------------------------------------------------------------

@given(
    A=valid_A_coeff,
    B=valid_B_coeff,
    p_sfc=valid_p_sfc,
)
@settings(max_examples=20)
def test_property_14_hybrid_pressure_positive(A, B, p_sfc):
    """**Validates: Requirements 6.3**

    Feature: hysplit-trajectory-engine, Property 14: Hybrid 좌표 양수 기압
    hybrid_to_pressure must always return positive pressure when
    A >= 0, B >= 0, and P_sfc > 0.
    """
    A_arr = np.array([A])
    B_arr = np.array([B])

    result = CoordinateConverter.hybrid_to_pressure(A_arr, B_arr, p_sfc)

    assert np.all(result > 0) or (A == 0.0 and B == 0.0), \
        f"Expected positive pressure, got {result}"
    # When both A and B are zero, pressure is zero — skip that edge case
    assume(A > 0 or B > 0)
    assert np.all(result > 0), f"Expected positive pressure, got {result}"


# ---------------------------------------------------------------------------
# Property 15: 지형 보정 불변량
# Validates: Requirements 6.4
# ---------------------------------------------------------------------------

@given(z_agl=valid_z_agl, terrain_h=valid_terrain)
@settings(max_examples=20)
def test_property_15_terrain_correction_invariant(z_agl, terrain_h):
    """**Validates: Requirements 6.4**

    Feature: hysplit-trajectory-engine, Property 15: 지형 보정 불변량
    terrain_correction(z_agl, terrain_h) = z_agl + terrain_h,
    and the result is always >= terrain_h.
    """
    z = np.array([z_agl])
    t = np.array([terrain_h])

    result = CoordinateConverter.terrain_correction(z, t)

    np.testing.assert_allclose(result, z + t, atol=1e-12)
    assert np.all(result >= terrain_h), \
        f"Result {result} should be >= terrain_h {terrain_h}"


# ---------------------------------------------------------------------------
# Property 2: Coordinate System Conditional Conversion
# Validates: Requirements 1.1, 1.3
# ---------------------------------------------------------------------------

# Additional strategies for Property 2
from datetime import datetime
from pyhysplit.models import MetData, SimulationConfig, StartLocation, InvalidCoordinateError
from pyhysplit.engine import TrajectoryEngine

# Height for start locations: 0 to 5000m (realistic range)
start_location_height = st.floats(min_value=0.0, max_value=5000.0,
                                   allow_nan=False, allow_infinity=False)

# Latitude and longitude
valid_lat = st.floats(min_value=-90.0, max_value=90.0,
                      allow_nan=False, allow_infinity=False)
valid_lon = st.floats(min_value=-180.0, max_value=180.0,
                      allow_nan=False, allow_infinity=False)

# Coordinate system type
z_type_strategy = st.sampled_from(["pressure", "height"])


@st.composite
def start_location_strategy(draw):
    """Generate a random StartLocation."""
    lat = draw(valid_lat)
    lon = draw(valid_lon)
    height = draw(start_location_height)
    return StartLocation(lat=lat, lon=lon, height=height)


def met_data_strategy(z_type):
    """Generate a random MetData with specified z_type.
    
    For pressure coordinates: z_grid in range [200, 1000] hPa
    For height coordinates: z_grid in range [0, 10000] m
    """
    # Simple 2x2 spatial grid
    lon_grid = np.array([0.0, 1.0])
    lat_grid = np.array([0.0, 1.0])
    
    # Time grid: 2 time steps
    t_grid = np.array([0.0, 3600.0])
    
    # Generate z_grid based on z_type
    if z_type == "pressure":
        # Pressure coordinates: 200-1000 hPa (descending order typical for pressure)
        z_grid = np.array([200.0, 500.0, 850.0, 1000.0])
    else:
        # Height coordinates: 0-10000 m (ascending order)
        z_grid = np.array([0.0, 500.0, 1000.0, 5000.0, 10000.0])
    
    # Create dummy wind fields with correct shape
    if z_type == "pressure":
        shape = (2, 4, 2, 2)  # (t, z, lat, lon)
    else:
        shape = (2, 5, 2, 2)
    
    u = np.zeros(shape)
    v = np.zeros(shape)
    w = np.zeros(shape)
    
    return st.just(MetData(
        lon_grid=lon_grid,
        lat_grid=lat_grid,
        z_grid=z_grid,
        t_grid=t_grid,
        u=u,
        v=v,
        w=w,
        z_type=z_type,
    ))


@given(
    z_type=z_type_strategy,
    start_loc=start_location_strategy(),
    data=st.data(),
)
@settings(max_examples=20)
def test_property_2_coordinate_system_conditional_conversion(z_type, start_loc, data):
    """**Validates: Requirements 1.1, 1.3**

    Feature: trajectory-engine-early-termination-bugfix, Property 2: Coordinate System Conditional Conversion
    For any StartLocation and MetData pair, if MetData.z_type == "pressure",
    then the height should be converted to pressure; if MetData.z_type == "height",
    then the height should be used directly without conversion.
    """
    # Generate MetData with the specified z_type
    met = data.draw(met_data_strategy(z_type=z_type))
    
    # Create a minimal SimulationConfig
    config = SimulationConfig(
        start_time=datetime(2024, 1, 1, 0, 0),
        num_start_locations=1,
        start_locations=[start_loc],
        total_run_hours=-7,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[(".", "test.arl")],
    )
    
    # Convert the height using CoordinateConverter to get expected value
    if z_type == "pressure":
        # Convert height to pressure
        pressure_pa = CoordinateConverter.height_to_pressure(
            np.array([start_loc.height])
        )[0]
        expected_z = pressure_pa / 100.0  # Convert Pa to hPa
        
        # Skip if the converted pressure is outside the valid range
        # (this would raise InvalidCoordinateError during initialization)
        z_min, z_max = met.z_grid[0], met.z_grid[-1]
        assume(z_min <= expected_z <= z_max)
    else:
        # Height coordinates: use directly
        expected_z = start_loc.height
        
        # Skip if the height is outside the valid range
        z_min, z_max = met.z_grid[0], met.z_grid[-1]
        assume(z_min <= expected_z <= z_max)
    
    # Initialize the engine
    engine = TrajectoryEngine(config=config, met=met)
    
    # Call the validation method directly to get converted coordinates
    converted = engine._validate_and_convert_start_locations()
    
    # Verify we have exactly one converted location
    assert len(converted) == 1
    
    lon, lat, z_converted = converted[0]
    
    # Verify lon and lat are unchanged
    assert lon == start_loc.lon
    assert lat == start_loc.lat
    
    # Verify the conversion logic based on z_type
    if z_type == "pressure":
        # For pressure coordinates, verify conversion occurred
        # The converted value should match our expected pressure in hPa
        np.testing.assert_allclose(z_converted, expected_z, rtol=1e-6)
        
        # Verify it's different from the original height (unless by coincidence)
        # and is within the valid pressure range
        assert met.z_grid[0] <= z_converted <= met.z_grid[-1]
    else:
        # For height coordinates, verify no conversion (direct use)
        assert z_converted == start_loc.height
        
        # Verify it's within the valid height range
        assert met.z_grid[0] <= z_converted <= met.z_grid[-1]


# ---------------------------------------------------------------------------
# Property 3: Initialization Validation Catches Invalid Coordinates
# Validates: Requirements 4.1, 4.2
# ---------------------------------------------------------------------------

# Strategy for heights that will convert to out-of-range pressures
# For pressure coordinates with range [200, 1000] hPa:
# - Heights > ~16000m convert to pressures < 200 hPa (too low)
# - Heights < 0m would be invalid (but we'll use very low heights that are still positive)
out_of_range_height_high = st.floats(min_value=16000.0, max_value=50000.0,
                                      allow_nan=False, allow_infinity=False)

# For testing out-of-range on the low end (high pressure), we need negative heights
# or we can use a MetData with a restricted range
# Let's use a strategy that generates heights that will be out of range


@st.composite
def out_of_range_start_location_strategy(draw, z_type):
    """Generate a StartLocation that will be out of range for the given z_type.
    
    For pressure coordinates:
    - High heights (>16000m) convert to low pressures (<200 hPa)
    
    For height coordinates:
    - Heights outside the MetData range
    """
    lat = draw(valid_lat)
    lon = draw(valid_lon)
    
    if z_type == "pressure":
        # Generate heights that convert to pressures outside [200, 1000] hPa
        # Heights > 16000m convert to pressures < 200 hPa
        height = draw(out_of_range_height_high)
    else:
        # For height coordinates, generate heights outside [0, 10000] m
        # Either negative or very high
        choice = draw(st.sampled_from(["too_high"]))
        if choice == "too_high":
            height = draw(st.floats(min_value=15000.0, max_value=50000.0,
                                   allow_nan=False, allow_infinity=False))
    
    return StartLocation(lat=lat, lon=lon, height=height)


def out_of_range_met_data_strategy(z_type):
    """Generate MetData with a restricted range to make it easier to create out-of-range coordinates."""
    lon_grid = np.array([0.0, 1.0])
    lat_grid = np.array([0.0, 1.0])
    t_grid = np.array([0.0, 3600.0])
    
    if z_type == "pressure":
        # Pressure coordinates: 200-1000 hPa
        z_grid = np.array([200.0, 500.0, 850.0, 1000.0])
        shape = (2, 4, 2, 2)
    else:
        # Height coordinates: 0-10000 m
        z_grid = np.array([0.0, 500.0, 1000.0, 5000.0, 10000.0])
        shape = (2, 5, 2, 2)
    
    u = np.zeros(shape)
    v = np.zeros(shape)
    w = np.zeros(shape)
    
    return st.just(MetData(
        lon_grid=lon_grid,
        lat_grid=lat_grid,
        z_grid=z_grid,
        t_grid=t_grid,
        u=u,
        v=v,
        w=w,
        z_type=z_type,
    ))


@given(
    z_type=z_type_strategy,
    data=st.data(),
)
@settings(max_examples=20)
def test_property_3_initialization_validation_catches_invalid_coordinates(z_type, data):
    """**Validates: Requirements 4.1, 4.2**

    Feature: trajectory-engine-early-termination-bugfix, Property 3: Initialization Validation Catches Invalid Coordinates
    For any StartLocation whose height converts to a value outside the MetData.z_grid range,
    initializing a TrajectoryEngine should raise an InvalidCoordinateError.
    """
    # Generate an out-of-range start location
    start_loc = data.draw(out_of_range_start_location_strategy(z_type=z_type))
    
    # Generate MetData with the specified z_type
    met = data.draw(out_of_range_met_data_strategy(z_type=z_type))
    
    # Create a minimal SimulationConfig
    config = SimulationConfig(
        start_time=datetime(2024, 1, 1, 0, 0),
        num_start_locations=1,
        start_locations=[start_loc],
        total_run_hours=-7,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[(".", "test.arl")],
    )
    
    # Verify that the height is indeed out of range
    if z_type == "pressure":
        # Convert height to pressure
        pressure_pa = CoordinateConverter.height_to_pressure(
            np.array([start_loc.height])
        )[0]
        z_converted = pressure_pa / 100.0  # Convert Pa to hPa
        
        z_min, z_max = met.z_grid[0], met.z_grid[-1]
        # Ensure the converted pressure is actually out of range
        assume(z_converted < z_min or z_converted > z_max)
    else:
        # Height coordinates
        z_converted = start_loc.height
        z_min, z_max = met.z_grid[0], met.z_grid[-1]
        # Ensure the height is actually out of range
        assume(z_converted < z_min or z_converted > z_max)
    
    # Initialize the engine - should raise InvalidCoordinateError
    with pytest.raises(InvalidCoordinateError) as exc_info:
        engine = TrajectoryEngine(config=config, met=met)
    
    # Verify the error message contains useful information
    error_msg = str(exc_info.value)
    assert "Start location" in error_msg
    assert "outside" in error_msg or "out" in error_msg.lower()
    
    if z_type == "pressure":
        assert "hPa" in error_msg
    else:
        assert "height" in error_msg.lower() or "m" in error_msg


# ---------------------------------------------------------------------------
# Property 4: Round-Trip Conversion Consistency
# Validates: Requirements 1.2
# ---------------------------------------------------------------------------

@given(height=valid_height)
@settings(max_examples=20)
def test_property_4_round_trip_conversion_consistency(height):
    """**Validates: Requirements 1.2**

    Feature: trajectory-engine-early-termination-bugfix, Property 4: Round-Trip Conversion Consistency
    For any height value that converts to a pressure within the valid range,
    converting back from pressure to height should yield approximately the same value
    (within numerical tolerance).
    """
    z = np.array([height])
    P0 = 101325.0  # Pa
    H = 8500.0     # m
    
    # Convert height to pressure
    pressure = CoordinateConverter.height_to_pressure(z, P0=P0, H=H)
    
    # Convert pressure back to height
    height_back = CoordinateConverter.pressure_to_height(pressure, P0=P0, H=H)
    
    # Verify result matches original within tolerance
    # Tolerance: 1% or 10m, whichever is larger
    tolerance = max(0.01 * height, 10.0)
    
    np.testing.assert_allclose(height_back, z, atol=tolerance)
    
    # Additional check: verify the absolute error is small
    # For the standard atmosphere formula, round-trip should be very accurate
    absolute_error = np.abs(height_back - z)
    assert np.all(absolute_error < 10.0), \
        f"Round-trip conversion error too large: {absolute_error}m for height {height}m"
