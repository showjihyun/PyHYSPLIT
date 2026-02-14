"""PyHYSPLIT과 HYSPLIT Web 결과 비교 테스트.

HYSPLIT Web 자동화로 얻은 결과와 PyHYSPLIT 결과를 비교합니다.

실행:
    python tests/integration/test_hysplit_web_comparison.py
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from pyhysplit.engine import TrajectoryEngine
from pyhysplit.models import MetData, SimulationConfig, StartLocation


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 지점 간 Haversine 거리 계산 (km)."""
    R = 6371.0
    dlat = np.deg2rad(lat2 - lat1)
    dlon = np.deg2rad(lon2 - lon1)
    a = np.sin(dlat/2)**2 + np.cos(np.deg2rad(lat1)) * np.cos(np.deg2rad(lat2)) * np.sin(dlon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    return R * c


def parse_hysplit_web_result(filepath: Path) -> list[dict]:
    """HYSPLIT Web trajectory endpoints 파일 파싱."""
    points = []
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # 데이터 라인 찾기 (첫 번째 필드가 1이고 두 번째 필드도 1인 라인)
    for line in lines:
        parts = line.strip().split()
        if len(parts) == 13 and parts[0] == '1' and parts[1] == '1':
            try:
                # 형식: traj# met# year month day hour min fhour age lat lon height pressure
                # 인덱스: 0     1    2    3     4   5    6   7     8   9   10  11     12
                year = int(parts[2])
                month = int(parts[3])
                day = int(parts[4])
                hour = int(parts[5])
                lat = float(parts[9])
                lon = float(parts[10])
                height = float(parts[11])
                
                dt = datetime(2000 + year, month, day, hour, 0)
                points.append({
                    'time': dt,
                    'lat': lat,
                    'lon': lon,
                    'height': height
                })
            except (ValueError, IndexError) as e:
                print(f"파싱 오류: {e}, line: {line}")
                continue
    
    return points


def load_cached_gfs_data(cache_file: Path) -> MetData | None:
    """캐시된 GFS 데이터 로드."""
    if not cache_file.exists():
        return None
    
    import netCDF4
    
    ds = netCDF4.Dataset(str(cache_file))
    
    lat_grid = np.array(ds.variables["lat"][:])
    lon_grid = np.array(ds.variables["lon"][:])
    lev_grid = np.array(ds.variables["lev"][:])
    t_grid = np.array(ds.variables["time"][:])
    
    u_data = np.array(ds.variables["u"][:])
    v_data = np.array(ds.variables["v"][:])
    omega_data = np.array(ds.variables["w"][:])  # This is omega (Pa/s) from GFS
    t_data = np.array(ds.variables["t"][:])
    
    ds.close()
    
    # IMPORTANT: GFS provides omega (Pa/s), but HYSPLIT expects it in a specific way
    # After testing, we found that using omega directly (scaled to hPa/s) works better
    # than converting to w (m/s) first.
    # 
    # The integrator will handle the conversion from omega to dP/dt correctly.
    print("  Using omega (Pa/s) directly, scaled to hPa/s...")
    
    # Scale omega from Pa/s to hPa/s for consistency with pressure grid (hPa)
    w_hpa_s = omega_data / 100.0  # Pa/s → hPa/s
    
    print(f"  Omega range: {omega_data.min():.3f} to {omega_data.max():.3f} Pa/s")
    print(f"  Scaled to: {w_hpa_s.min():.3f} to {w_hpa_s.max():.3f} hPa/s")
    
    return MetData(
        u=u_data,
        v=v_data,
        w=w_hpa_s,  # Now in hPa/s (omega scaled)
        t_field=t_data,
        lat_grid=lat_grid,
        lon_grid=lon_grid,
        z_grid=lev_grid,
        t_grid=t_grid,
        z_type="pressure",
        source="GFS_NC"
    )


def run_pyhysplit(met_data: MetData, start_time: datetime, lat: float, lon: float, 
                  height: float, duration_hours: int) -> list[tuple]:
    """PyHYSPLIT 궤적 계산."""
    # StartLocation.height는 항상 meters AGL로 전달해야 함
    # TrajectoryEngine이 자동으로 MetData 좌표계로 변환함
    print(f"  시작 고도: {height}m AGL (엔진이 자동으로 좌표 변환 수행)")
    
    start_loc = StartLocation(lat=lat, lon=lon, height=height)
    
    config = SimulationConfig(
        start_time=start_time,
        num_start_locations=1,
        start_locations=[start_loc],
        total_run_hours=duration_hours,
        vertical_motion=8,  # Mode 8: Damping based on data frequency and grid size
        model_top=10000.0,
        met_files=[],
        turbulence_on=False,
        dt_max=15.0  # 15초 최대 타임스텝 (더 높은 정확도)
    )
    
    print(f"  Config: total_run_hours={config.total_run_hours}, start_time={start_time}")
    print(f"  Met data: t_grid range = {met_data.t_grid[0]:.1f} ~ {met_data.t_grid[-1]:.1f} seconds")
    print(f"  Met data: z_type = {met_data.z_type}, z_grid range = {met_data.z_grid[0]:.1f} ~ {met_data.z_grid[-1]:.1f}")
    
    # 로깅 활성화
    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
    
    engine = TrajectoryEngine(config, met_data)
    
    print(f"  Engine: _total_seconds={engine._total_seconds}, _direction={engine._direction}")
    print(f"  Engine: is_forward={engine.is_forward}")
    
    trajectory = engine.run(output_interval_s=3600.0)[0]
    
    print(f"  Trajectory points: {len(trajectory)}")
    if trajectory:
        print(f"  First point: t={trajectory[0][0]:.1f}s, lat={trajectory[0][2]:.3f}, lon={trajectory[0][1]:.3f}")
        print(f"  Last point: t={trajectory[-1][0]:.1f}s, lat={trajectory[-1][2]:.3f}, lon={trajectory[-1][1]:.3f}")
    
    # 튜플을 dict로 변환
    # 튜플 형식: (t_seconds, lon, lat, height)
    # height는 met_data.z_type에 따라 압력 (hPa) 또는 고도 (m)
    result = []
    base_time = datetime(start_time.year, start_time.month, start_time.day, 0, 0)  # 00:00 UTC
    for pt in trajectory:
        t_seconds, lon_val, lat_val, height_val = pt
        # t_seconds는 00:00 UTC부터의 초
        dt = base_time + timedelta(seconds=t_seconds)
        
        # 압력을 고도로 변환
        if met_data.z_type == "pressure":
            from pyhysplit.coordinate_converter import CoordinateConverter
            from pyhysplit.interpolator import Interpolator
            
            # height_val은 hPa, Pa로 변환
            height_pa = height_val * 100.0
            
            # 온도 필드가 있으면 온도 기반 변환 사용 (더 정확함)
            if met_data.t_field is not None:
                try:
                    # 현재 위치의 온도 보간
                    interp = Interpolator(met_data)
                    T = interp.interpolate_scalar(met_data.t_field, lon_val, lat_val, height_val, t_seconds)
                    # Hypsometric equation 사용 (가장 정확)
                    height_m = CoordinateConverter.pressure_to_height_hypsometric(
                        np.array([height_pa]), np.array([T])
                    )[0]
                except Exception as e:
                    # 실패하면 표준 대기 공식 사용
                    height_m = CoordinateConverter.pressure_to_height(np.array([height_pa]))[0]
            else:
                # 표준 대기 공식 사용
                height_m = CoordinateConverter.pressure_to_height(np.array([height_pa]))[0]
        else:
            height_m = height_val
        
        result.append({
            'time': dt,
            'lat': lat_val,
            'lon': lon_val,
            'height': height_m
        })
    
    return result


def compare_trajectories(pyhysplit_traj: list[dict], web_traj: list[dict]) -> dict:
    """두 궤적 비교."""
    comparison = {
        'point_distances': [],
        'height_diffs': [],
        'lat_diffs': [],
        'lon_diffs': [],
        'mean_distance': 0.0,
        'max_distance': 0.0,
        'mean_height_diff': 0.0,
        'max_height_diff': 0.0
    }
    
    # 포인트별 비교
    min_len = min(len(pyhysplit_traj), len(web_traj))
    
    for i in range(min_len):
        py_pt = pyhysplit_traj[i]
        web_pt = web_traj[i]
        
        # 수평 거리
        dist = haversine_distance(py_pt['lat'], py_pt['lon'], web_pt['lat'], web_pt['lon'])
        comparison['point_distances'].append(dist)
        
        # 고도 차이
        height_diff = abs(py_pt['height'] - web_pt['height'])
        comparison['height_diffs'].append(height_diff)
        
        # 위도/경도 차이
        comparison['lat_diffs'].append(py_pt['lat'] - web_pt['lat'])
        comparison['lon_diffs'].append(py_pt['lon'] - web_pt['lon'])
    
    # 통계
    if comparison['point_distances']:
        comparison['mean_distance'] = np.mean(comparison['point_distances'])
        comparison['max_distance'] = np.max(comparison['point_distances'])
        comparison['mean_height_diff'] = np.mean(comparison['height_diffs'])
        comparison['max_height_diff'] = np.max(comparison['height_diffs'])
    
    return comparison


def visualize_comparison(pyhysplit_traj: list[dict], web_traj: list[dict], 
                        comparison: dict, output_path: Path):
    """비교 결과 시각화."""
    fig = plt.figure(figsize=(18, 12))
    
    # (1) 궤적 경로 오버레이
    ax1 = plt.subplot(2, 3, 1)
    py_lats = [pt['lat'] for pt in pyhysplit_traj]
    py_lons = [pt['lon'] for pt in pyhysplit_traj]
    web_lats = [pt['lat'] for pt in web_traj]
    web_lons = [pt['lon'] for pt in web_traj]
    
    ax1.plot(py_lons, py_lats, 'b-o', markersize=6, linewidth=2, label='PyHYSPLIT', alpha=0.7)
    ax1.plot(web_lons, web_lats, 'r-s', markersize=6, linewidth=2, label='HYSPLIT Web', alpha=0.7)
    ax1.plot(py_lons[0], py_lats[0], 'g*', markersize=20, label='Start', zorder=5)
    ax1.set_xlabel('Longitude (°E)', fontsize=11)
    ax1.set_ylabel('Latitude (°N)', fontsize=11)
    ax1.set_title('Trajectory Comparison', fontsize=13, fontweight='bold')
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)
    
    # (2) 고도 프로파일
    ax2 = plt.subplot(2, 3, 2)
    py_heights = [pt['height'] for pt in pyhysplit_traj]
    web_heights = [pt['height'] for pt in web_traj]
    py_hours = list(range(len(pyhysplit_traj)))
    web_hours = list(range(len(web_traj)))
    
    ax2.plot(py_hours, py_heights, 'b-o', markersize=6, linewidth=2, label='PyHYSPLIT', alpha=0.7)
    ax2.plot(web_hours, web_heights, 'r-s', markersize=6, linewidth=2, label='HYSPLIT Web', alpha=0.7)
    ax2.set_xlabel('Time (hours)', fontsize=11)
    ax2.set_ylabel('Height (m AGL)', fontsize=11)
    ax2.set_title('Height Profile Comparison', fontsize=13, fontweight='bold')
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)
    
    # (3) 수평 거리 차이
    ax3 = plt.subplot(2, 3, 3)
    distances = comparison['point_distances']
    ax3.plot(range(len(distances)), distances, 'g-o', markersize=6, linewidth=2)
    ax3.axhline(y=comparison['mean_distance'], color='r', linestyle='--', 
                label=f'Mean: {comparison["mean_distance"]:.1f} km')
    ax3.set_xlabel('Point Index', fontsize=11)
    ax3.set_ylabel('Distance (km)', fontsize=11)
    ax3.set_title('Horizontal Distance Difference', fontsize=13, fontweight='bold')
    ax3.legend(fontsize=9)
    ax3.grid(True, alpha=0.3)
    
    # (4) 고도 차이
    ax4 = plt.subplot(2, 3, 4)
    height_diffs = comparison['height_diffs']
    ax4.plot(range(len(height_diffs)), height_diffs, 'm-o', markersize=6, linewidth=2)
    ax4.axhline(y=comparison['mean_height_diff'], color='r', linestyle='--',
                label=f'Mean: {comparison["mean_height_diff"]:.1f} m')
    ax4.set_xlabel('Point Index', fontsize=11)
    ax4.set_ylabel('Height Difference (m)', fontsize=11)
    ax4.set_title('Height Difference', fontsize=13, fontweight='bold')
    ax4.legend(fontsize=9)
    ax4.grid(True, alpha=0.3)
    
    # (5) 위도 차이
    ax5 = plt.subplot(2, 3, 5)
    lat_diffs = comparison['lat_diffs']
    ax5.plot(range(len(lat_diffs)), lat_diffs, 'c-o', markersize=6, linewidth=2)
    ax5.axhline(y=0, color='k', linestyle='-', alpha=0.3)
    ax5.set_xlabel('Point Index', fontsize=11)
    ax5.set_ylabel('Latitude Difference (°)', fontsize=11)
    ax5.set_title('Latitude Difference (PyHYSPLIT - Web)', fontsize=13, fontweight='bold')
    ax5.grid(True, alpha=0.3)
    
    # (6) 경도 차이
    ax6 = plt.subplot(2, 3, 6)
    lon_diffs = comparison['lon_diffs']
    ax6.plot(range(len(lon_diffs)), lon_diffs, 'y-o', markersize=6, linewidth=2)
    ax6.axhline(y=0, color='k', linestyle='-', alpha=0.3)
    ax6.set_xlabel('Point Index', fontsize=11)
    ax6.set_ylabel('Longitude Difference (°)', fontsize=11)
    ax6.set_title('Longitude Difference (PyHYSPLIT - Web)', fontsize=13, fontweight='bold')
    ax6.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def main():
    """메인 함수."""
    script_dir = Path(__file__).parent
    
    print(f"\n{'='*80}")
    print(f"  PyHYSPLIT vs HYSPLIT Web 비교 테스트")
    print(f"{'='*80}\n")
    
    # 조건
    start_time = datetime(2026, 2, 13, 13, 0)
    lat = 37.5
    lon = 127.0
    height = 850.0
    duration_hours = -7
    
    print(f"테스트 조건:")
    print(f"  시작 시간: {start_time.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  위치: {lat}°N, {lon}°E")
    print(f"  고도: {height}m AGL")
    print(f"  기간: {duration_hours}h (backward)")
    print()
    
    # 1. HYSPLIT Web 결과 로드
    print(f"{'='*80}")
    print(f"  1. HYSPLIT Web 결과 로드")
    print(f"{'='*80}\n")
    
    web_result_file = script_dir / "hysplit_trajectory_endpoints.txt"
    if not web_result_file.exists():
        print(f"❌ HYSPLIT Web 결과 파일이 없습니다: {web_result_file}")
        return
    
    web_traj = parse_hysplit_web_result(web_result_file)
    print(f"✓ HYSPLIT Web 결과 로드 완료")
    print(f"  포인트 수: {len(web_traj)}")
    print(f"  시작점: {web_traj[0]['lat']:.3f}°N, {web_traj[0]['lon']:.3f}°E, {web_traj[0]['height']:.1f}m")
    print(f"  종료점: {web_traj[-1]['lat']:.3f}°N, {web_traj[-1]['lon']:.3f}°E, {web_traj[-1]['height']:.1f}m")
    
    # 2. PyHYSPLIT 실행
    print(f"\n{'='*80}")
    print(f"  2. PyHYSPLIT 실행")
    print(f"{'='*80}\n")
    
    cache_file = script_dir / "gfs_cache" / f"gfs_20260213_{lat}_{lon}_1h.nc"
    if not cache_file.exists():
        print(f"❌ GFS 캐시 파일이 없습니다: {cache_file}")
        print(f"   먼저 interpolate_gfs_time.py를 실행하세요.")
        return
    
    met_data = load_cached_gfs_data(cache_file)
    if met_data is None:
        print(f"❌ GFS 데이터 로드 실패")
        return
    
    print(f"✓ GFS 데이터 로드 완료 (캐시)")
    
    print(f"  PyHYSPLIT 엔진 실행 중...")
    pyhysplit_traj = run_pyhysplit(met_data, start_time, lat, lon, height, duration_hours)
    
    print(f"✓ PyHYSPLIT 계산 완료")
    print(f"  포인트 수: {len(pyhysplit_traj)}")
    print(f"  시작점: {pyhysplit_traj[0]['lat']:.3f}°N, {pyhysplit_traj[0]['lon']:.3f}°E, {pyhysplit_traj[0]['height']:.1f}m")
    print(f"  종료점: {pyhysplit_traj[-1]['lat']:.3f}°N, {pyhysplit_traj[-1]['lon']:.3f}°E, {pyhysplit_traj[-1]['height']:.1f}m")
    
    # 3. 비교
    print(f"\n{'='*80}")
    print(f"  3. 결과 비교")
    print(f"{'='*80}\n")
    
    comparison = compare_trajectories(pyhysplit_traj, web_traj)
    
    print(f"통계:")
    print(f"  평균 수평 거리 차이: {comparison['mean_distance']:.2f} km")
    print(f"  최대 수평 거리 차이: {comparison['max_distance']:.2f} km")
    print(f"  평균 고도 차이: {comparison['mean_height_diff']:.1f} m")
    print(f"  최대 고도 차이: {comparison['max_height_diff']:.1f} m")
    
    # 평가
    print(f"\n평가:")
    if comparison['mean_distance'] < 10:
        print(f"  ✓ 매우 우수 (평균 10km 이내)")
    elif comparison['mean_distance'] < 50:
        print(f"  ✓ 우수 (평균 50km 이내)")
    elif comparison['mean_distance'] < 100:
        print(f"  ✓ 양호 (평균 100km 이내)")
    elif comparison['mean_distance'] < 200:
        print(f"  ⚠ 허용 가능 (평균 200km 이내)")
    else:
        print(f"  ❌ 차이가 큼 (평균 200km 이상)")
    
    # 4. 시각화
    print(f"\n{'='*80}")
    print(f"  4. 시각화 생성")
    print(f"{'='*80}\n")
    
    output_path = script_dir / "comparison_visualization.png"
    visualize_comparison(pyhysplit_traj, web_traj, comparison, output_path)
    print(f"✓ 시각화 저장: {output_path}")
    
    # 5. 상세 비교 리포트
    print(f"\n{'='*80}")
    print(f"  5. 상세 비교 리포트")
    print(f"{'='*80}\n")
    
    report_path = script_dir / "HYSPLIT_WEB_COMPARISON.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# PyHYSPLIT vs HYSPLIT Web 비교 리포트\n\n")
        f.write(f"## 테스트 조건\n\n")
        f.write(f"- 시작 시간: {start_time.strftime('%Y-%m-%d %H:%M UTC')}\n")
        f.write(f"- 위치: {lat}°N, {lon}°E\n")
        f.write(f"- 고도: {height}m AGL\n")
        f.write(f"- 기간: {duration_hours}h (backward)\n")
        f.write(f"- Meteorology: GFS 0.25 Degree\n")
        f.write(f"- Vertical Motion: Model Vertical Velocity\n\n")
        
        f.write(f"## 결과 요약\n\n")
        f.write(f"### HYSPLIT Web\n")
        f.write(f"- 포인트 수: {len(web_traj)}\n")
        f.write(f"- 시작점: {web_traj[0]['lat']:.3f}°N, {web_traj[0]['lon']:.3f}°E, {web_traj[0]['height']:.1f}m\n")
        f.write(f"- 종료점: {web_traj[-1]['lat']:.3f}°N, {web_traj[-1]['lon']:.3f}°E, {web_traj[-1]['height']:.1f}m\n\n")
        
        f.write(f"### PyHYSPLIT\n")
        f.write(f"- 포인트 수: {len(pyhysplit_traj)}\n")
        f.write(f"- 시작점: {pyhysplit_traj[0]['lat']:.3f}°N, {pyhysplit_traj[0]['lon']:.3f}°E, {pyhysplit_traj[0]['height']:.1f}m\n")
        f.write(f"- 종료점: {pyhysplit_traj[-1]['lat']:.3f}°N, {pyhysplit_traj[-1]['lon']:.3f}°E, {pyhysplit_traj[-1]['height']:.1f}m\n\n")
        
        f.write(f"## 비교 통계\n\n")
        f.write(f"| 항목 | 값 |\n")
        f.write(f"|------|------|\n")
        f.write(f"| 평균 수평 거리 차이 | {comparison['mean_distance']:.2f} km |\n")
        f.write(f"| 최대 수평 거리 차이 | {comparison['max_distance']:.2f} km |\n")
        f.write(f"| 평균 고도 차이 | {comparison['mean_height_diff']:.1f} m |\n")
        f.write(f"| 최대 고도 차이 | {comparison['max_height_diff']:.1f} m |\n\n")
        
        f.write(f"## 포인트별 상세 비교\n\n")
        f.write(f"| 시간 | PyHYSPLIT (Lat, Lon, Height) | HYSPLIT Web (Lat, Lon, Height) | 거리 차이 (km) | 고도 차이 (m) |\n")
        f.write(f"|------|-------------------------------|--------------------------------|----------------|---------------|\n")
        
        for i in range(min(len(pyhysplit_traj), len(web_traj))):
            py_pt = pyhysplit_traj[i]
            web_pt = web_traj[i]
            dist = comparison['point_distances'][i]
            h_diff = comparison['height_diffs'][i]
            
            f.write(f"| {py_pt['time'].strftime('%H:%M')} | ")
            f.write(f"{py_pt['lat']:.3f}°N, {py_pt['lon']:.3f}°E, {py_pt['height']:.1f}m | ")
            f.write(f"{web_pt['lat']:.3f}°N, {web_pt['lon']:.3f}°E, {web_pt['height']:.1f}m | ")
            f.write(f"{dist:.2f} | {h_diff:.1f} |\n")
        
        f.write(f"\n## 시각화\n\n")
        f.write(f"![Comparison Visualization](comparison_visualization.png)\n\n")
        
        f.write(f"## 결론\n\n")
        if comparison['mean_distance'] < 50:
            f.write(f"PyHYSPLIT과 HYSPLIT Web의 결과가 매우 유사합니다 (평균 {comparison['mean_distance']:.2f}km 차이).\n")
            f.write(f"구현이 HYSPLIT과 높은 일치도를 보입니다.\n")
        elif comparison['mean_distance'] < 100:
            f.write(f"PyHYSPLIT과 HYSPLIT Web의 결과가 양호한 일치도를 보입니다 (평균 {comparison['mean_distance']:.2f}km 차이).\n")
            f.write(f"일반적인 궤적 모델링 용도로 사용 가능합니다.\n")
        else:
            f.write(f"PyHYSPLIT과 HYSPLIT Web의 결과에 차이가 있습니다 (평균 {comparison['mean_distance']:.2f}km 차이).\n")
            f.write(f"추가 검증이 필요할 수 있습니다.\n")
    
    print(f"✓ 리포트 저장: {report_path}")
    
    print(f"\n{'='*80}")
    print(f"  비교 테스트 완료!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
