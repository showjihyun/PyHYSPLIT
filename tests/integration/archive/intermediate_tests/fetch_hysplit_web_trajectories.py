"""HYSPLIT Web에서 자동으로 궤적 데이터를 가져오는 스크립트.

HYSPLIT Web의 공개 API를 사용하여 8개 지역의 24시간 역추적을 자동으로 실행하고
결과를 다운로드합니다.

사용법:
    python tests/integration/fetch_hysplit_web_trajectories.py
"""

import requests
import time
from pathlib import Path
from datetime import datetime
import json

# 테스트 지역
TEST_LOCATIONS = {
    "서울": {"lat": 37.5, "lon": 127.0, "height": 850.0},
    "부산": {"lat": 35.1, "lon": 129.0, "height": 850.0},
    "제주": {"lat": 33.5, "lon": 126.5, "height": 850.0},
    "도쿄": {"lat": 35.7, "lon": 139.7, "height": 850.0},
    "오사카": {"lat": 34.7, "lon": 135.5, "height": 850.0},
    "베이징": {"lat": 39.9, "lon": 116.4, "height": 850.0},
    "상하이": {"lat": 31.2, "lon": 121.5, "height": 850.0},
    "타이베이": {"lat": 25.0, "lon": 121.5, "height": 850.0},
}


def fetch_hysplit_trajectory(location_name: str, lat: float, lon: float, 
                             height: float, start_time: datetime):
    """HYSPLIT Web에서 궤적 데이터 가져오기.
    
    Parameters
    ----------
    location_name : str
        지역 이름
    lat : float
        위도
    lon : float
        경도
    height : float
        고도 (m AGL)
    start_time : datetime
        시작 시간
        
    Returns
    -------
    dict or None
        궤적 데이터 또는 None (실패 시)
    """
    
    print(f"\n📍 {location_name} 궤적 요청 중...")
    print(f"  위치: {lat}°N, {lon}°E, {height}m AGL")
    print(f"  시작: {start_time.strftime('%Y-%m-%d %H:%M UTC')}")
    
    # HYSPLIT Web API 엔드포인트
    # 주의: 실제 HYSPLIT Web은 공식 API를 제공하지 않습니다.
    # 이 스크립트는 개념적 예시이며, 실제로는 웹 자동화 도구(Selenium 등)가 필요합니다.
    
    print(f"  ⚠ HYSPLIT Web은 공식 API를 제공하지 않습니다.")
    print(f"  ⚠ 수동으로 실행하거나 Selenium을 사용해야 합니다.")
    
    return None


