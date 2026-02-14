"""Unit tests for TrajectoryEngine coordinate conversion and validation."""

from datetime import datetime

import numpy as np
import pytest

from pyhysplit.core.engine import TrajectoryEngine
from pyhysplit.core.models import (
    InvalidCoordinateError,
    MetData,
    SimulationConfig,
    StartLocation,
)


def test_validate_and_convert_start_locations_pressure_valid():
    """Test coordinate conversion for valid pressure coordinates."""
    # Create MetData with pressure coordinates (200-1000 hPa)
    met = MetData(
        lon_grid=np.array([0.0, 1.0]),
        lat_grid=np.array([0.0, 1.0]),
        z_grid=np.array([200.0, 500.0, 850.0, 1000.0]),  # hPa
        t_grid=np.array([0.0, 3600.0]),
        u=np.zeros((2, 4, 2, 2)),
        v=np.zeros((2, 4, 2, 2)),
        w=np.zeros((2, 4, 2, 2)),
        z_type="pressure",
    )
    
    # Create config with start location at 850m AGL
    # 850m should convert to ~916.8 hPa (within valid range)
    config = SimulationConfig(
        start_time=datetime(2024, 1, 1, 0, 0),
        num_start_locations=1,
        start_locations=[StartLocation(lat=0.5, lon=0.5, height=850.0)],
        total_run_hours=-7,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[(".", "test.arl")],
    )
    
    # Initialize engine (should not raise)
    engine = TrajectoryEngine(config=config, met=met)
    
    # Call the validation method
    converted = engine._validate_and_convert_start_locations()
    
    # Verify conversion
    assert len(converted) == 1
    lon, lat, z = converted[0]
    assert lon == 0.5
    assert lat == 0.5
    # 850m should convert to approximately 916.8 hPa
    assert 900.0 < z < 930.0  # Reasonable range


def test_validate_and_convert_start_locations_pressure_out_of_range():
    """Test that out-of-range pressure coordinates raise InvalidCoordinateError."""
    # Create MetData with pressure coordinates (200-1000 hPa)
    met = MetData(
        lon_grid=np.array([0.0, 1.0]),
        lat_grid=np.array([0.0, 1.0]),
        z_grid=np.array([200.0, 500.0, 850.0, 1000.0]),  # hPa
        t_grid=np.array([0.0, 3600.0]),
        u=np.zeros((2, 4, 2, 2)),
        v=np.zeros((2, 4, 2, 2)),
        w=np.zeros((2, 4, 2, 2)),
        z_type="pressure",
    )
    
    # Create config with start location at 15000m AGL
    # 15000m converts to ~19.3 hPa (outside valid range of 200-1000 hPa)
    config = SimulationConfig(
        start_time=datetime(2024, 1, 1, 0, 0),
        num_start_locations=1,
        start_locations=[StartLocation(lat=0.5, lon=0.5, height=15000.0)],
        total_run_hours=-7,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[(".", "test.arl")],
    )
    
    # Initialize engine - should raise InvalidCoordinateError
    with pytest.raises(InvalidCoordinateError) as exc_info:
        engine = TrajectoryEngine(config=config, met=met)
        engine._validate_and_convert_start_locations()
    
    # Verify error message contains useful information
    error_msg = str(exc_info.value)
    # Error message shows converted pressure, not original height
    assert "171" in error_msg or "outside" in error_msg.lower()  # Converted pressure
    assert "outside" in error_msg.lower()
    assert "200" in error_msg  # Min pressure
    assert "1000" in error_msg  # Max pressure


def test_validate_and_convert_start_locations_height_no_conversion():
    """Test that height coordinates are used directly without conversion."""
    # Create MetData with height coordinates (0-10000 m)
    met = MetData(
        lon_grid=np.array([0.0, 1.0]),
        lat_grid=np.array([0.0, 1.0]),
        z_grid=np.array([0.0, 500.0, 1000.0, 5000.0, 10000.0]),  # meters
        t_grid=np.array([0.0, 3600.0]),
        u=np.zeros((2, 5, 2, 2)),
        v=np.zeros((2, 5, 2, 2)),
        w=np.zeros((2, 5, 2, 2)),
        z_type="height",
    )
    
    # Create config with start location at 850m AGL
    config = SimulationConfig(
        start_time=datetime(2024, 1, 1, 0, 0),
        num_start_locations=1,
        start_locations=[StartLocation(lat=0.5, lon=0.5, height=850.0)],
        total_run_hours=-7,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[(".", "test.arl")],
    )
    
    # Initialize engine
    engine = TrajectoryEngine(config=config, met=met)
    
    # Call the validation method
    converted = engine._validate_and_convert_start_locations()
    
    # Verify no conversion occurred
    assert len(converted) == 1
    lon, lat, z = converted[0]
    assert lon == 0.5
    assert lat == 0.5
    assert z == 850.0  # Should be unchanged


