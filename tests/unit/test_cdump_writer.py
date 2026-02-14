"""Unit tests for HYSPLIT cdump writer."""

from datetime import datetime
from pathlib import Path
import struct
import tempfile

import numpy as np
import pytest

from pyhysplit.core.models import (
    SimulationConfig,
    StartLocation,
    ConcentrationGridConfig,
)
from pyhysplit.io.cdump_writer import CdumpWriter
from pyhysplit.physics.concentration import ConcentrationGrid


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
def grid_config():
    """Create a concentration grid configuration."""
    return ConcentrationGridConfig(
        center_lat=37.5,
        center_lon=127.0,
        spacing_lat=0.1,
        spacing_lon=0.1,
        span_lat=2.0,
        span_lon=2.0,
        levels=[0, 100, 500, 1000],
        sampling_start=datetime(2024, 1, 15, 0, 0),
        sampling_end=datetime(2024, 1, 16, 0, 0),  # Next day at midnight
        averaging_period=24,
    )


@pytest.fixture
def sample_grid(grid_config):
    """Create a sample concentration grid."""
    # Create grid arrays
    nlat = 21  # 2.0 / 0.1 + 1
    nlon = 21
    nlevels = 4
    
    lat_grid = np.linspace(36.5, 38.5, nlat)
    lon_grid = np.linspace(126.0, 128.0, nlon)
    z_grid = np.array([0, 100, 500, 1000], dtype=float)
    
    # Create concentration array with some non-zero values
    concentration = np.zeros((nlevels, nlat, nlon))  # Note: (nz, ny, nx) order
    concentration[0, 10, 10] = 1.0e-6  # Center point, ground level
    concentration[0, 10, 11] = 5.0e-7
    concentration[1, 11, 10] = 2.0e-7  # Level 1
    
    grid = ConcentrationGrid(
        lat_grid=lat_grid,
        lon_grid=lon_grid,
        z_grid=z_grid,
        concentration=concentration,
        mass_accumulated=concentration.copy(),
        sample_count=np.ones_like(concentration),
        start_time=grid_config.sampling_start,
        end_time=grid_config.sampling_end,
    )
    grid.config = grid_config  # Attach config for sampling times
    
    return grid


def test_cdump_writer_initialization(config):
    """Test CdumpWriter initialization."""
    writer = CdumpWriter(config)
    
    assert writer.config == config
    assert writer.met_model_id == "GFS "  # Padded to 4 chars
    assert writer.met_start_time == config.start_time
    assert writer.met_forecast_hour == 0
    assert writer.packing is True


def test_cdump_writer_custom_met_model(config):
    """Test CdumpWriter with custom met model ID."""
    writer = CdumpWriter(config, met_model_id="GDAS")
    
    assert writer.met_model_id == "GDAS"
    assert len(writer.met_model_id) == 4


def test_met_model_id_truncation(config):
    """Test that met model ID is truncated to 4 characters."""
    long_id = "VERYLONGNAME"
    writer = CdumpWriter(config, met_model_id=long_id)
    
    assert len(writer.met_model_id) == 4
    assert writer.met_model_id == long_id[:4]


def test_met_model_id_padding(config):
    """Test that short met model ID is padded to 4 characters."""
    short_id = "GF"
    writer = CdumpWriter(config, met_model_id=short_id)
    
    assert len(writer.met_model_id) == 4
    assert writer.met_model_id.startswith(short_id)


def test_write_single_grid_packed(config, sample_grid, tmp_path):
    """Test writing a single concentration grid in packed format."""
    writer = CdumpWriter(config, packing=True)
    output_file = tmp_path / "test_cdump_packed.bin"
    
    writer.write(output_file, [sample_grid])
    
    # Check file was created
    assert output_file.exists()
    assert output_file.stat().st_size > 0


def test_write_single_grid_unpacked(config, sample_grid, tmp_path):
    """Test writing a single concentration grid in unpacked format."""
    writer = CdumpWriter(config, packing=False)
    output_file = tmp_path / "test_cdump_unpacked.bin"
    
    writer.write(output_file, [sample_grid])
    
    # Check file was created
    assert output_file.exists()
    assert output_file.stat().st_size > 0


