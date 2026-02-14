# Omega 변환 조사 결과

## 문제 정의
PyHYSPLIT과 HYSPLIT Web의 궤적 비교에서 큰 오차 발생:
- 수평 오차: 평균 59 km
- 고도 오차: 평균 843 m
- 일치율: 수평 27.8%, 고도 0%

## 조사 내용

### 1. GFS 데이터 확인
- **변수명**: `w`
- **단위**: `Pa/s` (omega, 압력 수직 속도)
- **값 범위**: -15.34 ~ +9.43 Pa/s
- **변환 후**: -1.2 ~ +2.0 m/s (기하학적 수직 속도)

### 2. HYSPLIT 좌표계
HYSPLIT Web 출력 (tdump 파일):
```
BACKWARD OMEGA
PRESSURE
```
- **수직 좌표**: 압력 (hPa)
- **수직 속도**: omega (hPa/s 또는 Pa/s)

### 3. 변환 시도 결과

#### 시도 1: Omega → W 변환 (Mode 0)
```python
w = -omega * (R * T) / (P * g)  # Pa/s → m/s
vertical_motion = 0  # Data vertical velocity
```
**결과**: 
- 수평 오차: 46.46 km (악화)
- 고도 오차: 498.7 m (악화)
- **문제**: 압력 좌표계에서는 omega를 m/s로 변환하면 안 됨!

#### 시도 2: Omega 직접 사용 (Pa/s → hPa/s)
```python
w_data = omega_data / 100.0  # Pa/s → hPa/s
```
**결과**:
- 수평 오차: 42.72 km
- 고도 오차: 358.4 m
- **개선**: 고도 오차가 크게 개선됨

#### 시도 3: 시작 고도 수정
**발견**: `StartLocation.height`는 **meters AGL**로 전달해야 함!
- 850 hPa → ~1400m AGL로 변환
- 엔진이 다시 1400m → 압력으로 변환

**결과**:
- 수평 오차: 59.27 km (악화)
- 고도 오차: 843.4 m (크게 악화)
- **문제**: 이중 변환으로 인한 오차 누적

## 근본 원인

### 좌표계 불일치
1. **HYSPLIT Web**:
   - 시작점: 850 hPa (압력 직접 지정)
   - 수직 좌표: 압력 (hPa)
   - 수직 속도: omega (hPa/s)

2. **PyHYSPLIT**:
   - 시작점: meters AGL (API 요구사항)
   - 내부 변환: meters → pressure (hPa)
   - 수직 속도: omega (hPa/s)

### 변환 오차
```
HYSPLIT Web: 850 hPa (직접)
              ↓
PyHYSPLIT:   850 hPa → 1400m AGL (표준 대기)
              ↓
             1400m → 916 hPa (scale_height 기반)
              ↓
             실제 궤적 계산
```

**문제**: 
- 표준 대기 가정 vs 실제 기온 프로파일
- Scale height 파라미터 (8430m) 불확실성
- 이중 변환으로 인한 오차 누적

## 해결 방안

### 옵션 1: API 수정 (권장)
`StartLocation`에 좌표계 옵션 추가:
```python
StartLocation(
    lat=37.5, 
    lon=127.0, 
    height=850.0,
    height_type="pressure"  # 또는 "meters_agl"
)
```

### 옵션 2: 역변환 최적화
현재 변환 공식 개선:
- 실제 기온 프로파일 사용
- Scale height 자동 조정
- Hypsometric equation 정확도 향상

### 옵션 3: 비교 방법 변경
- HYSPLIT Web 결과를 meters AGL로 변환
- 동일한 좌표계에서 비교
- 하지만 여전히 변환 오차 존재

## 다음 단계

1. **즉시 조치**: 
   - `StartLocation` API에 `height_type` 파라미터 추가
   - 압력 좌표 직접 지정 지원

2. **중기 개선**:
   - 실제 기온 프로파일 기반 변환
   - Hypsometric equation 정확도 검증

3. **장기 목표**:
   - HYSPLIT과 1:1 검증
   - 99% 일치율 달성

## 참고 문헌
- NOAA HYSPLIT Meteorological Data: https://www.ready.noaa.gov/hypub/hysp_meteoinfo.html
- GFS 0.25도 모델: sigma-pressure hybrid 좌표계
- Omega equation: ω = dp/dt (Pa/s)
