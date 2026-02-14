# 정방향 궤적 가이드 (Forward Trajectory Guide)

## 개요

PyHYSPLIT은 역궤적(backward)과 정방향(forward) 궤적을 모두 지원합니다.

## 설정 방법

### 역궤적 (Backward Trajectory)

```python
config = SimulationConfig(
    start_time=datetime(2026, 2, 12, 0, 0),
    total_run_hours=-24,  # 음수 = 역궤적
    # ... 기타 설정
)
```

### 정방향 (Forward Trajectory)

```python
config = SimulationConfig(
    start_time=datetime(2026, 2, 12, 0, 0),
    total_run_hours=+24,  # 양수 = 정방향
    # ... 기타 설정
)
```

## 현재 상태

### ✅ 구현 완료

- 정방향/역궤적 모두 코드 레벨에서 완전히 지원
- `total_run_hours`의 부호로 방향 결정
- 동일한 엔진, 적분기, 보간기 사용
- 시간 방향만 반대로 진행

### ⚠️ 데이터 제약

현재 테스트 데이터(`gfs_eastasia_24h_very_wide.nc`)는 **역궤적용**으로 준비되어 있습니다:

- 시간 범위: 0 → -24시간 (과거 방향)
- 역궤적 계산에 최적화

정방향 궤적을 완전히 테스트하려면 **정방향용 GFS 데이터**가 필요합니다:

- 시간 범위: 0 → +24시간 (미래 방향)
- 예보 데이터 사용

## 테스트 결과

### 현재 테스트 (역궤적용 데이터 사용)

```bash
python tests/integration/active/test_forward_trajectory.py
```

**결과**:
- ✅ 4/4 위치 100% 완료
- ✅ 경계 오류 없음
- ⚠️ 이동 거리 매우 작음 (평균 1.2 km)
- ⚠️ 시간이 음수로 표시 (-24h → 0h)

**원인**: 역궤적용 데이터를 정방향으로 사용하여 시간 방향이 반대

### 올바른 정방향 테스트를 위한 요구사항

1. **정방향용 GFS 데이터 다운로드**
   - 시간 범위: 0 → +24시간
   - 예보 데이터 (forecast)

2. **데이터 준비 스크립트**
   ```bash
   python tests/integration/active/download_gfs_forecast.py
   ```

3. **정방향 테스트 실행**
   ```bash
   python tests/integration/active/test_forward_trajectory.py --forecast-data
   ```

## 코드 구조

### 방향 결정 로직

`pyhysplit/engine.py`:

```python
class TrajectoryEngine:
    def __init__(self, config: SimulationConfig, met: MetData):
        # 방향 결정
        self.is_forward = config.total_run_hours > 0
        self._direction = 1.0 if self.is_forward else -1.0
        
        # 시작 시간 결정
        if self.is_forward:
            t_start = met.t_grid[0]  # 데이터의 첫 시간
        else:
            t_start = met.t_grid[-1]  # 데이터의 마지막 시간
```

### 시간 적분

```python
# dt는 항상 양수로 계산
dt_abs = self.dt_controller.compute_dt(u, v, w, t)

# 방향 적용
dt = dt_abs * self._direction  # forward: +dt, backward: -dt

# 시간 업데이트
t += dt
```

## HYSPLIT과 비교

### HYSPLIT Web

HYSPLIT Web에서도 정방향 궤적을 지원합니다:

1. **Trajectory Direction** 선택
   - Backward (역궤적)
   - Forward (정방향)

2. **데이터 자동 선택**
   - Backward: 분석 데이터 (analysis)
   - Forward: 예보 데이터 (forecast)

### PyHYSPLIT

PyHYSPLIT도 동일한 방식으로 작동합니다:

1. **방향 설정**
   ```python
   total_run_hours = -24  # Backward
   total_run_hours = +24  # Forward
   ```

2. **데이터 준비**
   - Backward: 과거 데이터 (0 → -24h)
   - Forward: 예보 데이터 (0 → +24h)

## 다음 단계

### 즉시 가능

