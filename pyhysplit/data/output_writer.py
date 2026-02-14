"""Output writers for HYSPLIT-compatible trajectory and concentration data.

Provides TdumpWriter, CdumpWriter, CSVWriter, and NetCDFWriter for
producing output in formats compatible with HYSPLIT post-processing tools.

Requirements: 12.1, 12.2, 12.3, 12.4, 12.5
"""

from __future__ import annotations

import csv
import struct
from datetime import datetime, timedelta
from io import StringIO
from typing import Any

import numpy as np

from pyhysplit.core.models import ConcentrationGridConfig, StartLocation


# ---------------------------------------------------------------------------
# Trajectory point representation
# ---------------------------------------------------------------------------

class TrajectoryPoint:
    """A single point along a trajectory with optional diagnostic variables."""

    __slots__ = (
        "traj_id", "grid_id", "year", "month", "day", "hour", "minute",
        "forecast_hour", "age", "lat", "lon", "height", "diag_vars",
    )

    def __init__(
        self,
        traj_id: int,
        grid_id: int,
        year: int,
        month: int,
        day: int,
        hour: int,
        minute: int,
        forecast_hour: float,
        age: float,
        lat: float,
        lon: float,
        height: float,
        diag_vars: dict[str, float] | None = None,
    ):
        self.traj_id = traj_id
        self.grid_id = grid_id
        self.year = year
        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute
        self.forecast_hour = forecast_hour
        self.age = age
        self.lat = lat
        self.lon = lon
        self.height = height
        self.diag_vars = diag_vars or {}


# ---------------------------------------------------------------------------
# Parsed tdump result
# ---------------------------------------------------------------------------

class TdumpData:
    """Container for parsed tdump file data."""

    def __init__(
        self,
        met_grids: list[dict[str, Any]],
        start_info: list[dict[str, Any]],
        diag_var_names: list[str],
        points: list[TrajectoryPoint],
    ):
        self.met_grids = met_grids
        self.start_info = start_info
        self.diag_var_names = diag_var_names
        self.points = points


# ---------------------------------------------------------------------------
# TdumpWriter  (Req 12.1, 12.4, 12.5)
# ---------------------------------------------------------------------------

