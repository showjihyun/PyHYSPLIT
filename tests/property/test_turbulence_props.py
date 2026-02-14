"""Property-based tests for the TurbulenceModule.

Properties 16-19 from the HYSPLIT Trajectory Engine design document.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
from hypothesis import given, settings, assume, strategies as st

from pyhysplit.models import MetData, SimulationConfig, StartLocation
from pyhysplit.turbulence import TurbulenceModule, KZ_BACKGROUND


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**overrides) -> SimulationConfig:
    """Create a minimal SimulationConfig with optional overrides."""
    defaults = dict(
        start_time=datetime(2020, 1, 1),
        num_start_locations=1,
        start_locations=[StartLocation(lat=37.0, lon=127.0, height=500.0)],
        total_run_hours=48,
        vertical_motion=0,
        model_top=25000.0,
        met_files=[(".", "met.arl")],
    )
    defaults.update(overrides)
    return SimulationConfig(**defaults)


def _make_met() -> MetData:
    """Create a tiny MetData stub (only grid arrays needed)."""
    return MetData(
        u=np.zeros((2, 3, 4, 5)),
        v=np.zeros((2, 3, 4, 5)),
        w=np.zeros((2, 3, 4, 5)),
        lon_grid=np.linspace(100, 110, 5),
        lat_grid=np.linspace(30, 40, 4),
        z_grid=np.linspace(0, 3000, 3),
        t_grid=np.array([0.0, 10800.0]),
    )


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

positive_z = st.floats(min_value=0.0, max_value=50000.0,
                       allow_nan=False, allow_infinity=False)
positive_pbl = st.floats(min_value=1.0, max_value=5000.0,
                         allow_nan=False, allow_infinity=False)
positive_ustar = st.floats(min_value=0.01, max_value=5.0,
                           allow_nan=False, allow_infinity=False)
negative_L = st.floats(min_value=-10000.0, max_value=-0.1,
                       allow_nan=False, allow_infinity=False)
positive_L = st.floats(min_value=0.1, max_value=10000.0,
                       allow_nan=False, allow_infinity=False)
positive_dx = st.floats(min_value=1.0, max_value=1e7,
                        allow_nan=False, allow_infinity=False)
positive_khmax = st.floats(min_value=1.0, max_value=1e8,
                           allow_nan=False, allow_infinity=False)


# ---------------------------------------------------------------------------
# Property 16: Kz 비음수 및 PBL 경계 동작
# Validates: Requirements 7.2, 7.8
# ---------------------------------------------------------------------------

@given(z=positive_z, pbl_h=positive_pbl, ustar=positive_ustar, L=negative_L)
@settings(max_examples=100)
def test_property_16_kz_nonneg_and_pbl_boundary_unstable(z, pbl_h, ustar, L):
    """**Validates: Requirements 7.2, 7.8**

    Feature: hysplit-trajectory-engine, Property 16: Kz 비음수 및 PBL 경계
    Kz must always be >= KZ_BACKGROUND (0.01).
    When z > pbl_h, Kz must equal exactly KZ_BACKGROUND.
    """
    kz = TurbulenceModule.compute_kz(z, pbl_h, ustar, L)
    assert kz >= KZ_BACKGROUND, f"Kz={kz} < background {KZ_BACKGROUND}"
    if z > pbl_h:
        assert kz == KZ_BACKGROUND, (
            f"Above PBL (z={z} > pbl_h={pbl_h}): Kz={kz} != {KZ_BACKGROUND}"
        )


@given(z=positive_z, pbl_h=positive_pbl, ustar=positive_ustar, L=positive_L)
@settings(max_examples=100)
def test_property_16_kz_nonneg_and_pbl_boundary_stable(z, pbl_h, ustar, L):
    """**Validates: Requirements 7.2, 7.8**

    Feature: hysplit-trajectory-engine, Property 16: Kz 비음수 및 PBL 경계 (stable)
    Same property under stable atmospheric conditions (L > 0).
    """
    kz = TurbulenceModule.compute_kz(z, pbl_h, ustar, L)
    assert kz >= KZ_BACKGROUND, f"Kz={kz} < background {KZ_BACKGROUND}"
    if z > pbl_h:
        assert kz == KZ_BACKGROUND, (
            f"Above PBL (z={z} > pbl_h={pbl_h}): Kz={kz} != {KZ_BACKGROUND}"
        )


# ---------------------------------------------------------------------------
# Property 17: 안정도 Kz 순서
# Validates: Requirements 7.3, 7.4
# ---------------------------------------------------------------------------

@given(
    z_frac=st.floats(min_value=0.01, max_value=0.99,
                     allow_nan=False, allow_infinity=False),
    pbl_h=positive_pbl,
    ustar=positive_ustar,
    L_neg=negative_L,
    L_pos=positive_L,
)
@settings(max_examples=100)
def test_property_17_stability_kz_ordering(z_frac, pbl_h, ustar, L_neg, L_pos):
    """**Validates: Requirements 7.3, 7.4**

    Feature: hysplit-trajectory-engine, Property 17: 안정도 Kz 순서
    For the same height inside the PBL, unstable (L<0) Kz >= stable (L>0) Kz.
    """
    z = z_frac * pbl_h  # ensure 0 < z < pbl_h

    kz_unstable = TurbulenceModule.compute_kz(z, pbl_h, ustar, L_neg)
    kz_stable = TurbulenceModule.compute_kz(z, pbl_h, ustar, L_pos)

    assert kz_unstable >= kz_stable, (
        f"Unstable Kz ({kz_unstable}) < Stable Kz ({kz_stable}) "
        f"at z={z}, pbl_h={pbl_h}, u*={ustar}, L_neg={L_neg}, L_pos={L_pos}"
    )


# ---------------------------------------------------------------------------
# Property 18: Kh 격자 비례
# Validates: Requirements 7.5
# ---------------------------------------------------------------------------

@given(dx_m=positive_dx, khmax=positive_khmax)
@settings(max_examples=100)
def test_property_18_kh_grid_proportionality(dx_m, khmax):
    """**Validates: Requirements 7.5**

    Feature: hysplit-trajectory-engine, Property 18: Kh 격자 비례
    Kh must equal min(0.0001 * dx^(4/3), khmax).
    """
    kh = TurbulenceModule.compute_kh(dx_m, khmax)
    expected = min(0.0001 * dx_m ** (4.0 / 3.0), khmax)
    assert abs(kh - expected) < 1e-6 * max(abs(expected), 1.0), (
        f"Kh={kh} != expected {expected} for dx={dx_m}, khmax={khmax}"
    )


@given(
    dx_small=st.floats(min_value=1.0, max_value=1e4,
                       allow_nan=False, allow_infinity=False),
    dx_large=st.floats(min_value=1e4, max_value=1e7,
                       allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_property_18_kh_monotonicity(dx_small, dx_large):
    """**Validates: Requirements 7.5**

    Feature: hysplit-trajectory-engine, Property 18: Kh 단조 증가
    Kh should be non-decreasing as dx increases (or saturate at khmax).
    """
    assume(dx_small < dx_large)
    khmax = 1e12  # large enough to not cap
    kh_small = TurbulenceModule.compute_kh(dx_small, khmax)
    kh_large = TurbulenceModule.compute_kh(dx_large, khmax)
    assert kh_large >= kh_small, (
        f"Kh not monotone: Kh({dx_small})={kh_small} > Kh({dx_large})={kh_large}"
    )


# ---------------------------------------------------------------------------
# Property 19: 난류 비활성화 영섭동
# Validates: Requirements 7.7
# ---------------------------------------------------------------------------

@given(
    lon=st.floats(min_value=100, max_value=110,
                  allow_nan=False, allow_infinity=False),
    lat=st.floats(min_value=30, max_value=40,
                  allow_nan=False, allow_infinity=False),
    z=st.floats(min_value=0, max_value=3000,
                allow_nan=False, allow_infinity=False),
    dt=st.floats(min_value=1, max_value=3600,
                 allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_property_19_zero_perturbation_when_disabled(lon, lat, z, dt):
    """**Validates: Requirements 7.7**

    Feature: hysplit-trajectory-engine, Property 19: 난류 비활성화 영섭동
    When turbulence_on=False, get_perturbation must return (0, 0, 0).
    """
    met = _make_met()
    config = _make_config(turbulence_on=False, sigma=0.0)
    turb = TurbulenceModule(met, config)

    du, dv, dw = turb.get_perturbation(lon, lat, z, 0.0, dt)

    assert du == 0.0, f"du={du} != 0 with turbulence off"
    assert dv == 0.0, f"dv={dv} != 0 with turbulence off"
    assert dw == 0.0, f"dw={dw} != 0 with turbulence off"
