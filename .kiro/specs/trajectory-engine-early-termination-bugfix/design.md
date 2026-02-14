# Design Document: Trajectory Engine Early Termination Bugfix

## Overview

This design addresses a critical bug in the PyHYSPLIT trajectory engine where backward trajectories terminate prematurely after approximately 6 minutes instead of running for the full simulation duration. The root cause is a height coordinate system mismatch: `StartLocation.height` is specified in meters AGL (Above Ground Level), but `MetData.z_grid` uses hPa (hectopascal) pressure levels. When the height value is used directly without conversion, the particle quickly exits the valid pressure range (200-1000 hPa), triggering a `BoundaryError` and early termination.

The fix involves three main components:
1. **Coordinate conversion at initialization**: Convert `StartLocation.height` from meters AGL to the appropriate vertical coordinate system (pressure or height) based on `MetData.z_type`
2. **Validation at initialization**: Verify that converted coordinates fall within valid `MetData` bounds before starting the simulation
3. **Enhanced diagnostics**: Improve logging to help diagnose coordinate system issues

## Architecture

### Current Flow (Buggy)

```
StartLocation(height=850m AGL)
    ↓
TrajectoryEngine._run_single_source()
    ↓
z = start.height  # 850 (interpreted as 850 hPa, which is invalid!)
    ↓
Interpolator.interpolate_4d(lon, lat, z=850, t)
    ↓
BoundaryError: z=850 outside range [200, 1000]
    ↓
Early termination after ~6 minutes
```

### Fixed Flow

```
StartLocation(height=850m AGL)
    ↓
TrajectoryEngine.__init__()
    ↓
_validate_and_convert_start_locations()
    ├─ If MetData.z_type == "pressure":
    │   └─ Convert 850m → 916.8 hPa using standard atmosphere
    └─ If MetData.z_type == "height":
        └─ Use 850m directly
    ↓
Validate converted z is within MetData.z_grid range
    ↓
Store converted coordinates
    ↓
TrajectoryEngine._run_single_source()
    ↓
z = converted_start_height  # 916.8 hPa (valid!)
    ↓
Interpolator.interpolate_4d(lon, lat, z=916.8, t)
    ↓
Successful interpolation, trajectory continues
```

## Components and Interfaces

### 1. CoordinateConverter (Existing, No Changes Needed)

The `CoordinateConverter` class already provides the necessary conversion functions:

```python
@staticmethod
def height_to_pressure(
    z: np.ndarray,
    P0: float = 101325.0,  # Pa
    H: float = 8500.0,      # m
) -> np.ndarray:
    """Convert height to pressure using standard atmosphere.
    
    P = P0 * exp(-z / H)
    """
    return P0 * np.exp(-np.asarray(z, dtype=float) / H)

@staticmethod
def pressure_to_height(
    P: np.ndarray,
    hgt: np.ndarray | None = None,
    P0: float = 101325.0,
    H: float = 8500.0,
) -> np.ndarray:
    """Convert pressure to height.
    
    Z = -H * ln(P / P0)
    """
    if hgt is not None:
        return hgt
    return -H * np.log(np.asarray(P, dtype=float) / P0)
```

These functions are already implemented correctly and will be used as-is.

### 2. TrajectoryEngine (Modifications Required)

#### New Method: `_validate_and_convert_start_locations()`

