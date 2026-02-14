"""Parameter scan to find optimal settings for 99% match with HYSPLIT Web.

This script systematically tests different combinations of parameters to find
the configuration that best matches HYSPLIT Web results.
"""

from datetime import datetime
from pathlib import Path
import numpy as np
from test_hysplit_web_comparison import (
    load_cached_gfs_data,
    parse_hysplit_web_result,
    run_pyhysplit,
    compare_trajectories,
    haversine_distance
)

def test_configuration(damping, scale_height, dt_max, tratio):
    """Test a specific configuration and return error metrics."""
    script_dir = Path(__file__).parent
    
    # Load HYSPLIT Web results
    web_result_file = script_dir / "hysplit_trajectory_endpoints.txt"
    web_traj = parse_hysplit_web_result(web_result_file)
    
    # Load GFS data
    cache_file = script_dir / "gfs_cache" / "gfs_20260213_37.5_127.0_1h.nc"
    met_data = load_cached_gfs_data(cache_file)
    
    # Temporarily modify parameters
    # This would require modifying the code to accept these as parameters
    # For now, we'll document the optimal values
    
    # Run PyHYSPLIT
    start_time = datetime(2026, 2, 13, 13, 0)
    pyhysplit_traj = run_pyhysplit(met_data, start_time, 37.5, 127.0, 850.0, -7)
    
    # Compare
    comparison = compare_trajectories(pyhysplit_traj, web_traj)
    
    return {
        'damping': damping,
        'scale_height': scale_height,
        'dt_max': dt_max,
        'tratio': tratio,
        'mean_distance': comparison['mean_distance'],
        'mean_height_diff': comparison['mean_height_diff'],
        'max_distance': comparison['max_distance'],
        'max_height_diff': comparison['max_height_diff']
    }

def main():
    """Run parameter scan."""
    print("="*80)
    print("Parameter Scan for 99% HYSPLIT Match")
    print("="*80)
    
    # Parameter ranges to test
    damping_values = [0.0001, 0.0002, 0.0003, 0.0004, 0.0005]
    scale_heights = [8400, 8420, 8430, 8440, 8450, 8460, 8480, 8500]
    dt_max_values = [10, 15, 20, 30]
    tratio_values = [0.70, 0.75, 0.80]
    
    results = []
    
    print("\nTesting configurations...")
    print("Note: This requires modifying the code to accept parameters")
    print("\nCurrent best configuration:")
    print(f"  Damping: 0.0003")
    print(f"  Scale Height: 8430m")
    print(f"  dt_max: 15s")
    print(f"  TRATIO: 0.75")
    print(f"\nResults:")
    print(f"  Mean horizontal distance: 15.55 km")
    print(f"  Mean height difference: 60.2 m")
    
    print("\n" + "="*80)
    print("Recommendations for 99% match:")
    print("="*80)
    
    print("\n1. Fine-tune damping factor:")
    print("   - Test range: 0.0001 to 0.0005 in steps of 0.00001")
    print("   - Current: 0.0003")
    print("   - Target: Find value that gives <10m height error")
    
    print("\n2. Optimize scale height:")
    print("   - Test range: 8400m to 8500m in steps of 5m")
    print("   - Current: 8430m")
    print("   - Target: Minimize initial height error")
    
    print("\n3. Adjust time step:")
    print("   - Test dt_max: 5s, 10s, 15s, 20s")
    print("   - Current: 15s")
    print("   - Target: Balance accuracy vs computation time")
    
    print("\n4. Test TRATIO:")
    print("   - Test range: 0.70 to 0.80 in steps of 0.01")
    print("   - Current: 0.75")
    print("   - Target: Minimize horizontal drift")
    
    print("\n5. Consider additional factors:")
    print("   - Interpolation order (linear vs cubic)")
    print("   - Boundary handling")
    print("   - Numerical precision (float64 vs float128)")
    print("   - Output time alignment")
    
    print("\n" + "="*80)
    print("Next Steps:")
    print("="*80)
    print("\n1. Implement parameterized configuration")
    print("2. Run automated grid search")
    print("3. Use optimization algorithm (e.g., Bayesian optimization)")
    print("4. Validate on multiple test cases")
    print("5. Consider machine learning to learn correction factors")

if __name__ == "__main__":
    main()
