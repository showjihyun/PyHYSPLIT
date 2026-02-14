"""자동 수직 속도 모드 선택 기능 테스트"""
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

# 테스트 위치
locations = {
    '서울': (37.5, 127.0),
    '부산': (35.1, 129.0),
    '제주': (33.5, 126.5),
    '도쿄': (35.7, 139.7),
    '오사카': (34.7, 135.5),
    '베이징': (39.9, 116.4),
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
        print(f"Error reading {location_name}: {e}")
    return trajectory

print("\n" + "="*100)
print("  자동 수직 속도 모드 선택 기능 테스트")
print("="*100)
print("\n자동 선택 규칙:")
print("  - 위도 > 33°N: Mode 7 (Spatially averaged)")
print("  - 위도 ≤ 33°N: Mode 3 (Isentropic)")
print()

results = []

for name, (lat, lon) in locations.items():
    pressure = 850.0
    
    # HYSPLIT Web 결과 읽기
    hysplit_traj = read_hysplit_trajectory(name)
    if not hysplit_traj:
        continue
    
    # 자동 모드 선택 활성화
    start_loc = StartLocation(lat=lat, lon=lon, height=pressure, height_type="pressure")
    config = SimulationConfig(
        start_time=datetime(2026, 2, 14, 0, 0),
        num_start_locations=1,
        start_locations=[start_loc],
        total_run_hours=-24,
        vertical_motion=0,  # 이 값은 auto_vertical_mode=True일 때 무시됨
        model_top=10000.0,
        met_files=[],
        turbulence_on=False,
        dt_max=15.0,
        tratio=0.75,
        auto_vertical_mode=True,  # 자동 모드 선택 활성화
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
        
        # 선택된 모드 확인
        selected_mode = 7 if lat > 33.5 else 3
        
        results.append({
            'name': name,
            'lat': lat,
            'selected_mode': selected_mode,
            'p_error': mean_p_error,
            'h_error': mean_h_error,
            'direction_match': direction_match,
            'py_change': py_change,
            'hy_change': hy_change,
        })
        
        match_symbol = "✓" if direction_match else "✗"
        print(f"{name:^10} ({lat:5.1f}°N) → Mode {selected_mode}:")
        print(f"  P오차={mean_p_error:5.1f} hPa, H오차={mean_h_error:6.1f} km")
        print(f"  PyΔP={py_change:+7.1f}, HyΔP={hy_change:+7.1f} {match_symbol}")
        print()
        
    except Exception as e:
        print(f"{name:^10}: ❌ Error - {str(e)}")
        print()

# 전체 통계
print("\n" + "="*100)
print("  전체 통계")
print("="*100)

if results:
    direction_matches = sum(1 for r in results if r['direction_match'])
    total = len(results)
    
    p_errors = [r['p_error'] for r in results]
    h_errors = [r['h_error'] for r in results]
    
    print(f"\n방향 일치: {direction_matches}/{total} ({100*direction_matches/total:.1f}%)")
    print(f"평균 압력 오차: {np.mean(p_errors):.1f} hPa")
    print(f"평균 수평 오차: {np.mean(h_errors):.1f} km")
    print(f"압력 오차 중앙값: {np.median(p_errors):.1f} hPa")
    
    # 모드별 통계
    mode7_results = [r for r in results if r['selected_mode'] == 7]
    mode3_results = [r for r in results if r['selected_mode'] == 3]
    
    if mode7_results:
        mode7_matches = sum(1 for r in mode7_results if r['direction_match'])
        print(f"\nMode 7 (중위도, {len(mode7_results)}개 위치):")
        print(f"  방향 일치: {mode7_matches}/{len(mode7_results)}")
        print(f"  평균 압력 오차: {np.mean([r['p_error'] for r in mode7_results]):.1f} hPa")
    
    if mode3_results:
        mode3_matches = sum(1 for r in mode3_results if r['direction_match'])
        print(f"\nMode 3 (저위도, {len(mode3_results)}개 위치):")
        print(f"  방향 일치: {mode3_matches}/{len(mode3_results)}")
        print(f"  평균 압력 오차: {np.mean([r['p_error'] for r in mode3_results]):.1f} hPa")

# 결론
print("\n" + "="*100)
print("  결론")
print("="*100)

if direction_matches == total:
    print("\n🎉 자동 모드 선택으로 모든 위치의 방향이 일치합니다!")
    print(f"   평균 압력 오차: {np.mean(p_errors):.1f} hPa")
    print(f"   평균 수평 오차: {np.mean(h_errors):.1f} km")
    print("\n✅ auto_vertical_mode=True 사용을 권장합니다.")
elif direction_matches >= 0.75 * total:
    print(f"\n✓ 자동 모드 선택이 효과적입니다 ({direction_matches}/{total} 일치)")
    print("  추가 조정으로 더 개선 가능합니다.")
else:
    print(f"\n⚠️ 자동 모드 선택이 충분하지 않습니다 ({direction_matches}/{total} 일치)")
    print("  추가 조사가 필요합니다.")
