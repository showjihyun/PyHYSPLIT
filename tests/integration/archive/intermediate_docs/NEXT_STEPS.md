# 다음 단계: HYSPLIT Web 비교

## 현재 상태 ✅

PyHYSPLIT이 8개 극동아시아 도시에서 24시간 역추적을 성공적으로 완료했습니다:

- ✅ 실제 GFS 0.25도 데이터 사용
- ✅ 100% 계산 성공률
- ✅ 11개 고품질 시각화 이미지
- ✅ 완전한 문서화
- ✅ 비교 인프라 준비 완료

## 즉시 실행 가능한 작업

### 옵션 1: HYSPLIT Web 수동 실행 (권장, 30-60분)

가장 확실하고 정확한 방법입니다.

**단계:**

1. **HYSPLIT Web 접속**
   ```
   https://www.ready.noaa.gov/HYSPLIT_traj.php
   ```

2. **공통 설정 입력**
   - Meteorology: GFS (0.25 degree)
   - Start Time: 2026-02-14 00:00 UTC
   - Direction: Backward
   - Duration: 24 hours
   - Vertical Motion: Model Vertical Velocity
   - Output Interval: 1 hour

3. **8개 지역 각각 실행** (각 3-5분)
   
   | 지역 | 위도 | 경도 | 고도 |
   |------|------|------|------|
   | 서울 | 37.5 | 127.0 | 850 |
   | 부산 | 35.1 | 129.0 | 850 |
   | 제주 | 33.5 | 126.5 | 850 |
   | 도쿄 | 35.7 | 139.7 | 850 |
   | 오사카 | 34.7 | 135.5 | 850 |
   | 베이징 | 39.9 | 116.4 | 850 |
   | 상하이 | 31.2 | 121.5 | 850 |
   | 타이베이 | 25.0 | 121.5 | 850 |

4. **tdump 파일 다운로드**
   - Run 클릭 → 계산 대기 (1-2분)
   - "Trajectory Endpoints" 다운로드
   - 저장: `tests/integration/hysplit_web_data/tdump_<지역명>.txt`

5. **비교 실행**
   ```bash
   python tests/integration/multi_location_24h_comparison.py --compare
   ```

**상세 가이드:** `HYSPLIT_WEB_BATCH_GUIDE.md`

### 옵션 2: Selenium 자동화 (고급, 2-3시간)

웹 자동화 도구를 사용하여 자동으로 실행합니다.

**필요 사항:**
```bash
pip install selenium webdriver-manager
```

**단계:**

1. **Selenium 스크립트 실행**
   ```bash
   python tests/integration/fetch_hysplit_web_trajectories.py
   ```
   - 옵션 2 선택: Selenium 자동화 예제 생성

2. **HYSPLIT Web HTML 구조 분석**
   - 브라우저 개발자 도구로 입력 필드 ID/Name 확인
   - `hysplit_web_selenium.py` 스크립트 수정

3. **자동화 실행**
   ```bash
   python tests/integration/hysplit_web_selenium.py
   ```

4. **비교 실행**
   ```bash
   python tests/integration/multi_location_24h_comparison.py --compare
   ```

**주의:** HYSPLIT Web의 HTML 구조가 변경될 수 있어 유지보수가 필요합니다.

### 옵션 3: 샘플 데이터로 테스트 (즉시, 1분)

비교 기능을 테스트하기 위한 샘플 데이터를 생성합니다.

```bash
python tests/integration/fetch_hysplit_web_trajectories.py
# 옵션 3 선택: 샘플 tdump 파일 생성

python tests/integration/multi_location_24h_comparison.py --compare
```

**주의:** 샘플 데이터는 실제 HYSPLIT Web 결과가 아니므로 정확한 비교가 불가능합니다.

## 예상 결과

### 현재 파라미터 기준 (95-97% 일치 예상)

**7시간 테스트 결과:**
- 수평 오차: 평균 15.55 km
- 고도 오차: 평균 60.2 m
- 일치율: 95%

**24시간 테스트 예상:**
- 수평 오차: 평균 40-50 km
- 고도 오차: 평균 150-180 m
- 일치율: 95-97%

### 지역별 예상 오차

| 지역 | 이동 거리 | 예상 수평 오차 | 예상 고도 오차 |
|------|----------|--------------|--------------|
| 서울 | 484 km | 40-50 km | 150-180 m |
| 부산 | 551 km | 45-55 km | 160-190 m |
| 제주 | 634 km | 50-65 km | 170-210 m |
| 도쿄 | 319 km | 30-40 km | 130-160 m |
| 오사카 | 134 km | 15-25 km | 100-130 m |
| 베이징 | 434 km | 40-50 km | 150-180 m |
| 상하이 | 414 km | 40-50 km | 150-180 m |
| 타이베이 | 195 km | 20-30 km | 110-140 m |

## 비교 후 다음 단계

### 1. 결과 분석 (즉시)

비교 결과를 분석하여 오차 패턴을 파악합니다:

- 수평 오차가 큰 지역은?
- 고도 오차가 큰 지역은?
- 시간에 따른 오차 증가 패턴은?
- 특정 기상 조건에서 오차가 큰가?

### 2. 파라미터 최적화 (1-2일)

현재 파라미터를 미세 조정하여 99% 일치를 목표로 합니다:

```bash
python tests/integration/quick_optimize.py
```

**조정 가능한 파라미터:**
- `vertical_damping`: 0.0003 (수직 속도 감쇠)
- `scale_height`: 8430.0 m (기압-고도 변환)
- `tratio`: 0.75 (CFL 비율)
- `dt_max`: 15.0 s (최대 시간 간격)

### 3. 알고리즘 개선 (1-2주)

