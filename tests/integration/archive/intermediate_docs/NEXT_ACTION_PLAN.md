# 다음 액션 플랜

## 현재 상황
- Omega (Pa/s) → hPa/s 변환 완료 ✅
- 압력 좌표계에서 omega 직접 사용 확인 ✅
- **문제 발견**: StartLocation API가 meters AGL만 지원, 압력 직접 지정 불가 ❌

## 즉시 해결 방안

### 방법 1: 임시 우회 (빠름, 테스트용)
`multi_location_24h_comparison.py`에서 엔진 초기화 전에 직접 압력 설정:
```python
# 엔진 생성 후 내부 변환 결과 덮어쓰기
engine = TrajectoryEngine(config, met_data)
engine._converted_start_locations = [(lon, lat, 850.0)]  # 압력 직접 설정
```

**장점**: 코드 수정 최소
**단점**: Private API 사용, 임시 방편

### 방법 2: StartLocation API 확장 (정석)
`models.py`의 `StartLocation` 수정:
```python
@dataclass
class StartLocation:
    lat: float
    lon: float
    height: float
    height_type: str = "meters_agl"  # "meters_agl" 또는 "pressure"
```

`engine.py`의 변환 로직 수정:
```python
def _validate_and_convert_start_locations(self):
    for loc in self.config.start_locations:
        if loc.height_type == "pressure":
            if self.met.z_type != "pressure":
                raise ValueError("height_type='pressure' requires pressure coordinates")
            z_converted = loc.height  # 직접 사용
        else:
            # 기존 meters AGL → pressure 변환
            z_converted = self._convert_height_to_pressure(loc.height)
```

**장점**: 깔끔한 API, 재사용 가능
**단점**: 코드 수정 범위 큼

### 방법 3: 비교 스크립트만 수정 (중간)
HYSPLIT Web 결과를 meters로 변환하여 비교:
```python
# tdump 파일의 압력을 meters로 변환
hysplit_pressure = 874.3  # hPa
hysplit_height_m = pressure_to_height(hysplit_pressure * 100)
```

**장점**: 엔진 코드 수정 불필요
**단점**: 변환 오차 여전히 존재

## 권장 순서

### 1단계: 임시 우회로 검증 (30분)
- `multi_location_24h_comparison.py`에서 방법 1 적용
- 압력 직접 지정 시 정확도 확인
- 예상 결과: 고도 오차 < 100m

### 2단계: API 확장 (2시간)
- `StartLocation`에 `height_type` 추가
- `TrajectoryEngine` 변환 로직 수정
- 단위 테스트 추가

### 3단계: 전체 검증 (1시간)
- 8개 지역 재비교
- 99% 일치율 목표 달성 확인
- 문서화

## 예상 결과

### 현재 (이중 변환)
```
수평 오차: 59.27 km
고도 오차: 843.4 m
일치율: 27.8% / 0%
```

### 목표 (압력 직접 지정)
```
수평 오차: < 20 km
고도 오차: < 100 m
일치율: > 80% / > 80%
```

## 실행 명령

### 1단계 테스트
```bash
# 임시 우회 적용 후
python tests/integration/multi_location_24h_comparison.py --compare
```

### 2단계 테스트
```bash
# API 수정 후
python tests/integration/multi_location_24h_comparison.py --compare
pytest tests/unit/test_engine.py -v
```

## 다음 회의 안건
1. StartLocation API 확장 승인
2. 기존 코드 호환성 유지 방안
3. 문서 업데이트 범위
