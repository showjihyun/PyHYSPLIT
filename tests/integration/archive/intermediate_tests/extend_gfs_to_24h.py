"""기존 GFS 캐시를 24시간 분량으로 확장하는 스크립트.

기존 7시간 GFS 캐시를 시간 외삽(extrapolation)을 통해 24시간으로 확장합니다.
실제 데이터가 아닌 외삽 데이터이므로 정확도는 떨어지지만, 테스트 목적으로 사용 가능합니다.

사용법:
    python tests/integration/extend_gfs_to_24h.py
"""

from pathlib import Path
import numpy as np
import netCDF4
from scipy.interpolate import interp1d


def extend_gfs_cache_to_24h(input_file: Path, output_file: Path):
    """GFS 캐시를 24시간으로 확장.
    
    Parameters
    ----------
    input_file : Path
        입력 GFS 캐시 파일 (7시간 분량)
    output_file : Path
        출력 GFS 캐시 파일 (24시간 분량)
    """
    print(f"\n{'='*80}")
    print(f"  GFS 캐시 24시간 확장")
    print(f"{'='*80}\n")
    
    print(f"입력: {input_file}")
    print(f"출력: {output_file}")
    
    # 입력 파일 읽기
    print(f"\n1. 입력 파일 읽기...")
    ds_in = netCDF4.Dataset(str(input_file))
    
    # 변수명 확인 (파일에 따라 다를 수 있음)
    var_names = list(ds_in.variables.keys())
    print(f"  변수: {var_names}")
    
    # 위도/경도/레벨 변수명 결정
    if 'latitude' in var_names:
        lat_var, lon_var, lev_var = 'latitude', 'longitude', 'level'
    elif 'lat' in var_names:
        lat_var, lon_var, lev_var = 'lat', 'lon', 'lev'
    else:
        raise ValueError("위도/경도 변수를 찾을 수 없습니다")
    
    lat_grid = np.array(ds_in.variables[lat_var][:])
    lon_grid = np.array(ds_in.variables[lon_var][:])
    lev_grid = np.array(ds_in.variables[lev_var][:])
    time_grid_in = np.array(ds_in.variables["time"][:])
    
    u_in = np.array(ds_in.variables["u"][:])
    v_in = np.array(ds_in.variables["v"][:])
    w_in = np.array(ds_in.variables["w"][:])
    t_in = np.array(ds_in.variables["t"][:])
    
    ds_in.close()
    
    print(f"  Shape: {u_in.shape}")
    print(f"  시간 범위: {time_grid_in[0]:.1f}s ~ {time_grid_in[-1]:.1f}s")
    print(f"  시간 개수: {len(time_grid_in)}")
    
    # 시간을 시간 단위로 변환
    time_hours_in = time_grid_in / 3600.0
    print(f"  시간 범위: {time_hours_in[0]:.1f}h ~ {time_hours_in[-1]:.1f}h")
    
    # 24시간 분량의 시간 그리드 생성 (1시간 간격)
    # 시작 시간부터 24시간 전까지 (역궤적이므로 음수)
    start_hour = time_hours_in[0]
    time_hours_out = np.arange(start_hour, start_hour - 24.5, -1.0)  # 25개 포인트 (0, -1, -2, ..., -24)
    time_grid_out = time_hours_out * 3600.0
    
    print(f"\n2. 24시간 시간 그리드 생성...")
    print(f"  출력 시간 범위: {time_hours_out[0]:.1f}h ~ {time_hours_out[-1]:.1f}h")
    print(f"  출력 시간 개수: {len(time_hours_out)}")
    
    # 외삽을 통한 데이터 확장
    print(f"\n3. 데이터 외삽 중...")
    print(f"  ⚠ 주의: 외삽 데이터는 실제 기상 데이터가 아닙니다!")
    print(f"  ⚠ 테스트 목적으로만 사용하세요.")
    
    u_out = np.zeros((len(time_hours_out), *u_in.shape[1:]), dtype=np.float32)
    v_out = np.zeros((len(time_hours_out), *v_in.shape[1:]), dtype=np.float32)
    w_out = np.zeros((len(time_hours_out), *w_in.shape[1:]), dtype=np.float32)
    t_out = np.zeros((len(time_hours_out), *t_in.shape[1:]), dtype=np.float32)
    
    total_points = u_in.shape[1] * u_in.shape[2] * u_in.shape[3]
    processed = 0
    
    # 각 레벨, 위도, 경도에 대해 시간 외삽
    for k in range(u_in.shape[1]):  # lev
        for j in range(u_in.shape[2]):  # lat
            for i in range(u_in.shape[3]):  # lon
                # 선형 외삽 (fill_value='extrapolate')
                f_u = interp1d(time_hours_in, u_in[:, k, j, i], kind='linear', 
                              fill_value='extrapolate', bounds_error=False)
                u_out[:, k, j, i] = f_u(time_hours_out)
                
                f_v = interp1d(time_hours_in, v_in[:, k, j, i], kind='linear',
                              fill_value='extrapolate', bounds_error=False)
                v_out[:, k, j, i] = f_v(time_hours_out)
                
                f_w = interp1d(time_hours_in, w_in[:, k, j, i], kind='linear',
                              fill_value='extrapolate', bounds_error=False)
                w_out[:, k, j, i] = f_w(time_hours_out)
                
                f_t = interp1d(time_hours_in, t_in[:, k, j, i], kind='linear',
                              fill_value='extrapolate', bounds_error=False)
                t_out[:, k, j, i] = f_t(time_hours_out)
                
                processed += 1
                if processed % 1000 == 0:
                    progress = (processed / total_points) * 100
                    print(f"  진행: {progress:.1f}% ({processed}/{total_points})", end='\r')
    
    print(f"\n  ✓ 외삽 완료")
    
    # 출력 파일 저장
    print(f"\n4. 출력 파일 저장 중...")
    ds_out = netCDF4.Dataset(str(output_file), 'w', format='NETCDF4')
    
    # 차원 생성
    ds_out.createDimension('time', len(time_grid_out))
    ds_out.createDimension('level', len(lev_grid))
    ds_out.createDimension('latitude', len(lat_grid))
    ds_out.createDimension('longitude', len(lon_grid))
    
    # 변수 생성
    var_time = ds_out.createVariable('time', 'f8', ('time',))
    var_lev = ds_out.createVariable('level', 'f4', ('level',))
    var_lat = ds_out.createVariable('latitude', 'f4', ('latitude',))
    var_lon = ds_out.createVariable('longitude', 'f4', ('longitude',))
    var_u = ds_out.createVariable('u', 'f4', ('time', 'level', 'latitude', 'longitude'))
    var_v = ds_out.createVariable('v', 'f4', ('time', 'level', 'latitude', 'longitude'))
    var_w = ds_out.createVariable('w', 'f4', ('time', 'level', 'latitude', 'longitude'))
    var_t = ds_out.createVariable('t', 'f4', ('time', 'level', 'latitude', 'longitude'))
    
    # 속성 추가
    var_time.units = 'seconds since reference'
    var_lev.units = 'hPa'
    var_lat.units = 'degrees_north'
    var_lon.units = 'degrees_east'
    var_u.units = 'm/s'
    var_v.units = 'm/s'
    var_w.units = 'hPa/s'
    var_t.units = 'K'
    
    # 데이터 쓰기
    var_time[:] = time_grid_out
    var_lev[:] = lev_grid
    var_lat[:] = lat_grid
    var_lon[:] = lon_grid
    var_u[:] = u_out
    var_v[:] = v_out
    var_w[:] = w_out
    var_t[:] = t_out
    
    # 전역 속성
    ds_out.description = 'GFS data extended to 24 hours via extrapolation'
    ds_out.source = 'Extended from 7-hour GFS cache'
    ds_out.warning = 'Extrapolated data - use for testing only!'
    
    ds_out.close()
    
    print(f"  ✓ 저장 완료: {output_file}")
    print(f"\n{'='*80}")
    print(f"  완료!")
    print(f"{'='*80}\n")
    print(f"⚠ 주의사항:")
    print(f"  - 이 파일은 외삽된 데이터입니다")
    print(f"  - 실제 기상 데이터가 아니므로 정확도가 떨어집니다")
    print(f"  - 테스트 및 개발 목적으로만 사용하세요")
    print(f"  - 실제 검증을 위해서는 실제 GFS 데이터를 사용하세요")


