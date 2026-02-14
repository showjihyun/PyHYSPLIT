"""HYSPLIT Web 결과 분석 스크립트.

HYSPLIT Web에서 다운로드한 궤적 결과를 분석하고 시각화합니다.

실행:
    python tests/integration/analyze_hysplit_web_result.py
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image


def parse_hysplit_web_endpoints(filepath: str) -> dict:
    """HYSPLIT Web의 tdump 파일을 파싱합니다.
    
    Parameters
    ----------
    filepath : str
        tdump 파일 경로
        
    Returns
    -------
    dict
        파싱된 궤적 데이터
    """
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # 헤더 정보 파싱
    info = {}
    trajectory_points = []
    
    # 시작 시간 찾기 (라인 7: 26     2    13    13   37.500  127.000   850.0)
    start_line = lines[6].strip().split()
    info['start_year'] = 2000 + int(start_line[0])
    info['start_month'] = int(start_line[1])
    info['start_day'] = int(start_line[2])
    info['start_hour'] = int(start_line[3])
    info['start_lat'] = float(start_line[4])
    info['start_lon'] = float(start_line[5])
    info['start_height'] = float(start_line[6])
    
    # 궤적 포인트 파싱 (라인 9부터)
    for line in lines[8:]:
        parts = line.strip().split()
        if len(parts) >= 12:
            point = {
                'year': 2000 + int(parts[2]),
                'month': int(parts[3]),
                'day': int(parts[4]),
                'hour': int(parts[5]),
                'minute': int(parts[6]),
                'forecast_hour': int(parts[7]),
                'age': float(parts[8]),
                'lat': float(parts[9]),
                'lon': float(parts[10]),
                'height': float(parts[11]),
                'pressure': float(parts[12]) if len(parts) > 12 else None
            }
            trajectory_points.append(point)
    
    info['points'] = trajectory_points
    info['num_points'] = len(trajectory_points)
    
    return info


def analyze_hysplit_web_result(output_dir: str = "tests/integration"):
    """HYSPLIT Web 결과를 분석합니다."""
    script_dir = Path(__file__).parent
    
    print(f"\n{'='*80}")
    print(f"  HYSPLIT Web 결과 분석")
    print(f"{'='*80}\n")
    
    # 1. Endpoints 파일 파싱
    endpoints_file = script_dir / "hysplit_trajectory_endpoints.txt"
    
    if not endpoints_file.exists():
        print(f"❌ Endpoints 파일을 찾을 수 없습니다: {endpoints_file}")
        print("   먼저 hysplit_web_full_automation.py를 실행하세요.")
        return
    
    print("1. Trajectory Endpoints 파일 분석")
    print("-" * 80)
    
    data = parse_hysplit_web_endpoints(str(endpoints_file))
    
    print(f"  시작 시간: {data['start_year']}-{data['start_month']:02d}-{data['start_day']:02d} {data['start_hour']:02d}:00 UTC")
    print(f"  시작 위치: {data['start_lat']:.3f}°N, {data['start_lon']:.3f}°E")
    print(f"  시작 고도: {data['start_height']:.1f}m AGL")
    print(f"  포인트 수: {data['num_points']}")
    print()
    
    # 2. 궤적 경로 출력
    print("2. 궤적 경로 (시간별)")
    print("-" * 80)
    print(f"{'시간':^20} {'위도':>10} {'경도':>10} {'고도(m)':>10} {'기압(hPa)':>12}")
    print("-" * 80)
    
    for i, pt in enumerate(data['points']):
        time_str = f"{pt['year']}-{pt['month']:02d}-{pt['day']:02d} {pt['hour']:02d}:{pt['minute']:02d}"
        pressure_str = f"{pt['pressure']:.1f}" if pt['pressure'] else "N/A"
        print(f"{time_str:^20} {pt['lat']:>10.3f} {pt['lon']:>10.3f} {pt['height']:>10.1f} {pressure_str:>12}")
    
    print()
    
    # 3. 통계 정보
    print("3. 궤적 통계")
    print("-" * 80)
    
    lats = [pt['lat'] for pt in data['points']]
    lons = [pt['lon'] for pt in data['points']]
    heights = [pt['height'] for pt in data['points']]
    
    print(f"  위도 범위: {min(lats):.3f}°N ~ {max(lats):.3f}°N (변화: {max(lats) - min(lats):.3f}°)")
    print(f"  경도 범위: {min(lons):.3f}°E ~ {max(lons):.3f}°E (변화: {max(lons) - min(lons):.3f}°)")
    print(f"  고도 범위: {min(heights):.1f}m ~ {max(heights):.1f}m (변화: {max(heights) - min(heights):.1f}m)")
    
    # 총 이동 거리 계산 (Haversine)
    R = 6371  # 지구 반경 (km)
    total_distance = 0
    for i in range(len(data['points']) - 1):
        pt1 = data['points'][i]
        pt2 = data['points'][i + 1]
        
        dlat = np.radians(pt2['lat'] - pt1['lat'])
        dlon = np.radians(pt2['lon'] - pt1['lon'])
        a = np.sin(dlat/2)**2 + np.cos(np.radians(pt1['lat'])) * np.cos(np.radians(pt2['lat'])) * np.sin(dlon/2)**2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
        distance = R * c
        total_distance += distance
    
    print(f"  총 이동 거리: {total_distance:.2f} km")
    
    # 시작점-종료점 직선 거리
    start_pt = data['points'][0]
    end_pt = data['points'][-1]
    dlat = np.radians(end_pt['lat'] - start_pt['lat'])
    dlon = np.radians(end_pt['lon'] - start_pt['lon'])
    a = np.sin(dlat/2)**2 + np.cos(np.radians(start_pt['lat'])) * np.cos(np.radians(end_pt['lat'])) * np.sin(dlon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    straight_distance = R * c
    
    print(f"  직선 거리: {straight_distance:.2f} km")
    print(f"  경로 효율: {straight_distance / total_distance * 100:.1f}%")
    print()
    
    # 4. 시각화
    print("4. 시각화 생성 중...")
    print("-" * 80)
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    
    # (1) 궤적 경로 (위도-경도)
    ax = axes[0, 0]
    ax.plot(lons, lats, 'b-o', markersize=6, linewidth=2, label='Trajectory')
    ax.plot(lons[0], lats[0], 'g*', markersize=20, label='Start', zorder=5)
    ax.plot(lons[-1], lats[-1], 'r*', markersize=20, label='End', zorder=5)
    
    # 시간 레이블 추가
    for i, pt in enumerate(data['points']):
        if i % 2 == 0:  # 2시간마다
            ax.annotate(f"{pt['hour']:02d}h", (pt['lon'], pt['lat']), 
                       textcoords="offset points", xytext=(5,5), fontsize=8, alpha=0.7)
    
    ax.set_xlabel('Longitude (°E)', fontsize=12)
    ax.set_ylabel('Latitude (°N)', fontsize=12)
    ax.set_title('HYSPLIT Web Trajectory Path', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # (2) 고도 변화
    ax = axes[0, 1]
    ages = [pt['age'] for pt in data['points']]
    ax.plot(ages, heights, 'b-o', markersize=6, linewidth=2)
    ax.set_xlabel('Time (hours)', fontsize=12)
    ax.set_ylabel('Height (m AGL)', fontsize=12)
    ax.set_title('Height Profile', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.axhline(y=data['start_height'], color='r', linestyle='--', alpha=0.5, label='Start height')
    ax.legend(fontsize=10)
    
    # (3) 위도 변화
    ax = axes[1, 0]
    ax.plot(ages, lats, 'g-o', markersize=6, linewidth=2)
    ax.set_xlabel('Time (hours)', fontsize=12)
    ax.set_ylabel('Latitude (°N)', fontsize=12)
    ax.set_title('Latitude Change', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # (4) 경도 변화
    ax = axes[1, 1]
    ax.plot(ages, lons, 'm-o', markersize=6, linewidth=2)
    ax.set_xlabel('Time (hours)', fontsize=12)
    ax.set_ylabel('Longitude (°E)', fontsize=12)
    ax.set_title('Longitude Change', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    output_path = script_dir / "hysplit_web_analysis.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"  ✓ 분석 그래프 저장: {output_path}")
    
    plt.close()
    
    # 5. HYSPLIT Web 결과 이미지 표시
    print("\n5. HYSPLIT Web 결과 이미지")
    print("-" * 80)
    
    gif_file = script_dir / "hysplit_result_trajectory_1.gif"
    if gif_file.exists():
        print(f"  ✓ 궤적 이미지: {gif_file}")
        
        # GIF 이미지를 PNG로 변환하여 표시
        try:
            img = Image.open(gif_file)
            
            fig, ax = plt.subplots(1, 1, figsize=(12, 10))
            ax.imshow(img)
            ax.axis('off')
            ax.set_title('HYSPLIT Web Trajectory Result', fontsize=14, fontweight='bold')
            
            plt.tight_layout()
            
            output_path = script_dir / "hysplit_web_trajectory_display.png"
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            print(f"  ✓ 이미지 표시 저장: {output_path}")
            
            plt.close()
        except Exception as e:
            print(f"  ⚠ 이미지 표시 실패: {e}")
    else:
        print(f"  ⚠ 궤적 이미지를 찾을 수 없습니다: {gif_file}")
    
    print(f"\n{'='*80}")
    print(f"  분석 완료!")
    print(f"{'='*80}")
    print(f"  결과 파일:")
    print(f"    - 분석 그래프: {script_dir / 'hysplit_web_analysis.png'}")
    print(f"    - 궤적 이미지: {script_dir / 'hysplit_web_trajectory_display.png'}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    analyze_hysplit_web_result()
