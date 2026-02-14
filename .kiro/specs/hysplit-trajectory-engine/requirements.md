# 요구사항 문서

## 소개

HYSPLIT(Hybrid Single-Particle Lagrangian Integrated Trajectory)은 NOAA ARL에서 개발한 대기 수송 및 확산 모델링 시스템이다. 본 프로젝트는 HYSPLIT의 궤적(trajectory) 및 확산(dispersion) 계산 알고리즘을 Python으로 완전히 동일하게 재구현하여, 멀티프로세싱/멀티쓰레딩/GPU 가속을 지원하는 상용 소프트웨어를 개발하는 것을 목표로 한다.

핵심 참고 문헌:
- Stein, A.F. et al. (2015) "NOAA's HYSPLIT Atmospheric Transport and Dispersion Modeling System", BAMS (DOI: 10.1175/BAMS-D-14-00110.1)
- Draxler, R.R. & Hess, G.D. (1998) "An overview of the HYSPLIT_4 modeling system for trajectories, dispersion, and deposition"
- Draxler, R.R. (1999) "HYSPLIT-4 User's Guide", NOAA Technical Memorandum
- Rolph, G. et al. (2017) "The NOAA HYSPLIT model and the READY system"

## 용어 정의

- **Trajectory_Engine**: 궤적 및 확산 계산을 수행하는 핵심 엔진 시스템
- **Interpolator**: 4차원(x, y, z, t) 풍속장 보간을 수행하는 모듈
- **Integrator**: Heun(Modified Euler) 방식의 시간 적분을 수행하는 모듈
- **Met_Reader**: 기상 데이터를 읽고 내부 배열 구조로 변환하는 모듈
- **Particle_Manager**: 다중 입자의 생성, 추적, 상태 관리를 담당하는 모듈
- **Concentration_Grid**: 3차원 농도 격자를 정의하고 농도를 계산하는 모듈
- **Config_Parser**: HYSPLIT CONTROL/SETUP.CFG 파일을 파싱하는 모듈
- **Output_Writer**: tdump, cdump 등 HYSPLIT 호환 출력 포맷을 생성하는 모듈
- **Deposition_Module**: 건조/습윤 침적 과정을 계산하는 모듈
- **Turbulence_Module**: 대기경계층 기반 난류 확산을 계산하는 모듈
- **Coordinate_Converter**: sigma, pressure, height, hybrid 좌표계 간 변환을 수행하는 모듈
- **ARL_Format**: NOAA ARL에서 사용하는 packed binary 기상 데이터 포맷. 인덱스 레코드 + 레벨별 변수 데이터로 구성
- **Heun_Method**: Predictor-Corrector 2단계 적분 방식 (Modified Euler). RK4가 아님에 주의
- **Trilinear_Interpolation**: x → y → z 순서의 3차원 선형 보간. 순서가 바뀌면 결과가 달라짐
- **PBL**: Planetary Boundary Layer, 대기경계층
- **Kz**: 수직 난류 확산 계수 (m²/s)
- **tdump**: HYSPLIT 궤적 출력 텍스트 포맷
- **cdump**: HYSPLIT 농도 출력 바이너리 포맷
- **CONTROL_File**: HYSPLIT 실행 설정 파일. 시작점, 시간, 기상파일 경로 등 정의
- **SETUP_CFG**: HYSPLIT 고급 설정 namelist 파일. 난류, 침적, 농도 격자 등 상세 파라미터 정의
- **Lagrangian_Framework**: 입자를 따라가며 물리량을 계산하는 프레임워크. Eulerian(격자 고정)과 대비
- **CFL_Condition**: Courant-Friedrichs-Lewy 조건. Δt ≤ Δx/V로 수치 안정성 보장
- **Mixed_Layer_Depth**: 대기경계층 내 혼합층 깊이. 난류 파라미터화의 핵심 입력
- **Monin_Obukhov_Length**: 대기 안정도를 나타내는 스케일 길이. 양수=안정, 음수=불안정
- **Scavenging_Coefficient**: 강수에 의한 오염물질 제거 계수 (s⁻¹)

## 요구사항

### 요구사항 1: 4차원 풍속장 보간 (Stein et al. 2015, Section 2a; Draxler 1999, Chapter 3)

**사용자 스토리:** 개발자로서, HYSPLIT과 동일한 순서(x → y → z → t)로 풍속장을 보간하여, 임의의 3차원 위치와 시간에서 정확한 풍속 벡터를 얻고 싶다.

