"""HYSPLIT Web에서 고위도 위치 궤적 다운로드.

목적: 고위도 위치에서 HYSPLIT이 실제로 어떻게 계산하는지 확인
위치: 서울, 베이징 (경계 오류 발생 위치)

사용법:
    python tests/integration/download_hysplit_high_latitude.py
"""

import requests
from datetime import datetime, timedelta
from pathlib import Path
import time


def download_hysplit_trajectory(lat, lon, height, start_time, duration_hours, location_name):
    """HYSPLIT Web에서 궤적 다운로드.
    
    Parameters:
        lat: 위도
        lon: 경도
        height: 고도 (m AGL)
        start_time: 시작 시간 (datetime)
        duration_hours: 지속 시간 (음수 = 역궤적)
        location_name: 위치 이름
    """
    
    print(f"\n{'='*80}")
    print(f"Downloading HYSPLIT trajectory for {location_name}")
    print(f"{'='*80}\n")
    
    print(f"Location: {lat}°N, {lon}°E")
    print(f"Height: {height} m AGL")
    print(f"Start time: {start_time}")
    print(f"Duration: {duration_hours} hours")
    print()
    
    # HYSPLIT Web API endpoint
    # Note: This is a simplified example. Actual HYSPLIT Web API may differ.
    # You may need to use the web interface manually or check their API documentation.
    
    print("⚠️ HYSPLIT Web API 접근 방법:")
    print()
    print("1. 웹 브라우저로 접속:")
    print("   https://www.ready.noaa.gov/HYSPLIT_traj.php")
    print()
    print("2. 다음 파라미터 입력:")
    print(f"   - Start Location: {lat}, {lon}")
    print(f"   - Height: {height} m AGL")
    print(f"   - Start Time: {start_time.strftime('%Y-%m-%d %H:00 UTC')}")
    print(f"   - Run Duration: {duration_hours} hours")
    print(f"   - Meteorology: GFS 0.25 degree")
    print(f"   - Vertical Motion: Model Vertical Velocity")
    print()
    print("3. 'Run Model' 클릭 후 결과 다운로드")
    print()
    print("4. tdump 파일을 다음 위치에 저장:")
    output_dir = Path("tests/integration/hysplit_web_data/high_latitude")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"tdump_{location_name.lower()}_850hpa.txt"
    print(f"   {output_file}")
    print()
    
    # Check if file already exists
    if output_file.exists():
        print(f"✓ File already exists: {output_file}")
        print(f"  Size: {output_file.stat().st_size} bytes")
        return True
    else:
        print(f"⚠️ File not found. Please download manually.")
        return False


def main():
    """메인 함수."""
    
    print("\n" + "="*80)
    print("HYSPLIT Web 고위도 궤적 다운로드 가이드")
    print("="*80 + "\n")
    
    print("목적: 고위도 위치에서 HYSPLIT이 실제로 어떻게 계산하는지 확인")
    print()
    
    # Test locations (high latitude with boundary errors)
    locations = [
        {"name": "서울", "lat": 37.5, "lon": 127.0},
        {"name": "베이징", "lat": 39.9, "lon": 116.4},
        {"name": "부산", "lat": 35.1, "lon": 129.0},
        {"name": "도쿄", "lat": 35.7, "lon": 139.7},
    ]
    
    # Start time (same as our tests)
    start_time = datetime(2026, 2, 14, 0, 0)
    
    # Check if start_time is in the future
    now = datetime.utcnow()
    if start_time > now:
        print(f"⚠️ 시작 시간이 미래입니다: {start_time}")
        print(f"   현재 시간: {now}")
        print(f"   HYSPLIT Web은 과거 데이터만 사용 가능합니다.")
        print()
        print("대안:")
        print("1. 과거 날짜 사용 (예: 2024-02-14)")
        print("2. 또는 현재 날짜에서 24시간 전")
        print()
        
        # Use yesterday
        start_time = now - timedelta(days=1)
        start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        print(f"✓ 수정된 시작 시간: {start_time}")
        print()
    
    # Download for each location
    for loc in locations:
        download_hysplit_trajectory(
            lat=loc['lat'],
            lon=loc['lon'],
            height=850,  # 850 hPa ≈ 1500 m AGL
            start_time=start_time,
            duration_hours=-24,
            location_name=loc['name']
        )
        time.sleep(1)
    
    print("\n" + "="*80)
    print("다음 단계")
    print("="*80 + "\n")
    
    print("1. HYSPLIT Web에서 수동으로 궤적 다운로드")
    print("2. tdump 파일을 지정된 위치에 저장")
    print("3. 비교 스크립트 실행:")
    print("   python tests/integration/compare_high_latitude_detailed.py")
    print()
    
    print("비교 항목:")
    print("  - 시간별 위치 (lat, lon, pressure)")
    print("  - 수직 운동 패턴")
    print("  - 경계 탈출 시점")
    print("  - 제트 기류 진입 시점")
    print()


if __name__ == "__main__":
    main()