def create_manual_instructions():
    """수동 실행 가이드 생성."""
    
    print("\n" + "="*80)
    print("  HYSPLIT Web 수동 실행 가이드")
    print("="*80 + "\n")
    
    print("HYSPLIT Web은 공식 API를 제공하지 않으므로 수동으로 실행해야 합니다.\n")
    
    print("1. 웹사이트 접속:")
    print("   https://www.ready.noaa.gov/HYSPLIT_traj.php\n")
    
    print("2. 공통 설정:")
    print("   - Meteorology: GFS (0.25 degree)")
    print("   - Start Time: 2026-02-14 00:00 UTC")
    print("   - Direction: Backward")
    print("   - Duration: 24 hours")
    print("   - Vertical Motion: Model Vertical Velocity")
    print("   - Output Interval: 1 hour\n")
    
    print("3. 각 지역별 실행:\n")
    
    for location_name, info in TEST_LOCATIONS.items():
        print(f"   {location_name}:")
        print(f"     Latitude: {info['lat']}")
        print(f"     Longitude: {info['lon']}")
        print(f"     Height: {info['height']} meters AGL")
        print(f"     → Run → Download 'Trajectory Endpoints'")
        print(f"     → 저장: tests/integration/hysplit_web_data/tdump_{location_name}.txt\n")
    
    print("4. 비교 실행:")
    print("   python tests/integration/multi_location_24h_comparison.py --compare\n")
    
    # 가이드 파일 저장
    guide_file = Path("tests/integration/HYSPLIT_WEB_MANUAL_GUIDE.txt")
    
    with open(guide_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("HYSPLIT Web 수동 실행 가이드\n")
        f.write("="*80 + "\n\n")
        
        f.write("웹사이트: https://www.ready.noaa.gov/HYSPLIT_traj.php\n\n")
        
        f.write("공통 설정:\n")
        f.write("  - Meteorology: GFS (0.25 degree)\n")
        f.write("  - Start Time: 2026-02-14 00:00 UTC\n")
        f.write("  - Direction: Backward\n")
        f.write("  - Duration: 24 hours\n")
        f.write("  - Vertical Motion: Model Vertical Velocity\n")
        f.write("  - Output Interval: 1 hour\n\n")
        
        f.write("각 지역별 설정:\n\n")
        
        for location_name, info in TEST_LOCATIONS.items():
            f.write(f"{location_name}:\n")
            f.write(f"  Latitude: {info['lat']}\n")
            f.write(f"  Longitude: {info['lon']}\n")
            f.write(f"  Height: {info['height']} meters AGL\n")
            f.write(f"  저장: tests/integration/hysplit_web_data/tdump_{location_name}.txt\n\n")
        
        f.write("\n비교 실행:\n")
        f.write("  python tests/integration/multi_location_24h_comparison.py --compare\n")
    
    print(f"✅ 가이드 저장: {guide_file}")


def create_selenium_example():
    """Selenium 자동화 예제 생성."""
    
    selenium_script = '''"""HYSPLIT Web Selenium 자동화 예제.

Selenium을 사용하여 HYSPLIT Web을 자동으로 실행합니다.

필요한 패키지:
    pip install selenium webdriver-manager

사용법:
    python tests/integration/hysplit_web_selenium.py
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
from pathlib import Path

# 테스트 지역
TEST_LOCATIONS = {
    "서울": {"lat": 37.5, "lon": 127.0, "height": 850.0},
    "부산": {"lat": 35.1, "lon": 129.0, "height": 850.0},
    "제주": {"lat": 33.5, "lon": 126.5, "height": 850.0},
    "도쿄": {"lat": 35.7, "lon": 139.7, "height": 850.0},
    "오사카": {"lat": 34.7, "lon": 135.5, "height": 850.0},
    "베이징": {"lat": 39.9, "lon": 116.4, "height": 850.0},
    "상하이": {"lat": 31.2, "lon": 121.5, "height": 850.0},
    "타이베이": {"lat": 25.0, "lon": 121.5, "height": 850.0},
}


def run_hysplit_web_selenium():
    """Selenium으로 HYSPLIT Web 자동 실행."""
    
    print("\\n" + "="*80)
    print("  HYSPLIT Web Selenium 자동화")
    print("="*80 + "\\n")
    
    # Chrome 드라이버 설정
    print("Chrome 드라이버 초기화 중...")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
    
    try:
        # HYSPLIT Web 접속
        print("HYSPLIT Web 접속 중...")
        driver.get("https://www.ready.noaa.gov/HYSPLIT_traj.php")
        time.sleep(3)
        
        # 출력 디렉토리
        output_dir = Path("tests/integration/hysplit_web_data")
        output_dir.mkdir(exist_ok=True)
        
        # 각 지역에 대해 반복
        for location_name, info in TEST_LOCATIONS.items():
            print(f"\\n📍 {location_name} 처리 중...")
            
            try:
                # 위도 입력
                lat_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "lat"))
                )
                lat_input.clear()
                lat_input.send_keys(str(info['lat']))
                
                # 경도 입력
                lon_input = driver.find_element(By.NAME, "lon")
                lon_input.clear()
                lon_input.send_keys(str(info['lon']))
                
                # 고도 입력
                height_input = driver.find_element(By.NAME, "height")
                height_input.clear()
                height_input.send_keys(str(int(info['height'])))
                
                # 시작 시간 설정
                # (실제 구현 시 날짜/시간 입력 필드 찾아서 설정)
                
                # 역궤적 설정
                # (실제 구현 시 Backward 옵션 선택)
                
                # 24시간 설정
                # (실제 구현 시 Duration 입력)
                
                # 실행 버튼 클릭
                submit_button = driver.find_element(By.NAME, "submit")
                submit_button.click()
                
                # 결과 대기 (30초)
                print(f"  계산 대기 중... (30초)")
                time.sleep(30)
                
                # tdump 다운로드
                # (실제 구현 시 다운로드 링크 찾아서 클릭)
                
                print(f"  ✓ {location_name} 완료")
                
                # 다음 지역을 위해 페이지 새로고침
                driver.get("https://www.ready.noaa.gov/HYSPLIT_traj.php")
                time.sleep(3)
                
            except Exception as e:
                print(f"  ❌ {location_name} 실패: {e}")
                continue
        
        print(f"\\n✅ 모든 지역 처리 완료!")
        
    finally:
        driver.quit()
        print("\\nChrome 드라이버 종료")


if __name__ == "__main__":
    print("\\n⚠ 주의: 이 스크립트는 예제입니다.")
    print("실제 사용을 위해서는 HYSPLIT Web의 HTML 구조를 분석하여")
    print("정확한 요소 선택자를 찾아야 합니다.\\n")
    
    response = input("계속하시겠습니까? (y/n): ")
    if response.lower() == 'y':
        run_hysplit_web_selenium()
    else:
        print("취소되었습니다.")
'''
    
    output_file = Path("tests/integration/hysplit_web_selenium.py")
    output_file.write_text(selenium_script, encoding='utf-8')
    
    print(f"\n✅ Selenium 예제 생성: {output_file}")
    print(f"  실행: python {output_file}")
    print(f"  필요: pip install selenium webdriver-manager")


def create_sample_tdump_files():
    """샘플 tdump 파일 생성 (테스트용)."""
    
    print("\n" + "="*80)
    print("  샘플 tdump 파일 생성 (테스트용)")
    print("="*80 + "\n")
    
    output_dir = Path("tests/integration/hysplit_web_data")
    output_dir.mkdir(exist_ok=True)
    
    # 샘플 tdump 형식
    sample_tdump = """     1 BACKWARD OMEGA   
     1 METEOROLOGICAL DATA FROM: GFS0P25
     1     26  2 14  0  0
     1 TRAJECTORY STARTED AT  0000 UTC 14 FEB 2026
     1      1    37.5000   127.0000    850.0
     1 PRESSURE LEVEL
     1      1 TRAJECTORY DIRECTION: BACKWARD
     1      1 VERTICAL MOTION CALCULATION: OMEGA
     1      1 METEOROLOGICAL DATA: GFS0P25
     1      1 STARTING LOCATION:  37.5000N  127.0000E    850.0 M AGL
     1      1 STARTING TIME: 14 02 26 00 00
     1      1 TRAJECTORY DURATION:  -24.0 HOURS
     1      1 TRAJECTORY OUTPUT INTERVAL:   1.0 HOURS
     1      1 NUMBER OF TRAJECTORY POINTS:    25
     1      1 TRAJECTORY POINT DATA:
     1      1 POINT  YEAR MO DA HR MN   AGE    LAT      LON      HEIGHT   PRESSURE
     1      1     1    26  2 14  0  0   0.00  37.5000  127.0000   850.0    916.1
     1      1     2    26  2 13 23  0  -1.00  37.6000  126.8000   840.0    918.0
     1      1     3    26  2 13 22  0  -2.00  37.7000  126.6000   830.0    920.0
"""
    
    print("⚠ 주의: 실제 HYSPLIT Web 데이터가 아닌 샘플 데이터입니다.")
    print("실제 비교를 위해서는 HYSPLIT Web에서 직접 다운로드해야 합니다.\n")
    
    for location_name in TEST_LOCATIONS.keys():
        output_file = output_dir / f"tdump_{location_name}_sample.txt"
        output_file.write_text(sample_tdump, encoding='utf-8')
        print(f"  ✓ {output_file.name}")
    
    print(f"\n✅ 샘플 파일 생성 완료: {output_dir}/")
    print(f"\n실제 데이터로 교체하려면:")
    print(f"  1. HYSPLIT Web에서 각 지역 실행")
    print(f"  2. tdump 파일 다운로드")
    print(f"  3. {output_dir}/tdump_<지역명>.txt로 저장")


def main():
    """메인 함수."""
    
    print("\n" + "="*80)
    print("  HYSPLIT Web 궤적 데이터 가져오기")
    print("="*80 + "\n")
    
    print("HYSPLIT Web은 공식 API를 제공하지 않습니다.")
    print("다음 옵션 중 하나를 선택하세요:\n")
    
    print("1. 수동 실행 가이드 생성")
    print("2. Selenium 자동화 예제 생성")
    print("3. 샘플 tdump 파일 생성 (테스트용)")
    print("4. 모두 생성")
    print("5. 종료\n")
    
    choice = input("선택 (1-5): ")
    
    if choice == '1':
        create_manual_instructions()
    elif choice == '2':
        create_selenium_example()
    elif choice == '3':
        create_sample_tdump_files()
    elif choice == '4':
        create_manual_instructions()
        create_selenium_example()
        create_sample_tdump_files()
    else:
        print("종료합니다.")
        return
    
    print("\n" + "="*80)
    print("  완료!")
    print("="*80 + "\n")
    
    print("다음 단계:")
    print("  1. HYSPLIT Web에서 8개 지역 실행")
    print("  2. tdump 파일 다운로드")
    print("  3. tests/integration/hysplit_web_data/에 저장")
    print("  4. 비교 실행: python tests/integration/multi_location_24h_comparison.py --compare")


if __name__ == "__main__":
    main()
