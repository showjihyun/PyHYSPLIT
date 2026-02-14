"""GFS 데이터 범위 확장 다운로드 (105-150°E).

경계 오류 해결을 위해 서쪽으로 5도 확장 (110°E → 105°E).
베이징, 서울, 부산, 도쿄, 오사카의 궤적이 그리드를 벗어나지 않도록 합니다.

변경사항:
- 경도 범위: 110-150°E → 105-150°E (5도 확장)
- 추가 데이터: 약 12.5% 증가 (~20 MB)

사용법:
    python tests/integration/download_gfs_extended.py
"""

from pathlib import Path
from datetime import datetime, timedelta
import sys

def download_gfs_extended():
    """확장된 범위로 GFS 데이터 다운로드."""
    
    try:
        import xarray as xr
        import numpy as np
    except ImportError:
        print("\n❌ 필요한 패키지가 설치되지 않았습니다.")
        print("다음 명령으로 설치하세요:")
        print("  pip install xarray netCDF4 dask")
        return False
    
    print("\n" + "="*80)
    print("  GFS 데이터 범위 확장 다운로드 (105-150°E)")
    print("="*80 + "\n")
    
    print("목적: 경계 오류 해결")
    print("  - 이전 범위: 110-150°E (40도)")
    print("  - 새 범위: 105-150°E (45도, +12.5%)")
    print("  - 영향: 베이징, 서울, 부산, 도쿄, 오사카 궤적 완전 계산")
    print()
    
    # 최근 GFS 런 찾기
    now = datetime.utcnow()
    run_hour = (now.hour // 6) * 6
    run_date = now.replace(hour=run_hour, minute=0, second=0, microsecond=0)
    run_date = run_date - timedelta(hours=6)
    
    print(f"GFS 런 시간: {run_date.strftime('%Y-%m-%d %H:00 UTC')}")
    
    # NOMADS URL 구성
    date_str = run_date.strftime('%Y%m%d')
    hour_str = f"{run_date.hour:02d}"
    url = f"https://nomads.ncep.noaa.gov/dods/gfs_0p25/gfs{date_str}/gfs_0p25_{hour_str}z"
    
    print(f"URL: {url}")
    print(f"\n다운로드 중... (약 5-10분 소요)")
    print(f"⚠ 인터넷 연결이 필요합니다.")
    
    try:
        # 데이터셋 열기
        print(f"\n1. 데이터셋 연결 중...")
        ds = xr.open_dataset(url)
        
        print(f"   ✓ 연결 성공")
        
        # 변수명 확인
        if 'ugrdprs' in ds.data_vars:
            u_var, v_var, w_var, t_var, gh_var = 'ugrdprs', 'vgrdprs', 'vvelprs', 'tmpprs', 'hgtprs'
        elif 'ugrd' in ds.data_vars:
            u_var, v_var, w_var, t_var, gh_var = 'ugrd', 'vgrd', 'vvel', 'tmp', 'hgt'
        else:
            print(f"\n❌ 풍속 변수를 찾을 수 없습니다.")
            return False
        
        # 지오포텐셜 고도 변수 확인
        if gh_var not in ds.data_vars:
            for alt_name in ['geopotential_height', 'gh', 'z', 'hgt', 'height']:
                if alt_name in ds.data_vars:
                    gh_var = alt_name
                    break
            else:
                gh_var = None
        
        # 확장된 영역 선택
        print(f"\n2. 확장된 영역 선택 중...")
        print(f"   위도: 20-50°N")
        print(f"   경도: 105-150°E (폭 45도, 약 3,600km) ← 5도 확장!")
        print(f"   레벨: 200-1000 hPa")
        print(f"   시간: 0-24시간 예보")
        
        # 영역 선택
        if ds.lat.values[0] > ds.lat.values[-1]:
            subset = ds.sel(
                lat=slice(50, 20),
                lon=slice(105, 150),  # ← 105°E로 확장!
                lev=slice(1000, 200)
            ).isel(time=slice(0, 25))
        else:
            subset = ds.sel(
                lat=slice(20, 50),
                lon=slice(105, 150),  # ← 105°E로 확장!
                lev=slice(1000, 200)
            ).isel(time=slice(0, 25))
        
        print(f"   ✓ 영역 선택 완료")
        print(f"   Shape: lat={len(subset.lat)}, lon={len(subset.lon)}, "
              f"lev={len(subset.lev)}, time={len(subset.time)}")
        
        if len(subset.lat) == 0 or len(subset.lon) == 0:
            print(f"\n❌ 선택된 영역에 데이터가 없습니다.")
            return False
        
        # 필요한 변수만 추출
        print(f"\n3. 변수 추출 중...")
        vars_to_extract = [u_var, v_var, w_var, t_var]
        if gh_var:
            vars_to_extract.append(gh_var)
        
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
        
        if 'lev' in data.coords:
            data = data.rename({'lev': 'level'})
        
        print(f"   ✓ 변수 추출 완료")
        
        # 저장
        output_file = Path("tests/integration/gfs_cache/gfs_eastasia_24h_extended.nc")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"\n4. 저장 중: {output_file.name}")
        
        # 시간을 초 단위로 변환
        time_hours = np.arange(len(data.time), dtype=float)
        time_seconds = time_hours * 3600.0
        time_seconds = -time_seconds[::-1]
        
        # netCDF4로 저장
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
        var_lev[:] = data.level.values[::-1]
        var_lat[:] = data.lat.values
        var_lon[:] = data.lon.values
        
        var_u[:] = data.u.values[::-1, ::-1, :, :]
        var_v[:] = data.v.values[::-1, ::-1, :, :]
        var_w[:] = data.w.values[::-1, ::-1, :, :]
        var_t[:] = data.t.values[::-1, ::-1, :, :]
        
        if 'gh' in data:
            var_gh[:] = data.gh.values[::-1, ::-1, :, :]
        
        # 전역 속성
        ds_out.description = f'GFS 0.25 degree data for East Asia (105-150E, 20-50N) - EXTENDED RANGE'
        ds_out.source = f'NOMADS OpenDAP: {url}'
        ds_out.run_date = run_date.strftime('%Y-%m-%d %H:00 UTC')
        ds_out.download_date = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        ds_out.note = 'Extended 5 degrees westward (110E -> 105E) to prevent boundary errors'
        
        ds_out.close()
        
        print(f"   ✓ 저장 완료!")
        
        # 정보 출력
        print(f"\n" + "="*80)
        print(f"  다운로드 완료!")
        print(f"="*80 + "\n")
        
        print(f"파일 정보:")
        print(f"  경로: {output_file}")
        print(f"  크기: {output_file.stat().st_size / 1024 / 1024:.1f} MB")
        
        # 이전 파일과 비교
        old_file = Path("tests/integration/gfs_cache/gfs_eastasia_24h_real.nc")
        if old_file.exists():
            old_size = old_file.stat().st_size / 1024 / 1024
            new_size = output_file.stat().st_size / 1024 / 1024
            increase = ((new_size - old_size) / old_size) * 100
            print(f"  이전 파일: {old_size:.1f} MB")
            print(f"  증가량: +{new_size - old_size:.1f} MB (+{increase:.1f}%)")
        
        print(f"\n데이터 정보:")
        print(f"  GFS 런: {run_date.strftime('%Y-%m-%d %H:00 UTC')}")
        print(f"  시간 범위: 0 ~ -24시간")
        print(f"  위도 범위: {data.lat.values.min():.1f} ~ {data.lat.values.max():.1f}°N")
        print(f"  경도 범위: {data.lon.values.min():.1f} ~ {data.lon.values.max():.1f}°E ← 확장!")
        print(f"  레벨 범위: {data.level.values.min():.0f} ~ {data.level.values.max():.0f} hPa")
        print(f"  Shape: {data.u.shape}")
        
        print(f"\n다음 단계:")
        print(f"  1. 확장된 데이터로 테스트:")
        print(f"     python tests/integration/test_extended_range.py")
        print(f"  2. 경계 오류 확인:")
        print(f"     - 베이징, 서울, 부산, 도쿄, 오사카 궤적이 완전히 계산되는지 확인")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """메인 함수."""
    print("\n" + "="*80)
    print("  GFS 데이터 범위 확장 다운로드")
    print("="*80 + "\n")
    
    print("이 스크립트는 경계 오류를 해결하기 위해")
    print("GFS 데이터 범위를 서쪽으로 5도 확장합니다.")
    print()
    print("변경사항:")
    print("  - 경도 범위: 110-150°E → 105-150°E")
    print("  - 추가 데이터: 약 20 MB")
    print("  - 다운로드 시간: 약 5-10분")
    print()
    print("예상 효과:")
    print("  - 베이징, 서울, 부산, 도쿄, 오사카의 경계 오류 제거")
    print("  - 압력 오차 정상화 (298.85 hPa → 20-30 hPa)")
    print("  - 진행률: 80% → 83-84%")
    print()
    
    response = input("계속하시겠습니까? (y/n): ")
    if response.lower() != 'y':
        print("취소되었습니다.")
        return
    
    success = download_gfs_extended()
    
    if success:
        print("\n✅ 성공! 이제 확장된 범위로 테스트할 수 있습니다.")
        print("\n다음 명령 실행:")
        print("  python tests/integration/test_extended_range.py")
    else:
        print("\n⚠️ 다운로드 실패.")
        print("\n대안:")
        print("  1. 몇 분 후 다시 시도")
        print("  2. 기존 데이터로 계속 진행")


if __name__ == "__main__":
    main()
