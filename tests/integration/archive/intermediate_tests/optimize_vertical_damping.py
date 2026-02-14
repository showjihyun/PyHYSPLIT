"""Vertical Damping 파라미터 최적화

HYSPLIT Web 비교 결과를 바탕으로 vertical_damping 파라미터를 최적화합니다.

현재 문제:
- 부산: 고도 오차 427m (해양 상공)
- 타이베이: 고도 오차 415m (해양 상공)
- 상하이: 고도 오차 318m (해양 상공)

HYSPLIT 문서 참고:
- Mode 8: Damping based on data frequency and grid size ratio
- 수직 속도는 수평 속도보다 100배 약함
- 해양 상공에서 더 강한 damping 필요
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
import numpy as np

# 현재 결과 로드
results_file = Path("tests/integration/multi_location_24h_results.json")
with open(results_file, encoding='utf-8') as f:
    current_results = json.load(f)

# HYSPLIT Web tdump 파일 로드
def load_tdump(location_name):
    """HYSPLIT Web tdump 파일에서 고도 데이터 추출"""
    tdump_file = Path(f"tests/integration/hysplit_web_data/tdump_{location_name}.txt")
    if not tdump_file.exists():
        return None
    
    heights = []
    with open(tdump_file, 'r') as f:
        lines = f.readlines()
        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 12:
                try:
                    # tdump 형식: ... lat lon height ...
                    height = float(parts[11])  # 고도 (m AGL)
                    heights.append(height)
                except:
                    continue
    return heights

print("="*80)
print("  Vertical Damping 파라미터 최적화")
print("="*80)

# 각 지역의 고도 변화 분석
print("\n지역별 고도 변화 분석:")
print(f"{'지역':<10} {'PyHYSPLIT':<15} {'HYSPLIT Web':<15} {'오차':<10}")
print("-"*50)

analysis = {}
for loc_name in ["서울", "부산", "제주", "도쿄", "오사카", "베이징", "상하이", "타이베이"]:
    # PyHYSPLIT 결과
    pyhysplit_start = current_results[loc_name]["start"]["height"]
    pyhysplit_end = current_results[loc_name]["end"]["height"]
    pyhysplit_change = abs(pyhysplit_end - pyhysplit_start)
    
    # HYSPLIT Web 결과
    hysplit_heights = load_tdump(loc_name)
    if hysplit_heights and len(hysplit_heights) >= 2:
        hysplit_change = abs(hysplit_heights[-1] - hysplit_heights[0])
        error = abs(pyhysplit_change - hysplit_change)
        
        analysis[loc_name] = {
            "pyhysplit_change": pyhysplit_change,
            "hysplit_change": hysplit_change,
            "error": error,
            "vertical_error": current_results[loc_name]["hysplit_comparison"]["mean_vertical_error"]
        }
        
        print(f"{loc_name:<10} {pyhysplit_change:>10.1f}m {hysplit_change:>10.1f}m {error:>8.1f}m")

# 패턴 분석
print("\n패턴 분석:")
high_error_locs = [k for k, v in analysis.items() if v["vertical_error"] > 200]
print(f"  고도 오차 > 200m: {', '.join(high_error_locs)}")

# 평균 오차 비율 계산
total_pyhysplit = sum(v["pyhysplit_change"] for v in analysis.values())
total_hysplit = sum(v["hysplit_change"] for v in analysis.values())
ratio = total_pyhysplit / total_hysplit if total_hysplit > 0 else 1.0

print(f"\n고도 변화 비율:")
print(f"  PyHYSPLIT 총 변화: {total_pyhysplit:.1f}m")
print(f"  HYSPLIT Web 총 변화: {total_hysplit:.1f}m")
print(f"  비율: {ratio:.3f}")

# 최적 damping 계산
current_damping = 0.0003
if ratio < 1.0:
    # PyHYSPLIT이 더 작은 고도 변화 → damping 감소 필요 (수직 속도 더 사용)
    optimal_damping = current_damping * ratio
    print(f"\n⚠️  PyHYSPLIT의 고도 변화가 너무 작습니다!")
    print(f"  → 수직 속도를 더 많이 사용해야 합니다")
    print(f"\n권장 vertical_damping:")
    print(f"  현재: {current_damping}")
    print(f"  최적: {optimal_damping:.6f}")
    print(f"  변화: {(optimal_damping/current_damping - 1)*100:+.1f}%")
    print(f"\n또는 Mode 0 (Data vertical velocity)를 직접 사용하세요")
else:
    print(f"\n현재 damping이 적절합니다: {current_damping}")

# 개선 예상
print(f"\n개선 예상 효과:")
if ratio < 1.0:
    for loc_name in high_error_locs:
        current_error = analysis[loc_name]["vertical_error"]
        expected_error = current_error * ratio  # 비율에 맞춰 조정
        improvement = (1 - expected_error/current_error) * 100
        print(f"  {loc_name}: {current_error:.1f}m → {expected_error:.1f}m ({improvement:.1f}% 개선)")

print(f"\n다음 단계:")
print(f"  1. pyhysplit/vertical_motion.py에서 vertical_damping 수정")
print(f"  2. 재계산 및 비교")
print(f"  3. 필요시 추가 미세 조정")