class TdumpWriter:
    """Write and read HYSPLIT tdump trajectory text files."""

    @staticmethod
    def write(
        filepath: str,
        trajectories: list[list[TrajectoryPoint]],
        met_info: list[dict[str, Any]],
        start_locations: list[StartLocation],
        diag_var_names: list[str] | None = None,
    ) -> None:
        """Write trajectory data to a tdump text file.

        Parameters
        ----------
        filepath : str
            Output file path.
        trajectories : list[list[TrajectoryPoint]]
            One inner list per trajectory, each containing ordered points.
        met_info : list[dict]
            Meteorological grid info dicts with keys:
            ``model_id``, ``year``, ``month``, ``day``, ``hour``,
            ``forecast_hour``.
        start_locations : list[StartLocation]
            Starting locations for each trajectory.
        diag_var_names : list[str] | None
            Names of diagnostic variables appended to each data row.
        """
        if diag_var_names is None:
            diag_var_names = []

        lines: list[str] = []

        # --- Header section: met grids ---
        lines.append(f"{len(met_info):>6d}")
        for mg in met_info:
            lines.append(
                f"{mg['model_id']:>8s}"
                f"{mg['year']:>5d}{mg['month']:>3d}{mg['day']:>3d}"
                f"{mg['hour']:>3d}"
                f"{mg['forecast_hour']:>6d}"
            )

        # --- Header section: trajectory start info ---
        n_traj = len(trajectories)
        lines.append(f"{n_traj:>6d}")
        direction = "FORWARD"
        for i, sl in enumerate(start_locations):
            # Use first point's time if available, else zeros
            if trajectories and trajectories[i]:
                pt = trajectories[i][0]
                yr, mo, dy, hr = pt.year, pt.month, pt.day, pt.hour
            else:
                yr = mo = dy = hr = 0
            lines.append(
                f"{direction:>8s}"
                f"{yr:>5d}{mo:>3d}{dy:>3d}{hr:>3d}"
                f"{sl.lat:>9.3f}{sl.lon:>10.3f}{sl.height:>9.1f}"
            )

        # --- Header section: diagnostic variable names ---
        n_diag = len(diag_var_names)
        var_str = "".join(f"{v:>9s}" for v in diag_var_names)
        lines.append(f"{n_diag:>6d}{var_str}")

        # --- Data section ---
        for traj in trajectories:
            for pt in traj:
                row = (
                    f"{pt.traj_id:>6d}{pt.grid_id:>6d}"
                    f"{pt.year:>5d}{pt.month:>3d}{pt.day:>3d}"
                    f"{pt.hour:>3d}{pt.minute:>3d}"
                    f"{pt.forecast_hour:>8.1f}{pt.age:>9.1f}"
                    f"{pt.lat:>9.3f}{pt.lon:>10.3f}{pt.height:>9.1f}"
                )
                for vn in diag_var_names:
                    val = pt.diag_vars.get(vn, 0.0)
                    row += f"{val:>9.1f}"
                lines.append(row)

        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    @staticmethod
    def write_string(
        trajectories: list[list[TrajectoryPoint]],
        met_info: list[dict[str, Any]],
        start_locations: list[StartLocation],
        diag_var_names: list[str] | None = None,
    ) -> str:
        """Return tdump content as a string (useful for testing)."""
        if diag_var_names is None:
            diag_var_names = []

        lines: list[str] = []

        lines.append(f"{len(met_info):>6d}")
        for mg in met_info:
            lines.append(
                f"{mg['model_id']:>8s}"
                f"{mg['year']:>5d}{mg['month']:>3d}{mg['day']:>3d}"
                f"{mg['hour']:>3d}"
                f"{mg['forecast_hour']:>6d}"
            )

        n_traj = len(trajectories)
        lines.append(f"{n_traj:>6d}")
        direction = "FORWARD"
        for i, sl in enumerate(start_locations):
            if trajectories and trajectories[i]:
                pt = trajectories[i][0]
                yr, mo, dy, hr = pt.year, pt.month, pt.day, pt.hour
            else:
                yr = mo = dy = hr = 0
            lines.append(
                f"{direction:>8s}"
                f"{yr:>5d}{mo:>3d}{dy:>3d}{hr:>3d}"
                f"{sl.lat:>9.3f}{sl.lon:>10.3f}{sl.height:>9.1f}"
            )

        n_diag = len(diag_var_names)
        var_str = "".join(f"{v:>9s}" for v in diag_var_names)
        lines.append(f"{n_diag:>6d}{var_str}")

        for traj in trajectories:
            for pt in traj:
                row = (
                    f"{pt.traj_id:>6d}{pt.grid_id:>6d}"
                    f"{pt.year:>5d}{pt.month:>3d}{pt.day:>3d}"
                    f"{pt.hour:>3d}{pt.minute:>3d}"
                    f"{pt.forecast_hour:>8.1f}{pt.age:>9.1f}"
                    f"{pt.lat:>9.3f}{pt.lon:>10.3f}{pt.height:>9.1f}"
                )
                for vn in diag_var_names:
                    val = pt.diag_vars.get(vn, 0.0)
                    row += f"{val:>9.1f}"
                lines.append(row)

        return "\n".join(lines) + "\n"

    @staticmethod
    def read(filepath: str) -> TdumpData:
        """Parse a tdump text file and return structured data."""
        with open(filepath, "r", encoding="utf-8") as fh:
            text = fh.read()
        return TdumpWriter.read_string(text)

    @staticmethod
    def read_string(text: str) -> TdumpData:
        """Parse tdump content from a string."""
        lines = text.strip().split("\n")
        idx = 0

        # --- Met grids ---
        n_met = int(lines[idx].strip())
        idx += 1
        met_grids: list[dict[str, Any]] = []
        for _ in range(n_met):
            parts = lines[idx].split()
            idx += 1
            met_grids.append({
                "model_id": parts[0],
                "year": int(parts[1]),
                "month": int(parts[2]),
                "day": int(parts[3]),
                "hour": int(parts[4]),
                "forecast_hour": int(parts[5]),
            })

        # --- Trajectory start info ---
        n_traj = int(lines[idx].strip())
        idx += 1
        start_info: list[dict[str, Any]] = []
        for _ in range(n_traj):
            parts = lines[idx].split()
            idx += 1
            start_info.append({
                "direction": parts[0],
                "year": int(parts[1]),
                "month": int(parts[2]),
                "day": int(parts[3]),
                "hour": int(parts[4]),
                "lat": float(parts[5]),
                "lon": float(parts[6]),
                "height": float(parts[7]),
            })

        # --- Diagnostic variable names ---
        diag_line = lines[idx].split()
        idx += 1
        n_diag = int(diag_line[0])
        diag_var_names = diag_line[1: 1 + n_diag]

        # --- Data rows ---
        points: list[TrajectoryPoint] = []
        while idx < len(lines):
            line = lines[idx].strip()
            idx += 1
            if not line:
                continue
            parts = line.split()
            # Fixed columns: traj_id grid_id YY MM DD HH MM fcst age lat lon hgt
            traj_id = int(parts[0])
            grid_id = int(parts[1])
            year = int(parts[2])
            month = int(parts[3])
            day = int(parts[4])
            hour = int(parts[5])
            minute = int(parts[6])
            forecast_hour = float(parts[7])
            age = float(parts[8])
            lat = float(parts[9])
            lon = float(parts[10])
            height = float(parts[11])

            diag: dict[str, float] = {}
            for vi, vn in enumerate(diag_var_names):
                if 12 + vi < len(parts):
                    diag[vn] = float(parts[12 + vi])

            points.append(TrajectoryPoint(
                traj_id=traj_id,
                grid_id=grid_id,
                year=year,
                month=month,
                day=day,
                hour=hour,
                minute=minute,
                forecast_hour=forecast_hour,
                age=age,
                lat=lat,
                lon=lon,
                height=height,
                diag_vars=diag,
            ))

        return TdumpData(
            met_grids=met_grids,
            start_info=start_info,
            diag_var_names=diag_var_names,
            points=points,
        )


