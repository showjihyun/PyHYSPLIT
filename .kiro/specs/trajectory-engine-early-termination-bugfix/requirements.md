# Requirements Document: Trajectory Engine Early Termination Bugfix

## Introduction

This document specifies the requirements for fixing a critical bug in the PyHYSPLIT trajectory engine where backward trajectories terminate prematurely after approximately 6 minutes instead of running for the full simulation duration (e.g., 7 hours). The bug is caused by a height coordinate system mismatch between the particle's starting height (specified in meters AGL) and the meteorological data's vertical grid (specified in hPa pressure levels).

## Glossary

- **Trajectory_Engine**: The main simulation driver in `pyhysplit/engine.py` that orchestrates trajectory calculations
- **Interpolator**: The component in `pyhysplit/interpolator.py` that performs 4D interpolation of meteorological fields
- **Coordinate_Converter**: The utility in `pyhysplit/coordinate_converter.py` that converts between vertical coordinate systems
- **StartLocation**: A data structure containing initial particle position (lon, lat, height in meters AGL)
- **MetData**: A data structure containing meteorological fields with vertical coordinates in pressure (hPa) or height (m)
- **AGL**: Above Ground Level - height measured from terrain surface
- **ASL**: Above Sea Level - height measured from sea level
- **hPa**: Hectopascals - pressure unit (1 hPa = 100 Pa)
- **Backward_Trajectory**: A trajectory calculated by integrating backward in time from the starting point
- **BoundaryError**: An exception raised when a particle position falls outside the valid meteorological grid bounds

## Requirements

### Requirement 1: Height Coordinate Conversion

**User Story:** As a trajectory modeler, I want the engine to correctly convert starting heights from meters AGL to the meteorological data's vertical coordinate system, so that particles remain within valid grid bounds throughout the simulation.

#### Acceptance Criteria

1. WHEN a StartLocation with height in meters AGL is provided, THE Trajectory_Engine SHALL convert it to the MetData vertical coordinate system before interpolation
2. WHEN MetData uses pressure coordinates (z_type="pressure"), THE Coordinate_Converter SHALL convert height in meters to pressure in hPa using the standard atmosphere approximation
3. WHEN MetData uses height coordinates (z_type="height"), THE Trajectory_Engine SHALL use the height value directly without conversion
4. THE Coordinate_Converter SHALL use the formula P = P0 * exp(-z / H) WHERE P0=101325 Pa and H=8500 m
5. IF the converted pressure falls outside the MetData pressure range, THEN THE Trajectory_Engine SHALL raise an InvalidCoordinateError with a descriptive message

### Requirement 2: Vertical Velocity Sign Correction

**User Story:** As a trajectory modeler, I want vertical motion to be physically correct in backward trajectories, so that particles follow realistic atmospheric paths.

#### Acceptance Criteria

1. WHEN running a backward trajectory (total_run_hours < 0), THE Trajectory_Engine SHALL ensure vertical velocity produces physically realistic motion
2. WHEN interpolating vertical velocity for backward trajectories, THE Interpolator SHALL account for time direction in the vertical motion calculation
3. THE Trajectory_Engine SHALL verify that particles in backward trajectories do not unrealistically ascend from surface to stratosphere
4. WHEN a particle's pressure decreases by more than 200 hPa in a single time step, THE Trajectory_Engine SHALL log a warning about potential vertical motion issues

### Requirement 3: Boundary Checking Enhancement

**User Story:** As a trajectory modeler, I want clear diagnostic information when particles leave the grid, so that I can identify and fix coordinate system issues.

#### Acceptance Criteria

1. WHEN a BoundaryError occurs, THE Trajectory_Engine SHALL log the particle position in both the original coordinate system and the converted coordinate system
2. THE Trajectory_Engine SHALL log the valid range for each coordinate dimension when a boundary error occurs
3. WHEN a particle exits through the vertical boundaries, THE Trajectory_Engine SHALL specifically indicate whether it exited through the top or bottom
4. THE Trajectory_Engine SHALL log the time elapsed and number of trajectory points generated before termination

### Requirement 4: Coordinate System Validation

**User Story:** As a trajectory modeler, I want the engine to validate coordinate system compatibility at initialization, so that I can catch configuration errors before running expensive simulations.

#### Acceptance Criteria

1. WHEN the Trajectory_Engine is initialized, THE Trajectory_Engine SHALL validate that all StartLocation heights are convertible to the MetData vertical coordinate system
2. WHEN a StartLocation height converts to a pressure outside the MetData pressure range, THE Trajectory_Engine SHALL raise an InvalidCoordinateError during initialization
3. THE Trajectory_Engine SHALL log the converted vertical coordinates for all start locations at initialization
4. WHEN MetData z_type is "pressure", THE Trajectory_Engine SHALL log the pressure range in hPa at initialization

### Requirement 5: Integration Test Coverage

**User Story:** As a developer, I want comprehensive integration tests that verify full-duration trajectory calculations, so that I can prevent regression of this bug.

#### Acceptance Criteria

1. THE test suite SHALL include a test case for the Seoul winter backward trajectory (7h, 850m starting height)
2. THE test SHALL verify that the trajectory generates 8 points (1 per hour + initial point)
3. THE test SHALL verify that the simulation runs for the full 7 hours (25200 seconds)
4. THE test SHALL verify that all trajectory points have pressure values within the valid MetData range
5. THE test SHALL verify that vertical motion in backward trajectories is physically realistic (no stratospheric ascent from surface)

### Requirement 6: Coordinate Conversion Documentation

**User Story:** As a developer, I want clear documentation of coordinate system handling, so that I can understand and maintain the conversion logic.

#### Acceptance Criteria

1. THE Coordinate_Converter SHALL include docstring documentation explaining the standard atmosphere approximation
2. THE Trajectory_Engine SHALL include comments explaining where and why coordinate conversion occurs
3. THE Interpolator SHALL document the expected coordinate system for the z parameter
4. THE MetData dataclass SHALL document the units and coordinate system for z_grid