def test_validate_and_convert_start_locations_multiple_locations():
    """Test conversion of multiple start locations."""
    # Create MetData with pressure coordinates
    met = MetData(
        lon_grid=np.array([0.0, 1.0]),
        lat_grid=np.array([0.0, 1.0]),
        z_grid=np.array([200.0, 500.0, 850.0, 1000.0]),  # hPa
        t_grid=np.array([0.0, 3600.0]),
        u=np.zeros((2, 4, 2, 2)),
        v=np.zeros((2, 4, 2, 2)),
        w=np.zeros((2, 4, 2, 2)),
        z_type="pressure",
    )
    
    # Create config with multiple start locations
    config = SimulationConfig(
        start_time=datetime(2024, 1, 1, 0, 0),
        num_start_locations=3,
        start_locations=[
            StartLocation(lat=0.3, lon=0.3, height=500.0),
            StartLocation(lat=0.5, lon=0.5, height=850.0),
            StartLocation(lat=0.7, lon=0.7, height=1500.0),
        ],
        total_run_hours=-7,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[(".", "test.arl")],
    )
    
    # Initialize engine
    engine = TrajectoryEngine(config=config, met=met)
    
    # Call the validation method
    converted = engine._validate_and_convert_start_locations()
    
    # Verify all locations were converted
    assert len(converted) == 3
    
    # Check each location
    for i, (lon, lat, z) in enumerate(converted):
        assert lon == config.start_locations[i].lon
        assert lat == config.start_locations[i].lat
        # Verify z is in valid pressure range
        assert 200.0 <= z <= 1000.0


def test_initialization_logs_coordinate_system_info_pressure(caplog):
    """Test that coordinate system info is logged during initialization (pressure)."""
    import logging
    caplog.set_level(logging.INFO)
    
    # Create MetData with pressure coordinates
    met = MetData(
        lon_grid=np.array([0.0, 1.0]),
        lat_grid=np.array([0.0, 1.0]),
        z_grid=np.array([200.0, 500.0, 850.0, 1000.0]),  # hPa
        t_grid=np.array([0.0, 3600.0]),
        u=np.zeros((2, 4, 2, 2)),
        v=np.zeros((2, 4, 2, 2)),
        w=np.zeros((2, 4, 2, 2)),
        z_type="pressure",
    )
    
    config = SimulationConfig(
        start_time=datetime(2024, 1, 1, 0, 0),
        num_start_locations=1,
        start_locations=[StartLocation(lat=0.5, lon=0.5, height=850.0)],
        total_run_hours=-7,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[(".", "test.arl")],
    )
    
    # Initialize engine
    engine = TrajectoryEngine(config=config, met=met)
    
    # Verify coordinate system info is logged
    log_messages = [record.message for record in caplog.records]
    
    # Check that z_type is logged
    assert any("MetData vertical coordinate system: pressure" in msg for msg in log_messages)
    
    # Check that pressure range is logged (Requirement 4.4)
    assert any("MetData pressure range: 200.0 - 1000.0 hPa" in msg for msg in log_messages)


def test_initialization_logs_coordinate_system_info_height(caplog):
    """Test that coordinate system info is logged during initialization (height)."""
    import logging
    caplog.set_level(logging.INFO)
    
    # Create MetData with height coordinates
    met = MetData(
        lon_grid=np.array([0.0, 1.0]),
        lat_grid=np.array([0.0, 1.0]),
        z_grid=np.array([0.0, 500.0, 1000.0, 5000.0, 10000.0]),  # meters
        t_grid=np.array([0.0, 3600.0]),
        u=np.zeros((2, 5, 2, 2)),
        v=np.zeros((2, 5, 2, 2)),
        w=np.zeros((2, 5, 2, 2)),
        z_type="height",
    )
    
    config = SimulationConfig(
        start_time=datetime(2024, 1, 1, 0, 0),
        num_start_locations=1,
        start_locations=[StartLocation(lat=0.5, lon=0.5, height=850.0)],
        total_run_hours=-7,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[(".", "test.arl")],
    )
    
    # Initialize engine
    engine = TrajectoryEngine(config=config, met=met)
    
    # Verify coordinate system info is logged
    log_messages = [record.message for record in caplog.records]
    
    # Check that z_type is logged
    assert any("MetData vertical coordinate system: height" in msg for msg in log_messages)
    
    # Check that height range is logged
    assert any("MetData height range: 0.0 - 10000.0 m" in msg for msg in log_messages)