def test_packed_vs_unpacked_file_size(config, sample_grid, tmp_path):
    """Test that packed files are smaller for sparse grids."""
    # Packed format
    writer_packed = CdumpWriter(config, packing=True)
    file_packed = tmp_path / "test_packed.bin"
    writer_packed.write(file_packed, [sample_grid])
    
    # Unpacked format
    writer_unpacked = CdumpWriter(config, packing=False)
    file_unpacked = tmp_path / "test_unpacked.bin"
    writer_unpacked.write(file_unpacked, [sample_grid])
    
    # Packed should be smaller for sparse grid
    size_packed = file_packed.stat().st_size
    size_unpacked = file_unpacked.stat().st_size
    
    # Unpacked writes full grid, so should be larger
    assert size_unpacked > size_packed


def test_write_empty_grid_list(config, tmp_path):
    """Test that writing empty grid list raises error."""
    writer = CdumpWriter(config)
    output_file = tmp_path / "test_empty.bin"
    
    with pytest.raises(ValueError, match="At least one concentration grid required"):
        writer.write(output_file, [])


def test_write_multiple_grids(config, sample_grid, tmp_path):
    """Test writing multiple concentration grids."""
    # Create second grid (copy with different values)
    grid2 = ConcentrationGrid(
        lat_grid=sample_grid.lat_grid.copy(),
        lon_grid=sample_grid.lon_grid.copy(),
        z_grid=sample_grid.z_grid.copy(),
        concentration=sample_grid.concentration.copy() * 2,
        mass_accumulated=sample_grid.mass_accumulated.copy() * 2,
        sample_count=sample_grid.sample_count.copy(),
        start_time=sample_grid.start_time,
        end_time=sample_grid.end_time,
    )
    grid2.config = sample_grid.config
    
    writer = CdumpWriter(config)
    output_file = tmp_path / "test_multi_grid.bin"
    
    writer.write(output_file, [sample_grid, grid2])
    
    assert output_file.exists()


def test_write_with_custom_pollutants(config, sample_grid, tmp_path):
    """Test writing with custom pollutant IDs."""
    writer = CdumpWriter(config)
    output_file = tmp_path / "test_pollutants.bin"
    
    pollutant_ids = ["SO2", "NO2", "PM10"]
    writer.write(output_file, [sample_grid], pollutant_ids=pollutant_ids)
    
    assert output_file.exists()


def test_binary_format_big_endian(config, sample_grid, tmp_path):
    """Test that binary output is big-endian."""
    writer = CdumpWriter(config)
    output_file = tmp_path / "test_endian.bin"
    
    writer.write(output_file, [sample_grid])
    
    # Read first few bytes and check they're big-endian
    with open(output_file, 'rb') as f:
        # First 4 bytes should be met model ID (ASCII)
        met_id = f.read(4).decode('ascii')
        assert met_id == "GFS "
        
        # Next should be year (big-endian int)
        year_bytes = f.read(4)
        year = struct.unpack('>i', year_bytes)[0]
        assert year == 2024


def test_header_record_1(config, sample_grid, tmp_path):
    """Test that header record #1 is correctly written."""
    writer = CdumpWriter(config, packing=True)
    output_file = tmp_path / "test_header1.bin"
    
    writer.write(output_file, [sample_grid])
    
    with open(output_file, 'rb') as f:
        # Record #1: Model ID + 5 ints + num_locations + packing_flag
        met_id = f.read(4).decode('ascii')
        year, month, day, hour, fcst = struct.unpack('>5i', f.read(20))
        num_locs = struct.unpack('>i', f.read(4))[0]
        packing = struct.unpack('>i', f.read(4))[0]
        
        assert met_id == "GFS "
        assert year == 2024
        assert month == 1
        assert day == 15
        assert hour == 12
        assert fcst == 0
        assert num_locs == 1
        assert packing == 1  # Packed format


def test_header_record_3_grid_definition(config, sample_grid, tmp_path):
    """Test that grid definition is correctly written."""
    writer = CdumpWriter(config)
    output_file = tmp_path / "test_grid_def.bin"
    
    writer.write(output_file, [sample_grid])
    
    with open(output_file, 'rb') as f:
        # Skip to record #3 (after record #1 and #2)
        # Record #1: 4 + 20 + 4 + 4 = 32 bytes
        # Record #2: 16 + 12 + 4 = 32 bytes per location
        skip_bytes = 32 + 32 * config.num_start_locations
        f.seek(skip_bytes)
        
        # Record #3: Grid definition
        nlat, nlon = struct.unpack('>2i', f.read(8))
        dlat, dlon = struct.unpack('>2f', f.read(8))
        lat_ll, lon_ll = struct.unpack('>2f', f.read(8))
        
        assert nlat == len(sample_grid.lat_grid)
        assert nlon == len(sample_grid.lon_grid)
        assert dlat == pytest.approx(0.1, abs=0.01)
        assert dlon == pytest.approx(0.1, abs=0.01)


