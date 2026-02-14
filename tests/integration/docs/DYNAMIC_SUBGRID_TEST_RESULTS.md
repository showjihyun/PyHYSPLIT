# Dynamic Subgrid Test Results

## Test Date: 2026-02-14

## Summary

The dynamic subgrid detection system has been successfully implemented and tested. The system correctly identifies when particles approach boundaries and calculates the required expansion.

## Test Configuration

- **GFS Data Range**: 105-150°E, 20-50°N
- **Trajectory Type**: 24-hour backward
- **Vertical Level**: 850 hPa (standard level)
- **Vertical Motion Mode**: Mode 7 (Spatially averaged)
- **Dynamic Subgrid**: ENABLED

## Results by Location

### 1. Seoul (37.5°N, 127.0°E)

**Status**: ✅ COMPLETE (100%)

**Expansions**: 2
- Expansion #1 at t=66107s: (110.60°E, 37.91°N), wind=39.8 m/s
  - Old bounds: 105-150°E → New bounds: 102.5-150°E
- Expansion #2 at t=78300s: (107.60°E, 38.15°N), wind=11.3 m/s
  - Old bounds: 102.5-150°E → New bounds: 100-150°E

**Analysis**: Seoul trajectory completed successfully with the current data range (105-150°E). The dynamic subgrid correctly detected when the particle approached the western boundary and calculated the required expansion.

### 2. Beijing (39.9°N, 116.4°E)

**Status**: ⚠️ PARTIAL (36% - 9/25 points)

**Expansions**: 3
- Expansion #1 at t=11851s: (110.69°E, 40.31°N), wind=50.9 m/s
  - Old bounds: 105-150°E → New bounds: 102.5-150°E
- Expansion #2 at t=20161s: (107.70°E, 40.37°N), wind=28.2 m/s
  - Old bounds: 102.5-150°E → New bounds: 100-150°E
- Expansion #3 at t=25200s: (105.49°E, 40.11°N), wind=32.1 m/s
  - Old bounds: 100-150°E → New bounds: 97.5-150°E

**Termination**: Boundary error at (105.09°E, 40.07°N) after 26267s

**Analysis**: Beijing trajectory moved rapidly westward due to strong jet stream winds (50.9 m/s). The dynamic subgrid correctly detected 3 expansion events, but the particle still exited through the western boundary at 105°E. This indicates that actual data loading is needed, not just virtual expansion tracking.

### 3. Tokyo (35.7°N, 139.7°E)

**Status**: ⚠️ PARTIAL (92% - 23/25 points)

**Expansions**: 3
- Expansion #1 at t=68286s: (110.83°E, 34.35°N), wind=51.2 m/s
  - Old bounds: 105-150°E → New bounds: 102.5-150°E
- Expansion #2 at t=73034s: (108.32°E, 34.17°N), wind=53.3 m/s
  - Old bounds: 102.5-150°E → New bounds: 100-150°E
- Expansion #3 at t=78211s: (105.64°E, 34.06°N), wind=44.7 m/s
  - Old bounds: 100-150°E → New bounds: 97.5-150°E

**Termination**: Boundary error at (105.14°E, 34.07°N) after 79200s

**Analysis**: Tokyo trajectory achieved 92% completion, very close to full trajectory. The dynamic subgrid detected 3 expansions with high wind speeds (51-53 m/s). The particle exited just 2 hours before completion, indicating that a small additional westward expansion would complete the trajectory.

### 4. Busan (35.2°N, 129.0°E)

**Status**: ⚠️ PARTIAL (76% - 19/25 points)

**Expansions**: 3
- Expansion #1 at t=53584s: (110.91°E, 34.01°N), wind=56.3 m/s
  - Old bounds: 105-150°E → New bounds: 102.5-150°E
- Expansion #2 at t=58293s: (108.20°E, 33.49°N), wind=59.1 m/s
  - Old bounds: 102.5-150°E → New bounds: 100-150°E
- Expansion #3 at t=64051s: (105.48°E, 33.12°N), wind=38.5 m/s
  - Old bounds: 100-150°E → New bounds: 97.5-150°E

**Termination**: Boundary error at (105.16°E, 33.11°N) after 64800s

**Analysis**: Busan trajectory experienced the strongest winds (59.1 m/s) and moved rapidly westward. The dynamic subgrid correctly detected 3 expansions, but the particle still exited through the western boundary.

## Key Findings

### 1. Dynamic Subgrid Detection Works Correctly ✅

The system successfully:
- Detects when particles approach boundaries (within 5° threshold)
- Calculates wind speed and predicted movement
- Determines required expansion based on MGMIN and wind speed
- Tracks expansion history with detailed logging

### 2. Expansion Pattern Analysis

