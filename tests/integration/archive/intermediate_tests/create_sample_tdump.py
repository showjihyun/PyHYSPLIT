"""샘플 HYSPLIT Web tdump 파일 생성.

PyHYSPLIT 결과를 기반으로 약간의 오차를 추가한 샘플 tdump 파일을 생성합니다.
실제 비교 기능을 테스트하기 위한 용도입니다.

사용법:
    python tests/integration/create_sample_tdump.py
"""

from pathlib import Path
import json
import numpy as np
from datetime import datetime, timedelta

# PyHYSPLIT 결과 로드
results_file = Path("tests/integration/multi_location_24h_results.json")

if not results_file.exists():
    print(f"❌ PyHYSPLIT 결과 파일이 없습니다: {results_file}")
    print(f"먼저 실행하세요: python tests/integration/multi_location_24h_comparison.py")
    exit(1)

with open(results_file, 'r', encoding='utf-8') as f:
    results = json.load(f)

# 출력 디렉토리
output_dir = Path("tests/integration/hysplit_web_data")
output_dir.mkdir(exist_ok=True)

print("\n" + "="*80)
print("  샘플 HYSPLIT Web tdump 파일 생성")
print("="*80 + "\n")

print("⚠️  주의: 이것은 테스트용 샘플 데이터입니다.")
print("실제 HYSPLIT Web 결과가 아니므로 정확한 비교가 불가능합니다.\n")

# 각 지역에 대해 샘플 tdump 생성
for location_name, result in results.items():
    print(f"생성 중: {location_name}...", end=" ")
    
    # 시작 위치
    start_lat = result['start']['lat']
    start_lon = result['start']['lon']
    start_height = result['start']['height']
    start_time = datetime.fromisoformat(result['start']['time'])
    
    # 종료 위치
    end_lat = result['end']['lat']
    end_lon = result['end']['lon']
    end_height = result['end']['height']
    
    # 24개 포인트 생성 (0-24시간, 1시간 간격)
    num_points = 25
    
    # 선형 보간으로 중간 포인트 생성
    lats = np.linspace(start_lat, end_lat, num_points)
    lons = np.linspace(start_lon, end_lon, num_points)
    heights = np.linspace(start_height, end_height, num_points)
    
    # 약간의 랜덤 오차 추가 (95% 일치를 시뮬레이션)
    np.random.seed(hash(location_name) % 2**32)  # 재현 가능한 랜덤
    
    # 수평 오차: 평균 40km, 표준편차 20km
    lat_errors = np.random.normal(0, 0.2, num_points)  # ~20km
    lon_errors = np.random.normal(0, 0.2, num_points)  # ~20km
    
    # 고도 오차: 평균 150m, 표준편차 80m
    height_errors = np.random.normal(0, 80, num_points)
    
    lats += lat_errors
    lons += lon_errors
    heights += height_errors
    
    # 압력 계산 (간단한 기압 고도 공식)
    pressures = 1013.25 * np.exp(-heights / 8430.0)
    
    # tdump 파일 생성
    output_file = output_dir / f"tdump_{location_name}.txt"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # 헤더
        f.write("     1 BACKWARD OMEGA   \n")
        f.write("     1 METEOROLOGICAL DATA FROM: GFS0P25\n")
        f.write(f"     1     {start_time.year % 100:2d}  {start_time.month:2d} {start_time.day:2d}  {start_time.hour:2d}  {start_time.minute:2d}\n")
        f.write(f"     1 TRAJECTORY STARTED AT  {start_time.strftime('%H%M UTC %d %b %Y').upper()}\n")
        f.write(f"     1      1    {start_lat:8.4f}   {start_lon:8.4f}    {start_height:6.1f}\n")
        f.write("     1 PRESSURE LEVEL\n")
        f.write("     1      1 TRAJECTORY DIRECTION: BACKWARD\n")
        f.write("     1      1 VERTICAL MOTION CALCULATION: OMEGA\n")
        f.write("     1      1 METEOROLOGICAL DATA: GFS0P25\n")
        f.write(f"     1      1 STARTING LOCATION:  {start_lat:7.4f}N  {start_lon:8.4f}E    {start_height:6.1f} M AGL\n")
        f.write(f"     1      1 STARTING TIME: {start_time.strftime('%d %m %y %H %M')}\n")
        f.write("     1      1 TRAJECTORY DURATION:  -24.0 HOURS\n")
        f.write("     1      1 TRAJECTORY OUTPUT INTERVAL:   1.0 HOURS\n")
        f.write(f"     1      1 NUMBER OF TRAJECTORY POINTS:    {num_points}\n")
        f.write("     1      1 TRAJECTORY POINT DATA:\n")
        f.write("     1      1 POINT  YEAR MO DA HR MN   AGE    LAT      LON      HEIGHT   PRESSURE\n")
        
        # 데이터 포인트
        for i in range(num_points):
            current_time = start_time - timedelta(hours=i)
            age = -float(i)
            
            f.write(f"     1      1 {i+1:5d}    {current_time.year % 100:2d}  "
                   f"{current_time.month:2d} {current_time.day:2d} "
                   f"{current_time.hour:2d}  {current_time.minute:2d}  "
                   f"{age:6.2f}  {lats[i]:8.4f}  {lons[i]:8.4f}  "
                   f"{heights[i]:8.1f}    {pressures[i]:6.1f}\n")
    
    print(f"✓ ({num_points} 포인트)")

print(f"\n✅ 샘플 파일 생성 완료: {output_dir}/")
print(f"\n다음 단계:")
print(f"  python tests\\integration\\multi_location_24h_comparison.py --compare")
print(f"\n⚠️  실제 HYSPLIT Web 데이터로 교체하려면:")
print(f"  1. https://www.ready.noaa.gov/HYSPLIT_traj.php 접속")
print(f"  2. 각 지역 실행 및 tdump 다운로드")
print(f"  3. {output_dir}/tdump_<지역명>.txt로 저장")
