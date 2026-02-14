"""HYSPLIT tdump (trajectory dump) file writer.

Implements the HYSPLIT trajectory endpoint file format as specified in:
https://www.ready.noaa.gov/hysplitusersguide/S263.htm

The tdump format is an ASCII text file containing trajectory positions
and diagnostic variables at each time step.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import TextIO

import numpy as np

from pyhysplit.core.models import SimulationConfig


class TdumpWriter:
    """Writer for HYSPLIT tdump (trajectory endpoint) files.
    
    The tdump format is the standard HYSPLIT trajectory output format,
    compatible with HYSPLIT visualization tools.
    
    Format specification (from HYSPLIT User's Guide S263):
    - Record #1: Number of met grids, format version
    - Record #2 (loop): Met model ID, starting time
    - Record #3: Number of trajectories, direction, vertical method
    - Record #4 (loop): Starting time, location, height for each trajectory
    - Record #5: Number and names of diagnostic variables
    - Record #6 (loop): Trajectory points with position and diagnostics
    
    Attributes
    ----------
    config : SimulationConfig
        Simulation configuration
    met_model_id : str
        Meteorological model identifier (e.g., "GDAS", "GFS")
    met_start_time : datetime
        Starting time of meteorological data
    met_forecast_hour : int
        Forecast hour of meteorological data (0 for analysis)
    diagnostic_vars : list[str]
        Names of diagnostic output variables
    """
    
    def __init__(
        self,
        config: SimulationConfig,
        met_model_id: str = "GFS",
        met_start_time: datetime | None = None,
        met_forecast_hour: int = 0,
        diagnostic_vars: list[str] | None = None,
    ):
        """Initialize tdump writer.
        
        Parameters
        ----------
        config : SimulationConfig
            Simulation configuration
        met_model_id : str, optional
            Meteorological model identifier, by default "GFS"
        met_start_time : datetime, optional
            Starting time of met data, by default uses config.start_time
        met_forecast_hour : int, optional
            Forecast hour (0 for analysis), by default 0
        diagnostic_vars : list[str], optional
            Diagnostic variables to output, by default ["PRESSURE", "THETA", "AIR_TEMP", "RAINFALL"]
        """
        self.config = config
        self.met_model_id = met_model_id[:8]  # Max 8 characters
        self.met_start_time = met_start_time or config.start_time
        self.met_forecast_hour = met_forecast_hour
        
        # Default diagnostic variables (PRESSURE is always first)
        if diagnostic_vars is None:
            self.diagnostic_vars = ["PRESSURE", "THETA", "AIR_TEMP", "RAINFALL"]
        else:
            # Ensure PRESSURE is first
            if "PRESSURE" not in diagnostic_vars:
                self.diagnostic_vars = ["PRESSURE"] + diagnostic_vars
            elif diagnostic_vars[0] != "PRESSURE":
                vars_copy = [v for v in diagnostic_vars if v != "PRESSURE"]
                self.diagnostic_vars = ["PRESSURE"] + vars_copy
            else:
                self.diagnostic_vars = diagnostic_vars
    
    def write(
        self,
        filepath: str | Path,
        trajectories: list[list[tuple[float, float, float, float]]],
        diagnostics: list[list[dict[str, float]]] | None = None,
    ) -> None:
        """Write trajectories to tdump file.
        
        Parameters
        ----------
        filepath : str or Path
            Output file path
        trajectories : list of list of tuple
            List of trajectories, where each trajectory is a list of
            (time_seconds, lon, lat, height_m) tuples
        diagnostics : list of list of dict, optional
            Diagnostic variables for each point in each trajectory.
            Each dict should contain keys matching self.diagnostic_vars.
            If None, default values are used.
        """
        filepath = Path(filepath)
        
        with open(filepath, "w") as f:
            self._write_header(f, len(trajectories))
            self._write_trajectories(f, trajectories, diagnostics)
    
    def _write_header(self, f: TextIO, num_trajectories: int) -> None:
        """Write tdump file header records."""
        # Record #1: Number of met grids and format version
        num_grids = 1  # We use single met grid
        format_version = 2  # Latest format version
        f.write(f"{num_grids:6d}{format_version:6d}\n")
        
        # Record #2: Met model info (loop for each grid)
        met_year = self.met_start_time.year % 100  # 2-digit year
        met_month = self.met_start_time.month
        met_day = self.met_start_time.day
        met_hour = self.met_start_time.hour
        f.write(
            f"{self.met_model_id:8s}"
            f"{met_year:6d}{met_month:6d}{met_day:6d}"
            f"{met_hour:6d}{self.met_forecast_hour:6d}\n"
        )
        
        # Record #3: Number of trajectories, direction, vertical method
        direction = "BACKWARD" if self.config.total_run_hours < 0 else "FORWARD"
        
        # Vertical motion method names
        vertical_methods = {
            0: "DATA",
            1: "ISODEN",
            2: "ISOBAR",
            3: "ISENTRP",
            4: "ISOSIGM",
            5: "DIVERG",
            6: "ETA",
            7: "AVERAGE",
        }
        vertical_method = vertical_methods.get(self.config.vertical_motion, "DATA")
        
        f.write(f"{num_trajectories:6d} {direction:8s} {vertical_method:8s}\n")
        
        # Record #4: Starting location for each trajectory (loop)
        for start_loc in self.config.start_locations[:num_trajectories]:
            start_year = self.config.start_time.year % 100
            start_month = self.config.start_time.month
            start_day = self.config.start_time.day
            start_hour = self.config.start_time.hour
            
            f.write(
                f"{start_year:6d}{start_month:6d}{start_day:6d}{start_hour:6d}"
                f"{start_loc.lat:9.3f}{start_loc.lon:9.3f} {start_loc.height:9.2f}\n"
            )
        
        # Record #5: Number and names of diagnostic variables
        num_vars = len(self.diagnostic_vars)
        f.write(f"{num_vars:6d}")
        for var_name in self.diagnostic_vars:
            f.write(f" {var_name:8s}")
        f.write("\n")
    
    def _write_trajectories(
        self,
        f: TextIO,
        trajectories: list[list[tuple[float, float, float, float]]],
        diagnostics: list[list[dict[str, float]]] | None = None,
    ) -> None:
        """Write trajectory point records."""
        for traj_num, trajectory in enumerate(trajectories, start=1):
            for point_idx, (t, lon, lat, height) in enumerate(trajectory):
                # Calculate datetime for this point
                dt = timedelta(seconds=t)
                point_time = self.config.start_time + dt
                
                year = point_time.year % 100
                month = point_time.month
                day = point_time.day
                hour = point_time.hour
                minute = point_time.minute
                
                # Age in hours
                age_hours = t / 3600.0
                
                # Meteorological grid number (always 1 for single grid)
                met_grid = 1
                
                # Forecast hour at this point
                forecast_hour = self.met_forecast_hour + int(age_hours)
                
                # Write position record
                f.write(
                    f"{traj_num:6d}{met_grid:6d}"
                    f"{year:6d}{month:6d}{day:6d}{hour:6d}{minute:6d}"
                    f"{forecast_hour:6d}"
                    f"{age_hours:8.2f}"
                    f"{lat:9.3f}{lon:9.3f} {height:9.2f}"
                )
                
                # Write diagnostic variables
                if diagnostics and point_idx < len(diagnostics[traj_num - 1]):
                    diag_dict = diagnostics[traj_num - 1][point_idx]
                    for var_name in self.diagnostic_vars:
                        value = diag_dict.get(var_name, 0.0)
                        f.write(f" {value:9.2f}")
                else:
                    # Default values if diagnostics not provided
                    for var_name in self.diagnostic_vars:
                        if var_name == "PRESSURE":
                            # Estimate pressure from height (standard atmosphere)
                            pressure_hpa = 1013.25 * np.exp(-height / 7400.0)
                            f.write(f" {pressure_hpa:9.2f}")
                        else:
                            f.write(f" {0.0:9.2f}")
                
                f.write("\n")
    
    @staticmethod
    def generate_filename(
        start_time: datetime,
        location_name: str = "",
        suffix: str = "",
    ) -> str:
        """Generate standard HYSPLIT tdump filename.
        
        Parameters
        ----------
        start_time : datetime
            Trajectory start time
        location_name : str, optional
            Location identifier to include in filename
        suffix : str, optional
            Additional suffix for filename
        
        Returns
        -------
        str
            Filename in format: tdump[_location][_suffix]_YYMMDD_HH
        
        Examples
        --------
        >>> TdumpWriter.generate_filename(datetime(2024, 1, 15, 12), "seoul")
        'tdump_seoul_240115_12'
        """
        year = start_time.year % 100
        month = start_time.month
        day = start_time.day
        hour = start_time.hour
        
        parts = ["tdump"]
        if location_name:
            parts.append(location_name)
        if suffix:
            parts.append(suffix)
        
        filename = "_".join(parts)
        filename += f"_{year:02d}{month:02d}{day:02d}_{hour:02d}"
        
        return filename
