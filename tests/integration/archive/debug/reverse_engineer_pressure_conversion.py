"""HYSPLIT Web의 압력 변환 방식 역공학"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import netCDF4

# 모든 8개 위치의 HYSPLIT Web 시작 압력 수집
locations = {
    '서울': {'lat': 37.5, 'lon': 127.0, 'input_p': 850.0, 'hysplit_p': 906.3},
    '부산': {'lat': 35.1, 'lon': 129.0, 'input_p': 850.0, 'hysplit_p': None},  # tdump에서 확인 필요
    '제주': {'lat': 33.5, 'lon': 126.5, 'input_p': 850.0, 'hysplit_p': None},
    '도쿄': {'lat': 35.7, 'lon': 139.7, 'input_p': 850.0, 'hysplit_p': None},
    '오사카': {'lat': 34.7, 'lon': 135.5, 'input_p': 850.0, 'hysplit_p': None},
    '베이징': {'lat': 39.9, 'lon': 116.4, 'input_p': 850.0, 'hysplit_p': None},
    '상하이': {'lat': 31.2, 'lon': 121.5, 'input_p': 850.0, 'hysplit_p': None},
    '타이베이': {'lat': 25.0, 'lon': 121.5, 'input_p': 850.0, 'hysplit_p': None},
}

# tdump 파일에서 시작 압력 읽기
def read_start_pressure_from_tdump(location_name):
    """tdump 파일에서 시작 압력 읽기"""
    tdump_file = f"tests/integration/hysplit_web_data/tdump_{location_name}.txt"
    try:
        with open(tdump_file, 'r') as f:
            lines = f.readlines()
            # 첫 번째 데이터 라인 (보통 6번째 줄)
            for line in lines:
                if line.strip() and not line.startswith('#') and len(line.split()) >= 9:
                    parts = line.split()
                    try:
                        pressure = float(parts[8])  # PRESSURE 컬럼
                        return pressure
                    except:
                        continue
    except:
        pass
    return None

# 모든 위치의 시작 압력 수집
print("="*80)
print("  HYSPLIT Web 시작 압력 수집")
print("="*80)

for name, info in locations.items():
    if info['hysplit_p'] is None:
        info['hysplit_p'] = read_start_pressure_from_tdump(name)
    
    if info['hysplit_p']:
        diff = info['hysplit_p'] - info['input_p']
        print(f"\n{name}:")
        print(f"  입력: {info['input_p']:.1f} hPa")
        print(f"  HYSPLIT: {info['hysplit_p']:.1f} hPa")
        print(f"  차이: {diff:+.1f} hPa ({diff/info['input_p']*100:+.1f}%)")

# GFS 데이터 로드
print(f"\n{'='*80}")
print("  GFS 데이터 분석")
print(f"{'='*80}")

ds = netCDF4.Dataset('tests/integration/gfs_cache/gfs_eastasia_24h_real.nc')
lat_grid = np.array(ds.variables['latitude'][:])
lon_grid = np.array(ds.variables['longitude'][:])
lev_grid = np.array(ds.variables['level'][:])
t_data = np.array(ds.variables['t'][:])
ds.close()

# 각 위치에서 850 hPa 레벨의 온도 확인
print(f"\n850 hPa 레벨의 온도:")
for name, info in locations.items():
    if info['hysplit_p'] is None:
        continue
    
    lat, lon = info['lat'], info['lon']
    lat_idx = np.argmin(np.abs(lat_grid - lat))
    lon_idx = np.argmin(np.abs(lon_grid - lon))
    lev_850_idx = np.argmin(np.abs(lev_grid - 850))
    
    t_850 = t_data[0, lev_850_idx, lat_idx, lon_idx]
    print(f"  {name}: {t_850:.1f} K ({t_850-273.15:.1f}°C)")

# 패턴 분석
print(f"\n{'='*80}")
print("  패턴 분석")
print(f"{'='*80}")

valid_locations = {k: v for k, v in locations.items() if v['hysplit_p'] is not None}

if len(valid_locations) > 0:
    diffs = [v['hysplit_p'] - v['input_p'] for v in valid_locations.values()]
    print(f"\n압력 차이 통계:")
    print(f"  평균: {np.mean(diffs):.1f} hPa")
    print(f"  표준편차: {np.std(diffs):.1f} hPa")
    print(f"  최소: {np.min(diffs):.1f} hPa")
    print(f"  최대: {np.max(diffs):.1f} hPa")
    
    # 위도와의 상관관계
    lats = [v['lat'] for v in valid_locations.values()]
    if len(lats) > 1:
        corr = np.corrcoef(lats, diffs)[0, 1]
        print(f"\n위도와의 상관계수: {corr:.3f}")
    
    # 가설: HYSPLIT은 850 hPa를 "지표면 위 850 hPa"로 해석?
    print(f"\n{'='*80}")
    print("  가설 검증")
    print(f"{'='*80}")
    
    print(f"\n가설: HYSPLIT은 입력 압력을 '모델 레벨'이 아닌 '실제 압력'으로 해석")
    print(f"      즉, 850 hPa 입력 → 실제로 그 위치에서 850 hPa에 해당하는 고도 찾기")
    print(f"      → 그 고도에서의 실제 압력 사용")
    
    # 표준 대기 공식으로 850 hPa 고도 계산
    def altitude_at_pressure(P, P0=1013.25, T0=288.15, L=0.0065, g=9.80665, R=287.05):
        return (T0 / L) * (1 - (P / P0) ** (R * L / g))
    
    def pressure_at_altitude(h, P0=1013.25, T0=288.15, L=0.0065, g=9.80665, R=287.05):
        return P0 * (1 - L * h / T0) ** (g / (R * L))
    
    h_850 = altitude_at_pressure(850)
    print(f"\n표준 대기에서 850 hPa 고도: {h_850:.0f} m")
    
    # 서울 예시
    seoul = locations['서울']
    seoul_elevation = 38  # m
    
    print(f"\n서울 예시:")
    print(f"  지형 고도: {seoul_elevation} m")
    print(f"  850 hPa 고도 (해발): {h_850:.0f} m")
    print(f"  850 hPa 고도 (AGL): {h_850 - seoul_elevation:.0f} m")
    
    # 그 고도에서의 압력 (표준 대기)
    p_at_850_level = pressure_at_altitude(h_850)
    print(f"  그 고도에서의 압력 (표준 대기): {p_at_850_level:.1f} hPa")
    print(f"  HYSPLIT 실제 압력: {seoul['hysplit_p']:.1f} hPa")
    print(f"  차이: {abs(p_at_850_level - seoul['hysplit_p']):.1f} hPa")
    
    print(f"\n결론: 표준 대기 공식으로는 설명 안 됨")
    print(f"      → GFS 모델의 실제 기상 조건 (온도, 습도 등)을 고려한 계산 필요")
    print(f"      → 지오포텐셜 고도 데이터가 필수!")

else:
    print(f"\n⚠️ HYSPLIT Web 데이터가 충분하지 않습니다.")
    print(f"   tdump 파일을 확인하세요.")

print(f"\n{'='*80}")
print("  권장 사항")
print(f"{'='*80}")

print(f"\n1. 단기 해결책: 경험적 보정")
print(f"   - 서울 데이터: 850 hPa → 906.3 hPa (차이 +56.3 hPa)")
print(f"   - 다른 위치들도 유사한 패턴일 가능성")
print(f"   - 임시로 고정 오프셋 적용: p_actual = p_input + 56 hPa")

print(f"\n2. 중기 해결책: 온도 기반 추정")
print(f"   - GFS 온도 프로파일 사용")
print(f"   - 정역학 방정식으로 압력-고도 관계 계산")
print(f"   - 정확도: 중간")

print(f"\n3. 장기 해결책: 지오포텐셜 고도 사용")
print(f"   - GFS 데이터에 지오포텐셜 고도 추가")
print(f"   - HYSPLIT과 동일한 방식")
print(f"   - 정확도: 높음")

print(f"\n다음 단계:")
print(f"  1. 모든 위치의 tdump 파일에서 시작 압력 확인")
print(f"  2. 패턴 분석 (위도, 고도, 온도와의 관계)")
print(f"  3. 경험적 보정 공식 도출")
print(f"  4. 전체 테스트 재실행")
