# Next Investigation Steps

## Current Status Summary

### Overall Progress: 70%

| Metric | Current | Goal | Progress |
|--------|---------|------|----------|
| Pressure Error (mean) | 31.8 hPa | <20 hPa | 68% |
| Pressure Error (median) | 23.2 hPa | <20 hPa | 87% |
| Horizontal Error (mean) | 43.31 km | <20 km | 65% |
| Horizontal Error (median) | 25.34 km | <20 km | 78% |

## Critical Discovery: Inconsistent Omega Behavior

### Problem
압력 변화 방향이 일부 위치에서만 맞고 일부는 틀립니다:

**방향이 맞는 위치 (5/8 = 62.5%)**:
- 서울, 부산, 도쿄, 오사카, 베이징
- 평균 위도: 36.6°N
- Omega 양수 비율: 46.7%

**방향이 틀린 위치 (3/8 = 37.5%)**:
- 제주, 상하이, 타이베이
- 평균 위도: 29.9°N
- Omega 양수 비율: 88.9%

### Analysis

1. **위도 패턴**: 남쪽 위치(29.9°N)에서 방향이 틀림
2. **Omega 부호**: 틀린 위치들은 대부분 양수 omega (하강)
3. **HYSPLIT Web 결과**: 이 위치들은 상승(+ΔP)을 보임

### Hypothesis

HYSPLIT이 다음 중 하나를 사용할 가능성:

1. **위도 의존적 omega 처리**
   - 북반구/남반구에 따라 다른 부호 규칙?
   - 중위도 vs 저위도 다른 처리?

2. **수직 속도 모드 차이**
   - HYSPLIT Web이 Mode 0이 아닌 다른 모드 사용?
   - Mode별로 omega 부호 처리가 다를 수 있음

3. **Omega 정의 차이**
   - GFS omega vs HYSPLIT 내부 omega 정의 차이?
   - 좌표계 변환 시 부호 규칙?

4. **역궤적 특수 처리**
   - HYSPLIT이 역궤적에서 위치별로 다른 알고리즘 사용?

## Priority 1: HYSPLIT Web 설정 확인

### Action Items

1. **HYSPLIT Web 수직 속도 모드 확인**
   ```
   - HYSPLIT Web UI에서 "Vertical Motion" 설정 확인
   - 기본값이 Mode 0인지, 다른 모드인지 확인
   - 각 모드별로 테스트 실행
   ```

2. **HYSPLIT 소스 코드 분석**
   ```
   - NOAA HYSPLIT 소스 코드에서 omega 처리 부분 찾기
   - 역궤적에서 omega 부호 처리 로직 확인
   - 위도 의존적 처리가 있는지 확인
   ```

3. **GFS Omega 데이터 검증**
   ```
   - GFS omega 값이 올바른지 확인
   - HYSPLIT이 사용하는 omega와 동일한지 확인
   - 단위 변환이 올바른지 재확인
   ```

## Priority 2: 수직 속도 모드 재테스트

### Test Plan

각 위치에서 모든 수직 속도 모드(0, 1, 3, 7, 8) 테스트:

```python
modes = [0, 1, 3, 7, 8]
locations = ['서울', '부산', '제주', '도쿄', '오사카', '베이징', '상하이', '타이베이']

for mode in modes:
    for location in locations:
        # Run trajectory with mode
        # Compare with HYSPLIT Web
        # Record pressure change direction and error
```

### Expected Outcome

- 특정 모드에서 모든 위치의 방향이 맞는지 확인
- 위치별로 다른 모드가 필요한지 확인

## Priority 3: Omega 부호 규칙 재검토

### Hypothesis Testing

**Test 1: 조건부 부호 반전**
```python
def _convert_w_to_dz_dt(self, w, z, t, lon, lat, dt):
    if met.z_type == "pressure":
        # 위도 기반 조건부 처리?
        if lat < 35.0:  # 저위도
            return -w if dt < 0 else w
        else:  # 중위도
            return w
```

