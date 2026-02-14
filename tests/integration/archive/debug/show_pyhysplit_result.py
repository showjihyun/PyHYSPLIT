"""PyHYSPLIT 궤적 결과만 출력하는 스크립트.

HYSPLIT Web과 비교하기 위해 PyHYSPLIT 결과를 먼저 확인합니다.

실행:
    python tests/integration/show_pyhysplit_result.py
"""

from __future__ import annotations

from datetime import datetime

import numpy as np

from pyhysplit.models import MetData, SimulationConfig, StartLocation
from pyhysplit.engine import TrajectoryEngine


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
    print("  PyHYSPLIT 궤적 계산 결과")
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
    print("  PyHYSPLIT 실행 중...")
    print(f"{'='*80}")
    
    try:
        print("\n  GFS 데이터 다운로드 중...")
        met = download_gfs_data("20260213")
        print("  ✓ GFS 데이터 다운로드 완료")
        
        print("  궤적 계산 중...")
        traj = run_pyhysplit_trajectory(met, lat, lon, height, duration)
        print(f"  ✓ 궤적 계산 완료 ({len(traj)} 포인트)")
        
        # 결과 출력
        print(f"\n{'='*80}")
        print("  PyHYSPLIT 궤적 결과")
        print(f"{'='*80}")
        
        print(f"\n  시작점:")
        print(f"    위도: {traj[0][2]:.2f}°N")
        print(f"    경도: {traj[0][1]:.2f}°E")
        print(f"    고도: {traj[0][3]:.0f}m")
        print(f"    시간: t={traj[0][0]/3600:.1f}h")
        
        print(f"\n  종료점:")
        print(f"    위도: {traj[-1][2]:.2f}°N")
        print(f"    경도: {traj[-1][1]:.2f}°E")
        print(f"    고도: {traj[-1][3]:.0f}m")
        print(f"    시간: t={traj[-1][0]/3600:.1f}h")
        
        print(f"\n  이동:")
        print(f"    Δ위도: {traj[-1][2]-traj[0][2]:+.2f}°")
        print(f"    Δ경도: {traj[-1][1]-traj[0][1]:+.2f}°")
        print(f"    Δ고도: {traj[-1][3]-traj[0][3]:+.0f}m")
        
        # 전체 궤적 출력
        print(f"\n  전체 궤적 ({len(traj)} 포인트):")
        print(f"  {'시간(h)':>8} {'위도(°N)':>10} {'경도(°E)':>10} {'고도(m)':>10}")
        print(f"  {'-'*8} {'-'*10} {'-'*10} {'-'*10}")
        for t, lon, lat, z in traj:
            print(f"  {t/3600:8.1f} {lat:10.2f} {lon:10.2f} {z:10.0f}")
        
        # HYSPLIT Web 비교 안내
        print(f"\n{'='*80}")
        print("  HYSPLIT Web과 비교하기")
        print(f"{'='*80}")
        
        print(f"\n  1. HYSPLIT Web 접속:")
        print(f"     https://www.ready.noaa.gov/HYSPLIT_traj.php")
        
        print(f"\n  2. 다음 설정으로 실행:")
        print(f"     Start Location: {lat}°N, {lon}°E")
        print(f"     Start Height: {int(height)}m AGL")
        print(f"     Start Time: 2026-02-13 00:00 UTC")
        print(f"     Run Duration: {duration}h")
        print(f"     Meteorology: GFS 0.25 degree")
        
        print(f"\n  3. 결과 비교:")
        print(f"     - PyHYSPLIT 종료점: {traj[-1][2]:.2f}°N, {traj[-1][1]:.2f}°E")
        print(f"     - HYSPLIT Web 종료점과 비교")
        print(f"     - 50~100km 차이는 정상 범위")
        
        print(f"\n{'='*80}\n")
        
    except Exception as e:
        print(f"\n  ❌ 오류: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
