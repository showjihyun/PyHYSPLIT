# Implementation Plan: HYSPLIT Trajectory Engine (pyhysplit)

## Overview

HYSPLIT 대기 수송 및 확산 모델링 시스템을 Python으로 재구현한다. 핵심 알고리즘(보간, 적분, Δt 제어)부터 시작하여 물리 과정, 입출력, 병렬/GPU 가속 순서로 점진적으로 구축한다. 각 단계에서 속성 기반 테스트로 정확성을 검증한다.

## Tasks

- [x] 1. 프로젝트 구조 및 핵심 데이터 모델 설정
  - [x] 1.1 프로젝트 디렉토리 구조 생성 및 pyproject.toml/setup 설정
    - `pyhysplit/` 패키지 디렉토리, `tests/unit/`, `tests/property/`, `tests/integration/` 생성
    - pytest, hypothesis, numpy, scipy 의존성 설정
    - _Requirements: 전체_
  - [x] 1.2 핵심 데이터 모델 정의 (`pyhysplit/models.py`)
    - `StartLocation`, `ConcentrationGridConfig`, `SimulationConfig`, `MetData`, `ParticleState` dataclass 구현
    - 커스텀 예외 클래스 정의 (`BoundaryError`, `ConfigParseError`, `MetFileNotFoundError` 등)
    - _Requirements: 1.1-1.6, 5.1-5.8, 10.1-10.6_

- [x] 2. 4D 보간기 구현
  - [x] 2.1 Interpolator 클래스 구현 (`pyhysplit/interpolator.py`)
    - `trilinear` 메서드: x→y→z 순서 3D 선형 보간
    - `interpolate_4d` 메서드: 공간 보간 후 시간 보간으로 (u, v, w) 반환
    - `interpolate_scalar` 메서드: 임의 스칼라 변수 4D 보간
    - 격자 범위 밖 위치에서 `BoundaryError` 발생
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_
  - [x] 2.2 보간기 속성 테스트 작성 (`tests/property/test_interpolator_props.py`)
    - **Property 1: 보간 격자점 정확성** — 격자점 위 보간 = 실제 값
    - **Validates: Requirements 1.2, 1.6**
    - **Property 2: 보간 순서 민감성** — x→y→z 순서 검증
    - **Validates: Requirements 1.1, 1.3, 1.5**
    - **Property 3: 격자 범위 밖 오류** — 범위 밖 위치에서 BoundaryError
    - **Validates: Requirements 1.4**

- [x] 3. Heun 적분기 및 Δt 제어 구현
  - [x] 3.1 HeunIntegrator 클래스 구현 (`pyhysplit/integrator.py`)
    - `advect_lonlat` 정적 메서드: 지구 곡률 기반 lon/lat 이동
    - `step` 메서드: Predictor-Corrector 2단계 Heun 적분
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_
  - [x] 3.2 AdaptiveDtController 클래스 구현 (`pyhysplit/integrator.py`)
    - `_compute_grid_spacing`: 격자 간격 미터 단위 계산
    - `compute_dt`: CFL 기반 적응형 Δt (수평+수직), 상한 적용, 시간 경계 클리핑
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_
  - [x] 3.3 적분기 속성 테스트 작성 (`tests/property/test_integrator_props.py`)
    - **Property 4: 균일 풍속장 Heun 정확성** — 균일 풍속에서 Heun = Euler
    - **Validates: Requirements 2.1, 2.2**
    - **Property 5: 지구 곡률 이동 공식** — advect_lonlat 공식 검증
    - **Validates: Requirements 2.3, 2.4**
  - [x] 3.4 Δt 제어 속성 테스트 작성 (`tests/property/test_dt_controller_props.py`)
    - **Property 6: CFL 조건 불변량** — Δt ≤ min(Δx/|u|, Δy/|v|, Δz/|w|, dt_max)
    - **Validates: Requirements 3.1, 3.3, 3.6**
    - **Property 7: 시간 경계 클리핑** — Δt가 시간 경계 초과 안 함
    - **Validates: Requirements 3.4**

