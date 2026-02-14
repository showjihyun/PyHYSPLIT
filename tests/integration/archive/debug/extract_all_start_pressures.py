"""모든 위치의 HYSPLIT Web 시작 압력 추출"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np

locations = {
    '서울': {'lat': 37.5, 'lon': 127.0},
    '부산': {'lat': 35.1, 'lon': 129.0},
    '제주': {'lat': 33.5, 'lon': 126.5},
    '도쿄': {'lat': 35.7, 'lon': 139.7},
    '오사카': {'lat': 34.7, 'lon': 135.5},
    '베이징': {'lat': 39.9, 'lon': 116.4},
    '상하이': {'lat': 31.2, 'lon': 121.5},
    '타이베이': {'lat': 25.0, 'lon': 121.5},
}

def read_start_pressure_from_tdump(location_name):
    """tdump 파일에서 시작 압력 읽기
    
    tdump 형식:
    컬럼 1-8: 메타데이터
    컬럼 9: AGE (hours)
    컬럼 10-11: LAT, LON
    컬럼 12: HEIGHT (m)
    컬럼 13: PRESSURE (hPa) - 실제 압력
    """
    tdump_file = f"tests/integration/hysplit_web_data/tdump_{location_name}.txt"
    try:
        with open(tdump_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # 7번째 줄에서 입력 압력 읽기
            if len(lines) >= 7:
                header_parts = lines[6].split()
                if len(header_parts) >= 7:
                    input_pressure = float(header_parts[6])
                else:
                    input_pressure = None
            else:
                input_pressure = None
            
            # 데이터 라인 찾기 (보통 9번째 줄부터)
            for i, line in enumerate(lines[8:], start=8):  # 9번째 줄부터
                parts = line.split()
                if len(parts) >= 13:
                    try:
                        # 첫 번째 데이터 포인트 (age = 0.0)
                        age = float(parts[8])
                        if abs(age) < 0.01:  # age ≈ 0
                            # 13번째 컬럼이 실제 압력
                            actual_pressure = float(parts[12])
                            return input_pressure, actual_pressure
                    except (ValueError, IndexError):
                        continue
    except Exception as e:
        print(f"  ⚠️ {location_name}: 파일 읽기 실패 - {e}")
    return None, None

print("="*80)
print("  모든 위치의 HYSPLIT Web 시작 압력 추출")
print("="*80)

results = []

for name, info in locations.items():
    input_p, actual_p = read_start_pressure_from_tdump(name)
    if input_p and actual_p:
        info['input_p'] = input_p
        info['hysplit_p'] = actual_p
        info['diff'] = actual_p - input_p
        results.append(info)
        print(f"\n{name}:")
        print(f"  위치: {info['lat']}°N, {info['lon']}°E")
        print(f"  입력: {input_p:.1f} hPa")
        print(f"  HYSPLIT 실제: {actual_p:.1f} hPa")
        print(f"  차이: {info['diff']:+.1f} hPa ({info['diff']/input_p*100:+.1f}%)")
    else:
        print(f"\n{name}: ⚠️ 데이터 없음")

if len(results) > 0:
    print(f"\n{'='*80}")
    print("  통계 분석")
    print(f"{'='*80}")
    
    diffs = [r['diff'] for r in results]
    hysplit_ps = [r['hysplit_p'] for r in results]
    input_ps = [r['input_p'] for r in results]
    lats = [r['lat'] for r in results]
    
    print(f"\n압력 차이 (HYSPLIT 실제 - 입력):")
    print(f"  평균: {np.mean(diffs):.1f} hPa")
    print(f"  표준편차: {np.std(diffs):.1f} hPa")
    print(f"  최소: {np.min(diffs):.1f} hPa")
    print(f"  최대: {np.max(diffs):.1f} hPa")
    
    print(f"\nHYSPLIT 실제 압력:")
    print(f"  평균: {np.mean(hysplit_ps):.1f} hPa")
    print(f"  표준편차: {np.std(hysplit_ps):.1f} hPa")
    print(f"  최소: {np.min(hysplit_ps):.1f} hPa")
    print(f"  최대: {np.max(hysplit_ps):.1f} hPa")
    
    # 위도와의 상관관계
    if len(lats) > 1 and np.std(diffs) > 0:
        corr_lat_diff = np.corrcoef(lats, diffs)[0, 1]
        corr_lat_p = np.corrcoef(lats, hysplit_ps)[0, 1]
        print(f"\n상관관계:")
        print(f"  위도 vs 압력 차이: {corr_lat_diff:.3f}")
        print(f"  위도 vs HYSPLIT 압력: {corr_lat_p:.3f}")
    
    print(f"\n{'='*80}")
    print("  결론")
    print(f"{'='*80}")
    
    if np.std(diffs) < 10:
        print(f"\n✓ 압력 차이가 일정함 (표준편차 {np.std(diffs):.1f} hPa)")
        print(f"  → 고정 오프셋 사용 가능: p_actual = p_input + {np.mean(diffs):.1f} hPa")
    else:
        print(f"\n✗ 압력 차이가 위치에 따라 다름 (표준편차 {np.std(diffs):.1f} hPa)")
        print(f"  → 위치별 보정 필요")
        
        if abs(corr_lat_diff) > 0.5:
            print(f"  → 위도와 강한 상관관계 ({corr_lat_diff:.3f})")
            print(f"  → 위도 기반 보정 공식 가능")
        else:
            print(f"  → 위도와 약한 상관관계 ({corr_lat_diff:.3f})")
            print(f"  → 다른 요인 고려 필요 (온도, 지형 등)")
    
    # 간단한 보정 공식 제안
    print(f"\n권장 보정 방법:")
    if np.std(diffs) < 10:
        print(f"  1. 고정 오프셋: +{np.mean(diffs):.1f} hPa")
    else:
        # 위도 기반 선형 회귀
        from numpy.polynomial import Polynomial
        p = Polynomial.fit(lats, diffs, 1)
        a, b = p.convert().coef
        print(f"  1. 위도 기반: offset = {a:.2f} + {b:.2f} * lat")
        print(f"     예: 서울(37.5°N) → {a + b*37.5:.1f} hPa")
    
    print(f"  2. 개별 위치 매핑 (가장 정확)")
    print(f"  3. 지오포텐셜 고도 사용 (HYSPLIT 방식)")

else:
    print(f"\n⚠️ 데이터를 추출할 수 없습니다.")
