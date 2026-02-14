"""고도 변환 문제 디버깅."""

import sys
from datetime import datetime

import numpy as np

sys.path.insert(0, '/workspaces/pyhysplit')

from pyhysplit.coordinate_converter import CoordinateConverter
from pyhysplit.engine import TrajectoryEngine
from pyhysplit.met_reader import NetCDFReader
from pyhysplit.models import SimulationConfig, StartLocation


def main():
    """고도 변환 테스트."""
    
    print("\n=== 고도 변환 테스트 ===\n")
    
    # 1. 표준 대기 변환 테스트
    print("1. 표준 대기 변환")
    heights_m = np.array([0, 500, 850, 1500, 3000])
    
    for h in heights_m:
        p_pa = CoordinateConverter.height_to_pressure(np.array([h]))[0]
        p_hpa = p_pa / 100.0
        h_back = CoordinateConverter.pressure_to_height(np.array([p_pa]))[0]
        
        print(f"  {h:5.0f}m → {p_hpa:7.1f} hPa → {h_back:5.0f}m")
    
    # 2. GFS 데이터의 z_grid 확인
    print("\n2. GFS 데이터 z_grid")
    gfs_file = "tests/integration/gfs_cache/gfs_20260213_37.5_127.0_1h.nc"
    reader = NetCDFReader()
    met = reader.read(gfs_file)
    
    print(f"  z_type: {met.z_type}")
    print(f"  z_grid: {met.z_grid}")
    print(f"  z_grid 범위: {met.z_grid[0]:.1f} ~ {met.z_grid[-1]:.1f} hPa")
    
    # 3. 850m AGL을 기압으로 변환
    print("\n3. 850m AGL 변환")
    height_agl = 850.0  # m
    
    # 표준 대기 변환
    p_pa = CoordinateConverter.height_to_pressure(np.array([height_agl]))[0]
    p_hpa = p_pa / 100.0
    
    print(f"  850m AGL → {p_pa:.1f} Pa → {p_hpa:.1f} hPa")
    
    # z_grid 범위 체크
    if p_hpa < met.z_grid[0] or p_hpa > met.z_grid[-1]:
        print(f"  ⚠️ {p_hpa:.1f} hPa는 z_grid 범위 밖입니다!")
        print(f"     z_grid: {met.z_grid[0]:.1f} ~ {met.z_grid[-1]:.1f} hPa")
    else:
        print(f"  ✓ {p_hpa:.1f} hPa는 z_grid 범위 내입니다.")
    
    # 4. 실제 엔진 실행 테스트
    print("\n4. 엔진 실행 테스트")
    
    # 케이스 A: 850m를 그대로 사용 (잘못된 방법)
    print("\n  케이스 A: 850m를 그대로 사용")
    start_loc_a = StartLocation(lat=37.5, lon=127.0, height=850.0)
    
    config_a = SimulationConfig(
        start_time=datetime(2026, 2, 13, 13, 0),
        num_start_locations=1,
        start_locations=[start_loc_a],
        total_run_hours=-7,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[],
        turbulence_on=False
    )
    
    engine_a = TrajectoryEngine(config_a, met)
    
    try:
        traj_a = engine_a.run(output_interval_s=3600.0)[0]
        print(f"    결과: {len(traj_a)}개 포인트")
        if len(traj_a) >= 2:
            print(f"    시작: z={traj_a[0][3]:.1f}")
            print(f"    종료: z={traj_a[-1][3]:.1f}")
    except Exception as e:
        print(f"    오류: {e}")
    
    # 케이스 B: 850m를 기압으로 변환하여 사용 (올바른 방법)
    print("\n  케이스 B: 850m를 기압(hPa)으로 변환")
    p_hpa_start = p_hpa
    start_loc_b = StartLocation(lat=37.5, lon=127.0, height=p_hpa_start)
    
    config_b = SimulationConfig(
        start_time=datetime(2026, 2, 13, 13, 0),
        num_start_locations=1,
        start_locations=[start_loc_b],
        total_run_hours=-7,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[],
        turbulence_on=False
    )
    
    engine_b = TrajectoryEngine(config_b, met)
    
    # 로깅 활성화
    import logging
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')
    
    try:
        traj_b = engine_b.run(output_interval_s=3600.0)[0]
        print(f"    결과: {len(traj_b)}개 포인트")
        if len(traj_b) >= 2:
            print(f"    시작: z={traj_b[0][3]:.1f} hPa")
            print(f"    종료: z={traj_b[-1][3]:.1f} hPa")
            
            # 기압을 고도로 변환
            z_start_m = CoordinateConverter.pressure_to_height(np.array([traj_b[0][3] * 100]))[0]
            z_end_m = CoordinateConverter.pressure_to_height(np.array([traj_b[-1][3] * 100]))[0]
            print(f"    시작 (m): {z_start_m:.1f}m")
            print(f"    종료 (m): {z_end_m:.1f}m")
    except Exception as e:
        print(f"    오류: {e}")
    
    print("\n=== 테스트 완료 ===\n")


if __name__ == "__main__":
    main()