```python
def _validate_and_convert_start_locations(self) -> list[tuple[float, float, float]]:
    """Validate and convert start locations to MetData coordinate system.
    
    Returns
    -------
    list[tuple[float, float, float]]
        Converted (lon, lat, z) tuples in MetData coordinate system.
        
    Raises
    ------
    InvalidCoordinateError
        If any start location converts to coordinates outside MetData bounds.
    """
    converted_locations = []
    
    for idx, loc in enumerate(self.config.start_locations):
        lon, lat = loc.lon, loc.lat
        height_agl = loc.height
        
        # Convert height based on MetData coordinate system
        if self.met.z_type == "pressure":
            # Convert meters AGL to pressure (Pa), then to hPa
            pressure_pa = CoordinateConverter.height_to_pressure(
                np.array([height_agl])
            )[0]
            z_converted = pressure_pa / 100.0  # Convert Pa to hPa
            
            logger.info(
                f"Start location {idx}: {height_agl}m AGL → {z_converted:.1f} hPa"
            )
            
            # Validate pressure is within MetData range
            z_min, z_max = self.met.z_grid[0], self.met.z_grid[-1]
            if z_converted < z_min or z_converted > z_max:
                raise InvalidCoordinateError(
                    f"Start location {idx} height {height_agl}m AGL converts to "
                    f"{z_converted:.1f} hPa, which is outside MetData pressure "
                    f"range [{z_min:.1f}, {z_max:.1f}] hPa"
                )
        else:
            # MetData uses height coordinates, use directly
            z_converted = height_agl
            logger.info(
                f"Start location {idx}: {height_agl}m AGL (no conversion needed)"
            )
            
            # Validate height is within MetData range
            z_min, z_max = self.met.z_grid[0], self.met.z_grid[-1]
            if z_converted < z_min or z_converted > z_max:
                raise InvalidCoordinateError(
                    f"Start location {idx} height {height_agl}m is outside "
                    f"MetData height range [{z_min:.1f}, {z_max:.1f}] m"
                )
        
        converted_locations.append((lon, lat, z_converted))
    
    return converted_locations
```

#### Modified `__init__()` Method

```python
def __init__(
    self,
    config: SimulationConfig,
    met: MetData,
    backend: Optional[ComputeBackend] = None,
    parallel: Optional[ParallelExecutor] = None,
    prefer_gpu: bool = False,
    num_workers: Optional[int] = None,
) -> None:
    self.config = config
    self.met = met

    # Log MetData coordinate system info
    logger.info(f"MetData vertical coordinate system: {met.z_type}")
    if met.z_type == "pressure":
        logger.info(
            f"MetData pressure range: {met.z_grid[0]:.1f} - {met.z_grid[-1]:.1f} hPa"
        )
    else:
        logger.info(
            f"MetData height range: {met.z_grid[0]:.1f} - {met.z_grid[-1]:.1f} m"
        )

    # Validate and convert start locations
    self._converted_start_locations = self._validate_and_convert_start_locations()

    # ... rest of initialization (unchanged) ...
```

#### Modified `_run_single_source()` Method

```python
def _run_single_source(
    self,
    start: StartLocation,
    output_interval_s: float,
) -> list[tuple]:
    """Compute trajectory for a single start location."""
    
    # Find the converted coordinates for this start location
    start_idx = self.config.start_locations.index(start)
    lon, lat, z = self._converted_start_locations[start_idx]
    
    # Log initial position in both coordinate systems
    logger.info(
        f"Starting trajectory: {start.lat}°N, {start.lon}°E, "
        f"{start.height}m AGL (z={z:.1f} in {self.met.z_type} coordinates)"
    )
    
    t = float(self.met.t_grid[0]) if self.is_forward else float(self.met.t_grid[-1])

    trajectory: list[tuple] = [(t, lon, lat, z)]
    elapsed = 0.0
    next_output = output_interval_s
    mass = 1.0

    while elapsed < self._total_seconds:
        # ... rest of method (unchanged) ...
        
        try:
            u, v, w = self.interpolator.interpolate_4d(lon, lat, z, t)
        except BoundaryError as e:
            # Enhanced logging for boundary errors
            logger.warning(
                f"Particle left grid at (lon={lon:.4f}, lat={lat:.4f}, "
                f"z={z:.1f} {self.met.z_type}, t={t:.1f}s)"
            )
            logger.warning(
                f"Valid ranges: lon=[{self.met.lon_grid[0]:.1f}, {self.met.lon_grid[-1]:.1f}], "
                f"lat=[{self.met.lat_grid[0]:.1f}, {self.met.lat_grid[-1]:.1f}], "
                f"z=[{self.met.z_grid[0]:.1f}, {self.met.z_grid[-1]:.1f}] {self.met.z_type}"
            )
            
            # Determine if vertical exit was through top or bottom
            if z < self.met.z_grid[0]:
                if self.met.z_type == "pressure":
                    logger.warning("Particle exited through TOP (pressure too low)")
                else:
                    logger.warning("Particle exited through BOTTOM (height too low)")
            elif z > self.met.z_grid[-1]:
                if self.met.z_type == "pressure":
                    logger.warning("Particle exited through BOTTOM (pressure too high)")
                else:
                    logger.warning("Particle exited through TOP (height too high)")
            
            logger.warning(
                f"Trajectory terminated after {elapsed:.1f}s with {len(trajectory)} points"
            )
            break
        
        # ... rest of loop (unchanged) ...
    
    return trajectory
```

