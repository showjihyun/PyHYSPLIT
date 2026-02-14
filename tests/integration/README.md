# Integration Tests

통합 테스트 및 검증 스크립트 모음입니다.

## 폴더 구조

```
tests/integration/
├── README.md              # 이 파일
├── __init__.py
│
├── active/                # 현재 사용 중인 스크립트
│   ├── test_all_locations_very_wide.py  # 전체 위치 테스트
│   ├── test_dynamic_subgrid.py          # 동적 서브그리드 테스트
│   ├── final_hysplit_comparison.py      # 최종 HYSPLIT 비교
│   ├── download_gfs_west_extension.py   # GFS 서쪽 확장 다운로드
│   ├── merge_gfs_data.py                # GFS 데이터 병합
│   └── hysplit_web_helper.py            # HYSPLIT Web 헬퍼
│
├── docs/                  # 최종 문서
│   ├── FINAL_PROJECT_STATUS.md          # 최종 프로젝트 상태
│   ├── PROJECT_COMPLETION_SUMMARY.md    # 프로젝트 완료 요약 (영문)
│   ├── 프로젝트_완료_최종_보고서.md      # 프로젝트 완료 보고서 (한글)
│   ├── VERY_WIDE_TEST_FINAL_RESULTS.md  # 최종 테스트 결과
│   ├── DYNAMIC_SUBGRID_*.md             # 동적 서브그리드 문서
│   ├── HYSPLIT_LITERATURE_REVIEW.md     # HYSPLIT 문헌 조사
│   └── QUICK_START_DYNAMIC_SUBGRID.md   # 빠른 시작 가이드
│
├── results/               # 최종 결과 파일
│   ├── final_comparison_results.json
│   ├── very_wide_test_results.json
│   └── dynamic_subgrid_results.json
│
├── gfs_cache/             # GFS 기상 데이터
│   └── gfs_eastasia_24h_very_wide.nc    # 95-150°E 범위 (395 MB)
│
└── archive/               # 과거 개발 과정 (참고용)
    ├── debug/             # 디버그 스크립트
    ├── intermediate_tests/  # 중간 테스트 스크립트
    ├── intermediate_docs/   # 중간 문서
    ├── intermediate_results/  # 중간 결과
    ├── screenshots/       # 스크린샷 및 HTML
    └── korean_docs/       # 한글 중간 문서
```

## 주요 테스트

### 1. 전체 위치 테스트

```bash
python tests/integration/active/test_all_locations_very_wide.py
```

7개 위치에서 24시간 역궤적 계산 및 검증:
- 서울, 베이징, 도쿄, 부산, 상하이, 타이베이, 홍콩

**예상 결과**: 7/7 위치 100% 완료

### 2. 동적 서브그리드 테스트

```bash
python tests/integration/active/test_dynamic_subgrid.py
```

동적 서브그리드 확장 감지 기능 테스트:
- 경계 근접 감지
- 풍속 기반 확장 계산
- 확장 이력 추적

### 3. 최종 HYSPLIT 비교

```bash
python tests/integration/active/final_hysplit_comparison.py
```

HYSPLIT과의 최종 정확도 비교:
- 수평 오차: ~35 km
- 압력 오차: ~8 hPa
- 완료율: 100%

## 데이터 다운로드

### GFS 서쪽 확장 다운로드

```bash
python tests/integration/active/download_gfs_west_extension.py
```

95-105°E 범위의 GFS 데이터 다운로드 (최신 데이터)

### 데이터 병합

```bash
python tests/integration/active/merge_gfs_data.py
```

서쪽 확장 (95-105°E) + 기존 (105-150°E) → 완전한 범위 (95-150°E)

## 최종 결과

### 성능 지표

| 지표 | 값 | 상태 |
|------|-----|------|
| **진행률** | 95-98% | ✅ |
| **완료율** | 100% (7/7) | ✅ |
| **수평 오차** | ~35 km | ✅ |
| **압력 오차** | ~8 hPa | ✅ |
| **경계 오류** | 0% | ✅ |

### 위치별 결과

| 위치 | 완료율 | 상태 |
|------|--------|------|
| 서울 | 100% | ✅ |
| 베이징 | 100% | ✅ |
| 도쿄 | 100% | ✅ |
| 부산 | 100% | ✅ |
| 상하이 | 100% | ✅ |
| 타이베이 | 100% | ✅ |
| 홍콩 | 100% | ✅ |

## 문서

### 최종 문서 (docs/)

1. **FINAL_PROJECT_STATUS.md** - 최종 프로젝트 상태 및 평가
2. **PROJECT_COMPLETION_SUMMARY.md** - 영문 완료 요약
3. **프로젝트_완료_최종_보고서.md** - 한글 완료 보고서
4. **VERY_WIDE_TEST_FINAL_RESULTS.md** - 최종 테스트 결과 분석
5. **DYNAMIC_SUBGRID_IMPLEMENTATION_SUMMARY.md** - 동적 서브그리드 구현
6. **HYSPLIT_LITERATURE_REVIEW.md** - HYSPLIT 문헌 조사
7. **QUICK_START_DYNAMIC_SUBGRID.md** - 빠른 시작 가이드

### 개발 과정 문서 (archive/)

과거 개발 과정의 모든 문서, 스크립트, 결과가 보관되어 있습니다.
참고용으로 보관되며, 현재 사용하지 않습니다.

## 주의사항

### GFS 데이터

- **파일 크기**: 395 MB (gfs_eastasia_24h_very_wide.nc)
- **범위**: 95-150°E, 20-50°N
- **해상도**: 0.25°
- **시간 범위**: 24시간

### 테스트 실행 시간

- 전체 위치 테스트: ~10초 (7개 위치)
- 동적 서브그리드 테스트: ~5초 (4개 위치)
- 최종 비교: ~10초 (7개 위치)

## 문제 해결

### GFS 데이터가 없는 경우

```bash
# 서쪽 확장 다운로드
python tests/integration/active/download_gfs_west_extension.py

# 데이터 병합
python tests/integration/active/merge_gfs_data.py
```

### 테스트 실패 시

1. GFS 데이터 확인: `gfs_cache/gfs_eastasia_24h_very_wide.nc` 존재 여부
2. 데이터 범위 확인: 95-150°E, 20-50°N
3. 로그 확인: 경계 오류 메시지

## 참고

- 프로젝트 루트의 `README.md` 참조
- `docs/` 폴더의 최종 문서 참조
- 문제 발생 시 GitHub Issues 참조

---

**마지막 업데이트**: 2026-02-14  
**상태**: ✅ 정리 완료  
**버전**: 1.0.0
