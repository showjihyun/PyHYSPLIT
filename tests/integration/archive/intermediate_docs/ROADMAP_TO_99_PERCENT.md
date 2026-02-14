# PyHYSPLIT 99% 일치 달성 로드맵

## 현재 상태
- **수평 거리:** 평균 15.55 km (98.4% 일치)
- **고도:** 평균 60.2 m (92.9% 일치, 850m 기준)
- **전체 일치도:** ~95%

## 목표
- **수평 거리:** <2 km (99.8% 일치)
- **고도:** <10 m (98.8% 일치)
- **전체 일치도:** >99%

---

## 단계 1: 미세 파라미터 튜닝 (예상 개선: 2-3%)

### 1.1 Vertical Damping Factor 정밀 스캔
```python
# 현재: 0.0003
# 테스트 범위: 0.00025 ~ 0.00035 (0.00001 간격)
damping_values = np.arange(0.00025, 0.00036, 0.00001)

# 각 값에 대해:
# - 평균 고도 오차 측정
# - 최적값 선택 (목표: <30m)
```

### 1.2 Scale Height 정밀 조정
```python
# 현재: 8430m
# 테스트 범위: 8420 ~ 8450m (2m 간격)
scale_heights = np.arange(8420, 8451, 2)

# 각 값에 대해:
# - 초기 고도 오차 측정
# - 최적값 선택 (목표: <10m)
```

### 1.3 Time Step 최적화
```python
# 현재: dt_max = 15s
# 테스트: 5s, 7s, 10s, 12s, 15s, 20s

# 더 작은 dt는 더 정확하지만 느림
# 목표: 정확도와 속도의 최적 균형
```

### 1.4 TRATIO 미세 조정
```python
# 현재: 0.75
# 테스트 범위: 0.72 ~ 0.78 (0.01 간격)

# 수평 drift에 영향
# 목표: 동쪽/북쪽 drift 최소화
```

**예상 결과:** 수평 10-12km, 고도 40-50m

---

## 단계 2: 알고리즘 정밀도 개선 (예상 개선: 3-4%)

### 2.1 보간 방식 개선
```python
# 현재: Trilinear interpolation
# 개선: Tricubic interpolation (더 부드러운 보간)

# 또는 HYSPLIT과 동일한 가중치 사용
# - 격자 경계에서의 특별 처리
# - 비균일 격자 처리
```

### 2.2 지구 곡률 계산 정밀화
```python
# 현재: 단순 구면 좌표 변환
# 개선: Vincenty 공식 또는 Haversine 개선

def advect_lonlat_precise(lon, lat, u, v, dt):
    """More accurate great circle calculation."""
    # WGS84 타원체 사용
    # 또는 더 정확한 대원 거리 계산
    pass
```

### 2.3 수치 정밀도 향상
```python
# 현재: float64 (배정밀도)
# 개선: float128 (4배 정밀도) - 누적 오차 감소

# 또는 Kahan summation algorithm 사용
# - 부동소수점 오차 최소화
```

### 2.4 시간 보간 개선
```python
# 현재: 선형 보간
# 개선: 
# - 3차 스플라인 보간
# - 또는 HYSPLIT의 정확한 시간 가중치 사용
```

**예상 결과:** 수평 6-8km, 고도 25-35m

---

## 단계 3: HYSPLIT 특수 처리 구현 (예상 개선: 2-3%)

### 3.1 격자 경계 처리
```python
# HYSPLIT은 격자 경계에서 특별한 처리를 할 수 있음
# - 경계 근처에서 보간 가중치 조정
# - 외삽 방지 메커니즘
```

### 3.2 출력 시간 정렬
```python
# HYSPLIT Web은 정확히 1시간 간격으로 출력
# 현재: 가장 가까운 시간으로 보간
# 개선: 정확한 시간에 도달하도록 시간 step 조정
```

### 3.3 압력-고도 변환 일관성
```python
# 초기 변환과 출력 변환을 완전히 일치시킴
# - 동일한 온도 프로파일 사용
# - 또는 lookup table 사용
```

### 3.4 수직 속도 처리 세부사항
```python
# HYSPLIT의 정확한 omega 처리 방식
# - 압력 좌표계에서의 정확한 적분
# - 경계층 효과 고려
# - 지형 영향 고려
```

**예상 결과:** 수평 3-5km, 고도 15-25m

---

## 단계 4: HYSPLIT 소스 코드 분석 (예상 개선: 1-2%)

### 4.1 소스 코드 접근
```bash
# HYSPLIT 등록 및 소스 코드 다운로드
# https://www.ready.noaa.gov/HYSPLIT_linux.php

# 주요 파일:
# - advpnt.f: 이동 계산
# - advmet.f: 기상 데이터 보간
# - adviec.f: 적분 계산
```

### 4.2 핵심 알고리즘 추출
```fortran
! HYSPLIT Fortran 코드에서:
! 1. 정확한 보간 가중치
! 2. 시간 step 계산 방식
! 3. 수직 속도 damping 공식
! 4. 경계 처리 로직
```