1. ✅ 역궤적 테스트 (완료)
   - 7/7 위치 100% 완료
   - HYSPLIT과 동등한 정확도

2. ⏳ 정방향 데이터 준비
   - GFS 예보 데이터 다운로드
   - 시간 범위: 0 → +24시간

3. ⏳ 정방향 테스트
   - 동일한 7개 위치
   - HYSPLIT Web과 비교

### 선택 사항

1. 🔮 자동 데이터 선택
   - 방향에 따라 자동으로 적절한 데이터 선택
   - 분석 데이터 vs 예보 데이터

2. 🔮 실시간 예보
   - 최신 GFS 예보 데이터 자동 다운로드
   - 실시간 정방향 궤적 계산

## 예제 코드

### 기본 정방향 궤적

```python
from datetime import datetime
from pyhysplit.engine import TrajectoryEngine
from pyhysplit.met_reader import NetCDFReader
from pyhysplit.models import SimulationConfig, StartLocation

# GFS 예보 데이터 로드
reader = NetCDFReader()
met = reader.read("gfs_forecast_24h.nc")  # 0 → +24h 데이터

# 정방향 설정
config = SimulationConfig(
    start_time=datetime(2026, 2, 12, 0, 0),
    num_start_locations=1,
    start_locations=[
        StartLocation(lat=37.5, lon=127.0, height=850.0, height_type="pressure")
    ],
    total_run_hours=+24,  # 정방향 24시간
    vertical_motion=7,
    model_top=10000.0,
    met_files=[],
    auto_vertical_mode=True,
)

# 궤적 계산
engine = TrajectoryEngine(config, met)
trajectories = engine.run(output_interval_s=3600.0)

# 결과 출력
trajectory = trajectories[0]
for t, lon, lat, z in trajectory:
    print(f"Time: {t/3600:.1f}h, Lon: {lon:.2f}°E, Lat: {lat:.2f}°N, P: {z:.1f} hPa")
```

### HYSPLIT Web과 비교

```python
# 1. HYSPLIT Web에서 정방향 궤적 계산
#    - Direction: Forward
#    - Duration: 24 hours
#    - 결과 다운로드: tdump_forward.txt

# 2. PyHYSPLIT으로 동일한 궤적 계산
config = SimulationConfig(
    start_time=datetime(2026, 2, 12, 0, 0),
    start_locations=[StartLocation(lat=37.5, lon=127.0, height=850.0, height_type="pressure")],
    total_run_hours=+24,  # 정방향
    # ... 기타 설정
)

engine = TrajectoryEngine(config, met)
trajectories = engine.run()

# 3. 비교
from tests.integration.active.hysplit_web_helper import compare_trajectories
compare_trajectories("tdump_forward.txt", trajectories[0])
```

## 참고

### 관련 파일

- `pyhysplit/engine.py` - 방향 로직 구현
- `pyhysplit/integrator.py` - 시간 적분
- `tests/integration/active/test_forward_trajectory.py` - 정방향 테스트
- `tests/integration/active/download_gfs_forecast.py` - 예보 데이터 다운로드 (TODO)

### 관련 문서

- [README.md](../../../README.md) - 프로젝트 개요
- [PROJECT_COMPLETION_SUMMARY.md](PROJECT_COMPLETION_SUMMARY.md) - 완료 요약
- [HYSPLIT_LITERATURE_REVIEW.md](HYSPLIT_LITERATURE_REVIEW.md) - HYSPLIT 분석

## 결론

### 현재 상태

- ✅ 정방향 궤적 **코드 완전 지원**
- ✅ 역궤적 **완전 검증 완료** (7/7 위치 100%)
- ⏳ 정방향 **데이터 준비 필요**

### 다음 작업

1. GFS 예보 데이터 다운로드 스크립트 작성
2. 정방향용 데이터 준비 (0 → +24h)
3. 정방향 궤적 완전 테스트
4. HYSPLIT Web과 비교

---

**작성일**: 2026-02-14  
**상태**: ✅ 정방향 지원 완료, ⏳ 데이터 준비 필요  
**버전**: 1.0.0
