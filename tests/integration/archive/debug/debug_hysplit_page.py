"""HYSPLIT Web 페이지 구조 디버그 스크립트."""

import asyncio
from playwright.async_api import async_playwright


async def debug_page():
    """페이지 구조를 분석하고 모든 input/select 요소를 출력합니다."""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            # 1. 메인 페이지 접속
            print("1. 메인 페이지 접속 중...")
            await page.goto("https://www.ready.noaa.gov/HYSPLIT_traj.php", timeout=60000)
            await page.wait_for_load_state("networkidle")
            print("   ✓ 메인 페이지 로드 완료\n")
            
            # 2. "Compute forecast trajectories" 클릭
            print("2. 'Compute forecast trajectories' 클릭 중...")
            await page.click('text=Compute forecast trajectories')
            await page.wait_for_load_state("networkidle", timeout=60000)
            print("   ✓ 입력 폼 페이지 로드 완료\n")
            
            # 3. 모든 input 요소 찾기
            print("="*80)
            print("모든 INPUT 요소:")
            print("="*80)
            
            inputs = await page.query_selector_all("input")
            print(f"총 {len(inputs)}개 발견\n")
            
            for i, inp in enumerate(inputs):
                name = await inp.get_attribute("name")
                input_type = await inp.get_attribute("type")
                value = await inp.get_attribute("value")
                input_id = await inp.get_attribute("id")
                placeholder = await inp.get_attribute("placeholder")
                
                print(f"[{i}] type={input_type}, name={name}, id={input_id}")
                if value:
                    print(f"    value={value}")
                if placeholder:
                    print(f"    placeholder={placeholder}")
            
            # 4. 모든 select 요소 찾기
            print("\n" + "="*80)
            print("모든 SELECT 요소:")
            print("="*80)
            
            selects = await page.query_selector_all("select")
            print(f"총 {len(selects)}개 발견\n")
            
            for i, sel in enumerate(selects):
                name = await sel.get_attribute("name")
                sel_id = await sel.get_attribute("id")
                
                print(f"[{i}] name={name}, id={sel_id}")
                
                # 옵션들도 출력
                options = await sel.query_selector_all("option")
                if len(options) <= 10:  # 10개 이하면 모두 출력
                    for opt in options:
                        opt_value = await opt.get_attribute("value")
                        opt_text = await opt.inner_text()
                        print(f"    - value={opt_value}, text={opt_text}")
            
            # 5. 모든 button/submit 요소 찾기
            print("\n" + "="*80)
            print("모든 BUTTON/SUBMIT 요소:")
            print("="*80)
            
            buttons = await page.query_selector_all("button, input[type='submit'], input[type='button']")
            print(f"총 {len(buttons)}개 발견\n")
            
            for i, btn in enumerate(buttons):
                btn_type = await btn.get_attribute("type")
                btn_value = await btn.get_attribute("value")
                btn_text = await btn.inner_text() if await btn.evaluate("el => el.tagName") == "BUTTON" else ""
                btn_name = await btn.get_attribute("name")
                
                print(f"[{i}] type={btn_type}, name={btn_name}")
                if btn_value:
                    print(f"    value={btn_value}")
                if btn_text:
                    print(f"    text={btn_text}")
            
            # 6. HTML 저장
            print("\n" + "="*80)
            print("HTML 저장 중...")
            print("="*80)
            
            content = await page.content()
            with open("tests/integration/hysplit_forecast_page.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("✓ 저장 완료: tests/integration/hysplit_forecast_page.html")
            
            # 7. 스크린샷 저장
            await page.screenshot(path="tests/integration/hysplit_forecast_page.png", full_page=True)
            print("✓ 스크린샷 저장: tests/integration/hysplit_forecast_page.png")
            
            print("\n브라우저 창을 확인하세요. 종료하려면 Enter를 누르세요...")
            input()
            
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_page())