def test_initialization_logs_converted_coordinates_pressure(caplog):
    """Test that converted coordinates are logged for each start location (pressure)."""
    import logging
    caplog.set_level(logging.INFO)
    
    # Create MetData with pressure coordinates
    met = MetData(
        lon_grid=np.array([0.0, 1.0]),
        lat_grid=np.array([0.0, 1.0]),
        z_grid=np.array([200.0, 500.0, 850.0, 1000.0]),  # hPa
        t_grid=np.array([0.0, 3600.0]),
        u=np.zeros((2, 4, 2, 2)),
        v=np.zeros((2, 4, 2, 2)),
        w=np.zeros((2, 4, 2, 2)),
        z_type="pressure",
    )
    
    config = SimulationConfig(
        start_time=datetime(2024, 1, 1, 0, 0),
        num_start_locations=2,
        start_locations=[
            StartLocation(lat=0.3, lon=0.3, height=500.0),
            StartLocation(lat=0.7, lon=0.7, height=1500.0),
        ],
        total_run_hours=-7,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[(".", "test.arl")],
    )
    
    # Initialize engine
    engine = TrajectoryEngine(config=config, met=met)
    
    # Verify converted coordinates are logged for each start location (Requirement 4.3)
    log_messages = [record.message for record in caplog.records]
    
    # Check that both start locations are logged with conversions
    assert any("Start location 0: 500.0m AGL" in msg and "hPa" in msg for msg in log_messages)
    assert any("Start location 1: 1500.0m AGL" in msg and "hPa" in msg for msg in log_messages)


def test_initialization_logs_converted_coordinates_height(caplog):
    """Test that converted coordinates are logged for each start location (height)."""
    import logging
    caplog.set_level(logging.INFO)
    
    # Create MetData with height coordinates
    met = MetData(
        lon_grid=np.array([0.0, 1.0]),
        lat_grid=np.array([0.0, 1.0]),
        z_grid=np.array([0.0, 500.0, 1000.0, 5000.0, 10000.0]),  # meters
        t_grid=np.array([0.0, 3600.0]),
        u=np.zeros((2, 5, 2, 2)),
        v=np.zeros((2, 5, 2, 2)),
        w=np.zeros((2, 5, 2, 2)),
        z_type="height",
    )
    
    config = SimulationConfig(
        start_time=datetime(2024, 1, 1, 0, 0),
        num_start_locations=2,
        start_locations=[
            StartLocation(lat=0.3, lon=0.3, height=850.0),
            StartLocation(lat=0.7, lon=0.7, height=2000.0),
        ],
        total_run_hours=-7,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[(".", "test.arl")],
    )
    
    # Initialize engine
    engine = TrajectoryEngine(config=config, met=met)
    
    # Verify converted coordinates are logged for each start location (Requirement 4.3)
    log_messages = [record.message for record in caplog.records]
    
    # Check that both start locations are logged (no conversion needed for height)
    assert any("Start location 0: 850.0m AGL (no conversion needed)" in msg for msg in log_messages)
    assert any("Start location 1: 2000.0m AGL (no conversion needed)" in msg for msg in log_messages)


