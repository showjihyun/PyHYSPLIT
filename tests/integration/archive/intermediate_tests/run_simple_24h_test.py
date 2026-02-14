"""간단한 24시간 테스트 실행 스크립트."""

from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import netCDF4

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pyhysplit.models import StartLocation, SimulationConfig, MetData
from pyhysplit.engine import TrajectoryEngine
from pyhysplit.coordinate_converter import CoordinateConverter
from pyhysplit.interpolator import Interpolator


def main():
    print("\n" + "="*80)
    print("  18시간 역궤적 테스트 (극동아시아)")
    print("="*80 + "\n")
    
    # GFS 캐시 로드 - 실제 데이터 우선, 없으면 외삽 데이터 사용
    cache_file_real = Path(__file__).parent / "gfs_cache" / "gfs_eastasia_24h_real.nc"
    cache_file_extended = Path(__file__).parent / "gfs_cache" / "gfs_24h_extended.nc"
    
    if cache_file_real.exists():
        cache_file = cache_file_real
        data_type = "실제 GFS 0.25도 데이터"
    elif cache_file_extended.exists():
        cache_file = cache_file_extended
        data_type = "외삽 데이터 (7h → 24h)"
    else:
        print(f"[ERROR] GFS 캐시 파일이 없습니다.")
        print(f"다음 중 하나를 실행하세요:")
        print(f"  1. 실제 GFS 다운로드: python tests/integration/download_gfs_real_eastasia.py")
        print(f"  2. 외삽 데이터 생성: python tests/integration/extend_gfs_to_24h.py")
        return
    
    print(f"[OK] GFS 캐시 로드: {cache_file.name}")
    print(f"  데이터 타입: {data_type}")
    
    # 데이터 로드
    ds = netCDF4.Dataset(str(cache_file))
    
    u_data = np.array(ds.variables['u'][:])
    v_data = np.array(ds.variables['v'][:])
    w_data = np.array(ds.variables['w'][:])
    t_data = np.array(ds.variables['t'][:])
    
    lat_grid = np.array(ds.variables['latitude'][:])
    lon_grid = np.array(ds.variables['longitude'][:])
    lev_grid = np.array(ds.variables['level'][:])
    time_grid = np.array(ds.variables['time'][:])
    
    ds.close()
    
    # 시간 그리드가 역순인 경우 정렬 (interpolator는 오름차순 가정)
    if time_grid[0] > time_grid[-1]:
        print(f"  시간 그리드 역순 감지, 정렬 중...")
        time_indices = np.argsort(time_grid)
        time_grid = time_grid[time_indices]
        u_data = u_data[time_indices]
        v_data = v_data[time_indices]
        w_data = w_data[time_indices]
        t_data = t_data[time_indices]
        print(f"  정렬 완료: {time_grid[0]/3600:.1f}h ~ {time_grid[-1]/3600:.1f}h")
    
    print(f"  데이터 shape: {u_data.shape}")
    print(f"  시간 범위: {time_grid[0]/3600:.1f}h ~ {time_grid[-1]/3600:.1f}h")
    print(f"  위도 범위: {lat_grid[0]:.1f} ~ {lat_grid[-1]:.1f}")
    print(f"  경도 범위: {lon_grid[0]:.1f} ~ {lon_grid[-1]:.1f}")
    print()
    
    # MetData 생성
    met_data = MetData(
        u=u_data,
        v=v_data,
        w=w_data,
        t_field=t_data,
        lat_grid=lat_grid,
        lon_grid=lon_grid,
        z_grid=lev_grid,
        t_grid=time_grid,
        z_type="pressure",
        source="GFS_NC"
    )
    
    # 테스트 조건
    # start_time은 출력 포맷용이며, 실제 시뮬레이션은 t_grid를 사용
    start_time = datetime(2026, 2, 13, 6, 0)
    lat = 37.5
    lon = 127.0
    height = 850.0
    
    # GFS 데이터의 실제 시간 범위 계산
    duration_hours = (time_grid[0] - time_grid[-1]) / 3600.0
    
    print(f"테스트 조건:")
    print(f"  시작 시간: {start_time.strftime('%Y-%m-%d %H:%M UTC')} (출력 포맷용)")
    print(f"  위치: {lat}°N, {lon}°E")
    print(f"  고도: {height}m AGL")
    print(f"  기간: {duration_hours:.0f}시간 역궤적 (GFS 데이터 범위)")
    print()
    
    # PyHYSPLIT 실행
    print("[OK] PyHYSPLIT 실행 중...")
    
    start_loc = StartLocation(lat=lat, lon=lon, height=height)
    
    # total_run_hours는 GFS 데이터의 실제 시간 범위와 일치해야 함
    total_run_hours = int(-duration_hours)
    
    config = SimulationConfig(
        start_time=start_time,
        num_start_locations=1,
        start_locations=[start_loc],
        total_run_hours=total_run_hours,
        vertical_motion=8,
        model_top=10000.0,
        met_files=[],
        turbulence_on=False,
        dt_max=15.0,
        vertical_damping=0.0003,
        scale_height=8430.0,
        tratio=0.75
    )
    
    engine = TrajectoryEngine(config, met_data)
    trajectory = engine.run(output_interval_s=3600.0)[0]
    
    print(f"[OK] 계산 완료")
    print(f"  포인트 수: {len(trajectory)}")
    
    if len(trajectory) > 1:
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
        
        print(f"\n결과:")
        print(f"  시작: {results[0]['time'].strftime('%m-%d %H:%M')} - "
              f"{results[0]['lat']:.3f}°N, {results[0]['lon']:.3f}°E, {results[0]['height']:.1f}m")
        print(f"  종료: {results[-1]['time'].strftime('%m-%d %H:%M')} - "
              f"{results[-1]['lat']:.3f}°N, {results[-1]['lon']:.3f}°E, {results[-1]['height']:.1f}m")
        
        # 이동 거리 계산
        from math import radians, sin, cos, sqrt, atan2
        
        def haversine(lat1, lon1, lat2, lon2):
            R = 6371.0
            lat1_rad, lat2_rad = radians(lat1), radians(lat2)
            dlon = radians(lon2 - lon1)
            dlat = lat2_rad - lat1_rad
            
            a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            return R * c
        
        total_distance = haversine(
            results[0]['lat'], results[0]['lon'],
            results[-1]['lat'], results[-1]['lon']
        )
        
        height_change = results[-1]['height'] - results[0]['height']
        
        print(f"\n이동:")
        print(f"  수평 거리: {total_distance:.2f} km")
        print(f"  고도 변화: {height_change:+.1f} m")
        
        # 시간대별 분석
        print(f"\n시간대별 이동:")
        for i in range(0, len(results), 6):
            if i + 6 < len(results):
                dist = haversine(
                    results[i]['lat'], results[i]['lon'],
                    results[i+6]['lat'], results[i+6]['lon']
                )
                hours = (results[i+6]['time'] - results[i]['time']).total_seconds() / 3600
                print(f"  {results[i]['time'].strftime('%H:%M')} ~ {results[i+6]['time'].strftime('%H:%M')}: "
                      f"{dist:.2f} km ({hours:.0f}시간)")
        
        print(f"\n[OK] {duration_hours:.0f}시간 테스트 완료!")
        print(f"\n극동아시아 지역 (한국 중심) {duration_hours:.0f}시간 역궤적 결과:")
        print(f"  - 시작: 서울 인근 ({lat}°N, {lon}°E)")
        print(f"  - 총 이동: {total_distance:.2f} km")
        print(f"  - 고도 변화: {height_change:+.1f} m")
        print(f"  - 데이터: {data_type}")
        
    else:
        print(f"[WARN] 궤적이 조기 종료되었습니다.")
        print(f"  시간 범위 또는 공간 범위를 확인하세요.")


if __name__ == "__main__":
    main()
