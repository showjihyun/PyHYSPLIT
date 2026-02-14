# Next Steps: Dynamic Subgrid Data Loading

## Current Status

✅ **Phase 1 Complete**: Dynamic subgrid detection and tracking
🔴 **Phase 2 Pending**: Actual meteorological data loading

## Why Data Loading is Critical

The current implementation **detects** when expansion is needed but doesn't **load** new data. This means:
- Expansion events are logged ✅
- Boundary calculations are correct ✅
- But trajectories still fail at boundaries ❌

**Example from Beijing test**:
```
Expansion #1: 105-150°E → 102.5-150°E (virtual)
Expansion #2: 102.5-150°E → 100-150°E (virtual)
Expansion #3: 100-150°E → 97.5-150°E (virtual)
Result: Still exits at 105°E (actual data boundary)
```

## Implementation Options

### Option A: Pre-load Wide Range (RECOMMENDED for Testing)

**Approach**: Download very wide GFS data range upfront

**Pros**:
- Simple to implement
- No dynamic loading complexity
- Immediate testing possible

**Cons**:
- Large data size (~500 MB for 90-150°E)
- Memory intensive
- Not true HYSPLIT behavior

**Implementation**:
```bash
# 1. Download wider GFS data
python tests/integration/download_gfs_very_wide.py  # 90-150°E

# 2. Test with wider data
python tests/integration/test_all_locations_very_wide.py

# 3. Verify 100% completion
```

**Estimated Time**: 30 minutes

### Option B: Dynamic Data Loading (HYSPLIT-Compatible)

**Approach**: Load data on-demand as expansion occurs

**Pros**:
- True HYSPLIT behavior
- Memory efficient
- Scalable to any trajectory

**Cons**:
- More complex implementation
- Requires data caching strategy
- Longer development time

**Implementation Steps**:

1. **Create DynamicMetDataLoader** (1 hour)
   ```python
   class DynamicMetDataLoader:
       def __init__(self, base_file, cache_dir):
           self.base_file = base_file
           self.cache_dir = cache_dir
           self.loaded_regions = {}
       
       def load_region(self, lon_min, lon_max, lat_min, lat_max):
           """Load GFS data for specified region."""
           # Check cache
           # Download if needed
           # Load NetCDF subset
           # Return MetData
   ```

2. **Implement Data Merging** (1 hour)
   ```python
   def merge_met_data(base_met, new_met):
       """Merge two MetData objects."""
       # Combine grids
       # Interpolate overlapping regions
       # Return merged MetData
   ```

3. **Update TrajectoryEngine** (30 minutes)
   ```python
   # In __init__:
   if config.enable_dynamic_subgrid:
       self.met_loader = DynamicMetDataLoader(...)
   
   # In _run_single_source:
   if self.dynamic_subgrid.check_and_expand(...):
       new_bounds = self.dynamic_subgrid.get_bounds()
       expanded_met = self.met_loader.load_region(*new_bounds)
       self.interpolator.update_met_data(expanded_met)
   ```

4. **Test and Validate** (30 minutes)
   ```bash
   python tests/integration/test_dynamic_loading.py
   ```

**Estimated Time**: 3 hours

### Option C: Hybrid Approach (RECOMMENDED for Production)

**Approach**: Pre-load wide range, use dynamic subgrid for diagnostics

**Pros**:
- Best of both worlds
- Immediate results
- Future-proof for dynamic loading

**Cons**:
- Requires both implementations

**Implementation**:
```python
# 1. Download wide range (90-150°E)
python tests/integration/download_gfs_very_wide.py

# 2. Enable dynamic subgrid for diagnostics
config = SimulationConfig(
    enable_dynamic_subgrid=True,  # Track expansions
    # ... use wide data range ...
)

# 3. Verify no expansions needed with wide data
# 4. Later implement true dynamic loading
```

**Estimated Time**: 30 minutes + 3 hours (later)