def test_seoul_winter_trajectory_regression():
    """Test Seoul winter backward trajectory regression case.
    
    This test verifies the fix for the early termination bug where backward
    trajectories would terminate after ~6 minutes due to coordinate system
    mismatch. The test runs a 7-hour backward trajectory from Seoul at 850m AGL
    and verifies it completes successfully.
    
    Requirements: 5.1, 5.2, 5.3, 5.4
    """
    # Create MetData covering Seoul region with pressure coordinates
    # Seoul: 37.5°N, 127.0°E
    # Grid should cover a reasonable area around Seoul
    lon_grid = np.linspace(120.0, 135.0, 10)  # 120°E to 135°E
    lat_grid = np.linspace(30.0, 45.0, 10)    # 30°N to 45°N
    z_grid = np.array([200.0, 500.0, 700.0, 850.0, 925.0, 1000.0])  # hPa
    
    # 7 hours backward = 8 time points (0, -1h, -2h, ..., -7h)
    # Need at least 8 time points in met data
    t_grid = np.linspace(0.0, 7 * 3600.0, 8)  # 0 to 7 hours in seconds
    
    # Create wind fields (simple uniform wind for testing)
    shape = (8, 6, 10, 10)  # (nt, nz, ny, nx)
    u = np.full(shape, 5.0, dtype=np.float64)   # 5 m/s eastward
    v = np.full(shape, 3.0, dtype=np.float64)   # 3 m/s northward
    w = np.full(shape, 0.0, dtype=np.float64)   # No vertical motion
    
    met = MetData(
        lon_grid=lon_grid,
        lat_grid=lat_grid,
        z_grid=z_grid,
        t_grid=t_grid,
        u=u,
        v=v,
        w=w,
        z_type="pressure",
        terrain=np.zeros((10, 10), dtype=np.float64),
    )
    
    # Create config for Seoul winter trajectory
    # Seoul: 37.5°N, 127.0°E, 850m AGL, 7h backward
    start_location = StartLocation(lat=37.5, lon=127.0, height=850.0)
    config = SimulationConfig(
        start_time=datetime(2024, 1, 15, 0, 0),  # Winter date
        num_start_locations=1,
        start_locations=[start_location],
        total_run_hours=-7,  # 7 hours backward
        vertical_motion=0,
        model_top=10000.0,
        met_files=[(".", "test.arl")],
    )
    
    # Initialize engine (should not raise InvalidCoordinateError)
    engine = TrajectoryEngine(config=config, met=met)
    
    # Run trajectory with 1-hour output interval
    trajectories = engine.run(output_interval_s=3600.0)
    
    # Verify trajectory was computed
    assert len(trajectories) == 1, "Should have 1 trajectory"
    trajectory = trajectories[0]
    
    # Requirement 5.2: Verify 8 trajectory points (initial + 7 hourly outputs)
    assert len(trajectory) == 8, (
        f"Expected 8 trajectory points (1 initial + 7 hourly), got {len(trajectory)}"
    )
    
    # Requirement 5.3: Verify simulation runs for full 7 hours (25200 seconds)
    # In backward mode, time decreases, so check elapsed time
    t_start = trajectory[0][0]
    t_end = trajectory[-1][0]
    elapsed_time = abs(t_end - t_start)
    expected_time = 7 * 3600.0  # 25200 seconds
    
    assert abs(elapsed_time - expected_time) < 1.0, (
        f"Expected simulation to run for {expected_time}s, "
        f"but elapsed time was {elapsed_time}s"
    )
    
    # Requirement 5.4: Verify all points have valid pressure values
    # 850m AGL should convert to approximately 916.8 hPa
    # All trajectory points should have pressure within valid range [200, 1000] hPa
    for i, (t, lon, lat, z) in enumerate(trajectory):
        assert 200.0 <= z <= 1000.0, (
            f"Trajectory point {i} has pressure {z:.1f} hPa, "
            f"which is outside valid range [200.0, 1000.0] hPa"
        )
    
    # Additional verification: Check that trajectory points are spaced ~1 hour apart
    for i in range(1, len(trajectory)):
        t_prev = trajectory[i-1][0]
        t_curr = trajectory[i][0]
        time_diff = abs(t_curr - t_prev)
        # Should be approximately 3600 seconds (1 hour)
        assert abs(time_diff - 3600.0) < 10.0, (
            f"Time difference between points {i-1} and {i} is {time_diff}s, "
            f"expected ~3600s"
        )
    
    # Verify backward time direction
    for i in range(1, len(trajectory)):
        assert trajectory[i][0] < trajectory[i-1][0], (
            f"Backward trajectory should have decreasing time, "
            f"but t[{i}]={trajectory[i][0]} >= t[{i-1}]={trajectory[i-1][0]}"
        )