**Common Pattern**:
- All trajectories moved westward (backward in time)
- First expansion: ~110°E (5° from western boundary)
- Second expansion: ~108°E (2.5° from new boundary)
- Third expansion: ~105°E (at the boundary)

**Expansion Amounts**:
- Expansion #1: 2.5° westward (105° → 102.5°)
- Expansion #2: 2.5° westward (102.5° → 100°)
- Expansion #3: 2.5° westward (100° → 97.5°)

### 3. Wind Speed Correlation

High wind speeds trigger expansions:
- Beijing: 50.9 m/s (strongest)
- Busan: 56.3-59.1 m/s (very strong)
- Tokyo: 51.2-53.3 m/s (strong)
- Seoul: 39.8 m/s (moderate)

### 4. Boundary Exit Analysis

All partial trajectories exited through the **western boundary at 105°E**:
- Beijing: 105.09°E (just inside)
- Tokyo: 105.14°E (just inside)
- Busan: 105.16°E (just inside)

This indicates that the current GFS data range (105-150°E) is insufficient for high-latitude jet stream trajectories.

## Next Steps

### Phase 1: Implement Actual Data Loading (CRITICAL)

The current implementation only **tracks** expansion but doesn't **load** new data. We need to:

1. **Modify MetData Loading**:
   ```python
   class DynamicMetDataLoader:
       def load_expanded_region(self, new_bounds):
           """Load additional GFS data for expanded region."""
           # Download or load from cache
           # Merge with existing MetData
           # Update interpolator
   ```

2. **Integrate with TrajectoryEngine**:
   ```python
   if self.dynamic_subgrid.check_and_expand(...):
       # Load new data
       new_met = self.met_loader.load_expanded_region(
           self.dynamic_subgrid.get_bounds()
       )
       # Update interpolator
       self.interpolator.update_met_data(new_met)
   ```

3. **GFS Data Caching Strategy**:
   - Pre-download wider range (e.g., 90-150°E)
   - Load subsets on demand
   - Cache loaded regions

### Phase 2: Optimize Expansion Parameters

Current parameters:
- `mgmin`: 10 grid units (2.5° at 0.25° resolution)
- `safety_factor`: 2.0
- `expansion_threshold`: 5.0°

Potential optimizations:
- Increase `expansion_threshold` to 7-8° for earlier detection
- Adjust `safety_factor` based on wind speed
- Implement adaptive `mgmin` based on trajectory characteristics

### Phase 3: Test with Actual Data Loading

Once data loading is implemented:
1. Test with all 8 locations
2. Verify 100% completion rate
3. Measure performance impact
4. Compare with HYSPLIT Web results

## Expected Results After Implementation

### Before (Current - Detection Only)

| Location | Completion | Expansions | Status |
|----------|-----------|------------|--------|
| Seoul | 100% | 2 | ✅ Complete |
| Beijing | 36% | 3 | ⚠️ Boundary exit |
| Tokyo | 92% | 3 | ⚠️ Boundary exit |
| Busan | 76% | 3 | ⚠️ Boundary exit |

**Average**: 76% completion

### After (With Data Loading)

| Location | Completion | Expansions | Status |
|----------|-----------|------------|--------|
| Seoul | 100% | 2 | ✅ Complete |
| Beijing | 100% | 3 | ✅ Complete |
| Tokyo | 100% | 3 | ✅ Complete |
| Busan | 100% | 3 | ✅ Complete |

**Expected Average**: 100% completion

## Technical Implementation Notes

### 1. Expansion Algorithm

The expansion calculation follows HYSPLIT's approach:

```python
# Predicted movement distance
predicted_distance = wind_speed * dt * safety_factor

# Minimum expansion based on MGMIN
min_expansion = mgmin * grid_spacing

# Use larger of the two
expansion = max(min_expansion, predicted_distance)
```

### 2. Boundary Check

Expansion is triggered when:
```python
distance_to_boundary < expansion_threshold + predicted_distance
```

This ensures proactive expansion before the particle reaches the boundary.

### 3. Expansion Direction

The system intelligently expands only the boundaries that are being approached:
- Westward movement → expand western boundary
- Eastward movement → expand eastern boundary
- Similar for north/south

### 4. Global Limits

Expansions are clamped to global coverage:
- Longitude: -180° to 180°
- Latitude: -90° to 90°

## Conclusion

The dynamic subgrid detection system is **working correctly** and successfully identifies when and where expansion is needed. The next critical step is to implement actual meteorological data loading to complete the HYSPLIT-style dynamic subgrid functionality.

**Current Status**: 🟡 Detection implemented, data loading pending

**Expected Impact**: 76% → 100% completion rate for high-latitude trajectories

**Estimated Implementation Time**: 2-3 hours for data loading integration

---

**Test Date**: 2026-02-14
**Test Script**: `tests/integration/test_dynamic_subgrid.py`
**Results File**: `tests/integration/dynamic_subgrid_results.json`
