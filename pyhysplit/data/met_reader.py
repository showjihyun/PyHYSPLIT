"""Meteorological data readers for pyhysplit.

Provides readers for ARL packed binary, NetCDF (GDAS/GFS), ERA5, and WRF
formats, plus utility functions for omega-to-w conversion and multi-file
concatenation.

References:
    - Draxler, R.R. (1999) "HYSPLIT-4 User's Guide", NOAA Technical Memorandum
    - Stein, A.F. et al. (2015) BAMS, DOI: 10.1175/BAMS-D-14-00110.1
"""

from __future__ import annotations

import logging
import struct
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np

from pyhysplit.core.models import MetData, MetFileNotFoundError, MetFormatError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------
RD = 287.05       # Specific gas constant for dry air (J/(kg·K))
GRAVITY = 9.80665  # Standard gravitational acceleration (m/s²)

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def convert_omega_to_w(
    omega: np.ndarray,
    T: np.ndarray,
    P: np.ndarray,
    Rd: float = RD,
    g: float = GRAVITY,
) -> np.ndarray:
    """Convert vertical velocity from Pa/s to m/s.

    Uses the hydrostatic approximation:
        w = -omega * Rd * T / (g * P)

    Parameters
    ----------
    omega : ndarray
        Vertical velocity in Pa/s (positive = downward).
    T : ndarray
        Temperature in Kelvin.
    P : ndarray
        Pressure in Pa (must be > 0).
    Rd : float
        Specific gas constant for dry air (J/(kg·K)).
    g : float
        Gravitational acceleration (m/s²).

    Returns
    -------
    ndarray
        Vertical velocity in m/s (positive = upward).
    """
    return -omega * Rd * T / (g * P)


def concatenate_met_files(
    readers: list[MetReaderBase],
    filepaths: list[str],
) -> MetData:
    """Concatenate multiple meteorological files in time order.

    Each reader/filepath pair is read independently, then the resulting
    MetData objects are merged along the time axis.  The output ``t_grid``
    is guaranteed to be strictly monotonically increasing; duplicate time
    steps at file boundaries are removed.

    Parameters
    ----------
    readers : list[MetReaderBase]
        One reader per file (may all be the same instance).
    filepaths : list[str]
        Paths to the meteorological files, in chronological order.

    Returns
    -------
    MetData
        Merged meteorological dataset.

    Raises
    ------
    ValueError
        If the spatial grids of the files are incompatible.
    MetFileNotFoundError
        If any file does not exist.
    """
    if len(readers) != len(filepaths):
        raise ValueError("readers and filepaths must have the same length")
    if not readers:
        raise ValueError("At least one reader/filepath pair is required")

    datasets: list[MetData] = []
    for reader, fp in zip(readers, filepaths):
        datasets.append(reader.read(fp))

    if len(datasets) == 1:
        return datasets[0]

    # Validate spatial grid compatibility
    ref = datasets[0]
    for i, ds in enumerate(datasets[1:], start=1):
        if not np.array_equal(ref.lon_grid, ds.lon_grid):
            raise ValueError(
                f"lon_grid mismatch between file 0 and file {i}"
            )
        if not np.array_equal(ref.lat_grid, ds.lat_grid):
            raise ValueError(
                f"lat_grid mismatch between file 0 and file {i}"
            )
        if not np.array_equal(ref.z_grid, ds.z_grid):
            raise ValueError(
                f"z_grid mismatch between file 0 and file {i}"
            )

    # Concatenate along time axis, removing duplicate boundary times
    all_t = []
    all_u = []
    all_v = []
    all_w = []
    all_t_field = []
    all_rh = []
    all_hgt = []
    all_precip = []
    all_pbl = []

    seen_times: set[float] = set()

    for ds in datasets:
        mask = np.array([t not in seen_times for t in ds.t_grid])
        if not np.any(mask):
            continue

        indices = np.where(mask)[0]
        all_t.append(ds.t_grid[indices])
        all_u.append(ds.u[indices])
        all_v.append(ds.v[indices])
        all_w.append(ds.w[indices])

        if ds.t_field is not None:
            all_t_field.append(ds.t_field[indices])
        if ds.rh is not None:
            all_rh.append(ds.rh[indices])
        if ds.hgt is not None:
            all_hgt.append(ds.hgt[indices])
        if ds.precip is not None:
            all_precip.append(ds.precip[indices])
        if ds.pbl_height is not None:
            all_pbl.append(ds.pbl_height[indices])

        seen_times.update(ds.t_grid[indices].tolist())

    merged_t = np.concatenate(all_t)
    sort_idx = np.argsort(merged_t)
    merged_t = merged_t[sort_idx]

    def _sort_concat(arrays: list[np.ndarray]) -> np.ndarray | None:
        if not arrays:
            return None
        return np.concatenate(arrays)[sort_idx]

    return MetData(
        u=np.concatenate(all_u)[sort_idx],
        v=np.concatenate(all_v)[sort_idx],
        w=np.concatenate(all_w)[sort_idx],
        t_field=_sort_concat(all_t_field),
        rh=_sort_concat(all_rh),
        hgt=_sort_concat(all_hgt),
        precip=_sort_concat(all_precip),
        pbl_height=_sort_concat(all_pbl),
        terrain=ref.terrain,
        lon_grid=ref.lon_grid,
        lat_grid=ref.lat_grid,
        z_grid=ref.z_grid,
        t_grid=merged_t,
        z_type=ref.z_type,
        source=ref.source,
    )


