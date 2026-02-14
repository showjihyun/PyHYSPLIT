"""Property-based tests for the meteorological data reader module.

Properties 11-12 from the HYSPLIT Trajectory Engine design document.
"""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings, assume, strategies as st

from pyhysplit.met_reader import (
    convert_omega_to_w,
    concatenate_met_files,
    MetReaderBase,
    RD,
    GRAVITY,
)
from pyhysplit.models import MetData


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Omega in Pa/s — typical range for atmospheric vertical velocity
omega_st = st.floats(min_value=-10.0, max_value=10.0,
                     allow_nan=False, allow_infinity=False)

# Temperature in Kelvin — realistic atmospheric range
temperature_st = st.floats(min_value=180.0, max_value=330.0,
                           allow_nan=False, allow_infinity=False)

# Pressure in Pa — from ~1 hPa to ~1100 hPa
pressure_st = st.floats(min_value=100.0, max_value=110000.0,
                        allow_nan=False, allow_infinity=False)


# ---------------------------------------------------------------------------
# Helper: simple in-memory MetReader for concatenation tests
# ---------------------------------------------------------------------------

class _SyntheticReader(MetReaderBase):
    """A reader that returns a pre-built MetData (no file I/O)."""

    def __init__(self, met: MetData):
        self._met = met

    def read(self, filepath: str) -> MetData:
        return self._met

    def get_variable_mapping(self) -> dict[str, str]:
        return {}


def _make_met(
    t_start: float,
    t_step: float,
    nt: int,
    nx: int = 3,
    ny: int = 3,
    nz: int = 2,
) -> MetData:
    """Create a minimal synthetic MetData with a given time grid."""
    t_grid = np.array([t_start + i * t_step for i in range(nt)], dtype=np.float64)
    shape = (nt, nz, ny, nx)
    return MetData(
        u=np.random.default_rng(42).standard_normal(shape),
        v=np.random.default_rng(43).standard_normal(shape),
        w=np.random.default_rng(44).standard_normal(shape),
        lon_grid=np.linspace(0, 10, nx),
        lat_grid=np.linspace(0, 10, ny),
        z_grid=np.linspace(1000, 500, nz),
        t_grid=t_grid,
        z_type="pressure",
        source="ARL",
    )


# ---------------------------------------------------------------------------
# Property 11: Pa/s → m/s 변환 공식 (Omega Conversion)
# Validates: Requirements 5.4
# ---------------------------------------------------------------------------

@given(omega=omega_st, T=temperature_st, P=pressure_st)
@settings(max_examples=200)
def test_property_11_omega_to_w_formula(omega, T, P):
    """**Validates: Requirements 5.4**

    Feature: hysplit-trajectory-engine, Property 11: Pa/s → m/s 변환 공식
    convert_omega_to_w must satisfy w = -omega * Rd * T / (g * P).
    """
    omega_arr = np.array([omega])
    T_arr = np.array([T])
    P_arr = np.array([P])

    w = convert_omega_to_w(omega_arr, T_arr, P_arr)
    expected = -omega * RD * T / (GRAVITY * P)

    assert np.isfinite(w[0]), f"w must be finite, got {w[0]}"
    assert abs(w[0] - expected) < 1e-10 * max(abs(expected), 1e-30), (
        f"w={w[0]} != expected {expected} for omega={omega}, T={T}, P={P}"
    )


@given(omega=st.floats(min_value=0.01, max_value=10.0,
                       allow_nan=False, allow_infinity=False),
       T=temperature_st, P=pressure_st)
@settings(max_examples=100)
def test_property_11_positive_omega_gives_negative_w(omega, T, P):
    """**Validates: Requirements 5.4**

    Feature: hysplit-trajectory-engine, Property 11: omega > 0 (하강) → w < 0
    Positive omega (subsidence in Pa/s) must produce negative w (downward in m/s).
    """
    w = convert_omega_to_w(np.array([omega]), np.array([T]), np.array([P]))
    assert w[0] < 0, (
        f"Positive omega={omega} should give negative w, got {w[0]}"
    )


# ---------------------------------------------------------------------------
# Property 12: 다중 기상 파일 시간 단조성 (Met File Time Monotonicity)
# Validates: Requirements 5.5
# ---------------------------------------------------------------------------

@given(
    t_start1=st.floats(min_value=0.0, max_value=1e6,
                       allow_nan=False, allow_infinity=False),
    t_step=st.floats(min_value=1.0, max_value=10800.0,
                     allow_nan=False, allow_infinity=False),
    nt1=st.integers(min_value=2, max_value=5),
    nt2=st.integers(min_value=2, max_value=5),
)
@settings(max_examples=100)
def test_property_12_concatenated_time_monotonicity(t_start1, t_step, nt1, nt2):
    """**Validates: Requirements 5.5**

    Feature: hysplit-trajectory-engine, Property 12: 다중 파일 시간 단조성
    After concatenating multiple met files, t_grid must be strictly
    monotonically increasing.
    """
    # File 1: [t_start1, t_start1 + t_step, ...]
    met1 = _make_met(t_start1, t_step, nt1)

    # File 2 starts where file 1 ends (may overlap at boundary)
    t_start2 = t_start1 + (nt1 - 1) * t_step
    met2 = _make_met(t_start2, t_step, nt2)

    reader1 = _SyntheticReader(met1)
    reader2 = _SyntheticReader(met2)

    merged = concatenate_met_files([reader1, reader2], ["file1", "file2"])

    # Strictly monotonically increasing
    diffs = np.diff(merged.t_grid)
    assert np.all(diffs > 0), (
        f"t_grid not strictly increasing: diffs={diffs}, t_grid={merged.t_grid}"
    )


@given(
    t_start=st.floats(min_value=0.0, max_value=1e6,
                      allow_nan=False, allow_infinity=False),
    t_step=st.floats(min_value=1.0, max_value=10800.0,
                     allow_nan=False, allow_infinity=False),
    n_files=st.integers(min_value=2, max_value=4),
    nt_per_file=st.integers(min_value=2, max_value=4),
)
@settings(max_examples=100)
def test_property_12_multi_file_monotonicity(t_start, t_step, n_files, nt_per_file):
    """**Validates: Requirements 5.5**

    Feature: hysplit-trajectory-engine, Property 12: N개 파일 시간 단조성
    Concatenating N files with overlapping boundaries still produces
    strictly monotonic t_grid.
    """
    readers = []
    paths = []
    for i in range(n_files):
        file_start = t_start + i * (nt_per_file - 1) * t_step
        met = _make_met(file_start, t_step, nt_per_file)
        readers.append(_SyntheticReader(met))
        paths.append(f"file_{i}")

    merged = concatenate_met_files(readers, paths)

    diffs = np.diff(merged.t_grid)
    assert np.all(diffs > 0), (
        f"t_grid not strictly increasing after {n_files}-file merge: "
        f"diffs={diffs}"
    )
