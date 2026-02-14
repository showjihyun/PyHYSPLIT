# Quick Start: Dynamic Subgrid

## What Is It?

HYSPLIT's dynamic subgrid expansion automatically extends the meteorological data domain when particles move rapidly (e.g., in jet streams) to prevent boundary errors.

## Current Status

✅ **Detection**: Implemented and working
🔴 **Data Loading**: Not yet implemented

## Quick Test

```bash
# Test dynamic subgrid detection
python tests/integration/test_dynamic_subgrid.py

# View results
cat tests/integration/dynamic_subgrid_results.json
```

## How to Enable

```python
from pyhysplit.models import SimulationConfig, StartLocation
from pyhysplit.engine import TrajectoryEngine

config = SimulationConfig(
    start_time=datetime(2024, 1, 15, 0, 0),
    start_locations=[StartLocation(lat=37.5, lon=127.0, height=850.0, height_type="pressure")],
    total_run_hours=-24,
    vertical_motion=7,
    model_top=10000.0,
    met_files=[],
    enable_dynamic_subgrid=True,  # ← Enable here
)

engine = TrajectoryEngine(config, met)
trajectories = engine.run()

# Check expansion statistics
if engine.dynamic_subgrid:
    stats = engine.dynamic_subgrid.get_expansion_stats()
    print(f"Expansions: {stats['expansion_count']}")
    for exp in stats['expansion_history']:
        print(f"  #{exp['count']}: {exp['position']}, wind={exp['wind_speed']:.1f} m/s")
```

## What It Does

1. **Monitors** particle position relative to data boundaries
2. **Calculates** wind speed and predicted movement
3. **Detects** when expansion is needed (within 5° of boundary)
4. **Computes** required expansion based on MGMIN and wind speed
5. **Logs** expansion events with detailed information
6. **Tracks** expansion history for analysis

## What It Doesn't Do (Yet)

- ❌ Load new meteorological data
- ❌ Update interpolator with expanded data
- ❌ Prevent boundary errors (detection only)

## Test Results

| Location | Completion | Expansions | Status |
|----------|-----------|------------|--------|
| Seoul | 100% | 2 | ✅ Complete |
| Beijing | 36% | 3 | ⚠️ Needs data loading |
| Tokyo | 92% | 3 | ⚠️ Needs data loading |
| Busan | 76% | 3 | ⚠️ Needs data loading |

## Parameters

```python
DynamicSubgrid(
    initial_bounds=(105.0, 150.0, 20.0, 50.0),  # (lon_min, lon_max, lat_min, lat_max)
    mgmin=10,                    # Minimum subgrid size (grid units)
    grid_spacing=0.25,           # Grid resolution (degrees)
    safety_factor=2.0,           # Expansion multiplier
    expansion_threshold=5.0,     # Trigger distance (degrees)
)
```

## Typical Expansion Pattern

```
Initial:     105-150°E (45° width)
Expansion 1: 102.5-150°E (47.5° width) at ~110°E, wind=40-50 m/s
Expansion 2: 100-150°E (50° width) at ~108°E, wind=30-40 m/s
Expansion 3: 97.5-150°E (52.5° width) at ~105°E, wind=30-40 m/s
```

## Next Steps

### For Testing (30 minutes)

```bash
# Download wider GFS data
python tests/integration/download_gfs_very_wide.py  # 90-150°E

# Test with wider data
python tests/integration/test_all_locations_very_wide.py

# Expected: 100% completion
```

### For Production (2-3 hours)

Implement actual data loading:
1. Create `DynamicMetDataLoader` class
2. Implement data merging logic
3. Update `TrajectoryEngine` to load data on expansion
4. Test and validate

## Troubleshooting

### "Particle left grid" errors still occur

**Cause**: Data loading not yet implemented
**Solution**: Use wider GFS data range (90-150°E) or implement data loading

### No expansions detected

**Cause**: Particle stays within boundaries
**Solution**: This is normal for low-latitude locations or short trajectories

### Too many expansions

**Cause**: Very strong winds or small initial domain
**Solution**: Adjust `expansion_threshold` or use wider initial domain

## Files

**Implementation**:
- `pyhysplit/dynamic_subgrid.py` - Main class
- `pyhysplit/engine.py` - Integration
- `pyhysplit/models.py` - Configuration

**Tests**:
- `tests/integration/test_dynamic_subgrid.py` - Test suite
- `tests/integration/dynamic_subgrid_results.json` - Results

**Documentation**:
- `DYNAMIC_SUBGRID_TEST_RESULTS.md` - Detailed results
- `DYNAMIC_SUBGRID_IMPLEMENTATION_SUMMARY.md` - Implementation details
- `NEXT_STEPS_DATA_LOADING.md` - Future work
- `SESSION_DYNAMIC_SUBGRID_SUMMARY.md` - Session summary

## Quick Commands

```bash
# Test detection
python tests/integration/test_dynamic_subgrid.py

# View expansion history
python -c "
import json
with open('tests/integration/dynamic_subgrid_results.json') as f:
    results = json.load(f)
    for r in results:
        print(f\"{r['name']}: {r['expansion_count']} expansions\")
"

# Check logs
grep "Subgrid expansion" tests/integration/*.log
```

## Expected Output

```
2026-02-14 21:32:24 - pyhysplit.dynamic_subgrid - INFO - DynamicSubgrid initialized: bounds=(105.0, 150.0, 20.0, 50.0), mgmin=10, threshold=5.0°
2026-02-14 21:32:24 - pyhysplit.engine - INFO - Dynamic subgrid enabled for HYSPLIT-style boundary expansion
2026-02-14 21:32:24 - pyhysplit.dynamic_subgrid - INFO - Subgrid expansion #1: (110.60, 37.91), wind=39.8 m/s
2026-02-14 21:32:24 - pyhysplit.dynamic_subgrid - INFO -   Old bounds: (105.0, 150.0, 20.0, 50.0)
2026-02-14 21:32:24 - pyhysplit.dynamic_subgrid - INFO -   New bounds: (102.5, 150.0, 20.0, 50.0)
```

## FAQ

**Q: Does this fix high-latitude boundary errors?**
A: Not yet. Detection is implemented, but data loading is needed.

**Q: How much does it slow down calculations?**
A: Minimal impact (~1-2% overhead for boundary checks).

**Q: Can I disable it?**
A: Yes, set `enable_dynamic_subgrid=False` (default).

**Q: Does it work with all vertical motion modes?**
A: Yes, it's independent of vertical motion mode.

**Q: How do I know if expansion is needed?**
A: Check the logs or `get_expansion_stats()` after running.

---

**Last Updated**: 2026-02-14
**Status**: Detection implemented, data loading pending
**Quick Test**: `python tests/integration/test_dynamic_subgrid.py`
