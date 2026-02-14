"""HYSPLIT Web에서 8개 지역의 tdump 파일을 자동으로 다운로드.

Playwright를 사용하여 HYSPLIT Web에서 8개 극동아시아 도시의
24시간 역추적 궤적을 실행하고 tdump 파일을 다운로드합니다.

설치:
    pip install playwright
    playwright install chromium

실행:
    python tests/integration/download_hysplit_web_data.py
"""

import asyncio
import time
from pathlib import Path
from datetime import datetime

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("❌ Playwright가 설치되지 않았습니다.")
    print("   설치: pip install playwright")
    print("   브라우저 설치: playwright install chromium")
    exit(1)


# 테스트 지역
TEST_LOCATIONS = {
    "서울": {"lat": 37.5, "lon": 127.0, "height": 850, "region": "한국"},
    "부산": {"lat": 35.1, "lon": 129.0, "height": 850, "region": "한국"},
    "제주": {"lat": 33.5, "lon": 126.5, "height": 850, "region": "한국"},
    "도쿄": {"lat": 35.7, "lon": 139.7, "height": 850, "region": "일본"},
    "오사카": {"lat": 34.7, "lon": 135.5, "height": 850, "region": "일본"},
    "베이징": {"lat": 39.9, "lon": 116.4, "height": 850, "region": "중국"},
    "상하이": {"lat": 31.2, "lon": 121.5, "height": 850, "region": "중국"},
    "타이베이": {"lat": 25.0, "lon": 121.5, "height": 850, "region": "대만"},
}


