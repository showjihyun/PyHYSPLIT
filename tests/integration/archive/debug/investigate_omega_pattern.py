"""Omega 패턴 조사 - 왜 일부 위치는 방향이 반대인가?"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import netCDF4
from datetime import datetime
from pyhysplit.models import StartLocation, SimulationConfig, MetData
from pyhysplit.engine import TrajectoryEngine

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

# 방향이 맞는 위치와 틀린 위치
correct_locations = {
    '서울': (37.5, 127.0),
    '부산': (35.1, 129.0),
    '도쿄': (35.7, 139.7),
    '오사카': (34.7, 135.5),
    '베이징': (39.9, 116.4),
}

wrong_locations = {
    '제주': (33.5, 126.5),
    '상하이': (31.2, 121.5),
    '타이베이': (25.0, 121.5),
}

def analyze_omega_pattern(name, lat, lon):
    """특정 위치의 omega 패턴 분석"""
    pressure = 850.0
    
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
        tratio=0.75
    )
    
    engine = TrajectoryEngine(config, met_data)
    
    # 첫 3시간 동안의 omega 값 추적
    current_lon = lon
    current_lat = lat
    current_p = pressure + 57.3  # 압력 오프셋 적용
    current_t = 0.0
    dt = -3600.0  # 1시간 backward
    
    omega_values = []
    
    for hour in range(3):
        try:
            # 현재 위치에서 omega 보간
            u, v, omega_raw = engine.integrator.interp.interpolate_4d(
                current_lon, current_lat, current_p, current_t
            )
            
            omega_values.append({
                'hour': -hour,
                'lon': current_lon,
                'lat': current_lat,
                'p': current_p,
                'omega': omega_raw,
                'u': u,
                'v': v,
            })
            
            # 다음 위치로 이동
            if hour < 2:
                new_lon, new_lat, new_p = engine.integrator.step(
                    current_lon, current_lat, current_p, current_t, dt
                )
                current_lon = new_lon
                current_lat = new_lat
                current_p = new_p
                current_t += dt
        except Exception as e:
            break
    
    return omega_values

print("\n" + "="*100)
print("  Omega 패턴 비교: 방향이 맞는 위치 vs 틀린 위치")
print("="*100)

print("\n방향이 맞는 위치 (5개):")
print("-"*100)

for name, (lat, lon) in correct_locations.items():
    omega_values = analyze_omega_pattern(name, lat, lon)
    avg_omega = np.mean([v['omega'] for v in omega_values])
    print(f"\n{name} ({lat}°N, {lon}°E):")
    print(f"  평균 omega: {avg_omega:+.6f} hPa/s")
    for v in omega_values:
        print(f"    Hour {v['hour']:2d}: omega={v['omega']:+.6f}, P={v['p']:.1f}, u={v['u']:+.2f}, v={v['v']:+.2f}")

print("\n\n방향이 틀린 위치 (3개):")
print("-"*100)

for name, (lat, lon) in wrong_locations.items():
    omega_values = analyze_omega_pattern(name, lat, lon)
    avg_omega = np.mean([v['omega'] for v in omega_values])
    print(f"\n{name} ({lat}°N, {lon}°E):")
    print(f"  평균 omega: {avg_omega:+.6f} hPa/s")
    for v in omega_values:
        print(f"    Hour {v['hour']:2d}: omega={v['omega']:+.6f}, P={v['p']:.1f}, u={v['u']:+.2f}, v={v['v']:+.2f}")

# 통계 비교
print("\n\n" + "="*100)
print("  통계 비교")
print("="*100)

correct_omegas = []
for name, (lat, lon) in correct_locations.items():
    omega_values = analyze_omega_pattern(name, lat, lon)
    correct_omegas.extend([v['omega'] for v in omega_values])

wrong_omegas = []
for name, (lat, lon) in wrong_locations.items():
    omega_values = analyze_omega_pattern(name, lat, lon)
    wrong_omegas.extend([v['omega'] for v in omega_values])

print(f"\n방향이 맞는 위치:")
print(f"  평균 omega: {np.mean(correct_omegas):+.6f} hPa/s")
print(f"  표준편차: {np.std(correct_omegas):.6f} hPa/s")
print(f"  범위: {np.min(correct_omegas):+.6f} ~ {np.max(correct_omegas):+.6f} hPa/s")
print(f"  양수 비율: {100*np.sum(np.array(correct_omegas) > 0)/len(correct_omegas):.1f}%")

print(f"\n방향이 틀린 위치:")
print(f"  평균 omega: {np.mean(wrong_omegas):+.6f} hPa/s")
print(f"  표준편차: {np.std(wrong_omegas):.6f} hPa/s")
print(f"  범위: {np.min(wrong_omegas):+.6f} ~ {np.max(wrong_omegas):+.6f} hPa/s")
print(f"  양수 비율: {100*np.sum(np.array(wrong_omegas) > 0)/len(wrong_omegas):.1f}%")

# 위도 패턴 확인
print("\n\n위도 패턴:")
print(f"  방향이 맞는 위치 평균 위도: {np.mean([lat for _, (lat, lon) in correct_locations.items()]):.1f}°N")
print(f"  방향이 틀린 위치 평균 위도: {np.mean([lat for _, (lat, lon) in wrong_locations.items()]):.1f}°N")