# ---------------------------------------------------------------------------
# CdumpWriter  (Req 12.2)
# ---------------------------------------------------------------------------

class CdumpWriter:
    """Write HYSPLIT cdump binary concentration files.

    The binary format stores concentration grids as sequential records:
    header record → per-time-step concentration arrays.
    """

    @staticmethod
    def write(
        filepath: str,
        concentration: np.ndarray,
        grid_config: ConcentrationGridConfig,
        time_info: dict[str, Any],
    ) -> None:
        """Write concentration data to a cdump binary file.

        Parameters
        ----------
        filepath : str
            Output file path.
        concentration : np.ndarray
            3-D concentration array (nz, ny, nx).
        grid_config : ConcentrationGridConfig
            Grid geometry.
        time_info : dict
            Keys: ``year``, ``month``, ``day``, ``hour``, ``minute``,
            ``forecast_hour``.
        """
        nz, ny, nx = concentration.shape

        with open(filepath, "wb") as fh:
            # Header record
            fh.write(struct.pack("<i", nx))
            fh.write(struct.pack("<i", ny))
            fh.write(struct.pack("<i", nz))
            fh.write(struct.pack("<d", grid_config.center_lat))
            fh.write(struct.pack("<d", grid_config.center_lon))
            fh.write(struct.pack("<d", grid_config.spacing_lat))
            fh.write(struct.pack("<d", grid_config.spacing_lon))

            # Time info
            fh.write(struct.pack("<i", time_info.get("year", 0)))
            fh.write(struct.pack("<i", time_info.get("month", 0)))
            fh.write(struct.pack("<i", time_info.get("day", 0)))
            fh.write(struct.pack("<i", time_info.get("hour", 0)))

            # Concentration data (level by level, row by row)
            for k in range(nz):
                for j in range(ny):
                    fh.write(concentration[k, j, :].astype("<f4").tobytes())

    @staticmethod
    def read(filepath: str) -> tuple[np.ndarray, dict[str, Any]]:
        """Read a cdump binary file.

        Returns
        -------
        concentration : np.ndarray
            3-D array (nz, ny, nx).
        header : dict
            Grid and time metadata.
        """
        with open(filepath, "rb") as fh:
            nx = struct.unpack("<i", fh.read(4))[0]
            ny = struct.unpack("<i", fh.read(4))[0]
            nz = struct.unpack("<i", fh.read(4))[0]
            center_lat = struct.unpack("<d", fh.read(8))[0]
            center_lon = struct.unpack("<d", fh.read(8))[0]
            spacing_lat = struct.unpack("<d", fh.read(8))[0]
            spacing_lon = struct.unpack("<d", fh.read(8))[0]
            year = struct.unpack("<i", fh.read(4))[0]
            month = struct.unpack("<i", fh.read(4))[0]
            day = struct.unpack("<i", fh.read(4))[0]
            hour = struct.unpack("<i", fh.read(4))[0]

            data = np.zeros((nz, ny, nx), dtype=np.float32)
            for k in range(nz):
                for j in range(ny):
                    row_bytes = fh.read(nx * 4)
                    data[k, j, :] = np.frombuffer(row_bytes, dtype="<f4")

        header = {
            "nx": nx, "ny": ny, "nz": nz,
            "center_lat": center_lat, "center_lon": center_lon,
            "spacing_lat": spacing_lat, "spacing_lon": spacing_lon,
            "year": year, "month": month, "day": day, "hour": hour,
        }
        return data, header


