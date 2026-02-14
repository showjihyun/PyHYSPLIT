"""HYSPLIT Web에서 8개 지역의 실제 tdump 파일 다운로드.

기존 hysplit_web_automation.py를 기반으로 8개 지역에 대해 실행합니다.

실행:
    python tests/integration/download_real_hysplit_data.py
"""

import asyncio
import re
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# 테스트 지역
TEST_LOCATIONS = {
    "서울": {"lat": 37.5, "lon": 127.0, "height": 850},
    "부산": {"lat": 35.1, "lon": 129.0, "height": 850},
    "제주": {"lat": 33.5, "lon": 126.5, "height": 850},
    "도쿄": {"lat": 35.7, "lon": 139.7, "height": 850},
    "오사카": {"lat": 34.7, "lon": 135.5, "height": 850},
    "베이징": {"lat": 39.9, "lon": 116.4, "height": 850},
    "상하이": {"lat": 31.2, "lon": 121.5, "height": 850},
    "타이베이": {"lat": 25.0, "lon": 121.5, "height": 850},
}


async def download_one_location(browser, location_name, lat, lon, height, output_dir):
    """한 지역에 대해 HYSPLIT Web 실행 및 tdump 다운로드.
    
    hysplit_web_full_automation.py의 검증된 워크플로우 사용:
    trajsrc.pl → GFS 0.25 선택 → forecast cycle 선택 → traj1.pl → 파라미터 설정
    """
    
    print(f"\n{'='*80}")
    print(f"  {location_name} 처리 중...")
    print(f"{'='*80}")
    print(f"  위치: {lat}°N, {lon}°E, {height}m AGL")
    
    context = await browser.new_context()
    page = await context.new_page()
    
    try:
        # Step 1: trajsrc.pl 페이지 접속 (Meteorology & Starting Location)
        print("\n1. trajsrc.pl 페이지 접속 중...")
        url = "https://www.ready.noaa.gov/hypub-bin/trajsrc.pl"
        await page.goto(url, timeout=60000)
        await page.wait_for_load_state("networkidle")
        print("   ✓ trajsrc.pl 페이지 로드 완료")

        # Step 2: Meteorology 선택 및 좌표 입력
        print(f"\n2. 기상 데이터 및 좌표 설정 중...")
        
        # GFS 0.25 Degree 선택
        try:
            await page.select_option('select[name="metdata"]', value='GFS0p25')
            print("   ✓ GFS 0.25 Degree 선택")
        except Exception as e:
            print(f"   ⚠ GFS 0.25 선택 실패: {e}")

        # 위도 입력
        try:
            await page.fill('input[name="Lat"]', str(abs(lat)))
            lat_direction = 'N' if lat >= 0 else 'S'
            await page.select_option('select[name="Latns"]', label=lat_direction)
            print(f"   ✓ 위도: {abs(lat)}°{lat_direction}")
        except Exception as e:
            print(f"   ⚠ 위도 입력 실패: {e}")

        # 경도 입력
        try:
            await page.fill('input[name="Lon"]', str(abs(lon)))
            lon_direction = 'E' if lon >= 0 else 'W'
            await page.select_option('select[name="Lonew"]', label=lon_direction)
            print(f"   ✓ 경도: {abs(lon)}°{lon_direction}")
        except Exception as e:
            print(f"   ⚠ 경도 입력 실패: {e}")

        # Step 3: Next 버튼 클릭
        print("\n3. Next 버튼 클릭 중...")
        try:
            await page.click('input[type="button"][value="Next>>"]')
            await page.wait_for_load_state("networkidle", timeout=30000)
            print("   ✓ 다음 페이지로 이동")
        except Exception as e:
            print(f"   ⚠ Next 버튼 클릭 실패: {e}")

        # Step 4: Meteorological Forecast Cycle 선택
        print("\n4. Forecast Cycle 선택 중...")
        try:
            # 가장 최신 forecast cycle 선택 (첫 번째 옵션)
            await page.select_option('select[name="metcyc"]', index=0)
            print("   ✓ 최신 Forecast Cycle 선택")
        except Exception as e:
            print(f"   ⚠ Forecast Cycle 선택 실패: {e}")

        # Next 버튼 클릭
        try:
            await page.click('input[type="submit"][value="Next>>"]')
            await page.wait_for_load_state("networkidle", timeout=30000)
            print("   ✓ traj1.pl 페이지로 이동")
        except Exception as e:
            print(f"   ⚠ Next 버튼 클릭 실패: {e}")

        # Step 5: traj1.pl 페이지에서 궤적 설정
        print("\n5. 궤적 파라미터 설정 중...")
        
        # 시작 시간은 forecast cycle 기본값 사용 (2026-02-14 00:00 UTC 근처)
        print("   ✓ 시간: 자동 선택 (forecast cycle 기준)")
        
        # Direction 선택 (Backward)
        try:
            await page.check('input[type="RADIO"][name="direction"][value="Backward"]')
            print("   ✓ 방향: Backward")
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

        # 실행 시간 입력 (24시간)
        try:
            runtime_input = page.locator('input[name="duration"]').first
            await runtime_input.fill("24")
            print("   ✓ 실행 시간: 24h")
        except Exception as e:
            print(f"   ⚠ 실행 시간 입력 실패: {e}")

        # 수직 운동 모드 선택 (Model Vertical Velocity = 0)
        try:
            await page.check('input[type="RADIO"][name="vertical"][value="0"]')
            print("   ✓ 수직 운동: Model Vertical Velocity")
        except Exception as e:
            print(f"   ⚠ 수직 운동 모드 선택 실패: {e}")

        # Step 6: Run trajectory 버튼 클릭
        print("\n6. Run trajectory 버튼 클릭 중...")
        print("   (모델 실행은 1~3분 소요될 수 있습니다)")
        
        try:
            await page.click('input[type="submit"][value="Request trajectory"]')
            print("   ✓ 궤적 계산 시작")
        except Exception as e:
            print(f"   ⚠ Run 버튼 클릭 실패: {e}")

        # Step 7: 결과 대기
        print("\n7. 결과 대기 중...")
        
        # 결과 페이지 로딩 대기 (최대 3분)
        try:
            await page.wait_for_load_state("networkidle", timeout=180000)
            print("   ✓ 결과 페이지 로드 완료")
        except PlaywrightTimeout:
            print("   ⚠ 결과 로딩 타임아웃 (3분 초과)")

        # 그래픽 파일이 준비될 때까지 대기
        print("   그래픽 파일 생성 대기 중...")
        graphics_ready = False
        for attempt in range(24):  # 24 * 5초 = 2분
            try:
                await asyncio.sleep(5)
                no_graphics = await page.locator('h2:has-text("There are no graphics files available yet")').count()
                
                if no_graphics == 0:
                    graphics_ready = True
                    print(f"   ✓ 그래픽 파일 준비 완료 ({(attempt+1)*5}초 경과)")
                    break
                else:
                    if (attempt + 1) % 2 == 0:  # 10초마다 출력
                        print(f"   - 대기 중... ({(attempt+1)*5}초 경과)")
            except Exception:
                pass
        
        if not graphics_ready:
            print("   ⚠ 그래픽 파일 생성 타임아웃 (2분 초과)")

        # 추가 대기 (결과 렌더링)
        await asyncio.sleep(5)
        
        # Step 8: tdump 파일 다운로드 (hysplit_web_full_automation.py의 검증된 방식)
        print("\n8. tdump 파일 다운로드 중...")
        try:
            # Trajectory endpoints 파일 다운로드 (tdump)
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
                        
                        print(f"   tdump URL: {src}")
                        
                        # 텍스트 파일 다운로드
                        tdump_page = await context.new_page()
                        await tdump_page.goto(src, timeout=30000)
                        
                        # <pre> 태그 내용 추출
                        pre_content = await tdump_page.locator('pre').first.inner_text()
                        
                        tdump_path = output_dir / f"tdump_{location_name}.txt"
                        with open(tdump_path, 'w', encoding='utf-8') as f:
                            f.write(pre_content)
                        
                        await tdump_page.close()
                        print(f"   ✓ tdump 파일 저장: {tdump_path}")
                        return True
                    else:
                        print("   ❌ tdump URL 파싱 실패")
                        return False
                else:
                    print("   ❌ tdump 링크 형식 오류")
                    return False
            else:
                print("   ❌ tdump 다운로드 링크를 찾을 수 없음")
                return False
        except Exception as e:
            print(f"   ❌ tdump 다운로드 실패: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except PlaywrightTimeout as e:
        print(f"\n❌ 타임아웃 오류: {e}")
        return False
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await context.close()


async def main():
    """메인 함수."""
    
    print("\n" + "="*80)
    print("  HYSPLIT Web 8개 지역 실제 데이터 다운로드")
    print("="*80 + "\n")
    
    print("설정:")
    print("  - Meteorology: GFS 0.25 degree")
    print("  - Start Time: 2026-02-14 00:00 UTC")
    print("  - Direction: Backward")
    print("  - Duration: 24 hours")
    print("  - Vertical Motion: Model Vertical Velocity")
    
    # 출력 디렉토리
    output_dir = Path("tests/integration/hysplit_web_data")
    output_dir.mkdir(exist_ok=True)
    
    # 브라우저 실행
    print(f"\n브라우저 실행 중...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        
        results = {}
        
        try:
            # 각 지역에 대해 실행
            for i, (location_name, info) in enumerate(TEST_LOCATIONS.items(), 1):
                print(f"\n\n{'#'*80}")
                print(f"  진행: {i}/8 - {location_name}")
                print(f"{'#'*80}")
                
                success = await download_one_location(
                    browser,
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
            
            if success_count == len(TEST_LOCATIONS):
                print(f"\n🎉 모든 지역 다운로드 성공!")
                print(f"\n다음 단계:")
                print(f"  python tests\\integration\\multi_location_24h_comparison.py --compare")
            elif success_count > 0:
                print(f"\n⚠️  일부 지역만 성공했습니다.")
                print(f"실패한 지역은 수동으로 다운로드해야 합니다.")
            else:
                print(f"\n❌ 모든 지역 다운로드 실패")
                print(f"수동 다운로드를 시도하세요:")
                print(f"  python tests\\integration\\hysplit_web_helper.py")
            
        finally:
            print(f"\n브라우저를 닫습니다...")
            await browser.close()


if __name__ == "__main__":
    print("\n⚠️  주의사항:")
    print("  - 각 지역당 2-3분 소요 예상 (총 20-30분)")
    print("  - 브라우저 창이 열리며 진행 상황을 확인할 수 있습니다")
    print("  - HYSPLIT Web 서버 상태에 따라 시간이 더 걸릴 수 있습니다\n")
    
    asyncio.run(main())
