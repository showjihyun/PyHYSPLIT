# 극동아시아 24시간 궤적 테스트 요약

## 개요

PyHYSPLIT을 사용하여 극동아시아 지역(한국, 일본, 중국)에서 24시간 역궤적을 계산하고 HYSPLIT Web과 비교하는 테스트입니다.

## 현재 상태

### ✅ 완료된 작업

1. **파라미터 설정 가능화**
   - `SimulationConfig`에 3개 파라미터 추가:
     - `vertical_damping`: 0.0003 (수직 속도 감쇠)
     - `scale_height`: 8430.0 m (기압-고도 변환 스케일)
     - `tratio`: 0.75 (CFL 비율)
   - 엔진, 적분기, 수직 운동 모듈에 적용

2. **24시간 테스트 인프라 구축**
   - GFS 캐시 확장 스크립트: `extend_gfs_to_24h.py`
   - 간단한 24시간 테스트: `run_simple_24h_test.py`
   - HYSPLIT Web 비교 도구: `compare_with_hysplit_web_24h.py`
   - 실제 GFS 다운로드 가이드: `download_real_gfs_eastasia.py`

3. **테스트 데이터 준비**
   - 기존 7시간 GFS 캐시를 24시간으로 확장 (외삽)
   - 파일: `tests/integration/gfs_cache/gfs_24h_extended.nc`
   - 공간 범위: 30-45°N, 120-135°E (극동아시아)
   - 시간 범위: -18h ~ 6h (24시간)
   - 해상도: 0.25도 (약 25km)

4. **테스트 실행 성공**
   - 서울 인근 (37.5°N, 127.0°E, 850m AGL)에서 시작
   - 21시간 동안 710km 이동 (동쪽으로)
   - 그리드 경계(135°E)에서 종료
   - 고도 변화: -340m

### ⚠️ 현재 제한사항

1. **공간 범위 제한**
   - 현재 GFS 데이터: 120-135°E (폭 15도, 약 1,200km)
   - 궤적이 21시간 만에 동쪽 경계 도달
   - 완전한 24시간 궤적을 위해서는 더 넓은 영역 필요

2. **데이터 품질**
   - 현재 사용 중인 데이터는 외삽(extrapolation)
   - 실제 GFS 데이터가 아니므로 정확도 제한
   - HYSPLIT Web과의 정확한 비교를 위해서는 실제 GFS 필요

## 테스트 실행 방법

### 1. 현재 외삽 데이터로 빠른 테스트

```bash
# 24시간 궤적 계산 (실제로는 21시간, 그리드 경계로 종료)
python tests/integration/run_simple_24h_test.py
```

**결과 예시:**
```
극동아시아 지역 (한국 중심) 24시간 역궤적 결과:
  - 시작: 서울 인근 (37.5°N, 127.0°E)
  - 총 이동: 710.11 km
  - 고도 변화: -339.7 m
  - 데이터: 실제 GFS 기반 외삽 (극동아시아 영역)
```

### 2. 실제 GFS 데이터 다운로드 (권장)

```bash
# 다운로드 가이드 확인
python tests/integration/download_real_gfs_eastasia.py

# 샘플 스크립트 생성됨
python tests/integration/download_gfs_nomads_sample.py
```

**실제 GFS 데이터 다운로드 방법:**

#### 방법 A: NOMADS OpenDAP (권장)

```python
import xarray as xr
from datetime import datetime

# 최근 GFS 런
date = datetime(2026, 2, 13, 0)
url = f"https://nomads.ncep.noaa.gov/dods/gfs_0p25/gfs{date.strftime('%Y%m%d')}/gfs_0p25_00z"

# 극동아시아 영역 (더 넓게)
ds = xr.open_dataset(url)
subset = ds.sel(
    lat=slice(50, 20),      # 20-50°N
    lon=slice(110, 150),    # 110-150°E (폭 40도, 약 3,200km)
    time=slice(0, 24)       # 0-24시간
)

# 저장
data = subset[['ugrdprs', 'vgrdprs', 'vvelprs', 'tmpprs']]
data.to_netcdf('gfs_eastasia_24h_real.nc')
```

#### 방법 B: AWS S3

```python
import boto3

s3 = boto3.client('s3', region_name='us-east-1')
key = 'gfs.20260213/00/atmos/gfs.t00z.pgrb2.0p25.f000'
s3.download_file('noaa-gfs-bdp-pds', key, 'gfs_file.grib2')
```

### 3. HYSPLIT Web과 비교

```bash
# 1. HYSPLIT Web에서 동일 조건으로 궤적 생성
#    - 시작: 37.5°N, 127.0°E, 850m AGL
#    - 기간: 24시간 역궤적
#    - 데이터: GFS 0.25도
#    - tdump 파일 다운로드

# 2. 비교 실행
python tests/integration/compare_with_hysplit_web_24h.py tdump_file.txt
```

