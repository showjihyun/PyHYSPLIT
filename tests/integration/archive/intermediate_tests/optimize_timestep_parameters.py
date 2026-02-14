"""시간 스텝 파라미터 최적화 (dt_max, tratio)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import netCDF4
from datetime import datetime
from pyhysplit.models import StartLocation, SimulationConfig, MetData
from pyhysplit.engine import TrajectoryEngine
from math import radians, sin, cos, sqrt, atan2
import time

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

# 테스트 위치 (대표 1개만 사용하여 빠른 테스트)
test_locations = {
    '서울': (37.5, 127.0),
}

def read_hysplit_trajectory(location_name):
    """tdump 파일에서 전체 궤적 읽기"""
    tdump_file = f"tests/integration/hysplit_web_data/tdump_{location_name}.txt"
    trajectory = []
    try:
        with open(tdump_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[8:]:
                parts = line.split()
                if len(parts) >= 13:
                    try:
                        age = float(parts[8])
                        lat = float(parts[9])
                        lon = float(parts[10])
                        height = float(parts[11])
                        pressure = float(parts[12])
                        trajectory.append({
                            'age': age,
                            'lat': lat,
                            'lon': lon,
                            'height': height,
                            'pressure': pressure
                        })
                    except (ValueError, IndexError):
                        continue
    except Exception as e:
        pass
    return trajectory

def test_parameters(dt_max, tratio):
    """특정 파라미터 조합 테스트"""
    results = []
    
    for name, (lat, lon) in test_locations.items():
        pressure = 850.0
        
        hysplit_traj = read_hysplit_trajectory(name)
        if not hysplit_traj:
            continue
        
        start_loc = StartLocation(lat=lat, lon=lon, height=pressure, height_type="pressure")
        config = SimulationConfig(
            start_time=datetime(2026, 2, 14, 0, 0),
            num_start_locations=1,
            start_locations=[start_loc],
            total_run_hours=-24,
            vertical_motion=0,
            model_top=10000.0,
            met_files=[],
            turbulence_on=False,
            dt_max=dt_max,
            tratio=tratio,
            auto_vertical_mode=True,
        )
        
        try:
            engine = TrajectoryEngine(config, met_data)
            trajectory = engine.run(output_interval_s=3600.0)[0]
            
            # 오차 계산
            horizontal_errors = []
            pressure_errors = []
            
            for i in range(min(len(trajectory), len(hysplit_traj))):
                py_lat, py_lon = trajectory[i][1], trajectory[i][2]
                py_p = trajectory[i][3]
                hy_lat, hy_lon = hysplit_traj[i]['lat'], hysplit_traj[i]['lon']
                hy_p = hysplit_traj[i]['pressure']
                
                h_error = haversine(py_lat, py_lon, hy_lat, hy_lon)
                p_error = abs(py_p - hy_p)
                
                horizontal_errors.append(h_error)
                pressure_errors.append(p_error)
            
            results.append({
                'name': name,
                'h_error': np.mean(horizontal_errors),
                'p_error': np.mean(pressure_errors),
            })
            
        except Exception as e:
            pass
    
    if results:
        return {
            'h_error': np.mean([r['h_error'] for r in results]),
            'p_error': np.mean([r['p_error'] for r in results]),
            'count': len(results),
        }
    return None

print("\n" + "="*100)
print("  시간 스텝 파라미터 최적화")
print("="*100)

print("\n파라미터:")
print("  - dt_max: 최대 시간 스텝 (초)")
print("  - tratio: CFL 비율 (격자 셀 당 이동 비율)")
print()

print("현재 설정:")
print("  - dt_max = 15.0 s")
print("  - tratio = 0.75")
print()

# 파라미터 그리드 (빠른 테스트를 위해 축소)
dt_max_values = [10.0, 15.0, 20.0]
tratio_values = [0.75, 0.9]

print(f"테스트 조합: {len(dt_max_values)} dt_max × {len(tratio_values)} tratio = {len(dt_max_values) * len(tratio_values)} 조합")
print(f"각 조합당 {len(test_locations)}개 위치 테스트")
print(f"예상 소요 시간: ~{len(dt_max_values) * len(tratio_values) * len(test_locations) * 2} 초\n")

results_grid = []

for dt_max in dt_max_values:
    for tratio in tratio_values:
        print(f"Testing dt_max={dt_max:5.1f}s, tratio={tratio:.2f}...", end=" ")
        
        start_time = time.time()
        result = test_parameters(dt_max, tratio)
        elapsed = time.time() - start_time
        
        if result:
            results_grid.append({
                'dt_max': dt_max,
                'tratio': tratio,
                'h_error': result['h_error'],
                'p_error': result['p_error'],
                'time': elapsed,
            })
            print(f"H={result['h_error']:5.1f} km, P={result['p_error']:5.1f} hPa, t={elapsed:.1f}s")
        else:
            print("Failed")

# 결과 분석
print("\n" + "="*100)
print("  결과 분석")
print("="*100)

if results_grid:
    # 정렬: 수평 오차 → 압력 오차 순
    results_grid.sort(key=lambda x: (x['h_error'], x['p_error']))
    
    print(f"\n{'dt_max':>8} {'tratio':>7} {'H 오차':>10} {'P 오차':>10} {'시간':>8} {'순위':>6}")
    print("-"*100)
    
    for i, r in enumerate(results_grid[:10], 1):  # 상위 10개만 표시
        print(f"{r['dt_max']:>8.1f} {r['tratio']:>7.2f} {r['h_error']:>10.1f} {r['p_error']:>10.1f} {r['time']:>8.1f} {i:>6}")
    
    # 최적 조합
    best = results_grid[0]
    current = [r for r in results_grid if r['dt_max'] == 15.0 and r['tratio'] == 0.75][0]
    
    print("\n" + "="*100)
    print("  최적 파라미터")
    print("="*100)
    
    print(f"\n현재 설정 (dt_max=15.0, tratio=0.75):")
    print(f"  수평 오차: {current['h_error']:.1f} km")
    print(f"  압력 오차: {current['p_error']:.1f} hPa")
    print(f"  계산 시간: {current['time']:.1f} s")
    
    print(f"\n최적 설정 (dt_max={best['dt_max']:.1f}, tratio={best['tratio']:.2f}):")
    print(f"  수평 오차: {best['h_error']:.1f} km")
    print(f"  압력 오차: {best['p_error']:.1f} hPa")
    print(f"  계산 시간: {best['time']:.1f} s")
    
    h_improvement = ((current['h_error'] - best['h_error']) / current['h_error']) * 100
    p_improvement = ((current['p_error'] - best['p_error']) / current['p_error']) * 100
    time_change = ((best['time'] - current['time']) / current['time']) * 100
    
    print(f"\n개선:")
    print(f"  수평 오차: {h_improvement:+.1f}%")
    print(f"  압력 오차: {p_improvement:+.1f}%")
    print(f"  계산 시간: {time_change:+.1f}%")
    
    # 권장사항
    print("\n" + "="*100)
    print("  권장사항")
    print("="*100)
    
    if abs(h_improvement) < 5 and abs(p_improvement) < 5:
        print("\n현재 설정이 이미 최적에 가깝습니다.")
        print("시간 스텝 최적화로는 큰 개선이 어렵습니다.")
        print("\n다음 우선순위:")
        print("  1. Mode 3 압력 오차 개선 (저위도 위치)")
        print("  2. GFS 데이터 범위 확장 (베이징 경계 오류)")
        print("  3. 다른 알고리즘 개선 고려")
    elif h_improvement > 10 or p_improvement > 10:
        print(f"\n✅ 최적 파라미터로 변경 권장:")
        print(f"   dt_max = {best['dt_max']:.1f}")
        print(f"   tratio = {best['tratio']:.2f}")
        print(f"\n예상 개선: 수평 {h_improvement:+.1f}%, 압력 {p_improvement:+.1f}%")
    else:
        print(f"\n약간의 개선 가능 (수평 {h_improvement:+.1f}%, 압력 {p_improvement:+.1f}%)")
        print("하지만 계산 시간 증가를 고려하면 현재 설정 유지 권장")

else:
    print("\n❌ 테스트 실패")
