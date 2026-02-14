"""Concentration Grid for 3-D pollutant concentration calculation.

Maps Lagrangian particle positions/masses onto an Eulerian grid and
computes time-averaged concentrations.  Supports multiple species with
independent grids and a 2-D surface deposition grid.

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from pyhysplit.core.models import ConcentrationGridConfig, ParticleState


class ConcentrationGrid:
    """3-D concentration grid with multi-species support.

    Parameters
    ----------
    grid_config : ConcentrationGridConfig
        Grid geometry and averaging parameters.
    num_species : int
        Number of independent pollutant species (default 1).
    """

    def __init__(self, grid_config: ConcentrationGridConfig,
                 num_species: int = 1):
        self.config = grid_config
        self.num_species = num_species

        # Build grid edges
        self.lon_edges: np.ndarray = np.array([])
        self.lat_edges: np.ndarray = np.array([])
        self.z_edges: np.ndarray = np.array([])
        self.nx: int = 0
        self.ny: int = 0
        self.nz: int = 0

        # Per-species grids: dict[species_id -> (nz, ny, nx)]
        self.grids: dict[int, np.ndarray] = {}
        # Per-species 2-D deposition grids: dict[species_id -> (ny, nx)]
        self.deposition_grids: dict[int, np.ndarray] = {}

        # Accumulation counter for time averaging
        self._accumulation_count: int = 0

        self._setup_grid()
        self._init_species_grids()

    # ------------------------------------------------------------------
    # Grid setup (Req 9.1)
    # ------------------------------------------------------------------

    def _setup_grid(self) -> None:
        """Create grid edges from the configuration."""
        cfg = self.config

        half_span_lon = cfg.span_lon / 2.0
        half_span_lat = cfg.span_lat / 2.0

        lon_min = cfg.center_lon - half_span_lon
        lon_max = cfg.center_lon + half_span_lon
        lat_min = cfg.center_lat - half_span_lat
        lat_max = cfg.center_lat + half_span_lat

        self.nx = max(1, int(round(cfg.span_lon / cfg.spacing_lon)))
        self.ny = max(1, int(round(cfg.span_lat / cfg.spacing_lat)))

        self.lon_edges = np.linspace(lon_min, lon_max, self.nx + 1)
        self.lat_edges = np.linspace(lat_min, lat_max, self.ny + 1)

        # Vertical edges from levels list
        levels = sorted(cfg.levels)
        if len(levels) == 0:
            levels = [0.0, 10000.0]
        if levels[0] > 0:
            levels = [0.0] + levels
        self.z_edges = np.array(levels, dtype=np.float64)
        self.nz = len(self.z_edges) - 1

    def _init_species_grids(self) -> None:
        """Allocate zero grids for each species."""
        for sid in range(self.num_species):
            self.grids[sid] = np.zeros(
                (self.nz, self.ny, self.nx), dtype=np.float64)
            self.deposition_grids[sid] = np.zeros(
                (self.ny, self.nx), dtype=np.float64)

    # ------------------------------------------------------------------
    # Cell volume computation
    # ------------------------------------------------------------------

    def cell_volumes(self) -> np.ndarray:
        """Return cell volumes in m³ as array of shape (nz, ny, nx).

        Horizontal area is approximated using the latitude-dependent
        metric: dx = Δlon·R·cos(lat), dy = Δlat·R.
        """
        R = 6_371_000.0  # Earth radius (m)

        # Horizontal cell sizes (m) — vary with latitude
        dlon_rad = np.deg2rad(np.diff(self.lon_edges))  # (nx,)
        dlat_rad = np.deg2rad(np.diff(self.lat_edges))  # (ny,)
        lat_centers = 0.5 * (self.lat_edges[:-1] + self.lat_edges[1:])
        cos_lat = np.cos(np.deg2rad(lat_centers))  # (ny,)

        dx = dlon_rad[np.newaxis, :] * R * cos_lat[:, np.newaxis]  # (ny, nx)
        dy = dlat_rad[:, np.newaxis] * R * np.ones(self.nx)  # (ny, nx)
        area = dx * dy  # (ny, nx)

        dz = np.diff(self.z_edges)  # (nz,)
        # Broadcast to (nz, ny, nx)
        volumes = dz[:, np.newaxis, np.newaxis] * area[np.newaxis, :, :]
        return volumes

    # ------------------------------------------------------------------
    # Accumulation (Req 9.2)
    # ------------------------------------------------------------------

    def accumulate(self, particles: ParticleState) -> None:
        """Bin active particle masses into the 3-D grid.

        C_cell = Σ m_i / V_cell  for particles falling in that cell.
        Each species is accumulated independently (Req 9.5).
        """
        if particles is None:
            return

        active = particles.active
        if not np.any(active):
            return

        lons = particles.lon[active]
        lats = particles.lat[active]
        zs = particles.z[active]
        masses = particles.mass[active]
        sids = particles.species_id[active]

        volumes = self.cell_volumes()

        # Digitize positions into grid bins
        ix = np.searchsorted(self.lon_edges, lons, side="right") - 1
        iy = np.searchsorted(self.lat_edges, lats, side="right") - 1
        iz = np.searchsorted(self.z_edges, zs, side="right") - 1

        # Clamp to valid range
        ix = np.clip(ix, 0, self.nx - 1)
        iy = np.clip(iy, 0, self.ny - 1)
        iz = np.clip(iz, 0, self.nz - 1)

        for sid in range(self.num_species):
            mask = sids == sid
            if not np.any(mask):
                continue
            # Use np.add.at for unbuffered accumulation
            np.add.at(
                self.grids[sid],
                (iz[mask], iy[mask], ix[mask]),
                masses[mask] / volumes[iz[mask], iy[mask], ix[mask]],
            )

        self._accumulation_count += 1

    # ------------------------------------------------------------------
    # Deposition grid (Req 9.6)
    # ------------------------------------------------------------------

    def accumulate_deposition(self, particles: ParticleState,
                              deposited_mass: np.ndarray) -> None:
        """Add deposited mass to the 2-D deposition grid.

        Parameters
        ----------
        particles : ParticleState
            Full particle state (positions used for binning).
        deposited_mass : np.ndarray
            Mass deposited per particle in this time step (shape (N,)).
        """
        if particles is None:
            return

        lons = particles.lon
        lats = particles.lat
        sids = particles.species_id

        ix = np.searchsorted(self.lon_edges, lons, side="right") - 1
        iy = np.searchsorted(self.lat_edges, lats, side="right") - 1
        ix = np.clip(ix, 0, self.nx - 1)
        iy = np.clip(iy, 0, self.ny - 1)

        for sid in range(self.num_species):
            mask = sids == sid
            if not np.any(mask):
                continue
            np.add.at(
                self.deposition_grids[sid],
                (iy[mask], ix[mask]),
                deposited_mass[mask],
            )

    # ------------------------------------------------------------------
    # Time averaging (Req 9.3)
    # ------------------------------------------------------------------

    def get_average(self) -> dict[int, np.ndarray]:
        """Return time-averaged concentration grids per species.

        Returns
        -------
        dict[int, np.ndarray]
            species_id → averaged (nz, ny, nx) array.
        """
        count = max(self._accumulation_count, 1)
        return {sid: grid / count for sid, grid in self.grids.items()}

    # ------------------------------------------------------------------
    # Reset (after averaging period)
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Zero out concentration grids for the next averaging period."""
        for sid in self.grids:
            self.grids[sid][:] = 0.0
        self._accumulation_count = 0

    def reset_deposition(self) -> None:
        """Zero out deposition grids."""
        for sid in self.deposition_grids:
            self.deposition_grids[sid][:] = 0.0

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def total_grid_mass(self, species_id: int = 0) -> float:
        """Return Σ(C·V) for a given species — should equal Σm_active."""
        volumes = self.cell_volumes()
        return float(np.sum(self.grids[species_id] * volumes))