# ---------------------------------------------------------------------------
# Abstract base reader
# ---------------------------------------------------------------------------


class MetReaderBase(ABC):
    """Abstract base class for meteorological data readers."""

    @abstractmethod
    def read(self, filepath: str) -> MetData:
        """Read a meteorological data file and return a MetData object.

        Parameters
        ----------
        filepath : str
            Path to the meteorological data file.

        Returns
        -------
        MetData
            Parsed meteorological data.
        """

    @abstractmethod
    def get_variable_mapping(self) -> dict[str, str]:
        """Return a mapping from internal variable names to file variable names.

        Returns
        -------
        dict[str, str]
            Keys are internal names (u, v, w, t_field, rh, hgt, precip,
            pbl_height, terrain), values are the names used in the file format.
        """


# ---------------------------------------------------------------------------
# ARL Reader
# ---------------------------------------------------------------------------


class ARLReader(MetReaderBase):
    """Reader for NOAA ARL packed binary meteorological data.

    The ARL format consists of index records followed by level-by-level
    variable data.  Each record starts with a 50-byte ASCII header
    containing metadata (year, month, day, hour, forecast hour, level,
    grid number, variable name, exponent, precision, and initial value).

    Reference: Draxler (1999) HYSPLIT-4 User's Guide, Chapter 5.
    """

    HEADER_SIZE = 50  # bytes per record header

    # Variable mapping: internal name → ARL variable name
    _VAR_MAP: dict[str, str] = {
        "u": "UWND",
        "v": "VWND",
        "w": "WWND",
        "t_field": "TEMP",
        "rh": "RELH",
        "hgt": "HGTS",
        "precip": "TPP6",
        "pbl_height": "PBLH",
        "terrain": "SHGT",
    }

    def get_variable_mapping(self) -> dict[str, str]:
        return dict(self._VAR_MAP)

    def read(self, filepath: str) -> MetData:
        """Read an ARL packed binary file.

        Parameters
        ----------
        filepath : str
            Path to the ARL file.

        Returns
        -------
        MetData
            Parsed meteorological data.

        Raises
        ------
        MetFileNotFoundError
            If the file does not exist.
        MetFormatError
            If the file header is corrupted or unreadable.
        """
        path = Path(filepath)
        if not path.exists():
            raise MetFileNotFoundError(f"ARL file not found: {filepath}")

        with open(path, "rb") as f:
            data = f.read()

        if len(data) < self.HEADER_SIZE:
            raise MetFormatError(
                f"ARL file too small ({len(data)} bytes): {filepath}"
            )

        try:
            index = self._parse_index_record(data[:self.HEADER_SIZE])
        except Exception as exc:
            raise MetFormatError(
                f"Failed to parse ARL index record: {exc}"
            ) from exc

        nx = index.get("nx", 0)
        ny = index.get("ny", 0)
        nz = index.get("nz", 1)
        nt = index.get("nt", 1)

        if nx <= 0 or ny <= 0:
            raise MetFormatError(
                f"Invalid grid dimensions nx={nx}, ny={ny} in {filepath}"
            )

        # Build grids from index metadata
        lon0 = index.get("lon0", 0.0)
        lat0 = index.get("lat0", 0.0)
        dlon = index.get("dlon", 1.0)
        dlat = index.get("dlat", 1.0)
        lon_grid = np.array([lon0 + i * dlon for i in range(nx)], dtype=np.float64)
        lat_grid = np.array([lat0 + j * dlat for j in range(ny)], dtype=np.float64)

        # Vertical levels (pressure in hPa or height in m)
        levels = index.get("levels", [1000.0])
        z_grid = np.array(levels, dtype=np.float64)

        # Time grid
        t0 = index.get("t0", 0.0)
        dt_met = index.get("dt_met", 10800.0)  # default 3h
        t_grid = np.array([t0 + i * dt_met for i in range(nt)], dtype=np.float64)

        # Unpack variable data
        record_size = nx * ny
        header_offset = self.HEADER_SIZE
        variables: dict[str, np.ndarray] = {}

        for var_name in ["u", "v", "w", "t_field", "rh", "hgt"]:
            arl_name = self._VAR_MAP.get(var_name)
            if arl_name is None:
                continue
            arr = np.zeros((nt, nz, ny, nx), dtype=np.float64)
            variables[var_name] = arr

        # Parse data records
        offset = header_offset
        for it in range(nt):
            for iz in range(nz):
                for var_name, arl_name in self._VAR_MAP.items():
                    if var_name in ("precip", "pbl_height", "terrain"):
                        continue  # surface variables handled separately
                    if var_name not in variables:
                        continue

                    if offset + self.HEADER_SIZE + record_size > len(data):
                        # Pad with zeros if data is truncated
                        logger.warning(
                            "ARL data truncated at t=%d, z=%d, var=%s",
                            it, iz, var_name,
                        )
                        break

                    rec_header = data[offset:offset + self.HEADER_SIZE]
                    offset += self.HEADER_SIZE

                    unpacked = self._unpack_level_data(
                        data[offset:offset + record_size], nx, ny,
                        rec_header,
                    )
                    variables[var_name][it, iz, :, :] = unpacked
                    offset += record_size

        # Surface variables (2D)
        terrain = np.zeros((ny, nx), dtype=np.float64)
        precip = np.zeros((nt, ny, nx), dtype=np.float64)
        pbl_height = np.zeros((nt, ny, nx), dtype=np.float64)

        return MetData(
            u=variables.get("u", np.zeros((nt, nz, ny, nx))),
            v=variables.get("v", np.zeros((nt, nz, ny, nx))),
            w=variables.get("w", np.zeros((nt, nz, ny, nx))),
            t_field=variables.get("t_field"),
            rh=variables.get("rh"),
            hgt=variables.get("hgt"),
            precip=precip,
            pbl_height=pbl_height,
            terrain=terrain,
            lon_grid=lon_grid,
            lat_grid=lat_grid,
            z_grid=z_grid,
            t_grid=t_grid,
            z_type="pressure",
            source="ARL",
        )

    def _parse_index_record(self, header_bytes: bytes) -> dict[str, Any]:
        """Parse a 50-byte ARL index record header.

        The header is ASCII-encoded with fixed-width fields:
            Bytes  0-3  : year (2-digit) and month (2-digit)
            Bytes  4-7  : day (2-digit) and hour (2-digit)
            Bytes  8-11 : forecast hour (4-digit)
            Bytes 12-13 : level index (2-digit)
            Bytes 14    : grid number (1-digit)
            Bytes 15-18 : variable name (4 chars)
            Bytes 19-22 : exponent (4-digit)
            Bytes 23-36 : precision / scaling (14 chars)
            Bytes 37-49 : initial value / grid info (13 chars)

        Parameters
        ----------
        header_bytes : bytes
            Exactly 50 bytes of header data.

        Returns
        -------
        dict
            Parsed header fields including grid dimensions and metadata.
        """
        if len(header_bytes) < self.HEADER_SIZE:
            raise MetFormatError(
                f"Header too short: {len(header_bytes)} < {self.HEADER_SIZE}"
            )

        header_str = header_bytes.decode("ascii", errors="replace")

        result: dict[str, Any] = {}
        try:
            result["year"] = int(header_str[0:2].strip() or "0")
            result["month"] = int(header_str[2:4].strip() or "0")
            result["day"] = int(header_str[4:6].strip() or "0")
            result["hour"] = int(header_str[6:8].strip() or "0")
            result["forecast_hour"] = int(header_str[8:12].strip() or "0")
            result["level"] = int(header_str[12:14].strip() or "0")
            result["grid_num"] = int(header_str[14:15].strip() or "0")
            result["var_name"] = header_str[15:19].strip()
            result["exponent"] = int(header_str[19:23].strip() or "0")
        except (ValueError, IndexError) as exc:
            raise MetFormatError(f"Cannot parse ARL header fields: {exc}") from exc

        # Extract grid info from the remaining header portion
        # These are typically encoded in the first index record
        info_str = header_str[23:50]
        try:
            # Attempt to extract grid dimensions from info string
            # Format varies; use defaults if parsing fails
            parts = info_str.split()
            if len(parts) >= 6:
                result["nx"] = int(float(parts[0]))
                result["ny"] = int(float(parts[1]))
                result["nz"] = int(float(parts[2]))
                result["nt"] = int(float(parts[3]))
                result["lon0"] = float(parts[4])
                result["lat0"] = float(parts[5])
            if len(parts) >= 8:
                result["dlon"] = float(parts[6])
                result["dlat"] = float(parts[7])
            if len(parts) >= 9:
                result["dt_met"] = float(parts[8])
        except (ValueError, IndexError):
            logger.debug("Could not parse extended grid info from ARL header")

        # Defaults for missing grid info
        result.setdefault("nx", 360)
        result.setdefault("ny", 181)
        result.setdefault("nz", 23)
        result.setdefault("nt", 1)
        result.setdefault("lon0", -180.0)
        result.setdefault("lat0", -90.0)
        result.setdefault("dlon", 1.0)
        result.setdefault("dlat", 1.0)
        result.setdefault("dt_met", 10800.0)
        result.setdefault("t0", 0.0)
        result.setdefault("levels", [1000.0, 925.0, 850.0, 700.0, 500.0,
                                      400.0, 300.0, 250.0, 200.0, 150.0,
                                      100.0, 70.0, 50.0, 30.0, 20.0,
                                      10.0, 7.0, 5.0, 3.0, 2.0,
                                      1.0, 0.5, 0.2])

        return result

    def _unpack_level_data(
        self,
        data: bytes,
        nx: int,
        ny: int,
        header: bytes | None = None,
    ) -> np.ndarray:
        """Unpack a single level of ARL packed data.

        ARL data is packed as 1-byte differences from an initial value,
        scaled by a power-of-two exponent.  The formula is:
            value[i] = (byte[i] - 127) * 2^exponent + previous_value

        Parameters
        ----------
        data : bytes
            Raw packed data bytes (nx * ny bytes).
        nx, ny : int
            Grid dimensions.
        header : bytes, optional
            The 50-byte record header for extracting exponent and initial value.

        Returns
        -------
        ndarray
            Unpacked 2D array of shape (ny, nx).
        """
        expected_size = nx * ny
        if len(data) < expected_size:
            # Pad with zeros
            arr = np.zeros(expected_size, dtype=np.float64)
            raw = np.frombuffer(data, dtype=np.uint8)
            arr[:len(raw)] = raw.astype(np.float64)
        else:
            arr = np.frombuffer(data[:expected_size], dtype=np.uint8).astype(np.float64)

        # Extract scaling from header if available
        exponent = 0
        initial_value = 0.0
        if header is not None and len(header) >= self.HEADER_SIZE:
            try:
                header_str = header.decode("ascii", errors="replace")
                exponent = int(header_str[19:23].strip() or "0")
                # Initial value from precision field
                prec_str = header_str[23:37].strip()
                if prec_str:
                    initial_value = float(prec_str)
            except (ValueError, IndexError):
                pass

        # Unpack: value = (byte - 127) * 2^exponent + running_sum
        scale = 2.0 ** exponent
        differences = (arr - 127.0) * scale

        # Cumulative sum to reconstruct values
        values = np.empty_like(differences)
        values[0] = initial_value + differences[0]
        for i in range(1, len(values)):
            values[i] = values[i - 1] + differences[i]

        return values.reshape(ny, nx)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class MetReaderFactory:
    """Factory for creating meteorological data readers."""

    _REGISTRY: dict[str, type[MetReaderBase]] = {}

    @classmethod
    def register(cls, source_type: str, reader_class: type[MetReaderBase]) -> None:
        """Register a reader class for a given source type."""
        cls._REGISTRY[source_type.upper()] = reader_class

    @classmethod
    def create(cls, source_type: str) -> MetReaderBase:
        """Create a reader instance for the given source type.

        Parameters
        ----------
        source_type : str
            One of "ARL", "GDAS_NC", "GFS_NC", "ERA5", "WRF", "NAM".

        Returns
        -------
        MetReaderBase
            An instance of the appropriate reader.

        Raises
        ------
        ValueError
            If the source type is not supported.
        """
        key = source_type.upper()
        reader_cls = cls._REGISTRY.get(key)
        if reader_cls is None:
            supported = ", ".join(sorted(cls._REGISTRY.keys()))
            raise ValueError(
                f"Unsupported source type '{source_type}'. "
                f"Supported: {supported}"
            )
        return reader_cls()


