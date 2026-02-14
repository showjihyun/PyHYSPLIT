"""Property-based tests for the DepositionModule.

Properties 20-23 from the HYSPLIT Trajectory Engine design document.
"""

from __future__ import annotations

import math

from hypothesis import given, settings, assume, strategies as st

from pyhysplit.deposition import DepositionModule, GRAVITY, AIR_VISCOSITY


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

positive_mass = st.floats(min_value=1e-15, max_value=1e6,
                          allow_nan=False, allow_infinity=False)
positive_vd = st.floats(min_value=0.0, max_value=1.0,
                        allow_nan=False, allow_infinity=False)
positive_dz = st.floats(min_value=1.0, max_value=50000.0,
                        allow_nan=False, allow_infinity=False)
positive_scav = st.floats(min_value=0.0, max_value=0.01,
                          allow_nan=False, allow_infinity=False)
positive_dt = st.floats(min_value=1.0, max_value=3600.0,
                        allow_nan=False, allow_infinity=False)
positive_diameter = st.floats(min_value=1e-9, max_value=1e-3,
                              allow_nan=False, allow_infinity=False)
positive_density = st.floats(min_value=100.0, max_value=10000.0,
                             allow_nan=False, allow_infinity=False)
positive_resistance = st.floats(min_value=1.0, max_value=1e6,
                                allow_nan=False, allow_infinity=False)
positive_vg = st.floats(min_value=0.0, max_value=1.0,
                        allow_nan=False, allow_infinity=False)
positive_precip = st.floats(min_value=1e-6, max_value=200.0,
                            allow_nan=False, allow_infinity=False)
positive_a = st.floats(min_value=1e-8, max_value=1e-2,
                       allow_nan=False, allow_infinity=False)
positive_b = st.floats(min_value=0.1, max_value=2.0,
                       allow_nan=False, allow_infinity=False)


# ---------------------------------------------------------------------------
# Property 20: 침적 질량 단조 감소 및 양수
# Validates: Requirements 8.5, 8.6
# ---------------------------------------------------------------------------

@given(mass=positive_mass, v_d=positive_vd, dz=positive_dz,
       scav=positive_scav, dt=positive_dt)
@settings(max_examples=200)
def test_property_20_mass_monotone_decrease_and_positive(mass, v_d, dz, scav, dt):
    """**Validates: Requirements 8.5, 8.6**

    Feature: hysplit-trajectory-engine, Property 20: 침적 질량 단조 감소 및 양수
    For any positive initial mass, apply_deposition must return
    0 < m(t+dt) <= m(t).
    """
    new_mass = DepositionModule.apply_deposition(mass, v_d, dz, scav, dt)
    assert new_mass > 0, f"Mass must be positive, got {new_mass}"
    assert new_mass <= mass, (
        f"Mass must not increase: {new_mass} > {mass}"
    )


@given(mass=positive_mass, dz=positive_dz, dt=positive_dt)
@settings(max_examples=100)
def test_property_20_zero_deposition_preserves_mass(mass, dz, dt):
    """**Validates: Requirements 8.5, 8.6**

    Feature: hysplit-trajectory-engine, Property 20: 영침적 시 질량 보존
    When v_d=0 and Λ=0, mass must be exactly preserved.
    """
    new_mass = DepositionModule.apply_deposition(mass, 0.0, dz, 0.0, dt)
    assert new_mass == mass, (
        f"With zero deposition, mass should be preserved: {new_mass} != {mass}"
    )


# ---------------------------------------------------------------------------
# Property 21: Stokes 침강 속도 공식
# Validates: Requirements 8.1
# ---------------------------------------------------------------------------

@given(d=positive_diameter, rho=positive_density)
@settings(max_examples=200)
def test_property_21_stokes_settling_velocity(d, rho):
    """**Validates: Requirements 8.1**

    Feature: hysplit-trajectory-engine, Property 21: Stokes 침강 속도
    v_g must equal ρ·d²·g/(18·μ).
    """
    vg = DepositionModule.gravitational_settling(d, rho)
    expected = rho * d ** 2 * GRAVITY / (18.0 * AIR_VISCOSITY)
    assert abs(vg - expected) < 1e-12 * max(abs(expected), 1e-30), (
        f"v_g={vg} != expected {expected} for d={d}, rho={rho}"
    )
    assert vg >= 0, f"Settling velocity must be non-negative, got {vg}"


