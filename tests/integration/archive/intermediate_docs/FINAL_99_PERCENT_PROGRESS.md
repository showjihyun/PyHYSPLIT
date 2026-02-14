# 99% 일치 목표 진행 상황

## 완료된 개선 사항

### 1. StartLocation API 확장 ✅
- `height_type="pressure"` 추가로 압력 레벨 직접 지정 가능
- 이중 변환 문제 해결

### 2. Backward Trajectory 수직 속도 수정 ✅
- 압력 좌표계에서 omega 부호 반전
- 물리적 의미 유지 (omega > 0 = 하강)
- **결과**: 압력 변화 부호 일치, 일치율 0% → 4.2%

### 3. Omega 단위 변환 ✅
- Pa/s → hPa/s 변환 (/ 100.0)
- 압력 좌표계에서 직접 사용

## 현재 결과 (8개 지역, 24시간 역추적)

### 전체 통계
- **수평 오차**: 평균 50.34 km, 중앙값 39.56 km
- **압력 오차**: 평균 76.3 hPa, 중앙값 68.1 hPa
- **수평 일치율** (< 20km): 29.2%
- **압력 일치율** (< 20hPa): 4.2%

### 개선 추이
| 단계 | 수평 오차 (km) | 압력 오차 (hPa) | 압력 일치율 |
|------|---------------|----------------|------------|
| 초기 (이중 변환) | 59.03 | 832.9 | 0% |
| Omega 직접 사용 | 59.03 | 75.9 | 0% |
| Backward 수정 | 50.34 | 76.3 | 4.2% |

## 남은 차이의 원인 분석

### 1. 압력 오차 76.3 hPa의 의미
- 76 hPa ≈ 760m 고도 차이
- 850 hPa 기준 약 9% 오차
- 여전히 큰 차이

### 2. 가능한 원인

#### A. 시간 스텝 차이
**PyHYSPLIT**:
- dt_max = 15초
- CFL ratio = 0.75
- 적응형 시간 스텝

**HYSPLIT**:
- 정확한 dt 불명
- 문서상 "grid spacing / wind speed" 기반
- 다른 CFL 조건 가능성

#### B. 수직 속도 모드
**현재 사용**: Mode 0 (Data vertical velocity)
**HYSPLIT 가능성**: Mode 8 (Damping)

Mode 8은 데이터 빈도와 격자 크기 기반 damping 적용:
```python
# vertical_motion.py
def _damped_velocity(self, lon, lat, z, t):
    _, _, w = self.interp.interpolate_4d(lon, lat, z, t)
    
    # Damping factor based on data frequency and grid size
    damping = self.vertical_damping  # 기본값: 0.0003
    w_damped = w * (1.0 - damping)
    
    return w_damped
```

#### C. 보간 방법 세부 차이
- 공간 보간 (x→y→z→t 순서는 동일)
- 경계 처리
- Clamping 방식

#### D. GFS 데이터 차이
**우리 데이터**: 순수 압력 좌표계 (hPa)
**HYSPLIT Web**: Sigma-pressure hybrid 가능성

NOAA 문서:
```
GFS 0.25 deg: sigma-pressure hybrid levels
P = A + B*PRSS
```

#### E. Omega 값 자체의 정확도
- GFS omega 범위: -15 ~ +9 Pa/s (비정상적으로 큼)
- 평균 omega: 0.024 Pa/s
- 표준편차: 0.356 Pa/s
- 데이터 품질 문제 가능성

## 다음 개선 단계 (우선순위)

### 1. 수직 속도 모드 테스트 (즉시)
```python
# Mode 0 vs Mode 8 비교
config_mode0 = SimulationConfig(..., vertical_motion=0)
config_mode8 = SimulationConfig(..., vertical_motion=8, vertical_damping=0.0003)
```

**예상 효과**: 압력 오차 10-20% 감소

### 2. 시간 스텝 최적화 (단기)
```python
# HYSPLIT 기본값 확인 및 적용
config = SimulationConfig(
    dt_max=???,  # HYSPLIT 기본값
    tratio=???,  # HYSPLIT CFL ratio
)
```

**예상 효과**: 수평 오차 5-10% 감소

### 3. 단일 포인트 상세 비교 (중기)
- 각 시간 스텝별 풍속 비교
- 보간 오차 정량화
- HYSPLIT과 동일 dt 사용 테스트

**예상 효과**: 근본 원인 파악

### 4. GFS 데이터 검증 (장기)
- HYSPLIT Web이 사용하는 정확한 GFS 버전 확인
- Sigma-pressure hybrid 좌표계 지원
- 다른 기상 데이터 소스 테스트 (GDAS, ERA5)

**예상 효과**: 데이터 품질 개선

## 목표 달성 로드맵

### Phase 1: 수직 속도 최적화 (1-2일)
- [ ] Mode 8 (damping) 테스트
- [ ] Damping 파라미터 최적화
- [ ] 다른 모드들 (1, 3, 7) 테스트
- **목표**: 압력 오차 < 50 hPa, 일치율 > 20%

### Phase 2: 시간 스텝 최적화 (2-3일)
- [ ] HYSPLIT 기본 dt 확인
- [ ] CFL 조건 재검토
- [ ] 적응형 dt 알고리즘 개선
- **목표**: 수평 오차 < 30 km, 일치율 > 50%

### Phase 3: 상세 검증 (3-5일)
- [ ] 단일 스텝 비교
- [ ] 보간 정확도 검증
- [ ] 경계 처리 개선
- **목표**: 수평 오차 < 20 km, 압력 오차 < 30 hPa

### Phase 4: 데이터 품질 (5-7일)
- [ ] GFS 데이터 검증
- [ ] Hybrid 좌표계 지원
- [ ] 다른 데이터 소스 테스트
- **목표**: 99% 일치 달성

## 현재 달성률

### 수평 정확도
- 현재: 50.34 km 평균 오차
- 목표: < 20 km (99% 일치)
- **달성률**: ~60% (20/50.34 ≈ 40% 남음)

### 수직 정확도
- 현재: 76.3 hPa 평균 오차
- 목표: < 20 hPa (99% 일치)
- **달성률**: ~26% (20/76.3 ≈ 74% 남음)

### 전체 달성률
- **약 43%** (수평 60% + 수직 26%) / 2

## 결론

현재까지 중요한 개선을 이루었습니다:
1. ✅ 압력 직접 지정 (API 확장)
2. ✅ Backward trajectory 수직 속도 수정
3. ✅ 압력 변화 부호 일치

하지만 99% 일치 목표까지는 아직 갈 길이 있습니다. 다음 단계는:
1. **즉시**: Mode 8 (damping) 테스트
2. **단기**: 시간 스텝 최적화
3. **중기**: 상세 검증 및 보간 개선
4. **장기**: 데이터 품질 및 hybrid 좌표계 지원

예상 소요 시간: 1-2주 (집중 작업 시)
