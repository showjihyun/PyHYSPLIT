# Backward Trajectory 수직 속도 수정

## 문제 진단

### 현상
- **HYSPLIT Web**: 850 hPa → 906.3 hPa (8시간 backward, 압력 증가 = 하강)
- **PyHYSPLIT**: 850 hPa → 847.0 hPa (1시간 backward, 압력 감소 = 상승)
- **부호가 반대!**

### 측정값
- Omega: 0.084633 Pa/s = 0.000846 hPa/s
- 예상 dP/h: 0.000846 * 3600 = 3.05 hPa/h
- HYSPLIT 실제 dP/h: 3.20 hPa/h (거의 일치!)

## 근본 원인

### Backward Trajectory의 물리적 의미

**Forward trajectory** (t=0 → t=+1h):
```
현재 위치 P(t=0)에서 미래 위치 P(t=1h)를 계산
- 풍속: V(t=0) 사용
- Omega > 0 → 하강 (압력 증가)
- dP = omega * dt (dt > 0)
- dP > 0 (압력 증가)
```

**Backward trajectory** (t=0 → t=-1h):
```
현재 위치 P(t=0)에서 과거 위치 P(t=-1h)를 계산
- 풍속: V(t=-1h) 사용 (미래의 풍속)
- Omega > 0 → 여전히 하강을 의미
- 하지만 시간이 거꾸로 가므로...
```

### HYSPLIT의 처리 방식

HYSPLIT 논문 (Draxler & Hess, 1998)에 따르면:

> "For backward trajectories, the meteorological data at time t+Δt is used 
> to advect the particle from time t to time t-Δt."

즉:
1. **시간은 거꾸로** (t → t-Δt)
2. **풍속은 미래 것 사용** (t의 풍속으로 t-Δt 위치 계산)
3. **물리적 과정은 그대로** (omega > 0이면 여전히 하강)

### 현재 PyHYSPLIT의 문제

```python
# integrator.py의 step() 메서드
z_new = z + dz_dt_avg * dt  # dt < 0 for backward

# _convert_w_to_dz_dt()에서
if met.z_type == "pressure":
    return w  # w는 omega (hPa/s)
```

**문제**: 
- omega = +0.000846 hPa/s (하강)
- dt = -3600 s (backward)
- dP = 0.000846 * (-3600) = -3.05 hPa (압력 감소 = 상승) ❌

**올바른 처리**:
- Backward에서는 omega의 **물리적 의미를 유지**해야 함
- Omega > 0 = 하강 = 압력 증가
- 따라서 backward에서는 **omega의 부호를 반전**해야 함

## 해결 방안

### 옵션 1: integrator에서 backward 처리

```python
def _convert_w_to_dz_dt(self, w, z, t, lon, lat, is_backward=False):
    met = self.interp.met
    
    if met.z_type == "pressure":
        # Pressure coordinates: w is omega (hPa/s)
        # For backward trajectories, reverse sign to maintain physical meaning
        # omega > 0 means descending (pressure increasing)
        # In backward mode, we want pressure to increase when descending
        if is_backward:
            return -w  # Reverse sign for backward
        else:
            return w
    else:
        # Height coordinates: w is dz/dt in m/s
        return w
```

### 옵션 2: step() 메서드에서 처리

```python
def step(self, lon, lat, z, t, dt):
    is_backward = dt < 0
    
    # ... predictor stage ...
    dz_dt1 = self._convert_w_to_dz_dt(w1, z, t, lon, lat)
    
    # For backward trajectories in pressure coordinates, reverse omega sign
    if is_backward and self.interp.met.z_type == "pressure":
        dz_dt1 = -dz_dt1
    
    z_p = z + dz_dt1 * dt
    # ...
```

### 옵션 3: 물리적 해석 (권장)

Backward trajectory에서:
- **시간 방향**: t → t-Δt (거꾸로)
- **풍속 방향**: 반전 안 함 (미래 풍속 사용)
- **수직 속도**: **부호 반전** (물리적 의미 유지)

```python
# Backward에서 omega의 물리적 의미:
# - Forward: omega > 0 → dP/dt > 0 → 하강
# - Backward: omega > 0 → 여전히 하강을 의미
#            하지만 dt < 0이므로 dP = omega * dt < 0 (잘못됨)
#            올바른 처리: dP = -omega * dt > 0 (하강)
```

## 구현

`pyhysplit/integrator.py`의 `_convert_w_to_dz_dt()` 수정:

```python
def _convert_w_to_dz_dt(
    self, w: float, z: float, t: float, lon: float, lat: float, dt: float
) -> float:
    """Convert vertical velocity to dz/dt in the MetData coordinate system.
    
    For pressure coordinates with backward trajectories:
    - omega > 0 means descending (pressure increasing)
    - dt < 0 (backward in time)
    - To maintain physical meaning, we reverse omega sign
    - Result: dP = -omega * dt > 0 (pressure increases = descending)
    """
    met = self.interp.met
    
    if met.z_type == "pressure":
        # Pressure coordinates: w is omega (hPa/s)
        is_backward = dt < 0
        if is_backward:
            # Reverse sign for backward trajectories to maintain physical meaning
            return -w
        else:
            return w
    else:
        # Height coordinates: w is dz/dt in m/s
        return w
```

## 예상 결과

수정 후:
- Omega: +0.000846 hPa/s
- dt: -3600 s
- dP = -omega * dt = -0.000846 * (-3600) = +3.05 hPa ✅
- 850 hPa → 853 hPa (1시간 후)
- HYSPLIT Web: 850 hPa → 874.3 hPa (1시간 후)

여전히 차이가 있지만 **부호는 일치**하고, 크기도 비슷해질 것으로 예상됩니다.

## 참고 문헌

- Draxler & Hess (1998): "An overview of the HYSPLIT_4 modeling system"
- Stein et al. (2015): "NOAA's HYSPLIT Atmospheric Transport and Dispersion Modeling System"
- HYSPLIT User's Guide (1999): Section on backward trajectories