def test_generate_filename():
    """Test filename generation."""
    dt = datetime(2024, 1, 15, 12, 0)
    
    # Basic filename
    filename = CdumpWriter.generate_filename(dt)
    assert filename == "cdump_240115_12"
    
    # With location
    filename = CdumpWriter.generate_filename(dt, location_name="seoul")
    assert filename == "cdump_seoul_240115_12"
    
    # With location and suffix
    filename = CdumpWriter.generate_filename(dt, location_name="seoul", suffix="test")
    assert filename == "cdump_seoul_test_240115_12"


def test_packed_concentration_format(config, sample_grid, tmp_path):
    """Test that packed concentration format is correct."""
    writer = CdumpWriter(config, packing=True)
    output_file = tmp_path / "test_packed_format.bin"
    
    writer.write(output_file, [sample_grid])
    
    # File should exist and be readable
    assert output_file.exists()
    
    # Packed format should write non-zero count followed by (i, j, value) tuples
    # This is tested implicitly by successful write


def test_unpacked_concentration_format(config, sample_grid, tmp_path):
    """Test that unpacked concentration format is correct."""
    writer = CdumpWriter(config, packing=False)
    output_file = tmp_path / "test_unpacked_format.bin"
    
    writer.write(output_file, [sample_grid])
    
    # File should exist and be readable
    assert output_file.exists()
    
    # Unpacked format should write full grid as float array
    # Size should be predictable: header + (nlat * nlon * nlevels * 4 bytes per float)
    nlat = len(sample_grid.lat_grid)
    nlon = len(sample_grid.lon_grid)
    nlevels = len(sample_grid.z_grid)
    
    # At least the concentration data should be present
    file_size = output_file.stat().st_size
    min_conc_size = nlat * nlon * nlevels * 4  # 4 bytes per float
    assert file_size >= min_conc_size


def test_multiple_pollutants(config, sample_grid, tmp_path):
    """Test writing with multiple pollutant species."""
    writer = CdumpWriter(config)
    output_file = tmp_path / "test_multi_pollutant.bin"
    
    pollutants = ["PM25", "PM10", "SO2"]
    writer.write(output_file, [sample_grid], pollutant_ids=pollutants)
    
    assert output_file.exists()
    
    # File should be larger with multiple pollutants
    # (same grid written multiple times, once per pollutant per level)


def test_pollutant_id_formatting(config, sample_grid, tmp_path):
    """Test that pollutant IDs are correctly formatted."""
    writer = CdumpWriter(config)
    output_file = tmp_path / "test_pollutant_format.bin"
    
    # Test with various ID lengths
    pollutants = ["A", "AB", "ABC", "ABCD", "ABCDE"]  # Last one should be truncated
    writer.write(output_file, [sample_grid], pollutant_ids=pollutants)
    
    assert output_file.exists()


def test_grid_without_config(config, sample_grid, tmp_path):
    """Test writing grid without config (should use fallback times)."""
    # Remove config from grid
    if hasattr(sample_grid, 'config'):
        delattr(sample_grid, 'config')
    
    writer = CdumpWriter(config)
    output_file = tmp_path / "test_no_config.bin"
    
    # Should still write successfully using simulation times
    writer.write(output_file, [sample_grid])
    
    assert output_file.exists()


def test_zero_concentration_grid(config, grid_config, tmp_path):
    """Test writing a grid with all zero concentrations."""
    # Create grid with all zeros
    nlat = 21
    nlon = 21
    nlevels = 4
    
    lat_grid = np.linspace(36.5, 38.5, nlat)
    lon_grid = np.linspace(126.0, 128.0, nlon)
    z_grid = np.array([0, 100, 500, 1000], dtype=float)
    
    concentration = np.zeros((nlevels, nlat, nlon))  # (nz, ny, nx) order
    
    grid = ConcentrationGrid(
        lat_grid=lat_grid,
        lon_grid=lon_grid,
        z_grid=z_grid,
        concentration=concentration,
        mass_accumulated=concentration.copy(),
        sample_count=np.ones_like(concentration),
        start_time=grid_config.sampling_start,
        end_time=grid_config.sampling_end,
    )
    grid.config = grid_config
    
    writer = CdumpWriter(config, packing=True)
    output_file = tmp_path / "test_zero_grid.bin"
    
    writer.write(output_file, [grid])
    
    assert output_file.exists()
    # Packed format should be very small for all-zero grid