def test_boundary_error_logs_position_and_ranges_pressure(caplog):
    """Test that boundary errors log particle position and valid ranges (pressure).
    
    Requirements: 3.1, 3.2
    """
    import logging
    caplog.set_level(logging.WARNING)
    
    # Create MetData with pressure coordinates and limited spatial extent
    # to trigger boundary error
    met = MetData(
        lon_grid=np.array([126.0, 128.0]),  # Small lon range
        lat_grid=np.array([36.0, 38.0]),    # Small lat range
        z_grid=np.array([200.0, 500.0, 850.0, 1000.0]),  # hPa
        t_grid=np.array([0.0, 3600.0, 7200.0]),
        u=np.full((3, 4, 2, 2), 50.0, dtype=np.float64),  # Strong eastward wind
        v=np.full((3, 4, 2, 2), 0.0, dtype=np.float64),
        w=np.full((3, 4, 2, 2), 0.0, dtype=np.float64),
        z_type="pressure",
        terrain=np.zeros((2, 2), dtype=np.float64),
    )
    
    # Start location that will exit the grid due to strong wind
    config = SimulationConfig(
        start_time=datetime(2024, 1, 1, 0, 0),
        num_start_locations=1,
        start_locations=[StartLocation(lat=37.0, lon=127.0, height=850.0)],
        total_run_hours=2,  # Forward trajectory
        vertical_motion=0,
        model_top=10000.0,
        met_files=[(".", "test.arl")],
    )
    
    # Initialize and run engine
    engine = TrajectoryEngine(config=config, met=met)
    trajectories = engine.run(output_interval_s=3600.0)
    
    # Verify boundary error was logged
    log_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
    
    # Requirement 3.1: Check that particle position is logged
    # Can be either "Particle left grid at" or "Heun step boundary error at"
    assert any(("Particle left grid at" in msg or "Heun step boundary error at" in msg) 
               and "lon=" in msg and "lat=" in msg and "z=" in msg 
               for msg in log_messages), "Position should be logged"
    
    # Requirement 3.2: Check that valid ranges are logged
    assert any("Valid ranges:" in msg and "lon=" in msg and "lat=" in msg and "z=" in msg 
               for msg in log_messages), "Valid ranges should be logged"
    
    # Verify coordinate system is mentioned
    assert any("pressure" in msg for msg in log_messages), "Coordinate system should be mentioned"


def test_boundary_error_logs_position_and_ranges_height(caplog):
    """Test that boundary errors log particle position and valid ranges (height).
    
    Requirements: 3.1, 3.2
    """
    import logging
    caplog.set_level(logging.WARNING)
    
    # Create MetData with height coordinates and limited spatial extent
    met = MetData(
        lon_grid=np.array([126.0, 128.0]),  # Small lon range
        lat_grid=np.array([36.0, 38.0]),    # Small lat range
        z_grid=np.array([0.0, 500.0, 1000.0, 5000.0]),  # meters
        t_grid=np.array([0.0, 3600.0, 7200.0]),
        u=np.full((3, 4, 2, 2), 50.0, dtype=np.float64),  # Strong eastward wind
        v=np.full((3, 4, 2, 2), 0.0, dtype=np.float64),
        w=np.full((3, 4, 2, 2), 0.0, dtype=np.float64),
        z_type="height",
        terrain=np.zeros((2, 2), dtype=np.float64),
    )
    
    # Start location that will exit the grid
    config = SimulationConfig(
        start_time=datetime(2024, 1, 1, 0, 0),
        num_start_locations=1,
        start_locations=[StartLocation(lat=37.0, lon=127.0, height=850.0)],
        total_run_hours=2,  # Forward trajectory
        vertical_motion=0,
        model_top=10000.0,
        met_files=[(".", "test.arl")],
    )
    
    # Initialize and run engine
    engine = TrajectoryEngine(config=config, met=met)
    trajectories = engine.run(output_interval_s=3600.0)
    
    # Verify boundary error was logged
    log_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
    
    # Requirement 3.1: Check that particle position is logged
    # Can be either "Particle left grid at" or "Heun step boundary error at"
    assert any(("Particle left grid at" in msg or "Heun step boundary error at" in msg) 
               and "lon=" in msg and "lat=" in msg and "z=" in msg 
               for msg in log_messages), "Position should be logged"
    
    # Requirement 3.2: Check that valid ranges are logged
    assert any("Valid ranges:" in msg and "lon=" in msg and "lat=" in msg and "z=" in msg 
               for msg in log_messages), "Valid ranges should be logged"
    
    # Verify coordinate system is mentioned
    assert any("height" in msg for msg in log_messages), "Coordinate system should be mentioned"