- [x] 4. Checkpoint — 핵심 알고리즘 검증
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. 좌표 변환 및 수직 운동 구현
  - [x] 5.1 CoordinateConverter 클래스 구현 (`pyhysplit/coordinate_converter.py`)
    - `sigma_to_pressure`, `pressure_to_height`, `height_to_pressure`, `hybrid_to_pressure`, `terrain_correction` 메서드
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  - [x] 5.2 VerticalMotionHandler 클래스 구현 (`pyhysplit/vertical_motion.py`)
    - 5가지 수직 운동 방식 (0=데이터, 1=등밀도, 2=등압, 3=등온위, 4=등고도)
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_
  - [x] 5.3 좌표 변환 속성 테스트 작성 (`tests/property/test_coordinate_props.py`)
    - **Property 13: 좌표 변환 Round Trip** — sigma↔pressure, pressure↔height round trip
    - **Validates: Requirements 6.1, 6.2**
    - **Property 14: Hybrid 좌표 양수 기압** — hybrid_to_pressure > 0
    - **Validates: Requirements 6.3**
    - **Property 15: 지형 보정 불변량** — terrain_correction = z_agl + terrain_h
    - **Validates: Requirements 6.4**
  - [x] 5.4 수직 운동 속성 테스트 작성 (`tests/property/test_vertical_motion_props.py`)
    - **Property 34: 등압면 수직 속도 영** — mode=2일 때 w=0
    - **Validates: Requirements 17.3**
    - **Property 35: 등온위면 온위 보존** — mode=3에서 θ 보존
    - **Validates: Requirements 17.4**

- [x] 6. 난류 확산 모듈 구현
  - [x] 6.1 TurbulenceModule 클래스 구현 (`pyhysplit/turbulence.py`)
    - `compute_kz`: PBL/u*/L 기반 수직 확산 계수 (CBL/SBL 분기)
    - `compute_kh`: Richardson 확산 법칙 기반 수평 확산 계수
    - `get_perturbation`: 난류 속도 섭동 계산 (σ 모드 + PBL 모드)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_
  - [x] 6.2 난류 모듈 속성 테스트 작성 (`tests/property/test_turbulence_props.py`)
    - **Property 16: Kz 비음수 및 PBL 경계** — Kz ≥ 0.01, z > PBL이면 Kz = 0.01
    - **Validates: Requirements 7.2, 7.8**
    - **Property 17: 안정도 Kz 순서** — 불안정(L<0) Kz ≥ 안정(L>0) Kz
    - **Validates: Requirements 7.3, 7.4**
    - **Property 18: Kh 격자 비례** — Kh = min(0.0001·Δx^(4/3), khmax)
    - **Validates: Requirements 7.5**
    - **Property 19: 난류 비활성화 영섭동** — off일 때 (0,0,0)
    - **Validates: Requirements 7.7**

- [x] 7. 침적 모듈 구현
  - [x] 7.1 DepositionModule 클래스 구현 (`pyhysplit/deposition.py`)
    - `gravitational_settling`: Stokes 법칙 침강 속도
    - `dry_deposition_velocity`: 3-저항 모델
    - `below_cloud_scavenging`: Λ = a·P^b
    - `apply_deposition`: 질량 감소 m·exp(-(v_d/Δz + Λ)·Δt)
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_
  - [x] 7.2 침적 모듈 속성 테스트 작성 (`tests/property/test_deposition_props.py`)
    - **Property 20: 질량 단조 감소 및 양수** — 0 < m(t+Δt) ≤ m(t)
    - **Validates: Requirements 8.5, 8.6**
    - **Property 21: Stokes 침강 속도** — v_g = ρ·d²·g/(18·μ)
    - **Validates: Requirements 8.1**
    - **Property 22: 3-저항 건조 침적** — v_d = 1/(r_a+r_b+r_s) + v_g
    - **Validates: Requirements 8.2**
    - **Property 23: Below-Cloud Scavenging** — Λ = a·P^b, P=0이면 Λ=0
    - **Validates: Requirements 8.3**

- [x] 8. 경계 처리 구현
  - [x] 8.1 BoundaryHandler 클래스 구현 (`pyhysplit/boundary.py`)
    - 날짜변경선 처리, 극점 통과, 지표면/상한 반사, 수평 격자 범위 검사
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_
  - [x] 8.2 경계 처리 속성 테스트 작성 (`tests/property/test_boundary_props.py`)
    - **Property 29: 수직 경계 반사 불변량** — terrain_h ≤ z ≤ model_top
    - **Validates: Requirements 13.1, 13.2**
    - **Property 30: 수평 좌표 정규화** — -180 ≤ lon ≤ 180, -90 ≤ lat ≤ 90
    - **Validates: Requirements 13.3, 13.5**

- [x] 9. Checkpoint — 물리 과정 모듈 검증
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. 설정 파일 파서 구현
  - [x] 10.1 ConfigParser 구현 (`pyhysplit/config_parser.py`)
    - CONTROL 파일 파싱 (고정 형식 텍스트)
    - SETUP.CFG 파싱 (Fortran namelist &SETUP 블록)
    - SimulationConfig dataclass로 변환
    - CONTROL/SETUP.CFG 역생성 (write) 기능
    - 오류 처리: 누락/형식 오류 시 줄 번호 명시
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  - [x] 10.2 설정 파서 속성 테스트 작성 (`tests/property/test_config_props.py`)
    - **Property 26: CONTROL/SETUP.CFG Round Trip** — write → parse → write = 원본
    - **Validates: Requirements 11.1, 11.2, 11.5**
    - **Property 27: CONTROL 파일 오류 검출** — 잘못된 입력에서 오류 발생
    - **Validates: Requirements 11.3**

