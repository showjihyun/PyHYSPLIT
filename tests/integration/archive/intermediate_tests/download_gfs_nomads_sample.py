"""GFS 0.25도 데이터 다운로드 샘플 스크립트.

필요한 패키지:
    pip install xarray netCDF4 dask
"""

import xarray as xr
from datetime import datetime
from pathlib import Path

def download_gfs_nomads():
    """NOMADS OpenDAP에서 GFS 데이터 다운로드."""
    
    # 최근 GFS 런 선택 (실제 사용 시 현재 날짜로 변경)
    date = datetime(2026, 2, 13, 0)
    
    # NOMADS URL
    url = f"https://nomads.ncep.noaa.gov/dods/gfs_0p25/gfs{date.strftime('%Y%m%d')}/gfs_0p25_00z"
    
    print(f"다운로드 중: {url}")
    print("⚠ 주의: 대용량 데이터이므로 시간이 걸릴 수 있습니다.")
    
    try:
        # 데이터셋 열기
        ds = xr.open_dataset(url)
        
        # 극동아시아 영역 선택 (20-50°N, 110-150°E)
        subset = ds.sel(
            lat=slice(50, 20),
            lon=slice(110, 150),
            lev=slice(1000, 200),  # 200-1000 hPa
            time=slice(0, 24)  # 0-24시간 예보
        )
        
        # 필요한 변수만 추출
        variables = ['ugrdprs', 'vgrdprs', 'vvelprs', 'tmpprs']
        data = subset[variables]
        
        # 저장
        output_file = Path("tests/integration/gfs_cache/gfs_eastasia_24h_real.nc")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        data.to_netcdf(output_file)
        print(f"✓ 저장 완료: {output_file}")
        
        # 정보 출력
        print(f"\n데이터 정보:")
        print(f"  시간 범위: {data.time.values[0]} ~ {data.time.values[-1]}")
        print(f"  위도 범위: {data.lat.values.min():.1f} ~ {data.lat.values.max():.1f}")
        print(f"  경도 범위: {data.lon.values.min():.1f} ~ {data.lon.values.max():.1f}")
        print(f"  레벨 범위: {data.lev.values.min():.0f} ~ {data.lev.values.max():.0f} hPa")
        print(f"  Shape: {data.ugrdprs.shape}")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print("\n가능한 원인:")
        print("  1. 인터넷 연결 문제")
        print("  2. NOMADS 서버 문제")
        print("  3. 해당 날짜의 데이터가 아직 없음")
        print("\n해결 방법:")
        print("  - 최근 날짜로 변경 (보통 현재 시각 기준 3-6시간 전)")
        print("  - NOMADS 웹사이트에서 사용 가능한 날짜 확인:")
        print("    https://nomads.ncep.noaa.gov/")


if __name__ == "__main__":
    download_gfs_nomads()