HYSPLIT은 기상장 보간 시 반드시 x(경도) → y(위도) → z(고도) → t(시간) 순서를 따른다. 이 순서는 Draxler(1999) User's Guide에 명시되어 있으며, 순서를 변경하면 수치적으로 다른 결과가 산출된다. 보간은 인접 격자점 8개(3D)를 사용하는 trilinear 방식이며, 시간 방향은 두 시간 스냅샷의 공간 보간 결과를 선형 보간한다.

#### 수용 기준

1. WHEN 3차원 위치(lon, lat, z)와 시간(t)이 주어지면, THE Interpolator SHALL x(경도) → y(위도) → z(고도) → t(시간) 순서로 trilinear + temporal 보간을 수행하여 풍속 벡터(u, v, w)를 반환한다
2. WHEN 보간 대상 위치가 격자점 사이에 있으면, THE Interpolator SHALL 인접한 8개 격자점(3D)의 값을 사용하여 각 축 방향의 분수 거리(fractional distance)를 계산하고 선형 보간을 수행한다
3. WHEN 시간 보간을 수행하면, THE Interpolator SHALL 먼저 두 시간 스냅샷(t_n, t_n+1) 각각에서 공간 보간을 완료한 후, 그 결과를 시간 분수 거리 (t - t_n)/(t_n+1 - t_n)로 선형 보간한다
4. IF 보간 대상 위치가 격자 범위 밖에 있으면, THEN THE Interpolator SHALL 경계 초과 오류를 반환하고 해당 입자를 비활성화한다
5. THE Interpolator SHALL u(동서 바람), v(남북 바람), w(수직 속도) 외에도 온도(T), 상대습도(RH), 기압(P), 지오포텐셜 높이(HGT) 등 추가 기상 변수에 대해서도 동일한 보간을 수행한다
6. WHEN 격자 간격이 불균일(non-uniform)하면, THE Interpolator SHALL 각 축의 실제 격자 간격을 사용하여 분수 거리를 계산한다

### 요구사항 2: Heun(Modified Euler) 시간 적분 (Stein et al. 2015, Section 2a; Draxler & Hess 1998)

**사용자 스토리:** 개발자로서, HYSPLIT과 동일한 Heun 방식의 Predictor-Corrector 적분을 사용하여, 입자의 위치를 시간에 따라 정확하게 갱신하고 싶다.

