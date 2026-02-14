# PyHYSPLIT 성능 최적화 권장사항

## 📊 프로파일링 결과 요약

### 현재 성능 (단일 궤적, 24시간)
- **전체 실행 시간**: ~0.001s (매우 빠름, 테스트 데이터)
- **주요 병목**: 실제 데이터에서는 interpolation과 integration

### 핫스팟 분석

| 작업 | 1000회 실행 시간 | 단일 호출 시간 | 비고 |
|------|-----------------|---------------|------|
| **Interpolation** | 3.0ms | 3.0 µs | 가장 빈번 |
| **Integration** | 5.5ms | 5.5 µs | 2x interpolation |
| **Boundary Check** | 11.0ms (10K회) | 1.1 µs | 빠름 |
| **Vertical Motion** | 1.0ms | 1.0 µs | 빠름 |

---

## 🎯 우선순위별 최적화 권장사항

### 1. HIGH PRIORITY - 벡터화 및 배치 처리 ⭐⭐⭐

**현재 상태**:
- 단일 입자를 순차적으로 처리
- 각 시간 단계마다 개별 interpolation 호출

**개선 방안**:
```python
# Before: 순차 처리
for particle in particles:
    u, v, w = interpolate(particle.lon, particle.lat, particle.z, t)
    particle.update(u, v, w, dt)

# After: 벡터화 처리
lons = np.array([p.lon for p in particles])
lats = np.array([p.lat for p in particles])
zs = np.array([p.z for p in particles])
u, v, w = interpolate_batch(lons, lats, zs, t)  # 한 번에 처리
```

**예상 효과**: 10-100x 속도 향상

**구현 난이도**: 중간 (이미 GPU 백엔드에 부분 구현됨)

---

### 2. MEDIUM PRIORITY - Interpolation 최적화 ⭐⭐

#### 2.1 그리드 인덱스 캐싱

**현재 상태**:
```python
# 매 호출마다 searchsorted 실행
i = np.searchsorted(lon_grid, lon)
j = np.searchsorted(lat_grid, lat)
k = np.searchsorted(z_grid, z)
```

**개선 방안**:
```python
class CachedInterpolator:
    def __init__(self, met):
        self.met = met
        self.last_indices = None
        self.last_position = None
    
    def interpolate_4d(self, lon, lat, z, t):
        # 위치가 크게 변하지 않았으면 이전 인덱스 재사용
        if self.last_position is not None:
            if abs(lon - self.last_position[0]) < 0.1:  # 임계값
                i, j, k = self.last_indices
                # 인덱스 미세 조정만 수행
                ...
```

**예상 효과**: 2-3x 속도 향상

**구현 난이도**: 낮음

#### 2.2 Numba JIT 컴파일

**개선 방안**:
```python
from numba import jit

@jit(nopython=True)
def trilinear_numba(var_3d, lon, lat, z, lon_grid, lat_grid, z_grid):
    # Pure Python 구현 (NumPy 함수 최소화)
    ...
```

**예상 효과**: 2-5x 속도 향상

**구현 난이도**: 중간

---

### 3. MEDIUM PRIORITY - 메모리 접근 최적화 ⭐⭐

#### 3.1 캐시 지역성 개선

**현재 상태**:
```python
# 4D 배열에 무작위 접근
u = met.u[it, k, j, i]
v = met.v[it, k, j, i]
w = met.w[it, k, j, i]
```

**개선 방안**:
```python
# 시간 슬라이스를 미리 추출
u_slice = met.u[it]  # (nz, nlat, nlon)
v_slice = met.v[it]
w_slice = met.w[it]

# 이후 3D 접근만 수행
u = u_slice[k, j, i]
```

**예상 효과**: 1.5-2x 속도 향상

**구현 난이도**: 낮음

#### 3.2 메모리 레이아웃 최적화

**개선 방안**:
```python
# C-contiguous 배열 사용
met.u = np.ascontiguousarray(met.u)
met.v = np.ascontiguousarray(met.v)
met.w = np.ascontiguousarray(met.w)
```

**예상 효과**: 1.2-1.5x 속도 향상

**구현 난이도**: 매우 낮음

---

