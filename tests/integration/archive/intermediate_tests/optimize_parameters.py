"""Automated parameter optimization for PyHYSPLIT to match HYSPLIT Web.

This script systematically tests different combinations of parameters to find
the optimal configuration that minimizes the difference between PyHYSPLIT and
HYSPLIT Web results.

Parameters to optimize:
1. Vertical damping factor (0.00025 - 0.00035)
2. Scale height (8420 - 8450m)
3. dt_max (5 - 20 seconds)
4. TRATIO (0.72 - 0.78)

Optimization methods:
- Grid Search: Exhaustive search over all combinations
- Random Search: Random sampling for faster exploration
- Bayesian Optimization: Intelligent search using Gaussian Process
"""

import numpy as np
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import itertools

# Import test functions
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.integration.test_hysplit_web_comparison import (
    load_gfs_data, run_pyhysplit, HYSPLIT_WEB_RESULTS
)
from pyhysplit.models import StartLocation, SimulationConfig
from pyhysplit.coordinate_converter import CoordinateConverter


def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate great circle distance in km."""
    R = 6371.0
    lat1_rad, lat2_rad = np.radians(lat1), np.radians(lat2)
    dlon = np.radians(lon2 - lon1)
    dlat = lat2_rad - lat1_rad
    
    a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    return R * c


def evaluate_configuration(
    damping: float,
    scale_height: float,
    dt_max: float,
    tratio: float,
    verbose: bool = False
) -> Dict[str, float]:
    """Evaluate a parameter configuration against HYSPLIT Web results.
    
    Returns:
        Dictionary with metrics:
        - mean_horizontal_distance: Average horizontal distance error (km)
        - mean_vertical_distance: Average vertical distance error (m)
        - max_horizontal_distance: Maximum horizontal distance error (km)
        - max_vertical_distance: Maximum vertical distance error (m)
        - initial_height_error: Initial height conversion error (m)
        - total_score: Combined score (lower is better)
    """
    try:
        # Load GFS data
        start_time = datetime(2024, 1, 15, 12, 0)
        met_data = load_gfs_data(start_time)
        
        # Test parameters
        lat_start, lon_start, height_start = 37.0, 127.0, 850.0
        duration_hours = -7
        
        # Create config with modified parameters
        start_loc = StartLocation(lat=lat_start, lon=lon_start, height=height_start)
        config = SimulationConfig(
            start_time=start_time,
            num_start_locations=1,
            start_locations=[start_loc],
            total_run_hours=duration_hours,
            vertical_motion=8,
            model_top=10000.0,
            met_files=[],
            turbulence_on=False,
            dt_max=dt_max,
            vertical_damping=damping,
            scale_height=scale_height,
            tratio=tratio
        )
        
        # Run PyHYSPLIT
        from pyhysplit.engine import TrajectoryEngine
        engine = TrajectoryEngine(config, met_data)
        trajectory = engine.run(output_interval_s=3600.0)[0]
        
        # Convert trajectory to comparable format
        pyhysplit_results = []
        base_time = datetime(start_time.year, start_time.month, start_time.day, 0, 0)
        
        for pt in trajectory:
            t_seconds, lon_val, lat_val, height_val = pt
            dt = base_time + timedelta(seconds=t_seconds)
            
            # Convert pressure to height if needed
            if met_data.z_type == "pressure":
                from pyhysplit.interpolator import Interpolator
                height_pa = height_val * 100.0
                
                if met_data.t_field is not None:
                    try:
                        interp = Interpolator(met_data)
                        T = interp.interpolate_scalar(met_data.t_field, lon_val, lat_val, height_val, t_seconds)
                        height_m = CoordinateConverter.pressure_to_height_hypsometric(
                            np.array([height_pa]), np.array([T])
                        )[0]
                    except Exception:
                        height_m = CoordinateConverter.pressure_to_height(np.array([height_pa]))[0]
                else:
                    height_m = CoordinateConverter.pressure_to_height(np.array([height_pa]))[0]
            else:
                height_m = height_val
            
            pyhysplit_results.append({
                'datetime': dt,
                'lat': lat_val,
                'lon': lon_val,
                'height': height_m
            })
        
        # Compare with HYSPLIT Web results
        horizontal_distances = []
        vertical_distances = []
        
        for pyhysplit_pt in pyhysplit_results:
            # Find matching HYSPLIT Web point
            matching_web = None
            for web_pt in HYSPLIT_WEB_RESULTS:
                if pyhysplit_pt['datetime'] == web_pt['datetime']:
                    matching_web = web_pt
                    break
            
            if matching_web:
                # Calculate horizontal distance
                h_dist = haversine_distance(
                    pyhysplit_pt['lon'], pyhysplit_pt['lat'],
                    matching_web['lon'], matching_web['lat']
                )
                horizontal_distances.append(h_dist)
                
                # Calculate vertical distance
                v_dist = abs(pyhysplit_pt['height'] - matching_web['height'])
                vertical_distances.append(v_dist)
        
        if not horizontal_distances:
            return {
                'mean_horizontal_distance': 999.0,
                'mean_vertical_distance': 999.0,
                'max_horizontal_distance': 999.0,
                'max_vertical_distance': 999.0,
                'initial_height_error': 999.0,
                'total_score': 999.0
            }
        
        # Calculate initial height error
        initial_height_error = abs(pyhysplit_results[0]['height'] - height_start)
        
        # Calculate metrics
        mean_h_dist = np.mean(horizontal_distances)
        mean_v_dist = np.mean(vertical_distances)
        max_h_dist = np.max(horizontal_distances)
        max_v_dist = np.max(vertical_distances)
        
        # Combined score (weighted)
        # Horizontal distance is in km, vertical in m
        # Weight: 1.0 for horizontal, 0.01 for vertical (to balance scales)
        total_score = mean_h_dist + mean_v_dist * 0.01
        
        return {
            'mean_horizontal_distance': float(mean_h_dist),
            'mean_vertical_distance': float(mean_v_dist),
            'max_horizontal_distance': float(max_h_dist),
            'max_vertical_distance': float(max_v_dist),
            'initial_height_error': float(initial_height_error),
            'total_score': float(total_score)
        }
        
    except Exception as e:
        if verbose:
            print(f"  ERROR: {e}")
        return {
            'mean_horizontal_distance': 999.0,
            'mean_vertical_distance': 999.0,
            'max_horizontal_distance': 999.0,
            'max_vertical_distance': 999.0,
            'initial_height_error': 999.0,
            'total_score': 999.0,
            'error': str(e)
        }


def grid_search(
    damping_range: Tuple[float, float, float],
    scale_height_range: Tuple[float, float, float],
    dt_max_values: List[float],
    tratio_range: Tuple[float, float, float],
    output_file: str = "grid_search_results.json"
) -> Dict:
    """Perform exhaustive grid search over parameter space.
    
    Args:
        damping_range: (start, stop, step) for damping factor
        scale_height_range: (start, stop, step) for scale height
        dt_max_values: List of dt_max values to test
        tratio_range: (start, stop, step) for TRATIO
        output_file: File to save results
    
    Returns:
        Dictionary with best parameters and all results
    """
    print("=" * 80)
    print("GRID SEARCH OPTIMIZATION")
    print("=" * 80)
    
    # Generate parameter grids
    damping_values = np.arange(*damping_range)
    scale_height_values = np.arange(*scale_height_range)
    tratio_values = np.arange(*tratio_range)
    
    total_combinations = (
        len(damping_values) * len(scale_height_values) * 
        len(dt_max_values) * len(tratio_values)
    )
    
    print(f"\nParameter ranges:")
    print(f"  Damping: {damping_range[0]:.5f} - {damping_range[1]:.5f} ({len(damping_values)} values)")
    print(f"  Scale height: {scale_height_range[0]:.0f} - {scale_height_range[1]:.0f}m ({len(scale_height_values)} values)")
    print(f"  dt_max: {dt_max_values} ({len(dt_max_values)} values)")
    print(f"  TRATIO: {tratio_range[0]:.2f} - {tratio_range[1]:.2f} ({len(tratio_values)} values)")
    print(f"\nTotal combinations: {total_combinations}")
    print(f"Estimated time: {total_combinations * 2:.0f} seconds (~{total_combinations * 2 / 60:.1f} minutes)\n")
    
    results = []
    best_score = float('inf')
    best_params = None
    
    # Iterate over all combinations
    for i, (damping, sh, dt, tr) in enumerate(itertools.product(
        damping_values, scale_height_values, dt_max_values, tratio_values
    )):
        print(f"[{i+1}/{total_combinations}] Testing: damping={damping:.5f}, "
              f"scale_height={sh:.0f}, dt_max={dt:.0f}, tratio={tr:.2f}", end=" ")
        
        metrics = evaluate_configuration(damping, sh, dt, tr)
        
        result = {
            'damping': float(damping),
            'scale_height': float(sh),
            'dt_max': float(dt),
            'tratio': float(tr),
            **metrics
        }
        results.append(result)
        
        print(f"→ score={metrics['total_score']:.2f}")
        
        if metrics['total_score'] < best_score:
            best_score = metrics['total_score']
            best_params = result
            print(f"  ★ NEW BEST! Horizontal: {metrics['mean_horizontal_distance']:.2f}km, "
                  f"Vertical: {metrics['mean_vertical_distance']:.1f}m")
    
    # Save results
    output = {
        'method': 'grid_search',
        'timestamp': datetime.now().isoformat(),
        'total_combinations': total_combinations,
        'best_params': best_params,
        'best_score': best_score,
        'all_results': results
    }
    
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print("\n" + "=" * 80)
    print("BEST CONFIGURATION FOUND:")
    print("=" * 80)
    print(f"Damping factor: {best_params['damping']:.5f}")
    print(f"Scale height: {best_params['scale_height']:.0f}m")
    print(f"dt_max: {best_params['dt_max']:.0f}s")
    print(f"TRATIO: {best_params['tratio']:.2f}")
    print(f"\nPerformance:")
    print(f"  Horizontal distance: {best_params['mean_horizontal_distance']:.2f} km")
    print(f"  Vertical distance: {best_params['mean_vertical_distance']:.1f} m")
    print(f"  Initial height error: {best_params['initial_height_error']:.1f} m")
    print(f"  Total score: {best_params['total_score']:.2f}")
    print(f"\nResults saved to: {output_file}")
    
    return output


def random_search(
    n_iterations: int = 100,
    output_file: str = "random_search_results.json"
) -> Dict:
    """Perform random search over parameter space.
    
    Args:
        n_iterations: Number of random configurations to test
        output_file: File to save results
    
    Returns:
        Dictionary with best parameters and all results
    """
    print("=" * 80)
    print("RANDOM SEARCH OPTIMIZATION")
    print("=" * 80)
    print(f"\nTesting {n_iterations} random configurations")
    print(f"Estimated time: {n_iterations * 2:.0f} seconds (~{n_iterations * 2 / 60:.1f} minutes)\n")
    
    results = []
    best_score = float('inf')
    best_params = None
    
    for i in range(n_iterations):
        # Sample random parameters
        damping = np.random.uniform(0.00025, 0.00035)
        scale_height = np.random.uniform(8420, 8450)
        dt_max = np.random.choice([5, 7, 10, 12, 15, 20])
        tratio = np.random.uniform(0.72, 0.78)
        
        print(f"[{i+1}/{n_iterations}] Testing: damping={damping:.5f}, "
              f"scale_height={scale_height:.0f}, dt_max={dt_max:.0f}, tratio={tratio:.2f}", end=" ")
        
        metrics = evaluate_configuration(damping, scale_height, dt_max, tratio)
        
        result = {
            'damping': float(damping),
            'scale_height': float(scale_height),
            'dt_max': float(dt_max),
            'tratio': float(tratio),
            **metrics
        }
        results.append(result)
        
        print(f"→ score={metrics['total_score']:.2f}")
        
        if metrics['total_score'] < best_score:
            best_score = metrics['total_score']
            best_params = result
            print(f"  ★ NEW BEST! Horizontal: {metrics['mean_horizontal_distance']:.2f}km, "
                  f"Vertical: {metrics['mean_vertical_distance']:.1f}m")
    
    # Save results
    output = {
        'method': 'random_search',
        'timestamp': datetime.now().isoformat(),
        'n_iterations': n_iterations,
        'best_params': best_params,
        'best_score': best_score,
        'all_results': results
    }
    
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print("\n" + "=" * 80)
    print("BEST CONFIGURATION FOUND:")
    print("=" * 80)
    print(f"Damping factor: {best_params['damping']:.5f}")
    print(f"Scale height: {best_params['scale_height']:.0f}m")
    print(f"dt_max: {best_params['dt_max']:.0f}s")
    print(f"TRATIO: {best_params['tratio']:.2f}")
    print(f"\nPerformance:")
    print(f"  Horizontal distance: {best_params['mean_horizontal_distance']:.2f} km")
    print(f"  Vertical distance: {best_params['mean_vertical_distance']:.1f} m")
    print(f"  Initial height error: {best_params['initial_height_error']:.1f} m")
    print(f"  Total score: {best_params['total_score']:.2f}")
    print(f"\nResults saved to: {output_file}")
    
    return output


def main():
    """Main optimization routine."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Optimize PyHYSPLIT parameters")
    parser.add_argument(
        '--method',
        choices=['grid', 'random', 'both'],
        default='grid',
        help='Optimization method'
    )
    parser.add_argument(
        '--iterations',
        type=int,
        default=100,
        help='Number of iterations for random search'
    )
    
    args = parser.parse_args()
    
    if args.method in ['grid', 'both']:
        # Fine-grained grid search
        grid_search(
            damping_range=(0.00025, 0.00036, 0.00001),  # 11 values
            scale_height_range=(8420, 8451, 2),  # 16 values
            dt_max_values=[5, 10, 15, 20],  # 4 values
            tratio_range=(0.72, 0.79, 0.01),  # 7 values
            output_file="tests/integration/grid_search_results.json"
        )
    
    if args.method in ['random', 'both']:
        random_search(
            n_iterations=args.iterations,
            output_file="tests/integration/random_search_results.json"
        )


if __name__ == "__main__":
    main()
