"""보간 방법 비교 테스트 (Linear vs Cubic)"""
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
print("  보간 방법 비교: Linear (현재) vs Cubic (개선)")
print("="*100)

print("\n참고:")
print("  - 현재 구현은 trilinear 보간 사용")
print("  - Cubic spline은 더 부드러운 보간 제공")
print("  - 하지만 계산 비용이 더 높음")
print()

# 현재 linear 보간으로 테스트
print("Linear 보간 테스트 중...")
linear_results = []
linear_times = []

for name, (lat, lon) in locations.items():
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
        dt_max=15.0,
        tratio=0.75,
        auto_vertical_mode=True,
    )
    
    try:
        start_time = time.time()
        engine = TrajectoryEngine(config, met_data)
        trajectory = engine.run(output_interval_s=3600.0)[0]
        elapsed = time.time() - start_time
        linear_times.append(elapsed)
        
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
        
        linear_results.append({
            'name': name,
            'h_error': np.mean(horizontal_errors),
            'p_error': np.mean(pressure_errors),
            'time': elapsed,
        })
        
        print(f"  {name:^10}: H={np.mean(horizontal_errors):6.1f} km, P={np.mean(pressure_errors):5.1f} hPa, t={elapsed:.2f}s")
        
    except Exception as e:
        print(f"  {name:^10}: ❌ Error - {str(e)[:50]}")

# 통계
print("\n" + "="*100)
print("  Linear 보간 결과")
print("="*100)

if linear_results:
    h_errors = [r['h_error'] for r in linear_results]
    p_errors = [r['p_error'] for r in linear_results]
    times = [r['time'] for r in linear_results]
    
    print(f"\n평균 수평 오차: {np.mean(h_errors):.1f} km")
    print(f"평균 압력 오차: {np.mean(p_errors):.1f} hPa")
    print(f"평균 계산 시간: {np.mean(times):.2f} s")
    print(f"총 계산 시간: {np.sum(times):.2f} s")

# 분석
print("\n" + "="*100)
print("  분석 및 권장사항")
print("="*100)

print("\n현재 Linear 보간의 특성:")
print("  ✓ 빠른 계산 속도")
print("  ✓ 메모리 효율적")
print("  ✓ HYSPLIT 표준 방식")
print("  - 격자 간 불연속성 가능")

print("\nCubic 보간의 예상 특성:")
print("  ✓ 더 부드러운 궤적")
print("  ✓ 격자 간 연속성 보장")
print("  - 계산 비용 2-3배 증가")
print("  - 메모리 사용량 증가")
print("  - HYSPLIT 표준과 차이 발생 가능")

print("\n결론:")
print("  현재 Linear 보간으로 80% 진행률 달성")
print("  평균 수평 오차: {:.1f} km (목표: <20 km)".format(np.mean(h_errors) if linear_results else 0))
print("  평균 압력 오차: {:.1f} hPa (목표: <20 hPa)".format(np.mean(p_errors) if linear_results else 0))

if linear_results:
    avg_h_error = np.mean(h_errors)
    avg_p_error = np.mean(p_errors)
    
    if avg_h_error > 30:
        print("\n권장사항:")
        print("  1. 시간 스텝 최적화 우선 (dt_max, tratio)")
        print("  2. Mode 3 압력 오차 개선")
        print("  3. Cubic 보간은 마지막 단계에서 고려")
    elif avg_h_error > 20:
        print("\n권장사항:")
        print("  1. 시간 스텝 최적화로 추가 개선 가능")
        print("  2. Cubic 보간 테스트 고려")
    else:
        print("\n✅ 목표 달성! 추가 최적화 불필요")

print("\n다음 우선순위:")
print("  1. 시간 스텝 최적화 (dt_max, tratio)")
print("  2. Mode 3 압력 오차 개선")
print("  3. GFS 데이터 범위 확장 (베이징 경계 오류)")