# Register built-in readers
MetReaderFactory.register("ARL", ARLReader)


# ---------------------------------------------------------------------------
# NetCDF Reader (GDAS/GFS)
# ---------------------------------------------------------------------------


class NetCDFReader(MetReaderBase):
    """Reader for NetCDF format meteorological data (GDAS/GFS).

    Expects CF-convention compliant NetCDF files with standard variable
    names for GDAS or GFS reanalysis products.
    """

    _VAR_MAP: dict[str, str] = {
        "u": "UGRD",
        "v": "VGRD",
        "w": "VVEL",       # omega (Pa/s) — converted to m/s
        "t_field": "TMP",
        "rh": "RH",
        "hgt": "HGT",
        "precip": "APCP",
        "pbl_height": "HPBL",
        "terrain": "OROG",
    }

    def get_variable_mapping(self) -> dict[str, str]:
        return dict(self._VAR_MAP)

    def read(self, filepath: str) -> MetData:
        """Read a NetCDF GDAS/GFS file.

        Requires the ``netCDF4`` package (optional dependency).

        Parameters
        ----------
        filepath : str
            Path to the NetCDF file.

        Returns
        -------
        MetData
            Parsed meteorological data with omega converted to w (m/s).
        """
        path = Path(filepath)
        if not path.exists():
            raise MetFileNotFoundError(f"NetCDF file not found: {filepath}")

        try:
            import netCDF4 as nc  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "netCDF4 package is required for NetCDF reading. "
                "Install with: pip install netCDF4"
            ) from exc

        ds = nc.Dataset(str(path), "r")
        try:
            return self._extract(ds, filepath)
        finally:
            ds.close()

    def _extract(self, ds: Any, filepath: str) -> MetData:
        """Extract MetData from an open netCDF4 Dataset."""
        # Coordinate grids
        lon_grid = self._get_coord(ds, ["longitude", "lon", "x"])
        lat_grid = self._get_coord(ds, ["latitude", "lat", "y"])
        z_grid = self._get_coord(ds, ["level", "lev", "isobaricInhPa", "pressure"])
        t_grid = self._get_coord(ds, ["time", "t"])

        nx, ny, nz, nt = len(lon_grid), len(lat_grid), len(z_grid), len(t_grid)

        def _read_var(internal_name: str, shape_4d: bool = True) -> np.ndarray | None:
            nc_name = self._VAR_MAP.get(internal_name)
            
            # Try multiple names: mapped name, lowercase mapped name, internal name, lowercase internal name
            names_to_try = []
            if nc_name:
                names_to_try.extend([nc_name, nc_name.lower()])
            names_to_try.extend([internal_name, internal_name.lower()])
            
            for name in names_to_try:
                if name in ds.variables:
                    arr = np.array(ds.variables[name][:], dtype=np.float64)
                    if shape_4d and arr.ndim == 3:
                        arr = arr[:, np.newaxis, :, :]
                    return arr
            
            return None

        u = _read_var("u")
        if u is None:
            u = np.zeros((nt, nz, ny, nx))
        v = _read_var("v")
        if v is None:
            v = np.zeros((nt, nz, ny, nx))
        omega = _read_var("w")
        if omega is None:
            omega = np.zeros((nt, nz, ny, nx))
        t_field = _read_var("t_field")
        rh = _read_var("rh")
        hgt = _read_var("hgt")
        precip = _read_var("precip", shape_4d=False)
        pbl_height = _read_var("pbl_height", shape_4d=False)
        terrain_var = _read_var("terrain", shape_4d=False)
        terrain = terrain_var[0] if terrain_var is not None and terrain_var.ndim == 3 else (
            terrain_var if terrain_var is not None else np.zeros((ny, nx))
        )

        # Convert omega (Pa/s) to w (m/s)
        if t_field is not None:
            P_3d = z_grid[np.newaxis, :, np.newaxis, np.newaxis] * 100.0  # hPa → Pa
            P_3d = np.broadcast_to(P_3d, omega.shape)
            w = convert_omega_to_w(omega, t_field, P_3d)
        else:
            w = omega  # assume already in m/s if no temperature

        # Optimize memory layout: ensure C-contiguous arrays for better cache performance
        u = np.ascontiguousarray(u)
        v = np.ascontiguousarray(v)
        w = np.ascontiguousarray(w)
        if t_field is not None:
            t_field = np.ascontiguousarray(t_field)
        if rh is not None:
            rh = np.ascontiguousarray(rh)
        if hgt is not None:
            hgt = np.ascontiguousarray(hgt)

        return MetData(
            u=u, v=v, w=w,
            t_field=t_field, rh=rh, hgt=hgt,
            precip=precip, pbl_height=pbl_height,
            terrain=terrain,
            lon_grid=lon_grid, lat_grid=lat_grid,
            z_grid=z_grid, t_grid=t_grid,
            z_type="pressure",
            source="GDAS_NC",
        )

    @staticmethod
    def _get_coord(ds: Any, names: list[str]) -> np.ndarray:
        """Try multiple coordinate names and return the first match."""
        for name in names:
            if name in ds.variables:
                return np.array(ds.variables[name][:], dtype=np.float64)
            if name in ds.dimensions:
                dim = ds.dimensions[name]
                return np.arange(dim.size, dtype=np.float64)
        raise MetFormatError(
            f"Could not find coordinate variable. Tried: {names}"
        )


