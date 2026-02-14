"""HYSPLIT Web 페이지 구조 분석 스크립트."""

import asyncio
from playwright.async_api import async_playwright


async def inspect_page():
    """HYSPLIT Web 페이지의 HTML 구조를 분석합니다."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("HYSPLIT Web 접속 중...")
        await page.goto("https://www.ready.noaa.gov/HYSPLIT_traj.php", timeout=60000)
        await page.wait_for_load_state("networkidle")
        
        print("\n페이지 로드 완료. HTML 구조 분석 중...\n")
        
        # 모든 input 요소 찾기
        inputs = await page.query_selector_all("input")
        print(f"총 {len(inputs)} 개의 input 요소 발견:\n")
        
        for i, inp in enumerate(inputs[:20]):  # 처음 20개만
            name = await inp.get_attribute("name")
            input_type = await inp.get_attribute("type")
            value = await inp.get_attribute("value")
            placeholder = await inp.get_attribute("placeholder")
            input_id = await inp.get_attribute("id")
            
            print(f"[{i}] type={input_type}, name={name}, id={input_id}, "
                  f"value={value}, placeholder={placeholder}")
        
        # 모든 select 요소 찾기
        selects = await page.query_selector_all("select")
        print(f"\n\n총 {len(selects)} 개의 select 요소 발견:\n")
        
        for i, sel in enumerate(selects[:10]):
            name = await sel.get_attribute("name")
            sel_id = await sel.get_attribute("id")
            print(f"[{i}] name={name}, id={sel_id}")
        
        # 페이지 HTML 일부 저장
        content = await page.content()
        with open("tests/integration/hysplit_web_page.html", "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\n\n페이지 HTML 저장: tests/integration/hysplit_web_page.html")
        
        print("\n\n브라우저 창을 확인하세요. 종료하려면 Enter를 누르세요...")
        input()
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(inspect_page())
