"""압력 직접 지정 테스트"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pyhysplit.models import StartLocation, SimulationConfig, MetData
from pyhysplit.engine import TrajectoryEngine
from datetime import datetime
import numpy as np

# 간단한 테스트 MetData 생성
met_data = MetData(
    u=np.zeros((2, 3, 5, 5)),
    v=np.zeros((2, 3, 5, 5)),
    w=np.zeros((2, 3, 5, 5)),
    lon_grid=np.array([125, 126, 127, 128, 129]),
    lat_grid=np.array([35, 36, 37, 38, 39]),
    z_grid=np.array([1000, 850, 700]),  # hPa
    t_grid=np.array([0, 3600]),
    z_type="pressure",
    source="TEST"
)

print("="*80)
print("  압력 직접 지정 테스트")
print("="*80)

# 테스트 1: height_type="pressure"
print("\n테스트 1: height_type='pressure'로 850 hPa 직접 지정")
start_loc = StartLocation(
    lat=37.0,
    lon=127.0,
    height=850.0,
    height_type="pressure"
)

config = SimulationConfig(
    start_time=datetime(2026, 2, 14, 0, 0),
    num_start_locations=1,
    start_locations=[start_loc],
    total_run_hours=-1,
    vertical_motion=0,
    model_top=10000.0,
    met_files=[],
    turbulence_on=False
)

try:
    engine = TrajectoryEngine(config, met_data)
    print(f"  ✓ 엔진 생성 성공")
    print(f"  변환된 시작 위치: {engine._converted_start_locations}")
    
    trajectory = engine.run(output_interval_s=3600.0)[0]
    print(f"  ✓ 궤적 계산 성공")
    print(f"  시작 압력: {trajectory[0][3]:.1f} hPa")
    
except Exception as e:
    print(f"  ❌ 실패: {e}")

# 테스트 2: height_type="meters_agl" (기본값)
print("\n테스트 2: height_type='meters_agl'로 1400m 지정")
start_loc2 = StartLocation(
    lat=37.0,
    lon=127.0,
    height=1400.0,
    height_type="meters_agl"
)

config2 = SimulationConfig(
    start_time=datetime(2026, 2, 14, 0, 0),
    num_start_locations=1,
    start_locations=[start_loc2],
    total_run_hours=-1,
    vertical_motion=0,
    model_top=10000.0,
    met_files=[],
    turbulence_on=False
)

try:
    engine2 = TrajectoryEngine(config2, met_data)
    print(f"  ✓ 엔진 생성 성공")
    print(f"  변환된 시작 위치: {engine2._converted_start_locations}")
    
    trajectory2 = engine2.run(output_interval_s=3600.0)[0]
    print(f"  ✓ 궤적 계산 성공")
    print(f"  시작 압력: {trajectory2[0][3]:.1f} hPa")
    
except Exception as e:
    print(f"  ❌ 실패: {e}")

print("\n결론:")
print("  - height_type='pressure': 850 hPa 직접 사용")
print("  - height_type='meters_agl': 1400m → 압력 변환")
