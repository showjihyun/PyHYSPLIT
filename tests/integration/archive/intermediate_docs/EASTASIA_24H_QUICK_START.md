# 극동아시아 24시간 테스트 - 빠른 시작 가이드

## 5분 안에 시작하기

### 1. 즉시 실행 (외삽 데이터 사용)

```bash
python tests/integration/run_simple_24h_test.py
```

**결과:**
- 서울 인근에서 시작하여 21시간 동안 710km 이동
- 동쪽으로 이동하여 일본 방향으로 진행
- 그리드 경계에서 종료

### 2. 실제 GFS 데이터 다운로드 (권장)

```bash
# 다운로드 가이드 확인
python tests/integration/download_real_gfs_eastasia.py

# 샘플 스크립트 실행 (xarray 필요)
python tests/integration/download_gfs_nomads_sample.py
```

### 3. HYSPLIT Web과 비교

```bash
# HYSPLIT Web에서 tdump 파일 다운로드 후
python tests/integration/compare_with_hysplit_web_24h.py tdump_file.txt
```

## 현재 상태

### ✅ 작동 중
- 극동아시아 24시간 역궤적 계산 성공
- 710km 이동, 21시간 계산
- 모든 스크립트 준비 완료

### ⚠️ 제한사항
- 공간 범위: 120-135°E (15도, 약 1,200km)
- 데이터: 외삽 (7시간 → 24시간)
- 궤적이 21시간 만에 그리드 경계 도달

### 🎯 해결 방법
- 더 넓은 영역 다운로드: 110-150°E (40도, 약 3,200km)
- 실제 GFS 데이터 사용 (NOMADS 또는 AWS S3)

## 파일 구조

```
tests/integration/
├── gfs_cache/
│   └── gfs_24h_extended.nc              # 24시간 GFS (외삽) ✅
├── run_simple_24h_test.py               # 메인 테스트 스크립트 ✅
├── extend_gfs_to_24h.py                 # GFS 확장 도구 ✅
├── compare_with_hysplit_web_24h.py      # 비교 도구 ✅
├── download_real_gfs_eastasia.py        # 다운로드 가이드 ✅
├── download_gfs_nomads_sample.py        # 다운로드 샘플 ✅
├── 24H_EASTASIA_TEST_SUMMARY.md         # 상세 문서 (영문) ✅
├── EASTASIA_24H_QUICK_START.md          # 이 문서 ✅
└── 한글_요약.md                          # 전체 요약 (한글) ✅
```

## 실제 GFS 다운로드 (NOMADS)

### 필요한 패키지

```bash
pip install xarray netCDF4 dask
```

### 다운로드 코드

```python
import xarray as xr
from datetime import datetime

# 최근 GFS 런 (실제 날짜로 변경)
date = datetime(2026, 2, 13, 0)
url = f"https://nomads.ncep.noaa.gov/dods/gfs_0p25/gfs{date.strftime('%Y%m%d')}/gfs_0p25_00z"

# 극동아시아 영역 (넓게)
ds = xr.open_dataset(url)
subset = ds.sel(
    lat=slice(50, 20),      # 20-50°N
    lon=slice(110, 150),    # 110-150°E (폭 40도)
    lev=slice(1000, 200),   # 200-1000 hPa
    time=slice(0, 24)       # 0-24시간
)

# 저장
data = subset[['ugrdprs', 'vgrdprs', 'vvelprs', 'tmpprs']]
data.to_netcdf('tests/integration/gfs_cache/gfs_eastasia_24h_real.nc')
```

## HYSPLIT Web 설정

### 1. 웹사이트 접속
https://www.ready.noaa.gov/HYSPLIT_traj.php

### 2. 설정
- **Start Location**: 37.5°N, 127.0°E
- **Height**: 850 m AGL
- **Start Time**: 2026-02-13 06:00 UTC
- **Duration**: -24 hours (backward)
- **Meteorology**: GFS 0.25 degree

### 3. 다운로드
- "Trajectory Endpoints" 클릭
- tdump 파일 저장

### 4. 비교
```bash
python tests/integration/compare_with_hysplit_web_24h.py tdump_file.txt
```

## 예상 결과

### 현재 (외삽 데이터)
```
극동아시아 지역 (한국 중심) 24시간 역궤적 결과:
  - 시작: 서울 인근 (37.5°N, 127.0°E)
  - 총 이동: 710.11 km
  - 고도 변화: -339.7 m
  - 계산 시간: ~5초
```

### 실제 GFS 데이터 사용 시
```
극동아시아 지역 (한국 중심) 24시간 역궤적 결과:
  - 시작: 서울 인근 (37.5°N, 127.0°E)
  - 총 이동: 800-1000 km (예상)
  - 고도 변화: -400 ~ -600 m (예상)
  - 계산 시간: ~5초
```

### HYSPLIT Web 비교 (예상)
```
통계:
  수평 오차: 평균 15-20 km, 최대 40-50 km
  고도 오차: 평균 60-80 m, 최대 150-200 m
  일치율: 수평 95-97%, 고도 93-95%
```

## 문제 해결

### GFS 캐시 파일이 없는 경우
```bash
python tests/integration/extend_gfs_to_24h.py
```

### NOMADS 접속 오류
- 최근 날짜로 변경 (현재 시각 기준 3-6시간 전)
- NOMADS 웹사이트에서 사용 가능한 날짜 확인
- https://nomads.ncep.noaa.gov/

### 메모리 부족
```python
# run_simple_24h_test.py 수정
config = SimulationConfig(
    # ...
    dt_max=30.0,  # 15.0에서 30.0으로 증가
)
```

### 궤적 조기 종료
- 더 넓은 공간 범위 사용 (110-150°E)
- 실제 GFS 데이터 다운로드

## 다음 단계

### 즉시 (오늘)
1. ✅ 외삽 데이터로 빠른 테스트 완료
2. ⏳ 실제 GFS 데이터 다운로드
3. ⏳ HYSPLIT Web과 비교

### 단기 (1주일)
1. 더 넓은 영역 (110-150°E) 테스트
2. 다양한 시작 위치 테스트
3. 계절별 테스트

### 중기 (1개월)
1. 파라미터 최적화
2. 알고리즘 개선
3. 99% 일치 달성

## 참고 문서

- **상세 문서 (영문)**: `24H_EASTASIA_TEST_SUMMARY.md`
- **전체 요약 (한글)**: `한글_요약.md`
- **파라미터 최적화**: `PARAMETER_OPTIMIZATION_READY.md`
- **99% 달성 로드맵**: `ACHIEVING_99_PERCENT.md`

## 연락처

문제가 발생하거나 질문이 있으면 이슈를 생성해주세요.

---

**현재 상태: 극동아시아 24시간 테스트 준비 완료! 🚀**

**다음 명령:**
```bash
python tests/integration/run_simple_24h_test.py
```
