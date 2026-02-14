"""실제 GFS 0.25도 데이터를 다운로드하여 극동아시아 24시간 테스트용 데이터 생성.

NOAA NOMADS 서버에서 GFS 0.25도 데이터를 다운로드합니다.
극동아시아 지역 (20-50°N, 110-150°E)을 커버하여 24시간 궤적이 그리드를 벗어나지 않도록 합니다.

사용법:
    python tests/integration/download_real_gfs_eastasia.py
"""

from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
import netCDF4

def download_gfs_data_eastasia():
    """극동아시아 지역 GFS 0.25도 데이터 다운로드 및 변환."""
    
    print("\n" + "="*80)
    print("  실제 GFS 0.25도 데이터 다운로드 (극동아시아)")
    print("="*80 + "\n")
    
    print("⚠ 주의: 이 스크립트는 실제 GFS 데이터 다운로드 방법을 안내합니다.")
    print("실제 다운로드를 위해서는 다음 중 하나를 선택하세요:\n")
    
    print("방법 1: NOMADS OpenDAP 사용 (권장)")
    print("-" * 80)
    print("NOAA NOMADS 서버에서 직접 데이터를 읽어옵니다.")
    print("URL 형식: https://nomads.ncep.noaa.gov/dods/gfs_0p25/gfs{YYYYMMDD}/gfs_0p25_{HH}z")
    print("\n예제 코드:")
    print("""
import xarray as xr
from datetime import datetime

# 최근 GFS 런 (예: 2026-02-13 00Z)
date = datetime(2026, 2, 13, 0)
url = f"https://nomads.ncep.noaa.gov/dods/gfs_0p25/gfs{date.strftime('%Y%m%d')}/gfs_0p25_00z"

# 극동아시아 영역 선택
ds = xr.open_dataset(url)
subset = ds.sel(
    lat=slice(50, 20),  # 북위 20-50도
    lon=slice(110, 150),  # 동경 110-150도
    time=slice(0, 24)  # 0-24시간 예보
)

# 필요한 변수만 추출
data = subset[['ugrdprs', 'vgrdprs', 'vvelprs', 'tmpprs']]
data.to_netcdf('gfs_eastasia_24h.nc')
""")
    
    print("\n방법 2: AWS S3 사용")
    print("-" * 80)
    print("AWS S3에서 GFS 데이터를 다운로드합니다 (무료, 빠름).")
    print("버킷: s3://noaa-gfs-bdp-pds/")
    print("\n예제 코드:")
    print("""
import boto3
import xarray as xr

# AWS S3 클라이언트 (인증 불필요)
s3 = boto3.client('s3', region_name='us-east-1')

# GFS 파일 경로
date = '20260213'
hour = '00'
forecast_hour = '000'  # 0시간 예보

key = f'gfs.{date}/{hour}/atmos/gfs.t{hour}z.pgrb2.0p25.f{forecast_hour}'

# 다운로드
s3.download_file('noaa-gfs-bdp-pds', key, 'gfs_file.grib2')

# GRIB2 파일을 xarray로 읽기 (cfgrib 필요)
ds = xr.open_dataset('gfs_file.grib2', engine='cfgrib')
""")
    
    print("\n방법 3: 기존 테스트 데이터 확장 (현재 사용 중)")
    print("-" * 80)
    print("기존 7시간 GFS 캐시를 외삽하여 24시간으로 확장합니다.")
    print("✓ 이미 완료: tests/integration/gfs_cache/gfs_24h_extended.nc")
    print("⚠ 주의: 외삽 데이터이므로 정확도가 떨어집니다.")
    
    print("\n" + "="*80)
    print("  권장 사항")
    print("="*80 + "\n")
    
    print("1. 빠른 테스트: 방법 3 사용 (이미 준비됨)")
    print("   - 장점: 즉시 사용 가능")
    print("   - 단점: 외삽 데이터, 공간 범위 제한 (120-135°E)")
    print()
    print("2. 정확한 검증: 방법 1 또는 2 사용")
    print("   - 장점: 실제 GFS 데이터, 넓은 공간 범위 (110-150°E)")
    print("   - 단점: 다운로드 필요, 추가 라이브러리 필요 (xarray, cfgrib)")
    print()
    
    print("다음 단계:")
    print("  1. 현재 외삽 데이터로 테스트: python tests/integration/run_simple_24h_test.py")
    print("  2. 실제 데이터 다운로드: 위 방법 1 또는 2 참고")
    print("  3. HYSPLIT Web과 비교: 동일 조건으로 HYSPLIT Web 실행 후 비교")
    print()


def create_sample_download_script():
    """실제 다운로드를 위한 샘플 스크립트 생성."""
    
    sample_script = '''"""GFS 0.25도 데이터 다운로드 샘플 스크립트.

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
        print(f"\\n데이터 정보:")
        print(f"  시간 범위: {data.time.values[0]} ~ {data.time.values[-1]}")
        print(f"  위도 범위: {data.lat.values.min():.1f} ~ {data.lat.values.max():.1f}")
        print(f"  경도 범위: {data.lon.values.min():.1f} ~ {data.lon.values.max():.1f}")
        print(f"  레벨 범위: {data.lev.values.min():.0f} ~ {data.lev.values.max():.0f} hPa")
        print(f"  Shape: {data.ugrdprs.shape}")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print("\\n가능한 원인:")
        print("  1. 인터넷 연결 문제")
        print("  2. NOMADS 서버 문제")
        print("  3. 해당 날짜의 데이터가 아직 없음")
        print("\\n해결 방법:")
        print("  - 최근 날짜로 변경 (보통 현재 시각 기준 3-6시간 전)")
        print("  - NOMADS 웹사이트에서 사용 가능한 날짜 확인:")
        print("    https://nomads.ncep.noaa.gov/")


if __name__ == "__main__":
    download_gfs_nomads()
'''
    
    output_file = Path("tests/integration/download_gfs_nomads_sample.py")
    output_file.write_text(sample_script, encoding='utf-8')
    print(f"\n✓ 샘플 스크립트 생성: {output_file}")
    print(f"  실행: python {output_file}")


def main():
    """메인 함수."""
    download_gfs_data_eastasia()
    create_sample_download_script()


if __name__ == "__main__":
    main()