### 4.3 Python 구현
```python
# Fortran 코드를 Python으로 정확히 변환
# - 동일한 수치 정밀도
# - 동일한 알고리즘 순서
# - 동일한 상수 값
```

**예상 결과:** 수평 <2km, 고도 <10m

---

## 단계 5: 검증 및 최적화 (예상 개선: 0.5-1%)

### 5.1 다중 테스트 케이스
```python
# 다양한 조건에서 테스트:
# - 다른 시작 위치
# - 다른 고도
# - 다른 시간대
# - 다른 기간 (24h, 48h, 72h)
```

### 5.2 통계적 검증
```python
# 100개 이상의 궤적으로 검증
# - 평균 오차
# - 표준편차
# - 최대 오차
# - 99% 신뢰구간
```

### 5.3 기계학습 보정
```python
# 남은 체계적 오차를 ML로 보정
# - 입력: 위치, 시간, 기상 조건
# - 출력: 보정 벡터
# - 모델: Random Forest 또는 Neural Network
```

**예상 결과:** 수평 <1km, 고도 <5m

---

## 구현 우선순위

### 즉시 구현 가능 (1-2일)
1. ✅ Damping factor 정밀 스캔 (0.00025 ~ 0.00035)
2. ✅ Scale height 정밀 조정 (8420 ~ 8450m)
3. ✅ dt_max 테스트 (5s ~ 20s)
4. ✅ TRATIO 미세 조정 (0.72 ~ 0.78)

### 단기 구현 (1주)
5. ⏳ Tricubic interpolation 구현
6. ⏳ 출력 시간 정렬 개선
7. ⏳ 수치 정밀도 향상 (Kahan summation)
8. ⏳ 격자 경계 처리 개선

### 중기 구현 (2-4주)
9. ⏳ HYSPLIT 소스 코드 등록 및 다운로드
10. ⏳ 핵심 알고리즘 분석 및 추출
11. ⏳ Python 정확 구현
12. ⏳ 다중 테스트 케이스 검증

### 장기 구현 (1-2개월)
13. ⏳ 기계학습 보정 모델 개발
14. ⏳ 대규모 검증 (1000+ 궤적)
15. ⏳ 성능 최적화
16. ⏳ 문서화 및 배포

---

## 자동화된 최적화 전략

### Grid Search
```python
from itertools import product

# 파라미터 그리드
params = {
    'damping': np.arange(0.00025, 0.00036, 0.00001),
    'scale_height': np.arange(8420, 8451, 2),
    'dt_max': [5, 10, 15, 20],
    'tratio': np.arange(0.72, 0.79, 0.01)
}

# 모든 조합 테스트
best_score = float('inf')
best_params = None

for damping, sh, dt, tr in product(*params.values()):
    score = test_configuration(damping, sh, dt, tr)
    if score < best_score:
        best_score = score
        best_params = (damping, sh, dt, tr)
```

### Bayesian Optimization
```python
from skopt import gp_minimize

# 목적 함수
def objective(params):
    damping, scale_height, dt_max, tratio = params
    result = test_configuration(damping, scale_height, dt_max, tratio)
    return result['mean_distance'] + result['mean_height_diff'] / 100

# 최적화
result = gp_minimize(
    objective,
    dimensions=[
        (0.00025, 0.00035),  # damping
        (8420, 8450),         # scale_height
        (5, 20),              # dt_max
        (0.72, 0.78)          # tratio
    ],
    n_calls=100,
    random_state=42
)
```

### Genetic Algorithm
```python
from deap import base, creator, tools, algorithms

# 유전 알고리즘으로 최적 파라미터 탐색
# - 빠른 수렴
# - 전역 최적해 탐색
# - 다목적 최적화 가능 (수평 + 수직)
```

---

## 예상 타임라인

| 단계 | 기간 | 예상 일치도 |
|------|------|------------|
| 현재 | - | 95% |
| 단계 1 완료 | 1-2일 | 97% |
| 단계 2 완료 | 1주 | 98% |
| 단계 3 완료 | 2주 | 98.5% |
| 단계 4 완료 | 1개월 | 99% |
| 단계 5 완료 | 2개월 | 99.5% |

---

## 결론

99% 일치는 달성 가능하지만, 다음이 필요합니다:

1. **체계적인 파라미터 최적화** (즉시 가능)
2. **알고리즘 정밀도 개선** (1-2주)
3. **HYSPLIT 소스 코드 분석** (1개월, 가장 확실한 방법)
4. **기계학습 보정** (선택사항, 추가 1-2%)

**추천 접근:**
1. 먼저 단계 1-2를 구현하여 97-98% 달성
2. HYSPLIT 소스 코드 등록 및 분석
3. 핵심 알고리즘을 정확히 복제
4. 필요시 ML 보정 추가

이 로드맵을 따르면 99% 이상의 일치도를 달성할 수 있습니다!
