"""HYSPLIT Web traj1.pl 페이지 구조 분석 (forecast cycle 선택 후)."""

import asyncio
from playwright.async_api import async_playwright


async def inspect_traj1():
    """trajsrc.pl → forecast cycle → traj1.pl 페이지의 HTML 구조를 분석합니다."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # Step 1: trajsrc.pl 접속
        print("Step 1: trajsrc.pl 접속 중...")
        await page.goto("https://www.ready.noaa.gov/hypub-bin/trajsrc.pl", timeout=60000)
        await page.wait_for_load_state("networkidle")
        print("✓ trajsrc.pl 로드 완료\n")
        
        # Step 2: GFS 0.25 선택 및 좌표 입력
        print("Step 2: GFS 0.25 선택 및 좌표 입력...")
        await page.select_option('select[name="metdata"]', value='GFS0p25')
        await page.fill('input[name="Lat"]', '37.5')
        await page.select_option('select[name="Latns"]', label='N')
        await page.fill('input[name="Lon"]', '127.0')
        await page.select_option('select[name="Lonew"]', label='E')
        print("✓ 좌표 입력 완료\n")
        
        # Step 3: Next 버튼 클릭
        print("Step 3: Next 버튼 클릭...")
        await page.click('input[type="button"][value="Next>>"]')
        await page.wait_for_load_state("networkidle", timeout=30000)
        print("✓ Forecast cycle 페이지로 이동\n")
        
        # Step 4: Forecast cycle 선택
        print("Step 4: Forecast cycle 선택...")
        await page.select_option('select[name="metcyc"]', index=0)
        print("✓ Forecast cycle 선택 완료\n")
        
        # Step 5: Next 버튼 클릭 (submit 타입)
        print("Step 5: Next 버튼 클릭...")
        await page.click('input[type="submit"][value="Next>>"]')
        await page.wait_for_load_state("networkidle", timeout=30000)
        print("✓ traj1.pl 페이지로 이동\n")
        
        # 추가 대기
        await asyncio.sleep(2)
        
        # 페이지 분석
        print("="*80)
        print("traj1.pl 페이지 분석 중...")
        print("="*80 + "\n")
        
        # 모든 input 요소 찾기
        inputs = await page.query_selector_all("input")
        print(f"총 {len(inputs)} 개의 input 요소 발견:\n")
        
        for i, inp in enumerate(inputs):
            name = await inp.get_attribute("name")
            input_type = await inp.get_attribute("type")
            value = await inp.get_attribute("value")
            input_id = await inp.get_attribute("id")
            
            print(f"[{i}] type={input_type}, name={name}, id={input_id}, value={value}")
        
        # 모든 select 요소 찾기
        selects = await page.query_selector_all("select")
        print(f"\n\n총 {len(selects)} 개의 select 요소 발견:\n")
        
        for i, sel in enumerate(selects):
            name = await sel.get_attribute("name")
            sel_id = await sel.get_attribute("id")
            print(f"[{i}] name={name}, id={sel_id}")
            
            # 옵션 확인
            options = await sel.query_selector_all("option")
            if len(options) <= 15:  # 옵션이 적으면 모두 출력
                for opt in options:
                    opt_value = await opt.get_attribute("value")
                    opt_text = await opt.inner_text()
                    print(f"     - value={opt_value}, text={opt_text}")
        
        # 페이지 HTML 저장
        content = await page.content()
        with open("tests/integration/hysplit_traj1_page.html", "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\n\n페이지 HTML 저장: tests/integration/hysplit_traj1_page.html")
        
        # 스크린샷 저장
        await page.screenshot(path="tests/integration/hysplit_traj1_screenshot.png", full_page=True)
        print(f"스크린샷 저장: tests/integration/hysplit_traj1_screenshot.png")
        
        print("\n\n브라우저 창을 확인하세요. 종료하려면 Enter를 누르세요...")
        input()
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(inspect_traj1())
