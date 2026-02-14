"""PyHYSPLIT vs HYSPLIT Web 결과 비교 스크립트.

HYSPLIT Web에서 자동으로 실행한 궤적과 PyHYSPLIT 결과를 비교합니다.
- 궤적 endpoints 비교 (위치, 고도, 시간)
- 시각적 비교 (이미지)
- 통계적 차이 분석
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from pyhysplit.engine import TrajectoryEngine
from pyhysplit.models import SimulationConfig, StartLocation


def parse_hysplit_web_endpoints(filepath: str) -> dict:
    """HYSPLIT Web의 tdump 파일을 파싱합니다.
    
    Parameters
    ----------
    filepath : str
        tdump 파일 경로
        
    Returns
    -------
    dict
        파싱된 궤적 데이터
    """
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # 헤더 정보 파싱
    info = {}
    trajectory_points = []
    
    # 시작 시간 찾기 (라인 7: 26     2    13    13   37.500  127.000   850.0)
    start_line = lines[6].strip().split()
    info['start_year'] = 2000 + int(start_line[0])
    info['start_month'] = int(start_line[1])
    info['start_day'] = int(start_line[2])
    info['start_hour'] = int(start_line[3])
    info['start_lat'] = float(start_line[4])
    info['start_lon'] = float(start_line[5])
    info['start_height'] = float(start_line[6])
    
    # 궤적 포인트 파싱 (라인 9부터)
    for line in lines[8:]:
        parts = line.strip().split()
        if len(parts) >= 12:
            point = {
                'year': 2000 + int(parts[2]),
                'month': int(parts[3]),
                'day': int(parts[4]),
                'hour': int(parts[5]),
                'minute': int(parts[6]),
                'forecast_hour': int(parts[7]),
                'age': float(parts[8]),
                'lat': float(parts[9]),
                'lon': float(parts[10]),
                'height': float(parts[11]),
                'pressure': float(parts[12]) if len(parts) > 12 else None
            }
            trajectory_points.append(point)
    
    info['points'] = trajectory_points
    info['num_points'] = len(trajectory_points)
    
    return info


def run_pyhysplit_comparison(
    lat: float,
    lon: float,
    height: float,
    start_time: datetime,
    duration_hours: int,
    output_dir: str = "tests/integration"
):
    """PyHYSPLIT으로 동일한 조건의 궤적을 계산합니다.
    
    Parameters
    ----------
    lat : float
        시작 위도
    lon : float
        시작 경도
    height : float
        시작 고도 (m AGL)
    start_time : datetime
        시작 시간 (UTC)
    duration_hours : int
        실행 시간 (음수=backward)
    output_dir : str
        결과 저장 디렉토리
    """
    print(f"\n{'='*80}")
    print(f"  PyHYSPLIT 실행 중...")
    print(f"{'='*80}")
    print(f"  위치: {lat}°N, {lon}°E")
    print(f"  고도: {height}m AGL")
    print(f"  시작: {start_time.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  기간: {duration_hours}h")
    print(f"{'='*80}\n")
    
    # GFS 데이터 다운로드 (간단한 버전)
    print("GFS 데이터 다운로드 중...")
    
    # 캐시 디렉토리
    cache_dir = Path(output_dir) / "gfs_cache"
    cache_dir.mkdir(exist_ok=True)
    
    # 캐시 파일 이름
    date_str = start_time.strftime("%Y%m%d")
    cache_file = cache_dir / f"gfs_{date_str}_{lat}_{lon}.nc"
    
    if cache_file.exists():
        print(f"✓ 캐시된 GFS 데이터 사용: {cache_file}")
        gfs_file = cache_file
    else:
        print(f"⚠ GFS 데이터 다운로드가 필요하지만 구현되지 않았습니다.")
        print(f"  대신 기존 테스트의 show_pyhysplit_result.py를 참고하여 수동으로 실행하세요.")
        return None
    
    print(f"✓ GFS 데이터: {gfs_file}\n")
    
    # GFS 데이터 로드
    from pyhysplit.met_reader import NetCDFReader
    reader = NetCDFReader()
    met_data = reader.read(str(gfs_file))
    
    # 궤적 설정
    start_loc = StartLocation(
        lat=lat,
        lon=lon,
        height=height
    )
    
    config = SimulationConfig(
        start_time=start_time,
        num_start_locations=1,
        start_locations=[start_loc],
        total_run_hours=duration_hours,
        vertical_motion=0,  # Model vertical velocity
        model_top=10000.0,
        met_files=[],
        turbulence_on=False
    )
    
    # 엔진 실행
    engine = TrajectoryEngine(config, met_data)
    trajectory = engine.run(output_interval_s=3600.0)[0]  # 1시간 간격
    
    print(f"\n✓ PyHYSPLIT 계산 완료")
    print(f"  포인트 수: {len(trajectory)}")
    
    if trajectory:
        # trajectory는 (t, lon, lat, z) 튜플 리스트
        t0, lon0, lat0, z0 = trajectory[0]
        t1, lon1, lat1, z1 = trajectory[-1]
        print(f"  시작점: {lat0:.3f}°N, {lon0:.3f}°E, {z0:.1f}m")
        print(f"  종료점: {lat1:.3f}°N, {lon1:.3f}°E, {z1:.1f}m")
    
    return trajectory


def compare_trajectories(pyhysplit_traj, hysplit_web_data, output_dir: str = "tests/integration"):
    """두 궤적을 비교하고 결과를 출력합니다.
    
    Parameters
    ----------
    pyhysplit_traj : list[tuple]
        PyHYSPLIT 궤적 [(t, lon, lat, z), ...]
    hysplit_web_data : dict
        HYSPLIT Web 데이터
    output_dir : str
        결과 저장 디렉토리
    """
    print(f"\n{'='*80}")
    print(f"  궤적 비교 분석")
    print(f"{'='*80}\n")
    
    # 1. 기본 정보 비교
    print("1. 기본 정보 비교")
    print("-" * 80)
    print(f"  PyHYSPLIT 포인트 수: {len(pyhysplit_traj)}")
    print(f"  HYSPLIT Web 포인트 수: {hysplit_web_data['num_points']}")
    print()
    
    # 2. 시작점 비교
    print("2. 시작점 비교")
    print("-" * 80)
    t0, lon0, lat0, z0 = pyhysplit_traj[0]
    web_start = hysplit_web_data['points'][0]
    
    print(f"  PyHYSPLIT:")
    print(f"    위치: {lat0:.3f}°N, {lon0:.3f}°E")
    print(f"    고도: {z0:.1f}m")
    
    print(f"  HYSPLIT Web:")
    print(f"    위치: {web_start['lat']:.3f}°N, {web_start['lon']:.3f}°E")
    print(f"    고도: {web_start['height']:.1f}m")
    
    lat_diff = abs(lat0 - web_start['lat'])
    lon_diff = abs(lon0 - web_start['lon'])
    height_diff = abs(z0 - web_start['height'])
    
    print(f"  차이:")
    print(f"    위도: {lat_diff:.6f}° ({lat_diff * 111:.2f} km)")
    print(f"    경도: {lon_diff:.6f}° ({lon_diff * 111 * np.cos(np.radians(lat0)):.2f} km)")
    print(f"    고도: {height_diff:.1f}m")
    print()
    
    # 3. 종료점 비교
    print("3. 종료점 비교")
    print("-" * 80)
    t1, lon1, lat1, z1 = pyhysplit_traj[-1]
    web_end = hysplit_web_data['points'][-1]
    
    print(f"  PyHYSPLIT:")
    print(f"    위치: {lat1:.3f}°N, {lon1:.3f}°E")
    print(f"    고도: {z1:.1f}m")
    
    print(f"  HYSPLIT Web:")
    print(f"    위치: {web_end['lat']:.3f}°N, {web_end['lon']:.3f}°E")
    print(f"    고도: {web_end['height']:.1f}m")
    
    lat_diff = abs(lat1 - web_end['lat'])
    lon_diff = abs(lon1 - web_end['lon'])
    height_diff = abs(z1 - web_end['height'])
    
    print(f"  차이:")
    print(f"    위도: {lat_diff:.6f}° ({lat_diff * 111:.2f} km)")
    print(f"    경도: {lon_diff:.6f}° ({lon_diff * 111 * np.cos(np.radians(lat1)):.2f} km)")
    print(f"    고도: {height_diff:.1f}m")
    
    # 수평 거리 계산 (Haversine)
    R = 6371  # 지구 반경 (km)
    dlat = np.radians(web_end['lat'] - lat1)
    dlon = np.radians(web_end['lon'] - lon1)
    a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(web_end['lat'])) * np.sin(dlon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    distance = R * c
    
    print(f"    수평 거리: {distance:.2f} km")
    print()
    
    # 4. 궤적 경로 비교 (중간 포인트들)
    print("4. 궤적 경로 통계")
    print("-" * 80)
    
    # 공통 시간 포인트에서 비교
    min_points = min(len(pyhysplit_traj.points), len(hysplit_web_data['points']))
    
    lat_diffs = []
    lon_diffs = []
    height_diffs = []
    distances = []
    
    for i in range(min_points):
        py_pt = pyhysplit_traj.points[i]
        web_pt = hysplit_web_data['points'][i]
        
        lat_diff = abs(py_pt.lat - web_pt['lat'])
        lon_diff = abs(py_pt.lon - web_pt['lon'])
        height_diff = abs(py_pt.height - web_pt['height'])
        
        # 수평 거리
        dlat = np.radians(web_pt['lat'] - py_pt.lat)
        dlon = np.radians(web_pt['lon'] - py_pt.lon)
        a = np.sin(dlat/2)**2 + np.cos(np.radians(py_pt.lat)) * np.cos(np.radians(web_pt['lat'])) * np.sin(dlon/2)**2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
        dist = R * c
        
        lat_diffs.append(lat_diff)
        lon_diffs.append(lon_diff)
        height_diffs.append(height_diff)
        distances.append(dist)
    
    print(f"  평균 차이 ({min_points}개 포인트):")
    print(f"    위도: {np.mean(lat_diffs):.6f}° (±{np.std(lat_diffs):.6f}°)")
    print(f"    경도: {np.mean(lon_diffs):.6f}° (±{np.std(lon_diffs):.6f}°)")
    print(f"    고도: {np.mean(height_diffs):.1f}m (±{np.std(height_diffs):.1f}m)")
    print(f"    수평 거리: {np.mean(distances):.2f} km (±{np.std(distances):.2f} km)")
    
    print(f"  최대 차이:")
    print(f"    위도: {np.max(lat_diffs):.6f}°")
    print(f"    경도: {np.max(lon_diffs):.6f}°")
    print(f"    고도: {np.max(height_diffs):.1f}m")
    print(f"    수평 거리: {np.max(distances):.2f} km")
    print()
    
    # 5. 시각화
    print("5. 시각화 생성 중...")
    print("-" * 80)
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    
    # (1) 궤적 경로 비교 (위도-경도)
    ax = axes[0, 0]
    py_lats = [pt.lat for pt in pyhysplit_traj.points]
    py_lons = [pt.lon for pt in pyhysplit_traj.points]
    web_lats = [pt['lat'] for pt in hysplit_web_data['points']]
    web_lons = [pt['lon'] for pt in hysplit_web_data['points']]
    
    ax.plot(py_lons, py_lats, 'b-o', label='PyHYSPLIT', markersize=4, linewidth=2)
    ax.plot(web_lons, web_lats, 'r--s', label='HYSPLIT Web', markersize=4, linewidth=2)
    ax.plot(py_lons[0], py_lats[0], 'g*', markersize=15, label='Start')
    ax.set_xlabel('Longitude (°E)', fontsize=12)
    ax.set_ylabel('Latitude (°N)', fontsize=12)
    ax.set_title('Trajectory Path Comparison', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # (2) 고도 변화 비교
    ax = axes[0, 1]
    py_heights = [pt.height for pt in pyhysplit_traj.points]
    web_heights = [pt['height'] for pt in hysplit_web_data['points']]
    py_times = [(pt.time - pyhysplit_traj.points[0].time).total_seconds() / 3600 for pt in pyhysplit_traj.points]
    web_times = [pt['age'] for pt in hysplit_web_data['points']]
    
    ax.plot(py_times, py_heights, 'b-o', label='PyHYSPLIT', markersize=4, linewidth=2)
    ax.plot(web_times, web_heights, 'r--s', label='HYSPLIT Web', markersize=4, linewidth=2)
    ax.set_xlabel('Time (hours)', fontsize=12)
    ax.set_ylabel('Height (m AGL)', fontsize=12)
    ax.set_title('Height Profile Comparison', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # (3) 위치 차이 (시간에 따른)
    ax = axes[1, 0]
    ax.plot(range(min_points), distances, 'g-o', markersize=4, linewidth=2)
    ax.set_xlabel('Point Index', fontsize=12)
    ax.set_ylabel('Horizontal Distance Difference (km)', fontsize=12)
    ax.set_title('Position Difference Over Time', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.axhline(y=np.mean(distances), color='r', linestyle='--', label=f'Mean: {np.mean(distances):.2f} km')
    ax.legend(fontsize=10)
    
    # (4) 고도 차이 (시간에 따른)
    ax = axes[1, 1]
    ax.plot(range(min_points), height_diffs, 'm-o', markersize=4, linewidth=2)
    ax.set_xlabel('Point Index', fontsize=12)
    ax.set_ylabel('Height Difference (m)', fontsize=12)
    ax.set_title('Height Difference Over Time', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.axhline(y=np.mean(height_diffs), color='r', linestyle='--', label=f'Mean: {np.mean(height_diffs):.1f} m')
    ax.legend(fontsize=10)
    
    plt.tight_layout()
    
    output_path = Path(output_dir) / "pyhysplit_vs_hysplit_web_comparison.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"  ✓ 비교 그래프 저장: {output_path}")
    
    plt.close()
    
    # 6. 결론
    print(f"\n{'='*80}")
    print(f"  비교 결론")
    print(f"{'='*80}")
    
    avg_distance = np.mean(distances)
    max_distance = np.max(distances)
    
    if avg_distance < 1.0:
        similarity = "매우 유사"
        color = "🟢"
    elif avg_distance < 5.0:
        similarity = "유사"
        color = "🟡"
    elif avg_distance < 20.0:
        similarity = "보통"
        color = "🟠"
    else:
        similarity = "차이 있음"
        color = "🔴"
    
    print(f"\n  {color} 유사도: {similarity}")
    print(f"  평균 수평 거리 차이: {avg_distance:.2f} km")
    print(f"  최대 수평 거리 차이: {max_distance:.2f} km")
    print(f"  평균 고도 차이: {np.mean(height_diffs):.1f} m")
    print(f"\n{'='*80}\n")
    
    return {
        'avg_distance_km': avg_distance,
        'max_distance_km': max_distance,
        'avg_height_diff_m': np.mean(height_diffs),
        'max_height_diff_m': np.max(height_diffs),
        'similarity': similarity
    }


def main():
    """메인 함수."""
    # 현재 스크립트 위치 기준으로 경로 설정
    script_dir = Path(__file__).parent
    output_dir = str(script_dir)
    
    # 1. HYSPLIT Web 결과 파싱
    print("\n" + "="*80)
    print("  HYSPLIT Web vs PyHYSPLIT 비교")
    print("="*80)
    
    web_endpoints_file = script_dir / "hysplit_trajectory_endpoints.txt"
    
    if not web_endpoints_file.exists():
        print(f"\n❌ HYSPLIT Web 결과 파일을 찾을 수 없습니다: {web_endpoints_file}")
        print("   먼저 hysplit_web_full_automation.py를 실행하세요.")
        return
    
    print(f"\n1. HYSPLIT Web 결과 로드 중...")
    web_data = parse_hysplit_web_endpoints(str(web_endpoints_file))
    print(f"   ✓ {web_data['num_points']}개 포인트 로드")
    
    # 2. PyHYSPLIT 실행 (동일한 조건)
    start_time = datetime(
        web_data['start_year'],
        web_data['start_month'],
        web_data['start_day'],
        web_data['start_hour']
    )
    
    # 실행 시간 계산 (Web 결과의 마지막 포인트 age 사용)
    duration_hours = int(web_data['points'][-1]['age'])
    
    print(f"\n2. PyHYSPLIT 실행 중...")
    pyhysplit_traj = run_pyhysplit_comparison(
        lat=web_data['start_lat'],
        lon=web_data['start_lon'],
        height=web_data['start_height'],
        start_time=start_time,
        duration_hours=duration_hours,
        output_dir=output_dir
    )
    
    if pyhysplit_traj is None:
        print("\n❌ PyHYSPLIT 실행 실패")
        return
    
    # 3. 비교 분석
    print(f"\n3. 결과 비교 중...")
    results = compare_trajectories(pyhysplit_traj, web_data, output_dir)
    
    print("\n✓ 비교 완료!")
    print(f"  결과 이미지: {Path(output_dir) / 'pyhysplit_vs_hysplit_web_comparison.png'}")


if __name__ == "__main__":
    main()
