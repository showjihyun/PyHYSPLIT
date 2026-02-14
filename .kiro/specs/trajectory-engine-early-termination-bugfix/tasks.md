# Implementation Plan: Trajectory Engine Early Termination Bugfix

## Overview

This plan implements a fix for the trajectory engine early termination bug caused by height coordinate system mismatch. The implementation adds coordinate conversion and validation at engine initialization, enhances error diagnostics, and includes comprehensive tests to prevent regression.

## Tasks

- [ ] 1. Add coordinate conversion and validation to TrajectoryEngine
  - [x] 1.1 Implement `_validate_and_convert_start_locations()` method
    - Add new method to `TrajectoryEngine` class in `pyhysplit/engine.py`
    - Implement coordinate conversion logic based on `MetData.z_type`
    - Use `CoordinateConverter.height_to_pressure()` for pressure coordinates
    - Validate converted coordinates are within `MetData.z_grid` range
    - Raise `InvalidCoordinateError` for out-of-range coordinates
    - Add logging for each start location conversion
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 4.1, 4.2_
  
  - [x] 1.2 Write property test for coordinate conversion correctness
    - **Property 1: Height to Pressure Conversion Correctness**
    - **Validates: Requirements 1.2, 1.4**
  
  - [x] 1.3 Write property test for conditional conversion logic
    - **Property 2: Coordinate System Conditional Conversion**
    - **Validates: Requirements 1.1, 1.3**

- [ ] 2. Modify TrajectoryEngine initialization
  - [x] 2.1 Update `__init__()` method
    - Add logging for `MetData` coordinate system information
    - Call `_validate_and_convert_start_locations()` during initialization
    - Store converted coordinates in `self._converted_start_locations`
    - _Requirements: 4.3, 4.4_
  
  - [x] 2.2 Write property test for initialization validation
    - **Property 3: Initialization Validation Catches Invalid Coordinates**
    - **Validates: Requirements 4.1, 4.2**
  
  - [x] 2.3 Write unit tests for initialization logging
    - Test that coordinate system info is logged
    - Test that converted coordinates are logged for each start location
    - _Requirements: 4.3, 4.4_

- [ ] 3. Update `_run_single_source()` to use converted coordinates
  - [x] 3.1 Modify trajectory calculation to use converted coordinates
    - Look up converted coordinates from `self._converted_start_locations`
    - Use converted `z` value instead of `start.height`
    - Add logging for initial position in both coordinate systems
    - _Requirements: 1.1_
  
  - [x] 3.2 Write unit test for Seoul winter trajectory regression
    - Test case: Seoul (37.5°N, 127.0°E), 850m AGL, 7h backward
    - Verify 8 trajectory points generated
    - Verify simulation runs for full 7 hours (25200 seconds)
    - Verify all points have valid pressure values
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ] 4. Enhance boundary error diagnostics
  - [x] 4.1 Improve BoundaryError logging in `_run_single_source()`
    - Log particle position in `MetData` coordinate system
    - Log valid ranges for all coordinate dimensions
    - Determine and log whether vertical exit was through top or bottom
    - Log time elapsed and number of trajectory points generated
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  
  - [x] 4.2 Write unit tests for boundary error logging
    - Test that boundary errors log position and ranges
    - Test that top/bottom exit is correctly identified
    - Test that elapsed time and point count are logged
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [ ] 5. Add vertical motion diagnostics
  - [x] 5.1 Implement large pressure change warning
    - Add check after Heun integration step in `_run_single_source()`
    - Log warning when pressure changes by more than 200 hPa in one step
    - Include pressure change magnitude and time step in warning
    - _Requirements: 2.4_
  
  - [x] 5.2 Write unit test for vertical motion warning
    - Create scenario with large pressure change
    - Verify warning is logged with correct information
    - _Requirements: 2.4_

- [x] 6. Checkpoint - Run all tests and verify fix
  - Ensure all unit tests pass
  - Ensure all property tests pass
  - Run Seoul winter trajectory test and verify 8 points generated
  - Verify no regressions in existing functionality
  - Ask the user if questions arise

- [ ] 7. Add round-trip conversion property test
  - [x] 7.1 Write property test for round-trip conversion consistency
    - **Property 4: Round-Trip Conversion Consistency**
    - **Validates: Requirements 1.2**
    - Generate random heights, convert to pressure and back
    - Verify result matches original within tolerance (1% or 10m)

- [ ] 8. Update documentation
  - [x] 8.1 Add docstring documentation to CoordinateConverter
    - Document standard atmosphere approximation in `height_to_pressure()`
    - Document inverse formula in `pressure_to_height()`
    - _Requirements: 6.1_
  
  - [x] 8.2 Add comments to TrajectoryEngine
    - Explain coordinate conversion in `_validate_and_convert_start_locations()`
    - Explain why conversion is needed in `__init__()`
    - _Requirements: 6.2_
  
  - [x] 8.3 Update Interpolator documentation
    - Document expected coordinate system for `z` parameter in `interpolate_4d()`
    - Clarify that `z` should be in `MetData` coordinate system
    - _Requirements: 6.3_
  
  - [x] 8.4 Update MetData documentation
    - Document units and coordinate system for `z_grid` field
    - Clarify that `z_type` determines interpretation of `z_grid`
    - _Requirements: 6.4_

- [ ] 9. Final checkpoint - Comprehensive testing
  - Run full test suite including integration tests
  - Verify Seoul winter trajectory generates correct output
  - Compare with HYSPLIT Web results if available
  - Ensure all tests pass, ask the user if questions arise

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- The fix is backward-incompatible but necessary to correct buggy behavior
