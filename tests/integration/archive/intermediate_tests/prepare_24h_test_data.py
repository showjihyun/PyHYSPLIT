"""24시간 역궤적 테스트를 위한 데이터 준비 스크립트.

이 스크립트는:
1. HYSPLIT Web에서 24시간 역궤적 실행 및 결과 다운로드
2. GFS 데이터 다운로드 및 1시간 간격으로 보간
3. 24시간 비교 테스트 실행

사용법:
    python tests/integration/prepare_24h_test_data.py
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


async def prepare_hysplit_web_24h():
    """HYSPLIT Web에서 24시간 역궤적 실행."""
    print(f"\n{'='*80}")
    print(f"  1단계: HYSPLIT Web 24시간 역궤적 실행")
    print(f"{'='*80}\n")
    
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("❌ Playwright가 설치되지 않았습니다.")
        print("   설치: pip install playwright")
        print("   브라우저 설치: playwright install chromium")
        return False
    
    # 테스트 조건
    lat = 37.0
    lon = 127.0
    height = 850
    duration = -24  # 24시간 역궤적
    
    print(f"설정:")
    print(f"  위치: {lat}°N, {lon}°E")
    print(f"  고도: {height}m AGL")
    print(f"  기간: {duration}h (24시간 역궤적)")
    print()
    
    # HYSPLIT Web 자동화 실행
    from tests.integration.hysplit_web_full_automation import run_hysplit_web_full
    
    try:
        await run_hysplit_web_full(
            lat=lat,
            lon=lon,
            height=height,
            duration=duration,
            output_dir="tests/integration",
            headless=False  # 브라우저 창 표시
        )
        print("\n✓ HYSPLIT Web 24시간 역궤적 완료")
        
        # 결과 파일 확인
        endpoints_file = Path("tests/integration/hysplit_trajectory_endpoints.txt")
        if endpoints_file.exists():
            # 24시간용으로 복사
            endpoints_24h = Path("tests/integration/hysplit_trajectory_endpoints_24h.txt")
            import shutil
            shutil.copy(endpoints_file, endpoints_24h)
            print(f"✓ 결과 저장: {endpoints_24h}")
            return True
        else:
            print(f"❌ 결과 파일을 찾을 수 없습니다: {endpoints_file}")
            return False
            
    except Exception as e:
        print(f"❌ HYSPLIT Web 실행 실패: {e}")
        return False


def prepare_gfs_24h_data():
    """GFS 데이터 다운로드 및 24시간 분량 준비."""
    print(f"\n{'='*80}")
    print(f"  2단계: GFS 데이터 준비 (25시간 분량)")
    print(f"{'='*80}\n")
    
    # 기존 GFS 캐시 확인
    gfs_cache_dir = Path("tests/integration/gfs_cache")
    if not gfs_cache_dir.exists():
        gfs_cache_dir.mkdir(parents=True)
    
    # 기존 캐시 파일 찾기
    existing_cache = list(gfs_cache_dir.glob("gfs_*.nc"))
    
    if existing_cache:
        print(f"기존 GFS 캐시 파일 발견:")
        for cache_file in existing_cache:
            print(f"  - {cache_file.name}")
        
        # 가장 최근 파일 사용
        latest_cache = max(existing_cache, key=lambda p: p.stat().st_mtime)
        print(f"\n사용할 파일: {latest_cache.name}")
        
        # 24시간 분량인지 확인
        try:
            import netCDF4
            ds = netCDF4.Dataset(str(latest_cache))
            time_var = ds.variables['time'][:]
            ds.close()
            
            time_hours = time_var / 3600.0
            time_span = time_hours[-1] - time_hours[0]
            
            print(f"  시간 범위: {time_hours[0]:.1f}h ~ {time_hours[-1]:.1f}h ({time_span:.1f}시간)")
            
            if time_span >= 24:
                print(f"✓ 24시간 이상의 데이터 확인")
                
                # 24시간용 캐시로 복사
                cache_24h = gfs_cache_dir / "gfs_24h_cache.nc"
                import shutil
                shutil.copy(latest_cache, cache_24h)
                print(f"✓ 24시간 캐시 생성: {cache_24h}")
                return True
            else:
                print(f"⚠ 데이터가 24시간 미만입니다. 추가 데이터가 필요합니다.")
                
        except Exception as e:
            print(f"⚠ 캐시 파일 확인 실패: {e}")
    
    # 새로운 GFS 데이터 다운로드 필요
    print(f"\n새로운 GFS 데이터 다운로드가 필요합니다.")
    print(f"다음 중 하나를 실행하세요:")
    print(f"  1. 수동 다운로드: NOAA GFS 데이터 사이트에서 다운로드")
    print(f"  2. 기존 테스트 실행: python -m pytest tests/integration/test_hysplit_web_comparison.py")
    print(f"     (이 테스트가 GFS 캐시를 생성합니다)")
    
    return False


def check_dependencies():
    """필요한 패키지 확인."""
    print(f"\n{'='*80}")
    print(f"  의존성 확인")
    print(f"{'='*80}\n")
    
    missing = []
    
    # Playwright 확인
    try:
        import playwright
        print("✓ playwright 설치됨")
    except ImportError:
        print("❌ playwright 미설치")
        missing.append("playwright")
    
    # netCDF4 확인
    try:
        import netCDF4
        print("✓ netCDF4 설치됨")
    except ImportError:
        print("❌ netCDF4 미설치")
        missing.append("netCDF4")
    
    # scipy 확인
    try:
        import scipy
        print("✓ scipy 설치됨")
    except ImportError:
        print("❌ scipy 미설치")
        missing.append("scipy")
    
    # matplotlib 확인
    try:
        import matplotlib
        print("✓ matplotlib 설치됨")
    except ImportError:
        print("⚠ matplotlib 미설치 (시각화 불가)")
    
    if missing:
        print(f"\n필요한 패키지 설치:")
        print(f"  pip install {' '.join(missing)}")
        if 'playwright' in missing:
            print(f"  playwright install chromium")
        return False
    
    return True


async def main():
    """메인 함수."""
    print(f"\n{'='*80}")
    print(f"  24시간 역궤적 테스트 데이터 준비")
    print(f"{'='*80}\n")
    
    # 의존성 확인
    if not check_dependencies():
        print(f"\n❌ 필요한 패키지를 먼저 설치하세요.")
        return
    
    # 사용자 선택
    print(f"\n준비할 데이터를 선택하세요:")
    print(f"  1. HYSPLIT Web 24시간 궤적만 실행")
    print(f"  2. GFS 데이터만 준비")
    print(f"  3. 둘 다 준비 (전체)")
    print(f"  4. 기존 데이터로 24시간 테스트 실행")
    
    choice = input(f"\n선택 (1-4): ").strip()
    
    if choice == "1":
        # HYSPLIT Web만
        success = await prepare_hysplit_web_24h()
        if success:
            print(f"\n✓ HYSPLIT Web 데이터 준비 완료")
            print(f"  다음: GFS 데이터를 준비하세요 (옵션 2)")
        
    elif choice == "2":
        # GFS 데이터만
        success = prepare_gfs_24h_data()
        if success:
            print(f"\n✓ GFS 데이터 준비 완료")
            print(f"  다음: HYSPLIT Web 궤적을 실행하세요 (옵션 1)")
        
    elif choice == "3":
        # 둘 다
        print(f"\n전체 데이터 준비를 시작합니다...")
        
        # HYSPLIT Web 실행
        web_success = await prepare_hysplit_web_24h()
        
        # GFS 데이터 준비
        gfs_success = prepare_gfs_24h_data()
        
        if web_success and gfs_success:
            print(f"\n{'='*80}")
            print(f"  ✓ 모든 데이터 준비 완료!")
            print(f"{'='*80}\n")
            print(f"다음 명령으로 24시간 테스트를 실행하세요:")
            print(f"  python tests/integration/test_24hour_comparison.py")
        else:
            print(f"\n⚠ 일부 데이터 준비 실패")
            if not web_success:
                print(f"  - HYSPLIT Web 데이터 준비 실패")
            if not gfs_success:
                print(f"  - GFS 데이터 준비 실패")
    
    elif choice == "4":
        # 기존 데이터로 테스트
        print(f"\n기존 데이터로 24시간 테스트를 실행합니다...")
        
        # 파일 존재 확인
        endpoints_24h = Path("tests/integration/hysplit_trajectory_endpoints_24h.txt")
        gfs_24h = Path("tests/integration/gfs_cache/gfs_24h_cache.nc")
        
        if not endpoints_24h.exists():
            print(f"❌ HYSPLIT Web 결과 파일이 없습니다: {endpoints_24h}")
            print(f"   옵션 1을 먼저 실행하세요.")
            return
        
        if not gfs_24h.exists():
            print(f"❌ GFS 캐시 파일이 없습니다: {gfs_24h}")
            print(f"   옵션 2를 먼저 실행하세요.")
            return
        
        print(f"✓ 필요한 파일 확인 완료")
        print(f"  - {endpoints_24h}")
        print(f"  - {gfs_24h}")
        
        # 테스트 실행
        import subprocess
        result = subprocess.run(
            ["python", "tests/integration/test_24hour_comparison.py"],
            capture_output=False
        )
        
        if result.returncode == 0:
            print(f"\n✓ 24시간 테스트 완료!")
            print(f"  결과: tests/integration/HYSPLIT_WEB_24H_COMPARISON.md")
            print(f"  시각화: tests/integration/comparison_24h_visualization.png")
        else:
            print(f"\n❌ 24시간 테스트 실패")
    
    else:
        print(f"잘못된 선택입니다.")


if __name__ == "__main__":
    asyncio.run(main())