async def download_tdump_for_location(
    page,
    location_name: str,
    lat: float,
    lon: float,
    height: int,
    output_dir: Path,
):
    """한 지역에 대해 HYSPLIT Web 실행 및 tdump 다운로드.
    
    Parameters
    ----------
    page : Page
        Playwright 페이지 객체
    location_name : str
        지역 이름
    lat : float
        위도
    lon : float
        경도
    height : int
        고도 (m AGL)
    output_dir : Path
        출력 디렉토리
    """
    
    print(f"\n{'='*80}")
    print(f"  {location_name} 처리 중...")
    print(f"{'='*80}")
    print(f"  위치: {lat}°N, {lon}°E, {height}m AGL")
    
    try:
        # Step 1: HYSPLIT Trajectory 페이지 접속
        print("\n1. HYSPLIT Trajectory 페이지 접속 중...")
        await page.goto("https://www.ready.noaa.gov/HYSPLIT_traj.php", timeout=60000)
        await page.wait_for_load_state("networkidle")
        print("   ✓ 페이지 로드 완료")
        
        # Step 2: 설정 입력
        print("\n2. 설정 입력 중...")
        
        # 위도 입력
        await page.fill('input[name="latdeg"]', str(int(lat)))
        await page.fill('input[name="latmin"]', str(int((lat % 1) * 60)))
        print(f"   ✓ 위도: {lat}°N")
        
        # 경도 입력
        await page.fill('input[name="londeg"]', str(int(lon)))
        await page.fill('input[name="lonmin"]', str(int((lon % 1) * 60)))
        print(f"   ✓ 경도: {lon}°E")
        
        # 고도 입력
        await page.fill('input[name="height"]', str(height))
        print(f"   ✓ 고도: {height}m AGL")
        
        # 시작 시간 (2026-02-14 00:00 UTC)
        await page.select_option('select[name="year"]', "2026")
        await page.select_option('select[name="month"]', "2")
        await page.select_option('select[name="day"]', "14")
        await page.select_option('select[name="hour"]', "0")
        print(f"   ✓ 시작 시간: 2026-02-14 00:00 UTC")
        
        # 역추적 설정
        await page.select_option('select[name="direction"]', "backward")
        await page.fill('input[name="runtime"]', "24")
        print(f"   ✓ 역추적 24시간")
        
        # Vertical Motion: Model Vertical Velocity
        await page.select_option('select[name="vertmotion"]', "0")
        print(f"   ✓ Vertical Motion: Model Vertical Velocity")
        
        # Meteorology: GFS 0.25 degree
        await page.select_option('select[name="metdata"]', "gfs0p25")
        print(f"   ✓ Meteorology: GFS 0.25 degree")
        
        # Step 3: Run 버튼 클릭
        print("\n3. 궤적 계산 실행 중...")
        await page.click('input[type="submit"][value="Run"]')
        print("   ✓ Run 버튼 클릭")
        
        # 결과 페이지 대기 (최대 3분)
        print("   계산 대기 중... (최대 3분)")
        await page.wait_for_load_state("networkidle", timeout=180000)
        print("   ✓ 계산 완료")
        
        # Step 4: tdump 파일 다운로드
        print("\n4. tdump 파일 다운로드 중...")
        
        # "Trajectory Endpoints" 링크 찾기
        try:
            # 다운로드 대기 설정
            async with page.expect_download(timeout=30000) as download_info:
                # "Trajectory Endpoints" 또는 "tdump" 링크 클릭
                await page.click('text=/Trajectory Endpoints|tdump/i')
            
            download = await download_info.value
            
            # 파일 저장
            tdump_path = output_dir / f"tdump_{location_name}.txt"
            await download.save_as(tdump_path)
            print(f"   ✓ tdump 파일 저장: {tdump_path}")
            
            return True
            
        except Exception as e:
            print(f"   ❌ tdump 다운로드 실패: {e}")
            
            # 대안: 페이지 소스에서 tdump 데이터 추출
            print("   대안: 페이지 소스에서 tdump 추출 시도...")
            try:
                content = await page.content()
                
                # tdump 데이터가 <pre> 태그 안에 있는 경우
                pre_element = await page.query_selector('pre')
                if pre_element:
                    tdump_content = await pre_element.inner_text()
                    
                    tdump_path = output_dir / f"tdump_{location_name}.txt"
                    with open(tdump_path, 'w', encoding='utf-8') as f:
                        f.write(tdump_content)
                    print(f"   ✓ tdump 파일 저장 (페이지 소스): {tdump_path}")
                    return True
                else:
                    print(f"   ❌ tdump 데이터를 찾을 수 없습니다")
                    return False
                    
            except Exception as e2:
                print(f"   ❌ 페이지 소스 추출 실패: {e2}")
                return False
    
    except PlaywrightTimeout as e:
        print(f"\n❌ 타임아웃 오류: {e}")
        return False
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """메인 함수."""
    
    print("\n" + "="*80)
    print("  HYSPLIT Web 8개 지역 자동 다운로드")
    print("="*80 + "\n")
    
    print("설정:")
    print("  - Meteorology: GFS 0.25 degree")
    print("  - Start Time: 2026-02-14 00:00 UTC")
    print("  - Direction: Backward")
    print("  - Duration: 24 hours")
    print("  - Vertical Motion: Model Vertical Velocity")
    print("  - 지역: 8개 (서울, 부산, 제주, 도쿄, 오사카, 베이징, 상하이, 타이베이)")
    
    # 출력 디렉토리
    output_dir = Path("tests/integration/hysplit_web_data")
    output_dir.mkdir(exist_ok=True)
    
    # 브라우저 실행
    print(f"\n브라우저 실행 중...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # 진행 상황 확인을 위해 headless=False
        context = await browser.new_context()
        page = await context.new_page()
        
        results = {}
        
        try:
            # 각 지역에 대해 실행
            for i, (location_name, info) in enumerate(TEST_LOCATIONS.items(), 1):
                print(f"\n\n{'#'*80}")
                print(f"  진행: {i}/8 - {location_name} ({info['region']})")
                print(f"{'#'*80}")
                
                success = await download_tdump_for_location(
                    page,
                    location_name,
                    info['lat'],
                    info['lon'],
                    info['height'],
                    output_dir
                )
                
                results[location_name] = success
                
                if success:
                    print(f"\n✅ {location_name} 완료!")
                else:
                    print(f"\n❌ {location_name} 실패")
                
                # 다음 지역을 위해 잠시 대기
                if i < len(TEST_LOCATIONS):
                    print(f"\n다음 지역 준비 중... (3초 대기)")
                    await asyncio.sleep(3)
            
            # 결과 요약
            print(f"\n\n{'='*80}")
            print(f"  다운로드 완료!")
            print(f"{'='*80}\n")
            
            success_count = sum(1 for v in results.values() if v)
            print(f"성공: {success_count}/{len(TEST_LOCATIONS)}")
            print(f"\n지역별 결과:")
            for location_name, success in results.items():
                status = "✅" if success else "❌"
                print(f"  {status} {location_name}")
            
            print(f"\n저장 위치: {output_dir}/")
            print(f"\n다음 단계:")
            print(f"  python tests\\integration\\multi_location_24h_comparison.py --compare")
            
        finally:
            print(f"\n브라우저를 닫습니다...")
            await browser.close()


if __name__ == "__main__":
    print("\n⚠️  주의사항:")
    print("  - HYSPLIT Web 서버 상태에 따라 시간이 오래 걸릴 수 있습니다")
    print("  - 각 지역당 2-5분 소요 예상 (총 20-40분)")
    print("  - 브라우저 창이 열리며 진행 상황을 확인할 수 있습니다")
    print("  - 실패 시 수동으로 다운로드해야 할 수 있습니다\n")
    
    response = input("계속하시겠습니까? (y/n): ")
    if response.lower() == 'y':
        asyncio.run(main())
    else:
        print("취소되었습니다.")
