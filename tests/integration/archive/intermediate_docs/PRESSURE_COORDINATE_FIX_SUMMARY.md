# 압력 좌표계 수정 완료 보고서

## 작업 완료 사항

### 1. StartLocation API 확장 ✅
`pyhysplit/models.py`의 `StartLocation` 클래스에 `height_type` 파라미터 추가:

```python
@dataclass
class StartLocation:
    lat: float
    lon: float
    height: float
    height_type: str = "meters_agl"  # "meters_agl" 또는 "pressure"
```

**기능**:
- `height_type="meters_agl"`: 기존 동작 (meters AGL → 압력 변환)
- `height_type="pressure"`: 압력 레벨 직접 지정 (hPa)

### 2. TrajectoryEngine 변환 로직 수정 ✅
`pyhysplit/engine.py`의 `_validate_and_convert_start_locations()` 메서드 수정:

**변경 사항**:
- `height_type="pressure"` 지원 추가
- 압력 범위 검증 로직 수정 (min/max 올바르게 처리)
- 압력 좌표계에서 직접 지정 시 변환 생략

**코드**:
```python
if height_type == "pressure":
    # 직접 압력 지정 - 변환 없음
    z_converted = height_value
    logger.info(f"Start location {idx}: {height_value:.1f} hPa (direct pressure)")
elif self.met.z_type == "pressure":
    # meters AGL → 압력 변환
    pressure_pa = CoordinateConverter.height_to_pressure(...)
    z_converted = pressure_pa / 100.0
```

### 3. 비교 스크립트 수정 ✅
`tests/integration/multi_location_24h_comparison.py` 수정:

**변경 사항**:
- 압력 직접 지정 사용: `StartLocation(lat, lon, height=850.0, height_type="pressure")`
- 궤적 결과에 압력 데이터 추가: `{'lat', 'lon', 'height', 'pressure'}`
- HYSPLIT Web tdump 파일에서 압력 읽기
- 비교 로직을 압력 기반으로 변경 (meters 대신 hPa)

### 4. 압력 범위 검증 수정 ✅
압력 좌표계의 특성 반영:
- 압력은 고도가 높아질수록 감소 (1000 hPa → 200 hPa)
- z_grid가 [1000, 850, 700] 또는 [200, 500, 1000] 모두 지원
- min/max를 올바르게 계산하여 검증

## 테스트 결과

### 압력 직접 지정 테스트
```
테스트 1: height_type='pressure'로 850 hPa 직접 지정
  ✓ 엔진 생성 성공
  변환된 시작 위치: [(127.0, 37.0, 850.0)]
  시작 압력: 850.0 hPa

테스트 2: height_type='meters_agl'로 1400m 지정
  ✓ 엔진 생성 성공
  변환된 시작 위치: [(127.0, 37.0, 858.2)]
  시작 압력: 858.2 hPa
```

### 8개 지역 24시간 역추적 비교

**수평 오차**:
- 평균: 59.03 km
- 중앙값: 46.26 km
- 최대: 189.55 km
- 일치율 (< 20km): 27.8%

**압력 오차**:
- 평균: 75.9 hPa
- 중앙값: 70.8 hPa
- 최대: 130.5 hPa
- 일치율 (< 20hPa): 0.0%

## 남은 문제

### 1. 압력 오차가 여전히 큼
- 평균 75.9 hPa ≈ 750m 고도 차이
- 0% 일치율 (< 20hPa 기준)

### 2. 가능한 원인
1. **Omega 값 자체의 정확도**:
   - GFS omega 범위: -15 ~ +9 Pa/s (비정상적으로 큼)
   - 변환 후 w: -1.2 ~ +2.0 m/s (정상 범위)
   - 하지만 압력 좌표계에서는 omega를 hPa/s로 직접 사용

2. **수직 속도 스케일링**:
   - 현재: omega / 100.0 (Pa/s → hPa/s)
   - HYSPLIT이 다른 스케일링 사용 가능성

3. **적분 방법 차이**:
   - PyHYSPLIT: Heun (Modified Euler)
   - HYSPLIT: 동일하다고 문서화되어 있지만 세부 구현 차이 가능

4. **시간 스텝 차이**:
   - PyHYSPLIT: CFL 기반 적응형 dt (최대 15초)
   - HYSPLIT: 다른 dt 전략 가능성

5. **보간 방법 차이**:
   - 공간 보간 (x→y→z→t 순서는 동일)
   - 시간 보간 세부 구현 차이 가능

## 다음 단계

### 즉시 조치
1. ✅ StartLocation API 확장 완료
2. ✅ 압력 직접 지정 지원 완료
3. ✅ 압력 기반 비교 구현 완료

### 추가 개선 (우선순위)
1. **Omega 스케일링 검증**:
   - HYSPLIT 소스 코드 확인
   - Omega → dP/dt 변환 공식 재검토
   - 다른 스케일 팩터 테스트

2. **수직 속도 모드 테스트**:
   - Mode 0 (data): 현재 사용 중
   - Mode 8 (damping): 테스트 필요
   - 다른 모드들과 비교

3. **시간 스텝 최적화**:
   - dt_max 조정 (현재 15초)
   - CFL ratio 조정 (현재 0.75)
   - HYSPLIT 기본값 확인

4. **보간 정확도 검증**:
   - 단일 포인트 상세 비교
   - 각 시간 스텝별 풍속 비교
   - 보간 오차 정량화

### 장기 목표
- 99% 일치율 달성 (수평 < 20km, 압력 < 20hPa)
- HYSPLIT과 1:1 검증 완료
- 문서화 및 테스트 케이스 추가

## 사용 예제

### 압력 레벨 직접 지정
```python
from pyhysplit.models import StartLocation, SimulationConfig
from pyhysplit.engine import TrajectoryEngine

# 850 hPa 압력 레벨에서 시작
start_loc = StartLocation(
    lat=37.5,
    lon=127.0,
    height=850.0,
    height_type="pressure"  # 압력 직접 지정
)

config = SimulationConfig(
    start_time=datetime(2026, 2, 14, 0, 0),
    num_start_locations=1,
    start_locations=[start_loc],
    total_run_hours=-24,
    vertical_motion=0,
    model_top=10000.0,
    met_files=[],
    turbulence_on=False
)

engine = TrajectoryEngine(config, met_data)
trajectory = engine.run()[0]
```

### 기존 방식 (meters AGL)
```python
# 1400m AGL에서 시작 (압력으로 자동 변환)
start_loc = StartLocation(
    lat=37.5,
    lon=127.0,
    height=1400.0,
    height_type="meters_agl"  # 또는 생략 (기본값)
)
```

## 호환성

### 하위 호환성 유지
- `height_type` 기본값: `"meters_agl"`
- 기존 코드 수정 불필요
- 새로운 기능은 opt-in

### 테스트 커버리지
- ✅ 압력 직접 지정 테스트
- ✅ meters AGL 변환 테스트
- ✅ 압력 범위 검증 테스트
- ⏳ 단위 테스트 추가 필요

## 결론

압력 좌표계에서 압력 레벨을 직접 지정할 수 있도록 API를 확장했습니다. 이로 인해:
- ✅ 이중 변환 문제 해결
- ✅ HYSPLIT Web과 동일한 시작 조건 사용 가능
- ⚠️ 압력 오차는 여전히 큼 (추가 조사 필요)

다음 단계는 omega 스케일링과 수직 속도 모드를 검증하여 압력 오차를 줄이는 것입니다.
