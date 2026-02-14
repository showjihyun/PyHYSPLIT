"""Property-based tests for the ConfigParser module.

Properties 26-27 from the HYSPLIT Trajectory Engine design document.
"""

from __future__ import annotations

import re
from datetime import datetime

import pytest
from hypothesis import given, settings, assume, strategies as st

from pyhysplit.config_parser import (
    parse_control,
    parse_config,
    parse_setup_cfg,
    write_control,
    write_setup_cfg,
)
from pyhysplit.models import (
    ConfigParseError,
    ConcentrationGridConfig,
    SimulationConfig,
    StartLocation,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

valid_lat = st.floats(min_value=-89.0, max_value=89.0,
                      allow_nan=False, allow_infinity=False)
valid_lon = st.floats(min_value=-179.0, max_value=179.0,
                      allow_nan=False, allow_infinity=False)
valid_height = st.floats(min_value=0.0, max_value=25000.0,
                         allow_nan=False, allow_infinity=False)
valid_run_hours = st.integers(min_value=-8760, max_value=8760).filter(lambda x: x != 0)
valid_vertical_motion = st.integers(min_value=0, max_value=4)
valid_model_top = st.floats(min_value=1000.0, max_value=50000.0,
                            allow_nan=False, allow_infinity=False)

start_location_st = st.builds(
    StartLocation,
    lat=valid_lat,
    lon=valid_lon,
    height=valid_height,
)

# Strategy for a valid datetime within a reasonable range (2000-2049 for 2-digit year)
valid_datetime = st.builds(
    datetime,
    year=st.integers(min_value=2000, max_value=2049),
    month=st.integers(min_value=1, max_value=12),
    day=st.integers(min_value=1, max_value=28),  # safe for all months
    hour=st.integers(min_value=0, max_value=23),
)

# Strategy for a minimal valid SimulationConfig (no concentration grids)
simple_config_st = st.builds(
    SimulationConfig,
    start_time=valid_datetime,
    num_start_locations=st.just(1),
    start_locations=st.lists(start_location_st, min_size=1, max_size=1),
    total_run_hours=valid_run_hours,
    vertical_motion=valid_vertical_motion,
    model_top=valid_model_top,
    met_files=st.just([("/data/met", "gdas1.jan20.w1")]),
    concentration_grids=st.just([]),
    num_particles=st.integers(min_value=100, max_value=50000),
    max_particles=st.integers(min_value=1000, max_value=100000),
    kmixd=st.integers(min_value=0, max_value=3),
    kmix0=st.integers(min_value=50, max_value=1000),
    mgmin=st.integers(min_value=1, max_value=100),
    khmax=st.floats(min_value=1.0, max_value=99999.0,
                    allow_nan=False, allow_infinity=False),
    dt_max=st.floats(min_value=60.0, max_value=7200.0,
                     allow_nan=False, allow_infinity=False),
    sigma=st.floats(min_value=0.0, max_value=10.0,
                    allow_nan=False, allow_infinity=False),
    dry_deposition=st.booleans(),
    wet_deposition=st.booleans(),
    turbulence_on=st.booleans(),
)

# Strategy for config with concentration grids
conc_grid_st = st.builds(
    ConcentrationGridConfig,
    center_lat=valid_lat,
    center_lon=valid_lon,
    spacing_lat=st.floats(min_value=0.1, max_value=10.0,
                          allow_nan=False, allow_infinity=False),
    spacing_lon=st.floats(min_value=0.1, max_value=10.0,
                          allow_nan=False, allow_infinity=False),
    span_lat=st.floats(min_value=1.0, max_value=90.0,
                       allow_nan=False, allow_infinity=False),
    span_lon=st.floats(min_value=1.0, max_value=180.0,
                       allow_nan=False, allow_infinity=False),
    levels=st.just([100.0, 500.0, 1000.0]),
    sampling_start=valid_datetime,
    sampling_end=valid_datetime,
    averaging_period=st.integers(min_value=1, max_value=24),
)

config_with_grids_st = st.builds(
    SimulationConfig,
    start_time=valid_datetime,
    num_start_locations=st.just(1),
    start_locations=st.lists(start_location_st, min_size=1, max_size=1),
    total_run_hours=valid_run_hours,
    vertical_motion=valid_vertical_motion,
    model_top=valid_model_top,
    met_files=st.just([("/data/met", "gdas1.jan20.w1")]),
    concentration_grids=st.lists(conc_grid_st, min_size=1, max_size=2),
    num_particles=st.just(2500),
    max_particles=st.just(10000),
    kmixd=st.just(0),
    kmix0=st.just(250),
    mgmin=st.just(10),
    khmax=st.just(9999.0),
    dt_max=st.just(3600.0),
    sigma=st.just(0.0),
    dry_deposition=st.just(False),
    wet_deposition=st.just(False),
    turbulence_on=st.just(True),
)


# ---------------------------------------------------------------------------
# Property 26: CONTROL/SETUP.CFG Round Trip
# Validates: Requirements 11.1, 11.2, 11.5
# ---------------------------------------------------------------------------

@given(config=simple_config_st)
@settings(max_examples=100)
def test_property_26_control_round_trip(config: SimulationConfig):
    """**Validates: Requirements 11.1, 11.2, 11.5**

    Feature: hysplit-trajectory-engine, Property 26: CONTROL/SETUP.CFG Round Trip
    write_control → parse_control → write_control must produce identical output.
    """
    text1 = write_control(config)
    parsed = parse_control(text1)

    # Reconstruct a config from parsed data + original SETUP fields
    config2 = SimulationConfig(
        start_time=parsed["start_time"],
        num_start_locations=parsed["num_start_locations"],
        start_locations=parsed["start_locations"],
        total_run_hours=parsed["total_run_hours"],
        vertical_motion=parsed["vertical_motion"],
        model_top=parsed["model_top"],
        met_files=parsed["met_files"],
        concentration_grids=parsed["concentration_grids"],
    )
    text2 = write_control(config2)

    assert text1 == text2, (
        f"CONTROL round trip failed.\n--- Original ---\n{text1}\n--- Round-trip ---\n{text2}"
    )


@given(config=simple_config_st)
@settings(max_examples=100)
def test_property_26_setup_cfg_round_trip(config: SimulationConfig):
    """**Validates: Requirements 11.1, 11.2, 11.5**

    Feature: hysplit-trajectory-engine, Property 26: SETUP.CFG Round Trip
    write_setup_cfg → parse_setup_cfg → write_setup_cfg must produce identical output.
    """
    text1 = write_setup_cfg(config)
    setup_dict = parse_setup_cfg(text1)

    # Apply parsed SETUP values back to a fresh config
    config2 = SimulationConfig(
        start_time=config.start_time,
        num_start_locations=config.num_start_locations,
        start_locations=config.start_locations,
        total_run_hours=config.total_run_hours,
        vertical_motion=config.vertical_motion,
        model_top=config.model_top,
        met_files=config.met_files,
        concentration_grids=config.concentration_grids,
        **setup_dict,
    )
    text2 = write_setup_cfg(config2)

    assert text1 == text2, (
        f"SETUP.CFG round trip failed.\n--- Original ---\n{text1}\n--- Round-trip ---\n{text2}"
    )


@given(config=config_with_grids_st)
@settings(max_examples=100)
def test_property_26_full_config_round_trip(config: SimulationConfig):
    """**Validates: Requirements 11.1, 11.2, 11.5**

    Feature: hysplit-trajectory-engine, Property 26: Full Config Round Trip
    parse_config(write_control, write_setup_cfg) must reconstruct equivalent config.
    """
    ctrl_text = write_control(config)
    setup_text = write_setup_cfg(config)

    config2 = parse_config(ctrl_text, setup_text)

    # Verify key fields match
    assert config2.start_time == config.start_time
    assert config2.num_start_locations == config.num_start_locations
    assert config2.total_run_hours == config.total_run_hours
    assert config2.vertical_motion == config.vertical_motion
    assert config2.met_files == config.met_files
    assert len(config2.concentration_grids) == len(config.concentration_grids)

    # Verify SETUP fields
    assert config2.num_particles == config.num_particles
    assert config2.max_particles == config.max_particles
    assert config2.kmixd == config.kmixd
    assert config2.dry_deposition == config.dry_deposition
    assert config2.wet_deposition == config.wet_deposition
    assert config2.turbulence_on == config.turbulence_on

    # Second write should match first
    ctrl_text2 = write_control(config2)
    assert ctrl_text == ctrl_text2


# ---------------------------------------------------------------------------
# Property 27: CONTROL 파일 오류 검출
# Validates: Requirements 11.3
# ---------------------------------------------------------------------------

def test_property_27_empty_control_raises():
    """**Validates: Requirements 11.3**

    Feature: hysplit-trajectory-engine, Property 27: CONTROL 파일 오류 검출
    Empty CONTROL file must raise ConfigParseError.
    """
    with pytest.raises(ConfigParseError):
        parse_control("")


def test_property_27_missing_start_locations_raises():
    """**Validates: Requirements 11.3**

    Feature: hysplit-trajectory-engine, Property 27: CONTROL 파일 오류 검출
    CONTROL file truncated after start time must raise ConfigParseError.
    """
    with pytest.raises(ConfigParseError):
        parse_control("20 01 15 00\n")


def test_property_27_bad_start_time_raises():
    """**Validates: Requirements 11.3**

    Feature: hysplit-trajectory-engine, Property 27: CONTROL 파일 오류 검출
    Malformed start time must raise ConfigParseError.
    """
    with pytest.raises(ConfigParseError):
        parse_control("not a date\n1\n40.0 -90.0 500.0\n48\n0\n10000.0\n1\n/data\nfile.arl\n")


def test_property_27_bad_location_count_raises():
    """**Validates: Requirements 11.3**

    Feature: hysplit-trajectory-engine, Property 27: CONTROL 파일 오류 검출
    Non-integer location count must raise ConfigParseError.
    """
    with pytest.raises(ConfigParseError):
        parse_control("20 01 15 00\nabc\n")


@given(
    n_fields=st.integers(min_value=0, max_value=2),
)
@settings(max_examples=50)
def test_property_27_truncated_location_raises(n_fields):
    """**Validates: Requirements 11.3**

    Feature: hysplit-trajectory-engine, Property 27: CONTROL 파일 오류 검출
    Location line with fewer than 3 fields must raise ConfigParseError.
    """
    fields = " ".join(["40.0"] * n_fields)
    control = f"20 01 15 00\n1\n{fields}\n48\n0\n10000.0\n1\n/data\nfile.arl\n"
    with pytest.raises(ConfigParseError):
        parse_control(control)


def test_property_27_zero_start_locations_raises():
    """**Validates: Requirements 11.3**

    Feature: hysplit-trajectory-engine, Property 27: CONTROL 파일 오류 검출
    Zero start locations must raise ConfigParseError.
    """
    with pytest.raises(ConfigParseError):
        parse_control("20 01 15 00\n0\n48\n0\n10000.0\n1\n/data\nfile.arl\n")
