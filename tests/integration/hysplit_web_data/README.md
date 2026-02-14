# HYSPLIT Web 데이터 디렉토리

이 디렉토리는 HYSPLIT Web에서 다운로드한 tdump 파일을 저장하는 곳입니다.

## 필요한 파일

8개 지역의 tdump 파일이 필요합니다:

```
tdump_서울.txt
tdump_부산.txt
tdump_제주.txt
tdump_도쿄.txt
tdump_오사카.txt
tdump_베이징.txt
tdump_상하이.txt
tdump_타이베이.txt
```

## 다운로드 방법

### 1. 도우미 스크립트 실행

```bash
python tests\integration\hysplit_web_helper.py
```

이 스크립트는:
- 8개 지역의 정확한 좌표 제공
- 단계별 가이드 출력
- 다운로드 진행 상황 확인
- 체크리스트 생성 (`CHECKLIST.txt`)

### 2. HYSPLIT Web 접속

https://www.ready.noaa.gov/HYSPLIT_traj.php

### 3. 공통 설정

- Model: GFS (0.25 degree)
- Start Time: 2026-02-14 00:00 UTC
- Direction: Backward
- Duration: 24 hours
- Vertical Motion: Model Vertical Velocity
- Interval: 1 hour

### 4. 각 지역 실행

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

각 지역마다:
1. 위도/경도/고도 입력
2. Run 클릭
3. 계산 완료 대기 (1-2분)
4. "Trajectory Endpoints" 다운로드
5. 파일명을 `tdump_<지역명>.txt`로 변경
6. 이 디렉토리에 저장

### 5. 비교 실행

```bash
python tests\integration\multi_location_24h_comparison.py --compare
```

## 파일 형식

tdump 파일은 HYSPLIT의 표준 궤적 출력 형식입니다:

```
     1 BACKWARD OMEGA   
     1 METEOROLOGICAL DATA FROM: GFS0P25
     1     26  2 14  0  0
     1 TRAJECTORY STARTED AT  0000 UTC 14 FEB 2026
     ...
```

## 진행 상황 확인

```bash
# 도우미 스크립트로 확인
python tests\integration\hysplit_web_helper.py

# 또는 수동으로 확인
dir tdump_*.txt
```

## 문제 해결

### 파일이 없습니다
- HYSPLIT Web에서 다운로드했는지 확인
- 파일명이 정확한지 확인 (`tdump_서울.txt`)
- 이 디렉토리에 저장했는지 확인

### 파일 형식 오류
- "Trajectory Endpoints" 다운로드 확인
- 텍스트 파일로 저장 확인 (.txt)
- 파일 인코딩 확인 (UTF-8)

### 비교 실패
- 8개 파일이 모두 있는지 확인
- 파일명이 정확한지 확인
- 파일 내용이 비어있지 않은지 확인

## 참고 문서

- `../다음_단계_실행_가이드.md` - 상세 실행 가이드 (한글)
- `../NEXT_STEPS.md` - 다음 단계 (영문)
- `../HYSPLIT_WEB_BATCH_GUIDE.md` - HYSPLIT Web 가이드
- `CHECKLIST.txt` - 다운로드 체크리스트

## 예상 소요 시간

- 각 지역: 3-5분
- 총 시간: 30-60분
- 비교 실행: 1분

---

**작성일:** 2026-02-14  
**상태:** 대기 중 (0/8 완료)
