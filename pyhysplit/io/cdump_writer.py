"""HYSPLIT cdump (concentration dump) file writer.

Implements the HYSPLIT concentration file format as specified in:
https://www.ready.noaa.gov/hysplitusersguide/S363.htm

The cdump format is a binary (big-endian) file containing 3D concentration
grids with temporal sampling information.
"""

from __future__ import annotations

import struct
from datetime import datetime
from pathlib import Path

import numpy as np

from pyhysplit.core.models import ConcentrationGridConfig, SimulationConfig
from pyhysplit.physics.concentration import ConcentrationGrid


class CdumpWriter:
    """Writer for HYSPLIT cdump (concentration dump) files.
    
    The cdump format is the standard HYSPLIT concentration output format,
    compatible with HYSPLIT visualization and analysis tools.
    
    Format specification (from HYSPLIT User's Guide S363):
    - Binary file with big-endian byte order
    - Supports packed (non-zero only) or unpacked (full grid) output
    - Contains metadata, grid definition, and concentration arrays
    
    Attributes
    ----------
    config : SimulationConfig
        Simulation configuration
    met_model_id : str
        Meteorological model identifier (max 4 characters)
    met_start_time : datetime
        Starting time of meteorological data
    met_forecast_hour : int
        Forecast hour of meteorological data
    packing : bool
        Whether to use packed output (only non-zero values)
    """
    
    def __init__(
        self,
        config: SimulationConfig,
        met_model_id: str = "GFS",
        met_start_time: datetime | None = None,
        met_forecast_hour: int = 0,
        packing: bool = True,
    ):
        """Initialize cdump writer.
        
        Parameters
        ----------
        config : SimulationConfig
            Simulation configuration
        met_model_id : str, optional
            Meteorological model identifier (max 4 chars), by default "GFS"
        met_start_time : datetime, optional
            Starting time of met data, by default uses config.start_time
        met_forecast_hour : int, optional
            Forecast hour (0 for analysis), by default 0
        packing : bool, optional
            Use packed output format (smaller files), by default True
        """
        self.config = config
        self.met_model_id = met_model_id[:4].ljust(4)  # Exactly 4 characters
        self.met_start_time = met_start_time or config.start_time
        self.met_forecast_hour = met_forecast_hour
        self.packing = packing
    
    def write(
        self,
        filepath: str | Path,
        grids: list[ConcentrationGrid],
        pollutant_ids: list[str] | None = None,
    ) -> None:
        """Write concentration grids to cdump file.
        
        Parameters
        ----------
        filepath : str or Path
            Output file path
        grids : list of ConcentrationGrid
            Concentration grids to write (one per sampling period)
        pollutant_ids : list of str, optional
            Pollutant identifiers (max 4 chars each), by default ["PM25"]
        """
        filepath = Path(filepath)
        
        if not grids:
            raise ValueError("At least one concentration grid required")
        
        # Default pollutant IDs
        if pollutant_ids is None:
            pollutant_ids = ["PM25"]
        
        # Ensure pollutant IDs are 4 characters
        pollutant_ids = [pid[:4].ljust(4) for pid in pollutant_ids]
        
        with open(filepath, "wb") as f:
            self._write_header(f, grids[0], len(pollutant_ids))
            self._write_grids(f, grids, pollutant_ids)
    
    def _write_header(
        self,
        f,
        grid: ConcentrationGrid,
        num_pollutants: int,
    ) -> None:
        """Write cdump file header records."""
        # Record #1: Met model ID, starting time, number of locations, packing flag
        met_year = self.met_start_time.year
        met_month = self.met_start_time.month
        met_day = self.met_start_time.day
        met_hour = self.met_start_time.hour
        
        num_start_locations = self.config.num_start_locations
        packing_flag = 1 if self.packing else 0
        
        # Write as big-endian
        f.write(self.met_model_id.encode('ascii'))
        f.write(struct.pack('>5i', met_year, met_month, met_day, met_hour, self.met_forecast_hour))
        f.write(struct.pack('>i', num_start_locations))
        f.write(struct.pack('>i', packing_flag))
        
        # Record #2: Starting locations (loop)
        for start_loc in self.config.start_locations[:num_start_locations]:
            start_year = self.config.start_time.year
            start_month = self.config.start_time.month
            start_day = self.config.start_time.day
            start_hour = self.config.start_time.hour
            start_minute = 0
            
            f.write(struct.pack('>4i', start_year, start_month, start_day, start_hour))
            f.write(struct.pack('>3f', start_loc.lat, start_loc.lon, start_loc.height))
            f.write(struct.pack('>i', start_minute))
        
        # Record #3: Grid definition
        nlat = len(grid.lat_grid)
        nlon = len(grid.lon_grid)
        dlat = grid.lat_grid[1] - grid.lat_grid[0] if nlat > 1 else 0.1
        dlon = grid.lon_grid[1] - grid.lon_grid[0] if nlon > 1 else 0.1
        lat_ll = grid.lat_grid[0]  # Lower left corner
        lon_ll = grid.lon_grid[0]
        
        f.write(struct.pack('>2i', nlat, nlon))
        f.write(struct.pack('>2f', dlat, dlon))
        f.write(struct.pack('>2f', lat_ll, lon_ll))
        
        # Record #4: Vertical levels
        nlevels = len(grid.z_grid)
        f.write(struct.pack('>i', nlevels))
        for height in grid.z_grid:
            f.write(struct.pack('>i', int(height)))
        
        # Record #5: Pollutant IDs
        f.write(struct.pack('>i', num_pollutants))
        for pollutant_id in range(num_pollutants):
            # Use generic IDs if not enough provided
            pid = f"P{pollutant_id+1:03d}"[:4].ljust(4)
            f.write(pid.encode('ascii'))
    
    def _write_grids(
        self,
        f,
        grids: list[ConcentrationGrid],
        pollutant_ids: list[str],
    ) -> None:
        """Write concentration grid data records."""
        # For each grid, we need to write sampling times and concentration data
        for grid in grids:
            # Get sampling period from grid config
            if hasattr(grid, 'config'):
                sample_start = grid.config.sampling_start
                sample_end = grid.config.sampling_end
            else:
                # Fallback to simulation times
                sample_start = self.config.start_time
                sample_end = self.config.start_time
            
            # Record #6: Sample start time
            f.write(struct.pack('>6i',
                sample_start.year,
                sample_start.month,
                sample_start.day,
                sample_start.hour,
                sample_start.minute,
                self.met_forecast_hour
            ))
            
            # Record #7: Sample end time
            f.write(struct.pack('>6i',
                sample_end.year,
                sample_end.month,
                sample_end.day,
                sample_end.hour,
                sample_end.minute,
                self.met_forecast_hour
            ))
            
            # Record #8: Concentration arrays (loop over levels and pollutants)
            for level_idx, height in enumerate(grid.z_grid):
                for pollutant_idx, pollutant_id in enumerate(pollutant_ids):
                    # Write pollutant ID and level
                    f.write(pollutant_id.encode('ascii'))
                    f.write(struct.pack('>i', int(height)))
                    
                    # Get concentration slice for this level
                    # Grid shape is (nz, ny, nx)
                    conc_slice = grid.concentration[level_idx, :, :]
                    
                    if self.packing:
                        # Packed format: write only non-zero values
                        self._write_packed_concentration(f, conc_slice)
                    else:
                        # Unpacked format: write entire grid
                        self._write_unpacked_concentration(f, conc_slice)
    
    def _write_packed_concentration(self, f, conc_array: np.ndarray) -> None:
        """Write concentration array in packed format (non-zero only).
        
        Packed format:
        - For each non-zero element:
          - INT*2: i index
          - INT*2: j index
          - REAL*4: concentration value
        - Terminated by index pair (0, 0) or end of level
        """
        nlat, nlon = conc_array.shape
        
        # Find non-zero elements
        nonzero_indices = np.nonzero(conc_array)
        
        if len(nonzero_indices[0]) > 0:
            # Write number of non-zero elements
            num_nonzero = len(nonzero_indices[0])
            f.write(struct.pack('>i', num_nonzero))
            
            # Write each non-zero element
            for i, j in zip(nonzero_indices[0], nonzero_indices[1]):
                # HYSPLIT uses 1-based indexing
                f.write(struct.pack('>2h', i + 1, j + 1))
                f.write(struct.pack('>f', conc_array[i, j]))
        else:
            # No non-zero elements
            f.write(struct.pack('>i', 0))
    
    def _write_unpacked_concentration(self, f, conc_array: np.ndarray) -> None:
        """Write concentration array in unpacked format (full grid).
        
        Unpacked format:
        - REAL*4 array of all grid points in row-major order
        """
        # Flatten array in C order (row-major) and write as big-endian floats
        conc_flat = conc_array.flatten(order='C').astype('>f4')
        f.write(conc_flat.tobytes())
    
    @staticmethod
    def generate_filename(
        start_time: datetime,
        location_name: str = "",
        suffix: str = "",
    ) -> str:
        """Generate standard HYSPLIT cdump filename.
        
        Parameters
        ----------
        start_time : datetime
            Simulation start time
        location_name : str, optional
            Location identifier to include in filename
        suffix : str, optional
            Additional suffix for filename
        
        Returns
        -------
        str
            Filename in format: cdump[_location][_suffix]_YYMMDD_HH
        
        Examples
        --------
        >>> CdumpWriter.generate_filename(datetime(2024, 1, 15, 12), "seoul")
        'cdump_seoul_240115_12'
        """
        year = start_time.year % 100
        month = start_time.month
        day = start_time.day
        hour = start_time.hour
        
        parts = ["cdump"]
        if location_name:
            parts.append(location_name)
        if suffix:
            parts.append(suffix)
        
        filename = "_".join(parts)
        filename += f"_{year:02d}{month:02d}{day:02d}_{hour:02d}"
        
        return filename
