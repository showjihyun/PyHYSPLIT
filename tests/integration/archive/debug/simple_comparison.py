"""Simple comparison between PyHYSPLIT and HYSPLIT Web results."""

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, '/workspaces/pyhysplit')

from pyhysplit.engine import TrajectoryEngine
from pyhysplit.met_reader import NetCDFReader
from pyhysplit.models import SimulationConfig, StartLocation


def main():
    """Compare PyHYSPLIT with HYSPLIT Web."""
    
    # Load HYSPLIT Web results (from endpoints file)
    web_file = Path("tests/integration/hysplit_trajectory_endpoints.txt")
    web_points = []
    
    with open(web_file) as f:
        lines = f.readlines()
    
    # Parse trajectory points (skip header lines)
    for line in lines:
        parts = line.split()
        if len(parts) >= 13 and parts[0].isdigit() and parts[1].isdigit():
            # Format: traj# particle# YY MM DD HH MM age age_frac lat lon height pressure
            lat = float(parts[9])
            lon = float(parts[10])
            height = float(parts[11])
            age = float(parts[7])
            web_points.append({'lat': lat, 'lon': lon, 'height': height, 'age': age})
    
    print(f"\n{'='*80}")
    print(f"  HYSPLIT Web vs PyHYSPLIT 비교")
    print(f"{'='*80}\n")
    
    print(f"HYSPLIT Web 결과:")
    print(f"  포인트 수: {len(web_points)}")
    if web_points:
        print(f"  시작: {web_points[0]['lat']}°N, {web_points[0]['lon']}°E, {web_points[0]['height']}m")
        print(f"  종료: {web_points[-1]['lat']}°N, {web_points[-1]['lon']}°E, {web_points[-1]['height']}m")
    print()
    
    # Run PyHYSPLIT
    print("PyHYSPLIT 실행 중...")
    
    # Load GFS data
    gfs_file = "tests/integration/gfs_cache/gfs_20260213_37.5_127.0_1h.nc"
    reader = NetCDFReader()
    met = reader.read(gfs_file)
    
    # Configuration
    start_loc = StartLocation(
        lat=web_points[0]['lat'],
        lon=web_points[0]['lon'],
        height=web_points[0]['height']
    )
    
    start_time = datetime(2026, 2, 13, 13, 0)
    
    config = SimulationConfig(
        start_time=start_time,
        num_start_locations=1,
        start_locations=[start_loc],
        total_run_hours=-7,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[],
        turbulence_on=False
    )
    
    # Run engine
    engine = TrajectoryEngine(config, met)
    trajectory = engine.run(output_interval_s=3600.0)[0]
    
    print(f"\nPyHYSPLIT 결과:")
    print(f"  포인트 수: {len(trajectory)}")
    
    if trajectory:
        t0, lon0, lat0, z0 = trajectory[0]
        t1, lon1, lat1, z1 = trajectory[-1]
        print(f"  시작: {lat0:.3f}°N, {lon0:.3f}°E, {z0:.1f}m")
        print(f"  종료: {lat1:.3f}°N, {lon1:.3f}°E, {z1:.1f}m")
    
    # Compare
    print(f"\n{'='*80}")
    print(f"  비교 결과")
    print(f"{'='*80}\n")
    
    print(f"포인트 수:")
    print(f"  HYSPLIT Web: {len(web_points)}")
    print(f"  PyHYSPLIT: {len(trajectory)}")
    print()
    
    if len(trajectory) >= 2:
        # Compare endpoints
        t1, lon1, lat1, z1 = trajectory[-1]
        web_end = web_points[-1]
        
        lat_diff = abs(lat1 - web_end['lat'])
        lon_diff = abs(lon1 - web_end['lon'])
        height_diff = abs(z1 - web_end['height'])
        
        # Haversine distance
        R = 6371  # km
        dlat = np.radians(web_end['lat'] - lat1)
        dlon = np.radians(web_end['lon'] - lon1)
        a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(web_end['lat'])) * np.sin(dlon/2)**2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
        dist_km = R * c
        
        print(f"종료점 차이:")
        print(f"  위도: {lat_diff:.6f}° ({lat_diff * 111:.2f} km)")
        print(f"  경도: {lon_diff:.6f}° ({lon_diff * 111 * np.cos(np.radians(lat1)):.2f} km)")
        print(f"  수평 거리: {dist_km:.2f} km")
        print(f"  고도: {height_diff:.1f}m")
        print()
        
        # Print all points
        print("모든 포인트:")
        print(f"{'Index':>5} {'PyHYSPLIT Lat':>15} {'Web Lat':>15} {'Lat Diff':>15} {'PyHYSPLIT Lon':>15} {'Web Lon':>15} {'Lon Diff':>15}")
        print("-" * 110)
        
        for i in range(min(len(trajectory), len(web_points))):
            t, lon, lat, z = trajectory[i]
            web_pt = web_points[i]
            lat_diff = lat - web_pt['lat']
            lon_diff = lon - web_pt['lon']
            print(f"{i:>5} {lat:>15.6f} {web_pt['lat']:>15.6f} {lat_diff:>15.6f} {lon:>15.6f} {web_pt['lon']:>15.6f} {lon_diff:>15.6f}")

if __name__ == "__main__":
    main()