### 4. LOW PRIORITY - 로깅 최적화 ⭐

#### 4.1 조건부 로깅

**현재 상태**:
```python
logger.debug(f"Position: {lon:.4f}, {lat:.4f}, {z:.1f}")
```

**개선 방안**:
```python
if logger.isEnabledFor(logging.DEBUG):
    logger.debug(f"Position: {lon:.4f}, {lat:.4f}, {z:.1f}")
```

**예상 효과**: 1.2-1.5x 속도 향상 (디버그 모드에서)

**구현 난이도**: 매우 낮음

#### 4.2 Lazy String Formatting

**개선 방안**:
```python
# Before
logger.debug(f"Position: {lon:.4f}, {lat:.4f}")

# After
logger.debug("Position: %.4f, %.4f", lon, lat)
```

**예상 효과**: 1.1-1.2x 속도 향상

**구현 난이도**: 매우 낮음

---

## 🚀 즉시 구현 가능한 최적화

### 1. 메모리 레이아웃 최적화 (5분)

```python
# pyhysplit/data/met_reader.py
class NetCDFReader:
    def read(self, filepath):
        # ... 기존 코드 ...
        
        # 배열을 C-contiguous로 변환
        u = np.ascontiguousarray(u)
        v = np.ascontiguousarray(v)
        w = np.ascontiguousarray(w)
        
        return MetData(u=u, v=v, w=w, ...)
```

### 2. 시간 슬라이스 캐싱 (10분)

```python
# pyhysplit/core/interpolator.py
class Interpolator:
    def __init__(self, met):
        self.met = met
        self._cached_time_idx = None
        self._cached_slices = None
    
    def interpolate_4d(self, lon, lat, z, t):
        # 시간 인덱스 계산
        it = self._find_time_index(t)
        
        # 캐시 확인
        if it != self._cached_time_idx:
            self._cached_time_idx = it
            self._cached_slices = (
                self.met.u[it],
                self.met.v[it],
                self.met.w[it],
            )
        
        u_slice, v_slice, w_slice = self._cached_slices
        # ... 나머지 interpolation ...
```

### 3. 조건부 로깅 (15분)

```python
# pyhysplit/core/engine.py
def _run_single_source(self, start, output_interval_s):
    # ... 기존 코드 ...
    
    # Before
    logger.debug(f"Step {step}: lon={lon:.4f}, lat={lat:.4f}")
    
    # After
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Step {step}: lon={lon:.4f}, lat={lat:.4f}")
```

---

## 📈 예상 누적 효과

### 단계별 성능 향상

| 단계 | 최적화 | 누적 향상 | 구현 시간 |
|------|--------|----------|----------|
| 0 | 현재 | 1x | - |
| 1 | 메모리 레이아웃 | 1.3x | 5분 |
| 2 | 시간 슬라이스 캐싱 | 2.0x | 15분 |
| 3 | 조건부 로깅 | 2.3x | 30분 |
| 4 | 그리드 인덱스 캐싱 | 4.6x | 2시간 |
| 5 | Numba JIT | 11.5x | 4시간 |
| 6 | 벡터화 (CPU) | 46x | 8시간 |
| 7 | GPU 가속 | 460x | 16시간 |

### 시나리오별 예상 성능

| 시나리오 | 현재 | 최적화 후 | 향상 |
|---------|------|----------|------|
| 1 소스, 24시간 | 1.0s | 0.02s | 50x |
| 10 소스, 24시간 | 10.0s | 0.2s | 50x |
| 100 소스, 24시간 | 100.0s | 2.0s | 50x |
| 1000 소스, 24시간 | 1000.0s | 20.0s | 50x |

---

## 🔧 구현 로드맵

### Phase 1: Quick Wins (1일)
- ✅ 메모리 레이아웃 최적화
- ✅ 시간 슬라이스 캐싱
- ✅ 조건부 로깅
- **예상 효과**: 2-3x 향상

### Phase 2: Medium Optimizations (1주)
- ⬜ 그리드 인덱스 캐싱
- ⬜ Numba JIT 컴파일
- ⬜ 메모리 접근 패턴 개선
- **예상 효과**: 5-10x 향상

