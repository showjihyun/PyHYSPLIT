"""HYSPLIT CONTROL and SETUP.CFG file parser and writer.

Parses the fixed-format CONTROL text file and Fortran namelist SETUP.CFG
file into a SimulationConfig dataclass, and provides reverse generation
(write) from a SimulationConfig back to CONTROL/SETUP.CFG files.

References:
    Draxler, R.R. (1999) "HYSPLIT-4 User's Guide", NOAA Technical Memorandum
    Chapter 1, Appendix — CONTROL file format specification
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import TextIO

from pyhysplit.core.models import (
    ConfigParseError,
    ConcentrationGridConfig,
    SimulationConfig,
    StartLocation,
)


# ---------------------------------------------------------------------------
# CONTROL file parser
# ---------------------------------------------------------------------------

def _read_line(lines: list[str], idx: int, description: str) -> str:
    """Read a single line from the line list, raising on missing."""
    if idx >= len(lines):
        raise ConfigParseError(
            f"Unexpected end of file while reading {description}",
            line_number=idx + 1,
            expected=description,
        )
    return lines[idx].strip()


def _parse_int(value: str, line_number: int, description: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise ConfigParseError(
            f"Cannot parse integer '{value}' for {description}",
            line_number=line_number,
            expected=f"integer ({description})",
        )


def _parse_float(value: str, line_number: int, description: str) -> float:
    try:
        return float(value)
    except ValueError:
        raise ConfigParseError(
            f"Cannot parse float '{value}' for {description}",
            line_number=line_number,
            expected=f"float ({description})",
        )


def parse_control(text: str) -> dict:
    """Parse a HYSPLIT CONTROL file into a raw dictionary.

    Parameters
    ----------
    text : str
        Full text content of the CONTROL file.

    Returns
    -------
    dict
        Parsed fields ready for conversion to SimulationConfig.

    Raises
    ------
    ConfigParseError
        If required fields are missing or have invalid format.
    """
    lines = text.splitlines()
    idx = 0

    # Line 1: start time  YY MM DD HH
    raw = _read_line(lines, idx, "start time (YY MM DD HH)")
    idx += 1
    parts = raw.split()
    if len(parts) < 4:
        raise ConfigParseError(
            "Start time requires 4 fields (YY MM DD HH)",
            line_number=1,
            expected="YY MM DD HH",
        )
    yy = _parse_int(parts[0], 1, "year")
    mm = _parse_int(parts[1], 1, "month")
    dd = _parse_int(parts[2], 1, "day")
    hh = _parse_int(parts[3], 1, "hour")
    # Two-digit year convention: 0-49 → 2000s, 50-99 → 1900s
    year = yy + 2000 if yy < 50 else yy + 1900 if yy < 100 else yy
    start_time = datetime(year, mm, dd, hh)

    # Line 2: number of start locations
    raw = _read_line(lines, idx, "number of start locations")
    idx += 1
    num_starts = _parse_int(raw, 2, "number of start locations")
    if num_starts < 1:
        raise ConfigParseError(
            "Number of start locations must be >= 1",
            line_number=2,
            expected="positive integer",
        )

    # Lines 3..2+N: start locations  LAT LON HEIGHT
    start_locations: list[StartLocation] = []
    for i in range(num_starts):
        raw = _read_line(lines, idx, f"start location {i + 1}")
        idx += 1
        parts = raw.split()
        if len(parts) < 3:
            raise ConfigParseError(
                f"Start location {i + 1} requires 3 fields (LAT LON HEIGHT)",
                line_number=idx,
                expected="LAT LON HEIGHT",
            )
        lat = _parse_float(parts[0], idx, "latitude")
        lon = _parse_float(parts[1], idx, "longitude")
        height = _parse_float(parts[2], idx, "height")
        start_locations.append(StartLocation(lat=lat, lon=lon, height=height))

    # Total run hours
    raw = _read_line(lines, idx, "total run hours")
    idx += 1
    total_run_hours = _parse_int(raw, idx, "total run hours")

    # Vertical motion method
    raw = _read_line(lines, idx, "vertical motion method")
    idx += 1
    vertical_motion = _parse_int(raw, idx, "vertical motion method")

    # Model top
    raw = _read_line(lines, idx, "model top")
    idx += 1
    model_top = _parse_float(raw, idx, "model top")

    # Number of met files
    raw = _read_line(lines, idx, "number of met files")
    idx += 1
    num_met = _parse_int(raw, idx, "number of met files")

    # Met file pairs (directory, filename)
    met_files: list[tuple[str, str]] = []
    for i in range(num_met):
        met_dir = _read_line(lines, idx, f"met directory {i + 1}")
        idx += 1
        met_file = _read_line(lines, idx, f"met filename {i + 1}")
        idx += 1
        met_files.append((met_dir, met_file))

    # Number of concentration grids (optional — may not be present)
    concentration_grids: list[ConcentrationGridConfig] = []
    if idx < len(lines):
        raw = _read_line(lines, idx, "number of concentration grids")
        idx += 1
        num_grids = _parse_int(raw, idx, "number of concentration grids")

        for i in range(num_grids):
            grid = _parse_concentration_grid(lines, idx, i + 1)
            idx += grid["_lines_consumed"]
            concentration_grids.append(grid["config"])

    return {
        "start_time": start_time,
        "num_start_locations": num_starts,
        "start_locations": start_locations,
        "total_run_hours": total_run_hours,
        "vertical_motion": vertical_motion,
        "model_top": model_top,
        "met_files": met_files,
        "concentration_grids": concentration_grids,
    }


def _parse_concentration_grid(lines: list[str], idx: int,
                              grid_num: int) -> dict:
    """Parse a single concentration grid block from CONTROL lines.

    Returns dict with 'config' (ConcentrationGridConfig) and
    '_lines_consumed' (int).
    """
    start_idx = idx

    # Line: CENTER_LAT CENTER_LON SPACING_LAT SPACING_LON SPAN_LAT SPAN_LON
    raw = _read_line(lines, idx, f"concentration grid {grid_num} spatial params")
    idx += 1
    parts = raw.split()
    if len(parts) < 6:
        raise ConfigParseError(
            f"Concentration grid {grid_num} spatial params require 6 fields",
            line_number=idx,
            expected="CENTER_LAT CENTER_LON SPACING_LAT SPACING_LON SPAN_LAT SPAN_LON",
        )
    center_lat = _parse_float(parts[0], idx, "center_lat")
    center_lon = _parse_float(parts[1], idx, "center_lon")
    spacing_lat = _parse_float(parts[2], idx, "spacing_lat")
    spacing_lon = _parse_float(parts[3], idx, "spacing_lon")
    span_lat = _parse_float(parts[4], idx, "span_lat")
    span_lon = _parse_float(parts[5], idx, "span_lon")

    # Line: levels (space-separated floats)
    raw = _read_line(lines, idx, f"concentration grid {grid_num} levels")
    idx += 1
    levels = [_parse_float(v, idx, "level") for v in raw.split()]

    # Line: sampling start  YY MM DD HH
    raw = _read_line(lines, idx, f"concentration grid {grid_num} sampling start")
    idx += 1
    parts = raw.split()
    if len(parts) < 4:
        raise ConfigParseError(
            f"Sampling start requires 4 fields (YY MM DD HH)",
            line_number=idx,
            expected="YY MM DD HH",
        )
    syy = _parse_int(parts[0], idx, "sampling start year")
    smm = _parse_int(parts[1], idx, "sampling start month")
    sdd = _parse_int(parts[2], idx, "sampling start day")
    shh = _parse_int(parts[3], idx, "sampling start hour")
    syear = syy + 2000 if syy < 50 else syy + 1900 if syy < 100 else syy
    sampling_start = datetime(syear, smm, sdd, shh)

    # Line: sampling end  YY MM DD HH
    raw = _read_line(lines, idx, f"concentration grid {grid_num} sampling end")
    idx += 1
    parts = raw.split()
    if len(parts) < 4:
        raise ConfigParseError(
            f"Sampling end requires 4 fields (YY MM DD HH)",
            line_number=idx,
            expected="YY MM DD HH",
        )
    eyy = _parse_int(parts[0], idx, "sampling end year")
    emm = _parse_int(parts[1], idx, "sampling end month")
    edd = _parse_int(parts[2], idx, "sampling end day")
    ehh = _parse_int(parts[3], idx, "sampling end hour")
    eyear = eyy + 2000 if eyy < 50 else eyy + 1900 if eyy < 100 else eyy
    sampling_end = datetime(eyear, emm, edd, ehh)

    # Line: averaging period (hours)
    raw = _read_line(lines, idx, f"concentration grid {grid_num} averaging period")
    idx += 1
    averaging_period = _parse_int(raw, idx, "averaging period")

    config = ConcentrationGridConfig(
        center_lat=center_lat,
        center_lon=center_lon,
        spacing_lat=spacing_lat,
        spacing_lon=spacing_lon,
        span_lat=span_lat,
        span_lon=span_lon,
        levels=levels,
        sampling_start=sampling_start,
        sampling_end=sampling_end,
        averaging_period=averaging_period,
    )
    return {"config": config, "_lines_consumed": idx - start_idx}


# ---------------------------------------------------------------------------
# SETUP.CFG parser
# ---------------------------------------------------------------------------

# Mapping from SETUP.CFG namelist keys to SimulationConfig field names + types
_SETUP_KEY_MAP: dict[str, tuple[str, type]] = {
    "NUMPAR": ("num_particles", int),
    "MAXPAR": ("max_particles", int),
    "KMIXD": ("kmixd", int),
    "KMIX0": ("kmix0", int),
    "MGMIN": ("mgmin", int),
    "KHMAX": ("khmax", float),
    "DELT": ("dt_max", float),
    "TRATIO": ("sigma", float),
    "DRYDEP": ("dry_deposition", bool),
    "WETDEP": ("wet_deposition", bool),
    "TURBULENCE": ("turbulence_on", bool),
}


def parse_setup_cfg(text: str) -> dict:
    """Parse a HYSPLIT SETUP.CFG (Fortran &SETUP namelist) file.

    Parameters
    ----------
    text : str
        Full text content of the SETUP.CFG file.

    Returns
    -------
    dict
        Key-value pairs for SETUP parameters (using SimulationConfig field names).
    """
    result: dict = {}

    # Strip the &SETUP ... / block markers
    # Fortran namelist: starts with &SETUP, ends with / or &END
    content = text
    # Remove &SETUP header
    content = re.sub(r'&SETUP\b', '', content, flags=re.IGNORECASE)
    # Remove trailing / or &END
    content = re.sub(r'/\s*$', '', content, flags=re.MULTILINE)
    content = re.sub(r'&END\b', '', content, flags=re.IGNORECASE)

    # Parse key=value pairs (comma or newline separated)
    # Handle: KEY = VALUE, KEY = VALUE,
    pairs = re.findall(r'(\w+)\s*=\s*([^,/\n]+)', content)

    for key_raw, val_raw in pairs:
        key = key_raw.strip().upper()
        val = val_raw.strip().rstrip(',')

        if key in _SETUP_KEY_MAP:
            field_name, field_type = _SETUP_KEY_MAP[key]
            if field_type is bool:
                # Fortran booleans: .TRUE., .FALSE., T, F, 1, 0
                val_upper = val.upper().strip('.')
                result[field_name] = val_upper in ('TRUE', 'T', '1')
            elif field_type is int:
                try:
                    result[field_name] = int(float(val))
                except ValueError:
                    pass  # skip unparseable values
            elif field_type is float:
                try:
                    result[field_name] = float(val)
                except ValueError:
                    pass
            else:
                result[field_name] = val

    return result


# ---------------------------------------------------------------------------
# Combined parser: CONTROL + optional SETUP.CFG → SimulationConfig
# ---------------------------------------------------------------------------

def parse_config(control_text: str,
                 setup_text: str | None = None) -> SimulationConfig:
    """Parse CONTROL (and optionally SETUP.CFG) into a SimulationConfig.

    Parameters
    ----------
    control_text : str
        Full text of the CONTROL file.
    setup_text : str or None
        Full text of the SETUP.CFG file, or None if not provided.

    Returns
    -------
    SimulationConfig

    Raises
    ------
    ConfigParseError
        On any parsing error.
    """
    ctrl = parse_control(control_text)
    setup = parse_setup_cfg(setup_text) if setup_text else {}

    config = SimulationConfig(
        start_time=ctrl["start_time"],
        num_start_locations=ctrl["num_start_locations"],
        start_locations=ctrl["start_locations"],
        total_run_hours=ctrl["total_run_hours"],
        vertical_motion=ctrl["vertical_motion"],
        model_top=ctrl["model_top"],
        met_files=ctrl["met_files"],
        concentration_grids=ctrl["concentration_grids"],
        **{k: v for k, v in setup.items()},
    )
    return config


# ---------------------------------------------------------------------------
# CONTROL file writer
# ---------------------------------------------------------------------------

def _format_year(dt: datetime) -> int:
    """Format a datetime year as 2-digit YY for CONTROL file."""
    return dt.year % 100


def write_control(config: SimulationConfig) -> str:
    """Generate a HYSPLIT CONTROL file from a SimulationConfig.

    Parameters
    ----------
    config : SimulationConfig

    Returns
    -------
    str
        CONTROL file content.
    """
    lines: list[str] = []

    # Start time
    st = config.start_time
    lines.append(f"{_format_year(st):02d} {st.month:02d} {st.day:02d} {st.hour:02d}")

    # Number of start locations
    lines.append(str(config.num_start_locations))

    # Start locations
    for loc in config.start_locations:
        lines.append(f"{loc.lat} {loc.lon} {loc.height}")

    # Total run hours
    lines.append(str(config.total_run_hours))

    # Vertical motion
    lines.append(str(config.vertical_motion))

    # Model top
    lines.append(str(config.model_top))

    # Met files
    lines.append(str(len(config.met_files)))
    for met_dir, met_file in config.met_files:
        lines.append(met_dir)
        lines.append(met_file)

    # Concentration grids
    if config.concentration_grids:
        lines.append(str(len(config.concentration_grids)))
        for grid in config.concentration_grids:
            lines.append(
                f"{grid.center_lat} {grid.center_lon} "
                f"{grid.spacing_lat} {grid.spacing_lon} "
                f"{grid.span_lat} {grid.span_lon}"
            )
            lines.append(" ".join(str(lv) for lv in grid.levels))
            ss = grid.sampling_start
            lines.append(
                f"{_format_year(ss):02d} {ss.month:02d} {ss.day:02d} {ss.hour:02d}"
            )
            se = grid.sampling_end
            lines.append(
                f"{_format_year(se):02d} {se.month:02d} {se.day:02d} {se.hour:02d}"
            )
            lines.append(str(grid.averaging_period))

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# SETUP.CFG writer
# ---------------------------------------------------------------------------

# Reverse mapping: SimulationConfig field name → SETUP.CFG key
_FIELD_TO_SETUP_KEY: dict[str, str] = {v[0]: k for k, v in _SETUP_KEY_MAP.items()}


def write_setup_cfg(config: SimulationConfig) -> str:
    """Generate a HYSPLIT SETUP.CFG (Fortran namelist) from a SimulationConfig.

    Only writes fields that differ from SimulationConfig defaults.

    Parameters
    ----------
    config : SimulationConfig

    Returns
    -------
    str
        SETUP.CFG file content.
    """
    defaults = SimulationConfig.__dataclass_fields__
    lines: list[str] = ["&SETUP"]

    entries: list[str] = []
    for field_name, setup_key in _FIELD_TO_SETUP_KEY.items():
        value = getattr(config, field_name)
        field_info = defaults.get(field_name)

        # Always write all SETUP fields for round-trip fidelity
        if isinstance(value, bool):
            entries.append(f" {setup_key} = {'.TRUE.' if value else '.FALSE.'},")
        elif isinstance(value, int):
            entries.append(f" {setup_key} = {value},")
        elif isinstance(value, float):
            entries.append(f" {setup_key} = {value},")
        else:
            entries.append(f" {setup_key} = {value},")

    lines.extend(entries)
    lines.append(" /")
    return "\n".join(lines) + "\n"
