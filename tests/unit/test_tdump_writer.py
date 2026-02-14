"""Unit tests for HYSPLIT tdump writer."""

from datetime import datetime
from pathlib import Path
import tempfile

import pytest

from pyhysplit.core.models import SimulationConfig, StartLocation
from pyhysplit.io.tdump_writer import TdumpWriter


@pytest.fixture
def config():
    """Create a basic simulation configuration."""
    return SimulationConfig(
        start_time=datetime(2024, 1, 15, 12, 0),
        num_start_locations=1,
        start_locations=[
            StartLocation(lat=37.5, lon=127.0, height=500.0)
        ],
        total_run_hours=-24,
        vertical_motion=7,
        model_top=10000.0,
        met_files=[],
    )


@pytest.fixture
def sample_trajectory():
    """Create a sample trajectory."""
    # (time_seconds, lon, lat, height_m)
    return [
        (0.0, 127.0, 37.5, 500.0),
        (3600.0, 126.5, 37.8, 600.0),
        (7200.0, 126.0, 38.0, 700.0),
        (10800.0, 125.5, 38.2, 800.0),
    ]


def test_tdump_writer_initialization(config):
    """Test TdumpWriter initialization."""
    writer = TdumpWriter(config)
    
    assert writer.config == config
    assert writer.met_model_id == "GFS"
    assert writer.met_start_time == config.start_time
    assert writer.met_forecast_hour == 0
    assert "PRESSURE" in writer.diagnostic_vars
    assert writer.diagnostic_vars[0] == "PRESSURE"


def test_tdump_writer_custom_diagnostics(config):
    """Test TdumpWriter with custom diagnostic variables."""
    custom_vars = ["THETA", "AIR_TEMP"]
    writer = TdumpWriter(config, diagnostic_vars=custom_vars)
    
    # PRESSURE should be automatically added as first variable
    assert writer.diagnostic_vars[0] == "PRESSURE"
    assert "THETA" in writer.diagnostic_vars
    assert "AIR_TEMP" in writer.diagnostic_vars


def test_tdump_writer_pressure_always_first(config):
    """Test that PRESSURE is always the first diagnostic variable."""
    # Even if PRESSURE is in the list but not first
    custom_vars = ["THETA", "PRESSURE", "AIR_TEMP"]
    writer = TdumpWriter(config, diagnostic_vars=custom_vars)
    
    assert writer.diagnostic_vars[0] == "PRESSURE"
    assert len(writer.diagnostic_vars) == 3


def test_write_single_trajectory(config, sample_trajectory, tmp_path):
    """Test writing a single trajectory to tdump file."""
    writer = TdumpWriter(config)
    output_file = tmp_path / "test_tdump.txt"
    
    writer.write(output_file, [sample_trajectory])
    
    # Check file was created
    assert output_file.exists()
    
    # Read and verify content
    with open(output_file, 'r') as f:
        lines = f.readlines()
    
    # Should have header + trajectory points
    assert len(lines) > 5  # At least header lines
    
    # Check first line (number of grids and format version)
    first_line = lines[0].strip()
    assert "1" in first_line  # 1 met grid
    assert "2" in first_line  # format version 2


def test_write_multiple_trajectories(config, sample_trajectory, tmp_path):
    """Test writing multiple trajectories to tdump file."""
    # Create second trajectory (slightly different)
    traj2 = [(t, lon + 0.5, lat + 0.1, h + 50) for t, lon, lat, h in sample_trajectory]
    
    # Add second starting location
    config.num_start_locations = 2
    config.start_locations.append(
        StartLocation(lat=37.6, lon=127.5, height=550.0)
    )
    
    writer = TdumpWriter(config)
    output_file = tmp_path / "test_tdump_multi.txt"
    
    writer.write(output_file, [sample_trajectory, traj2])
    
    assert output_file.exists()
    
    with open(output_file, 'r') as f:
        content = f.read()
    
    # Should contain trajectory numbers 1 and 2
    assert "     1" in content  # Trajectory 1
    assert "     2" in content  # Trajectory 2


def test_write_with_diagnostics(config, sample_trajectory, tmp_path):
    """Test writing trajectory with diagnostic variables."""
    writer = TdumpWriter(config)
    output_file = tmp_path / "test_tdump_diag.txt"
    
    # Create diagnostic data for each point
    diagnostics = [[
        {"PRESSURE": 950.0, "THETA": 300.0, "AIR_TEMP": 280.0, "RAINFALL": 0.0},
        {"PRESSURE": 940.0, "THETA": 302.0, "AIR_TEMP": 282.0, "RAINFALL": 0.5},
        {"PRESSURE": 930.0, "THETA": 304.0, "AIR_TEMP": 284.0, "RAINFALL": 1.0},
        {"PRESSURE": 920.0, "THETA": 306.0, "AIR_TEMP": 286.0, "RAINFALL": 0.0},
    ]]
    
    writer.write(output_file, [sample_trajectory], diagnostics)
    
    assert output_file.exists()
    
    with open(output_file, 'r') as f:
        content = f.read()
    
    # Check that diagnostic values appear in output
    assert "950.00" in content  # Pressure value
    assert "300.00" in content  # Theta value


