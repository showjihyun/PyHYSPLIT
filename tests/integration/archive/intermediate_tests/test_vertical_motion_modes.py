"""수직 속도 모드 비교 테스트"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import netCDF4
from datetime import datetime
from pyhysplit.models import StartLocation, SimulationConfig, MetData
from pyhysplit.engine import TrajectoryEngine

# GFS 데이터 로드
ds = netCDF4.Dataset('tests/integration/gfs_cache/gfs_eastasia_24h_real.nc')

u_data = np.array(ds.variables['u'][:])
v_data = np.array(ds.variables['v'][:])
omega_data = np.array(ds.variables['w'][:])
t_data = np.array(ds.variables['t'][:])

lat_grid = np.array(ds.variables['latitude'][:])
lon_grid = np.array(ds.variables['longitude'][:])
lev_grid = np.array(ds.variables['level'][:])
time_grid = np.array(ds.variables['time'][:])

ds.close()

# 시간 그리드 정렬
if time_grid[0] > time_grid[-1]:
    time_indices = np.argsort(time_grid)
    time_grid = time_grid[time_indices]
    u_data = u_data[time_indices]
    v_data = v_data[time_indices]
    omega_data = omega_data[time_indices]
    t_data = t_data[time_indices]

# Omega를 hPa/s로 변환
w_data = omega_data / 100.0

met_data = MetData(
    u=u_data, v=v_data, w=w_data, t_field=t_data,
    lat_grid=lat_grid, lon_grid=lon_grid,
    z_grid=lev_grid, t_grid=time_grid,
    z_type="pressure", source="GFS_NC"
)

print("="*80)
print("  수직 속도 모드 비교 테스트")
print("="*80)

# 서울 테스트
lat, lon, pressure = 37.5, 127.0, 850.0

# HYSPLIT Web 결과 (참조)
hysplit_results = [
    {'age': 0.0, 'lat': 37.500, 'lon': 127.000, 'pressure': 906.3},
    {'age': -1.0, 'lat': 37.447, 'lon': 126.763, 'pressure': 909.1},
    {'age': -2.0, 'lat': 37.358, 'lon': 126.530, 'pressure': 914.2},
    {'age': -3.0, 'lat': 37.246, 'lon': 126.313, 'pressure': 917.4},
    {'age': -4.0, 'lat': 37.129, 'lon': 126.100, 'pressure': 920.9},
    {'age': -5.0, 'lat': 37.004, 'lon': 125.887, 'pressure': 923.6},
    {'age': -6.0, 'lat': 36.859, 'lon': 125.681, 'pressure': 924.1},
    {'age': -7.0, 'lat': 36.687, 'lon': 125.490, 'pressure': 926.5},
    {'age': -8.0, 'lat': 36.491, 'lon': 125.300, 'pressure': 931.9},
]

modes_to_test = [
    (0, "Data vertical velocity (no damping)"),
    (1, "Isodensity (constant density surfaces)"),
    (3, "Isentropic (constant potential temperature)"),
    (7, "Horizontal averaging for temporal consistency"),
    (8, "Damped vertical velocity (default damping=1.0)"),
]

# Damping 값들도 테스트 (multipliers: 1.0 = full velocity, 0.5 = half velocity)
damping_values = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.3, 0.1]

print(f"\n테스트 위치: {lat}°N, {lon}°E, {pressure} hPa")
print(f"HYSPLIT Web 8시간 후: {hysplit_results[-1]['lat']:.3f}°N, {hysplit_results[-1]['lon']:.3f}°E, {hysplit_results[-1]['pressure']:.1f} hPa")

from math import radians, sin, cos, sqrt, atan2

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1_rad, lat2_rad = radians(lat1), radians(lat2)
    dlon = radians(lon2 - lon1)
    dlat = lat2_rad - lat1_rad
    a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

results = []

# Test all modes
for mode, description in modes_to_test:
    print(f"\n{'='*80}")
    print(f"  Mode {mode}: {description}")
    print(f"{'='*80}")
    
    start_loc = StartLocation(lat=lat, lon=lon, height=pressure, height_type="pressure")
    
    config = SimulationConfig(
        start_time=datetime(2026, 2, 14, 0, 0),
        num_start_locations=1,
        start_locations=[start_loc],
        total_run_hours=-8,
        vertical_motion=mode,
        model_top=10000.0,
        met_files=[],
        turbulence_on=False,
        dt_max=15.0,
        tratio=0.75
    )
    
    engine = TrajectoryEngine(config, met_data)
    trajectory = engine.run(output_interval_s=3600.0)[0]
    
    if len(trajectory) >= 9:
        final = trajectory[8]
        h_error = haversine(final[2], final[1], hysplit_results[-1]['lat'], hysplit_results[-1]['lon'])
        p_error = abs(final[3] - hysplit_results[-1]['pressure'])
        
        print(f"  8시간 후: {final[2]:.3f}°N, {final[1]:.3f}°E, {final[3]:.1f} hPa")
        print(f"  수평 오차: {h_error:.2f} km")
        print(f"  압력 오차: {p_error:.1f} hPa")
        
        results.append({
            'mode': mode,
            'damping': 0.0,
            'h_error': h_error,
            'p_error': p_error,
            'final_pressure': final[3]
        })

# Mode 8 with different damping values (only test Mode 8 variations)
print(f"\n{'='*80}")
print(f"  Mode 8 추가 테스트: 다양한 damping 값")
print(f"{'='*80}")

for damping in damping_values:
    config8 = SimulationConfig(
        start_time=datetime(2026, 2, 14, 0, 0),
        num_start_locations=1,
        start_locations=[start_loc],
        total_run_hours=-8,
        vertical_motion=8,
        model_top=10000.0,
        met_files=[],
        turbulence_on=False,
        dt_max=15.0,
        tratio=0.75,
        vertical_damping=damping
    )
    
    engine8 = TrajectoryEngine(config8, met_data)
    trajectory8 = engine8.run(output_interval_s=3600.0)[0]
    
    if len(trajectory8) >= 9:
        final8 = trajectory8[8]
        h_error8 = haversine(final8[2], final8[1], hysplit_results[-1]['lat'], hysplit_results[-1]['lon'])
        p_error8 = abs(final8[3] - hysplit_results[-1]['pressure'])
        
        print(f"\n  Damping = {damping:.4f}:")
        print(f"    8시간 후: {final8[2]:.3f}°N, {final8[1]:.3f}°E, {final8[3]:.1f} hPa")
        print(f"    수평 오차: {h_error8:.2f} km")
        print(f"    압력 오차: {p_error8:.1f} hPa")
        
        results.append({
            'mode': 8,
            'damping': damping,
            'h_error': h_error8,
            'p_error': p_error8,
            'final_pressure': final8[3]
        })

# 최적 결과 찾기
print(f"\n{'='*80}")
print(f"  결과 요약")
print(f"{'='*80}")

print(f"\n{'Mode':>6} {'Damping':>10} {'수평 오차(km)':>15} {'압력 오차(hPa)':>17} {'최종 압력(hPa)':>17}")
print("-"*80)

for r in results:
    print(f"{r['mode']:>6} {r['damping']:>10.4f} {r['h_error']:>15.2f} {r['p_error']:>17.1f} {r['final_pressure']:>17.1f}")

# 최적값 찾기
best_h = min(results, key=lambda x: x['h_error'])
best_p = min(results, key=lambda x: x['p_error'])
best_combined = min(results, key=lambda x: x['h_error'] + x['p_error']/10)

print(f"\n최적 설정:")
print(f"  수평 오차 최소: Mode {best_h['mode']}, Damping {best_h['damping']:.4f} → {best_h['h_error']:.2f} km")
print(f"  압력 오차 최소: Mode {best_p['mode']}, Damping {best_p['damping']:.4f} → {best_p['p_error']:.1f} hPa")
print(f"  종합 최적: Mode {best_combined['mode']}, Damping {best_combined['damping']:.4f}")

print(f"\n권장 설정:")
if best_combined['mode'] == 0:
    print(f"  vertical_motion=0 (Data vertical velocity)")
else:
    print(f"  vertical_motion=8, vertical_damping={best_combined['damping']:.4f}")
