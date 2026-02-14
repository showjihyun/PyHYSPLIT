"""HYSPLIT Web 완전 자동화 스크립트 (Playwright 사용).

사용자가 제공한 정확한 워크플로우를 따라 HYSPLIT Web에서
역추적 궤적을 자동으로 실행하고 결과를 다운로드합니다.

워크플로우:
1. https://www.ready.noaa.gov/hypub-bin/trajsrc.pl 접속
2. Meteorology: GFS 0.25 Degree 선택, Longitude/Latitude 입력
3. Next 버튼 클릭
4. Select Meteorological Forecast Cycle 선택
5. https://www.ready.noaa.gov/hypub-bin/traj1.pl 화면에서 관련 항목 입력
6. Run trajectory 버튼 클릭
7. Model Status와 Result 이미지 다운로드

설치:
    pip install playwright
    playwright install chromium

실행:
    python tests/integration/hysplit_web_full_automation.py
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime
from pathlib import Path

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("Playwright가 설치되지 않았습니다.")
    print("설치: pip install playwright")
    print("브라우저 설치: playwright install chromium")
    exit(1)


async def run_hysplit_web_full(
    lat: float = 37.5,
    lon: float = 127.0,
    height: int = 850,
    year: int = None,  # None이면 forecast cycle에서 자동 선택
    month: int = None,
    day: int = None,
    hour: int = None,
    duration: int = -24,
    output_dir: str = "tests/integration",
    headless: bool = False,
):
    """HYSPLIT Web에서 역추적 궤적을 완전 자동으로 실행합니다.

    Parameters
    ----------
    lat : float
        시작 위도 (도)
    lon : float
        시작 경도 (도)
    height : int
        시작 고도 (m AGL)
    year, month, day, hour : int or None
        시작 시간 (UTC). None이면 forecast cycle에서 자동 선택
    duration : int
        실행 시간 (시간, 음수=backward)
    output_dir : str
        결과 저장 디렉토리
    headless : bool
        헤드리스 모드 (True=브라우저 창 숨김)
    """
    # 시간이 지정되지 않으면 자동 선택 모드
    auto_time = (year is None or month is None or day is None or hour is None)
    
    print(f"\n{'='*80}")
    print(f"  HYSPLIT Web 완전 자동화 시작")
    print(f"{'='*80}")
    print(f"  위치: {lat}°N, {lon}°E")
    print(f"  고도: {height}m AGL")
    if not auto_time:
        print(f"  시작: {year}-{month:02d}-{day:02d} {hour:02d}:00 UTC")
    else:
        print(f"  시작: 자동 선택 (forecast cycle 기준)")
    print(f"  기간: {duration}h ({'backward' if duration < 0 else 'forward'})")
    print(f"{'='*80}\n")

    async with async_playwright() as p:
        # 브라우저 실행
        print("1. 브라우저 실행 중...")
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # Step 1: trajsrc.pl 페이지 접속 (Meteorology & Starting Location)
            print("\n2. HYSPLIT Web 접속 중...")
            url = "https://www.ready.noaa.gov/hypub-bin/trajsrc.pl"
            await page.goto(url, timeout=60000)
            await page.wait_for_load_state("networkidle")
            print("   ✓ trajsrc.pl 페이지 로드 완료")

            # Step 2: Meteorology 선택 및 좌표 입력
            print(f"\n3. 기상 데이터 및 좌표 설정 중...")
            
            # GFS 0.25 Degree 선택 (select 요소)
            try:
                await page.select_option('select[name="metdata"]', value='GFS0p25')
                print("   ✓ GFS 0.25 Degree 선택")
            except Exception as e:
                print(f"   ⚠ GFS 0.25 선택 실패: {e}")

            # 위도 입력 (Source 1)
            try:
                await page.fill('input[name="Lat"]', str(abs(lat)))
                print(f"   ✓ 위도 입력: {abs(lat)}°")
                
                # 위도 방향 선택 (N/S)
                lat_direction = 'N' if lat >= 0 else 'S'
                await page.select_option('select[name="Latns"]', label=lat_direction)
                print(f"   ✓ 위도 방향: {lat_direction}")
            except Exception as e:
                print(f"   ⚠ 위도 입력 실패: {e}")

            # 경도 입력 (Source 1)
            try:
                await page.fill('input[name="Lon"]', str(abs(lon)))
                print(f"   ✓ 경도 입력: {abs(lon)}°")
                
                # 경도 방향 선택 (E/W)
                lon_direction = 'E' if lon >= 0 else 'W'
                await page.select_option('select[name="Lonew"]', label=lon_direction)
                print(f"   ✓ 경도 방향: {lon_direction}")
            except Exception as e:
                print(f"   ⚠ 경도 입력 실패: {e}")

            # 스크린샷 저장
            screenshot1 = Path(output_dir) / "hysplit_step1_trajsrc.png"
            await page.screenshot(path=str(screenshot1))
            print(f"   ✓ 스크린샷 저장: {screenshot1}")

            # Step 3: Next 버튼 클릭
            print("\n4. Next 버튼 클릭 중...")
            try:
                await page.click('input[type="button"][value="Next>>"]')
                await page.wait_for_load_state("networkidle", timeout=30000)
                print("   ✓ 다음 페이지로 이동")
            except Exception as e:
                print(f"   ⚠ Next 버튼 클릭 실패: {e}")

            # Step 4: Meteorological Forecast Cycle 선택
            print("\n5. Meteorological Forecast Cycle 선택 중...")
            
            # forecast cycle select 요소에서 첫 번째 옵션 선택
            try:
                # 가장 최신 forecast cycle 선택 (첫 번째 옵션)
                await page.select_option('select[name="metcyc"]', index=0)
                print("   ✓ 최신 Forecast Cycle 선택")
            except Exception as e:
                print(f"   ⚠ Forecast Cycle 선택 실패: {e}")

            screenshot2 = Path(output_dir) / "hysplit_step2_forecast.png"
            await page.screenshot(path=str(screenshot2))
            print(f"   ✓ 스크린샷 저장: {screenshot2}")

            # Next 버튼 클릭 (submit 타입)
            try:
                await page.click('input[type="submit"][value="Next>>"]')
                await page.wait_for_load_state("networkidle", timeout=30000)
                print("   ✓ traj1.pl 페이지로 이동")
            except Exception as e:
                print(f"   ⚠ Next 버튼 클릭 실패: {e}")

            # Step 5: traj1.pl 페이지에서 궤적 설정
            print("\n6. 궤적 설정 입력 중...")
            
            # 자동 시간 선택 모드: 페이지의 기본값 사용 (forecast cycle 기준)
            if auto_time:
                print("   ✓ 시간: 자동 선택 (페이지 기본값 사용)")
                # 페이지에 이미 선택된 값 확인
                try:
                    year_select = page.locator('select[name="Start year"]').first
                    selected_year = await year_select.input_value()
                    month_select = page.locator('select[name="Start month"]').first
                    selected_month = await month_select.input_value()
                    day_select = page.locator('select[name="Start day"]').first
                    selected_day = await day_select.input_value()
                    hour_select = page.locator('select[name="Start hour"]').first
                    selected_hour = await hour_select.input_value()
                    print(f"   ✓ 선택된 시간: 20{selected_year}-{selected_month}-{selected_day} {selected_hour}:00 UTC")
                except:
                    print("   ⚠ 선택된 시간 확인 실패")
            else:
                # 수동 시간 설정
                # 시작 시간 설정
                try:
                    # Year (2026 → 26)
                    year_select = page.locator('select[name="Start year"]').first
                    await year_select.select_option(label=str(year % 100))
                    print(f"   ✓ 연도: {year}")
                except Exception as e:
                    print(f"   ⚠ 연도 선택 실패: {e}")

                try:
                    # Month
                    month_select = page.locator('select[name="Start month"]').first
                    await month_select.select_option(label=f"{month:02d}")
                    print(f"   ✓ 월: {month}")
                except Exception as e:
                    print(f"   ⚠ 월 선택 실패: {e}")

                try:
                    # Day
                    day_select = page.locator('select[name="Start day"]').first
                    await day_select.select_option(label=str(day))
                    print(f"   ✓ 일: {day}")
                except Exception as e:
                    print(f"   ⚠ 일 선택 실패: {e}")

                try:
                    # Hour (0시는 "0", 1~9시는 "1"~"9", 10시 이상은 "10"~"23")
                    hour_select = page.locator('select[name="Start hour"]').first
                    hour_str = str(hour) if hour > 0 else "0"
                    await hour_select.select_option(label=hour_str)
                    print(f"   ✓ 시간: {hour}:00 UTC")
                except Exception as e:
                    print(f"   ⚠ 시간 선택 실패: {e}")
            
            # Direction 선택 (Forward/Backward)
            try:
                direction_value = 'Backward' if duration < 0 else 'Forward'
                await page.check(f'input[type="RADIO"][name="direction"][value="{direction_value}"]')
                print(f"   ✓ 방향: {direction_value}")
            except Exception as e:
                print(f"   ⚠ 방향 선택 실패: {e}")

            # 시작 고도 입력
            try:
                height_input = page.locator('input[name="Source hgt1"]').first
                await height_input.fill(str(height))
                print(f"   ✓ 고도: {height}m AGL")
                
                # 고도 단위 선택 (0 = meters AGL)
                await page.check('input[type="RADIO"][name="Source hunit"][value="0"]')
            except Exception as e:
                print(f"   ⚠ 고도 입력 실패: {e}")

            # 실행 시간 입력 (절댓값)
            try:
                runtime_input = page.locator('input[name="duration"]').first
                await runtime_input.fill(str(abs(duration)))
                print(f"   ✓ 실행 시간: {abs(duration)}h")
            except Exception as e:
                print(f"   ⚠ 실행 시간 입력 실패: {e}")

            # 수직 운동 모드 선택 (Model Vertical Velocity = 0)
            try:
                await page.check('input[type="RADIO"][name="vertical"][value="0"]')
                print("   ✓ 수직 운동: Model Vertical Velocity")
            except Exception as e:
                print(f"   ⚠ 수직 운동 모드 선택 실패: {e}")

            screenshot3 = Path(output_dir) / "hysplit_step3_traj_settings.png"
            await page.screenshot(path=str(screenshot3))
            print(f"   ✓ 스크린샷 저장: {screenshot3}")

            # Step 6: Run trajectory 버튼 클릭
            print("\n7. Run trajectory 버튼 클릭 중...")
            print("   (모델 실행은 1~3분 소요될 수 있습니다)")
            
            try:
                await page.click('input[type="submit"][value="Request trajectory"]')
                print("   ✓ 궤적 계산 시작")
            except Exception as e:
                print(f"   ⚠ Run 버튼 클릭 실패: {e}")

            # Step 7: 결과 대기 및 다운로드
            print("\n8. 결과 대기 중...")
            
            # 결과 페이지 로딩 대기 (최대 3분)
            try:
                await page.wait_for_load_state("networkidle", timeout=180000)
                print("   ✓ 결과 페이지 로드 완료")
            except PlaywrightTimeout:
                print("   ⚠ 결과 로딩 타임아웃 (3분 초과)")

            # 그래픽 파일이 준비될 때까지 대기 (간단한 폴링 방식)
            print("   그래픽 파일 생성 대기 중...")
            graphics_ready = False
            for attempt in range(24):  # 24 * 5초 = 2분
                try:
                    await asyncio.sleep(5)
                    # h2 요소에 "There are no graphics files available yet" 텍스트가 있는지 확인
                    no_graphics = await page.locator('h2:has-text("There are no graphics files available yet")').count()
                    
                    if no_graphics == 0:
                        graphics_ready = True
                        print(f"   ✓ 그래픽 파일 준비 완료 ({(attempt+1)*5}초 경과)")
                        break
                    else:
                        if (attempt + 1) % 2 == 0:  # 10초마다 출력
                            print(f"   - 대기 중... ({(attempt+1)*5}초 경과)")
                except Exception as e:
                    # 페이지 전환 중 오류 무시
                    pass
            
            if not graphics_ready:
                print("   ⚠ 그래픽 파일 생성 타임아웃 (2분 초과)")

            # 추가 대기 (결과 렌더링)
            await asyncio.sleep(5)

            # 결과 스크린샷 저장
            result_screenshot = Path(output_dir) / "hysplit_result_full.png"
            await page.screenshot(path=str(result_screenshot), full_page=True)
            print(f"   ✓ 결과 스크린샷 저장: {result_screenshot}")

            # 페이지 내용 분석
            print("\n9. 결과 분석 중...")
            content = await page.content()
            
            # Model Status 확인
            if "Model Status" in content or "Complete" in content or "SUCCESS" in content:
                print("   ✓ 모델 실행 완료")
            else:
                print("   ⚠ 모델 상태 확인 불가")

            # 궤적 이미지 찾기
            try:
                # javascript:wndw 링크 찾기 (GIF 이미지)
                gif_links = await page.locator('a[href*=".gif"]').all()
                print(f"   ✓ {len(gif_links)}개의 GIF 이미지 발견")
                
                # 이미지 다운로드
                for i, link in enumerate(gif_links[:3]):  # 최대 3개
                    href = await link.get_attribute('href')
                    if href:
                        # javascript:wndw('/hypubout/143184_trj001.gif') → /hypubout/143184_trj001.gif
                        if 'javascript:wndw' in href:
                            import re
                            match = re.search(r"'([^']+)'", href)
                            if match:
                                src = match.group(1)
                            else:
                                continue
                        else:
                            src = href
                        
                        # 상대 경로를 절대 경로로 변환
                        if not src.startswith('http'):
                            src = f"https://www.ready.noaa.gov{src if src.startswith('/') else '/' + src}"
                        
                        print(f"   - 이미지 {i+1}: {src}")
                        
                        # GIF 이미지 직접 다운로드
                        try:
                            img_page = await context.new_page()
                            response = await img_page.goto(src, timeout=30000)
                            
                            if response and response.ok:
                                img_path = Path(output_dir) / f"hysplit_result_trajectory_{i+1}.gif"
                                img_data = await response.body()
                                with open(img_path, 'wb') as f:
                                    f.write(img_data)
                                print(f"     ✓ 저장: {img_path}")
                            else:
                                print(f"     ⚠ 다운로드 실패: HTTP {response.status if response else 'No response'}")
                            
                            await img_page.close()
                        except Exception as e:
                            print(f"     ⚠ 다운로드 실패: {e}")
                
                # Trajectory endpoints 파일 다운로드
                tdump_links = await page.locator('a[href*="tdump"]').all()
                if tdump_links:
                    href = await tdump_links[0].get_attribute('href')
                    if href and 'javascript:wndw' in href:
                        import re
                        match = re.search(r"'([^']+)'", href)
                        if match:
                            src = match.group(1)
                            if not src.startswith('http'):
                                src = f"https://www.ready.noaa.gov{src if src.startswith('/') else '/' + src}"
                            print(f"\n   Trajectory endpoints 파일: {src}")
                            try:
                                # 텍스트 파일 다운로드
                                tdump_page = await context.new_page()
                                await tdump_page.goto(src, timeout=30000)
                                tdump_content = await tdump_page.content()
                                tdump_path = Path(output_dir) / "hysplit_trajectory_endpoints.txt"
                                
                                # <pre> 태그 내용 추출
                                pre_content = await tdump_page.locator('pre').first.inner_text()
                                with open(tdump_path, 'w', encoding='utf-8') as f:
                                    f.write(pre_content)
                                
                                await tdump_page.close()
                                print(f"   ✓ Endpoints 파일 저장: {tdump_path}")
                            except Exception as e:
                                print(f"   ⚠ Endpoints 파일 다운로드 실패: {e}")
            except Exception as e:
                print(f"   ⚠ 이미지 찾기 실패: {e}")

            # 종료점 좌표 추출
            try:
                # 좌표 패턴 찾기
                lat_matches = re.findall(r'(\d+\.\d+)\s*[°]?\s*[NS]', content)
                lon_matches = re.findall(r'(\d+\.\d+)\s*[°]?\s*[EW]', content)
                
                if lat_matches and lon_matches:
                    print(f"\n   궤적 좌표 발견:")
                    print(f"     시작점: {lat_matches[0]}°N, {lon_matches[0]}°E")
                    if len(lat_matches) > 1:
                        print(f"     종료점: {lat_matches[-1]}°N, {lon_matches[-1]}°E")
            except:
                pass

            # HTML 저장
            html_path = Path(output_dir) / "hysplit_result.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"\n   ✓ 결과 HTML 저장: {html_path}")

            print(f"\n{'='*80}")
            print(f"  HYSPLIT Web 자동화 완료!")
            print(f"{'='*80}")
            print(f"  결과 파일:")
            print(f"    - Step 1 스크린샷: {screenshot1}")
            print(f"    - Step 2 스크린샷: {screenshot2}")
            print(f"    - Step 3 스크린샷: {screenshot3}")
            print(f"    - 결과 스크린샷: {result_screenshot}")
            print(f"    - 결과 HTML: {html_path}")
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
    # 서울 24시간 backward trajectory (자동 시간 선택)
    await run_hysplit_web_full(
        lat=37.5,
        lon=127.0,
        height=850,
        year=None,  # 자동 선택
        month=None,
        day=None,
        hour=None,
        duration=-24,
        headless=False,  # 브라우저 창 표시
    )


if __name__ == "__main__":
    asyncio.run(main())
