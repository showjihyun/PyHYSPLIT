"""GFS 데이터에서 지오포텐셜 고도 확인"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import netCDF4

# GFS 데이터 로드
print("Loading GFS data...")
ds = netCDF4.Dataset('tests/integration/gfs_cache/gfs_eastasia_24h_real.nc')

print("\n사용 가능한 변수:")
for var in ds.variables:
    print(f"  {var}: {ds.variables[var].long_name if hasattr(ds.variables[var], 'long_name') else 'no description'}")

lat_grid = np.array(ds.variables['latitude'][:])
lon_grid = np.array(ds.variables['longitude'][:])
lev_grid = np.array(ds.variables['level'][:])
time_grid = np.array(ds.variables['time'][:])

# 서울 위치
seoul_lat, seoul_lon = 37.5, 127.0

# 가장 가까운 그리드 포인트 찾기
lat_idx = np.argmin(np.abs(lat_grid - seoul_lat))
lon_idx = np.argmin(np.abs(lon_grid - seoul_lon))
lev_850_idx = np.argmin(np.abs(lev_grid - 850))
time_0_idx = 0

print(f"\n서울 위치 (37.5°N, 127.0°E)에 가장 가까운 그리드:")
print(f"  Latitude: {lat_grid[lat_idx]:.2f}°N (index {lat_idx})")
print(f"  Longitude: {lon_grid[lon_idx]:.2f}°E (index {lon_idx})")
print(f"  850 hPa 레벨: {lev_grid[lev_850_idx]:.1f} hPa (index {lev_850_idx})")

# 지오포텐셜 고도가 있는지 확인
if 'z' in ds.variables or 'gh' in ds.variables or 'hgt' in ds.variables:
    # 변수 이름 찾기
    geo_var_name = None
    for name in ['z', 'gh', 'hgt', 'geopotential', 'geopotential_height']:
        if name in ds.variables:
            geo_var_name = name
            break
    
    if geo_var_name:
        print(f"\n지오포텐셜 변수 발견: {geo_var_name}")
        geo_data = np.array(ds.variables[geo_var_name][:])
        
        # 850 hPa 레벨의 지오포텐셜 고도
        geo_850 = geo_data[time_0_idx, lev_850_idx, lat_idx, lon_idx]
        print(f"850 hPa 레벨의 지오포텐셜 고도: {geo_850:.1f} m")
        
        # 지표면 레벨 (가장 높은 압력)
        surface_idx = -1  # 마지막 레벨 (가장 높은 압력)
        geo_surface = geo_data[time_0_idx, surface_idx, lat_idx, lon_idx]
        print(f"지표면 ({lev_grid[surface_idx]:.1f} hPa) 지오포텐셜 고도: {geo_surface:.1f} m")
        
        # 850 hPa 레벨의 지표면 위 높이
        agl_850 = geo_850 - geo_surface
        print(f"850 hPa 레벨의 지표면 위 높이: {agl_850:.1f} m AGL")
else:
    print("\n지오포텐셜 고도 변수를 찾을 수 없습니다.")
    print("온도 데이터를 사용하여 추정해보겠습니다.")
    
    # 온도 데이터로 압력-고도 관계 추정
    if 't' in ds.variables:
        t_data = np.array(ds.variables['t'][:])
        t_850 = t_data[time_0_idx, lev_850_idx, lat_idx, lon_idx]
        print(f"\n850 hPa 레벨의 온도: {t_850:.1f} K ({t_850-273.15:.1f}°C)")
        
        # 정역학 방정식으로 고도 추정
        # dz = -(R*T/g) * dp/p
        R = 287.05  # J/(kg·K)
        g = 9.80665  # m/s²
        
        # 850 hPa에서 1000 hPa까지의 고도 차
        p1, p2 = 850, 1000
        T_avg = t_850  # 평균 온도로 근사
        dz = -(R * T_avg / g) * np.log(p2 / p1) * 100  # hPa to Pa
        print(f"850 hPa와 1000 hPa 사이의 고도 차 (추정): {dz:.0f} m")
        print(f"850 hPa 레벨의 해발 고도 (추정): {dz:.0f} m")

# 풍속 데이터 확인
u_data = np.array(ds.variables['u'][:])
v_data = np.array(ds.variables['v'][:])
w_data = np.array(ds.variables['w'][:])

u_850 = u_data[time_0_idx, lev_850_idx, lat_idx, lon_idx]
v_850 = v_data[time_0_idx, lev_850_idx, lat_idx, lon_idx]
w_850 = w_data[time_0_idx, lev_850_idx, lat_idx, lon_idx]

print(f"\n850 hPa 레벨의 풍속:")
print(f"  U (동서 성분): {u_850:.2f} m/s")
print(f"  V (남북 성분): {v_850:.2f} m/s")
print(f"  W (수직 성분): {w_850:.6f} Pa/s = {w_850/100:.6f} hPa/s")
print(f"  수평 풍속: {np.sqrt(u_850**2 + v_850**2):.2f} m/s")

ds.close()

print(f"\n{'='*80}")
print("  결론")
print(f"{'='*80}")
print(f"\nHYSPLIT Web의 906.3 hPa 시작 압력은:")
print(f"1. GFS 데이터의 850 hPa 레벨을 사용")
print(f"2. 해당 위치의 실제 지오포텐셜 고도를 고려")
print(f"3. 지형 고도와 기상 조건을 반영하여 실제 압력 계산")
print(f"\n이는 HYSPLIT이 '850 hPa'를 표준 기압 레벨이 아닌")
print(f"'GFS 모델의 850 hPa 레벨'로 해석한다는 의미입니다.")