# ---------------------------------------------------------------------------
# ERA5 Reader
# ---------------------------------------------------------------------------


class ERA5Reader(MetReaderBase):
    """Reader for ECMWF ERA5 reanalysis data (NetCDF format).

    ERA5 uses different variable names and conventions compared to
    GDAS/GFS.  Pressure levels are in hPa, wind in m/s, and vertical
    velocity is omega (Pa/s).
    """

    _VAR_MAP: dict[str, str] = {
        "u": "u",
        "v": "v",
        "w": "w",           # omega (Pa/s) in ERA5
        "t_field": "t",
        "rh": "r",
        "hgt": "z",         # geopotential (m²/s²) — divide by g
        "precip": "tp",     # total precipitation (m)
        "pbl_height": "blh",
        "terrain": "z",     # surface geopotential
    }

    def get_variable_mapping(self) -> dict[str, str]:
        return dict(self._VAR_MAP)

    def read(self, filepath: str) -> MetData:
        """Read an ERA5 NetCDF file."""
        path = Path(filepath)
        if not path.exists():
            raise MetFileNotFoundError(f"ERA5 file not found: {filepath}")

        try:
            import netCDF4 as nc  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "netCDF4 package is required for ERA5 reading. "
                "Install with: pip install netCDF4"
            ) from exc

        ds = nc.Dataset(str(path), "r")
        try:
            return self._extract(ds)
        finally:
            ds.close()

    def _extract(self, ds: Any) -> MetData:
        lon_grid = self._get_coord(ds, ["longitude", "lon"])
        lat_grid = self._get_coord(ds, ["latitude", "lat"])
        z_grid = self._get_coord(ds, ["level", "pressure_level", "lev"])
        t_grid = self._get_coord(ds, ["time", "t"])

        nx, ny, nz, nt = len(lon_grid), len(lat_grid), len(z_grid), len(t_grid)

        def _read(name: str) -> np.ndarray | None:
            nc_name = self._VAR_MAP.get(name)
            if nc_name and nc_name in ds.variables:
                return np.array(ds.variables[nc_name][:], dtype=np.float64)
            return None

        u = _read("u") or np.zeros((nt, nz, ny, nx))
        v = _read("v") or np.zeros((nt, nz, ny, nx))
        omega = _read("w") or np.zeros((nt, nz, ny, nx))
        t_field = _read("t_field")
        rh = _read("rh")
        hgt_raw = _read("hgt")

        # ERA5 geopotential → geopotential height (divide by g)
        hgt = hgt_raw / GRAVITY if hgt_raw is not None else None

        precip = _read("precip")
        pbl_height = _read("pbl_height")
        terrain = np.zeros((ny, nx))

        # Convert omega (Pa/s) to w (m/s)
        if t_field is not None:
            P_3d = z_grid[np.newaxis, :, np.newaxis, np.newaxis] * 100.0
            P_3d = np.broadcast_to(P_3d, omega.shape)
            w = convert_omega_to_w(omega, t_field, P_3d)
        else:
            w = omega

        return MetData(
            u=u, v=v, w=w,
            t_field=t_field, rh=rh, hgt=hgt,
            precip=precip, pbl_height=pbl_height,
            terrain=terrain,
            lon_grid=lon_grid, lat_grid=lat_grid,
            z_grid=z_grid, t_grid=t_grid,
            z_type="pressure",
            source="ERA5",
        )

    @staticmethod
    def _get_coord(ds: Any, names: list[str]) -> np.ndarray:
        for name in names:
            if name in ds.variables:
                return np.array(ds.variables[name][:], dtype=np.float64)
        raise MetFormatError(f"Could not find coordinate. Tried: {names}")