**Test 2: Omega 절대값 사용**
```python
def _convert_w_to_dz_dt(self, w, z, t, lon, lat, dt):
    if met.z_type == "pressure":
        # 항상 하강 방향으로?
        return abs(w) if dt < 0 else w
```

**Test 3: 수직 속도 모드별 부호 규칙**
```python
def _convert_w_to_dz_dt(self, w, z, t, lon, lat, dt):
    if met.z_type == "pressure":
        if self.vertical_motion_mode == 0:
            return w  # 현재 구현
        elif self.vertical_motion_mode == 1:
            return -w if dt < 0 else w  # 이전 구현
        # ...
```

## Priority 4: HYSPLIT 문서 재검토

### Documents to Review

1. **Stein et al. (2015) - Section 2a**
   - 수직 속도 처리 방법
   - 역궤적 특수 처리

2. **Draxler & Hess (1998)**
   - Omega 정의 및 부호 규칙
   - 좌표계 변환

3. **HYSPLIT-4 User's Guide**
   - 수직 속도 모드 설명
   - 역궤적 알고리즘

### Key Questions

1. HYSPLIT에서 omega 부호 정의는?
2. 역궤적에서 omega를 어떻게 처리하는가?
3. 위도 의존적 처리가 있는가?
4. 수직 속도 모드별 차이는?

## Priority 5: 대안 접근법

### Option A: 위치별 보정 계수

각 위치에 대해 경험적 보정 계수 적용:

```python
OMEGA_CORRECTION = {
    'default': 1.0,
    'jeju': -1.0,      # 부호 반전
    'shanghai': -1.0,
    'taipei': -1.0,
}
```

**장점**: 즉시 정확도 향상
**단점**: 물리적 의미 없음, 일반화 불가

### Option B: 머신러닝 기반 보정

GFS omega → HYSPLIT 실제 압력 변화 학습:

```python
# Train on 8 locations
X = [lat, lon, pressure, omega, u, v, t]
y = actual_pressure_change

model = RandomForestRegressor()
model.fit(X, y)
```

**장점**: 패턴 자동 학습
**단점**: 물리적 해석 어려움

### Option C: 하이브리드 모드

여러 수직 속도 모드의 가중 평균:

```python
w_final = 0.5 * w_mode0 + 0.3 * w_mode1 + 0.2 * w_mode3
```

**장점**: 여러 모드의 장점 결합
**단점**: 가중치 결정 어려움

## Immediate Next Steps

1. **HYSPLIT Web 설정 확인** (1시간)
   - 수직 속도 모드 확인
   - 다른 설정 옵션 확인

2. **모든 모드 테스트** (2시간)
   - 8개 위치 × 5개 모드 = 40개 테스트
   - 결과 비교 및 분석

3. **HYSPLIT 소스 코드 분석** (3시간)
   - Omega 처리 로직 찾기
   - 역궤적 특수 처리 확인

4. **문서 재검토** (2시간)
   - 관련 논문 재읽기
   - 수직 속도 처리 부분 집중

5. **가설 테스트** (2시간)
   - 조건부 부호 반전 테스트
   - 결과 분석

**Total Estimated Time**: 10 hours

## Success Criteria

- 모든 8개 위치에서 압력 변화 방향 일치
- 평균 압력 오차 <20 hPa
- 압력 일치율 >80%

## Risk Assessment

**High Risk**:
- HYSPLIT 내부 알고리즘이 문서화되지 않은 경우
- 위치별로 다른 알고리즘을 사용하는 경우

**Medium Risk**:
- 수직 속도 모드 차이만으로 해결 안 되는 경우
- GFS 데이터 자체에 문제가 있는 경우

**Low Risk**:
- 단순한 부호 규칙 차이인 경우
- 설정 옵션 차이인 경우

## Conclusion

현재 70% 진행률에서 가장 큰 장애물은 **일관성 없는 omega 부호 처리**입니다. 이를 해결하면 80-85% 진행률 달성 가능할 것으로 예상됩니다.

다음 단계는 HYSPLIT Web 설정 확인과 모든 수직 속도 모드 테스트입니다.