@given(
    d_small=st.floats(min_value=1e-9, max_value=1e-6,
                      allow_nan=False, allow_infinity=False),
    d_large=st.floats(min_value=1e-6, max_value=1e-3,
                      allow_nan=False, allow_infinity=False),
    rho=positive_density,
)
@settings(max_examples=100)
def test_property_21_stokes_monotonicity_diameter(d_small, d_large, rho):
    """**Validates: Requirements 8.1**

    Feature: hysplit-trajectory-engine, Property 21: Stokes 직경 단조성
    Larger diameter → larger settling velocity.
    """
    assume(d_small < d_large)
    vg_small = DepositionModule.gravitational_settling(d_small, rho)
    vg_large = DepositionModule.gravitational_settling(d_large, rho)
    assert vg_large >= vg_small, (
        f"v_g not monotone in diameter: v_g({d_small})={vg_small} > v_g({d_large})={vg_large}"
    )


# ---------------------------------------------------------------------------
# Property 22: 3-저항 모델 건조 침적 속도
# Validates: Requirements 8.2
# ---------------------------------------------------------------------------

@given(r_a=positive_resistance, r_b=positive_resistance,
       r_s=positive_resistance, v_g=positive_vg)
@settings(max_examples=200)
def test_property_22_three_resistance_dry_deposition(r_a, r_b, r_s, v_g):
    """**Validates: Requirements 8.2**

    Feature: hysplit-trajectory-engine, Property 22: 3-저항 건조 침적
    v_d = 1/(r_a+r_b+r_s) + v_g, and v_d >= v_g.
    """
    vd = DepositionModule.dry_deposition_velocity(r_a, r_b, r_s, v_g)
    expected = 1.0 / (r_a + r_b + r_s) + v_g
    assert abs(vd - expected) < 1e-12 * max(abs(expected), 1e-30), (
        f"v_d={vd} != expected {expected}"
    )
    assert vd >= v_g, (
        f"v_d={vd} must be >= v_g={v_g}"
    )


# ---------------------------------------------------------------------------
# Property 23: Below-Cloud Scavenging 공식
# Validates: Requirements 8.3
# ---------------------------------------------------------------------------

@given(precip=positive_precip, a=positive_a, b=positive_b)
@settings(max_examples=200)
def test_property_23_below_cloud_scavenging_formula(precip, a, b):
    """**Validates: Requirements 8.3**

    Feature: hysplit-trajectory-engine, Property 23: Below-Cloud Scavenging
    Λ = a·P^b for P > 0.
    """
    lam = DepositionModule.below_cloud_scavenging(precip, a, b)
    expected = a * precip ** b
    assert abs(lam - expected) < 1e-12 * max(abs(expected), 1e-30), (
        f"Λ={lam} != expected {expected} for P={precip}, a={a}, b={b}"
    )
    assert lam >= 0, f"Scavenging coefficient must be non-negative, got {lam}"


def test_property_23_zero_precip_zero_scavenging():
    """**Validates: Requirements 8.3**

    Feature: hysplit-trajectory-engine, Property 23: P=0이면 Λ=0
    """
    assert DepositionModule.below_cloud_scavenging(0.0) == 0.0
    assert DepositionModule.below_cloud_scavenging(-1.0) == 0.0


@given(
    p_small=st.floats(min_value=0.01, max_value=10.0,
                      allow_nan=False, allow_infinity=False),
    p_large=st.floats(min_value=10.0, max_value=200.0,
                      allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_property_23_scavenging_monotonicity(p_small, p_large):
    """**Validates: Requirements 8.3**

    Feature: hysplit-trajectory-engine, Property 23: Scavenging 단조성
    Larger precipitation → larger scavenging coefficient.
    """
    assume(p_small < p_large)
    lam_small = DepositionModule.below_cloud_scavenging(p_small)
    lam_large = DepositionModule.below_cloud_scavenging(p_large)
    assert lam_large >= lam_small, (
        f"Scavenging not monotone: Λ({p_small})={lam_small} > Λ({p_large})={lam_large}"
    )