# ---------------------------------------------------------------------------
# WRF Reader
# ---------------------------------------------------------------------------


class WRFReader(MetReaderBase):
    """Reader for WRF (Weather Research and Forecasting) output files.

    WRF uses staggered grids and its own variable naming conventions.
    This reader de-staggers wind components and converts the eta/sigma
    vertical coordinate to pressure levels.
    """

    _VAR_MAP: dict[str, str] = {
        "u": "U",           # staggered in x
        "v": "V",           # staggered in y
        "w": "W",           # staggered in z (m/s, already vertical velocity)
        "t_field": "T",     # perturbation potential temperature
        "rh": "QVAPOR",    # water vapor mixing ratio → approximate RH
        "hgt": "PH",       # perturbation geopotential (staggered z)
        "precip": "RAINNC", # accumulated non-convective precipitation
        "pbl_height": "PBLH",
        "terrain": "HGT",  # terrain height
    }

    def get_variable_mapping(self) -> dict[str, str]:
        return dict(self._VAR_MAP)

    def read(self, filepath: str) -> MetData:
        """Read a WRF output NetCDF file."""
        path = Path(filepath)
        if not path.exists():
            raise MetFileNotFoundError(f"WRF file not found: {filepath}")

        try:
            import netCDF4 as nc  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "netCDF4 package is required for WRF reading. "
                "Install with: pip install netCDF4"
            ) from exc

        ds = nc.Dataset(str(path), "r")
        try:
            return self._extract(ds)
        finally:
            ds.close()

    def _extract(self, ds: Any) -> MetData:
        # WRF lat/lon are 2D; take the first row/column
        if "XLONG" in ds.variables:
            lon_2d = np.array(ds.variables["XLONG"][0, :, :], dtype=np.float64)
            lat_2d = np.array(ds.variables["XLAT"][0, :, :], dtype=np.float64)
            lon_grid = lon_2d[0, :]
            lat_grid = lat_2d[:, 0]
        else:
            lon_grid = self._get_coord(ds, ["longitude", "lon", "west_east"])
            lat_grid = self._get_coord(ds, ["latitude", "lat", "south_north"])

        nx, ny = len(lon_grid), len(lat_grid)

        # Time
        if "XTIME" in ds.variables:
            t_grid = np.array(ds.variables["XTIME"][:], dtype=np.float64) * 60.0  # min→s
        elif "Times" in ds.variables:
            nt = ds.dimensions["Time"].size
            t_grid = np.arange(nt, dtype=np.float64) * 3600.0
        else:
            nt = 1
            t_grid = np.array([0.0])

        nt = len(t_grid)

        # Vertical levels — use base-state pressure + perturbation
        if "PB" in ds.variables and "P" in ds.variables:
            pb = np.array(ds.variables["PB"][:], dtype=np.float64)
            p_pert = np.array(ds.variables["P"][:], dtype=np.float64)
            p_full = pb + p_pert  # Pa
            # Average over time and horizontal to get representative levels
            z_grid = np.mean(p_full, axis=(0, 2, 3)) / 100.0  # Pa → hPa
            nz = len(z_grid)
        else:
            nz_dim = ds.dimensions.get("bottom_top")
            nz = nz_dim.size if nz_dim else 1
            z_grid = np.arange(nz, dtype=np.float64)

        def _read(name: str) -> np.ndarray | None:
            nc_name = self._VAR_MAP.get(name)
            if nc_name and nc_name in ds.variables:
                return np.array(ds.variables[nc_name][:], dtype=np.float64)
            return None

        # De-stagger U (x-staggered)
        u_raw = _read("u")
        if u_raw is not None and u_raw.shape[-1] == nx + 1:
            u = 0.5 * (u_raw[..., :-1] + u_raw[..., 1:])
        else:
            u = u_raw if u_raw is not None else np.zeros((nt, nz, ny, nx))

        # De-stagger V (y-staggered)
        v_raw = _read("v")
        if v_raw is not None and v_raw.shape[-2] == ny + 1:
            v = 0.5 * (v_raw[..., :-1, :] + v_raw[..., 1:, :])
        else:
            v = v_raw if v_raw is not None else np.zeros((nt, nz, ny, nx))

        # De-stagger W (z-staggered) — WRF W is already in m/s
        w_raw = _read("w")
        if w_raw is not None and w_raw.shape[-3] == nz + 1:
            w = 0.5 * (w_raw[:, :-1, :, :] + w_raw[:, 1:, :, :])
        else:
            w = w_raw if w_raw is not None else np.zeros((nt, nz, ny, nx))

        t_field = _read("t_field")
        # WRF T is perturbation potential temperature; add base (300 K)
        if t_field is not None:
            t_field = t_field + 300.0

        rh = _read("rh")  # mixing ratio, not true RH
        hgt_raw = _read("hgt")
        # De-stagger geopotential height
        if hgt_raw is not None and hgt_raw.shape[-3] == nz + 1:
            hgt = 0.5 * (hgt_raw[:, :-1, :, :] + hgt_raw[:, 1:, :, :]) / GRAVITY
        elif hgt_raw is not None:
            hgt = hgt_raw / GRAVITY
        else:
            hgt = None

        precip = _read("precip")
        pbl_height = _read("pbl_height")
        terrain_raw = _read("terrain")
        terrain = terrain_raw[0] if terrain_raw is not None and terrain_raw.ndim == 3 else (
            terrain_raw if terrain_raw is not None else np.zeros((ny, nx))
        )

        return MetData(
            u=u, v=v, w=w,
            t_field=t_field, rh=rh, hgt=hgt,
            precip=precip, pbl_height=pbl_height,
            terrain=terrain,
            lon_grid=lon_grid, lat_grid=lat_grid,
            z_grid=z_grid, t_grid=t_grid,
            z_type="pressure",
            source="WRF",
        )

    @staticmethod
    def _get_coord(ds: Any, names: list[str]) -> np.ndarray:
        for name in names:
            if name in ds.variables:
                return np.array(ds.variables[name][:], dtype=np.float64)
            if name in ds.dimensions:
                return np.arange(ds.dimensions[name].size, dtype=np.float64)
        raise MetFormatError(f"Could not find coordinate. Tried: {names}")


# Register additional readers
MetReaderFactory.register("GDAS_NC", NetCDFReader)
MetReaderFactory.register("GFS_NC", NetCDFReader)
MetReaderFactory.register("ERA5", ERA5Reader)
MetReaderFactory.register("WRF", WRFReader)
MetReaderFactory.register("NAM", NetCDFReader)
