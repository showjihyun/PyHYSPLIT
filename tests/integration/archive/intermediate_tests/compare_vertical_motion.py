"""PyHYSPLIT과 HYSPLIT Web의 수직 운동 비교."""

from pathlib import Path
from datetime import datetime, timedelta
import numpy as np

# PyHYSPLIT 결과
pyhysplit_points = [
    {'time': datetime(2026, 2, 13, 13, 0), 'height': 804.8},
    {'time': datetime(2026, 2, 13, 12, 0), 'height': 1387.2},
    {'time': datetime(2026, 2, 13, 11, 0), 'height': 1473.5},
    {'time': datetime(2026, 2, 13, 10, 0), 'height': 1330.5},
    {'time': datetime(2026, 2, 13, 9, 0), 'height': 1125.1},
    {'time': datetime(2026, 2, 13, 8, 0), 'height': 1046.4},
    {'time': datetime(2026, 2, 13, 7, 0), 'height': 1106.1},
    {'time': datetime(2026, 2, 13, 6, 0), 'height': 975.7},
]

# HYSPLIT Web 결과
hysplit_points = [
    {'time': datetime(2026, 2, 13, 13, 0), 'height': 850.0},
    {'time': datetime(2026, 2, 13, 12, 0), 'height': 813.8},
    {'time': datetime(2026, 2, 13, 11, 0), 'height': 783.8},
    {'time': datetime(2026, 2, 13, 10, 0), 'height': 768.1},
    {'time': datetime(2026, 2, 13, 9, 0), 'height': 769.5},
    {'time': datetime(2026, 2, 13, 8, 0), 'height': 761.7},
    {'time': datetime(2026, 2, 13, 7, 0), 'height': 713.8},
    {'time': datetime(2026, 2, 13, 6, 0), 'height': 656.9},
]

print("=" * 80)
print("수직 운동 비교")
print("=" * 80)

print(f"\n{'Time':<12} {'PyHYSPLIT':<12} {'HYSPLIT Web':<12} {'Diff':<10} {'dZ/dt (Py)':<15} {'dZ/dt (Web)':<15}")
print("-" * 90)

for i in range(len(pyhysplit_points)):
    py = pyhysplit_points[i]
    web = hysplit_points[i]
    diff = py['height'] - web['height']
    
    # 수직 속도 계산 (다음 포인트와의 차이)
    if i < len(pyhysplit_points) - 1:
        dt = 3600  # 1시간
        dz_py = (pyhysplit_points[i+1]['height'] - py['height']) / dt
        dz_web = (hysplit_points[i+1]['height'] - web['height']) / dt
        print(f"{py['time'].strftime('%H:%M'):<12} {py['height']:<12.1f} {web['height']:<12.1f} {diff:<10.1f} {dz_py:<15.6f} {dz_web:<15.6f}")
    else:
        print(f"{py['time'].strftime('%H:%M'):<12} {py['height']:<12.1f} {web['height']:<12.1f} {diff:<10.1f}")

print("\n분석:")
print("- PyHYSPLIT: 초기에 급상승 후 하강")
print("- HYSPLIT Web: 지속적으로 완만하게 하강")
print("- 차이: PyHYSPLIT이 수직 속도를 과대평가하고 있음")
