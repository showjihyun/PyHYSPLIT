# 24시간 역궤적 비교 테스트 가이드

## 개요

7시간 대신 24시간 역궤적으로 비교하여 더 긴 시간 동안의 정확도를 검증합니다.

## 왜 24시간인가?

### 7시간 vs 24시간 비교

**7시간 테스트:**
- ✓ 빠른 검증
- ✓ 초기 정확도 확인
- ✗ 누적 오차 파악 어려움
- ✗ 장기 안정성 검증 부족

**24시간 테스트:**
- ✓ 누적 오차 명확히 파악
- ✓ 장기 안정성 검증
- ✓ 시간대별 오차 패턴 분석
- ✓ 실제 사용 시나리오에 가까움
- ✗ 계산 시간 증가 (3-4배)

### 예상 결과

**현재 파라미터 (damping=0.0003, scale_height=8430, tratio=0.75):**
- 7시간: 평균 15.55 km, 고도 60.2 m
- 24시간 예상: 평균 40-60 km, 고도 150-200 m

**최적화 후 예상:**
- 7시간: 평균 11-14 km, 고도 40-55 m
- 24시간: 평균 30-45 km, 고도 100-150 m

**목표 (99% 일치):**
- 7시간: 평균 <2 km, 고도 <10 m
- 24시간: 평균 <6 km, 고도 <30 m

## 실행 방법

### 1단계: HYSPLIT Web에서 24시간 궤적 생성

#### 방법 A: 수동 실행

1. HYSPLIT Web 접속: https://www.ready.noaa.gov/HYSPLIT_traj.php

2. 설정:
   - **Start Location:** 37.0°N, 127.0°E
   - **Height:** 850 m AGL
   - **Start Time:** 2024-01-15 12:00 UTC
   - **Duration:** -24 hours (backward)
   - **Meteorology:** GFS 0.25 Degree
   - **Vertical Motion:** Model Vertical Velocity

3. 실행 후 "Trajectory Endpoints" 다운로드

4. 파일을 `tests/integration/hysplit_trajectory_endpoints_24h.txt`로 저장

#### 방법 B: 자동화 스크립트 (추천)

```bash
# Selenium 설치 (처음 한 번만)
pip install selenium webdriver-manager

# 24시간 궤적 자동 생성
python tests/integration/hysplit_web_24h_automation.py
```

### 2단계: GFS 데이터 준비

24시간 역궤적을 위해서는 25시간 분량의 GFS 데이터가 필요합니다 (시작 시간 + 24시간 전).

```bash
# GFS 데이터 다운로드 및 캐시 생성
python tests/integration/download_gfs_24h.py --date 2024-01-15 --hour 12 --lat 37.0 --lon 127.0
```

또는 기존 GFS 파일이 있다면:

```bash
# 기존 GFS 파일을 24시간 캐시로 변환
python tests/integration/prepare_gfs_24h_cache.py --input gfs_files/ --output gfs_cache/
```

### 3단계: 비교 테스트 실행

```bash
# 24시간 비교 테스트 실행
python tests/integration/test_24hour_comparison.py
```

### 4단계: 결과 확인

테스트 완료 후 생성되는 파일:

1. **`HYSPLIT_WEB_24H_COMPARISON.md`** - 상세 비교 리포트
   - 통계 요약
   - 시간대별 분석
   - 포인트별 상세 비교

2. **`comparison_24h_visualization.png`** - 시각화
   - 궤적 지도
   - 시간별 수평 거리 오차
   - 시간별 고도 오차
   - 고도 프로파일 비교

## 결과 해석

### 시간대별 오차 패턴

**정상적인 패턴:**
```
초기 (0-6h):   수평 10-15 km, 고도 40-60 m
중기 (6-12h):  수평 20-30 km, 고도 80-120 m
후기 (12-18h): 수평 35-50 km, 고도 120-180 m
말기 (18-24h): 수평 50-70 km, 고도 160-220 m
```

**문제가 있는 패턴:**
```
초기부터 큰 오차: 초기 설정 문제 (scale_height, 초기 고도 변환)
급격한 증가: 수치 불안정성 또는 경계 처리 문제
진동 패턴: 시간 보간 또는 dt 설정 문제
```

### 평가 기준

**24시간 평균 수평 거리:**
- < 20 km: 매우 우수 (99%+ 일치)
- < 50 km: 우수 (97-99% 일치)
- < 100 km: 양호 (95-97% 일치)
- < 200 km: 허용 가능 (90-95% 일치)
- ≥ 200 km: 개선 필요 (< 90% 일치)

**24시간 평균 고도 차이:**
- < 30 m: 매우 우수
- < 100 m: 우수
- < 200 m: 양호
- < 400 m: 허용 가능
- ≥ 400 m: 개선 필요

## 파라미터 최적화

24시간 테스트 결과를 바탕으로 파라미터 최적화:

### 1. 현재 파라미터로 24시간 테스트

```bash
python tests/integration/test_24hour_comparison.py
```

### 2. 결과 분석

```bash
cat tests/integration/HYSPLIT_WEB_24H_COMPARISON.md
```

시간대별 오차 패턴 확인:
- 초기 오차가 크면: scale_height 조정
- 중기부터 증가하면: vertical_damping 조정
- 전체적으로 drift: tratio 조정

### 3. 24시간 기준 최적화 실행