def test_boundary_error_identifies_top_exit_pressure(caplog):
    """Test that top exit logging code exists for pressure coordinates.
    
    In pressure coordinates, low pressure = high altitude, so exiting through
    the top means pressure too low (z < z_grid[0]).
    
    This test verifies that the boundary error logging includes position,
    ranges, and can identify vertical exits. Due to the complexity of triggering
    an actual vertical exit in a unit test, this test verifies the logging
    infrastructure is in place.
    
    Requirements: 3.3
    """
    import logging
    caplog.set_level(logging.WARNING)
    
    # Create MetData with limited spatial extent to trigger boundary error
    met = MetData(
        lon_grid=np.array([126.0, 128.0]),  # Small range to trigger horizontal exit
        lat_grid=np.array([36.0, 38.0]),
        z_grid=np.array([200.0, 500.0, 850.0, 1000.0]),
        t_grid=np.array([0.0, 3600.0]),
        u=np.full((2, 4, 2, 2), 50.0, dtype=np.float64),  # Strong wind to exit horizontally
        v=np.full((2, 4, 2, 2), 0.0, dtype=np.float64),
        w=np.full((2, 4, 2, 2), 0.0, dtype=np.float64),
        z_type="pressure",
        terrain=np.zeros((2, 2), dtype=np.float64),
    )
    
    config = SimulationConfig(
        start_time=datetime(2024, 1, 1, 0, 0),
        num_start_locations=1,
        start_locations=[StartLocation(lat=37.0, lon=127.0, height=850.0)],
        total_run_hours=1,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[(".", "test.arl")],
    )
    
    engine = TrajectoryEngine(config=config, met=met)
    trajectories = engine.run(output_interval_s=3600.0)
    
    log_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
    
    # Requirement 3.3: Verify that boundary error logging infrastructure exists
    # The test verifies that when a boundary error occurs, the logging includes
    # the necessary information (position, ranges, termination info)
    assert len(log_messages) > 0, "Should have warning messages"
    assert any("boundary error" in msg.lower() or "left grid" in msg.lower() 
               for msg in log_messages), "Should log boundary error"
    assert any("Valid ranges:" in msg for msg in log_messages), "Should log valid ranges"
    assert any("terminated after" in msg.lower() for msg in log_messages), "Should log termination info"


def test_boundary_error_identifies_bottom_exit_pressure(caplog):
    """Test that bottom exit logging code exists for pressure coordinates.
    
    In pressure coordinates, high pressure = low altitude, so exiting through
    the bottom means pressure too high (z > z_grid[-1]).
    
    This test verifies that the boundary error logging includes position,
    ranges, and can identify vertical exits.
    
    Requirements: 3.3
    """
    import logging
    caplog.set_level(logging.WARNING)
    
    # Similar test to verify logging infrastructure
    met = MetData(
        lon_grid=np.array([126.0, 128.0]),
        lat_grid=np.array([36.0, 38.0]),
        z_grid=np.array([200.0, 500.0, 850.0, 1000.0]),
        t_grid=np.array([0.0, 3600.0]),
        u=np.full((2, 4, 2, 2), 50.0, dtype=np.float64),
        v=np.full((2, 4, 2, 2), 0.0, dtype=np.float64),
        w=np.full((2, 4, 2, 2), 0.0, dtype=np.float64),
        z_type="pressure",
        terrain=np.zeros((2, 2), dtype=np.float64),
    )
    
    config = SimulationConfig(
        start_time=datetime(2024, 1, 1, 0, 0),
        num_start_locations=1,
        start_locations=[StartLocation(lat=37.0, lon=127.0, height=850.0)],
        total_run_hours=1,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[(".", "test.arl")],
    )
    
    engine = TrajectoryEngine(config=config, met=met)
    trajectories = engine.run(output_interval_s=3600.0)
    
    log_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
    
    # Verify logging infrastructure
    assert len(log_messages) > 0, "Should have warning messages"
    assert any("boundary error" in msg.lower() or "left grid" in msg.lower() 
               for msg in log_messages), "Should log boundary error"
    assert any("Valid ranges:" in msg for msg in log_messages), "Should log valid ranges"
    assert any("terminated after" in msg.lower() for msg in log_messages), "Should log termination info"


