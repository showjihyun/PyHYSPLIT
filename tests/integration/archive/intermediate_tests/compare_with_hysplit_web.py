"""PyHYSPLIT과 HYSPLIT Web 결과 비교 스크립트.

사용자가 HYSPLIT Web에서 수동으로 실행한 결과를 입력하면,
PyHYSPLIT 결과와 자동으로 비교합니다.

실행:
    python tests/integration/compare_with_hysplit_web.py
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np

from pyhysplit.models import MetData, SimulationConfig, StartLocation
from pyhysplit.engine import TrajectoryEngine


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 지점 간 Haversine 거리 계산 (km)."""
    R = 6371.0  # 지구 반지름 (km)
    
    dlat = np.deg2rad(lat2 - lat1)
    dlon = np.deg2rad(lon2 - lon1)
    
    a = np.sin(dlat/2)**2 + np.cos(np.deg2rad(lat1)) * np.cos(np.deg2rad(lat2)) * np.sin(dlon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    
    return R * c


def download_gfs_data(date_str: str) -> MetData:
    """GFS 데이터 다운로드."""
    import netCDF4
    from pyhysplit.met_reader import convert_omega_to_w
    
    url = f"https://nomads.ncep.noaa.gov/dods/gfs_0p25/gfs{date_str}/gfs_0p25_00z"
    ds = netCDF4.Dataset(url)
    
    try:
        all_lat = np.array(ds.variables["lat"][:])
        all_lon = np.array(ds.variables["lon"][:])
        all_lev = np.array(ds.variables["lev"][:])
        all_time = np.array(ds.variables["time"][:])
        
        lat_range = (20.0, 55.0)
        lon_range = (100.0, 150.0)
        
        lat_mask = (all_lat >= lat_range[0]) & (all_lat <= lat_range[1])
        lon_mask = (all_lon >= lon_range[0]) & (all_lon <= lon_range[1])
        j_start, j_end = np.where(lat_mask)[0][[0, -1]]
        i_start, i_end = np.where(lon_mask)[0][[0, -1]]
        
        lev_indices = list(range(19))
        time_indices = list(range(0, min(17, len(all_time))))
        
        lat_grid = all_lat[j_start:j_end + 1]
        lon_grid = all_lon[i_start:i_end + 1]
        lev_grid = all_lev[lev_indices]
        time_raw = all_time[time_indices]
        t_grid = (time_raw - time_raw[0]) * 86400.0
        
        j_sl = slice(j_start, j_end + 1)
        i_sl = slice(i_start, i_end + 1)
        
        u = np.array(ds.variables["ugrdprs"][time_indices, lev_indices, j_sl, i_sl], dtype=np.float64)
        v = np.array(ds.variables["vgrdprs"][time_indices, lev_indices, j_sl, i_sl], dtype=np.float64)
        omega = np.array(ds.variables["vvelprs"][time_indices, lev_indices, j_sl, i_sl], dtype=np.float64)
        t_field = np.array(ds.variables["tmpprs"][time_indices, lev_indices, j_sl, i_sl], dtype=np.float64)
        hgt = np.array(ds.variables["hgtprs"][time_indices, lev_indices, j_sl, i_sl], dtype=np.float64)
        
        P_3d = np.broadcast_to(
            lev_grid[np.newaxis, :, np.newaxis, np.newaxis] * 100.0,
            omega.shape,
        )
        w = convert_omega_to_w(omega, t_field, P_3d)
        terrain = np.zeros((len(lat_grid), len(lon_grid)))
        
        if len(lev_grid) > 1 and lev_grid[0] > lev_grid[-1]:
            lev_grid = lev_grid[::-1]
            u, v, w = u[:, ::-1], v[:, ::-1], w[:, ::-1]
            t_field, hgt = t_field[:, ::-1], hgt[:, ::-1]
        
        if len(lat_grid) > 1 and lat_grid[0] > lat_grid[-1]:
            lat_grid = lat_grid[::-1]
            u, v, w = u[:, :, ::-1], v[:, :, ::-1], w[:, :, ::-1]
            t_field, hgt = t_field[:, :, ::-1], hgt[:, :, ::-1]
            terrain = terrain[::-1, :]
        
        return MetData(
            u=u, v=v, w=w, t_field=t_field, rh=None, hgt=hgt,
            precip=None, pbl_height=None, terrain=terrain,
            lon_grid=lon_grid, lat_grid=lat_grid,
            z_grid=lev_grid, t_grid=t_grid,
            z_type="pressure", source="GFS_NC",
        )
    finally:
        ds.close()


def run_pyhysplit_trajectory(met: MetData, lat: float, lon: float, height: float, duration: int) -> list[tuple]:
    """PyHYSPLIT 궤적 계산."""
    start = StartLocation(lat=lat, lon=lon, height=height)
    
    config = SimulationConfig(
        start_time=datetime(2026, 2, 13, 0, 0),
        num_start_locations=1,
        start_locations=[start],
        total_run_hours=duration,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[],
        turbulence_on=False,
        dt_max=3600.0,
    )
    
    engine = TrajectoryEngine(config, met)
    return engine.run(output_interval_s=3600.0)[0]


def main():
    """메인 함수."""
    print("\n" + "="*80)
    print("  PyHYSPLIT vs HYSPLIT Web 비교 도구")
    print("="*80)
    
    # 설정
    lat = 37.5
    lon = 127.0
    height = 850.0
    duration = -24
    
    print(f"\n설정:")
    print(f"  위치: {lat}°N, {lon}°E")
    print(f"  고도: {height}m AGL")
    print(f"  기간: {duration}h (backward)")
    print(f"  날짜: 2026-02-13 00:00 UTC")
    
    # PyHYSPLIT 실행
    print(f"\n{'='*80}")
    print("  1. PyHYSPLIT 궤적 계산 중...")
    print(f"{'='*80}")
    
    try:
        print("  GFS 데이터 다운로드 중...")
        met = download_gfs_data("20260213")
        print("  ✓ GFS 데이터 다운로드 완료")
        
        print("  궤적 계산 중...")
        traj = run_pyhysplit_trajectory(met, lat, lon, height, duration)
        print(f"  ✓ 궤적 계산 완료 ({len(traj)} 포인트)")
        
        # PyHYSPLIT 결과 출력
        print(f"\n  PyHYSPLIT 결과:")
        print(f"    시작점: {traj[0][2]:.2f}°N, {traj[0][1]:.2f}°E, {traj[0][3]:.0f}m")
        print(f"    종료점: {traj[-1][2]:.2f}°N, {traj[-1][1]:.2f}°E, {traj[-1][3]:.0f}m")
        print(f"    이동: Δlat={traj[-1][2]-traj[0][2]:+.2f}°, Δlon={traj[-1][1]-traj[0][1]:+.2f}°")
        
    except Exception as e:
        print(f"  ❌ 오류: {e}")
        return
    
    # HYSPLIT Web 결과 입력
    print(f"\n{'='*80}")
    print("  2. HYSPLIT Web 결과 입력")
    print(f"{'='*80}")
    print("\nHYSPLIT Web에서 다음 설정으로 실행하세요:")
    print(f"  URL: https://www.ready.noaa.gov/HYSPLIT_traj.php")
    print(f"  Start Location: {lat}°N, {lon}°E")
    print(f"  Start Height: {int(height)}m AGL")
    print(f"  Start Time: 2026-02-13 00:00 UTC")
    print(f"  Run Duration: {duration}h")
    print(f"  Meteorology: GFS 0.25 degree")
    
    print("\n실행 후 결과 페이지에서 '궤적 종료점' 좌표를 확인하세요.")
    print("(Trajectory Endpoints 테이블 또는 지도에서 확인)")
    
    try:
        print("\n종료점 위도를 입력하세요 (예: 32.5): ", end="")
        web_lat = float(input())
        
        print("종료점 경도를 입력하세요 (예: 107.2): ", end="")
        web_lon = float(input())
        
        print(f"종료점 고도를 입력하세요 (m, 선택, Enter=skip): ", end="")
        web_height_str = input().strip()
        web_height = float(web_height_str) if web_height_str else None
        
    except (ValueError, KeyboardInterrupt):
        print("\n입력이 취소되었습니다.")
        return
    
    # 비교
    print(f"\n{'='*80}")
    print("  3. 결과 비교")
    print(f"{'='*80}")
    
    pyhysplit_end = (traj[-1][2], traj[-1][1], traj[-1][3])
    web_end = (web_lat, web_lon, web_height if web_height else 0)
    
    print(f"\n  PyHYSPLIT 종료점: {pyhysplit_end[0]:.2f}°N, {pyhysplit_end[1]:.2f}°E, {pyhysplit_end[2]:.0f}m")
    print(f"  HYSPLIT Web 종료점: {web_end[0]:.2f}°N, {web_end[1]:.2f}°E", end="")
    if web_height:
        print(f", {web_end[2]:.0f}m")
    else:
        print()
    
    # 거리 계산
    distance = haversine_distance(pyhysplit_end[0], pyhysplit_end[1], web_end[0], web_end[1])
    
    print(f"\n  수평 거리 차이: {distance:.1f} km")
    
    if web_height:
        height_diff = abs(pyhysplit_end[2] - web_end[2])
        print(f"  고도 차이: {height_diff:.0f} m")
    
    # 평가
    print(f"\n  평가:")
    if distance < 50:
        print(f"    ✓ 매우 좋음 (50km 이내)")
    elif distance < 100:
        print(f"    ✓ 좋음 (100km 이내)")
    elif distance < 200:
        print(f"    ⚠ 허용 가능 (200km 이내)")
    else:
        print(f"    ❌ 차이가 큼 (200km 이상)")
        print(f"       설정을 다시 확인하거나 구현 차이를 검토하세요.")
    
    print(f"\n{'='*80}")
    print("  비교 완료!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