### 3. Enhanced Vertical Motion Diagnostics

Add a check for unrealistic vertical motion in backward trajectories:

```python
# In _run_single_source(), after Heun integration step:

# Check for unrealistic vertical motion (especially in backward trajectories)
if self.met.z_type == "pressure":
    pressure_change = abs(z_new - z)
    if pressure_change > 200.0:  # More than 200 hPa change in one step
        logger.warning(
            f"Large pressure change detected: {z:.1f} → {z_new:.1f} hPa "
            f"(Δ={pressure_change:.1f} hPa) in dt={dt:.1f}s. "
            f"This may indicate vertical motion issues."
        )
```

## Data Models

### Modified StartLocation Interpretation

The `StartLocation` dataclass itself does not change, but its interpretation does:

```python
@dataclass
class StartLocation:
    """A single trajectory start point."""
    lat: float        # degrees
    lon: float        # degrees
    height: float     # metres AGL (will be converted to MetData coordinate system)
```

**Important**: The `height` field is ALWAYS interpreted as meters AGL (Above Ground Level), regardless of the `MetData` coordinate system. The `TrajectoryEngine` is responsible for converting this to the appropriate coordinate system.

### New Exception Usage

```python
class InvalidCoordinateError(PyHysplitError):
    """Raised when coordinate values are out of valid range."""
```

This existing exception will be used to signal coordinate system validation failures.

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Height to Pressure Conversion Correctness

*For any* height value in meters, when converted to pressure using the standard atmosphere approximation, the result should satisfy P = P0 * exp(-z / H) where P0=101325 Pa and H=8500 m.

**Validates: Requirements 1.2, 1.4**

### Property 2: Coordinate System Conditional Conversion

*For any* `StartLocation` and `MetData` pair, if `MetData.z_type == "pressure"`, then the height should be converted to pressure; if `MetData.z_type == "height"`, then the height should be used directly without conversion.

**Validates: Requirements 1.1, 1.3**

### Property 3: Initialization Validation Catches Invalid Coordinates

*For any* `StartLocation` whose height converts to a value outside the `MetData.z_grid` range, initializing a `TrajectoryEngine` should raise an `InvalidCoordinateError`.

**Validates: Requirements 4.1, 4.2**

### Property 4: Round-Trip Conversion Consistency

*For any* height value that converts to a pressure within the valid range, converting back from pressure to height should yield approximately the same value (within numerical tolerance).

**Validates: Requirements 1.2**

## Error Handling

### 1. Initialization Errors

**InvalidCoordinateError during `__init__()`**:
- Raised when a `StartLocation` height converts to coordinates outside `MetData` bounds
- Includes descriptive message with:
  - Start location index
  - Original height in meters AGL
  - Converted coordinate value
  - Valid `MetData` range
- Prevents simulation from starting with invalid configuration

### 2. Runtime Boundary Errors

**BoundaryError during `_run_single_source()`**:
- Enhanced logging includes:
  - Particle position in `MetData` coordinate system
  - Valid ranges for all dimensions
  - Whether vertical exit was through top or bottom
  - Time elapsed and number of points generated
- Allows trajectory to terminate gracefully
- Provides diagnostic information for debugging

### 3. Vertical Motion Warnings

**Large pressure change warning**:
- Logged when pressure changes by more than 200 hPa in a single time step
- Indicates potential issues with vertical velocity or time step size
- Does not stop simulation, but alerts user to potential problems

