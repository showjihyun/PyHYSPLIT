# 물리 과정 구현 완료 보고서

## 개요

PySPlit에 HYSPLIT의 핵심 물리 과정 3가지를 완전히 구현했습니다:
1. **농도 계산 (Concentration Grid)** - 새로 구현 ✅
2. **건조 침적 (Dry Deposition)** - 개선 및 완성 ✅
3. **습윤 침적 (Wet Deposition)** - 개선 및 완성 ✅

## 1. 농도 계산 (Concentration Grid)

### 구현 내용

**파일**: `pyhysplit/physics/concentration.py`

HYSPLIT의 Lagrangian-Eulerian 하이브리드 접근법을 구현했습니다:
- Lagrangian 입자들의 질량을 Eulerian 격자로 분배
- 시간 평균 농도 계산
- 질량 보존 보장

### 핵심 기능

#### 1.1 ConcentrationCalculator 클래스
```python
calc = ConcentrationCalculator(
    config=grid_config,
    kernel_type="top_hat",  # or "gaussian"
    kernel_width=1.0
)
```

**주요 메서드**:
- `accumulate_particles()`: 입자 질량을 격자에 누적
- `compute_concentration()`: 최종 농도 계산 (mass/m³)
- `get_concentration_at_point()`: 임의 지점의 농도 보간
- `reset()`: 새로운 샘플링 기간을 위한 초기화

#### 1.2 질량 분배 커널

**Top-Hat 커널** (HYSPLIT 기본):
- `kernel_width=1.0`: 단일 셀에 질량 분배
- `kernel_width>1.0`: 주변 셀에 균등 분배
- 빠르고 간단한 계산

**Gaussian 커널** (고급 옵션):
- 부드러운 농도 장 생성
- 3-sigma 규칙 (99.7% 질량 포함)
- 질량 보존 보장

#### 1.3 격자 셀 부피 계산

구면 기하학을 사용한 정확한 부피 계산:
```
V = R² * cos(lat) * dlat * dlon * dz
```
- 위도에 따른 면적 변화 고려
- 수직 층 두께 고려

### 테스트 커버리지

**11개 단위 테스트** (모두 통과 ✅):
1. 격자 초기화
2. Top-hat 질량 분배
3. Gaussian 질량 분배
4. 입자 누적
5. 샘플링 기간 외 입자 무시
6. 비활성 입자 무시
7. 농도 계산
8. 셀 부피 계산
9. 리셋 기능
10. 지점 농도 보간
11. 질량 보존 검증

### HYSPLIT 호환성

✅ Stein et al. (2015) Section 2e 알고리즘 구현
✅ 질량 보존 보장 (테스트 검증)
✅ 시간 평균 농도 계산
✅ 3D Eulerian 격자 지원

---

## 2. 건조 침적 (Dry Deposition)

### 구현 내용

**파일**: `pyhysplit/physics/deposition.py` (개선)

HYSPLIT의 3-저항 모델을 완전히 구현했습니다.

### 핵심 기능

#### 2.1 중력 침강 (Stokes 법칙)
```python
v_g = ρ * d² * g / (18 * μ)
```
- 입자 크기와 밀도에 따른 침강 속도
- 공기 점성도 고려

#### 2.2 3-저항 모델
```python
v_d = 1 / (r_a + r_b + r_s) + v_g
```

**저항 성분**:
- `r_a`: 공기역학적 저항 (Aerodynamic resistance)
  - `r_a = ln(z/z0) / (κ * u*)`
  - 높이와 마찰 속도에 의존
  
- `r_b`: 준층류 저항 (Quasi-laminar resistance)
  - `r_b = 2 / (κ * u*)`
  - 표면 근처 얇은 층의 저항
  
- `r_s`: 표면 저항 (Surface resistance)
  - 지표면 유형에 따라 다름
  - 기본값: 100 s/m (식생 표면)

#### 2.3 기체 침적 (Henry's Law)
```python
v_d = 1 / (r_a + r_b + r_s)
where r_s ∝ 1/H
```
- 용해도가 높은 기체는 빠른 침적
- Henry 상수로 표면 저항 계산

#### 2.4 통합 적용 메서드
```python
new_mass, dz = depo.apply_deposition_step(
    mass, z, precip_rate, cloud_base, cloud_top, ustar, dt
)
```
- 건조/습윤 침적 통합
- 중력 침강에 의한 수직 변위 계산
- 입자/기체 자동 구분

### 테스트 커버리지

**16개 단위 테스트** (모두 통과 ✅):
1. 중력 침강 계산
2. 건조 침적 속도
3. 구름 아래 세정
4. 구름 내 세정
5. 질량 감소 적용
6. 기체 침적 속도
7. 침적 없음 (비활성화)
8. 건조 침적만
9. 습윤 침적만
10. 건조+습윤 침적
11. 기체 종 침적
12. 공기역학적 저항
13. 준층류 저항
14. 표면 저항
15. 고갈 임계값
16. 질량 보존 속성

---

## 3. 습윤 침적 (Wet Deposition)

### 구현 내용

**파일**: `pyhysplit/physics/deposition.py` (개선)

HYSPLIT의 세정 계수 모델을 구현했습니다.

### 핵심 기능

#### 3.1 구름 아래 세정 (Below-Cloud Scavenging)
```python
Λ = a * P^b
```
- `P`: 강수율 (mm/h)
- `a = 5×10⁻⁵`, `b = 0.8` (기본값)
- 빗방울에 의한 입자 포집

