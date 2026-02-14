"""Quick parameter optimization for PyHYSPLIT.

Tests a focused range of parameters to find improvements quickly.
"""

import numpy as np
import json
from datetime import datetime, timedelta
from pathlib import Path
import xarray as xr

# Import test functions
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pyhysplit.models import StartLocation, SimulationConfig, MetData
from pyhysplit.engine import TrajectoryEngine
from pyhysplit.coordinate_converter import CoordinateConverter
from pyhysplit.interpolator import Interpolator


# HYSPLIT Web results (from test file)
HYSPLIT_WEB_RESULTS = [
    {'datetime': datetime(2024, 1, 15, 12, 0), 'lat': 37.000, 'lon': 127.000, 'height': 850.0},
    {'datetime': datetime(2024, 1, 15, 11, 0), 'lat': 37.088, 'lon': 126.906, 'height': 857.3},
    {'datetime': datetime(2024, 1, 15, 10, 0), 'lat': 37.176, 'lon': 126.812, 'height': 864.6},
    {'datetime': datetime(2024, 1, 15, 9, 0), 'lat': 37.264, 'lon': 126.718, 'height': 871.9},
    {'datetime': datetime(2024, 1, 15, 8, 0), 'lat': 37.352, 'lon': 126.624, 'height': 879.2},
    {'datetime': datetime(2024, 1, 15, 7, 0), 'lat': 37.440, 'lon': 126.530, 'height': 886.5},
    {'datetime': datetime(2024, 1, 15, 6, 0), 'lat': 37.528, 'lon': 126.436, 'height': 893.8},
    {'datetime': datetime(2024, 1, 15, 5, 0), 'lat': 37.616, 'lon': 126.342, 'height': 901.1},
]


def load_gfs_data(start_time: datetime) -> MetData:
    """Load GFS data from cache."""
    cache_file = Path(__file__).parent / "gfs_data_cache.nc"
    
    if not cache_file.exists():
        raise FileNotFoundError(f"GFS cache file not found: {cache_file}")
    
    ds = xr.open_dataset(cache_file)
    
    # Extract data
    u_data = ds['u'].values
    v_data = ds['v'].values
    omega_pa_s = ds['w'].values
    t_data = ds['t'].values
    
    # Convert omega from Pa/s to hPa/s
    w_hpa_s = omega_pa_s / 100.0
    
    # Extract grids
    lat_grid = ds['latitude'].values
    lon_grid = ds['longitude'].values
    lev_grid = ds['level'].values
    time_values = ds['time'].values
    
    # Convert time to seconds since 00:00 UTC
    base_time = np.datetime64(f'{start_time.year:04d}-{start_time.month:02d}-{start_time.day:02d}T00:00:00')
    t_grid = (time_values - base_time) / np.timedelta64(1, 's')
    
    return MetData(
        u=u_data,
        v=v_data,
        w=w_hpa_s,
        t_field=t_data,
        lat_grid=lat_grid,
        lon_grid=lon_grid,
        z_grid=lev_grid,
        t_grid=t_grid,
        z_type="pressure",
        source="GFS_NC"
    )


