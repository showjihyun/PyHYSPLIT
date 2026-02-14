"""시간 스텝 크기 최적화 테스트"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import netCDF4
from datetime import datetime
from pyhysplit.models import StartLocation, SimulationConfig, MetData
from pyhysplit.engine import TrajectoryEngine
from math import radians, sin, cos, sqrt, atan2

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1_rad, lat2_rad = radians(lat1), radians(lat2)
    dlon = radians(lon2 - lon1)
    dlat = lat2_rad - lat1_rad
    a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

# GFS 데이터 로드
print("Loading GFS data...")
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

# 서울 테스트
lat, lon, pressure = 37.5, 127.0, 850.0

# HYSPLIT Web 참조 (8시간 후)
hysplit_final = {'lat': 36.491, 'lon': 125.300, 'pressure': 931.9}

print("="*80)
print("  시간 스텝 크기 최적화 테스트")
print("="*80)
print(f"시작: {lat}°N, {lon}°E, {pressure} hPa")
print(f"HYSPLIT Web 8시간 후: {hysplit_final['lat']}°N, {hysplit_final['lon']}°E, {hysplit_final['pressure']} hPa")
print("="*80)

# 테스트할 파라미터 조합
dt_max_values = [5.0, 10.0, 15.0, 20.0, 30.0]
tratio_values = [0.5, 0.75, 0.9]

results = []

for dt_max in dt_max_values:
    for tratio in tratio_values:
        start_loc = StartLocation(lat=lat, lon=lon, height=pressure, height_type="pressure")
        
        config = SimulationConfig(
            start_time=datetime(2026, 2, 14, 0, 0),
            num_start_locations=1,
            start_locations=[start_loc],
            total_run_hours=-8,
            vertical_motion=0,
            model_top=10000.0,
            met_files=[],
            turbulence_on=False,
            dt_max=dt_max,
            tratio=tratio
        )
        
        engine = TrajectoryEngine(config, met_data)
        trajectory = engine.run(output_interval_s=3600.0)[0]
        
        if len(trajectory) >= 9:
            final = trajectory[8]
            h_error = haversine(final[2], final[1], hysplit_final['lat'], hysplit_final['lon'])
            p_error = abs(final[3] - hysplit_final['pressure'])
            
            results.append({
                'dt_max': dt_max,
                'tratio': tratio,
                'lat': final[2],
                'lon': final[1],
                'pressure': final[3],
                'h_error': h_error,
                'p_error': p_error,
                'combined': h_error + p_error / 10.0  # 가중 조합
            })
            
            print(f"dt_max={dt_max:5.1f}s, tratio={tratio:.2f}: "
                  f"H_err={h_error:6.2f}km, P_err={p_error:5.1f}hPa, "
                  f"Final=({final[2]:.3f}°N, {final[1]:.3f}°E, {final[3]:.1f}hPa)")

print(f"\n{'='*80}")
print("  결과 요약")
print(f"{'='*80}")

print(f"\n{'dt_max':>8} {'tratio':>8} {'H_Err(km)':>12} {'P_Err(hPa)':>12} {'Combined':>12}")
print("-"*80)
for r in sorted(results, key=lambda x: x['combined']):
    print(f"{r['dt_max']:>8.1f} {r['tratio']:>8.2f} {r['h_error']:>12.2f} {r['p_error']:>12.1f} {r['combined']:>12.2f}")

best = min(results, key=lambda x: x['combined'])
print(f"\n최적 설정:")
print(f"  dt_max = {best['dt_max']:.1f}s")
print(f"  tratio = {best['tratio']:.2f}")
print(f"  수평 오차: {best['h_error']:.2f} km")
print(f"  압력 오차: {best['p_error']:.1f} hPa")
print(f"  최종 위치: {best['lat']:.3f}°N, {best['lon']:.3f}°E, {best['pressure']:.1f} hPa")