- [x] 11. 기상 데이터 리더 구현
  - [x] 11.1 MetReaderBase 및 ARLReader 구현 (`pyhysplit/met_reader.py`)
    - ARL packed binary 포맷: 50-byte 헤더 파싱, 데이터 언패킹
    - `convert_omega_to_w`: Pa/s → m/s 변환
    - `concatenate_met_files`: 다중 파일 시간 연결
    - MetReaderFactory 팩토리 패턴
    - _Requirements: 5.1, 5.2, 5.4, 5.5, 5.7, 5.8_
  - [x] 11.2 NetCDFReader, ERA5Reader, WRFReader 구현 (`pyhysplit/met_reader.py`)
    - 각 소스별 변수명 매핑 테이블
    - 좌표계 변환 및 메타데이터 추출
    - _Requirements: 5.3, 5.6_
  - [x] 11.3 기상 리더 속성 테스트 작성 (`tests/property/test_met_reader_props.py`)
    - **Property 11: Pa/s → m/s 변환 공식** — w = -omega·Rd·T/(g·P)
    - **Validates: Requirements 5.4**
    - **Property 12: 다중 파일 시간 단조성** — t_grid 순단조 증가
    - **Validates: Requirements 5.5**

- [x] 12. 입자 관리자 및 농도 격자 구현
  - [x] 12.1 ParticleManager 클래스 구현 (`pyhysplit/particle_manager.py`)
    - 입자 초기화, 연속 방출, 비활성화, 궤적 기록
    - 구조화된 배열 기반 벡터화 연산
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_
  - [x] 12.2 ConcentrationGrid 클래스 구현 (`pyhysplit/concentration_grid.py`)
    - 3D 격자 생성, 입자→격자 농도 누적, 시간 평균, 다중 종 관리
    - 2D 침적량 격자
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_
  - [x] 12.3 농도 격자 속성 테스트 작성 (`tests/property/test_concentration_props.py`)
    - **Property 24: 농도 질량 보존** — Σ(C·V) = Σm_active
    - **Validates: Requirements 9.2**
    - **Property 25: 다중 종 격자 독립성** — 종 A 입자가 종 B 격자에 영향 없음
    - **Validates: Requirements 9.5**

- [x] 13. 출력 모듈 구현
  - [x] 13.1 TdumpWriter/CdumpWriter/CSVWriter/NetCDFWriter 구현 (`pyhysplit/output_writer.py`)
    - tdump 텍스트 포맷 출력 (헤더 + 데이터, 진단 변수 포함)
    - tdump 파싱 (역방향 읽기)
    - cdump 바이너리 포맷 출력
    - CSV/NetCDF 출력
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_
  - [x] 13.2 출력 모듈 속성 테스트 작성 (`tests/property/test_output_props.py`)
    - **Property 28: tdump Round Trip** — write → read = 원본
    - **Validates: Requirements 12.1, 12.4, 12.5**

- [x] 14. Checkpoint — 입출력 모듈 검증
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. 엔진 통합 및 Forward/Backward 궤적
  - [x] 15.1 TrajectoryEngine 메인 클래스 구현 (`pyhysplit/engine.py`)
    - 모든 컴포넌트 조립: ConfigParser → MetReader → Interpolator → Integrator → BoundaryHandler → ParticleManager → OutputWriter
    - 메인 시뮬레이션 루프: Δt 계산 → 보간 → 난류 → Heun 적분 → 경계 처리 → 침적 → 상태 갱신 → 출력
    - Forward/Backward 모드: dt 부호 반전 방식
    - 다중 시작점 독립 계산
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 2.1-2.6_
  - [x] 15.2 Forward/Backward 속성 테스트 작성 (`tests/property/test_direction_props.py`)
    - **Property 8: Forward/Backward 방향 부호** — forward dt>0, backward dt<0
    - **Validates: Requirements 4.1, 4.2**
    - **Property 9: Forward-Backward Round Trip** — 균일 풍속에서 원점 복귀
    - **Validates: Requirements 4.3**
    - **Property 10: 다중 시작점 독립성** — 시작점 추가/제거 시 기존 궤적 불변
    - **Validates: Requirements 4.5**
  - [x] 15.3 검증 결정론적 재현성 테스트 (`tests/property/test_verification_props.py`)
    - **Property 33: 결정론적 재현성** — 동일 입력 → 동일 궤적 (난류 off)
    - **Validates: Requirements 16.2**

