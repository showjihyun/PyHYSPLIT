"""HYSPLIT Web 자동화 스크립트 (Playwright 사용).

Playwright를 사용하여 HYSPLIT Web에 접속하고,
서울 기준 역추적 궤적을 자동으로 실행한 후 결과를 다운로드합니다.

설치:
    pip install playwright
    playwright install chromium

실행:
    python tests/integration/hysplit_web_automation.py
"""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("Playwright가 설치되지 않았습니다.")
    print("설치: pip install playwright")
    print("브라우저 설치: playwright install chromium")
    exit(1)


async def run_hysplit_web_trajectory(
    lat: float = 37.5,
    lon: float = 127.0,
    height: int = 850,
    year: int = 2026,
    month: int = 2,
    day: int = 13,
    hour: int = 0,
    duration: int = -24,
    output_dir: str = "tests/integration",
    headless: bool = False,
):
    """HYSPLIT Web에서 역추적 궤적을 자동으로 실행합니다.

    Parameters
    ----------
    lat : float
        시작 위도 (도)
    lon : float
        시작 경도 (도)
    height : int
        시작 고도 (m AGL)
    year, month, day, hour : int
        시작 시간 (UTC)
    duration : int
        실행 시간 (시간, 음수=backward)
    output_dir : str
        결과 저장 디렉토리
    headless : bool
        헤드리스 모드 (True=브라우저 창 숨김)
    """
    print(f"\n{'='*80}")
    print(f"  HYSPLIT Web 자동화 시작")
    print(f"{'='*80}")
    print(f"  위치: {lat}°N, {lon}°E")
    print(f"  고도: {height}m AGL")
    print(f"  시작: {year}-{month:02d}-{day:02d} {hour:02d}:00 UTC")
    print(f"  기간: {duration}h ({'backward' if duration < 0 else 'forward'})")
    print(f"{'='*80}\n")

    async with async_playwright() as p:
        # 브라우저 실행
        print("1. 브라우저 실행 중...")
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # HYSPLIT Web 접속
            print("2. HYSPLIT Web 접속 중...")
            url = "https://www.ready.noaa.gov/HYSPLIT_traj.php"
            await page.goto(url, timeout=60000)
            await page.wait_for_load_state("networkidle")
            print("   ✓ 페이지 로드 완료")

            # 위도 입력
            print(f"3. 시작 위치 설정 중... ({lat}°N, {lon}°E)")
            await page.fill('input[name="lat"]', str(lat))
            await page.fill('input[name="lon"]', str(lon))
            print("   ✓ 위도/경도 입력 완료")

            # 고도 입력
            print(f"4. 시작 고도 설정 중... ({height}m AGL)")
            await page.fill('input[name="height"]', str(height))
            print("   ✓ 고도 입력 완료")

            # 시작 시간 설정
            print(f"5. 시작 시간 설정 중... ({year}-{month:02d}-{day:02d} {hour:02d}:00 UTC)")
            await page.select_option('select[name="year"]', str(year))
            await page.select_option('select[name="month"]', str(month))
            await page.select_option('select[name="day"]', str(day))
            await page.select_option('select[name="hour"]', str(hour))
            print("   ✓ 시작 시간 입력 완료")

            # 실행 시간 설정
            print(f"6. 실행 시간 설정 중... ({duration}h)")
            await page.fill('input[name="runtime"]', str(duration))
            print("   ✓ 실행 시간 입력 완료")

            # 기상 데이터 선택 (GFS 0.25도)
            print("7. 기상 데이터 선택 중... (GFS 0.25°)")
            # GFS 0.25도 라디오 버튼 찾기 및 선택
            try:
                await page.check('input[value="gfs0p25"]', timeout=5000)
                print("   ✓ GFS 0.25° 선택 완료")
            except:
                print("   ⚠ GFS 0.25° 라디오 버튼을 찾을 수 없음 (기본값 사용)")

            # 수직 운동 모드 선택 (Model Vertical Velocity)
            print("8. 수직 운동 모드 설정 중...")
            try:
                await page.check('input[value="0"]', timeout=5000)
                print("   ✓ Model Vertical Velocity 선택 완료")
            except:
                print("   ⚠ 수직 운동 모드 선택 실패 (기본값 사용)")

            # 스크린샷 저장 (설정 확인용)
            screenshot_path = Path(output_dir) / "hysplit_web_settings.png"
            await page.screenshot(path=str(screenshot_path))
            print(f"   ✓ 설정 스크린샷 저장: {screenshot_path}")

            # Run Model 버튼 클릭
            print("9. 모델 실행 중...")
            print("   (이 작업은 1~2분 소요될 수 있습니다)")
            
            # 새 페이지가 열릴 것을 대비
            async with context.expect_page() as new_page_info:
                await page.click('input[type="submit"][value="Run Model"]')
            
            result_page = await new_page_info.value
            await result_page.wait_for_load_state("networkidle", timeout=120000)
            print("   ✓ 모델 실행 완료")

            # 결과 페이지 대기
            print("10. 결과 페이지 로딩 중...")
            await asyncio.sleep(5)  # 결과 렌더링 대기
            
            # 결과 스크린샷 저장
            result_screenshot = Path(output_dir) / "hysplit_web_result.png"
            await result_page.screenshot(path=str(result_screenshot), full_page=True)
            print(f"   ✓ 결과 스크린샷 저장: {result_screenshot}")

            # 궤적 종료점 정보 추출
            print("11. 궤적 정보 추출 중...")
            try:
                # 페이지 텍스트에서 궤적 정보 찾기
                content = await result_page.content()
                
                # 종료점 좌표 패턴 찾기 (예: "37.5N 127.0E")
                lat_pattern = r'(\d+\.\d+)[NS]'
                lon_pattern = r'(\d+\.\d+)[EW]'
                
                lats = re.findall(lat_pattern, content)
                lons = re.findall(lon_pattern, content)
                
                if lats and lons:
                    print(f"   ✓ 궤적 종료점 발견:")
                    print(f"     위도: {lats[-1]}°N")
                    print(f"     경도: {lons[-1]}°E")
                else:
                    print("   ⚠ 궤적 종료점 정보를 추출할 수 없음")
                
            except Exception as e:
                print(f"   ⚠ 정보 추출 실패: {e}")

            # tdump 파일 다운로드 시도
            print("12. tdump 파일 다운로드 시도 중...")
            try:
                # 다운로드 링크 찾기
                download_link = result_page.locator('a:has-text("tdump")')
                if await download_link.count() > 0:
                    async with result_page.expect_download() as download_info:
                        await download_link.first.click()
                    download = await download_info.value
                    
                    tdump_path = Path(output_dir) / f"hysplit_web_seoul_{abs(duration)}h.tdump"
                    await download.save_as(str(tdump_path))
                    print(f"   ✓ tdump 파일 저장: {tdump_path}")
                else:
                    print("   ⚠ tdump 다운로드 링크를 찾을 수 없음")
            except Exception as e:
                print(f"   ⚠ tdump 다운로드 실패: {e}")

            print(f"\n{'='*80}")
            print(f"  HYSPLIT Web 자동화 완료!")
            print(f"{'='*80}")
            print(f"  결과 파일:")
            print(f"    - 설정 스크린샷: {screenshot_path}")
            print(f"    - 결과 스크린샷: {result_screenshot}")
            if 'tdump_path' in locals():
                print(f"    - tdump 파일: {tdump_path}")
            print(f"{'='*80}\n")

            # 브라우저를 닫지 않고 대기 (결과 확인용)
            if not headless:
                print("브라우저 창을 확인하세요. 종료하려면 Enter를 누르세요...")
                input()

        except PlaywrightTimeout as e:
            print(f"\n❌ 타임아웃 오류: {e}")
            print("   HYSPLIT Web 서버가 응답하지 않거나 페이지 로딩이 느립니다.")
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()


async def main():
    """메인 함수."""
    # 서울 24시간 backward trajectory
    await run_hysplit_web_trajectory(
        lat=37.5,
        lon=127.0,
        height=850,
        year=2026,
        month=2,
        day=13,
        hour=0,
        duration=-24,
        headless=False,  # 브라우저 창 표시
    )


if __name__ == "__main__":
    asyncio.run(main())
