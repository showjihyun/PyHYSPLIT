"""PyHYSPLIT을 HYSPLIT Web과 동일한 조건으로 실행.

HYSPLIT Web 결과와 비교하기 위해 동일한 조건으로 PyHYSPLIT을 실행합니다.

실행:
    python tests/integration/run_pyhysplit_for_comparison.py
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from pyhysplit.engine import TrajectoryEngine
from pyhysplit.models import MetData, SimulationConfig, StartLocation


def download_gfs_data_for_comparison(
    start_time: datetime,
    lat: float,
    lon: float,
    duration_hours: int,
    cache_dir: Path
) -> MetData | None:
    """GFS 데이터를 다운로드합니다."""
    import netCDF4
    from pyhysplit.met_reader import convert_omega_to_w
    
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # 캐시 파일 이름
    date_str = start_time.strftime("%Y%m%d")
    cache_file = cache_dir / f"gfs_{date_str}_{lat}_{lon}.nc"
    
    if cache_file.exists():
        print(f"✓ 캐시된 GFS 데이터 사용: {cache_file}")
        # 캐시된 파일에서 MetData 로드
        import netCDF4
        ds = netCDF4.Dataset(str(cache_file))
        
        lat_grid = np.array(ds.variables["lat"][:])
        lon_grid = np.array(ds.variables["lon"][:])
        lev_grid = np.array(ds.variables["lev"][:])
        t_grid = np.array(ds.variables["time"][:])
        
        u_data = np.array(ds.variables["u"][:])
        v_data = np.array(ds.variables["v"][:])
        w_data = np.array(ds.variables["w"][:])
        t_data = np.array(ds.variables["t"][:])
        
        ds.close()
        
        return MetData(
            u=u_data,
            v=v_data,
            w=w_data,
            t_field=t_data,
            lat_grid=lat_grid,
            lon_grid=lon_grid,
            z_grid=lev_grid,
            t_grid=t_grid,
            z_type="pressure",
            source="GFS_NC"
        )
    
    # GFS 데이터 다운로드
    print(f"GFS 데이터 다운로드 중... (날짜: {date_str})")
    
    url = f"https://nomads.ncep.noaa.gov/dods/gfs_0p25/gfs{date_str}/gfs_0p25_00z"
    
    try:
        ds = netCDF4.Dataset(url)
    except Exception as e:
        print(f"❌ GFS 데이터 접속 실패: {e}")
        return None
    
    try:
        all_lat = np.array(ds.variables["lat"][:])
        all_lon = np.array(ds.variables["lon"][:])
        all_lev = np.array(ds.variables["lev"][:])
        all_time = np.array(ds.variables["time"][:])
        
        # 관심 영역 설정 (서울 주변)
        lat_range = (30.0, 45.0)
        lon_range = (120.0, 135.0)
        
        lat_mask = (all_lat >= lat_range[0]) & (all_lat <= lat_range[1])
        lon_mask = (all_lon >= lon_range[0]) & (all_lon <= lon_range[1])
        j_start, j_end = np.where(lat_mask)[0][[0, -1]]
        i_start, i_end = np.where(lon_mask)[0][[0, -1]]
        
        # 압력 레벨 선택 (상위 19개)
        lev_indices = list(range(19))
        
        # 시간 선택: start_time 기준으로 backward 범위
        # start_time = 13:00 UTC, duration = -7h
        # 필요한 시간 범위: 6:00 ~ 15:00 UTC (여유있게)
        # GFS 시간 인덱스: 6:00 = 인덱스 2, 15:00 = 인덱스 5 (3시간 간격)
        start_hour = start_time.hour
        duration_hours_abs = abs(duration_hours) if duration_hours < 0 else duration_hours
        
        # 시작 시간 인덱스 (3시간 간격)
        start_idx = start_hour // 3
        # backward이므로 start_idx - duration_hours//3 부터 start_idx+1까지
        end_idx = start_idx + 2  # 여유있게 +2
        begin_idx = max(0, start_idx - duration_hours_abs // 3 - 1)  # 여유있게 -1
        
        time_indices = list(range(begin_idx, min(end_idx, len(all_time))))
        
        print(f"  시간 인덱스: {time_indices} (시작={start_hour}h, 기간={duration_hours_abs}h)")
        
        lat_grid = all_lat[j_start:j_end + 1]
        lon_grid = all_lon[i_start:i_end + 1]
        lev_grid = all_lev[lev_indices]
        time_raw = all_time[time_indices]
        
        # t_grid를 start_time을 기준으로 설정
        # time_raw[0]은 begin_idx 시간 (예: 3:00 UTC)
        # start_time은 13:00 UTC
        # t_grid를 조정하여 start_time이 특정 위치에 오도록 설정
        # backward의 경우 t_grid[-1]이 start_time이 되어야 함
        
        # 각 time_raw의 실제 시간(시)을 계산
        hours_from_00z = np.array([begin_idx + i * 3 for i in range(len(time_indices))])
        
        # start_time (13:00)을 기준으로 상대 시간(초) 계산
        t_grid = (hours_from_00z - start_hour) * 3600.0
        
        # backward의 경우 t_grid를 역순으로 만들어서 t_grid[-1]이 0 (start_time)이 되도록
        # 예: [3h, 6h, 9h, 12h, 15h] - 13h = [-10h, -7h, -4h, -1h, +2h]
        # backward이므로 역순: [+2h, -1h, -4h, -7h, -10h]
        # 하지만 엔진은 t_grid가 증가하는 순서를 기대하므로, 데이터를 역순으로 만들어야 함
        
        # 간단한 방법: t_grid를 그대로 두고, start_time에 가장 가까운 인덱스를 찾음
        # 13:00에 가장 가까운 인덱스는 12:00 (인덱스 4)
        closest_idx = np.argmin(np.abs(hours_from_00z - start_hour))
        
        # t_grid를 closest_idx를 기준으로 재조정
        # closest_idx가 마지막이 되도록 데이터를 자름
        time_indices = time_indices[:closest_idx + 1]
        time_raw = time_raw[:closest_idx + 1]
        hours_from_00z = hours_from_00z[:closest_idx + 1]
        t_grid = (hours_from_00z - hours_from_00z[0]) * 3600.0  # 0부터 시작
        
        print(f"  조정된 시간 인덱스: {time_indices}, hours: {hours_from_00z}")
        print(f"  t_grid: {t_grid}")
        
        j_sl = slice(j_start, j_end + 1)
        i_sl = slice(i_start, i_end + 1)
        
        print(f"  영역: lat {lat_grid[0]:.2f}~{lat_grid[-1]:.2f}, lon {lon_grid[0]:.2f}~{lon_grid[-1]:.2f}")
        print(f"  레벨: {len(lev_grid)}개, 시간: {len(time_indices)}개")
        
        # 데이터 다운로드
        u_data = np.array(ds.variables["ugrdprs"][time_indices, lev_indices, j_sl, i_sl])
        v_data = np.array(ds.variables["vgrdprs"][time_indices, lev_indices, j_sl, i_sl])
        omega_data = np.array(ds.variables["vvelprs"][time_indices, lev_indices, j_sl, i_sl])
        t_data = np.array(ds.variables["tmpprs"][time_indices, lev_indices, j_sl, i_sl])
        
        ds.close()
        
        # Omega를 w로 변환
        w_data = convert_omega_to_w(omega_data, t_data, lev_grid[np.newaxis, :, np.newaxis, np.newaxis])
        
        print(f"✓ GFS 데이터 다운로드 완료")
        
        # z_grid(기압면)가 오름차순이어야 보간기가 동작함
        # GFS는 1000→200 내림차순이므로 뒤집기
        if len(lev_grid) > 1 and lev_grid[0] > lev_grid[-1]:
            lev_grid = lev_grid[::-1]
            u_data = u_data[:, ::-1, :, :]
            v_data = v_data[:, ::-1, :, :]
            w_data = w_data[:, ::-1, :, :]
            t_data = t_data[:, ::-1, :, :]
            print(f"  z_grid 역순 변환: {lev_grid[0]:.1f} → {lev_grid[-1]:.1f} hPa")
        
        # 캐시 저장
        print(f"  캐시 저장 중: {cache_file}")
        ds_out = netCDF4.Dataset(str(cache_file), 'w', format='NETCDF4')
        
        ds_out.createDimension('time', len(t_grid))
        ds_out.createDimension('lev', len(lev_grid))
        ds_out.createDimension('lat', len(lat_grid))
        ds_out.createDimension('lon', len(lon_grid))
        
        var_time = ds_out.createVariable('time', 'f8', ('time',))
        var_lev = ds_out.createVariable('lev', 'f4', ('lev',))
        var_lat = ds_out.createVariable('lat', 'f4', ('lat',))
        var_lon = ds_out.createVariable('lon', 'f4', ('lon',))
        var_u = ds_out.createVariable('u', 'f4', ('time', 'lev', 'lat', 'lon'))
        var_v = ds_out.createVariable('v', 'f4', ('time', 'lev', 'lat', 'lon'))
        var_w = ds_out.createVariable('w', 'f4', ('time', 'lev', 'lat', 'lon'))
        var_t = ds_out.createVariable('t', 'f4', ('time', 'lev', 'lat', 'lon'))
        
        var_time[:] = t_grid
        var_lev[:] = lev_grid
        var_lat[:] = lat_grid
        var_lon[:] = lon_grid
        var_u[:] = u_data
        var_v[:] = v_data
        var_w[:] = w_data
        var_t[:] = t_data
        
        ds_out.close()
        print(f"✓ 캐시 저장 완료")
        
        return MetData(
            u=u_data,
            v=v_data,
            w=w_data,
            t_field=t_data,
            lat_grid=lat_grid,
            lon_grid=lon_grid,
            z_grid=lev_grid,
            t_grid=t_grid,
            z_type="pressure",
            source="GFS_NC"
        )
        
    except Exception as e:
        print(f"❌ GFS 데이터 처리 실패: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_pyhysplit_comparison():
    """PyHYSPLIT을 HYSPLIT Web과 동일한 조건으로 실행합니다."""
    script_dir = Path(__file__).parent
    
    print(f"\n{'='*80}")
    print(f"  PyHYSPLIT 실행 (HYSPLIT Web 조건)")
    print(f"{'='*80}\n")
    
    # HYSPLIT Web 조건
    start_time = datetime(2026, 2, 13, 13, 0)  # 2026-02-13 13:00 UTC
    lat = 37.5
    lon = 127.0
    height = 850.0  # m AGL
    duration_hours = -7  # 7시간 backward
    
    print(f"조건:")
    print(f"  시작 시간: {start_time.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  위치: {lat}°N, {lon}°E")
    print(f"  고도: {height}m AGL")
    print(f"  기간: {duration_hours}h (backward)")
    print()
    
    # GFS 데이터 다운로드
    cache_dir = script_dir / "gfs_cache"
    met_data = download_gfs_data_for_comparison(start_time, lat, lon, duration_hours, cache_dir)
    
    if met_data is None:
        print("\n❌ GFS 데이터 다운로드 실패")
        return None
    
    # 시뮬레이션 설정
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
    print("\nPyHYSPLIT 엔진 실행 중...")
    engine = TrajectoryEngine(config, met_data)
    trajectory = engine.run(output_interval_s=3600.0)[0]  # 1시간 간격 출력
    
    if not trajectory or len(trajectory) == 0:
        print("❌ 궤적 계산 실패")
        return None
    
    print(f"\n✓ PyHYSPLIT 계산 완료")
    print(f"  포인트 수: {len(trajectory)}")
    
    # 튜플 형식: (t_seconds, lon, lat, height)
    print(f"  시작점: {trajectory[0][2]:.3f}°N, {trajectory[0][1]:.3f}°E, {trajectory[0][3]:.1f}m")
    print(f"  종료점: {trajectory[-1][2]:.3f}°N, {trajectory[-1][1]:.3f}°E, {trajectory[-1][3]:.1f}m")
    
    # 결과 저장
    output_file = script_dir / "pyhysplit_result_for_comparison.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"PyHYSPLIT Trajectory Result\n")
        f.write(f"{'='*80}\n\n")
        f.write(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M UTC')}\n")
        f.write(f"Start Location: {lat}°N, {lon}°E, {height}m AGL\n")
        f.write(f"Duration: {duration_hours}h\n")
        f.write(f"Number of Points: {len(trajectory)}\n\n")
        f.write(f"{'Time(s)':^20} {'Latitude':>10} {'Longitude':>10} {'Height(m)':>10}\n")
        f.write(f"{'-'*80}\n")
        
        for pt in trajectory:
            t_seconds, lon_val, lat_val, height_val = pt
            # t_seconds를 시간으로 변환
            hours = t_seconds / 3600.0
            f.write(f"{hours:^20.1f} {lat_val:>10.3f} {lon_val:>10.3f} {height_val:>10.1f}\n")
    
    print(f"\n✓ 결과 저장: {output_file}")
    
    # 시각화
    print("\n시각화 생성 중...")
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    
    # (1) 궤적 경로
    ax = axes[0, 0]
    lats = [pt[2] for pt in trajectory]  # 튜플: (t_seconds, lon, lat, height)
    lons = [pt[1] for pt in trajectory]
    ax.plot(lons, lats, 'b-o', markersize=6, linewidth=2, label='PyHYSPLIT')
    ax.plot(lons[0], lats[0], 'g*', markersize=20, label='Start', zorder=5)
    ax.plot(lons[-1], lats[-1], 'r*', markersize=20, label='End', zorder=5)
    ax.set_xlabel('Longitude (°E)', fontsize=12)
    ax.set_ylabel('Latitude (°N)', fontsize=12)
    ax.set_title('PyHYSPLIT Trajectory Path', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # (2) 고도 프로파일
    ax = axes[0, 1]
    heights = [pt[3] for pt in trajectory]
    times = [(pt[0] - trajectory[0][0]) / 3600 for pt in trajectory]  # t_seconds를 hours로 변환
    ax.plot(times, heights, 'b-o', markersize=6, linewidth=2)
    ax.set_xlabel('Time (hours)', fontsize=12)
    ax.set_ylabel('Height (m AGL)', fontsize=12)
    ax.set_title('Height Profile', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # (3) 위도 변화
    ax = axes[1, 0]
    ax.plot(times, lats, 'g-o', markersize=6, linewidth=2)
    ax.set_xlabel('Time (hours)', fontsize=12)
    ax.set_ylabel('Latitude (°N)', fontsize=12)
    ax.set_title('Latitude Change', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # (4) 경도 변화
    ax = axes[1, 1]
    ax.plot(times, lons, 'm-o', markersize=6, linewidth=2)
    ax.set_xlabel('Time (hours)', fontsize=12)
    ax.set_ylabel('Longitude (°E)', fontsize=12)
    ax.set_title('Longitude Change', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    output_path = script_dir / "pyhysplit_result_visualization.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ 시각화 저장: {output_path}")
    
    plt.close()
    
    print(f"\n{'='*80}")
    print(f"  PyHYSPLIT 실행 완료!")
    print(f"{'='*80}\n")
    
    return trajectory


if __name__ == "__main__":
    run_pyhysplit_comparison()