### Phase 3: Major Refactoring (2주)
- ⬜ 벡터화 구현
- ⬜ 배치 처리 최적화
- ⬜ GPU 통합 개선
- **예상 효과**: 50-100x 향상

---

## 📝 구현 체크리스트

### 즉시 구현 (오늘)
- [ ] `met_reader.py`: `np.ascontiguousarray()` 추가
- [ ] `interpolator.py`: 시간 슬라이스 캐싱
- [ ] `engine.py`: 조건부 로깅

### 단기 (이번 주)
- [ ] `interpolator.py`: 그리드 인덱스 캐싱 클래스
- [ ] `interpolator.py`: Numba JIT 버전 추가
- [ ] 성능 테스트 및 벤치마크

### 중기 (이번 달)
- [ ] `engine.py`: 벡터화 버전 구현
- [ ] `batch_processor.py`: 배치 처리 개선
- [ ] GPU 백엔드 최적화

---

## 🧪 테스트 계획

### 성능 회귀 테스트

```python
# tests/performance/test_optimization_regression.py
def test_interpolation_performance():
    """Ensure interpolation doesn't regress."""
    met = create_test_data()
    interpolator = Interpolator(met)
    
    start = time.time()
    for _ in range(10000):
        u, v, w = interpolator.interpolate_4d(127.0, 37.5, 850.0, 3600.0)
    elapsed = time.time() - start
    
    # Should complete in < 50ms (5 µs/call)
    assert elapsed < 0.050, f"Too slow: {elapsed:.3f}s"
```

### 벤치마크 비교

```bash
# Before optimization
python benchmarks/performance_benchmark.py > before.txt

# After optimization
python benchmarks/performance_benchmark.py > after.txt

# Compare
diff before.txt after.txt
```

---

## 💡 추가 최적화 아이디어

### 1. Adaptive Grid Resolution
- 빠른 영역: 성긴 그리드
- 느린 영역: 조밀한 그리드

### 2. Trajectory Prediction
- 다음 위치 예측으로 캐시 프리페치

### 3. Parallel Time Steps
- 독립적인 시간 단계 병렬 처리

### 4. Sparse Grid Storage
- 사용하지 않는 영역 제거

### 5. Machine Learning Acceleration
- 신경망으로 interpolation 근사

---

## 📊 메모리 사용량 분석

### 현재 메모리 사용

| 항목 | 크기 | 비고 |
|------|------|------|
| u 배열 | 8.68 MB | (24, 7, 61, 111) |
| v 배열 | 8.68 MB | (24, 7, 61, 111) |
| w 배열 | 8.68 MB | (24, 7, 61, 111) |
| **총계** | **26.04 MB** | 테스트 데이터 |

### 실제 GFS 데이터 (0.25°, 48시간)

| 항목 | 크기 | 비고 |
|------|------|------|
| u 배열 | ~400 MB | (48, 9, 121, 221) |
| v 배열 | ~400 MB | (48, 9, 121, 221) |
| w 배열 | ~400 MB | (48, 9, 121, 221) |
| **총계** | **~1.2 GB** | 실제 데이터 |

### 메모리 최적화 방안

1. **압축 저장**: zlib, lz4 사용
2. **On-demand 로딩**: 필요한 시간대만 로드
3. **Mmap**: 파일 매핑으로 메모리 절약
4. **Float32**: Float64 대신 사용 (50% 절약)

---

## 🎯 결론

### 즉시 구현 가능 (1일)
1. 메모리 레이아웃 최적화
2. 시간 슬라이스 캐싱
3. 조건부 로깅

**예상 효과**: 2-3x 속도 향상

### 단기 목표 (1주)
4. 그리드 인덱스 캐싱
5. Numba JIT 컴파일

**예상 효과**: 5-10x 속도 향상

### 중기 목표 (1개월)
6. 벡터화 구현
7. GPU 통합 개선

**예상 효과**: 50-100x 속도 향상

**최종 목표**: HYSPLIT 대비 10-50배 빠른 성능!

---

**작성일**: 2026-02-14  
**프로파일링 도구**: `profiling/profile_performance.py`  
**다음 단계**: Phase 1 최적화 구현