# ---------------------------------------------------------------------------
# CSVWriter  (Req 12.3)
# ---------------------------------------------------------------------------

class CSVWriter:
    """Write trajectory data to CSV format."""

    @staticmethod
    def write(
        filepath: str,
        trajectories: list[list[TrajectoryPoint]],
        diag_var_names: list[str] | None = None,
    ) -> None:
        """Write trajectory points to a CSV file.

        Parameters
        ----------
        filepath : str
            Output file path.
        trajectories : list[list[TrajectoryPoint]]
            Trajectory data.
        diag_var_names : list[str] | None
            Diagnostic variable names to include as extra columns.
        """
        if diag_var_names is None:
            diag_var_names = []

        header = [
            "traj_id", "grid_id", "year", "month", "day",
            "hour", "minute", "forecast_hour", "age",
            "lat", "lon", "height",
        ] + list(diag_var_names)

        with open(filepath, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            for traj in trajectories:
                for pt in traj:
                    row = [
                        pt.traj_id, pt.grid_id,
                        pt.year, pt.month, pt.day,
                        pt.hour, pt.minute,
                        pt.forecast_hour, pt.age,
                        pt.lat, pt.lon, pt.height,
                    ]
                    for vn in diag_var_names:
                        row.append(pt.diag_vars.get(vn, 0.0))
                    writer.writerow(row)


# ---------------------------------------------------------------------------
# NetCDFWriter  (Req 12.3)
# ---------------------------------------------------------------------------

class NetCDFWriter:
    """Write trajectory data to NetCDF format.

    Requires the optional ``netCDF4`` dependency.
    """

    @staticmethod
    def write(
        filepath: str,
        trajectories: list[list[TrajectoryPoint]],
        diag_var_names: list[str] | None = None,
    ) -> None:
        """Write trajectory points to a NetCDF file.

        Parameters
        ----------
        filepath : str
            Output file path.
        trajectories : list[list[TrajectoryPoint]]
            Trajectory data.
        diag_var_names : list[str] | None
            Diagnostic variable names to include as extra variables.
        """
        try:
            from netCDF4 import Dataset  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "netCDF4 is required for NetCDF output. "
                "Install with: pip install netCDF4"
            ) from exc

        if diag_var_names is None:
            diag_var_names = []

        # Flatten all points
        all_points: list[TrajectoryPoint] = []
        for traj in trajectories:
            all_points.extend(traj)

        n = len(all_points)

        with Dataset(filepath, "w", format="NETCDF4") as ds:
            ds.createDimension("point", n)

            v_traj = ds.createVariable("traj_id", "i4", ("point",))
            v_grid = ds.createVariable("grid_id", "i4", ("point",))
            v_year = ds.createVariable("year", "i4", ("point",))
            v_month = ds.createVariable("month", "i4", ("point",))
            v_day = ds.createVariable("day", "i4", ("point",))
            v_hour = ds.createVariable("hour", "i4", ("point",))
            v_minute = ds.createVariable("minute", "i4", ("point",))
            v_fcst = ds.createVariable("forecast_hour", "f8", ("point",))
            v_age = ds.createVariable("age", "f8", ("point",))
            v_lat = ds.createVariable("lat", "f8", ("point",))
            v_lon = ds.createVariable("lon", "f8", ("point",))
            v_hgt = ds.createVariable("height", "f8", ("point",))

            diag_vars_nc: dict[str, Any] = {}
            for vn in diag_var_names:
                diag_vars_nc[vn] = ds.createVariable(vn, "f8", ("point",))

            for i, pt in enumerate(all_points):
                v_traj[i] = pt.traj_id
                v_grid[i] = pt.grid_id
                v_year[i] = pt.year
                v_month[i] = pt.month
                v_day[i] = pt.day
                v_hour[i] = pt.hour
                v_minute[i] = pt.minute
                v_fcst[i] = pt.forecast_hour
                v_age[i] = pt.age
                v_lat[i] = pt.lat
                v_lon[i] = pt.lon
                v_hgt[i] = pt.height
                for vn in diag_var_names:
                    diag_vars_nc[vn][i] = pt.diag_vars.get(vn, 0.0)
