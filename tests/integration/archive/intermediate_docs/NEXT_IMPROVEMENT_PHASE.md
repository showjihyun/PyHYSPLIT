# 다음 개선 단계 - 85-90% 목표

## 현재 상태 (80% 달성)

### 성과
- ✅ 방향 일치율: 100% (8/8 위치)
- ✅ 압력 오차 중앙값: 19.4 hPa (목표 <20 hPa 달성!)
- ⚠️ 압력 오차 평균: 22.9 hPa (목표 <20 hPa, 85% 달성)
- ⚠️ 수평 오차 평균: 43.31 km (목표 <20 km, 65% 달성)

### 주요 개선 완료
1. ✅ Omega 부호 수정 (역궤적 압력 변화 방향 수정)
2. ✅ 자동 수직 속도 모드 선택 (위도 기반)
3. ✅ Mode 3 조사 및 복원 (return 0.0이 최적)
4. ✅ 보간 및 시간 스텝 분석 (이미 최적)

## 남은 과제

### 1. Mode 3 압력 오차 (우선순위: 높음)
**현상**: 저위도 위치에서 평균 34.9 hPa
- 제주 (33.5°N): 36.3 hPa
- 상하이 (31.2°N): 68.3 hPa ⚠️ 가장 높음
- 타이베이 (25.0°N): 28.3 hPa

**원인**: Mode 3 (Isentropic)이 압력 변화를 0으로 만듦

**해결 방안**:
- Option A: 모든 위치에 Mode 7 사용 (단순화)
- Option B: Mode 0 (data velocity) 테스트
- Option C: 위도 경계 조정 (33.5°N → 30°N)

**예상 개선**: 22.9 hPa → 18-20 hPa (15-20% 개선)

### 2. 수평 오차 (우선순위: 중간)
**현상**: 평균 43.31 km (목표: <20 km)

**가능한 원인**:
- 풍속장 보간 정확도
- 수평 이동 알고리즘
- CFL 조건 (tratio)
- 시간 스텝 크기

**해결 방안**:
- 풍속장 오차 분석
- 오차 핫스팟 식별
- 파라미터 미세 조정

**예상 개선**: 43.31 km → 30-35 km (20-30% 개선)

### 3. 베이징 경계 오류 (우선순위: 낮음)
**현상**: 궤적이 GFS 그리드 경계를 벗어남

**해결**: GFS 데이터 범위 확장 (110°E → 105°E)

**예상 개선**: 경계 오류 제거

## 즉시 실행 가능한 개선

### Phase 1: Mode 7 전체 테스트 (1-2시간)

**목표**: Mode 7이 저위도에서도 Mode 3보다 나은지 확인

**실행**:
```bash
python tests/integration/test_mode7_all_locations.py
```

**예상 결과**:
- 저위도 압력 오차: 34.9 hPa → 20-25 hPa
- 전체 평균 압력 오차: 22.9 hPa → 18-20 hPa
- 진행률: 80% → 82-83%

**판단 기준**:
- Mode 7이 더 나으면: engine.py 업데이트하여 모든 위치에 Mode 7 사용
- Mode 3이 더 나으면: 현재 auto_vertical_mode 유지

### Phase 2: GFS 데이터 확장 (1시간)

**목표**: 베이징 경계 오류 해결

**실행**:
```bash
python tests/integration/download_gfs_extended.py
```

**변경사항**:
- 경도 범위: 110-150°E → 105-150°E
- 추가 데이터: ~20 MB

**예상 결과**:
- 베이징 궤적 완전 계산
- 진행률: 82-83% → 83-84%

### Phase 3: 풍속장 오차 분석 (3-4시간)

**목표**: 수평 오차의 원인 파악

**실행**:
```bash
python tests/integration/analyze_wind_errors.py
```

**분석 내용**:
1. 각 위치의 풍속장 그래디언트
2. 보간 오차 추정
3. 시간 스텝 vs 오차 관계
4. 오차 핫스팟 식별

**예상 결과**:
- 오차 원인 식별
- 개선 방향 제시
- 진행률: 변화 없음 (분석만)

### Phase 4: 타겟 수정 적용 (5-10시간)

**목표**: 풍속장 분석 결과 기반 개선

**가능한 수정**:
1. 풍속장 보간 개선
2. CFL 조건 조정
3. 시간 스텝 최적화
4. 지형 효과 보정

**예상 결과**:
- 수평 오차: 43.31 km → 30-35 km
- 진행률: 83-84% → 88-90%

## 실행 순서

### 1단계: Mode 7 테스트 (즉시 실행 가능)

```bash
# 1. 분석 스크립트 실행 (현재 상태 확인)
python tests/integration/analyze_remaining_errors.py

# 2. Mode 7 전체 테스트
python tests/integration/test_mode7_all_locations.py

# 3. 결과 비교 (HYSPLIT Web 데이터 있는 경우)
python tests/integration/compare_mode7_results.py
```

**소요 시간**: 1-2시간
**예상 개선**: 80% → 82-83%

### 2단계: GFS 확장 (Mode 7 테스트 후)