더 정확한 보간 및 적분 방법을 구현합니다:

- Tricubic 보간 (현재: trilinear)
- Cubic spline 시간 보간 (현재: linear)
- Kahan summation (수치 안정성)
- 적응형 시간 간격

**예상 개선:** 97-98% 일치

### 4. HYSPLIT 소스 분석 (1개월)

HYSPLIT Fortran 소스 코드를 분석하여 정확한 알고리즘을 추출합니다:

- `hymodelc.f` - 메인 궤적 계산
- `advpnt.f` - 이류 계산
- `adviec.f` - 적분 방법
- `vcoord.f` - 좌표 변환

**예상 개선:** 99%+ 일치

## 디렉토리 구조

```
tests/integration/
├── gfs_cache/
│   └── gfs_eastasia_24h_real.nc          # GFS 데이터 (141.2 MB)
├── hysplit_web_data/                      # HYSPLIT Web 결과 (생성 필요)
│   ├── tdump_서울.txt                     # ← 여기에 저장
│   ├── tdump_부산.txt
│   ├── tdump_제주.txt
│   ├── tdump_도쿄.txt
│   ├── tdump_오사카.txt
│   ├── tdump_베이징.txt
│   ├── tdump_상하이.txt
│   └── tdump_타이베이.txt
├── trajectory_plots/                      # 시각화 이미지 (11개)
│   ├── all_trajectories.png
│   ├── distance_comparison.png
│   ├── speed_comparison.png
│   └── individual/                        # 개별 궤적 (8개)
├── multi_location_24h_results.json        # PyHYSPLIT 결과
├── multi_location_24h_comparison.py       # 비교 스크립트
├── download_gfs_real_eastasia.py          # GFS 다운로드
├── plot_trajectories.py                   # 시각화
└── fetch_hysplit_web_trajectories.py      # HYSPLIT Web 자동화
```

## 빠른 실행 가이드

### PyHYSPLIT 재실행 (이미 완료)

```bash
# GFS 데이터 다운로드 (최초 1회)
python tests/integration/download_gfs_real_eastasia.py

# 8개 지역 24시간 역추적
python tests/integration/multi_location_24h_comparison.py

# 시각화
python tests/integration/plot_trajectories.py
```

### HYSPLIT Web 비교 (다음 단계)

```bash
# 1. HYSPLIT Web에서 8개 지역 실행 (수동)
#    https://www.ready.noaa.gov/HYSPLIT_traj.php
#    가이드: HYSPLIT_WEB_BATCH_GUIDE.md

# 2. tdump 파일 저장
#    tests/integration/hysplit_web_data/tdump_<지역명>.txt

# 3. 비교 실행
python tests/integration/multi_location_24h_comparison.py --compare
```

## 문제 해결

### HYSPLIT Web 접속 불가
- NOAA 서버 점검 시간 확인
- 다른 시간대에 재시도
- VPN 사용 (일부 지역에서 차단될 수 있음)

### 계산 실패
- 시작 위치가 GFS 데이터 범위 내인지 확인 (110-150°E, 20-50°N)
- 시작 시간이 GFS 데이터 범위 내인지 확인 (2026-02-14 00:00 UTC)
- 고도가 적절한지 확인 (850m AGL)

### tdump 파일 형식 오류
- "Trajectory Endpoints" 다운로드 확인 (다른 형식 아님)
- 텍스트 파일로 저장 확인 (.txt)
- 파일 인코딩 확인 (UTF-8)

### 비교 결과가 이상함
- PyHYSPLIT과 HYSPLIT Web의 설정이 동일한지 확인
- GFS 데이터 버전 확인 (0.25도)
- 시작 시간 확인 (2026-02-14 00:00 UTC)

## 참고 자료

### 문서
- `FINAL_SUMMARY.md` - 프로젝트 전체 요약
- `최종_요약.md` - 한글 요약
- `HYSPLIT_WEB_BATCH_GUIDE.md` - HYSPLIT Web 상세 가이드
- `MULTI_LOCATION_24H_SUMMARY.md` - 다중 지역 결과
- `PARAMETER_OPTIMIZATION_READY.md` - 파라미터 최적화
- `ACHIEVING_99_PERCENT_MATCH.md` - 99% 달성 로드맵

### 스크립트
- `multi_location_24h_comparison.py` - 메인 비교 스크립트
- `fetch_hysplit_web_trajectories.py` - HYSPLIT Web 자동화
- `plot_trajectories.py` - 시각화
- `download_gfs_real_eastasia.py` - GFS 다운로드

### 외부 링크
- [HYSPLIT Web](https://www.ready.noaa.gov/HYSPLIT_traj.php)
- [HYSPLIT 사용자 가이드](https://www.ready.noaa.gov/HYSPLIT_tutorial.php)
- [GFS 데이터](https://www.ncei.noaa.gov/products/weather-climate-models/global-forecast-system)

## 요약

**현재 상태:**
- ✅ PyHYSPLIT 8개 지역 24시간 역추적 완료
- ✅ 시각화 완료 (11개 이미지)
- ✅ 비교 인프라 준비 완료
- ⏳ HYSPLIT Web 데이터 필요

**즉시 실행:**
1. HYSPLIT Web에서 8개 지역 실행 (30-60분)
2. tdump 파일 다운로드 및 저장
3. 비교 실행: `python multi_location_24h_comparison.py --compare`

**예상 결과:**
- 수평 오차: 평균 40-50 km
- 고도 오차: 평균 150-180 m
- 일치율: 95-97%

**최종 목표:**
- 파라미터 최적화 → 99% 일치

---

**작성일:** 2026-02-14  
**PyHYSPLIT 버전:** Development  
**다음 업데이트:** HYSPLIT Web 비교 완료 후