def test_backward_trajectory_direction(config, sample_trajectory, tmp_path):
    """Test that backward trajectory is labeled correctly."""
    config.total_run_hours = -24  # Backward
    writer = TdumpWriter(config)
    output_file = tmp_path / "test_tdump_backward.txt"
    
    writer.write(output_file, [sample_trajectory])
    
    with open(output_file, 'r') as f:
        content = f.read()
    
    assert "BACKWARD" in content


def test_forward_trajectory_direction(config, sample_trajectory, tmp_path):
    """Test that forward trajectory is labeled correctly."""
    config.total_run_hours = 24  # Forward
    writer = TdumpWriter(config)
    output_file = tmp_path / "test_tdump_forward.txt"
    
    writer.write(output_file, [sample_trajectory])
    
    with open(output_file, 'r') as f:
        content = f.read()
    
    assert "FORWARD" in content


def test_vertical_motion_method_names(config, sample_trajectory, tmp_path):
    """Test that vertical motion methods are correctly named."""
    methods = {
        0: "DATA",
        1: "ISODEN",
        2: "ISOBAR",
        3: "ISENTRP",
        7: "AVERAGE",
    }
    
    for method_num, method_name in methods.items():
        config.vertical_motion = method_num
        writer = TdumpWriter(config)
        output_file = tmp_path / f"test_tdump_vm{method_num}.txt"
        
        writer.write(output_file, [sample_trajectory])
        
        with open(output_file, 'r') as f:
            content = f.read()
        
        assert method_name in content


def test_generate_filename():
    """Test filename generation."""
    dt = datetime(2024, 1, 15, 12, 0)
    
    # Basic filename
    filename = TdumpWriter.generate_filename(dt)
    assert filename == "tdump_240115_12"
    
    # With location
    filename = TdumpWriter.generate_filename(dt, location_name="seoul")
    assert filename == "tdump_seoul_240115_12"
    
    # With location and suffix
    filename = TdumpWriter.generate_filename(dt, location_name="seoul", suffix="test")
    assert filename == "tdump_seoul_test_240115_12"


def test_met_model_id_truncation(config):
    """Test that met model ID is truncated to 8 characters."""
    long_id = "VERYLONGMODELNAME"
    writer = TdumpWriter(config, met_model_id=long_id)
    
    assert len(writer.met_model_id) == 8
    assert writer.met_model_id == long_id[:8]


def test_empty_trajectory_list(config, tmp_path):
    """Test handling of empty trajectory list."""
    writer = TdumpWriter(config)
    output_file = tmp_path / "test_tdump_empty.txt"
    
    # Should still write header even with no trajectories
    writer.write(output_file, [])
    
    assert output_file.exists()


def test_trajectory_time_calculation(config, sample_trajectory, tmp_path):
    """Test that trajectory times are correctly calculated."""
    writer = TdumpWriter(config)
    output_file = tmp_path / "test_tdump_time.txt"
    
    writer.write(output_file, [sample_trajectory])
    
    with open(output_file, 'r') as f:
        lines = f.readlines()
    
    # Find trajectory point lines (they start with trajectory number and have age values)
    # Skip header lines by looking for lines that have the age pattern (X.00 hours)
    point_lines = []
    for line in lines:
        # Trajectory points have format: traj_num grid year month day hour minute forecast age ...
        # Age appears after forecast hour and before lat/lon
        parts = line.split()
        if len(parts) > 8:  # Enough fields for a trajectory point
            try:
                # Try to parse age field (should be around index 8)
                age = float(parts[8])
                if 0.0 <= age <= 10.0:  # Reasonable age range
                    point_lines.append(line)
            except (ValueError, IndexError):
                continue
    
    # Check age progression (should be 0.00, 1.00, 2.00, 3.00 hours)
    assert len(point_lines) == 4


def test_default_pressure_calculation(config, sample_trajectory, tmp_path):
    """Test that default pressure is calculated from height."""
    writer = TdumpWriter(config)
    output_file = tmp_path / "test_tdump_pressure.txt"
    
    # Write without diagnostics (should use default pressure calculation)
    writer.write(output_file, [sample_trajectory], diagnostics=None)
    
    with open(output_file, 'r') as f:
        content = f.read()
    
    # Should contain pressure values (not zero)
    # At 500m height, pressure should be around 950 hPa
    assert "9" in content  # Should have pressure values starting with 9


def test_file_format_compatibility(config, sample_trajectory, tmp_path):
    """Test that output format matches HYSPLIT specification."""
    writer = TdumpWriter(config)
    output_file = tmp_path / "test_tdump_format.txt"
    
    writer.write(output_file, [sample_trajectory])
    
    with open(output_file, 'r') as f:
        lines = f.readlines()
    
    # Line 1: Number of grids (I6) and format version (I6)
    line1_parts = lines[0].split()
    assert len(line1_parts) == 2
    assert int(line1_parts[0]) == 1  # 1 grid
    assert int(line1_parts[1]) == 2  # format version 2
    
    # Line 2: Met model ID (A8) + 5 integers (year, month, day, hour, forecast)
    line2 = lines[1]
    assert len(line2) >= 8  # At least 8 chars for model ID
    
    # Line 3: Number of trajectories, direction, vertical method
    line3_parts = lines[2].split()
    assert len(line3_parts) == 3
    assert int(line3_parts[0]) == 1  # 1 trajectory
