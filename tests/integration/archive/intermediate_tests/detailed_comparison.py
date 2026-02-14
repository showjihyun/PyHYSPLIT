"""상세 비교 - 각 시간 단계별 풍속, 위치, 고도 등을 출력하여 차이점 분석."""

from datetime import datetime, timedelta
from pathlib import Path
import numpy as np

from pyhysplit.engine import TrajectoryEngine
from pyhysplit.models import MetData, SimulationConfig, StartLocation


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


def parse_hysplit_web_result(filepath: Path) -> list[dict]:
    """HYSPLIT Web trajectory endpoints 파일 파싱."""
    points = []
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    for line in lines:
        parts = line.strip().split()
        if len(parts) == 13 and parts[0] == '1' and parts[1] == '1':
            try:
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
                continue
    
    return points


def run_detailed_pyhysplit(met_data: MetData, start_time: datetime, lat: float, lon: float, 
                           height: float, duration_hours: int):
    """PyHYSPLIT 궤적 계산 with detailed logging."""
    from pyhysplit.coordinate_converter import CoordinateConverter
    from pyhysplit.interpolator import Interpolator
    
    start_loc = StartLocation(lat=lat, lon=lon, height=height)
    
    config = SimulationConfig(
        start_time=start_time,
        num_start_locations=1,
        start_locations=[start_loc],
        total_run_hours=duration_hours,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[],
        turbulence_on=False,
        dt_max=600.0
    )
    
    engine = TrajectoryEngine(config, met_data)
    interp = Interpolator(met_data)
    
    # 각 출력 포인트에서의 상세 정보 수집
    trajectory = engine.run(output_interval_s=3600.0)[0]
    
    detailed_points = []
    base_time = datetime(start_time.year, start_time.month, start_time.day, 0, 0)
    
    for pt in trajectory:
        t_seconds, lon_val, lat_val, z_val = pt
        dt = base_time + timedelta(seconds=t_seconds)
        
        # 현재 위치에서의 풍속 보간
        try:
            u, v, w = interp.interpolate_4d(lon_val, lat_val, z_val, t_seconds)
        except:
            u, v, w = 0, 0, 0
        
        # 온도 보간
        try:
            T = interp.interpolate_scalar(met_data.t_field, lon_val, lat_val, z_val, t_seconds)
        except:
            T = 0
        
        # 압력을 고도로 변환
        if met_data.z_type == "pressure":
            z_pa = z_val * 100.0
            if met_data.t_field is not None and T > 0:
                try:
                    height_m = CoordinateConverter.pressure_to_height_with_temp(
                        np.array([z_pa]), np.array([T])
                    )[0]
                except:
                    height_m = CoordinateConverter.pressure_to_height(np.array([z_pa]))[0]
            else:
                height_m = CoordinateConverter.pressure_to_height(np.array([z_pa]))[0]
        else:
            height_m = z_val
        
        detailed_points.append({
            'time': dt,
            'lat': lat_val,
            'lon': lon_val,
            'height': height_m,
            'pressure': z_val if met_data.z_type == "pressure" else None,
            'u': u,
            'v': v,
            'w': w,
            'T': T,
            'wind_speed': np.sqrt(u**2 + v**2),
            'wind_dir': np.degrees(np.arctan2(u, v)) % 360
        })
    
    return detailed_points


def main():
    """메인 함수."""
    script_dir = Path(__file__).parent
    
    print(f"\n{'='*80}")
    print(f"  상세 비교 분석")
    print(f"{'='*80}\n")
    
    # 조건
    start_time = datetime(2026, 2, 13, 13, 0)
    lat = 37.5
    lon = 127.0
    height = 850.0
    duration_hours = -7
    
    # 1. HYSPLIT Web 결과 로드
    web_result_file = script_dir / "hysplit_trajectory_endpoints.txt"
    web_traj = parse_hysplit_web_result(web_result_file)
    
    print(f"HYSPLIT Web 결과: {len(web_traj)} 포인트\n")
    
    # 2. PyHYSPLIT 실행
    cache_file = script_dir / "gfs_cache" / f"gfs_20260213_{lat}_{lon}_1h.nc"
    met_data = load_cached_gfs_data(cache_file)
    
    print(f"PyHYSPLIT 실행 중...\n")
    py_traj = run_detailed_pyhysplit(met_data, start_time, lat, lon, height, duration_hours)
    
    print(f"PyHYSPLIT 결과: {len(py_traj)} 포인트\n")
    
    # 3. 포인트별 상세 비교
    print(f"{'='*80}")
    print(f"  포인트별 상세 비교")
    print(f"{'='*80}\n")
    
    min_len = min(len(py_traj), len(web_traj))
    
    for i in range(min_len):
        py = py_traj[i]
        web = web_traj[i]
        
        # 거리 계산
        R = 6371.0
        dlat = np.deg2rad(web['lat'] - py['lat'])
        dlon = np.deg2rad(web['lon'] - py['lon'])
        a = np.sin(dlat/2)**2 + np.cos(np.deg2rad(py['lat'])) * np.cos(np.deg2rad(web['lat'])) * np.sin(dlon/2)**2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
        dist_km = R * c
        
        print(f"시간: {py['time'].strftime('%H:%M')}")
        print(f"  PyHYSPLIT:")
        print(f"    위치: {py['lat']:.4f}°N, {py['lon']:.4f}°E, {py['height']:.1f}m")
        print(f"    압력: {py['pressure']:.1f} hPa" if py['pressure'] else "")
        print(f"    풍속: U={py['u']:.2f} m/s, V={py['v']:.2f} m/s, W={py['w']:.4f} m/s")
        print(f"    풍속크기: {py['wind_speed']:.2f} m/s, 풍향: {py['wind_dir']:.1f}°")
        print(f"    온도: {py['T']:.2f} K ({py['T']-273.15:.2f}°C)")
        print(f"  HYSPLIT Web:")
        print(f"    위치: {web['lat']:.4f}°N, {web['lon']:.4f}°E, {web['height']:.1f}m")
        print(f"  차이:")
        print(f"    수평 거리: {dist_km:.2f} km")
        print(f"    위도: {(py['lat'] - web['lat']):.4f}° ({(py['lat'] - web['lat'])*111:.2f} km)")
        print(f"    경도: {(py['lon'] - web['lon']):.4f}° ({(py['lon'] - web['lon'])*111*np.cos(np.deg2rad(py['lat'])):.2f} km)")
        print(f"    고도: {(py['height'] - web['height']):.1f} m")
        print()


if __name__ == "__main__":
    main()