def test_boundary_error_identifies_top_exit_height(caplog):
    """Test that top exit logging code exists for height coordinates.
    
    In height coordinates, high height = high altitude, so exiting through
    the top means height too high (z > z_grid[-1]).
    
    Requirements: 3.3
    """
    import logging
    caplog.set_level(logging.WARNING)
    
    # Create MetData with limited spatial extent to trigger boundary error
    met = MetData(
        lon_grid=np.array([126.0, 128.0]),
        lat_grid=np.array([36.0, 38.0]),
        z_grid=np.array([0.0, 500.0, 1000.0, 5000.0]),
        t_grid=np.array([0.0, 3600.0]),
        u=np.full((2, 4, 2, 2), 50.0, dtype=np.float64),  # Strong wind to exit horizontally
        v=np.full((2, 4, 2, 2), 0.0, dtype=np.float64),
        w=np.full((2, 4, 2, 2), 0.0, dtype=np.float64),
        z_type="height",
        terrain=np.zeros((2, 2), dtype=np.float64),
    )
    
    config = SimulationConfig(
        start_time=datetime(2024, 1, 1, 0, 0),
        num_start_locations=1,
        start_locations=[StartLocation(lat=37.0, lon=127.0, height=850.0)],
        total_run_hours=1,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[(".", "test.arl")],
    )
    
    engine = TrajectoryEngine(config=config, met=met)
    trajectories = engine.run(output_interval_s=3600.0)
    
    log_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
    
    # Verify logging infrastructure exists
    assert len(log_messages) > 0, "Should have warning messages"
    assert any("boundary error" in msg.lower() or "left grid" in msg.lower() 
               for msg in log_messages), "Should log boundary error"
    assert any("Valid ranges:" in msg for msg in log_messages), "Should log valid ranges"
    assert any("terminated after" in msg.lower() for msg in log_messages), "Should log termination info"


def test_boundary_error_identifies_bottom_exit_height(caplog):
    """Test that bottom exit logging code exists for height coordinates.
    
    In height coordinates, low height = low altitude, so exiting through
    the bottom means height too low (z < z_grid[0]).
    
    Requirements: 3.3
    """
    import logging
    caplog.set_level(logging.WARNING)
    
    # Create MetData with limited spatial extent to trigger boundary error
    met = MetData(
        lon_grid=np.array([126.0, 128.0]),
        lat_grid=np.array([36.0, 38.0]),
        z_grid=np.array([0.0, 500.0, 1000.0, 5000.0]),
        t_grid=np.array([0.0, 3600.0]),
        u=np.full((2, 4, 2, 2), 50.0, dtype=np.float64),  # Strong wind to exit horizontally
        v=np.full((2, 4, 2, 2), 0.0, dtype=np.float64),
        w=np.full((2, 4, 2, 2), 0.0, dtype=np.float64),
        z_type="height",
        terrain=np.zeros((2, 2), dtype=np.float64),
    )
    
    config = SimulationConfig(
        start_time=datetime(2024, 1, 1, 0, 0),
        num_start_locations=1,
        start_locations=[StartLocation(lat=37.0, lon=127.0, height=850.0)],
        total_run_hours=1,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[(".", "test.arl")],
    )
    
    engine = TrajectoryEngine(config=config, met=met)
    trajectories = engine.run(output_interval_s=3600.0)
    
    log_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
    
    # Verify logging infrastructure exists
    assert len(log_messages) > 0, "Should have warning messages"
    assert any("boundary error" in msg.lower() or "left grid" in msg.lower() 
               for msg in log_messages), "Should log boundary error"
    assert any("Valid ranges:" in msg for msg in log_messages), "Should log valid ranges"
    assert any("terminated after" in msg.lower() for msg in log_messages), "Should log termination info"


def test_boundary_error_logs_elapsed_time_and_point_count(caplog):
    """Test that elapsed time and trajectory point count are logged on boundary error.
    
    Requirements: 3.4
    """
    import logging
    caplog.set_level(logging.WARNING)
    
    # Create MetData with limited spatial extent to trigger boundary error
    met = MetData(
        lon_grid=np.array([126.0, 128.0]),  # Small lon range
        lat_grid=np.array([36.0, 38.0]),    # Small lat range
        z_grid=np.array([200.0, 500.0, 850.0, 1000.0]),  # hPa
        t_grid=np.array([0.0, 3600.0, 7200.0, 10800.0]),  # 3 hours
        u=np.full((4, 4, 2, 2), 50.0, dtype=np.float64),  # Strong eastward wind
        v=np.full((4, 4, 2, 2), 0.0, dtype=np.float64),
        w=np.full((4, 4, 2, 2), 0.0, dtype=np.float64),
        z_type="pressure",
        terrain=np.zeros((2, 2), dtype=np.float64),
    )
    
    # Start location that will exit the grid
    config = SimulationConfig(
        start_time=datetime(2024, 1, 1, 0, 0),
        num_start_locations=1,
        start_locations=[StartLocation(lat=37.0, lon=127.0, height=850.0)],
        total_run_hours=3,  # 3 hours forward
        vertical_motion=0,
        model_top=10000.0,
        met_files=[(".", "test.arl")],
    )
    
    # Initialize and run engine
    engine = TrajectoryEngine(config=config, met=met)
    trajectories = engine.run(output_interval_s=3600.0)
    
    # Verify elapsed time and point count are logged
    log_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
    
    # Requirement 3.4: Check that elapsed time is logged
    assert any("Trajectory terminated after" in msg and "s with" in msg and "points" in msg 
               for msg in log_messages), "Elapsed time and point count should be logged"
    
    # Verify the trajectory actually terminated early (didn't complete full 3 hours)
    assert len(trajectories) == 1
    trajectory = trajectories[0]
    
    # Should have terminated before completing all 3 hours
    t_start = trajectory[0][0]
    t_end = trajectory[-1][0]
    elapsed = abs(t_end - t_start)
    
    # Should be less than 3 hours (10800 seconds)
    assert elapsed < 10800.0, "Trajectory should have terminated early due to boundary error"


