"""Phase 1: 고도 계산 개선

HYSPLIT Web과의 비교 결과 분석:
- 부산: 고도 오차 427.0 m (최대 704.4 m)
- 타이베이: 고도 오차 414.8 m (최대 581.7 m)
- 문제: 해양 상공에서 수직 속도가 과대평가됨

개선 방안:
1. 수직 속도 damping 파라미터 최적화
2. 해양 상공 특수 처리
3. 기압-고도 변환 정확도 개선

참고 문헌:
- Stein et al. (2015) BAMS
- Draxler & Hess (1998)
- HYSPLIT User's Guide
"""

import json
import numpy as np
from pathlib import Path

# 현재 결과 로드
results_file = Path("tests/integration/multi_location_24h_results.json")
with open(results_file, encoding='utf-8') as f:
    current_results = json.load(f)

print("="*80)
print("  Phase 1: 고도 계산 개선 분석")
print("="*80)

# 고도 오차가 큰 지역 분석
problem_locations = []
for loc_name, data in current_results.items():
    if "hysplit_comparison" in data:
        comp = data["hysplit_comparison"]
        avg_alt_error = comp["mean_vertical_error"]
        max_alt_error = comp["max_vertical_error"]
        
        if avg_alt_error > 200:  # 200m 이상 오차
            problem_locations.append({
                "name": loc_name,
                "avg_error": avg_alt_error,
                "max_error": max_alt_error,
                "start_lat": data["start"]["lat"],
                "start_lon": data["start"]["lon"],
            })

print(f"\n고도 오차 > 200m 지역: {len(problem_locations)}개")
for loc in sorted(problem_locations, key=lambda x: x["avg_error"], reverse=True):
    print(f"  {loc['name']}: 평균 {loc['avg_error']:.1f}m, 최대 {loc['max_error']:.1f}m")
    print(f"    위치: {loc['start_lat']:.1f}°N, {loc['start_lon']:.1f}°E")

# 패턴 분석
print(f"\n패턴 분석:")
print(f"  - 해양 상공 궤적에서 고도 오차 증가")
print(f"  - 수직 속도가 과대평가되는 것으로 추정")
print(f"  - HYSPLIT은 더 강한 damping을 사용하는 것으로 보임")

# 개선 전략
print(f"\n개선 전략:")
print(f"  1. vertical_damping 파라미터 조정: 0.0003 → 0.001~0.01")
print(f"  2. 해양 상공 특수 처리 추가")
print(f"  3. 기압-고도 변환 정확도 개선")

# 예상 효과
print(f"\n예상 효과:")
print(f"  - 부산 고도 오차: 427m → 200m (53% 개선)")
print(f"  - 타이베이 고도 오차: 415m → 200m (52% 개선)")
print(f"  - 전체 평균 고도 오차: 202.5m → 100m (51% 개선)")

print(f"\n다음 단계:")
print(f"  1. vertical_damping 파라미터 최적화 테스트")
print(f"  2. 최적 값 찾기 (grid search)")
print(f"  3. 재비교 및 검증")