```bash
# 24시간 테스트 기반 최적화
python tests/integration/optimize_parameters_24h.py --method quick

# 또는 전체 Grid Search
python tests/integration/optimize_parameters_24h.py --method grid
```

### 4. 최적 파라미터 적용

최적화 결과에서 찾은 파라미터를 적용:

```python
# pyhysplit/models.py
@dataclass
class SimulationConfig:
    # ... 기존 필드 ...
    dt_max: float = 15.0  # 최적화 결과로 업데이트
    vertical_damping: float = 0.0003  # 최적화 결과로 업데이트
    scale_height: float = 8430.0  # 최적화 결과로 업데이트
    tratio: float = 0.75  # 최적화 결과로 업데이트
```

### 5. 재검증

```bash
# 새 파라미터로 24시간 테스트
python tests/integration/test_24hour_comparison.py

# 7시간 테스트도 재실행하여 확인
python -m pytest tests/integration/test_hysplit_web_comparison.py -v -s
```

## 다중 시나리오 테스트

단일 24시간 테스트 외에 다양한 조건에서 테스트:

```bash
# 여러 시작 위치, 시간, 고도에서 24시간 테스트
python tests/integration/test_multi_24h_scenarios.py
```

**테스트 시나리오:**
1. 다른 위치 (서울, 부산, 제주)
2. 다른 계절 (봄, 여름, 가을, 겨울)
3. 다른 고도 (500m, 850m, 1500m, 3000m)
4. 다른 기상 조건 (맑음, 비, 강풍)

## 문제 해결

### GFS 데이터 부족

**증상:** "GFS 캐시 파일이 없습니다" 오류

**해결:**
```bash
# GFS 데이터 다운로드
python tests/integration/download_gfs_24h.py --date 2024-01-15 --hour 12
```

### 메모리 부족

**증상:** "MemoryError" 또는 느린 실행

**해결:**
```python
# config에서 dt_max 증가 (더 큰 시간 간격)
config = SimulationConfig(
    # ...
    dt_max=30.0,  # 15.0에서 30.0으로 증가
)
```

### 궤적이 조기 종료

**증상:** 24시간 전에 궤적이 끝남

**해결:**
1. GFS 데이터 범위 확인
2. model_top 증가
3. 경계 처리 설정 확인

```python
config = SimulationConfig(
    # ...
    model_top=15000.0,  # 10000에서 15000으로 증가
)
```

## 예상 결과 예시

### 현재 파라미터 (95% 일치)

```
24시간 평균:
  수평 거리: 52.3 km
  고도 차이: 178.5 m

시간대별:
  초기 (0-6h):   수평 12.5 km, 고도 55.2 m
  중기 (6-12h):  수평 28.7 km, 고도 105.8 m
  후기 (12-18h):수평 45.2 km, 고도 165.3 m
  말기 (18-24h): 수평 62.8 km, 고도 225.7 m

평가: 양호 (95% 일치)
```

### 최적화 후 예상 (97-98% 일치)

```
24시간 평균:
  수평 거리: 35.8 km
  고도 차이: 125.3 m

시간대별:
  초기 (0-6h):   수평 8.5 km, 고도 38.2 m
  중기 (6-12h):  수평 19.7 km, 고도 72.8 m
  후기 (12-18h): 수평 32.5 km, 고도 115.3 m
  말기 (18-24h): 수평 45.2 km, 고도 158.7 m

평가: 우수 (97-98% 일치)
```

### 목표 (99%+ 일치)

```
24시간 평균:
  수평 거리: 5.2 km
  고도 차이: 25.3 m

시간대별:
  초기 (0-6h):   수평 1.5 km, 고도 8.2 m
  중기 (6-12h):  수평 3.2 km, 고도 15.8 m
  후기 (12-18h): 수평 5.8 km, 고도 25.3 m
  말기 (18-24h): 수평 8.5 km, 고도 35.7 m

평가: 매우 우수 (99%+ 일치)
```

## 다음 단계

24시간 테스트 완료 후:

1. **결과 분석**
   - 시간대별 오차 패턴 확인
   - 문제 영역 식별

2. **파라미터 최적화**
   - 24시간 기준으로 최적화
   - 7시간과 24시간 모두 고려

3. **알고리즘 개선**
   - Tricubic 보간
   - Cubic spline 시간 보간
   - Kahan summation

4. **HYSPLIT 소스 분석**
   - Fortran 코드 분석
   - 정확한 알고리즘 구현

5. **다중 시나리오 검증**
   - 다양한 조건에서 테스트
   - 일반화 성능 확인

## 요약

24시간 역궤적 비교는 PyHYSPLIT의 장기 정확도를 검증하는 중요한 테스트입니다.

**실행 순서:**
1. HYSPLIT Web에서 24시간 궤적 생성
2. GFS 데이터 준비 (25시간 분량)
3. `test_24hour_comparison.py` 실행
4. 결과 분석 및 파라미터 최적화
5. 재검증

**예상 소요 시간:**
- HYSPLIT Web 실행: 5-10분
- GFS 데이터 준비: 10-30분
- PyHYSPLIT 실행: 5-10분
- 총: 약 20-50분

**목표:**
- 현재: 24시간 평균 50-60 km (95% 일치)
- 최적화 후: 24시간 평균 30-40 km (97-98% 일치)
- 최종 목표: 24시간 평균 <6 km (99%+ 일치)
