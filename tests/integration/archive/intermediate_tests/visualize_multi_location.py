"""다중 지역 24시간 역추적 결과 시각화.

사용법:
    python tests/integration/visualize_multi_location.py
"""

import json
from pathlib import Path
import sys

def create_ascii_map(results: dict):
    """ASCII 지도로 궤적 시각화."""
    
    # 지도 범위 설정 (극동아시아)
    lat_min, lat_max = 20, 45
    lon_min, lon_max = 110, 145
    
    # 지도 크기
    width = 80
    height = 30
    
    # 빈 지도 생성
    map_grid = [[' ' for _ in range(width)] for _ in range(height)]
    
    # 좌표를 그리드 인덱스로 변환
    def to_grid(lat, lon):
        x = int((lon - lon_min) / (lon_max - lon_min) * (width - 1))
        y = int((lat_max - lat) / (lat_max - lat_min) * (height - 1))
        return max(0, min(width-1, x)), max(0, min(height-1, y))
    
    # 지역 마커
    markers = {
        "서울": "S", "부산": "B", "제주": "J",
        "도쿄": "T", "오사카": "O", "베이징": "P",
        "상하이": "H", "타이베이": "W"
    }
    
    # 각 지역의 시작점 표시
    for location_name, result in results.items():
        if result is None:
            continue
        
        start = result['start']
        x, y = to_grid(start['lat'], start['lon'])
        
        marker = markers.get(location_name, '?')
        map_grid[y][x] = marker
    
    # 지도 출력
    print("\n" + "="*82)
    print("  극동아시아 24시간 역추적 시작점 지도")
    print("="*82)
    print(f"  범위: {lat_min}-{lat_max}°N, {lon_min}-{lon_max}°E")
    print("="*82 + "\n")
    
    # 상단 경도 눈금
    print("    ", end="")
    for i in range(0, width, 10):
        lon = lon_min + (lon_max - lon_min) * i / width
        print(f"{lon:>10.0f}°E", end="")
    print()
    
    # 지도 그리드
    for y, row in enumerate(map_grid):
        # 좌측 위도 눈금
        lat = lat_max - (lat_max - lat_min) * y / height
        if y % 5 == 0:
            print(f"{lat:>3.0f}°N ", end="")
        else:
            print("      ", end="")
        
        # 지도 내용
        print(''.join(row))
    
    # 범례
    print("\n범례:")
    for location_name, marker in markers.items():
        region = {
            "서울": "한국", "부산": "한국", "제주": "한국",
            "도쿄": "일본", "오사카": "일본",
            "베이징": "중국", "상하이": "중국", "타이베이": "대만"
        }[location_name]
        
        result = results.get(location_name)
        if result:
            print(f"  {marker} = {location_name} ({region}): "
                  f"{result['total_distance']:.0f}km {result['direction']}")


def create_summary_table(results: dict):
    """결과 요약 테이블 생성."""
    
    print("\n" + "="*120)
    print("  지역별 24시간 역추적 결과 요약")
    print("="*120)
    
    # 헤더
    print(f"{'지역':<10} {'국가':<6} {'시작 위치':<20} {'종료 위치':<20} "
          f"{'이동거리':>10} {'방향':>6} {'고도변화':>10} {'평균속도':>10}")
    print("-"*120)
    
    # 데이터
    for location_name, result in results.items():
        if result is None:
            continue
        
        region = {
            "서울": "한국", "부산": "한국", "제주": "한국",
            "도쿄": "일본", "오사카": "일본",
            "베이징": "중국", "상하이": "중국", "타이베이": "대만"
        }[location_name]
        
        start = result['start']
        end = result['end']
        
        start_pos = f"{start['lat']:.1f}°N,{start['lon']:.1f}°E"
        end_pos = f"{end['lat']:.1f}°N,{end['lon']:.1f}°E"
        
        print(f"{location_name:<10} {region:<6} {start_pos:<20} {end_pos:<20} "
              f"{result['total_distance']:>9.0f}km {result['direction']:>6} "
              f"{result['height_change']:>+9.0f}m {result['avg_speed']:>9.1f}km/h")
    
    print("="*120)


def create_comparison_table(results: dict):
    """HYSPLIT Web 비교 테이블 생성."""
    
    has_comparison = any(
        'hysplit_comparison' in result 
        for result in results.values() if result
    )
    
    if not has_comparison:
        print("\n⚠ HYSPLIT Web 비교 데이터가 없습니다.")
        print("  비교를 위해: python multi_location_24h_comparison.py --compare")
        return
    
    print("\n" + "="*100)
    print("  HYSPLIT Web 비교 결과")
    print("="*100)
    
    # 헤더
    print(f"{'지역':<10} {'국가':<6} {'수평 오차 (평균)':<20} {'수평 오차 (최대)':<20} "
          f"{'고도 오차 (평균)':<20} {'고도 오차 (최대)':<20}")
    print("-"*100)
    
    # 데이터
    for location_name, result in results.items():
        if result is None or 'hysplit_comparison' not in result:
            continue
        
        region = {
            "서울": "한국", "부산": "한국", "제주": "한국",
            "도쿄": "일본", "오사카": "일본",
            "베이징": "중국", "상하이": "중국", "타이베이": "대만"
        }[location_name]
        
        comp = result['hysplit_comparison']
        
        print(f"{location_name:<10} {region:<6} "
              f"{comp['mean_horizontal_error']:>18.2f}km "
              f"{comp['max_horizontal_error']:>18.2f}km "
              f"{comp['mean_vertical_error']:>18.1f}m "
              f"{comp['max_vertical_error']:>18.1f}m")
    
    print("="*100)


def main():
    """메인 함수."""
    
    # 결과 파일 로드
    results_file = Path("tests/integration/multi_location_24h_results.json")
    
    if not results_file.exists():
        print(f"❌ 결과 파일이 없습니다: {results_file}")
        print(f"먼저 실행하세요: python tests/integration/multi_location_24h_comparison.py")
        return
    
    with open(results_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    # 시각화
    create_ascii_map(results)
    create_summary_table(results)
    create_comparison_table(results)
    
    print("\n✅ 시각화 완료!")


if __name__ == "__main__":
    main()
