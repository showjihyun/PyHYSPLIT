"""HYSPLIT Web의 압력 해석 방식 확인"""
import numpy as np

# 표준 대기 공식
def pressure_at_altitude(h, P0=1013.25, T0=288.15, L=0.0065, g=9.80665, R=287.05):
    """
    표준 대기 공식으로 고도에서의 압력 계산
    h: 고도 (m)
    P0: 해수면 기압 (hPa)
    T0: 해수면 온도 (K)
    L: 기온 감률 (K/m)
    g: 중력 가속도 (m/s²)
    R: 기체 상수 (J/(kg·K))
    """
    return P0 * (1 - L * h / T0) ** (g / (R * L))

def altitude_at_pressure(P, P0=1013.25, T0=288.15, L=0.0065, g=9.80665, R=287.05):
    """
    표준 대기 공식으로 압력에서의 고도 계산
    """
    return (T0 / L) * (1 - (P / P0) ** (R * L / g))

print("="*80)
print("  HYSPLIT Web 압력 해석 방식 분석")
print("="*80)

# 서울 고도
seoul_elevation = 38  # meters

# 서울 지표면 압력 (표준 대기 가정)
seoul_surface_pressure = pressure_at_altitude(seoul_elevation)
print(f"\n서울 지표면 압력 (표준 대기): {seoul_surface_pressure:.1f} hPa")

# 850 hPa 레벨의 해발 고도
altitude_850 = altitude_at_pressure(850)
print(f"850 hPa 레벨의 해발 고도: {altitude_850:.0f} m")

# 서울 지표면 위 850 hPa 레벨의 해발 고도
altitude_850_agl = altitude_850 + seoul_elevation
print(f"서울 지표면 위 850 hPa 레벨: {altitude_850_agl:.0f} m (해발)")

# 그 고도에서의 압력
pressure_at_850_agl = pressure_at_altitude(altitude_850_agl)
print(f"그 고도에서의 압력: {pressure_at_850_agl:.1f} hPa")

print(f"\n{'='*80}")
print("  HYSPLIT Web 시작 압력 분석")
print(f"{'='*80}")

# HYSPLIT Web이 보고한 시작 압력
hysplit_start_pressure = 906.3
print(f"\nHYSPLIT Web 시작 압력: {hysplit_start_pressure} hPa")

# 이 압력에 해당하는 고도
hysplit_altitude = altitude_at_pressure(hysplit_start_pressure)
print(f"이 압력에 해당하는 해발 고도: {hysplit_altitude:.0f} m")

# 서울 지표면 위 높이
hysplit_agl = hysplit_altitude - seoul_elevation
print(f"서울 지표면 위 높이: {hysplit_agl:.0f} m AGL")

print(f"\n{'='*80}")
print("  가설 검증")
print(f"{'='*80}")

print(f"\n가설 1: HYSPLIT Web은 '850 hPa'를 해발 기준으로 해석")
print(f"  예상 시작 압력: 850.0 hPa")
print(f"  실제 시작 압력: {hysplit_start_pressure} hPa")
print(f"  차이: {abs(850.0 - hysplit_start_pressure):.1f} hPa")
print(f"  결론: ❌ 일치하지 않음")

print(f"\n가설 2: HYSPLIT Web은 '850 hPa'를 지표면 위 레벨로 해석")
print(f"  850 hPa 레벨 고도: {altitude_850:.0f} m (해발)")
print(f"  서울에서의 실제 압력: {pressure_at_altitude(altitude_850):.1f} hPa")
print(f"  실제 시작 압력: {hysplit_start_pressure} hPa")
print(f"  차이: {abs(pressure_at_altitude(altitude_850) - hysplit_start_pressure):.1f} hPa")
print(f"  결론: ❌ 일치하지 않음")

print(f"\n가설 3: HYSPLIT Web은 GFS 데이터의 850 hPa 레벨을 사용하되,")
print(f"        지형 고도를 고려하여 실제 압력을 계산")
print(f"  서울 지표면 압력: {seoul_surface_pressure:.1f} hPa")
print(f"  850 hPa 레벨까지의 압력 차: {seoul_surface_pressure - 850:.1f} hPa")
print(f"  예상 시작 압력: {seoul_surface_pressure:.1f} hPa (지표면)")
print(f"  실제 시작 압력: {hysplit_start_pressure} hPa")
print(f"  차이: {abs(seoul_surface_pressure - hysplit_start_pressure):.1f} hPa")

# 더 정확한 분석: GFS 데이터에서 서울 위치의 지표면 압력 확인
print(f"\n{'='*80}")
print("  GFS 데이터 확인 필요")
print(f"{'='*80}")
print(f"\nGFS 데이터에서 서울 위치 (37.5°N, 127.0°E)의:")
print(f"  1. 지표면 압력 (surface pressure)")
print(f"  2. 지형 고도 (terrain height)")
print(f"  3. 850 hPa 레벨의 지오포텐셜 고도")
print(f"를 확인하면 HYSPLIT Web의 압력 해석 방식을 정확히 알 수 있습니다.")

print(f"\n추정: HYSPLIT Web은 입력된 '850 hPa'를 표준 기압 레벨로 해석하고,")
print(f"      해당 위치의 실제 지형과 기상 조건을 고려하여")
print(f"      실제 시작 압력을 {hysplit_start_pressure} hPa로 조정한 것으로 보입니다.")