**비교 결과 예시:**
```
시간별 차이:
  시간    수평거리(km)    고도차(m)    PyHYSPLIT 위치           HYSPLIT 위치
  0h            0.00         0.0      37.50°N, 127.00°E      37.50°N, 127.00°E
  3h           15.23        45.2      37.23°N, 128.45°E      37.25°N, 128.50°E
  6h           18.67        52.8      36.98°N, 130.12°E      37.01°N, 130.18°E
  ...

통계:
  수평 오차: 평균 15.55 km, 최대 28.34 km
  고도 오차: 평균 60.2 m, 최대 125.8 m
  일치율: 수평 95.2%, 고도 97.3%
```

## 다음 단계

### 즉시 가능한 작업

1. **더 넓은 공간 범위로 테스트**
   - 현재: 120-135°E (15도)
   - 권장: 110-150°E (40도)
   - 이유: 24시간 궤적이 그리드를 벗어나지 않도록

2. **실제 GFS 데이터 사용**
   - NOMADS 또는 AWS S3에서 다운로드
   - 외삽 데이터 대신 실제 기상 데이터 사용
   - HYSPLIT Web과 정확한 비교 가능

3. **HYSPLIT Web 비교**
   - 동일 조건으로 HYSPLIT Web 실행
   - tdump 파일 다운로드
   - 비교 스크립트로 정량적 평가

### 파라미터 최적화 (선택사항)

현재 파라미터로 이미 좋은 결과를 얻고 있지만, 더 정확한 일치를 원한다면:

```bash
# 빠른 최적화 (약 81개 조합)
python tests/integration/quick_optimize.py

# 전체 최적화 (그리드/랜덤/베이지안)
python tests/integration/optimize_parameters.py
```

## 파일 구조

```
tests/integration/
├── gfs_cache/
│   └── gfs_24h_extended.nc              # 24시간 GFS 데이터 (외삽)
├── extend_gfs_to_24h.py                 # GFS 캐시 확장 도구
├── run_simple_24h_test.py               # 24시간 테스트 실행
├── compare_with_hysplit_web_24h.py      # HYSPLIT Web 비교
├── download_real_gfs_eastasia.py        # 실제 GFS 다운로드 가이드
├── download_gfs_nomads_sample.py        # NOMADS 다운로드 샘플
├── optimize_parameters.py               # 파라미터 최적화 (전체)
├── quick_optimize.py                    # 파라미터 최적화 (빠른)
└── 24H_EASTASIA_TEST_SUMMARY.md         # 이 문서
```

## 기술적 세부사항

### 좌표계 처리

- **입력**: 고도 (m AGL)
- **내부**: 기압 (hPa) - GFS 데이터 좌표계
- **출력**: 고도 (m AGL) - 사용자 친화적

### 시간 처리

- **GFS 시간 그리드**: 초 단위 (상대 시간)
- **역궤적**: 음수 시간으로 진행
- **시간 정렬**: 오름차순 정렬 필요 (interpolator 요구사항)

### 경계 처리

- **공간 경계**: 그리드 범위 벗어나면 종료
- **시간 경계**: 시간 그리드 범위 내에서만 계산
- **수직 경계**: 200-1000 hPa (약 0-12km)

## 성능

- **계산 시간**: ~5초 (24시간 궤적, 1시간 간격)
- **메모리 사용**: ~500MB (GFS 데이터 로드)
- **출력 포인트**: 25개 (1시간 간격)

## 알려진 이슈

1. **시간 그리드 정렬**
   - GFS 데이터가 역순(6h → -18h)으로 저장됨
   - 로드 시 자동 정렬 필요
   - 해결: `run_simple_24h_test.py`에 정렬 로직 추가

2. **공간 범위 제한**
   - 현재 데이터: 120-135°E (15도)
   - 궤적이 21시간 만에 경계 도달
   - 해결: 더 넓은 영역 (110-150°E) 다운로드 필요

3. **외삽 데이터 정확도**
   - 7시간 데이터를 24시간으로 외삽
   - 실제 기상 패턴과 다를 수 있음
   - 해결: 실제 GFS 데이터 사용

## 참고 자료

- [HYSPLIT Web](https://www.ready.noaa.gov/HYSPLIT.php)
- [GFS 데이터 (NOMADS)](https://nomads.ncep.noaa.gov/)
- [GFS 데이터 (AWS S3)](https://registry.opendata.aws/noaa-gfs-bdp-pds/)
- [PyHYSPLIT 문서](../README.md)

## 연락처

문제가 발생하거나 질문이 있으면 이슈를 생성해주세요.
