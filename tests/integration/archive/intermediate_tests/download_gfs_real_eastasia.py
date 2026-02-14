"""실제 GFS 0.25도 데이터 다운로드 (극동아시아, 110-150°E).

NOAA NOMADS OpenDAP 서버에서 실제 GFS 데이터를 다운로드합니다.
넓은 영역(110-150°E)을 커버하여 24시간 궤적이 그리드를 벗어나지 않도록 합니다.

필요한 패키지:
    pip install xarray netCDF4 dask

사용법:
    python tests/integration/download_gfs_real_eastasia.py
"""

from pathlib import Path
from datetime import datetime, timedelta
import sys

def download_gfs_nomads():
    """NOMADS OpenDAP에서 GFS 데이터 다운로드."""
    
    try:
        import xarray as xr
        import numpy as np
    except ImportError:
        print("\n❌ 필요한 패키지가 설치되지 않았습니다.")
        print("다음 명령으로 설치하세요:")
        print("  pip install xarray netCDF4 dask")
        return False
    
    print("\n" + "="*80)
    print("  실제 GFS 0.25도 데이터 다운로드 (극동아시아)")
    print("="*80 + "\n")
    
    # 최근 GFS 런 찾기 (현재 시각 기준 6시간 전)
    now = datetime.utcnow()
    # GFS는 00, 06, 12, 18 UTC에 실행됨
    run_hour = (now.hour // 6) * 6
    run_date = now.replace(hour=run_hour, minute=0, second=0, microsecond=0)
    
    # 6시간 전 런 사용 (데이터 준비 시간 고려)
    run_date = run_date - timedelta(hours=6)
    
    print(f"GFS 런 시간: {run_date.strftime('%Y-%m-%d %H:00 UTC')}")
    
    # NOMADS URL 구성
    date_str = run_date.strftime('%Y%m%d')
    hour_str = f"{run_date.hour:02d}"
    url = f"https://nomads.ncep.noaa.gov/dods/gfs_0p25/gfs{date_str}/gfs_0p25_{hour_str}z"
    
    print(f"URL: {url}")
    print(f"\n다운로드 중... (대용량 데이터, 5-10분 소요)")
    print(f"⚠ 인터넷 연결이 필요합니다.")
    
    try:
        # 데이터셋 열기
        print(f"\n1. 데이터셋 연결 중...")
        ds = xr.open_dataset(url)
        
        print(f"   ✓ 연결 성공")
        print(f"   사용 가능한 변수: {list(ds.data_vars)[:10]}...")
        
        # 극동아시아 영역 선택 (넓게)
        print(f"\n2. 영역 선택 중...")
        print(f"   위도: 20-50°N")
        print(f"   경도: 110-150°E (폭 40도, 약 3,200km)")
        print(f"   레벨: 200-1000 hPa")
        print(f"   시간: 0-24시간 예보")
        
        # 변수명 확인 (GFS에 따라 다를 수 있음)
        if 'ugrdprs' in ds.data_vars:
            u_var, v_var, w_var, t_var, gh_var = 'ugrdprs', 'vgrdprs', 'vvelprs', 'tmpprs', 'hgtprs'
        elif 'ugrd' in ds.data_vars:
            u_var, v_var, w_var, t_var, gh_var = 'ugrd', 'vgrd', 'vvel', 'tmp', 'hgt'
        else:
            print(f"\n❌ 풍속 변수를 찾을 수 없습니다.")
            print(f"   사용 가능한 변수: {list(ds.data_vars)}")
            return False
        
        # 지오포텐셜 고도 변수 확인
        if gh_var not in ds.data_vars:
            print(f"\n⚠️ 지오포텐셜 고도 변수 '{gh_var}'를 찾을 수 없습니다.")
            print(f"   사용 가능한 변수: {list(ds.data_vars)}")
            # 대체 변수명 시도
            for alt_name in ['geopotential_height', 'gh', 'z', 'hgt', 'height']:
                if alt_name in ds.data_vars:
                    gh_var = alt_name
                    print(f"   ✓ 대체 변수 사용: {gh_var}")
                    break
            else:
                print(f"   ⚠️ 지오포텐셜 고도 없이 계속 진행합니다.")
                gh_var = None
        
        # 영역 선택
        # 시간은 isel로 인덱스 선택 (0-24시간 = 처음 25개 시간 포인트)
        # 위도는 내림차순일 수 있으므로 확인 후 선택
        if ds.lat.values[0] > ds.lat.values[-1]:
            # 위도가 내림차순 (90 → -90)
            subset = ds.sel(
                lat=slice(50, 20),      # 북위 20-50도
                lon=slice(110, 150),    # 동경 110-150도
                lev=slice(1000, 200)    # 200-1000 hPa
            ).isel(time=slice(0, 25))   # 처음 25개 시간 포인트 (0-24시간)
        else:
            # 위도가 오름차순 (-90 → 90)
            subset = ds.sel(
                lat=slice(20, 50),      # 북위 20-50도
                lon=slice(110, 150),    # 동경 110-150도
                lev=slice(1000, 200)    # 200-1000 hPa
            ).isel(time=slice(0, 25))   # 처음 25개 시간 포인트 (0-24시간)
        
        print(f"   ✓ 영역 선택 완료")
        print(f"   Shape: lat={len(subset.lat)}, lon={len(subset.lon)}, "
              f"lev={len(subset.lev)}, time={len(subset.time)}")
        
        # 데이터가 비어있는지 확인
        if len(subset.lat) == 0 or len(subset.lon) == 0:
            print(f"\n❌ 선택된 영역에 데이터가 없습니다.")
            print(f"   위도 범위: {ds.lat.values.min():.1f} ~ {ds.lat.values.max():.1f}")
            print(f"   경도 범위: {ds.lon.values.min():.1f} ~ {ds.lon.values.max():.1f}")
            return False
        
        # 필요한 변수만 추출
        print(f"\n3. 변수 추출 중...")
        vars_to_extract = [u_var, v_var, w_var, t_var]
        if gh_var:
            vars_to_extract.append(gh_var)
        print(f"   변수: {', '.join(vars_to_extract)}")
        
        data = subset[vars_to_extract]
        
        # 변수명 표준화
        rename_dict = {
            u_var: 'u',
            v_var: 'v',
            w_var: 'w',
            t_var: 't'
        }
        if gh_var:
            rename_dict[gh_var] = 'gh'
        
        data = data.rename(rename_dict)
        
        # 좌표명 표준화
        if 'lev' in data.coords:
            data = data.rename({'lev': 'level'})
        
        print(f"   ✓ 변수 추출 완료")
        
        # 저장
        output_file = Path("tests/integration/gfs_cache/gfs_eastasia_24h_real.nc")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"\n4. 저장 중: {output_file.name}")
        print(f"   ⚠ 대용량 파일, 시간이 걸릴 수 있습니다...")
        
        # 시간을 초 단위로 변환 (PyHYSPLIT 형식)
        # GFS 시간은 보통 hours since run_date
        # 단순히 0, 1, 2, ..., 24 시간으로 변환
        time_hours = np.arange(len(data.time), dtype=float)
        time_seconds = time_hours * 3600.0
        
        # 역궤적을 위해 시간을 음수로 변환하고 역순으로
        time_seconds = -time_seconds[::-1]  # [0, -3600, -7200, ..., -86400]
        
        # netCDF4로 저장 (PyHYSPLIT 형식)
        import netCDF4
        
        ds_out = netCDF4.Dataset(str(output_file), 'w', format='NETCDF4')
        
        # 차원 생성
        ds_out.createDimension('time', len(time_seconds))
        ds_out.createDimension('level', len(data.level))
        ds_out.createDimension('latitude', len(data.lat))
        ds_out.createDimension('longitude', len(data.lon))
        
        # 변수 생성
        var_time = ds_out.createVariable('time', 'f8', ('time',))
        var_lev = ds_out.createVariable('level', 'f4', ('level',))
        var_lat = ds_out.createVariable('latitude', 'f4', ('latitude',))
        var_lon = ds_out.createVariable('longitude', 'f4', ('longitude',))
        var_u = ds_out.createVariable('u', 'f4', ('time', 'level', 'latitude', 'longitude'))
        var_v = ds_out.createVariable('v', 'f4', ('time', 'level', 'latitude', 'longitude'))
        var_w = ds_out.createVariable('w', 'f4', ('time', 'level', 'latitude', 'longitude'))
        var_t = ds_out.createVariable('t', 'f4', ('time', 'level', 'latitude', 'longitude'))
        
        # 지오포텐셜 고도 변수 (있는 경우)
        if 'gh' in data:
            var_gh = ds_out.createVariable('gh', 'f4', ('time', 'level', 'latitude', 'longitude'))
            var_gh.units = 'm'
            var_gh.long_name = 'geopotential height'
        
        # 속성 추가
        var_time.units = 'seconds since reference'
        var_lev.units = 'hPa'
        var_lat.units = 'degrees_north'
        var_lon.units = 'degrees_east'
        var_u.units = 'm/s'
        var_v.units = 'm/s'
        var_w.units = 'Pa/s'
        var_t.units = 'K'
        
        # 데이터 쓰기
        var_time[:] = time_seconds
        var_lev[:] = data.level.values[::-1]  # 압력을 역순으로 (1000 → 200)
        var_lat[:] = data.lat.values
        var_lon[:] = data.lon.values
        
        # 데이터를 역순으로 저장 (시간 역순, 레벨 역순)
        var_u[:] = data.u.values[::-1, ::-1, :, :]
        var_v[:] = data.v.values[::-1, ::-1, :, :]
        var_w[:] = data.w.values[::-1, ::-1, :, :]
        var_t[:] = data.t.values[::-1, ::-1, :, :]
        
        if 'gh' in data:
            var_gh[:] = data.gh.values[::-1, ::-1, :, :]
            print(f"   ✓ 지오포텐셜 고도 포함")
        
        # 전역 속성
        ds_out.description = f'GFS 0.25 degree data for East Asia (110-150E, 20-50N)'
        ds_out.source = f'NOMADS OpenDAP: {url}'
        ds_out.run_date = run_date.strftime('%Y-%m-%d %H:00 UTC')
        ds_out.download_date = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        
        ds_out.close()
        
        print(f"   ✓ 저장 완료!")
        
        # 정보 출력
        print(f"\n" + "="*80)
        print(f"  다운로드 완료!")
        print(f"="*80 + "\n")
        
        print(f"파일 정보:")
        print(f"  경로: {output_file}")
        print(f"  크기: {output_file.stat().st_size / 1024 / 1024:.1f} MB")
        print(f"\n데이터 정보:")
        print(f"  GFS 런: {run_date.strftime('%Y-%m-%d %H:00 UTC')}")
        print(f"  시간 범위: 0 ~ -24시간 (역궤적용)")
        print(f"  위도 범위: {data.lat.values.min():.1f} ~ {data.lat.values.max():.1f}°N")
        print(f"  경도 범위: {data.lon.values.min():.1f} ~ {data.lon.values.max():.1f}°E")
        print(f"  레벨 범위: {data.level.values.min():.0f} ~ {data.level.values.max():.0f} hPa")
        print(f"  Shape: {data.u.shape}")
        
        print(f"\n다음 단계:")
        print(f"  1. 24시간 테스트 실행:")
        print(f"     python tests/integration/run_simple_24h_test.py")
        print(f"  2. HYSPLIT Web과 비교:")
        print(f"     python tests/integration/compare_with_hysplit_web_24h.py <tdump_file>")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        print(f"\n가능한 원인:")
        print(f"  1. 인터넷 연결 문제")
        print(f"  2. NOMADS 서버 문제 또는 점검 중")
        print(f"  3. 해당 날짜/시간의 데이터가 아직 준비되지 않음")
        print(f"  4. 변수명이 예상과 다름")
        print(f"\n해결 방법:")
        print(f"  - 몇 분 후 다시 시도")
        print(f"  - 더 이전 시간의 GFS 런 사용 (코드에서 timedelta 조정)")
        print(f"  - NOMADS 웹사이트에서 사용 가능한 날짜 확인:")
        print(f"    https://nomads.ncep.noaa.gov/")
        
        import traceback
        print(f"\n상세 오류:")
        traceback.print_exc()
        
        return False


def main():
    """메인 함수."""
    print("\n" + "="*80)
    print("  실제 GFS 0.25도 데이터 다운로드")
    print("="*80 + "\n")
    
    print("이 스크립트는 NOAA NOMADS 서버에서 실제 GFS 데이터를 다운로드합니다.")
    print("다운로드 시간: 약 5-10분")
    print("파일 크기: 약 100-200 MB")
    print()
    
    response = input("계속하시겠습니까? (y/n): ")
    if response.lower() != 'y':
        print("취소되었습니다.")
        return
    
    success = download_gfs_nomads()
    
    if success:
        print("\n✅ 성공! 이제 24시간 테스트를 실행할 수 있습니다.")
    else:
        print("\n⚠️ 다운로드 실패. 기존 외삽 데이터를 사용하거나 나중에 다시 시도하세요.")
        print("\n대안:")
        print("  1. 기존 외삽 데이터 사용:")
        print("     python tests/integration/run_simple_24h_test.py")
        print("  2. 수동으로 GFS 데이터 다운로드:")
        print("     https://nomads.ncep.noaa.gov/")


if __name__ == "__main__":
    main()