#### 3.2 구름 내 세정 (In-Cloud Scavenging)
```python
Λ = ratio * P  (if cloud_base < z < cloud_top)
```
- `ratio = 3×10⁻⁵ s⁻¹ per mm/h` (기본값)
- 구름 내부에서만 적용
- 구름 물방울에 의한 포집

#### 3.3 질량 감소 공식
```python
m(t+Δt) = m(t) * exp(-(v_d/Δz + Λ) * |Δt|)
```
- 건조 침적과 습윤 침적 통합
- 지수 감소 (exponential decay)
- 질량 보존 보장

### HYSPLIT 호환성

✅ Stein et al. (2015) Section 2d 알고리즘 구현
✅ 세정 계수 공식 정확히 구현
✅ 구름 높이 기반 세정 구분
✅ 질량 감소 지수 법칙 적용

---

## 성능 및 검증

### 계산 성능

**농도 계산**:
- Top-hat 커널: O(N) - N은 입자 수
- Gaussian 커널: O(N × M) - M은 커널 범위 내 셀 수
- 대규모 시뮬레이션: NumPy 벡터화로 최적화

**침적 계산**:
- 입자당 O(1) 복잡도
- 벡터화 가능 (향후 최적화)

### 질량 보존

모든 물리 과정에서 질량 보존 검증:
- ✅ 농도 계산: 분배 전후 총 질량 동일
- ✅ 침적: 질량 감소만 발생 (증가 없음)
- ✅ 수치 안정성: 언더플로우 방지

### 테스트 통과율

```
농도 계산: 11/11 (100%) ✅
침적 계산: 16/16 (100%) ✅
총계: 27/27 (100%) ✅
```

---

## 사용 예제

### 1. 농도 계산 예제

```python
from datetime import datetime
from pyhysplit.core.models import ConcentrationGridConfig, ParticleState
from pyhysplit.physics.concentration import ConcentrationCalculator

# 격자 설정
config = ConcentrationGridConfig(
    center_lat=37.5,
    center_lon=127.0,
    spacing_lat=0.1,
    spacing_lon=0.1,
    span_lat=2.0,
    span_lon=2.0,
    levels=[0, 100, 500, 1000, 2000],
    sampling_start=datetime(2024, 1, 1, 0, 0),
    sampling_end=datetime(2024, 1, 1, 24, 0),
    averaging_period=24,
)

# 계산기 초기화
calc = ConcentrationCalculator(config, kernel_type="top_hat")

# 시뮬레이션 루프에서 입자 누적
for t in time_steps:
    calc.accumulate_particles(particles, current_time)

# 최종 농도 계산
grid = calc.compute_concentration()

# 특정 지점 농도 조회
conc = calc.get_concentration_at_point(127.0, 37.5, 500.0, grid)
print(f"Concentration: {conc:.2e} kg/m³")
```

### 2. 침적 적용 예제

```python
from pyhysplit.physics.deposition import DepositionModule

# 침적 모듈 초기화
depo = DepositionModule(
    config,
    particle_diameter=1e-5,  # 10 microns
    particle_density=1000.0,  # water density
)

# 시뮬레이션 루프에서 침적 적용
for particle in particles:
    new_mass, dz = depo.apply_deposition_step(
        mass=particle.mass,
        z=particle.z,
        precip_rate=5.0,  # mm/h
        cloud_base=1000.0,
        cloud_top=3000.0,
        ustar=0.3,  # m/s
        dt=3600.0,  # 1 hour
    )
    
    particle.mass = new_mass
    particle.z += dz  # Apply settling
    
    # Check depletion
    if particle.mass < depo.get_depletion_threshold(initial_mass):
        particle.active = False
```

---

## 향후 개선 사항

### 단기 (우선순위 높음)
1. ✅ 농도 계산 - 완료
2. ✅ 건조/습윤 침적 - 완료
3. ⏳ 엔진 통합 - 다음 단계
4. ⏳ 실제 기상 데이터 테스트

### 중기
1. 농도 출력 포맷 (cdump)
2. 다중 종 지원
3. 화학 반응 (선택적)

### 장기
1. GPU 가속 농도 계산
2. 적응형 격자 세분화
3. 고급 침적 모델 (GOCART, MOSAIC)

---

## 참고 문헌

1. **Stein et al. (2015)**: NOAA's HYSPLIT Atmospheric Transport and Dispersion Modeling System. *Bulletin of the American Meteorological Society*.
   - Section 2d: Deposition
   - Section 2e: Concentration Calculations

2. **Draxler & Hess (1998)**: An overview of the HYSPLIT_4 modeling system for trajectories, dispersion, and deposition. *Australian Meteorological Magazine*.

3. **HYSPLIT User's Guide**: Chapter 4 "Concentration Grid"

---

## 결론

PySPlit은 이제 HYSPLIT의 핵심 물리 과정을 모두 구현했습니다:

✅ **궤적 계산**: Heun 적분, 좌표 변환, 경계 처리
✅ **수직 운동**: 7가지 모드 지원
✅ **난류 확산**: PBL 기반 Kz/Kh 계산
✅ **농도 계산**: Lagrangian-Eulerian 하이브리드
✅ **건조 침적**: 3-저항 모델, 중력 침강
✅ **습윤 침적**: 구름 내/외 세정

이제 PySPlit은 단순한 궤적 모델을 넘어 **완전한 대기 확산 모델**로 발전했습니다! 🎉

---

**작성일**: 2024년 2월 15일
**버전**: 1.0.0
**테스트 통과율**: 100% (27/27)