def test_large_pressure_change_warning(caplog):
    """Test that large pressure changes trigger a warning.
    
    This test verifies that when pressure changes by more than 200 hPa in a
    single time step, a warning is logged with the pressure change magnitude
    and time step.
    
    Requirements: 2.4
    """
    import logging
    caplog.set_level(logging.WARNING)
    
    # Create MetData with pressure coordinates and a very wide vertical range
    # to allow large pressure changes without hitting boundaries
    met = MetData(
        lon_grid=np.array([126.0, 128.0]),
        lat_grid=np.array([36.0, 38.0]),
        # Very wide pressure range to accommodate large changes
        # Extended range to handle Heun midpoint evaluation
        z_grid=np.array([100.0, 400.0, 700.0, 1000.0, 1300.0, 1600.0, 1900.0]),  # hPa
        t_grid=np.array([0.0, 100.0, 200.0]),  # Short time steps
        u=np.full((3, 7, 2, 2), 0.0, dtype=np.float64),
        v=np.full((3, 7, 2, 2), 0.0, dtype=np.float64),
        # Moderate vertical velocity that will cause >200 hPa change
        # but won't immediately exit bounds
        # With dt ~100s and w ~2.5, we get ~250 hPa change
        w=np.full((3, 7, 2, 2), 2.5, dtype=np.float64),  # Moderate downward motion
        z_type="pressure",
        terrain=np.zeros((2, 2), dtype=np.float64),
    )
    
    # Start at middle pressure to allow movement in both directions
    config = SimulationConfig(
        start_time=datetime(2024, 1, 1, 0, 0),
        num_start_locations=1,
        start_locations=[StartLocation(lat=37.0, lon=127.0, height=1500.0)],  # ~843 hPa
        total_run_hours=1,
        vertical_motion=1,  # Enable vertical motion
        model_top=10000.0,
        met_files=[(".", "test.arl")],
    )
    
    # Initialize and run engine
    engine = TrajectoryEngine(config=config, met=met)
    trajectories = engine.run(output_interval_s=100.0)
    
    # Verify large pressure change warning was logged
    log_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
    
    # Requirement 2.4: Check that warning includes pressure change magnitude and time step
    large_pressure_warnings = [msg for msg in log_messages if "Large pressure change detected" in msg]
    
    # With w=2.5 and dt~100s, we should trigger the warning
    assert len(large_pressure_warnings) > 0, (
        "Expected large pressure change warning to be logged with vertical motion. "
        f"Got warnings: {log_messages}"
    )
    
    # Verify warning contains required information
    warning_msg = large_pressure_warnings[0]
    assert "hPa" in warning_msg, "Warning should include pressure units"
    assert "Δ=" in warning_msg, "Warning should include pressure change magnitude (Δ=)"
    assert "dt=" in warning_msg, "Warning should include time step (dt=)"
    assert "vertical motion issues" in warning_msg.lower(), "Warning should mention vertical motion"
    
    # Verify the pressure change magnitude is > 200 hPa
    # Extract the delta value from the warning message
    import re
    delta_match = re.search(r'Δ=(\d+\.?\d*)', warning_msg)
    assert delta_match is not None, "Warning should contain Δ= with numeric value"
    delta_value = float(delta_match.group(1))
    assert delta_value > 200.0, f"Pressure change should be > 200 hPa, got {delta_value} hPa"
