"""실제 GFS 0.25도 데이터를 다운로드하여 24시간 역궤적용 데이터 준비.

극동아시아 지역 (한국, 일본, 중국 동부) 중심으로 데이터 수집.

사용법:
    python tests/integration/download_real_gfs_24h.py
"""

from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import requests
import netCDF4


def download_gfs_data_24h(
    center_lat: float = 37.0,
    center_lon: float = 127.0,
    date: datetime = None,
    output_dir: Path = None
):
    """GFS 0.25도 데이터를 다운로드하여 24시간 역궤적용 데이터 준비.
    
    Parameters
    ----------
    center_lat : float
        중심 위도 (기본: 37.0 - 서울)
    center_lon : float
        중심 경도 (기본: 127.0 - 서울)
    date : datetime
        시작 날짜/시간 (기본: 가장 최근 데이터)
    output_dir : Path
        출력 디렉토리 (기본: tests/integration/gfs_cache)
    """
    if output_dir is None:
        output_dir = Path(__file__).parent / "gfs_cache"
    
    if date is None:
        # 가장 최근 GFS 데이터 사용 (보통 6시간 전)
        now = datetime.utcnow()
        # GFS는 00, 06, 12, 18 UTC에 실행
        hour = (now.hour // 6) * 6
        date = datetime(now.year, now.month, now.day, hour, 0) - timedelta(hours=6)
    
    print(f"\n{'='*80}")
    print(f"  실제 GFS 0.25도 데이터 다운로드 (24시간 역궤적용)")
    print(f"{'='*80}\n")
    
    print(f"설정:")
    print(f"  중심 위치: {center_lat}°N, {center_lon}°E")
    print(f"  시작 시간: {date.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  데이터 범위: 24시간 전까지")
    print(f"  해상도: GFS 0.25도")
    print()
    
    # 극동아시아 지역 범위 설정 (중심 ±10도)
    lat_min = max(center_lat - 10, -90)
    lat_max = min(center_lat + 10, 90)
    lon_min = center_lon - 10
    lon_max = center_lon + 10
    
    print(f"다운로드 영역:")
    print(f"  위도: {lat_min}°N ~ {lat_max}°N")
    print(f"  경도: {lon_min}°E ~ {lon_max}°E")
    print()
    
    # NOMADS GFS 데이터 URL
    # https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl
    base_url = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
    
    # 필요한 변수
    variables = ['UGRD', 'VGRD', 'VVEL', 'TMP']  # u, v, omega, temperature
    levels = ['1000', '975', '950', '925', '900', '850', '800', '750', '700', '650', 
              '600', '550', '500', '450', '400', '350', '300', '250', '200', '150', '100']
    
    print(f"⚠ 주의: 실제 GFS 데이터 다운로드는 NOMADS 서버 접근이 필요합니다.")
    print(f"   이 스크립트는 데이터 구조를 보여주는 예시입니다.")
    print(f"   실제 다운로드를 위해서는:")
    print(f"   1. NOMADS 서버 접근 권한 확인")
    print(f"   2. 또는 다른 GFS 데이터 소스 사용 (예: AWS S3)")
    print(f"   3. 또는 기존 테스트 데이터 확장 사용")
    print()
    
    # 대안: 기존 데이터 확장 제안
    print(f"대안 방법:")
    print(f"  1. 기존 GFS 캐시 확장:")
    print(f"     python tests/integration/extend_gfs_to_24h.py")
    print(f"  2. HYSPLIT Web 사용 (실제 기상 데이터):")
    print(f"     python tests/integration/prepare_24h_test_data.py")
    print()
    
    # 예시: 데이터 구조 생성
    print(f"예시 데이터 구조 생성 중...")
    
    # 시간 그리드 (24시간 + 시작 시간 = 25개 포인트)
    time_hours = np.arange(0, -25, -1)  # 0, -1, -2, ..., -24
    
    # 공간 그리드
    lat_grid = np.arange(lat_min, lat_max + 0.25, 0.25)
    lon_grid = np.arange(lon_min, lon_max + 0.25, 0.25)
    lev_grid = np.array([float(l) for l in levels])
    
    print(f"  시간: {len(time_hours)}개 포인트 ({time_hours[0]}h ~ {time_hours[-1]}h)")
    print(f"  위도: {len(lat_grid)}개 포인트")
    print(f"  경도: {len(lon_grid)}개 포인트")
    print(f"  레벨: {len(lev_grid)}개 레벨")
    print(f"  총 크기: {len(time_hours)} × {len(lev_grid)} × {len(lat_grid)} × {len(lon_grid)}")
    print()
    
    # 실제 다운로드 대신 안내 메시지
    print(f"{'='*80}")
    print(f"  실제 GFS 데이터 다운로드 방법")
    print(f"{'='*80}\n")
    
    print(f"방법 1: NOMADS 서버 (무료, 최근 데이터)")
    print(f"  URL: https://nomads.ncep.noaa.gov/")
    print(f"  - GFS 0.25도 데이터 선택")
    print(f"  - 날짜/시간 선택: {date.strftime('%Y%m%d/%H')}")
    print(f"  - 변수 선택: UGRD, VGRD, VVEL, TMP")
    print(f"  - 레벨 선택: 1000-100 hPa")
    print(f"  - 영역 선택: {lat_min}°N-{lat_max}°N, {lon_min}°E-{lon_max}°E")
    print()
    
    print(f"방법 2: AWS S3 (무료, 아카이브)")
    print(f"  Bucket: noaa-gfs-bdp-pds")
    print(f"  경로: gfs.{date.strftime('%Y%m%d')}/{date.hour:02d}/atmos/")
    print(f"  파일: gfs.t{date.hour:02d}z.pgrb2.0p25.f000 ~ f024")
    print()
    
    print(f"방법 3: Python 라이브러리")
    print(f"  herbie-data: pip install herbie-data")
    print(f"  예시:")
    print(f"    from herbie import Herbie")
    print(f"    H = Herbie('{date.strftime('%Y-%m-%d %H:00')}', model='gfs', product='pgrb2.0p25')")
    print(f"    H.download()")
    print()
    
    print(f"방법 4: 기존 데이터 활용 (추천)")
    print(f"  기존 7시간 GFS 캐시를 24시간으로 확장:")
    print(f"  python tests/integration/extend_gfs_to_24h.py")
    print()
    
    return None


def create_sample_gfs_24h():
    """샘플 24시간 GFS 데이터 생성 (테스트용)."""
    print(f"\n{'='*80}")
    print(f"  샘플 24시간 GFS 데이터 생성")
    print(f"{'='*80}\n")
    
    print(f"⚠ 이것은 실제 기상 데이터가 아닌 테스트용 샘플입니다!")
    print()
    
    # 기존 캐시 확장 실행
    import subprocess
    import sys
    
    result = subprocess.run(
        [sys.executable, "tests/integration/extend_gfs_to_24h.py"],
        capture_output=False
    )
    
    if result.returncode == 0:
        print(f"\n✓ 샘플 24시간 GFS 데이터 생성 완료")
        return True
    else:
        print(f"\n❌ 샘플 데이터 생성 실패")
        return False


def main():
    """메인 함수."""
    print(f"\n{'='*80}")
    print(f"  실제 GFS 0.25도 데이터 다운로드 도구")
    print(f"{'='*80}\n")
    
    print(f"이 도구는 실제 GFS 데이터 다운로드 방법을 안내합니다.")
    print()
    
    print(f"선택하세요:")
    print(f"  1. 실제 GFS 데이터 다운로드 방법 보기")
    print(f"  2. 기존 캐시를 24시간으로 확장 (추천)")
    print(f"  3. HYSPLIT Web 자동화로 실제 데이터 사용")
    
    choice = input(f"\n선택 (1-3): ").strip()
    
    if choice == "1":
        # 다운로드 방법 안내
        download_gfs_data_24h()
        
    elif choice == "2":
        # 기존 캐시 확장
        print(f"\n기존 GFS 캐시를 24시간으로 확장합니다...")
        success = create_sample_gfs_24h()
        
        if success:
            print(f"\n다음 단계:")
            print(f"  python tests/integration/test_24hour_comparison.py")
        
    elif choice == "3":
        # HYSPLIT Web 자동화
        print(f"\nHYSPLIT Web 자동화를 실행합니다...")
        print(f"이 방법은 실제 기상 데이터를 사용합니다.")
        print()
        
        import subprocess
        import sys
        
        result = subprocess.run(
            [sys.executable, "tests/integration/prepare_24h_test_data.py"],
            capture_output=False
        )
        
    else:
        print(f"잘못된 선택입니다.")


if __name__ == "__main__":
    main()