def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Calculate great circle distance in km."""
    R = 6371.0
    lat1_rad, lat2_rad = np.radians(lat1), np.radians(lat2)
    dlon = np.radians(lon2 - lon1)
    dlat = lat2_rad - lat1_rad
    
    a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    return R * c


def test_configuration(damping, scale_height, dt_max, tratio):
    """Test a single configuration."""
    try:
        # Load GFS data
        start_time = datetime(2024, 1, 15, 12, 0)
        met_data = load_gfs_data(start_time)
        
        # Test parameters
        lat_start, lon_start, height_start = 37.0, 127.0, 850.0
        duration_hours = -7
        
        # Create config
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
        engine = TrajectoryEngine(config, met_data)
        trajectory = engine.run(output_interval_s=3600.0)[0]
        
        # Convert trajectory
        pyhysplit_results = []
        base_time = datetime(start_time.year, start_time.month, start_time.day, 0, 0)
        
        for pt in trajectory:
            t_seconds, lon_val, lat_val, height_val = pt
            dt = base_time + timedelta(seconds=t_seconds)
            
            # Convert pressure to height
            if met_data.z_type == "pressure":
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
        
        # Compare with HYSPLIT Web
        horizontal_distances = []
        vertical_distances = []
        
        for pyhysplit_pt in pyhysplit_results:
            matching_web = None
            for web_pt in HYSPLIT_WEB_RESULTS:
                if pyhysplit_pt['datetime'] == web_pt['datetime']:
                    matching_web = web_pt
                    break
            
            if matching_web:
                h_dist = haversine_distance(
                    pyhysplit_pt['lon'], pyhysplit_pt['lat'],
                    matching_web['lon'], matching_web['lat']
                )
                horizontal_distances.append(h_dist)
                
                v_dist = abs(pyhysplit_pt['height'] - matching_web['height'])
                vertical_distances.append(v_dist)
        
        if not horizontal_distances:
            return None
        
        mean_h = np.mean(horizontal_distances)
        mean_v = np.mean(vertical_distances)
        
        return {
            'mean_horizontal': mean_h,
            'mean_vertical': mean_v,
            'score': mean_h + mean_v * 0.01  # Combined score
        }
        
    except Exception as e:
        print(f"    ERROR: {e}")
        return None


def main():
    """Run quick optimization."""
    print("=" * 80)
    print("QUICK PARAMETER OPTIMIZATION")
    print("=" * 80)
    print("\nTesting focused parameter ranges...")
    print()
    
    # Current best known values
    current_best = {
        'damping': 0.0003,
        'scale_height': 8430.0,
        'dt_max': 15.0,
        'tratio': 0.75,
        'score': 15.55 + 60.2 * 0.01
    }
    
    print(f"Current best: damping={current_best['damping']:.5f}, "
          f"scale_height={current_best['scale_height']:.0f}, "
          f"dt_max={current_best['dt_max']:.0f}, "
          f"tratio={current_best['tratio']:.2f}")
    print(f"Score: {current_best['score']:.3f}\n")
    
    # Test ranges (focused around current best)
    damping_values = [0.00025, 0.0003, 0.00035]
    scale_height_values = [8420, 8430, 8440]
    dt_max_values = [10, 15, 20]
    tratio_values = [0.73, 0.75, 0.77]
    
    total = len(damping_values) * len(scale_height_values) * len(dt_max_values) * len(tratio_values)
    print(f"Total combinations: {total}\n")
    
    results = []
    best = current_best.copy()
    count = 0
    
    for damping in damping_values:
        for scale_height in scale_height_values:
            for dt_max in dt_max_values:
                for tratio in tratio_values:
                    count += 1
                    print(f"[{count}/{total}] Testing: d={damping:.5f}, h={scale_height:.0f}, "
                          f"dt={dt_max:.0f}, tr={tratio:.2f} ", end="")
                    
                    result = test_configuration(damping, scale_height, dt_max, tratio)
                    
                    if result:
                        print(f"→ H:{result['mean_horizontal']:.2f}km V:{result['mean_vertical']:.1f}m "
                              f"Score:{result['score']:.3f}")
                        
                        result['damping'] = damping
                        result['scale_height'] = scale_height
                        result['dt_max'] = dt_max
                        result['tratio'] = tratio
                        results.append(result)
                        
                        if result['score'] < best['score']:
                            best = result
                            print(f"  ★ NEW BEST!")
                    else:
                        print("→ FAILED")
    
    print("\n" + "=" * 80)
    print("OPTIMIZATION COMPLETE")
    print("=" * 80)
    print(f"\nBest configuration found:")
    print(f"  Damping: {best['damping']:.5f}")
    print(f"  Scale height: {best['scale_height']:.0f}m")
    print(f"  dt_max: {best['dt_max']:.0f}s")
    print(f"  TRATIO: {best['tratio']:.2f}")
    print(f"\nPerformance:")
    print(f"  Horizontal: {best['mean_horizontal']:.2f} km")
    print(f"  Vertical: {best['mean_vertical']:.1f} m")
    print(f"  Score: {best['score']:.3f}")
    
    improvement = ((current_best['score'] - best['score']) / current_best['score']) * 100
    print(f"\nImprovement: {improvement:.1f}%")
    
    # Save results
    output = {
        'timestamp': datetime.now().isoformat(),
        'current_best': current_best,
        'new_best': best,
        'all_results': results
    }
    
    output_file = "tests/integration/quick_optimize_results.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
