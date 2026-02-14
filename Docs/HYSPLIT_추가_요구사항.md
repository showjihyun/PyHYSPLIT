# HYSPLIT 완전 동일 구현을 위한 추가 요구사항 분석

## 개요

HYSPLIT(Hybrid Single-Particle Lagrangian Integrated Trajectory) 모델을 Python으로 완전히 동일하게 구현하기 위해,
기존 Docs 문서에서 언급되었으나 아직 구현되지 않은 부분과 상용 소프트웨어 수준에 필요한 추가 요구사항을 분석합니다.

## 1. 기상 데이터 입출력

### 1.1 NOAA ARL 바이너리 포맷 직접 읽기
- 현재: NetCDF만 지원
- 필요: HYSPLIT 네이티브 ARL packed binary 포맷 직접 파싱
- 이유: NOAA READY 시스템에서 제공하는 기상 데이터는 ARL 포맷이 기본
- 구현 요소: 인덱스 레코드 파싱, 레벨별 변수 언패킹, 체크섬 검증

### 1.2 다중 기상 데이터 소스 지원
- GDAS (Global Data Assimilation System) - 1°, 0.5° 해상도
- GFS (Global Forecast System)
- NAM (North American Mesoscale)
- ERA5 (ECMWF Reanalysis v5)
- WRF (Weather Research and Forecasting) 출력
- 각 소스별 변수명 매핑, 좌표계 변환, 시간 해상도 처리 필요

### 1.3 다중 기상 파일 시간 연결
- 여러 시간대의 기상 파일을 자동으로 연결하여 장기 궤적 계산
- 파일 간 시간 경계에서의 보간 처리

## 2. 수치 알고리즘 정밀 구현

### 2.1 수직 좌표계 변환
- Sigma 좌표계 ↔ Pressure 좌표계 ↔ Height 좌표계
- Hybrid 좌표계 (sigma-pressure) 지원
- Terrain-following 좌표 처리
- 각 좌표계 간 정확한 변환 공식 구현

### 2.2 경계 처리 (Boundary Clipping)
- 격자 경계 밖으로 나가는 입자 처리
- 수직 경계: 지표면(0m) 이하, 모델 상한 이상 처리
- 수평 경계: 기상 데이터 격자 범위 밖 처리
- 날짜변경선(180°) 통과 처리
- 극지방 처리

### 2.3 시간 Step Clipping
- 기상자료 시간 경계에서의 정확한 처리
- Δt가 기상자료 시간 간격을 넘지 않도록 클리핑
- 출력 시간 간격에 맞춘 보간 출력

### 2.4 Backward Trajectory 정밀 부호 처리
- 단순 배열 반전이 아닌 정확한 시간 역행 처리
- dt 부호 반전 + 풍속 부호 반전의 정확한 조합
- 시간 경계 처리의 역방향 버전

## 3. 물리 과정

### 3.1 난류 확산 (Turbulent Diffusion) 고도화
- 현재: 단순 Gaussian noise (σ 파라미터)
- 필요: 대기경계층(PBL) 높이 기반 난류 파라미터화
- Kz (수직 확산 계수) 프로파일 계산
- 안정도 함수 (Monin-Obukhov 유사도 이론)
- 대류 경계층 vs 안정 경계층 구분

### 3.2 건조 침적 (Dry Deposition)
- 침적 속도 (deposition velocity) 계산
- 입자 크기별 중력 침강 (gravitational settling)
- 저항 모델 (resistance model): 공기역학적, 준층류, 표면 저항

### 3.3 습윤 침적 (Wet Deposition)
- 강수에 의한 세정 (below-cloud scavenging)
- 구름 내 세정 (in-cloud scavenging)
- 강수율 데이터 활용

### 3.4 농도 계산 (Concentration Grid)
- 궤적뿐 아니라 확산 농도 계산
- 3D 농도 격자 정의 및 계산
- 입자 질량 분배 (mass partitioning)
- 시간 평균 농도 출력

## 4. 성능 최적화

### 4.1 멀티프로세싱
- 다중 궤적/입자의 병렬 계산
- Python multiprocessing 모듈 활용
- 입자 배치 분할 및 결과 병합

### 4.2 멀티쓰레딩
- I/O 바운드 작업 (기상 데이터 읽기) 병렬화
- 보간 계산의 쓰레드 병렬화
- GIL 우회를 위한 NumPy/C 확장 활용

### 4.3 GPU 가속
- CuPy 또는 Numba CUDA를 활용한 보간 연산 가속
- 대규모 입자 앙상블의 GPU 병렬 처리
- 풍속장 보간의 GPU 커널 구현

## 5. HYSPLIT 호환성

### 5.1 CONTROL 파일 파싱
- HYSPLIT CONTROL 파일 형식 읽기/쓰기
- 시작점, 시간, 기상 파일 경로 등 설정 파싱
- 기존 HYSPLIT 워크플로우와의 호환성

### 5.2 SETUP.CFG 파일 파싱
- HYSPLIT SETUP.CFG (namelist) 파일 읽기/쓰기
- 고급 설정 파라미터 지원

### 5.3 출력 포맷 호환
- tdump 포맷: 궤적 출력 (텍스트)
- cdump 포맷: 농도 출력 (바이너리)
- HYSPLIT 시각화 도구와 호환되는 출력

## 6. 검증 및 품질 보증

### 6.1 HYSPLIT 원본과의 1:1 검증
- 동일 입력 조건에서 HYSPLIT 원본과 결과 비교
- 허용 오차 기준 정의 (수평: < 1km, 수직: < 50m for 24h trajectory)
- 자동화된 검증 테스트 스위트

### 6.2 알려진 사례 검증
- 공개된 HYSPLIT 사례 연구 재현
- 화산재 확산, 방사능 확산 등 검증 사례
