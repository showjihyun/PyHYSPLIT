"""Analyze remaining errors and propose targeted improvements.

This script analyzes the current error patterns to identify:
1. Which locations have the highest errors
2. Error patterns by latitude/region
3. Potential causes and solutions

Current state: 80% progress
- Direction match: 100% (8/8)
- Avg pressure error: 22.9 hPa (goal: <20 hPa, 85% achieved)
- Avg horizontal error: 43.31 km (goal: <20 km, 65% achieved)
"""

import json
import numpy as np
from pathlib import Path

def analyze_errors():
    """Analyze error patterns from test results."""
    
    # Load test results
    results_file = Path("tests/integration/multi_location_24h_results.json")
    if not results_file.exists():
        print("❌ Results file not found. Run multi_location_24h_comparison.py first.")
        return
    
    with open(results_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    print("=" * 80)
    print("REMAINING ERROR ANALYSIS - 80% Progress")
    print("=" * 80)
    print()
    
    # Analyze by location
    print("1. ERROR BY LOCATION")
    print("-" * 80)
    
    locations = []
    for loc_name, data in results.items():
        if loc_name == "summary":
            continue
        
        # Get trajectory data
        traj = data.get("trajectory", [])
        if not traj:
            continue
        
        # Calculate average errors (if comparison data exists)
        # For now, use distance traveled as proxy
        distances = [p.get("distance_km", 0) for p in traj]
        total_distance = sum(distances)
        
        lat = data.get("start_location", {}).get("lat", 0)
        lon = data.get("start_location", {}).get("lon", 0)
        
        locations.append({
            "name": loc_name,
            "lat": lat,
            "lon": lon,
            "distance": total_distance,
            "points": len(traj)
        })
    
    # Sort by latitude
    locations.sort(key=lambda x: x["lat"], reverse=True)
    
    print(f"{'Location':<12} {'Lat':>6} {'Lon':>7} {'Distance':>10} {'Points':>7}")
    print("-" * 80)
    for loc in locations:
        print(f"{loc['name']:<12} {loc['lat']:>6.1f} {loc['lon']:>7.1f} "
              f"{loc['distance']:>9.1f} km {loc['points']:>7}")
    
    print()
    print("2. LATITUDE PATTERN ANALYSIS")
    print("-" * 80)
    
    # Group by latitude bands
    high_lat = [l for l in locations if l["lat"] > 35]
    mid_lat = [l for l in locations if 30 <= l["lat"] <= 35]
    low_lat = [l for l in locations if l["lat"] < 30]
    
    print(f"High latitude (>35°N): {len(high_lat)} locations")
    print(f"  - Using Mode 7 (Spatially averaged)")
    print(f"  - Expected pressure error: ~15.6 hPa")
    print()
    
    print(f"Mid latitude (30-35°N): {len(mid_lat)} locations")
    print(f"  - Transition zone")
    print(f"  - Mode selection critical")
    print()
    
    print(f"Low latitude (<30°N): {len(low_lat)} locations")
    print(f"  - Using Mode 3 (Isentropic)")
    print(f"  - Expected pressure error: ~34.9 hPa ⚠️")
    print()
    
    print("3. IDENTIFIED ISSUES")
    print("-" * 80)
    
    issues = [
        {
            "priority": "HIGH",
            "issue": "Mode 3 Pressure Error",
            "description": "Low-latitude locations (Jeju, Shanghai, Taipei) have high pressure error",
            "current": "34.9 hPa average",
            "target": "<20 hPa",
            "gap": "74.5% of target",
            "impact": "Affects 3/8 locations (37.5%)"
        },
        {
            "priority": "HIGH",
            "issue": "Horizontal Error",
            "description": "All locations exceed horizontal error target",
            "current": "43.31 km average",
            "target": "<20 km",
            "gap": "216% of target",
            "impact": "Affects 8/8 locations (100%)"
        },
        {
            "priority": "MEDIUM",
            "issue": "Beijing Boundary Error",
            "description": "Trajectory exits GFS grid bounds",
            "current": "Grid boundary violation",
            "target": "Stay within bounds",
            "gap": "N/A",
            "impact": "Affects 1/8 locations (12.5%)"
        }
    ]
    
    for i, issue in enumerate(issues, 1):
        print(f"\n{i}. [{issue['priority']}] {issue['issue']}")
        print(f"   Description: {issue['description']}")
        print(f"   Current: {issue['current']}")
        print(f"   Target: {issue['target']}")
        print(f"   Gap: {issue['gap']}")
        print(f"   Impact: {issue['impact']}")
    
    print()
    print("4. PROPOSED SOLUTIONS")
    print("-" * 80)
    
    solutions = [
        {
            "issue": "Mode 3 Pressure Error",
            "approach": "Hybrid Mode Selection",
            "description": "Test alternative modes for low-latitude locations",
            "options": [
                "Option A: Use Mode 7 for all latitudes (simpler, consistent)",
                "Option B: Use Mode 0 (data velocity) for low latitudes",
                "Option C: Adjust latitude threshold (33.5°N → 30°N)",
                "Option D: Implement weighted blend between modes"
            ],
            "expected_improvement": "34.9 hPa → 20-25 hPa (30-40% improvement)",
            "effort": "Low (2-3 hours)",
            "risk": "Low (easy to revert)"
        },
        {
            "issue": "Horizontal Error",
            "approach": "Wind Field Analysis",
            "description": "Investigate wind interpolation and advection accuracy",
            "options": [
                "Option A: Analyze wind field gradients at error hotspots",
                "Option B: Test different CFL ratios (tratio)",
                "Option C: Implement sub-grid wind variability",
                "Option D: Add terrain-following corrections"
            ],
            "expected_improvement": "43.31 km → 30-35 km (20-30% improvement)",
            "effort": "Medium (5-8 hours)",
            "risk": "Medium (may affect stability)"
        },
        {
            "issue": "Beijing Boundary Error",
            "approach": "Expand GFS Data Range",
            "description": "Download wider geographic coverage",
            "options": [
                "Option A: Extend westward (110°E → 105°E)",
                "Option B: Add boundary reflection/absorption",
                "Option C: Implement trajectory termination handling"
            ],
            "expected_improvement": "Eliminate boundary violations",
            "effort": "Low (1-2 hours)",
            "risk": "Very Low (data download only)"
        }
    ]
    
    for i, sol in enumerate(solutions, 1):
        print(f"\n{i}. {sol['issue']}")
        print(f"   Approach: {sol['approach']}")
        print(f"   Description: {sol['description']}")
        print(f"   Options:")
        for opt in sol['options']:
            print(f"     - {opt}")
        print(f"   Expected: {sol['expected_improvement']}")
        print(f"   Effort: {sol['effort']}")
        print(f"   Risk: {sol['risk']}")
    
    print()
    print("5. RECOMMENDED NEXT STEPS")
    print("-" * 80)
    
    steps = [
        {
            "step": 1,
            "action": "Test Mode 7 for Low Latitudes",
            "rationale": "Quick test to see if Mode 7 works better than Mode 3",
            "command": "python tests/integration/test_mode7_all_locations.py",
            "time": "1 hour",
            "expected": "May reduce pressure error from 34.9 to 20-25 hPa"
        },
        {
            "step": 2,
            "action": "Expand GFS Data for Beijing",
            "rationale": "Simple fix for boundary error",
            "command": "python tests/integration/download_gfs_extended.py",
            "time": "1 hour",
            "expected": "Eliminate Beijing boundary violations"
        },
        {
            "step": 3,
            "action": "Analyze Wind Field Errors",
            "rationale": "Understand horizontal error sources",
            "command": "python tests/integration/analyze_wind_errors.py",
            "time": "3-4 hours",
            "expected": "Identify specific causes of horizontal error"
        },
        {
            "step": 4,
            "action": "Implement Targeted Fixes",
            "rationale": "Apply fixes based on wind error analysis",
            "command": "TBD based on analysis",
            "time": "5-10 hours",
            "expected": "Reduce horizontal error by 20-30%"
        }
    ]
    
    for step in steps:
        print(f"\nStep {step['step']}: {step['action']}")
        print(f"  Rationale: {step['rationale']}")
        print(f"  Command: {step['command']}")
        print(f"  Time: {step['time']}")
        print(f"  Expected: {step['expected']}")
    
    print()
    print("6. PROGRESS PROJECTION")
    print("-" * 80)
    
    projections = [
        {"stage": "Current", "progress": 80, "pressure": 22.9, "horizontal": 43.31},
        {"stage": "After Mode 7 test", "progress": 82, "pressure": 20.5, "horizontal": 43.31},
        {"stage": "After Beijing fix", "progress": 83, "pressure": 20.5, "horizontal": 43.31},
        {"stage": "After wind analysis", "progress": 85, "pressure": 20.5, "horizontal": 35.0},
        {"stage": "After targeted fixes", "progress": 90, "pressure": 18.0, "horizontal": 25.0},
    ]
    
    print(f"{'Stage':<25} {'Progress':>10} {'Pressure':>12} {'Horizontal':>12}")
    print("-" * 80)
    for proj in projections:
        print(f"{proj['stage']:<25} {proj['progress']:>9}% "
              f"{proj['pressure']:>10.1f} hPa {proj['horizontal']:>10.1f} km")
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print("Current State: 80% progress")
    print("  ✓ Direction match: 100% (8/8)")
    print("  ⚠ Pressure error: 22.9 hPa (target: <20 hPa, 85% achieved)")
    print("  ⚠ Horizontal error: 43.31 km (target: <20 km, 65% achieved)")
    print()
    print("Immediate Actions:")
    print("  1. Test Mode 7 for all locations (1 hour)")
    print("  2. Expand GFS data for Beijing (1 hour)")
    print("  3. Analyze wind field errors (3-4 hours)")
    print()
    print("Expected Progress: 80% → 85-90% (within 1-2 days)")
    print()
    print("To start: python tests/integration/test_mode7_all_locations.py")
    print("=" * 80)

if __name__ == "__main__":
    analyze_errors()
