"""Deposition module for pyhysplit.

Implements dry deposition (3-resistance model), wet deposition
(below-cloud and in-cloud scavenging), gravitational settling (Stokes law),
and mass decay.

References:
    - Stein et al. (2015) Section 2d
    - Draxler & Hess (1998)

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7
"""

from __future__ import annotations

import math

import numpy as np

from pyhysplit.core.models import SimulationConfig


# Physical constants
GRAVITY = 9.80665        # m/s²
AIR_VISCOSITY = 1.81e-5  # Pa·s (dynamic viscosity of air at ~20°C)


class DepositionModule:
    """Handles dry/wet deposition and gravitational settling.

    Parameters
    ----------
    config : SimulationConfig
        Simulation configuration (used for dry/wet deposition flags).
    particle_diameter : float
        Particle diameter in meters (default: 1e-6 = 1 micron)
    particle_density : float
        Particle density in kg/m³ (default: 1000 = water density)
    henry_constant : float
        Henry's law constant for gaseous species (dimensionless, default: 0.0)
        Set to 0.0 for particulate matter, > 0 for soluble gases
    """

    def __init__(
        self,
        config: SimulationConfig,
        particle_diameter: float = 1e-6,
        particle_density: float = 1000.0,
        henry_constant: float = 0.0,
    ) -> None:
        self.config = config
        self.particle_diameter = particle_diameter
        self.particle_density = particle_density
        self.henry_constant = henry_constant
        
        # Pre-calculate settling velocity (constant for given particle properties)
        self.v_settling = self.gravitational_settling(
            particle_diameter, particle_density
        )

    # ------------------------------------------------------------------
    # Gravitational settling  (Req 8.1)
    # ------------------------------------------------------------------

    @staticmethod
    def gravitational_settling(
        diameter: float,
        density: float,
        mu: float = AIR_VISCOSITY,
        g: float = GRAVITY,
    ) -> float:
        """Stokes settling velocity: v_g = ρ·d²·g / (18·μ).

        Parameters
        ----------
        diameter : float
            Particle diameter (m).  Must be > 0.
        density : float
            Particle density (kg/m³).  Must be > 0.
        mu : float
            Dynamic viscosity of air (Pa·s).
        g : float
            Gravitational acceleration (m/s²).

        Returns
        -------
        float
            Terminal settling velocity (m/s), always ≥ 0.
        """
        return density * diameter ** 2 * g / (18.0 * mu)

    # ------------------------------------------------------------------
    # Dry deposition – 3-resistance model  (Req 8.2)
    # ------------------------------------------------------------------

    @staticmethod
    def dry_deposition_velocity(
        r_a: float,
        r_b: float,
        r_s: float,
        v_g: float,
    ) -> float:
        """Three-resistance dry deposition velocity.

        v_d = 1 / (r_a + r_b + r_s) + v_g

        Parameters
        ----------
        r_a : float
            Aerodynamic resistance (s/m).  Must be > 0.
        r_b : float
            Quasi-laminar sub-layer resistance (s/m).  Must be > 0.
        r_s : float
            Surface resistance (s/m).  Must be > 0.
        v_g : float
            Gravitational settling velocity (m/s).  Must be ≥ 0.

        Returns
        -------
        float
            Dry deposition velocity (m/s), always ≥ v_g.
        """
        return 1.0 / (r_a + r_b + r_s) + v_g

    # ------------------------------------------------------------------
    # Wet deposition – below-cloud scavenging  (Req 8.3)
    # ------------------------------------------------------------------

    @staticmethod
    def below_cloud_scavenging(
        precip_rate: float,
        a: float = 5e-5,
        b: float = 0.8,
    ) -> float:
        """Below-cloud scavenging coefficient: Λ = a·P^b.

        Parameters
        ----------
        precip_rate : float
            Precipitation rate (mm/h).
        a : float
            Scavenging coefficient constant.
        b : float
            Scavenging exponent.

        Returns
        -------
        float
            Scavenging coefficient (s⁻¹).  Returns 0 when precip_rate ≤ 0.
        """
        if precip_rate <= 0.0:
            return 0.0
        return a * precip_rate ** b

    # ------------------------------------------------------------------
    # In-cloud scavenging  (Req 8.4)
    # ------------------------------------------------------------------

    @staticmethod
    def in_cloud_scavenging(
        precip_rate: float,
        cloud_base: float,
        cloud_top: float,
        z: float,
        ratio: float = 3.0e-5,
    ) -> float:
        """In-cloud scavenging coefficient.

        Applied only when the particle is between cloud base and cloud top.

        Parameters
        ----------
        precip_rate : float
            Precipitation rate (mm/h).
        cloud_base : float
            Cloud base height (m).
        cloud_top : float
            Cloud top height (m).
        z : float
            Particle altitude (m).
        ratio : float
            In-cloud scavenging ratio (s⁻¹ per mm/h).

        Returns
        -------
        float
            In-cloud scavenging coefficient (s⁻¹).
        """
        if precip_rate <= 0.0:
            return 0.0
        if z < cloud_base or z > cloud_top:
            return 0.0
        return ratio * precip_rate

    # ------------------------------------------------------------------
    # Mass decay  (Req 8.5, 8.6)
    # ------------------------------------------------------------------

    @staticmethod
    def apply_deposition(
        mass: float,
        v_d: float,
        dz: float,
        scav_coeff: float,
        dt: float,
    ) -> float:
        """Apply deposition mass decay.

        m(t+dt) = m(t) · exp(-(v_d/Δz + Λ) · |Δt|)

        Parameters
        ----------
        mass : float
            Current particle mass (kg).  Must be > 0.
        v_d : float
            Dry deposition velocity (m/s).  Must be ≥ 0.
        dz : float
            Layer thickness (m).  Clamped to ≥ 1.0 to avoid division by zero.
        scav_coeff : float
            Scavenging coefficient (s⁻¹).  Must be ≥ 0.
        dt : float
            Time step (s).

        Returns
        -------
        float
            Updated mass (kg).  Always 0 < result ≤ mass.
        """
        decay_rate = v_d / max(dz, 1.0) + scav_coeff
        result = mass * math.exp(-decay_rate * abs(dt))
        # Guard against IEEE 754 underflow to exactly 0.0.
        # The spec requires 0 < m(t+Δt); actual particle removal is handled
        # by the depletion threshold (Req 8.6: mass < 1% of initial).
        if result <= 0.0:
            import sys
            result = sys.float_info.min
        return result

    # ------------------------------------------------------------------
    # Gaseous dry deposition via Henry's law  (Req 8.7)
    # ------------------------------------------------------------------

    @staticmethod
    def gaseous_dry_deposition_velocity(
        henry_const: float,
        r_a: float,
        r_b: float,
    ) -> float:
        """Dry deposition velocity for gaseous species using Henry's law.

        For highly soluble gases (large H), surface resistance → 0.
        v_d = 1 / (r_a + r_b + r_s), where r_s ∝ 1/H.

        Parameters
        ----------
        henry_const : float
            Dimensionless Henry's law constant (higher = more soluble).
        r_a : float
            Aerodynamic resistance (s/m).
        r_b : float
            Quasi-laminar sub-layer resistance (s/m).

        Returns
        -------
        float
            Gaseous dry deposition velocity (m/s).
        """
        # Surface resistance inversely proportional to Henry's law constant
        r_s = 1.0 / max(henry_const, 1e-30)
        return 1.0 / (r_a + r_b + r_s)


    # ------------------------------------------------------------------
    # High-level deposition application  (Req 8.8)
    # ------------------------------------------------------------------

    def apply_deposition_step(
        self,
        mass: float,
        z: float,
        precip_rate: float,
        cloud_base: float,
        cloud_top: float,
        ustar: float,
        dt: float,
        is_gaseous: bool = False,
    ) -> tuple[float, float]:
        """Apply all deposition processes for a single time step.
        
        This is the main interface for applying deposition to a particle.
        It combines dry deposition, wet deposition, and gravitational settling.
        
        Parameters
        ----------
        mass : float
            Current particle mass (kg)
        z : float
            Particle height (m AGL)
        precip_rate : float
            Precipitation rate (mm/h)
        cloud_base : float
            Cloud base height (m)
        cloud_top : float
            Cloud top height (m)
        ustar : float
            Friction velocity (m/s)
        dt : float
            Time step (s)
        is_gaseous : bool
            Whether the species is gaseous (uses Henry's law)
        
        Returns
        -------
        tuple[float, float]
            (new_mass, vertical_displacement)
            - new_mass: Updated mass after deposition (kg)
            - vertical_displacement: Vertical displacement due to settling (m)
        """
        if not self.config.dry_deposition and not self.config.wet_deposition:
            # No deposition enabled
            return mass, 0.0
        
        # Calculate dry deposition velocity
        if self.config.dry_deposition:
            if is_gaseous and self.henry_constant > 0:
                # Gaseous species
                r_a = self._aerodynamic_resistance(z, ustar)
                r_b = self._quasi_laminar_resistance(ustar)
                v_d = self.gaseous_dry_deposition_velocity(
                    self.henry_constant, r_a, r_b
                )
            else:
                # Particulate matter
                r_a = self._aerodynamic_resistance(z, ustar)
                r_b = self._quasi_laminar_resistance(ustar)
                r_s = self._surface_resistance()
                v_d = self.dry_deposition_velocity(r_a, r_b, r_s, self.v_settling)
        else:
            v_d = 0.0
        
        # Calculate wet deposition scavenging coefficient
        if self.config.wet_deposition:
            # Below-cloud scavenging
            lambda_below = self.below_cloud_scavenging(precip_rate)
            
            # In-cloud scavenging
            lambda_in = self.in_cloud_scavenging(
                precip_rate, cloud_base, cloud_top, z
            )
            
            # Total scavenging coefficient
            scav_coeff = lambda_below + lambda_in
        else:
            scav_coeff = 0.0
        
        # Apply deposition mass decay
        layer_thickness = max(z, 10.0)  # Minimum 10m layer
        new_mass = self.apply_deposition(
            mass, v_d, layer_thickness, scav_coeff, dt
        )
        
        # Calculate vertical displacement due to gravitational settling
        # (only for particulate matter, not gases)
        if not is_gaseous and self.v_settling > 0:
            vertical_displacement = -self.v_settling * dt  # Negative = downward
        else:
            vertical_displacement = 0.0
        
        return new_mass, vertical_displacement
    
    def _aerodynamic_resistance(self, z: float, ustar: float) -> float:
        """Calculate aerodynamic resistance.
        
        r_a = ln(z/z0) / (κ * u*)
        
        where κ = 0.4 (von Karman constant), z0 = roughness length
        
        Parameters
        ----------
        z : float
            Height above ground (m)
        ustar : float
            Friction velocity (m/s)
        
        Returns
        -------
        float
            Aerodynamic resistance (s/m)
        """
        kappa = 0.4  # von Karman constant
        z0 = 0.1  # Roughness length (m), typical for grassland
        
        if ustar < 0.01:
            ustar = 0.01  # Minimum to avoid division by zero
        
        if z <= z0:
            z = z0 + 1.0  # Ensure z > z0
        
        return np.log(z / z0) / (kappa * ustar)
    
    def _quasi_laminar_resistance(self, ustar: float) -> float:
        """Calculate quasi-laminar sub-layer resistance.
        
        r_b = 2 / (κ * u*)
        
        Parameters
        ----------
        ustar : float
            Friction velocity (m/s)
        
        Returns
        -------
        float
            Quasi-laminar resistance (s/m)
        """
        kappa = 0.4
        
        if ustar < 0.01:
            ustar = 0.01
        
        return 2.0 / (kappa * ustar)
    
    def _surface_resistance(self) -> float:
        """Calculate surface resistance.
        
        Surface resistance depends on surface type and particle properties.
        For simplicity, we use a typical value for vegetated surfaces.
        
        Returns
        -------
        float
            Surface resistance (s/m)
        """
        # Typical value for vegetated surface
        # Can be parameterized based on land use type in future
        return 100.0  # s/m
    
    def get_depletion_threshold(self, initial_mass: float) -> float:
        """Get mass depletion threshold (1% of initial mass).
        
        When particle mass drops below this threshold, it should be
        removed from the simulation (Req 8.6).
        
        Parameters
        ----------
        initial_mass : float
            Initial particle mass (kg)
        
        Returns
        -------
        float
            Depletion threshold (kg)
        """
        return 0.01 * initial_mass
