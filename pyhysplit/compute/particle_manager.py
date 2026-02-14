"""Particle Manager for multi-particle tracking in pyhysplit.

Handles particle initialization, continuous emission, deactivation,
and trajectory recording using vectorized NumPy operations.

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from pyhysplit.core.models import ParticleState, SimulationConfig, StartLocation


class ParticleManager:
    """Manages the lifecycle of Lagrangian particles.

    Supports multi-source initialization, continuous emission,
    deactivation by boundary/mass/age, and trajectory recording.
    All particle state is stored in structured NumPy arrays for
    vectorized operations.

    Parameters
    ----------
    config : SimulationConfig
        Simulation configuration (contains start locations, particle counts, etc.).
    """

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.state: Optional[ParticleState] = None
        self.trajectories: list[list[tuple]] = []
        self._initial_mass: Optional[np.ndarray] = None
        self._emission_interval: float = 0.0  # seconds between emissions
        self._last_emission_time: float = 0.0
        self._next_id: int = 0  # tracks next available particle slot

    # ------------------------------------------------------------------
    # Initialization (Req 10.1)
    # ------------------------------------------------------------------

    def initialize(
        self,
        start_locations: list[StartLocation],
        particles_per_source: int,
        species_ids: Optional[list[int]] = None,
        mass_per_particle: float = 1.0,
    ) -> None:
        """Create initial particles at the given start locations.

        Parameters
        ----------
        start_locations : list[StartLocation]
            Source positions.
        particles_per_source : int
            Number of particles released per source.
        species_ids : list[int] | None
            Species ID for each source (defaults to 0 for all).
        mass_per_particle : float
            Initial mass assigned to each particle (kg).
        """
        if species_ids is None:
            species_ids = [0] * len(start_locations)

        n = len(start_locations) * particles_per_source
        lons = np.empty(n, dtype=np.float64)
        lats = np.empty(n, dtype=np.float64)
        zs = np.empty(n, dtype=np.float64)
        masses = np.full(n, mass_per_particle, dtype=np.float64)
        ages = np.zeros(n, dtype=np.float64)
        active = np.ones(n, dtype=bool)
        sids = np.empty(n, dtype=np.int32)

        idx = 0
        for i, loc in enumerate(start_locations):
            for _ in range(particles_per_source):
                lons[idx] = loc.lon
                lats[idx] = loc.lat
                zs[idx] = loc.height
                sids[idx] = species_ids[i]
                idx += 1

        self.state = ParticleState(
            lon=lons, lat=lats, z=zs,
            mass=masses, age=ages, active=active,
            species_id=sids,
        )
        self._initial_mass = masses.copy()
        self._next_id = n
        # One trajectory record list per particle
        self.trajectories = [[] for _ in range(n)]

    # ------------------------------------------------------------------
    # Continuous Emission (Req 10.4)
    # ------------------------------------------------------------------

    def set_emission_interval(self, interval_s: float) -> None:
        """Set the time interval (seconds) between continuous emissions."""
        self._emission_interval = interval_s

    def emit(self, t: float, start_locations: list[StartLocation],
             particles_per_source: int = 1,
             species_ids: Optional[list[int]] = None,
             mass_per_particle: float = 1.0) -> None:
        """Emit new particles if the emission interval has elapsed.

        Parameters
        ----------
        t : float
            Current simulation time (seconds).
        start_locations : list[StartLocation]
            Source positions for new particles.
        particles_per_source : int
            Particles per source in this emission.
        species_ids : list[int] | None
            Species ID per source.
        mass_per_particle : float
            Mass for each new particle.
        """
        if self._emission_interval <= 0:
            return
        if abs(t - self._last_emission_time) < self._emission_interval:
            return

        if species_ids is None:
            species_ids = [0] * len(start_locations)

        n_new = len(start_locations) * particles_per_source
        new_lons = np.empty(n_new, dtype=np.float64)
        new_lats = np.empty(n_new, dtype=np.float64)
        new_zs = np.empty(n_new, dtype=np.float64)
        new_masses = np.full(n_new, mass_per_particle, dtype=np.float64)
        new_ages = np.zeros(n_new, dtype=np.float64)
        new_active = np.ones(n_new, dtype=bool)
        new_sids = np.empty(n_new, dtype=np.int32)

        idx = 0
        for i, loc in enumerate(start_locations):
            for _ in range(particles_per_source):
                new_lons[idx] = loc.lon
                new_lats[idx] = loc.lat
                new_zs[idx] = loc.height
                new_sids[idx] = species_ids[i]
                idx += 1

        if self.state is None:
            self.state = ParticleState(
                lon=new_lons, lat=new_lats, z=new_zs,
                mass=new_masses, age=new_ages, active=new_active,
                species_id=new_sids,
            )
            self._initial_mass = new_masses.copy()
        else:
            self.state = ParticleState(
                lon=np.concatenate([self.state.lon, new_lons]),
                lat=np.concatenate([self.state.lat, new_lats]),
                z=np.concatenate([self.state.z, new_zs]),
                mass=np.concatenate([self.state.mass, new_masses]),
                age=np.concatenate([self.state.age, new_ages]),
                active=np.concatenate([self.state.active, new_active]),
                species_id=np.concatenate([self.state.species_id, new_sids]),
            )
            self._initial_mass = np.concatenate([self._initial_mass, new_masses])

        # Extend trajectory records for new particles
        self.trajectories.extend([] for _ in range(n_new))
        self._next_id += n_new
        self._last_emission_time = t

    # ------------------------------------------------------------------
    # Deactivation (Req 10.3)
    # ------------------------------------------------------------------

    def deactivate(self, mask: np.ndarray) -> None:
        """Deactivate particles indicated by a boolean mask.

        Parameters
        ----------
        mask : np.ndarray
            Boolean array of shape (N,). True = deactivate.
        """
        if self.state is not None:
            self.state.active[mask] = False

    def deactivate_by_mass(self, threshold_fraction: float = 0.01) -> None:
        """Deactivate particles whose mass has fallen below *threshold_fraction*
        of their initial mass (Req 10.3)."""
        if self.state is None or self._initial_mass is None:
            return
        depleted = (
            self.state.active
            & (self.state.mass < threshold_fraction * self._initial_mass)
        )
        self.state.active[depleted] = False

    def deactivate_by_age(self, max_age_s: float) -> None:
        """Deactivate particles older than *max_age_s* seconds (Req 10.3)."""
        if self.state is None:
            return
        old = self.state.active & (self.state.age > max_age_s)
        self.state.active[old] = False

    # ------------------------------------------------------------------
    # State update helpers (Req 10.2)
    # ------------------------------------------------------------------

    def update_positions(self, lon: np.ndarray, lat: np.ndarray,
                         z: np.ndarray) -> None:
        """Overwrite positions for all particles (active mask applied externally)."""
        if self.state is None:
            return
        self.state.lon[:] = lon
        self.state.lat[:] = lat
        self.state.z[:] = z

    def advance_age(self, dt: float) -> None:
        """Increment the age of all active particles by *dt* seconds."""
        if self.state is None:
            return
        self.state.age[self.state.active] += abs(dt)

    # ------------------------------------------------------------------
    # Trajectory recording (Req 10.2)
    # ------------------------------------------------------------------

    def record_positions(self, t: float) -> None:
        """Append current positions of active particles to trajectory history."""
        if self.state is None:
            return
        for i in range(len(self.state.lon)):
            if self.state.active[i]:
                self.trajectories[i].append((
                    t,
                    float(self.state.lon[i]),
                    float(self.state.lat[i]),
                    float(self.state.z[i]),
                ))

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    @property
    def num_particles(self) -> int:
        """Total number of particles (active + inactive)."""
        if self.state is None:
            return 0
        return len(self.state.lon)

    @property
    def num_active(self) -> int:
        """Number of currently active particles."""
        if self.state is None:
            return 0
        return int(np.sum(self.state.active))

    def get_active_indices(self) -> np.ndarray:
        """Return indices of active particles."""
        if self.state is None:
            return np.array([], dtype=np.intp)
        return np.where(self.state.active)[0]
