# PyHYSPLIT 폴더 재구성 계획

## 현재 구조 (Flat)

```
pyhysplit/
├── __init__.py
├── boundary.py
├── cluster_analysis.py
├── concentration_grid.py
├── config_parser.py
├── coordinate_converter.py
├── deposition.py
├── dynamic_subgrid.py
├── engine.py
├── gpu_backend.py
├── integrator.py
├── interpolator.py
├── met_reader.py
├── models.py
├── output_writer.py
├── parallel.py
├── particle_manager.py
├── turbulence.py
├── verification.py
└── vertical_motion.py
```

## 새로운 구조 (Organized)

```
pyhysplit/
├── __init__.py                    # 메인 API 노출
│
├── core/                          # 핵심 엔진 및 모델
│   ├── __init__.py
│   ├── engine.py                  # 메인 궤적 엔진
│   ├── models.py                  # 데이터 모델 및 예외
│   ├── integrator.py              # Heun 적분기
│   └── interpolator.py            # 4D 보간
│
├── physics/                       # 물리 모듈
│   ├── __init__.py
│   ├── vertical_motion.py         # 수직 운동 (Mode 7 등)
│   ├── turbulence.py              # 난류
│   ├── deposition.py              # 침적
│   └── boundary.py                # 경계 조건
│
├── data/                          # 데이터 처리
│   ├── __init__.py
│   ├── met_reader.py              # 기상 데이터 읽기
│   ├── config_parser.py           # CONTROL/SETUP 파싱
│   └── output_writer.py           # TDUMP 출력
│
├── utils/                         # 유틸리티
│   ├── __init__.py
│   ├── coordinate_converter.py    # 좌표 변환
│   ├── dynamic_subgrid.py         # 동적 서브그리드
│   └── verification.py            # 검증 도구
│
├── analysis/                      # 분석 도구
│   ├── __init__.py
│   ├── cluster_analysis.py        # 클러스터 분석
│   └── concentration_grid.py      # 농도 그리드
│
└── compute/                       # 계산 백엔드
    ├── __init__.py
    ├── gpu_backend.py             # GPU/CPU 백엔드
    ├── parallel.py                # 병렬 처리
    └── particle_manager.py        # 입자 관리
```

## 카테고리 설명

### 1. core/ - 핵심 엔진
- 궤적 계산의 핵심 로직
- 데이터 모델 및 예외 정의
- 시간 적분 및 공간 보간

### 2. physics/ - 물리 모듈
- 대기 물리 관련 모듈
- 수직 운동, 난류, 침적, 경계 조건

### 3. data/ - 데이터 처리
- 입출력 관련 모듈
- 기상 데이터 읽기, 설정 파싱, 결과 출력

### 4. utils/ - 유틸리티
- 보조 기능
- 좌표 변환, 동적 서브그리드, 검증

### 5. analysis/ - 분석 도구
- 후처리 분석
- 클러스터 분석, 농도 계산

### 6. compute/ - 계산 백엔드
- 성능 최적화 관련
- GPU 지원, 병렬 처리, 입자 관리

## 마이그레이션 전략

### 1단계: 폴더 생성 및 파일 이동
- 각 카테고리 폴더 생성
- `__init__.py` 파일 생성
- 파일 이동 (smartRelocate 사용)

### 2단계: Import 경로 업데이트
- 모든 import 문 자동 업데이트 (smartRelocate가 처리)
- `__init__.py`에서 주요 API 재노출

### 3단계: 테스트 실행
- 모든 테스트 실행하여 검증
- Import 오류 수정

### 4단계: 문서 업데이트
- README.md 업데이트
- API 문서 업데이트

## 하위 호환성

메인 `pyhysplit/__init__.py`에서 주요 클래스를 재노출하여 기존 코드 호환:

```python
# 기존 코드가 계속 작동하도록
from pyhysplit.core.engine import TrajectoryEngine
from pyhysplit.core.models import SimulationConfig, StartLocation, MetData
from pyhysplit.data.met_reader import NetCDFReader

__all__ = [
    'TrajectoryEngine',
    'SimulationConfig',
    'StartLocation',
    'MetData',
    'NetCDFReader',
]
```

## 예상 효과

### 장점
1. ✅ 명확한 구조 - 파일 찾기 쉬움
2. ✅ 논리적 그룹화 - 관련 기능끼리 모임
3. ✅ 확장성 향상 - 새 기능 추가 위치 명확
4. ✅ 유지보수 용이 - 코드 관리 쉬움
5. ✅ 전문성 향상 - 프로젝트가 더 성숙해 보임

### 주의사항
1. ⚠️ Import 경로 변경 - smartRelocate가 자동 처리
2. ⚠️ 테스트 필요 - 모든 테스트 재실행
3. ⚠️ 문서 업데이트 - README 등 수정

## 실행 순서

1. 폴더 생성
2. `__init__.py` 파일 생성
3. 파일 이동 (smartRelocate)
4. 메인 `__init__.py` 업데이트
5. 테스트 실행
6. 문서 업데이트

---

**작성일**: 2026-02-14  
**상태**: 계획 단계  
**예상 소요 시간**: 10-15분