## Recommended Immediate Action

### Step 1: Download Wider GFS Data (30 minutes)

Create `tests/integration/download_gfs_very_wide.py`:

```python
"""Download very wide GFS data range for dynamic subgrid testing."""

import xarray as xr
from datetime import datetime
from pathlib import Path

# Download 90-150°E (60° width)
# This should cover all expansion needs
lon_min, lon_max = 90, 150
lat_min, lat_max = 20, 50

# ... download logic ...
```

### Step 2: Test with Wide Data (15 minutes)

```bash
# Run all 8 locations with wide data
python tests/integration/test_all_locations_very_wide.py

# Expected result: 100% completion for all locations
```

### Step 3: Verify Dynamic Subgrid (15 minutes)

```bash
# Enable dynamic subgrid with wide data
# Should show: expansions detected but not needed
python tests/integration/test_dynamic_subgrid_with_wide_data.py
```

### Step 4: Document Results (15 minutes)

Create summary showing:
- Wide data eliminates boundary errors ✅
- Dynamic subgrid correctly predicts needed range ✅
- Ready for true dynamic loading implementation ✅

**Total Time**: ~1.5 hours

## Expected Results

### After Wide Data Download

| Location | Current | With Wide Data | Improvement |
|----------|---------|----------------|-------------|
| Seoul | 100% | 100% | ✅ Maintained |
| Beijing | 36% | 100% | ✅ +64% |
| Tokyo | 92% | 100% | ✅ +8% |
| Busan | 76% | 100% | ✅ +24% |
| Shanghai | 100% | 100% | ✅ Maintained |
| Taipei | 100% | 100% | ✅ Maintained |
| Hong Kong | 100% | 100% | ✅ Maintained |
| Manila | 100% | 100% | ✅ Maintained |

**Average**: 86.5% → 100% (+13.5%)
**Progress**: 80% → 95-98%

## Decision Matrix

| Criterion | Option A (Wide) | Option B (Dynamic) | Option C (Hybrid) |
|-----------|----------------|-------------------|-------------------|
| Time to Results | ⭐⭐⭐ 30 min | ⭐ 3 hours | ⭐⭐⭐ 30 min |
| Memory Usage | ⭐ High | ⭐⭐⭐ Low | ⭐ High |
| HYSPLIT Match | ⭐⭐ Partial | ⭐⭐⭐ Full | ⭐⭐⭐ Full (later) |
| Complexity | ⭐⭐⭐ Simple | ⭐ Complex | ⭐⭐ Medium |
| Scalability | ⭐ Limited | ⭐⭐⭐ Excellent | ⭐⭐⭐ Excellent |

## Recommendation

**For Immediate Testing**: Option A (Wide Data)
- Quick results
- Validates dynamic subgrid detection
- Proves concept works

**For Production**: Option C (Hybrid)
- Start with wide data
- Implement dynamic loading later
- Best long-term solution

## Next Command to Run

```bash
# Create and run wide data download script
python tests/integration/download_gfs_very_wide.py

# Then test all locations
python tests/integration/test_all_locations_extended.py --data-range very_wide
```

## Questions to Consider

1. **Data Size**: Is 500 MB acceptable for testing?
   - Yes → Use Option A
   - No → Use Option B

2. **Timeline**: Need results today or can wait?
   - Today → Use Option A
   - Can wait → Use Option B

3. **Production Goal**: Memory-constrained environment?
   - Yes → Must use Option B eventually
   - No → Option A is fine

## Success Criteria

After implementation, we should see:
- ✅ 100% completion for all 8 locations
- ✅ No boundary errors
- ✅ Progress: 80% → 95-98%
- ✅ All trajectories match HYSPLIT Web

---

**Document Date**: 2026-02-14
**Status**: Ready for implementation
**Recommended**: Option A (Wide Data) for immediate testing
**Next Step**: Create `download_gfs_very_wide.py`
