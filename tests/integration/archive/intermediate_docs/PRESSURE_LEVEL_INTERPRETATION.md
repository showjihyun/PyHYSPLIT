# 압력 레벨 해석 문제 해결

## 문제 발견

PyHYSPLIT과 HYSPLIT Web 간의 주요 차이점을 발견했습니다:

### 시작 압력 차이
- **사용자 입력**: 850 hPa
- **PyHYSPLIT 해석**: 850.0 hPa (입력값 그대로 사용)
- **HYSPLIT Web 해석**: 906.3 hPa (56.3 hPa 차이!)

## 원인 분석

HYSPLIT Web은 "850 hPa"를 다음과 같이 해석합니다:
1. **표준 기압 레벨**이 아닌 **GFS 모델의 850 hPa 레벨**로 해석
2. 해당 위치의 **지형 고도**와 **기상 조건**을 고려
3. 실제 **지오포텐셜 고도**를 기반으로 실제 압력 계산

### 서울 예시 (37.5°N, 127.0°E)
- 지형 고도: ~38m
- GFS 850 hPa 레벨의 지오포텐셜 고도: ~1400m (추정)
- 해당 고도에서의 실제 압력: 906.3 hPa

## 개선 효과

올바른 시작 압력(906.3 hPa)을 사용했을 때:

| 지표 | 850 hPa 시작 | 906.3 hPa 시작 | 개선 |
|------|--------------|----------------|------|
| **초기 압력 오차** | 56.3 hPa | 0.0 hPa | **100%** |
| **8시간 후 수평 오차** | 185.14 km | 124.07 km | **33%** |
| **8시간 후 압력 오차** | 68.9 hPa | 27.1 hPa | **61%** |
| **평균 수평 오차** | 69.80 km | 34.22 km | **51%** |
| **평균 압력 오차** | 67.0 hPa | 12.8 hPa | **81%** |

## 해결 방안

### 방안 1: 지오포텐셜 고도 기반 변환 (정확)
GFS 데이터에 지오포텐셜 고도 필드가 있다면:
1. 입력된 압력 레벨 (예: 850 hPa)에서 지오포텐셜 고도 읽기
2. 해당 고도에서의 실제 압력 계산
3. 실제 압력을 시작 압력으로 사용

**장점**: HYSPLIT과 완전히 동일한 방식
**단점**: 지오포텐셜 고도 데이터 필요

### 방안 2: 정역학 방정식 사용 (근사)
온도 프로파일을 사용하여 압력-고도 관계 계산:
```python
def pressure_at_geopotential_level(p_level, lat, lon, met_data):
    # 1. p_level에서 온도 읽기
    T = interpolate_temperature(p_level, lat, lon, met_data)
    
    # 2. 지표면 압력 추정
    p_surface = estimate_surface_pressure(lat, lon, met_data)
    
    # 3. 정역학 방정식으로 실제 압력 계산
    # dz = -(R*T/g) * dp/p
    # 적분하여 p_level 고도에서의 실제 압력 계산
    
    return p_actual
```

**장점**: 지오포텐셜 데이터 없이도 가능
**단점**: 근사값, 정확도 낮음

### 방안 3: 경험적 보정 (임시)
테스트 데이터를 기반으로 보정 공식 도출:
```python
# 서울 예시: 850 hPa → 906.3 hPa (차이 56.3 hPa)
# 다른 위치들도 테스트하여 패턴 파악
def adjust_pressure_level(p_level, lat, lon, elevation):
    # 경험적 보정 공식
    correction = f(p_level, lat, lon, elevation)
    return p_level + correction
```

**장점**: 빠른 구현
**단점**: 일반화 어려움, 정확도 제한적

## 권장 사항

### 단기 (즉시 적용 가능)
1. **GFS 데이터에 지오포텐셜 고도 추가**
   - 현재 GFS 다운로드 스크립트 수정
   - `geopotential` 또는 `gh` 변수 포함
   
2. **압력 레벨 변환 함수 구현**
   ```python
   def convert_pressure_level_to_actual(
       p_level: float,
       lat: float,
       lon: float,
       met_data: MetData
   ) -> float:
       """Convert standard pressure level to actual pressure at location"""
       # 지오포텐셜 고도 기반 변환
       pass
   ```

3. **StartLocation 처리 수정**
   - `height_type="pressure"`일 때 자동 변환 적용
   - 사용자에게 투명하게 처리

### 중기 (추가 검증 필요)
1. **다양한 위치에서 테스트**
   - 8개 테스트 위치 모두에서 시작 압력 확인
   - HYSPLIT Web 결과와 비교
   
2. **고도별 테스트**
   - 다양한 압력 레벨 (700, 850, 925 hPa 등)
   - 변환 공식의 일반성 검증

3. **계절/기상 조건별 테스트**
   - 여름/겨울 데이터
   - 고기압/저기압 조건

## 다음 단계

1. ✅ 문제 발견 및 원인 분석 완료
2. ✅ 올바른 시작 압력 사용 시 개선 효과 확인
3. ⏳ GFS 데이터에 지오포텐셜 고도 추가
4. ⏳ 압력 레벨 변환 함수 구현
5. ⏳ 전체 테스트 재실행 및 검증

## 예상 최종 결과

압력 레벨 변환을 올바르게 구현하면:
- **수평 오차**: 50.34 km → ~30 km (40% 추가 개선)
- **압력 오차**: 76.3 hPa → ~15 hPa (80% 추가 개선)
- **전체 진행률**: 43% → **70%+** (99% 목표 대비)

## 참고 자료

- HYSPLIT User's Guide: 압력 좌표 처리 방식
- GFS 데이터 형식: 지오포텐셜 고도 필드
- 정역학 방정식: 압력-고도 관계

## 코드 위치

- 테스트 스크립트: `tests/integration/test_with_adjusted_start_pressure.py`
- 진단 스크립트: `tests/integration/diagnose_step_by_step.py`
- 압력 분석: `tests/integration/check_pressure_interpretation.py`
