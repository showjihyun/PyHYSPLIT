"""PyHYSPLIT과 HYSPLIT Web 24시간 궤적 비교 도구.

PyHYSPLIT으로 계산한 24시간 궤적과 HYSPLIT Web 결과를 비교합니다.

사용법:
    1. PyHYSPLIT 궤적 생성: python tests/integration/run_simple_24h_test.py
    2. HYSPLIT Web에서 동일 조건으로 궤적 생성 (tdump 파일 저장)
    3. 이 스크립트로 비교: python tests/integration/compare_with_hysplit_web_24h.py <tdump_file>
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
import netCDF4

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pyhysplit.models import StartLocation, SimulationConfig, MetData
from pyhysplit.engine import TrajectoryEngine
from pyhysplit.coordinate_converter import CoordinateConverter
from pyhysplit.interpolator import Interpolator


def parse_hysplit_tdump(tdump_file: Path) -> list[dict]:
    """HYSPLIT tdump 파일 파싱.
    
    Parameters
    ----------
    tdump_file : Path
        HYSPLIT tdump 파일 경로
        
    Returns
    -------
    list[dict]
        궤적 포인트 리스트, 각 포인트는 {'time', 'lat', 'lon', 'height'} 딕셔너리
    """
    points = []
    
    with open(tdump_file, 'r') as f:
        lines = f.readlines()
    
    # 헤더 스킵 (보통 첫 5줄)
    data_start = 0
    for i, line in enumerate(lines):
        if line.strip() and not line.startswith('#'):
            # 숫자로 시작하는 첫 줄 찾기
            try:
                int(line.split()[0])
                data_start = i
                break
            except (ValueError, IndexError):
                continue
    
    # 데이터 파싱
    for line in lines[data_start:]:
        parts = line.split()
        if len(parts) < 11:
            continue
        
        try:
            # tdump 형식: 
            # 1  26  2 13  6  0  0.00  37.5000 127.0000  850.0
            year = int(parts[1])
            month = int(parts[2])
            day = int(parts[3])
            hour = int(parts[4])
            minute = int(parts[5])
            
            lat = float(parts[7])
            lon = float(parts[8])
            height = float(parts[9])
            
            dt = datetime(2000 + year if year < 100 else year, month, day, hour, minute)
            
            points.append({
                'time': dt,
                'lat': lat,
                'lon': lon,
                'height': height
            })
        except (ValueError, IndexError) as e:
            continue
    
    return points


def haversine(lat1, lon1, lat2, lon2):
    """두 지점 간 거리 계산 (km)."""
    R = 6371.0
    from math import radians, sin, cos, sqrt, atan2
    
    lat1_rad, lat2_rad = radians(lat1), radians(lat2)
    dlon = radians(lon2 - lon1)
    dlat = lat2_rad - lat1_rad
    
    a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c


def run_pyhysplit_24h(gfs_file: Path, start_lat: float, start_lon: float, 
                      start_height: float, duration_hours: int) -> list[dict]:
    """PyHYSPLIT 24시간 궤적 실행.
    
    Parameters
    ----------
    gfs_file : Path
        GFS 데이터 파일
    start_lat : float
        시작 위도
    start_lon : float
        시작 경도
    start_height : float
        시작 고도 (m AGL)
    duration_hours : int
        궤적 기간 (음수 = 역궤적)
        
    Returns
    -------
    list[dict]
        궤적 포인트 리스트
    """
    print(f"\n[PyHYSPLIT] 궤적 계산 중...")
    
    # GFS 데이터 로드
    ds = netCDF4.Dataset(str(gfs_file))
    
    u_data = np.array(ds.variables['u'][:])
    v_data = np.array(ds.variables['v'][:])
    w_data = np.array(ds.variables['w'][:])
    t_data = np.array(ds.variables['t'][:])
    
    lat_grid = np.array(ds.variables['latitude'][:])
    lon_grid = np.array(ds.variables['longitude'][:])
    lev_grid = np.array(ds.variables['level'][:])
    time_grid = np.array(ds.variables['time'][:])
    
    ds.close()
    
    # 시간 그리드 정렬
    if time_grid[0] > time_grid[-1]:
        time_indices = np.argsort(time_grid)
        time_grid = time_grid[time_indices]
        u_data = u_data[time_indices]
        v_data = v_data[time_indices]
        w_data = w_data[time_indices]
        t_data = t_data[time_indices]
    
    # MetData 생성
    met_data = MetData(
        u=u_data, v=v_data, w=w_data, t_field=t_data,
        lat_grid=lat_grid, lon_grid=lon_grid,
        z_grid=lev_grid, t_grid=time_grid,
        z_type="pressure", source="GFS_NC"
    )
    
    # 시뮬레이션 설정
    start_time = datetime(2026, 2, 13, 6, 0)
    start_loc = StartLocation(lat=start_lat, lon=start_lon, height=start_height)
    
    config = SimulationConfig(
        start_time=start_time,
        num_start_locations=1,
        start_locations=[start_loc],
        total_run_hours=duration_hours,
        vertical_motion=8,
        model_top=10000.0,
        met_files=[],
        turbulence_on=False,
        dt_max=15.0,
        vertical_damping=0.0003,
        scale_height=8430.0,
        tratio=0.75
    )
    
    # 궤적 계산
    engine = TrajectoryEngine(config, met_data)
    trajectory = engine.run(output_interval_s=3600.0)[0]
    
    # 결과 변환
    results = []
    base_time = datetime(start_time.year, start_time.month, start_time.day, 0, 0)
    
    for pt in trajectory:
        t_seconds, lon_val, lat_val, height_val = pt
        dt = base_time + timedelta(seconds=t_seconds)
        
        # 압력을 고도로 변환
        height_pa = height_val * 100.0
        
        try:
            interp = Interpolator(met_data)
            T = interp.interpolate_scalar(met_data.t_field, lon_val, lat_val, height_val, t_seconds)
            height_m = CoordinateConverter.pressure_to_height_hypsometric(
                np.array([height_pa]), np.array([T])
            )[0]
        except Exception:
            height_m = CoordinateConverter.pressure_to_height(np.array([height_pa]))[0]
        
        results.append({
            'time': dt,
            'lat': lat_val,
            'lon': lon_val,
            'height': height_m
        })
    
    print(f"  ✓ 완료: {len(results)} 포인트")
    return results


def compare_trajectories(pyhysplit_traj: list[dict], hysplit_traj: list[dict]):
    """두 궤적 비교 및 통계 출력.
    
    Parameters
    ----------
    pyhysplit_traj : list[dict]
        PyHYSPLIT 궤적
    hysplit_traj : list[dict]
        HYSPLIT Web 궤적
    """
    print(f"\n{'='*80}")
    print(f"  궤적 비교 결과")
    print(f"{'='*80}\n")
    
    print(f"포인트 수:")
    print(f"  PyHYSPLIT: {len(pyhysplit_traj)}")
    print(f"  HYSPLIT Web: {len(hysplit_traj)}")
    
    # 시간별 비교 (공통 시간대만)
    min_len = min(len(pyhysplit_traj), len(hysplit_traj))
    
    horizontal_errors = []
    vertical_errors = []
    
    print(f"\n시간별 차이:")
    print(f"{'시간':>8} {'수평거리(km)':>15} {'고도차(m)':>12} {'PyHYSPLIT 위치':>25} {'HYSPLIT 위치':>25}")
    print(f"{'-'*100}")
    
    for i in range(min_len):
        py_pt = pyhysplit_traj[i]
        hy_pt = hysplit_traj[i]
        
        # 수평 거리
        h_dist = haversine(py_pt['lat'], py_pt['lon'], hy_pt['lat'], hy_pt['lon'])
        horizontal_errors.append(h_dist)
        
        # 고도 차이
        v_diff = abs(py_pt['height'] - hy_pt['height'])
        vertical_errors.append(v_diff)
        
        # 출력 (3시간 간격)
        if i % 3 == 0:
            py_pos = f"{py_pt['lat']:.2f}°N, {py_pt['lon']:.2f}°E"
            hy_pos = f"{hy_pt['lat']:.2f}°N, {hy_pt['lon']:.2f}°E"
            print(f"{i:>8}h {h_dist:>14.2f} {v_diff:>11.1f} {py_pos:>25} {hy_pos:>25}")
    
    # 통계
    print(f"\n{'='*80}")
    print(f"  통계")
    print(f"{'='*80}\n")
    
    print(f"수평 오차:")
    print(f"  평균: {np.mean(horizontal_errors):.2f} km")
    print(f"  중앙값: {np.median(horizontal_errors):.2f} km")
    print(f"  최대: {np.max(horizontal_errors):.2f} km")
    print(f"  최소: {np.min(horizontal_errors):.2f} km")
    print(f"  표준편차: {np.std(horizontal_errors):.2f} km")
    
    print(f"\n고도 오차:")
    print(f"  평균: {np.mean(vertical_errors):.1f} m")
    print(f"  중앙값: {np.median(vertical_errors):.1f} m")
    print(f"  최대: {np.max(vertical_errors):.1f} m")
    print(f"  최소: {np.min(vertical_errors):.1f} m")
    print(f"  표준편차: {np.std(vertical_errors):.1f} m")
    
    # 일치율 계산 (수평 < 20km, 고도 < 100m)
    h_match = sum(1 for e in horizontal_errors if e < 20.0)
    v_match = sum(1 for e in vertical_errors if e < 100.0)
    
    print(f"\n일치율 (수평 < 20km, 고도 < 100m):")
    print(f"  수평: {h_match}/{len(horizontal_errors)} ({h_match/len(horizontal_errors)*100:.1f}%)")
    print(f"  고도: {v_match}/{len(vertical_errors)} ({v_match/len(vertical_errors)*100:.1f}%)")


def main():
    """메인 함수."""
    print("\n" + "="*80)
    print("  PyHYSPLIT vs HYSPLIT Web 24시간 궤적 비교")
    print("="*80)
    
    # GFS 데이터 파일
    gfs_file = Path("tests/integration/gfs_cache/gfs_24h_extended.nc")
    
    if not gfs_file.exists():
        print(f"\n❌ GFS 데이터 파일이 없습니다: {gfs_file}")
        print(f"먼저 실행하세요: python tests/integration/extend_gfs_to_24h.py")
        return
    
    # 테스트 조건
    start_lat = 37.5
    start_lon = 127.0
    start_height = 850.0
    duration_hours = -24
    
    print(f"\n테스트 조건:")
    print(f"  시작 위치: {start_lat}°N, {start_lon}°E")
    print(f"  시작 고도: {start_height}m AGL")
    print(f"  기간: {abs(duration_hours)}시간 역궤적")
    
    # PyHYSPLIT 실행
    pyhysplit_traj = run_pyhysplit_24h(gfs_file, start_lat, start_lon, start_height, duration_hours)
    
    # HYSPLIT Web 결과 로드
    if len(sys.argv) > 1:
        tdump_file = Path(sys.argv[1])
        if tdump_file.exists():
            print(f"\n[HYSPLIT Web] tdump 파일 로드: {tdump_file}")
            hysplit_traj = parse_hysplit_tdump(tdump_file)
            print(f"  ✓ 완료: {len(hysplit_traj)} 포인트")
            
            # 비교
            compare_trajectories(pyhysplit_traj, hysplit_traj)
        else:
            print(f"\n❌ tdump 파일이 없습니다: {tdump_file}")
    else:
        print(f"\n⚠ HYSPLIT Web tdump 파일이 제공되지 않았습니다.")
        print(f"\n다음 단계:")
        print(f"  1. HYSPLIT Web에서 동일 조건으로 궤적 생성:")
        print(f"     - 시작: {start_lat}°N, {start_lon}°E, {start_height}m AGL")
        print(f"     - 기간: {abs(duration_hours)}시간 역궤적")
        print(f"     - 데이터: GFS 0.25도")
        print(f"  2. tdump 파일 다운로드")
        print(f"  3. 이 스크립트 재실행:")
        print(f"     python {Path(__file__).name} <tdump_file>")


if __name__ == "__main__":
    main()