HYSPLIT의 궤적 적분은 2단계 Heun(Modified Euler) 방식을 사용한다. 이는 RK4(4차 Runge-Kutta)가 아니며, Stein et al.(2015)과 Draxler & Hess(1998)에 명시적으로 기술되어 있다. 수식: P(t+Δt) = P(t) + 0.5·[V(P(t), t) + V(P'(t+Δt), t+Δt)]·Δt, 여기서 P'는 Predictor 단계의 예측 위치이다.

#### 수용 기준

1. WHEN 현재 위치 P(t)와 시간 t가 주어지면, THE Integrator SHALL 현재 위치에서 풍속 V1 = V(P, t)을 보간하고, 예측 위치 P' = P + V1·Δt를 계산한다 (Predictor 단계)
2. WHEN Predictor 단계가 완료되면, THE Integrator SHALL 예측 위치 P'에서 풍속 V2 = V(P', t+Δt)를 보간하고, 최종 위치 P(t+Δt) = P + 0.5·(V1+V2)·Δt를 계산한다 (Corrector 단계)
3. WHEN 수평 이동(advection)을 계산하면, THE Integrator SHALL 지구 반경(EARTH_RADIUS = 6,371,000m) 기반으로 다음 공식을 적용한다: Δlat = (v·Δt)/R, Δlon = (u·Δt)/(R·cos(lat))
4. WHEN 경도 변환을 수행하면, THE Integrator SHALL cos(latitude) 보정을 적용하여 위도에 따른 경도 간격 차이를 반영한다
5. THE Integrator SHALL Predictor와 Corrector 단계 모두에서 동일한 보간 방식(요구사항 1)을 사용한다
6. WHEN 난류 확산이 활성화되면, THE Integrator SHALL Predictor 단계와 Corrector 단계 각각에서 독립적인 난류 속도 섭동을 추가한다

### 요구사항 3: 적응형 시간 간격(Δt) 제어 (Draxler 1999, Chapter 2; Rolph et al. 2017)

**사용자 스토리:** 개발자로서, 풍속과 격자 간격에 따라 Δt를 자동으로 조절하여, CFL 조건을 만족시키고 수치 불안정성을 방지하고 싶다.

HYSPLIT은 CFL(Courant-Friedrichs-Lewy) 조건에 기반하여 Δt를 자동 조절한다. 입자가 한 시간 스텝에 하나의 격자 셀을 넘지 않도록 Δt ≤ Δx/|V|를 보장한다. Draxler(1999)에 따르면 시간 스텝은 기상자료 시간 간격의 경계에서도 클리핑된다.

#### 수용 기준

1. THE Trajectory_Engine SHALL Δt를 min(Δx/|u|, Δy/|v|) 공식으로 계산하여 수평 방향 각각에 대해 CFL 조건을 만족시킨다
2. WHEN 풍속이 매우 작으면(|V| < 0.001 m/s), THE Trajectory_Engine SHALL 최소 풍속 임계값(0.001 m/s)을 적용하여 Δt가 무한대가 되는 것을 방지한다
3. THE Trajectory_Engine SHALL Δt가 사용자 지정 최대값(기본값: 3600초)을 초과하지 않도록 상한을 적용한다
4. WHEN Δt가 기상자료 시간 간격 경계(예: 3시간 간격의 GDAS)를 넘으면, THE Trajectory_Engine SHALL 해당 경계까지만 적분하고 다음 시간 간격에서 새로운 Δt를 계산하여 계속 진행한다
5. WHEN 출력 시간 간격이 지정되면, THE Trajectory_Engine SHALL 출력 시점에 정확히 도달하도록 마지막 Δt를 조정한다
6. THE Trajectory_Engine SHALL 수직 방향에 대해서도 Δz/|w| 기준으로 Δt를 제한하여 수직 CFL 조건을 만족시킨다

### 요구사항 4: Forward/Backward 궤적 계산 (Stein et al. 2015, Section 2; Draxler 1999, Chapter 4)

**사용자 스토리:** 사용자로서, 동일한 시작점에서 전방(forward) 및 후방(backward) 궤적을 모두 계산하여, 대기 오염원 추적 및 영향 범위 분석을 수행하고 싶다.

HYSPLIT에서 backward trajectory는 단순히 배열을 반전시키는 것이 아니라, dt의 부호를 반전시켜 시간을 역행한다. Stein et al.(2015)에 따르면 forward와 backward는 동일한 적분 알고리즘을 사용하되 시간 진행 방향만 다르다.

#### 수용 기준

1. WHEN forward 모드가 선택되면, THE Trajectory_Engine SHALL 양의 Δt를 사용하여 시간 순방향으로 궤적을 계산한다
2. WHEN backward 모드가 선택되면, THE Trajectory_Engine SHALL 음의 Δt를 사용하여 시간 역방향으로 궤적을 계산하되, 보간 시 시간 분수 거리 계산에서 역방향을 올바르게 처리한다
3. WHEN backward 궤적을 계산하면, THE Trajectory_Engine SHALL 단순 배열 반전이 아닌 dt 부호 반전 방식으로 시간 역행을 처리하여, Predictor-Corrector 단계에서 t-|Δt| 시점의 풍속을 사용한다
4. THE Trajectory_Engine SHALL forward와 backward 모드에서 동일한 Heun 적분 알고리즘과 보간 방식을 사용한다
5. WHEN 다중 시작점이 지정되면, THE Trajectory_Engine SHALL 각 시작점에서 독립적으로 forward 또는 backward 궤적을 계산한다

### 요구사항 5: 기상 데이터 입력 (Draxler 1999, Chapter 5; Stein et al. 2015, Section 2b)

**사용자 스토리:** 사용자로서, GDAS, GFS, ERA5, WRF 등 다양한 기상 데이터 소스를 사용하여 궤적을 계산하고 싶다.

HYSPLIT은 자체 ARL packed binary 포맷을 기본으로 사용하며, NOAA READY 시스템에서 제공하는 기상 데이터는 이 포맷이다. ARL 포맷은 인덱스 레코드 헤더 + 레벨별 변수 데이터로 구성되며, 각 레코드는 50-byte 헤더를 가진다. Draxler(1999)에 ARL 포맷의 상세 구조가 기술되어 있다.

#### 수용 기준

1. THE Met_Reader SHALL NOAA ARL packed binary 포맷의 기상 데이터를 직접 읽어 내부 배열 구조(t, z, lat, lon)로 변환한다
2. WHEN ARL 포맷을 읽으면, THE Met_Reader SHALL 50-byte 레코드 헤더를 파싱하여 변수명, 레벨, 시간 정보를 추출하고, 패킹된 데이터를 언패킹한다
3. THE Met_Reader SHALL NetCDF 포맷의 GDAS/GFS 기상 데이터를 읽어 내부 배열 구조로 변환한다
4. WHEN 기상 데이터의 수직 속도(w)가 Pa/s 단위이면, THE Met_Reader SHALL 정수압 근사(w_m/s = -w_Pa/s · Rd · T / (g · p), Rd=287.05 J/(kg·K), g=9.80665 m/s²)를 사용하여 m/s 단위로 변환한다
5. WHEN 여러 시간대의 기상 파일이 제공되면, THE Met_Reader SHALL 파일들을 시간 순서로 연결하여 연속적인 기상장을 구성하고, 파일 경계에서의 시간 보간을 지원한다
6. THE Met_Reader SHALL GDAS(1°/0.5°), GFS, ERA5, NAM, WRF 데이터 소스 각각에 대해 변수명 매핑 테이블을 제공하고 좌표계 변환을 수행한다
7. THE Met_Reader SHALL 기상 데이터의 메타데이터(격자 해상도, 시간 간격, 변수 목록, 좌표계 유형)를 추출하여 엔진에 전달한다
8. WHEN 기상 데이터에 누락된 값(missing value)이 있으면, THE Met_Reader SHALL 누락 영역을 식별하고 해당 격자점을 보간에서 제외한다

### 요구사항 6: 수직 좌표계 변환 (Draxler & Hess 1998; Draxler 1999, Chapter 3)

**사용자 스토리:** 개발자로서, sigma, pressure, height, hybrid 좌표계 간 정확한 변환을 수행하여, 다양한 기상 데이터의 수직 좌표를 통일적으로 처리하고 싶다.

HYSPLIT은 내부적으로 terrain-following sigma 좌표계를 사용하며, 입력 데이터의 좌표계에 따라 변환을 수행한다. Draxler & Hess(1998)에 따르면 수직 좌표 변환은 궤적 정확도에 큰 영향을 미치며, 특히 지형이 복잡한 지역에서 중요하다.

#### 수용 기준

1. WHEN sigma 좌표계 데이터가 입력되면, THE Coordinate_Converter SHALL σ = (P - P_top)/(P_sfc - P_top) 공식을 사용하여 pressure 좌표로 변환한다
2. WHEN pressure 좌표를 height로 변환하면, THE Coordinate_Converter SHALL 기상장의 지오포텐셜 높이(HGT) 변수가 있으면 이를 사용하고, 없으면 표준 대기 근사(Z = -H·ln(P/P0), H=scale height)를 적용한다
3. WHEN hybrid 좌표계(sigma-pressure) 데이터가 입력되면, THE Coordinate_Converter SHALL P = A(k) + B(k)·P_sfc 공식으로 각 레벨의 기압을 계산한다
4. THE Coordinate_Converter SHALL terrain-following 좌표에서 지형 높이(terrain height)를 고려하여 해수면 기준 실제 고도(ASL)를 계산한다
5. THE Coordinate_Converter SHALL 내부 수직 좌표계를 사용자가 선택할 수 있도록 하며(pressure 기반 또는 height 기반), 선택에 따라 수직 속도 단위를 자동 변환한다

### 요구사항 7: 난류 확산 모델링 (Stein et al. 2015, Section 2c; Draxler & Hess 1998)

**사용자 스토리:** 개발자로서, 대기경계층 특성을 반영한 난류 확산을 모델링하여, 입자의 확산 거동을 현실적으로 시뮬레이션하고 싶다.

HYSPLIT의 난류 확산은 Lagrangian 입자 분산 모델에 기반한다. Stein et al.(2015)에 따르면 수직 확산은 대기경계층(PBL) 높이와 안정도에 따라 파라미터화되며, 수평 확산은 격자 해상도에 비례하는 확산 계수를 사용한다. 대류 경계층(CBL)과 안정 경계층(SBL)에서 서로 다른 파라미터화를 적용한다.

#### 수용 기준

1. THE Turbulence_Module SHALL 대기경계층(PBL) 높이를 기상 데이터에서 읽거나, 리처드슨 수(Richardson number) 방법으로 진단하여 결정한다
2. THE Turbulence_Module SHALL PBL 높이와 마찰 속도(u*), Monin-Obukhov 길이(L)를 기반으로 수직 확산 계수(Kz) 프로파일을 계산한다
3. WHEN Monin-Obukhov 길이(L)가 음수(불안정 대기)이면, THE Turbulence_Module SHALL 대류 혼합 파라미터화를 적용하여 대류 속도 스케일(w*)을 계산하고 이를 난류 속도 분산에 반영한다
4. WHEN Monin-Obukhov 길이(L)가 양수(안정 대기)이면, THE Turbulence_Module SHALL 안정도 함수 기반 파라미터화를 적용하여 억제된 난류 확산을 계산한다
5. THE Turbulence_Module SHALL 수평 확산 계수(Kh)를 격자 해상도에 비례하여 계산한다 (Kh ∝ Δx^(4/3), 리처드슨 확산 법칙)
6. THE Turbulence_Module SHALL 수평 및 수직 방향의 난류 속도 섭동을 σ_u = sqrt(2·Kh/Δt), σ_w = sqrt(2·Kz/Δt) 공식으로 계산하고 Gaussian 분포에서 샘플링하여 풍속에 추가한다
7. WHEN 난류 확산이 비활성화되면(σ=0), THE Turbulence_Module SHALL 풍속 섭동 없이 순수 이류(advection)만 수행한다
8. THE Turbulence_Module SHALL PBL 상부(자유 대기)에서는 배경 확산 계수만 적용한다

### 요구사항 8: 건조/습윤 침적 (Stein et al. 2015, Section 2d; Draxler & Hess 1998)

**사용자 스토리:** 사용자로서, 입자의 건조 침적과 습윤 침적을 모델링하여, 지표면에 도달하는 물질의 양을 정량적으로 계산하고 싶다.

HYSPLIT의 침적 모델은 Stein et al.(2015) Section 2d에 기술되어 있다. 건조 침적은 저항 모델(resistance model)을 사용하며, 습윤 침적은 강수율에 비례하는 scavenging coefficient를 사용한다. 입자의 크기와 밀도에 따라 중력 침강(gravitational settling)도 고려한다.

#### 수용 기준

1. THE Deposition_Module SHALL 입자 직경(d)과 밀도(ρ)를 기반으로 Stokes 법칙에 따른 중력 침강 속도(v_g = ρ·d²·g/(18·μ))를 계산한다
2. THE Deposition_Module SHALL 공기역학적 저항(r_a), 준층류 저항(r_b), 표면 저항(r_s)의 3-저항 모델을 사용하여 건조 침적 속도(v_d = 1/(r_a + r_b + r_s) + v_g)를 계산한다
3. WHEN 강수 데이터가 제공되면, THE Deposition_Module SHALL below-cloud scavenging 계수(Λ = a·P^b, P=강수율 mm/h, a,b는 입자 크기 의존 상수)를 계산한다
4. WHEN 입자가 구름 내부(cloud base ~ cloud top)에 위치하면, THE Deposition_Module SHALL in-cloud scavenging 비율을 적용한다
5. THE Deposition_Module SHALL 각 시간 스텝에서 입자 질량을 m(t+Δt) = m(t)·exp(-(v_d/Δz + Λ)·Δt) 공식으로 감소시킨다
6. WHEN 침적에 의해 입자 질량이 초기 질량의 1% 이하가 되면, THE Deposition_Module SHALL 해당 입자를 비활성화하고 침적 위치, 시간, 누적 침적량을 기록한다
7. THE Deposition_Module SHALL 가스상(gaseous) 물질에 대해서는 Henry 법칙 상수를 사용한 건조 침적 속도를 별도로 계산한다

### 요구사항 9: 농도 격자 계산 (Stein et al. 2015, Section 2e)

**사용자 스토리:** 사용자로서, 3차원 농도 격자를 정의하고 입자 분포로부터 농도를 계산하여, 오염물질의 공간 분포를 분석하고 싶다.

HYSPLIT의 농도 계산은 Lagrangian 입자의 위치와 질량을 Eulerian 격자에 매핑하는 방식이다. Stein et al.(2015) Section 2e에 따르면 각 입자의 질량을 해당 격자 셀의 부피로 나누어 농도를 계산하며, 시간 평균 농도를 출력한다.

#### 수용 기준

1. WHEN 농도 격자 파라미터(중심 위치, 범위, 수평 해상도, 수직 레벨)가 정의되면, THE Concentration_Grid SHALL 3차원 격자를 생성한다
2. THE Concentration_Grid SHALL 각 입자의 위치와 질량을 기반으로 해당 격자 셀에 농도(C = Σm_i / V_cell)를 누적한다
3. WHEN 출력 시간 간격(averaging period)이 도래하면, THE Concentration_Grid SHALL 해당 기간 동안의 시간 평균 농도를 계산하여 출력한다
4. THE Concentration_Grid SHALL cdump 바이너리 포맷으로 농도 데이터를 출력한다
5. THE Concentration_Grid SHALL 다중 오염 종(species)에 대해 독립적인 농도 격자를 관리한다
6. THE Concentration_Grid SHALL 지표면 침적량(deposition)을 별도의 2차원 격자로 누적하여 출력한다

### 요구사항 10: 다중 입자 관리 (Stein et al. 2015, Section 2b)

**사용자 스토리:** 사용자로서, 수천~수만 개의 입자를 동시에 추적하여, 대규모 확산 시뮬레이션을 수행하고 싶다.

HYSPLIT의 확산 모드는 다수의 Lagrangian 입자를 방출하고 추적한다. Stein et al.(2015)에 따르면 입자는 점 소스, 선 소스, 면 소스에서 방출될 수 있으며, 연속 방출(continuous emission)과 순간 방출(instantaneous release)을 모두 지원한다.

#### 수용 기준

1. THE Particle_Manager SHALL 다중 시작점, 시작 시간, 시작 고도에서 입자를 생성하며, 각 시작점에서 방출되는 입자 수를 설정할 수 있다
2. THE Particle_Manager SHALL 각 입자의 위치(lon, lat, z), 시간, 질량, 나이(age), 활성 상태를 관리한다
3. WHEN 입자가 격자 범위를 벗어나거나 질량이 소진되거나 최대 나이를 초과하면, THE Particle_Manager SHALL 해당 입자를 비활성화하고 더 이상 계산하지 않는다
4. THE Particle_Manager SHALL 지정된 시간 간격마다 새로운 입자를 방출(emission)하는 연속 방출 모드를 지원한다
5. THE Particle_Manager SHALL 각 입자에 오염 종(species) 정보와 방출률(emission rate)을 할당한다
6. THE Particle_Manager SHALL 입자 상태를 구조화된 배열(structured array 또는 dataclass 배열)로 관리하여 벡터화 연산을 지원한다

### 요구사항 11: HYSPLIT 설정 파일 호환 (Draxler 1999, Chapter 1, Appendix)

**사용자 스토리:** 사용자로서, 기존 HYSPLIT CONTROL 및 SETUP.CFG 파일을 그대로 사용하여, 기존 워크플로우를 변경 없이 활용하고 싶다.

HYSPLIT CONTROL 파일은 고정 형식의 텍스트 파일로, 시작 시간, 시작 위치 수, 각 위치의 좌표/고도, 시뮬레이션 시간, 기상 파일 수/경로, 출력 설정 등을 순서대로 기술한다. SETUP.CFG는 Fortran namelist 형식으로 고급 파라미터를 설정한다.

#### 수용 기준

1. WHEN HYSPLIT CONTROL 파일이 제공되면, THE Config_Parser SHALL 시작 시간(YY MM DD HH), 시작 위치 수, 각 위치의 위도/경도/고도, 시뮬레이션 총 시간, 수직 운동 방식, 모델 상한 고도, 기상 파일 수/디렉토리/파일명, 출력 격자 수/설정을 순서대로 파싱한다
2. WHEN HYSPLIT SETUP.CFG(namelist) 파일이 제공되면, THE Config_Parser SHALL &SETUP 블록 내의 키=값 쌍을 파싱하여 난류(KMIXD, KMIX0), 침적(DRYDEP, WETDEP), 농도 격자(NUMPAR, MAXPAR) 등 파라미터를 추출한다
3. IF CONTROL 파일에 필수 항목이 누락되거나 형식이 올바르지 않으면, THEN THE Config_Parser SHALL 누락/오류 항목의 줄 번호와 기대 형식을 명시하는 오류 메시지를 반환한다
4. THE Config_Parser SHALL 파싱된 설정을 Python dataclass로 변환하여 엔진에 전달한다
5. THE Config_Parser SHALL CONTROL 파일과 SETUP.CFG 파일을 Python 설정 객체로부터 역으로 생성(write)하는 기능을 제공한다

### 요구사항 12: 출력 포맷 호환 (Draxler 1999, Chapter 6)

**사용자 스토리:** 사용자로서, HYSPLIT과 동일한 출력 포맷(tdump, cdump)을 생성하여, 기존 HYSPLIT 후처리 및 시각화 도구를 그대로 사용하고 싶다.

HYSPLIT의 tdump 포맷은 헤더(기상 파일 정보, 시작점 정보) + 데이터 행(궤적 번호, 격자 번호, 연/월/일/시/분, 예보 시간, 위도, 경도, 고도, 기압 등)으로 구성된 고정 폭 텍스트 파일이다. cdump는 바이너리 포맷으로 농도 격자 데이터를 저장한다.

#### 수용 기준

1. THE Output_Writer SHALL 궤적 결과를 HYSPLIT tdump 텍스트 포맷으로 출력하되, 헤더 섹션(기상 그리드 수, 모델명, 시작점 수/좌표)과 데이터 섹션(궤적 번호, 시간, 위도, 경도, 고도)을 HYSPLIT 원본과 동일한 컬럼 형식으로 작성한다
2. THE Output_Writer SHALL 농도 결과를 HYSPLIT cdump 바이너리 포맷으로 출력한다
3. THE Output_Writer SHALL 궤적 결과를 CSV 및 NetCDF 포맷으로도 출력한다
4. WHEN tdump 포맷으로 출력하면, THE Output_Writer SHALL 각 궤적 지점에서의 기상 변수(기압, 온도, 강수, 혼합층 높이 등)를 진단 변수로 포함한다
5. THE Output_Writer SHALL tdump 파일을 읽어 Python 객체로 파싱하는 역방향 기능도 제공한다

### 요구사항 13: 경계 처리 (Draxler 1999, Chapter 2)

**사용자 스토리:** 개발자로서, 입자가 격자 경계, 지표면, 날짜변경선 등을 만났을 때 HYSPLIT과 동일하게 처리하여, 물리적으로 타당한 궤적을 보장하고 싶다.

HYSPLIT은 수직 경계에서 반사(reflection) 방식을 사용하며, 수평 경계에서는 입자를 비활성화한다. Draxler(1999)에 따르면 지표면 반사는 입자가 지면 아래로 내려갈 때 초과 거리만큼 위로 반사시키는 방식이다.

#### 수용 기준

1. WHEN 입자의 고도가 지표면(지형 높이) 이하로 내려가면, THE Trajectory_Engine SHALL 초과 거리만큼 지표면 위로 반사(z_new = z_sfc + |z_calc - z_sfc|)시킨다
2. WHEN 입자의 고도가 모델 상한(CONTROL 파일에서 지정)을 초과하면, THE Trajectory_Engine SHALL 입자를 모델 상한 높이로 반사시킨다
3. WHEN 입자가 경도 180°를 넘으면, THE Trajectory_Engine SHALL 날짜변경선 통과를 처리하여 -180° ~ 180° 범위를 유지한다 (예: 181° → -179°)
4. WHEN 입자가 기상 데이터 수평 격자 범위를 벗어나면, THE Trajectory_Engine SHALL 해당 입자를 비활성화하고 마지막 유효 위치를 기록한다
5. WHEN 입자가 극지방(위도 ±90°)에 접근하면, THE Trajectory_Engine SHALL 극점 통과 시 경도를 180° 반전시키고 위도를 반사시킨다

### 요구사항 14: 멀티프로세싱/멀티쓰레딩 병렬 처리

**사용자 스토리:** 사용자로서, 다중 CPU 코어를 활용하여 대규모 입자 앙상블 계산을 병렬로 수행하여, 계산 시간을 단축하고 싶다.

#### 수용 기준

1. THE Trajectory_Engine SHALL 다중 입자의 궤적 계산을 Python multiprocessing Pool을 사용하여 CPU 코어 수에 비례하게 병렬 처리한다
2. THE Trajectory_Engine SHALL 기상 데이터 I/O 작업(다중 파일 읽기, 전처리)을 concurrent.futures.ThreadPoolExecutor로 병렬화한다
3. WHEN 병렬 처리 시 기상 데이터를 공유하면, THE Trajectory_Engine SHALL multiprocessing.shared_memory를 사용하여 기상 배열의 메모리 중복을 방지한다
4. THE Trajectory_Engine SHALL 사용자가 병렬 워커 수를 설정할 수 있는 인터페이스를 제공하며, 기본값은 os.cpu_count()로 설정한다
5. THE Trajectory_Engine SHALL 입자 배치를 워커 수에 맞게 균등 분할하고, 각 워커의 결과를 시간 순서대로 병합한다

### 요구사항 15: GPU 가속

**사용자 스토리:** 사용자로서, GPU를 활용하여 수만 개 입자의 보간 및 적분 연산을 가속하여, 대규모 확산 시뮬레이션의 성능을 극대화하고 싶다.

#### 수용 기준

1. WHEN GPU가 사용 가능하면, THE Trajectory_Engine SHALL CuPy를 사용하여 풍속장 보간 연산(trilinear + temporal)을 GPU 배열 연산으로 수행한다
2. WHEN GPU가 사용 가능하면, THE Trajectory_Engine SHALL Numba CUDA 커널을 사용하여 다중 입자의 Heun 적분을 GPU에서 병렬 실행한다
3. IF GPU가 사용 불가능하면, THEN THE Trajectory_Engine SHALL 자동으로 CPU 기반 NumPy 연산으로 폴백(fallback)하며, 사용자에게 경고 메시지를 출력한다
4. THE Trajectory_Engine SHALL GPU 메모리 한계를 고려하여 입자 배치를 GPU 메모리 크기에 맞게 분할 처리한다
5. THE Trajectory_Engine SHALL GPU 연산과 CPU 연산의 결과가 부동소수점 허용 오차(1e-6) 이내에서 동일함을 보장한다

### 요구사항 16: 검증 및 시각화

**사용자 스토리:** 사용자로서, Python 궤적 결과를 HYSPLIT 원본 결과와 비교 검증하고 시각화하여, 구현의 정확성을 확인하고 싶다.

#### 수용 기준

1. THE Trajectory_Engine SHALL HYSPLIT tdump 출력 파일을 파싱하여 Python 궤적과 지점별 수평 거리 오차(geodesic distance)를 계산한다
2. WHEN 검증 모드가 활성화되면, THE Trajectory_Engine SHALL 난류 확산을 비활성화하고 결정론적(deterministic) 궤적만 계산하여 HYSPLIT 원본과 직접 비교 가능하게 한다
3. THE Trajectory_Engine SHALL 궤적을 지도 위에 시각화하는 기능을 제공하며, matplotlib/cartopy 기반으로 지도 투영을 지원한다
4. THE Trajectory_Engine SHALL HYSPLIT 궤적과 Python 궤적을 동일 지도에 오버레이하여 비교 시각화하고, 각 시간 스텝의 오차를 표시한다
5. THE Trajectory_Engine SHALL 검증 결과를 요약하는 통계(평균 오차, 최대 오차, RMSE)를 계산하여 출력한다

### 요구사항 17: 수직 운동 방식 선택 (Stein et al. 2015, Section 2a; Draxler 1999)

**사용자 스토리:** 개발자로서, HYSPLIT이 지원하는 다양한 수직 운동 방식을 선택할 수 있어, 시뮬레이션 목적에 맞는 수직 처리를 적용하고 싶다.

HYSPLIT은 CONTROL 파일에서 수직 운동 방식(KMSL)을 선택할 수 있다. 0=데이터 수직 속도 사용, 1=등밀도면, 2=등압면, 3=등온위면, 4=등고도면 등이 있다. Stein et al.(2015)에 따르면 수직 운동 방식의 선택은 궤적 결과에 상당한 영향을 미친다.

#### 수용 기준

1. WHEN 수직 운동 방식이 0(데이터 수직 속도)으로 설정되면, THE Trajectory_Engine SHALL 기상 데이터의 수직 속도(omega 또는 w)를 직접 사용하여 수직 이동을 계산한다
2. WHEN 수직 운동 방식이 1(등밀도면)로 설정되면, THE Trajectory_Engine SHALL 입자를 등밀도면 위에서 이동시킨다
3. WHEN 수직 운동 방식이 2(등압면)로 설정되면, THE Trajectory_Engine SHALL 수직 속도를 0으로 설정하여 입자를 동일 기압면에서 이동시킨다
4. WHEN 수직 운동 방식이 3(등온위면)으로 설정되면, THE Trajectory_Engine SHALL 온위(potential temperature)를 보존하며 입자를 이동시킨다
5. THE Trajectory_Engine SHALL CONTROL 파일의 수직 운동 방식 코드를 읽어 자동으로 해당 방식을 적용한다

### 요구사항 18: 다중 궤적 클러스터 분석

**사용자 스토리:** 사용자로서, 다중 backward 궤적의 클러스터 분석을 수행하여, 대기 수송 경로의 주요 패턴을 식별하고 싶다.

HYSPLIT은 다중 궤적의 클러스터 분석 기능을 내장하고 있으며, 이는 대기 오염원 추적에서 널리 사용된다.

#### 수용 기준

1. WHEN 다중 궤적 결과가 제공되면, THE Trajectory_Engine SHALL 궤적 간 공간 거리(SPVAR: spatial variance)를 계산한다
2. THE Trajectory_Engine SHALL Ward 계층적 클러스터링 알고리즘을 사용하여 궤적을 그룹화한다
3. THE Trajectory_Engine SHALL 총 공간 분산(TSV)의 변화율을 기반으로 최적 클러스터 수를 제안한다
4. THE Trajectory_Engine SHALL 클러스터별 평균 궤적과 소속 궤적 수를 출력한다
