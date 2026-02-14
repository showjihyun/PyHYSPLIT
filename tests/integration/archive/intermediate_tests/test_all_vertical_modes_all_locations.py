"""모든 위치에서 모든 수직 속도 모드 체계적 테스트"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import netCDF4
from datetime import datetime
from pyhysplit.models import StartLocation, SimulationConfig, MetData
from pyhysplit.engine import TrajectoryEngine
from math import radians, sin, cos, sqrt, atan2
import json

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

# 수직 속도 모드
modes = [0, 1, 3, 7, 8]
mode_names = {
    0: "Data vertical velocity",
    1: "Isodensity (constant density)",
    3: "Isentropic (constant potential temp)",
    7: "Spatially averaged",
    8: "Damped magnitude"
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

print("\n" + "="*120)
print("  모든 위치 × 모든 수직 속도 모드 체계적 테스트")
print("="*120)
print(f"\n테스트 조합: {len(locations)} 위치 × {len(modes)} 모드 = {len(locations) * len(modes)} 테스트")
print(f"예상 소요 시간: ~{len(locations) * len(modes) * 2} 초\n")

results = {}

for mode in modes:
    print(f"\n{'='*120}")
    print(f"  Mode {mode}: {mode_names[mode]}")
    print(f"{'='*120}\n")
    
    mode_results = {}
    
    for name, (lat, lon) in locations.items():
        pressure = 850.0
        
        # HYSPLIT Web 결과 읽기
        hysplit_traj = read_hysplit_trajectory(name)
        if not hysplit_traj:
            continue
        
        # PyHYSPLIT 계산
        start_loc = StartLocation(lat=lat, lon=lon, height=pressure, height_type="pressure")
        config = SimulationConfig(
            start_time=datetime(2026, 2, 14, 0, 0),
            num_start_locations=1,
            start_locations=[start_loc],
            total_run_hours=-24,
            vertical_motion=mode,
            model_top=10000.0,
            met_files=[],
            turbulence_on=False,
            dt_max=15.0,
            tratio=0.75
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
            
            mode_results[name] = {
                'py_change': py_change,
                'hy_change': hy_change,
                'direction_match': direction_match,
                'mean_p_error': mean_p_error,
                'mean_h_error': mean_h_error,
                'success': True
            }
            
            match_symbol = "✓" if direction_match else "✗"
            print(f"  {name:^10}: P오차={mean_p_error:6.1f} hPa, H오차={mean_h_error:6.1f} km, "
                  f"PyΔP={py_change:+7.1f}, HyΔP={hy_change:+7.1f} {match_symbol}")
            
        except Exception as e:
            mode_results[name] = {
                'success': False,
                'error': str(e)
            }
            print(f"  {name:^10}: ❌ Error - {str(e)[:50]}")
    
    results[mode] = mode_results

# 결과 분석
print("\n\n" + "="*120)
print("  결과 요약")
print("="*120)

summary = []

for mode in modes:
    mode_data = results[mode]
    successful = [r for r in mode_data.values() if r.get('success', False)]
    
    if not successful:
        continue
    
    direction_matches = sum(1 for r in successful if r['direction_match'])
    total = len(successful)
    match_rate = 100 * direction_matches / total if total > 0 else 0
    
    mean_p_errors = [r['mean_p_error'] for r in successful]
    mean_h_errors = [r['mean_h_error'] for r in successful]
    
    avg_p_error = np.mean(mean_p_errors)
    avg_h_error = np.mean(mean_h_errors)
    
    summary.append({
        'mode': mode,
        'mode_name': mode_names[mode],
        'match_rate': match_rate,
        'direction_matches': direction_matches,
        'total': total,
        'avg_p_error': avg_p_error,
        'avg_h_error': avg_h_error,
    })

# 정렬: 방향 일치율 → 압력 오차 순
summary.sort(key=lambda x: (-x['match_rate'], x['avg_p_error']))

print(f"\n{'Mode':^6} {'이름':^30} {'방향 일치':^12} {'평균 P 오차':^14} {'평균 H 오차':^14}")
print("-"*120)

for s in summary:
    print(f"{s['mode']:^6} {s['mode_name']:^30} {s['direction_matches']}/{s['total']} ({s['match_rate']:5.1f}%) "
          f"{s['avg_p_error']:>12.1f} hPa {s['avg_h_error']:>12.1f} km")

# 최적 모드 찾기
print("\n" + "="*120)
print("  최적 모드 분석")
print("="*120)

best_direction = max(summary, key=lambda x: x['match_rate'])
best_pressure = min(summary, key=lambda x: x['avg_p_error'])
best_horizontal = min(summary, key=lambda x: x['avg_h_error'])

print(f"\n방향 일치율 최고: Mode {best_direction['mode']} ({best_direction['mode_name']})")
print(f"  - 방향 일치: {best_direction['direction_matches']}/{best_direction['total']} ({best_direction['match_rate']:.1f}%)")
print(f"  - 평균 압력 오차: {best_direction['avg_p_error']:.1f} hPa")
print(f"  - 평균 수평 오차: {best_direction['avg_h_error']:.1f} km")

print(f"\n압력 오차 최소: Mode {best_pressure['mode']} ({best_pressure['mode_name']})")
print(f"  - 방향 일치: {best_pressure['direction_matches']}/{best_pressure['total']} ({best_pressure['match_rate']:.1f}%)")
print(f"  - 평균 압력 오차: {best_pressure['avg_p_error']:.1f} hPa")
print(f"  - 평균 수평 오차: {best_pressure['avg_h_error']:.1f} km")

print(f"\n수평 오차 최소: Mode {best_horizontal['mode']} ({best_horizontal['mode_name']})")
print(f"  - 방향 일치: {best_horizontal['direction_matches']}/{best_horizontal['total']} ({best_horizontal['match_rate']:.1f}%)")
print(f"  - 평균 압력 오차: {best_horizontal['avg_p_error']:.1f} hPa")
print(f"  - 평균 수평 오차: {best_horizontal['avg_h_error']:.1f} km")

# 위치별 최적 모드 분석
print("\n" + "="*120)
print("  위치별 최적 모드")
print("="*120)

location_best = {}

for name in locations.keys():
    location_modes = []
    for mode in modes:
        if name in results[mode] and results[mode][name].get('success', False):
            r = results[mode][name]
            location_modes.append({
                'mode': mode,
                'direction_match': r['direction_match'],
                'p_error': r['mean_p_error'],
                'h_error': r['mean_h_error'],
            })
    
    if location_modes:
        # 방향 일치 → 압력 오차 순으로 정렬
        location_modes.sort(key=lambda x: (-x['direction_match'], x['p_error']))
        best = location_modes[0]
        location_best[name] = best
        
        match_symbol = "✓" if best['direction_match'] else "✗"
        print(f"\n{name:^10}: Mode {best['mode']} ({mode_names[best['mode']]})")
        print(f"  방향: {match_symbol}, P오차: {best['p_error']:.1f} hPa, H오차: {best['h_error']:.1f} km")

# 결과 저장
output = {
    'test_info': {
        'locations': len(locations),
        'modes': len(modes),
        'total_tests': len(locations) * len(modes),
    },
    'summary': summary,
    'detailed_results': results,
    'location_best': location_best,
}

output_file = 'tests/integration/vertical_modes_systematic_test_results.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"\n\n✅ 결과 저장: {output_file}")

# 결론
print("\n" + "="*120)
print("  결론")
print("="*120)

if best_direction['match_rate'] == 100:
    print(f"\n🎉 Mode {best_direction['mode']} ({best_direction['mode_name']})에서 모든 위치의 방향이 일치합니다!")
    print(f"   이 모드를 기본값으로 사용하는 것을 권장합니다.")
elif best_direction['match_rate'] >= 75:
    print(f"\n✓ Mode {best_direction['mode']} ({best_direction['mode_name']})에서 {best_direction['match_rate']:.0f}%의 위치가 일치합니다.")
    print(f"   이 모드가 가장 적합하지만, 일부 위치는 추가 조정이 필요합니다.")
else:
    print(f"\n⚠️ 모든 모드에서 방향 일치율이 낮습니다 (최고 {best_direction['match_rate']:.0f}%).")
    print(f"   HYSPLIT이 다른 알고리즘을 사용하거나, 추가 보정이 필요할 수 있습니다.")

print(f"\n현재 Mode 0 사용 중: 방향 일치 {results[0] and sum(1 for r in results[0].values() if r.get('success') and r.get('direction_match'))}/{len(locations)}")