```bash
# 1. GFS 데이터 확장 다운로드
python tests/integration/download_gfs_extended.py

# 2. 베이징 재테스트
python tests/integration/test_beijing_extended.py
```

**소요 시간**: 1시간
**예상 개선**: 82-83% → 83-84%

### 3단계: 풍속장 분석 (GFS 확장 후)

```bash
# 1. 풍속장 오차 분석
python tests/integration/analyze_wind_errors.py

# 2. 오차 핫스팟 시각화
python tests/integration/visualize_error_hotspots.py
```

**소요 시간**: 3-4시간
**예상 개선**: 분석만 (개선 없음)

### 4단계: 타겟 수정 (분석 결과 기반)

분석 결과에 따라 결정

**소요 시간**: 5-10시간
**예상 개선**: 83-84% → 88-90%

## 진행률 예측

| 단계 | 작업 | 압력 오차 | 수평 오차 | 진행률 | 소요 시간 |
|------|------|-----------|-----------|--------|----------|
| 현재 | Auto vertical mode | 22.9 hPa | 43.31 km | 80% | - |
| 1 | Mode 7 전체 테스트 | 18-20 hPa | 43.31 km | 82-83% | 1-2h |
| 2 | GFS 확장 | 18-20 hPa | 43.31 km | 83-84% | 1h |
| 3 | 풍속장 분석 | 18-20 hPa | 43.31 km | 83-84% | 3-4h |
| 4 | 타겟 수정 | 18-20 hPa | 30-35 km | 88-90% | 5-10h |

**총 소요 시간**: 10-17시간
**예상 최종 진행률**: 88-90%

## 성공 기준

### 단기 목표 (1-2일)
- ✅ 압력 오차 평균: <20 hPa
- ⚠️ 수평 오차 평균: <35 km (중간 목표)
- ✅ 방향 일치율: 100% 유지
- 진행률: 85-90%

### 중기 목표 (1-2주)
- ✅ 압력 오차 평균: <18 hPa
- ✅ 수평 오차 평균: <25 km
- ✅ 방향 일치율: 100% 유지
- 진행률: 90-95%

### 장기 목표 (1개월)
- ✅ 압력 오차 평균: <15 hPa
- ✅ 수평 오차 평균: <20 km
- ✅ 방향 일치율: 100% 유지
- 진행률: 95-99%

## 파일 목록

### 새로 생성된 파일
- `tests/integration/analyze_remaining_errors.py` - 오차 분석 스크립트
- `tests/integration/test_mode7_all_locations.py` - Mode 7 전체 테스트
- `tests/integration/NEXT_IMPROVEMENT_PHASE.md` - 이 문서

### 생성 예정 파일
- `tests/integration/download_gfs_extended.py` - GFS 확장 다운로드
- `tests/integration/test_beijing_extended.py` - 베이징 재테스트
- `tests/integration/analyze_wind_errors.py` - 풍속장 오차 분석
- `tests/integration/visualize_error_hotspots.py` - 오차 시각화
- `tests/integration/compare_mode7_results.py` - Mode 7 결과 비교

## 의사결정 트리

```
현재 상태 (80%)
    │
    ├─> Mode 7 전체 테스트
    │       │
    │       ├─> Mode 7이 더 나음
    │       │       └─> engine.py 업데이트 (Mode 7 everywhere)
    │       │               └─> 82-83% 달성
    │       │
    │       └─> Mode 3이 더 나음
    │               └─> 현재 auto_vertical_mode 유지
    │                       └─> 80% 유지
    │
    ├─> GFS 데이터 확장
    │       └─> 베이징 경계 오류 해결
    │               └─> 83-84% 달성
    │
    ├─> 풍속장 오차 분석
    │       │
    │       ├─> 보간 오차 발견
    │       │       └─> 보간 방법 개선
    │       │
    │       ├─> CFL 조건 문제
    │       │       └─> tratio 조정
    │       │
    │       └─> 시간 스텝 문제
    │               └─> dt_max 조정
    │
    └─> 타겟 수정 적용
            └─> 88-90% 달성
```

## 리스크 관리

### 낮은 리스크
- Mode 7 전체 테스트: 쉽게 되돌릴 수 있음
- GFS 데이터 확장: 데이터 다운로드만
- 풍속장 분석: 코드 변경 없음

### 중간 리스크
- 보간 방법 변경: 안정성 영향 가능
- CFL 조건 조정: 수치 안정성 영향
- 시간 스텝 조정: 계산 시간 증가 가능

### 높은 리스크
- 알고리즘 대폭 변경: 예상치 못한 부작용
- HYSPLIT 소스 코드 분석: 시간 소요 큼

**권장**: 낮은 리스크 작업부터 순차적으로 진행

## 즉시 시작

**지금 바로 실행**:
```bash
# 1. 현재 상태 분석
python tests/integration/analyze_remaining_errors.py

# 2. Mode 7 전체 테스트
python tests/integration/test_mode7_all_locations.py
```

**예상 시간**: 1-2시간
**예상 결과**: 80% → 82-83% 진행률

---

**작성일**: 2026-02-14
**현재 진행률**: 80%
**목표 진행률**: 85-90% (단기), 95-99% (장기)
**다음 업데이트**: Mode 7 테스트 완료 후