def main():
    """메인 함수."""
    print(f"\n{'='*80}")
    print(f"  GFS 캐시 24시간 확장 도구")
    print(f"{'='*80}\n")
    
    # 기존 캐시 파일 찾기
    gfs_cache_dir = Path("tests/integration/gfs_cache")
    
    if not gfs_cache_dir.exists():
        print(f"❌ GFS 캐시 디렉토리가 없습니다: {gfs_cache_dir}")
        print(f"   먼저 기존 테스트를 실행하여 GFS 캐시를 생성하세요:")
        print(f"   python -m pytest tests/integration/test_hysplit_web_comparison.py -v -s")
        return
    
    # 캐시 파일 목록
    cache_files = list(gfs_cache_dir.glob("gfs_*.nc"))
    
    if not cache_files:
        print(f"❌ GFS 캐시 파일이 없습니다: {gfs_cache_dir}")
        print(f"   먼저 기존 테스트를 실행하여 GFS 캐시를 생성하세요:")
        print(f"   python -m pytest tests/integration/test_hysplit_web_comparison.py -v -s")
        return
    
    print(f"발견된 GFS 캐시 파일:")
    for i, cache_file in enumerate(cache_files, 1):
        print(f"  {i}. {cache_file.name}")
    
    # 가장 최근 파일 자동 선택
    latest_cache = max(cache_files, key=lambda p: p.stat().st_mtime)
    print(f"\n자동 선택: {latest_cache.name} (가장 최근 파일)")
    
    # 출력 파일명
    output_file = gfs_cache_dir / "gfs_24h_extended.nc"
    
    # 확장 실행
    try:
        extend_gfs_cache_to_24h(latest_cache, output_file)
        
        print(f"\n다음 단계:")
        print(f"  1. test_24hour_comparison.py를 수정하여 이 파일을 사용하도록 설정")
        print(f"  2. 24시간 테스트 실행:")
        print(f"     python tests/integration/test_24hour_comparison.py")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
