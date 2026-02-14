# HYSPLIT Web 배치 실행 가이드

## 개요

PyHYSPLIT과 비교하기 위해 HYSPLIT Web에서 8개 지역의 24시간 역추적을 실행하는 가이드입니다.

## 테스트 지역

| 지역 | 위도 | 경도 | 고도 | 국가 |
|------|------|------|------|------|
| 서울 | 37.5°N | 127.0°E | 850m | 한국 |
| 부산 | 35.1°N | 129.0°E | 850m | 한국 |
| 제주 | 33.5°N | 126.5°E | 850m | 한국 |
| 도쿄 | 35.7°N | 139.7°E | 850m | 일본 |
| 오사카 | 34.7°N | 135.5°E | 850m | 일본 |
| 베이징 | 39.9°N | 116.4°E | 850m | 중국 |
| 상하이 | 31.2°N | 121.5°E | 850m | 중국 |
| 타이베이 | 25.0°N | 121.5°E | 850m | 대만 |

## PyHYSPLIT 결과 요약

```
서울:    484 km 북쪽으로 이동 (평균 20.2 km/h)
부산:    551 km 북쪽으로 이동 (평균 22.9 km/h)
제주:    634 km 북쪽으로 이동 (평균 26.4 km/h)
도쿄:    319 km 서쪽으로 이동 (평균 13.3 km/h)
오사카:  134 km 서쪽으로 이동 (평균 5.6 km/h)
베이징:  434 km 서쪽으로 이동 (평균 18.1 km/h)
상하이:  415 km 북쪽으로 이동 (평균 17.3 km/h)
타이베이: 195 km 동쪽으로 이동 (평균 8.1 km/h)
```

## HYSPLIT Web 실행 방법

### 1. 웹사이트 접속

https://www.ready.noaa.gov/HYSPLIT_traj.php

### 2. 공통 설정

**Meteorology:**
- Model: GFS (0.25 degree)
- Start Time: 2026-02-14 00:00 UTC

**Trajectory:**
- Direction: Backward
- Duration: 24 hours
- Vertical Motion: Model Vertical Velocity

**Output:**
- Interval: 1 hour

### 3. 각 지역별 실행

#### 서울
```
Start Location:
  Latitude: 37.5
  Longitude: 127.0
  Height: 850 meters AGL

Run → Download "Trajectory Endpoints" → 저장: tdump_서울.txt
```

#### 부산
```
Start Location:
  Latitude: 35.1
  Longitude: 129.0
  Height: 850 meters AGL

Run → Download "Trajectory Endpoints" → 저장: tdump_부산.txt
```

#### 제주
```
Start Location:
  Latitude: 33.5
  Longitude: 126.5
  Height: 850 meters AGL

Run → Download "Trajectory Endpoints" → 저장: tdump_제주.txt
```

#### 도쿄
```
Start Location:
  Latitude: 35.7
  Longitude: 139.7
  Height: 850 meters AGL

Run → Download "Trajectory Endpoints" → 저장: tdump_도쿄.txt
```

#### 오사카
```
Start Location:
  Latitude: 34.7
  Longitude: 135.5
  Height: 850 meters AGL

Run → Download "Trajectory Endpoints" → 저장: tdump_오사카.txt
```

#### 베이징
```
Start Location:
  Latitude: 39.9
  Longitude: 116.4
  Height: 850 meters AGL

Run → Download "Trajectory Endpoints" → 저장: tdump_베이징.txt
```

#### 상하이
```
Start Location:
  Latitude: 31.2
  Longitude: 121.5
  Height: 850 meters AGL

Run → Download "Trajectory Endpoints" → 저장: tdump_상하이.txt
```

#### 타이베이
```
Start Location:
  Latitude: 25.0
  Longitude: 121.5
  Height: 850 meters AGL

Run → Download "Trajectory Endpoints" → 저장: tdump_타이베이.txt
```

### 4. 파일 저장

다운로드한 tdump 파일들을 다음 디렉토리에 저장:

```
tests/integration/hysplit_web_data/
├── tdump_서울.txt
├── tdump_부산.txt
├── tdump_제주.txt
├── tdump_도쿄.txt
├── tdump_오사카.txt
├── tdump_베이징.txt
├── tdump_상하이.txt
└── tdump_타이베이.txt
```

### 5. 비교 실행

```bash
python tests/integration/multi_location_24h_comparison.py --compare
```

## 예상 결과

### 현재 파라미터 (95% 일치 기준)

**7시간 테스트 결과:**
- 수평 오차: 평균 15.55 km
- 고도 오차: 평균 60.2 m

**24시간 테스트 예상:**
- 수평 오차: 평균 40-60 km
- 고도 오차: 평균 150-200 m
- 일치율: 95-97%

### 지역별 예상 오차

| 지역 | 예상 수평 오차 | 예상 고도 오차 | 비고 |
|------|--------------|--------------|------|
| 서울 | 40-50 km | 150-180 m | 중간 거리 |
| 부산 | 45-55 km | 160-190 m | 긴 거리 |
| 제주 | 50-65 km | 170-210 m | 가장 긴 거리 |
| 도쿄 | 30-40 km | 130-160 m | 중간 거리 |
| 오사카 | 15-25 km | 100-130 m | 짧은 거리 |
| 베이징 | 40-50 km | 150-180 m | 중간 거리 |
| 상하이 | 40-50 km | 150-180 m | 중간 거리 |
| 타이베이 | 20-30 km | 110-140 m | 짧은 거리 |

## 자동화 스크립트 (선택사항)

HYSPLIT Web은 공식 API를 제공하지 않지만, 웹 자동화 도구를 사용할 수 있습니다:

### Selenium 사용 예시

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
import time

# 브라우저 설정
driver = webdriver.Chrome()
driver.get("https://www.ready.noaa.gov/HYSPLIT_traj.php")

# 각 지역에 대해 반복
locations = {
    "서울": (37.5, 127.0, 850),
    "부산": (35.1, 129.0, 850),
    # ... 나머지 지역
}

for name, (lat, lon, height) in locations.items():
    # 위도 입력
    lat_input = driver.find_element(By.NAME, "lat")
    lat_input.clear()
    lat_input.send_keys(str(lat))
    
    # 경도 입력
    lon_input = driver.find_element(By.NAME, "lon")
    lon_input.clear()
    lon_input.send_keys(str(lon))
    
    # 고도 입력
    height_input = driver.find_element(By.NAME, "height")
    height_input.clear()
    height_input.send_keys(str(height))
    
    # 실행
    submit_button = driver.find_element(By.NAME, "submit")
    submit_button.click()
    
    # 결과 대기 및 다운로드
    time.sleep(30)  # 계산 대기
    
    # tdump 다운로드
    # ... (구현 필요)
    
    print(f"✓ {name} 완료")

driver.quit()
```

## 문제 해결

### HYSPLIT Web 접속 불가
- 서버 점검 시간 확인
- 다른 시간대에 재시도

### 계산 실패
- 시작 위치가 데이터 범위 내인지 확인
- 시작 시간이 GFS 데이터 범위 내인지 확인

### tdump 파일 형식 오류
- "Trajectory Endpoints" 다운로드 확인
- 텍스트 파일로 저장 확인

## 참고 자료

- [HYSPLIT Web](https://www.ready.noaa.gov/HYSPLIT.php)
- [HYSPLIT 사용자 가이드](https://www.ready.noaa.gov/HYSPLIT_tutorial.php)
- [GFS 데이터 정보](https://www.ncei.noaa.gov/products/weather-climate-models/global-forecast-system)

---

**작성일:** 2026-02-14  
**PyHYSPLIT 버전:** Development