## Testing Strategy

### Unit Tests

Unit tests will focus on specific examples and edge cases:

1. **Coordinate conversion examples**:
   - Test conversion of specific heights (0m, 500m, 850m, 1500m, 3000m)
   - Verify conversion matches expected formula
   - Test round-trip conversion (height → pressure → height)

2. **Initialization validation examples**:
   - Test engine initialization with valid start locations (should succeed)
   - Test engine initialization with out-of-range start locations (should raise `InvalidCoordinateError`)
   - Test logging output during initialization

3. **Boundary error logging examples**:
   - Trigger boundary errors and verify log messages contain required information
   - Test both top and bottom vertical exits
   - Verify log distinguishes between pressure and height coordinate systems

4. **Seoul winter trajectory regression test**:
   - Run the specific case that triggered the bug: Seoul (37.5°N, 127.0°E), 850m AGL, 7h backward
   - Verify trajectory generates 8 points (1 per hour + initial)
   - Verify simulation runs for full 7 hours (25200 seconds)
   - Verify all trajectory points have valid pressure/height values

### Property-Based Tests

Property tests will verify universal properties across all inputs (minimum 100 iterations each):

1. **Property 1: Height to Pressure Conversion Correctness**
   - Generate random heights in range [0, 10000] meters
   - Verify conversion matches formula P = P0 * exp(-z / H)
   - **Feature: trajectory-engine-early-termination-bugfix, Property 1: Height to Pressure Conversion Correctness**

2. **Property 2: Coordinate System Conditional Conversion**
   - Generate random `StartLocation` and `MetData` pairs
   - Verify conversion logic matches `z_type`
   - **Feature: trajectory-engine-early-termination-bugfix, Property 2: Coordinate System Conditional Conversion**

3. **Property 3: Initialization Validation Catches Invalid Coordinates**
   - Generate random start locations with heights that convert to out-of-range values
   - Verify `InvalidCoordinateError` is raised during initialization
   - **Feature: trajectory-engine-early-termination-bugfix, Property 3: Initialization Validation Catches Invalid Coordinates**

4. **Property 4: Round-Trip Conversion Consistency**
   - Generate random heights
   - Convert to pressure and back to height
   - Verify result matches original within tolerance (1% or 10m, whichever is larger)
   - **Feature: trajectory-engine-early-termination-bugfix, Property 4: Round-Trip Conversion Consistency**

### Integration Tests

Integration tests will verify end-to-end behavior:

1. **Full trajectory calculation**:
   - Run complete trajectories with various start locations and durations
   - Verify trajectories complete without premature termination
   - Verify all trajectory points have valid coordinates

2. **Comparison with HYSPLIT Web**:
   - Run the same scenarios as HYSPLIT Web
   - Compare trajectory paths and verify reasonable agreement
   - This validates that the fix produces physically realistic results

### Test Configuration

All property-based tests should be configured to run at least 100 iterations to ensure comprehensive coverage through randomization. Each test should include a comment tag referencing the design document property it validates.

## Implementation Notes

### Backward Compatibility

This fix changes the interpretation of `StartLocation.height`:
- **Before**: Ambiguous - could be meters or pressure depending on context
- **After**: Always meters AGL, converted automatically

This is a breaking change for any code that was manually converting heights before passing them to `StartLocation`. However, since the current behavior is buggy, this is an acceptable breaking change.

### Performance Impact

The coordinate conversion and validation adds minimal overhead:
- Conversion happens once per start location during initialization
- Uses simple mathematical operations (exp, log)
- No impact on the main simulation loop

### Future Enhancements

Potential future improvements not included in this bugfix:

1. **Terrain-aware conversion**: Account for terrain height when converting AGL to ASL
2. **Hybrid coordinate support**: Support for hybrid sigma-pressure coordinates
3. **Automatic coordinate system detection**: Infer coordinate system from data if not specified
4. **More sophisticated vertical motion validation**: Check for physically unrealistic ascent/descent rates

These enhancements are out of scope for this bugfix but could be addressed in future work.
