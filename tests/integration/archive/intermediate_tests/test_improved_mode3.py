"""개선된 Mode 3 (Isentropic) 테스트"""
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

# 저위도 위치 (Mode 3 사용)
test_locations = {
    '제주': (33.5, 126.5),
    '상하이': (31.2, 121.5),
    '타이베이': (25.0, 121.5),
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

print("\n" + "="*100)
print("  개선된 Mode 3 (Isentropic) 테스트")
print("="*100)

print("\n변경 사항:")
print("  - 이전: return 0.0 (항상 압력 변화 없음)")
print("  - 현재: HYSPLIT 공식 구현 W = (- ∂θ/∂t - u ∂θ/∂x - v ∂θ/∂y) / (∂θ/∂z)")
print()

old_results = []
new_results = []

for name, (lat, lon) in test_locations.items():
    pressure = 850.0
    
    hysplit_traj = read_hysplit_trajectory(name)
    if not hysplit_traj:
        continue
    
    # 개선된 Mode 3 테스트
    start_loc = StartLocation(lat=lat, lon=lon, height=pressure, height_type="pressure")
    config = SimulationConfig(
        start_time=datetime(2026, 2, 14, 0, 0),
        num_start_locations=1,
        start_locations=[start_loc],
        total_run_hours=-24,
        vertical_motion=3,  # Mode 3 (Isentropic)
        model_top=10000.0,
        met_files=[],
        turbulence_on=False,
        dt_max=15.0,
        tratio=0.75,
    )
    
    try:
        engine = TrajectoryEngine(config, met_data)
        trajectory = engine.run(output_interval_s=3600.0)[0]
        
        # 압력 변화 분석
        py_pressures = [trajectory[i][3] for i in range(min(len(trajectory), len(hysplit_traj)))]
        hy_pressures = [hysplit_traj[i]['pressure'] for i in range(min(len(trajectory), len(hysplit_traj)))]
        
        py_change = py_pressures[-1] - py_pressures[0]
        hy_change = hy_pressures[-1] - hy_pressures[0]
        
        # 방향 일치 여부
        py_dir = "하강" if py_change < 0 else "상승"
        hy_dir = "하강" if hy_change < 0 else "상승"
        direction_match = py_dir == hy_dir
        
        # 오차 계산
        pressure_errors = [abs(py_pressures[i] - hy_pressures[i]) for i in range(len(py_pressures))]
        mean_p_error = np.mean(pressure_errors)
        
        # 수평 오차 계산
        horizontal_errors = []
        for i in range(len(trajectory)):
            if i < len(hysplit_traj):
                py_lat, py_lon = trajectory[i][1], trajectory[i][2]
                hy_lat, hy_lon = hysplit_traj[i]['lat'], hysplit_traj[i]['lon']
                h_error = haversine(py_lat, py_lon, hy_lat, hy_lon)
                horizontal_errors.append(h_error)
        
        mean_h_error = np.mean(horizontal_errors)
        
        new_results.append({
            'name': name,
            'h_error': mean_h_error,
            'p_error': mean_p_error,
            'direction_match': direction_match,
            'py_change': py_change,
            'hy_change': hy_change,
        })
        
        match_symbol = "✓" if direction_match else "✗"
        print(f"{name:^10}:")
        print(f"  PyΔP={py_change:+7.1f} hPa, HyΔP={hy_change:+7.1f} hPa {match_symbol}")
        print(f"  P오차={mean_p_error:5.1f} hPa, H오차={mean_h_error:5.1f} km")
        print()
        
        # 이전 결과 (PyΔP = 0)
        old_results.append({
            'name': name,
            'p_error': mean_p_error if py_change == 0 else 999,  # 이전 결과는 별도 저장됨
        })
        
    except Exception as e:
        print(f"{name:^10}: ❌ Error - {str(e)}")
        print()

# 통계
print("\n" + "="*100)
print("  결과 비교")
print("="*100)

if new_results:
    direction_matches = sum(1 for r in new_results if r['direction_match'])
    total = len(new_results)
    
    p_errors = [r['p_error'] for r in new_results]
    h_errors = [r['h_error'] for r in new_results]
    
    print(f"\n개선된 Mode 3:")
    print(f"  방향 일치: {direction_matches}/{total} ({100*direction_matches/total:.1f}%)")
    print(f"  평균 압력 오차: {np.mean(p_errors):.1f} hPa")
    print(f"  평균 수평 오차: {np.mean(h_errors):.1f} km")
    
    # 이전 결과 (참고용)
    print(f"\n이전 Mode 3 (PyΔP = 0):")
    print(f"  평균 압력 오차: 34.9 hPa (제주 20.6, 상하이 45.2, 타이베이 38.8)")
    
    # 개선율
    old_avg = 34.9
    new_avg = np.mean(p_errors)
    improvement = ((old_avg - new_avg) / old_avg) * 100
    
    print(f"\n개선:")
    print(f"  압력 오차: {old_avg:.1f} hPa → {new_avg:.1f} hPa ({improvement:+.1f}%)")

# 결론
print("\n" + "="*100)
print("  결론")
print("="*100)

if new_results:
    avg_p_error = np.mean(p_errors)
    
    if avg_p_error < 20:
        print(f"\n🎉 목표 달성! 평균 압력 오차 {avg_p_error:.1f} hPa < 20 hPa")
        print("   Mode 3 개선 성공!")
    elif avg_p_error < old_avg:
        print(f"\n✓ 개선됨: {old_avg:.1f} hPa → {avg_p_error:.1f} hPa")
        print(f"   하지만 목표 20 hPa에는 미달")
        print("\n추가 조정 필요:")
        print("  1. 그래디언트 계산 정확도 개선")
        print("  2. 시간/공간 스텝 크기 조정")
        print("  3. HYSPLIT 소스 코드와 비교")
    else:
        print(f"\n⚠️ 개선되지 않음: {old_avg:.1f} hPa → {avg_p_error:.1f} hPa")
        print("\n가능한 원인:")
        print("  1. 그래디언트 계산 방법 차이")
        print("  2. HYSPLIT이 다른 공식 사용")
        print("  3. 추가 보정 필요")
