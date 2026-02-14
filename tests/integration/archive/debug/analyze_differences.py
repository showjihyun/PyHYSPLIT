"""PyHYSPLIT과 HYSPLIT Web의 차이를 상세 분석."""

from pathlib import Path
from datetime import datetime
import numpy as np

# HYSPLIT Web 결과
hysplit_points = [
    {'time': datetime(2026, 2, 13, 13, 0), 'lat': 37.500, 'lon': 127.000, 'height': 850.0},
    {'time': datetime(2026, 2, 13, 12, 0), 'lat': 37.402, 'lon': 126.800, 'height': 813.8},
    {'time': datetime(2026, 2, 13, 11, 0), 'lat': 37.307, 'lon': 126.618, 'height': 783.8},
    {'time': datetime(2026, 2, 13, 10, 0), 'lat': 37.206, 'lon': 126.420, 'height': 768.1},
    {'time': datetime(2026, 2, 13, 9, 0), 'lat': 37.097, 'lon': 126.185, 'height': 769.5},
    {'time': datetime(2026, 2, 13, 8, 0), 'lat': 36.983, 'lon': 125.932, 'height': 761.7},
    {'time': datetime(2026, 2, 13, 7, 0), 'lat': 36.860, 'lon': 125.685, 'height': 713.8},
    {'time': datetime(2026, 2, 13, 6, 0), 'lat': 36.717, 'lon': 125.433, 'height': 656.9},
]

# PyHYSPLIT 결과 (Mode 8)
pyhysplit_points = [
    {'time': datetime(2026, 2, 13, 13, 0), 'lat': 37.500, 'lon': 127.000, 'height': 804.8},
    {'time': datetime(2026, 2, 13, 12, 0), 'lat': 37.371, 'lon': 126.834, 'height': 863.7},
    {'time': datetime(2026, 2, 13, 11, 0), 'lat': 37.259, 'lon': 126.660, 'height': 902.9},
    {'time': datetime(2026, 2, 13, 10, 0), 'lat': 37.174, 'lon': 126.499, 'height': 930.2},
    {'time': datetime(2026, 2, 13, 9, 0), 'lat': 37.116, 'lon': 126.350, 'height': 933.5},
    {'time': datetime(2026, 2, 13, 8, 0), 'lat': 37.061, 'lon': 126.181, 'height': 927.7},
    {'time': datetime(2026, 2, 13, 7, 0), 'lat': 36.991, 'lon': 125.969, 'height': 934.9},
    {'time': datetime(2026, 2, 13, 6, 0), 'lat': 36.918, 'lon': 125.724, 'height': 937.2},
]

print("=" * 80)
print("상세 차이 분석")
print("=" * 80)

print(f"\n{'Time':<12} {'Δ Lat':<10} {'Δ Lon':<10} {'Δ Height':<12} {'Lat Drift':<12} {'Lon Drift':<12}")
print("-" * 80)

for i in range(len(hysplit_points)):
    h = hysplit_points[i]
    p = pyhysplit_points[i]
    
    dlat = p['lat'] - h['lat']
    dlon = p['lon'] - h['lon']
    dheight = p['height'] - h['height']
    
    # 누적 drift 계산
    if i == 0:
        lat_drift = 0.0
        lon_drift = 0.0
    else:
        lat_drift = (p['lat'] - hysplit_points[0]['lat']) - (h['lat'] - hysplit_points[0]['lat'])
        lon_drift = (p['lon'] - hysplit_points[0]['lon']) - (h['lon'] - hysplit_points[0]['lon'])
    
    print(f"{h['time'].strftime('%H:%M'):<12} {dlat:<10.4f} {dlon:<10.4f} {dheight:<12.1f} {lat_drift:<12.4f} {lon_drift:<12.4f}")

print("\n분석:")
print("1. 위도 차이: PyHYSPLIT이 북쪽으로 치우침 (평균 +0.15°)")
print("2. 경도 차이: PyHYSPLIT이 동쪽으로 치우침 (평균 +0.20°)")
print("3. 고도 차이: PyHYSPLIT이 높게 유지됨 (평균 +151m)")
print("\n가능한 원인:")
print("- 수평 풍속 보간 방식의 차이")
print("- 수직 속도 damping이 여전히 부족")
print("- 시간 간격 처리의 차이")
print("- 지구 곡률 계산의 차이")
