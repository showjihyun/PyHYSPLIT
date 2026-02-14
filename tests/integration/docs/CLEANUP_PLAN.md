# tests/integration 폴더 정리 계획

## 정리 날짜: 2026-02-14

## 보관할 파일 (현재 사용 중 또는 중요)

### 핵심 테스트 스크립트
- `test_all_locations_very_wide.py` - 최종 검증 테스트
- `test_dynamic_subgrid.py` - 동적 서브그리드 테스트
- `final_hysplit_comparison.py` - 최종 비교
- `test_hysplit_web_comparison.py` - HYSPLIT Web 비교

### 데이터 다운로드 스크립트
- `download_gfs_west_extension.py` - 서쪽 확장 다운로드
- `merge_gfs_data.py` - 데이터 병합
- `check_gfs_coverage.py` - 데이터 범위 확인

### 최종 문서 (보관)
- `FINAL_PROJECT_STATUS.md` - 최종 프로젝트 상태
- `PROJECT_COMPLETION_SUMMARY.md` - 프로젝트 완료 요약
- `프로젝트_완료_최종_보고서.md` - 한글 최종 보고서
- `VERY_WIDE_TEST_FINAL_RESULTS.md` - 최종 테스트 결과
- `DYNAMIC_SUBGRID_IMPLEMENTATION_SUMMARY.md` - 동적 서브그리드 구현
- `HYSPLIT_LITERATURE_REVIEW.md` - HYSPLIT 문헌 조사
- `QUICK_START_DYNAMIC_SUBGRID.md` - 빠른 시작 가이드

### 결과 파일
- `final_comparison_results.json`
- `very_wide_test_results.json`
- `dynamic_subgrid_results.json`

### 유틸리티
- `hysplit_web_helper.py` - HYSPLIT Web 헬퍼
- `plot_trajectories.py` - 궤적 시각화

## archive 폴더로 이동할 파일 (과거 개발 과정)

### 중간 단계 문서 (30+개)
- 모든 SESSION_*.md 파일
- 모든 PRIORITY*.md 파일
- 모든 PHASE*.md 파일
- 모든 NEXT_*.md 파일
- 모든 READY_*.md 파일
- 중간 요약 문서들

### 디버그/진단 스크립트 (40+개)
- debug_*.py
- diagnose_*.py
- check_*.py (일부)
- analyze_*.py
- inspect_*.py
- investigate_*.py

### 중간 테스트 스크립트 (20+개)
- test_mode7_*.py
- test_vertical_*.py
- test_improved_*.py
- test_extended_*.py
- test_optimized_*.py
- 기타 중간 테스트들

### 중간 결과 파일
- mode7_*.json
- vertical_*.json
- optimized_*.json
- extended_*.json
- 기타 중간 결과들

### 스크린샷/HTML 파일
- 모든 .png 파일
- 모든 .html 파일
- 모든 .gif 파일

### 한글 중간 문서
- 개선_*.md
- 다음_*.md
- 비교_*.md
- 준비_*.md
- 최종_요약.md (중복)
- 한글_요약.md (중복)

## 삭제할 파일

### 임시 파일
- __pycache__ 폴더
- *.pyc 파일

### 중복 문서
- FINAL_SUMMARY.md (구버전)
- 최종_요약.md (구버전)

## 정리 후 구조

```
tests/integration/
├── README.md (새로 작성)
├── __init__.py
│
├── active/  (현재 사용 중)
│   ├── test_all_locations_very_wide.py
│   ├── test_dynamic_subgrid.py
│   ├── final_hysplit_comparison.py
│   ├── download_gfs_west_extension.py
│   ├── merge_gfs_data.py
│   └── hysplit_web_helper.py
│
├── docs/  (최종 문서)
│   ├── FINAL_PROJECT_STATUS.md
│   ├── PROJECT_COMPLETION_SUMMARY.md
│   ├── 프로젝트_완료_최종_보고서.md
│   ├── VERY_WIDE_TEST_FINAL_RESULTS.md
│   ├── DYNAMIC_SUBGRID_IMPLEMENTATION_SUMMARY.md
│   ├── HYSPLIT_LITERATURE_REVIEW.md
│   └── QUICK_START_DYNAMIC_SUBGRID.md
│
├── results/  (최종 결과)
│   ├── final_comparison_results.json
│   ├── very_wide_test_results.json
│   └── dynamic_subgrid_results.json
│
├── gfs_cache/  (GFS 데이터)
│   └── gfs_eastasia_24h_very_wide.nc
│
└── archive/  (과거 개발 과정)
    ├── debug/
    ├── intermediate_tests/
    ├── intermediate_docs/
    ├── screenshots/
    └── intermediate_results/
```

## 실행 순서

1. archive 폴더 생성
2. 하위 폴더 생성 (debug, intermediate_tests, etc.)
3. 파일 이동
4. 임시 파일 삭제
5. active, docs, results 폴더 생성
6. 현재 파일 재구성
7. README.md 작성