- [x] 16. Checkpoint — 엔진 통합 검증
  - Ensure all tests pass, ask the user if questions arise.

- [x] 17. 병렬 처리 구현
  - [x] 17.1 ParallelExecutor 클래스 구현 (`pyhysplit/parallel.py`)
    - `run_trajectories_parallel`: multiprocessing Pool 기반 입자 병렬 계산
    - `load_met_files_parallel`: ThreadPoolExecutor 기반 I/O 병렬화
    - `setup_shared_memory`: 기상 데이터 shared memory 배치
    - 워커 수 설정 인터페이스 (기본값: os.cpu_count())
    - 입자 배치 균등 분할 및 결과 병합
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_
  - [x] 17.2 병렬 처리 속성 테스트 작성 (`tests/property/test_parallel_props.py`)
    - **Property 31: 병렬/순차 결과 동일성** — 병렬 결과 = 순차 결과
    - **Validates: Requirements 14.1, 14.5**

- [x] 18. GPU 가속 구현
  - [x] 18.1 ComputeBackend 추상 클래스 및 NumpyBackend 구현 (`pyhysplit/gpu_backend.py`)
    - `trilinear_batch`: 벡터화된 N개 입자 동시 보간
    - `heun_step_batch`: 벡터화된 N개 입자 동시 Heun 적분
    - _Requirements: 15.3_
  - [x] 18.2 CuPyBackend 및 NumbaGPUBackend 구현 (`pyhysplit/gpu_backend.py`)
    - CuPy GPU 배열 연산 기반 보간/적분
    - Numba CUDA 커널 기반 보간/적분
    - GPU 메모리 배치 분할 처리
    - `get_backend` 팩토리: GPU 사용 가능 시 자동 선택, 불가 시 CPU 폴백
    - _Requirements: 15.1, 15.2, 15.3, 15.4_
  - [x] 18.3 GPU/CPU 동등성 속성 테스트 작성 (`tests/property/test_parallel_props.py`)
    - **Property 32: GPU/CPU 결과 동등성** — GPU 결과 ≈ CPU 결과 (1e-6 이내)
    - **Validates: Requirements 15.1, 15.2, 15.5**

- [x] 19. Checkpoint — 성능 계층 검증
  - Ensure all tests pass, ask the user if questions arise.

- [x] 20. 검증 및 클러스터 분석 구현
  - [x] 20.1 Verifier 클래스 구현 (`pyhysplit/verification.py`)
    - tdump 파일 로드, geodesic 거리 오차 계산, 요약 통계(평균/최대/RMSE)
    - 지도 시각화 (matplotlib/cartopy), 비교 오버레이
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_
  - [x] 20.2 TrajectoryClusterAnalysis 클래스 구현 (`pyhysplit/cluster_analysis.py`)
    - SPVAR 거리 행렬 계산, Ward 클러스터링, TSV 기반 최적 클러스터 수, 평균 궤적
    - _Requirements: 18.1, 18.2, 18.3, 18.4_
  - [x] 20.3 클러스터 분석 속성 테스트 작성 (`tests/property/test_cluster_props.py`)
    - **Property 36: 거리 행렬 대칭성** — 대칭 + 대각 0
    - **Validates: Requirements 18.1**
    - **Property 37: 클러스터 평균 중심성** — 평균 궤적 = 소속 궤적 산술 평균
    - **Validates: Requirements 18.4**

- [x] 21. 엔진-ParallelExecutor-GPU 통합 와이어링
  - [x] 21.1 TrajectoryEngine에 병렬/GPU 백엔드 통합
    - 엔진 초기화 시 ComputeBackend 선택 (GPU/CPU)
    - ParallelExecutor를 통한 다중 입자 병렬 실행
    - 기상 파일 병렬 로딩 통합
    - _Requirements: 14.1-14.5, 15.1-15.5_
  - [x] 21.2 통합 테스트 작성 (`tests/integration/test_full_trajectory.py`)
    - 전체 궤적 계산 end-to-end 테스트 (CONTROL 파일 → tdump 출력)
    - Forward/Backward 모드 통합 테스트
    - 다중 시작점 + 농도 격자 통합 테스트
    - _Requirements: 4.1-4.5, 9.1-9.6, 12.1-12.5_

- [x] 22. Final Checkpoint — 전체 시스템 검증
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- `*` 표시된 태스크는 선택적이며 빠른 MVP를 위해 건너뛸 수 있음
- 각 태스크는 특정 요구사항을 참조하여 추적 가능성 보장
- 체크포인트에서 점진적 검증 수행
- 속성 테스트는 hypothesis 라이브러리 사용, 최소 100회 반복
- 단위 테스트는 특정 예제와 엣지 케이스에 집중
