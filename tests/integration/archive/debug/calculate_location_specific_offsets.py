"""위치별 최적 압력 오프셋 계산"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np

# 각 위치의 실제 압력 데이터 (extract_all_start_pressures.py 결과)
locations = {
    '서울': {'lat': 37.5, 'lon': 127.0, 'input': 850.0, 'actual': 906.3, 'offset': 56.3},
    '부산': {'lat': 35.1, 'lon': 129.0, 'input': 850.0, 'actual': 909.2, 'offset': 59.2},
    '제주': {'lat': 33.5, 'lon': 126.5, 'input': 850.0, 'actual': 889.2, 'offset': 39.2},
    '도쿄': {'lat': 35.7, 'lon': 139.7, 'input': 850.0, 'actual': 915.7, 'offset': 65.7},
    '오사카': {'lat': 34.7, 'lon': 135.5, 'input': 850.0, 'actual': 911.4, 'offset': 61.4},
    '베이징': {'lat': 39.9, 'lon': 116.4, 'input': 850.0, 'actual': 910.7, 'offset': 60.7},
    '상하이': {'lat': 31.2, 'lon': 121.5, 'input': 850.0, 'actual': 916.4, 'offset': 66.4},
    '타이베이': {'lat': 25.0, 'lon': 121.5, 'input': 850.0, 'actual': 899.8, 'offset': 49.8},
}

print("="*80)
print("  위치별 압력 오프셋 분석")
print("="*80)

# 통계
offsets = [loc['offset'] for loc in locations.values()]
lats = [loc['lat'] for loc in locations.values()]
lons = [loc['lon'] for loc in locations.values()]

print(f"\n기본 통계:")
print(f"  평균: {np.mean(offsets):.1f} hPa")
print(f"  표준편차: {np.std(offsets):.1f} hPa")
print(f"  최소: {np.min(offsets):.1f} hPa ({[k for k,v in locations.items() if v['offset']==np.min(offsets)][0]})")
print(f"  최대: {np.max(offsets):.1f} hPa ({[k for k,v in locations.items() if v['offset']==np.max(offsets)][0]})")

# 위도/경도와의 상관관계
corr_lat = np.corrcoef(lats, offsets)[0, 1]
corr_lon = np.corrcoef(lons, offsets)[0, 1]

print(f"\n상관관계:")
print(f"  위도 vs 오프셋: {corr_lat:.3f}")
print(f"  경도 vs 오프셋: {corr_lon:.3f}")

# 위도 기반 선형 회귀
from numpy.polynomial import Polynomial
p_lat = Polynomial.fit(lats, offsets, 1)
a_lat, b_lat = p_lat.convert().coef

print(f"\n위도 기반 선형 모델:")
print(f"  offset = {a_lat:.2f} + {b_lat:.2f} * lat")
print(f"  R² = {corr_lat**2:.3f}")

# 경도 기반 선형 회귀
p_lon = Polynomial.fit(lons, offsets, 1)
a_lon, b_lon = p_lon.convert().coef

print(f"\n경도 기반 선형 모델:")
print(f"  offset = {a_lon:.2f} + {b_lon:.2f} * lon")
print(f"  R² = {corr_lon**2:.3f}")

# 2차원 선형 회귀 (위도 + 경도)
from sklearn.linear_model import LinearRegression
X = np.array([[lat, lon] for lat, lon in zip(lats, lons)])
y = np.array(offsets)
model = LinearRegression()
model.fit(X, y)

a0 = model.intercept_
a1, a2 = model.coef_
r2 = model.score(X, y)

print(f"\n2차원 선형 모델 (위도 + 경도):")
print(f"  offset = {a0:.2f} + {a1:.2f} * lat + {a2:.2f} * lon")
print(f"  R² = {r2:.3f}")

# 각 모델의 예측 정확도
print(f"\n{'='*80}")
print("  모델 비교")
print(f"{'='*80}")

print(f"\n{'위치':>8} {'실제':>8} {'고정':>8} {'위도':>8} {'경도':>8} {'2D':>8} {'최적':>8}")
print("-"*80)

errors_fixed = []
errors_lat = []
errors_lon = []
errors_2d = []

for name, loc in locations.items():
    actual = loc['offset']
    fixed = 57.3
    lat_pred = a_lat + b_lat * loc['lat']
    lon_pred = a_lon + b_lon * loc['lon']
    pred_2d = a0 + a1 * loc['lat'] + a2 * loc['lon']
    
    # 오차 계산
    err_fixed = abs(actual - fixed)
    err_lat = abs(actual - lat_pred)
    err_lon = abs(actual - lon_pred)
    err_2d = abs(actual - pred_2d)
    
    errors_fixed.append(err_fixed)
    errors_lat.append(err_lat)
    errors_lon.append(err_lon)
    errors_2d.append(err_2d)
    
    # 최적 모델 표시
    best_err = min(err_fixed, err_lat, err_lon, err_2d)
    if best_err == err_fixed:
        best = "고정"
    elif best_err == err_lat:
        best = "위도"
    elif best_err == err_lon:
        best = "경도"
    else:
        best = "2D"
    
    print(f"{name:>8} {actual:>8.1f} {fixed:>8.1f} {lat_pred:>8.1f} {lon_pred:>8.1f} {pred_2d:>8.1f} {best:>8}")

print(f"\n평균 절대 오차:")
print(f"  고정 오프셋 (57.3): {np.mean(errors_fixed):.2f} hPa")
print(f"  위도 기반: {np.mean(errors_lat):.2f} hPa")
print(f"  경도 기반: {np.mean(errors_lon):.2f} hPa")
print(f"  2D 모델: {np.mean(errors_2d):.2f} hPa")

print(f"\n{'='*80}")
print("  권장 사항")
print(f"{'='*80}")

if np.mean(errors_2d) < np.mean(errors_fixed) * 0.8:
    print(f"\n✓ 2D 모델 사용 권장 (오차 {np.mean(errors_2d):.2f} hPa)")
    print(f"  offset = {a0:.2f} + {a1:.2f} * lat + {a2:.2f} * lon")
    print(f"\n구현 예시:")
    print(f"  def get_pressure_offset(lat, lon):")
    print(f"      return {a0:.2f} + {a1:.2f} * lat + {a2:.2f} * lon")
elif np.mean(errors_lat) < np.mean(errors_fixed) * 0.8:
    print(f"\n✓ 위도 기반 모델 사용 권장 (오차 {np.mean(errors_lat):.2f} hPa)")
    print(f"  offset = {a_lat:.2f} + {b_lat:.2f} * lat")
else:
    print(f"\n✓ 고정 오프셋 유지 권장 (오차 {np.mean(errors_fixed):.2f} hPa)")
    print(f"  offset = 57.3 hPa")
    print(f"\n이유: 복잡한 모델의 개선 효과가 미미함 (<20%)")

# 개별 위치 매핑 (가장 정확)
print(f"\n대안: 개별 위치 매핑 (가장 정확, 오차 0)")
print(f"  LOCATION_OFFSETS = {{")
for name, loc in locations.items():
    print(f"      ({loc['lat']}, {loc['lon']}): {loc['offset']:.1f},  # {name}")
print(f"  }}")
