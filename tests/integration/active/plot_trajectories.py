"""극동아시아 다중 지역 24시간 역추적 궤적 시각화.

matplotlib을 사용하여 8개 지역의 궤적을 지도 위에 그립니다.

사용법:
    python tests/integration/plot_trajectories.py
"""

import json
from pathlib import Path
import sys
import numpy as np

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.collections import LineCollection
except ImportError:
    print("❌ matplotlib이 설치되지 않았습니다.")
    print("설치: pip install matplotlib")
    sys.exit(1)

# 한글 폰트 설정 (Windows)
try:
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False
except:
    pass


def load_trajectory_data():
    """궤적 데이터 로드."""
    
    # PyHYSPLIT 결과
    results_file = Path("tests/integration/multi_location_24h_results.json")
    
    if not results_file.exists():
        print(f"❌ 결과 파일이 없습니다: {results_file}")
        print(f"먼저 실행하세요: python tests/integration/multi_location_24h_comparison.py")
        return None
    
    with open(results_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    return results


def plot_all_trajectories(results: dict, output_file: Path):
    """모든 궤적을 하나의 지도에 그리기."""
    
    fig, ax = plt.subplots(figsize=(16, 12))
    
    # 지도 범위 설정
    lat_min, lat_max = 20, 45
    lon_min, lon_max = 110, 145
    
    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    ax.set_aspect('equal')
    
    # 격자선
    ax.grid(True, linestyle='--', alpha=0.3)
    ax.set_xlabel('경도 (°E)', fontsize=12)
    ax.set_ylabel('위도 (°N)', fontsize=12)
    ax.set_title('극동아시아 8개 지역 24시간 역추적 궤적\n(2026-02-14 00:00 UTC, GFS 0.25도)', 
                 fontsize=14, fontweight='bold')
    
    # 색상 및 마커 설정
    colors = {
        '서울': '#FF4444', '부산': '#FF8844', '제주': '#FFCC44',
        '도쿄': '#44FF44', '오사카': '#44FFAA',
        '베이징': '#4444FF', '상하이': '#8844FF',
        '타이베이': '#FF44FF'
    }
    
    markers = {
        '서울': 'o', '부산': 's', '제주': '^',
        '도쿄': 'D', '오사카': 'v',
        '베이징': 'p', '상하이': 'h',
        '타이베이': '*'
    }
    
    # 각 지역의 궤적 그리기
    for location_name, result in results.items():
        if result is None:
            continue
        
        color = colors.get(location_name, '#888888')
        marker = markers.get(location_name, 'o')
        
        # 시작점과 종료점
        start = result['start']
        end = result['end']
        
        # 시작점 (큰 마커)
        ax.plot(start['lon'], start['lat'], marker=marker, 
                markersize=15, color=color, markeredgecolor='black', 
                markeredgewidth=2, label=location_name, zorder=10)
        
        # 종료점 (작은 마커)
        ax.plot(end['lon'], end['lat'], marker=marker, 
                markersize=8, color=color, markeredgecolor='black', 
                markeredgewidth=1, zorder=9)
        
        # 궤적선 (화살표)
        ax.annotate('', xy=(end['lon'], end['lat']), 
                   xytext=(start['lon'], start['lat']),
                   arrowprops=dict(arrowstyle='->', color=color, lw=2, alpha=0.7),
                   zorder=5)
        
        # 지역명 표시
        ax.text(start['lon'], start['lat'] + 0.5, location_name,
               fontsize=10, ha='center', va='bottom',
               bbox=dict(boxstyle='round,pad=0.3', facecolor='white', 
                        edgecolor=color, alpha=0.8))
    
    # 범례
    ax.legend(loc='upper left', fontsize=10, framealpha=0.9)
    
    # 주요 도시 표시 (참고용)
    cities = {
        '서울': (127.0, 37.5), '부산': (129.0, 35.1), '제주': (126.5, 33.5),
        '도쿄': (139.7, 35.7), '오사카': (135.5, 34.7),
        '베이징': (116.4, 39.9), '상하이': (121.5, 31.2),
        '타이베이': (121.5, 25.0)
    }
    
    # 저장
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✅ 저장: {output_file}")
    
    return fig


def plot_individual_trajectories(results: dict, output_dir: Path):
    """각 지역별로 개별 궤적 그리기."""
    
    output_dir.mkdir(exist_ok=True)
    
    for location_name, result in results.items():
        if result is None:
            continue
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        start = result['start']
        end = result['end']
        
        # 지도 범위 (궤적 주변)
        lats = [start['lat'], end['lat']]
        lons = [start['lon'], end['lon']]
        
        lat_margin = max(5, abs(end['lat'] - start['lat']) * 0.3)
        lon_margin = max(5, abs(end['lon'] - start['lon']) * 0.3)
        
        ax.set_xlim(min(lons) - lon_margin, max(lons) + lon_margin)
        ax.set_ylim(min(lats) - lat_margin, max(lats) + lat_margin)
        ax.set_aspect('equal')
        
        # 격자선
        ax.grid(True, linestyle='--', alpha=0.3)
        ax.set_xlabel('경도 (°E)', fontsize=12)
        ax.set_ylabel('위도 (°N)', fontsize=12)
        
        region = {
            '서울': '한국', '부산': '한국', '제주': '한국',
            '도쿄': '일본', '오사카': '일본',
            '베이징': '중국', '상하이': '중국', '타이베이': '대만'
        }[location_name]
        
        ax.set_title(f'{location_name} ({region}) 24시간 역추적\n'
                    f'이동: {result["total_distance"]:.0f} km {result["direction"]}, '
                    f'평균 속도: {result["avg_speed"]:.1f} km/h',
                    fontsize=12, fontweight='bold')
        
        # 시작점
        ax.plot(start['lon'], start['lat'], 'go', markersize=20, 
               markeredgecolor='black', markeredgewidth=2, 
               label=f'시작 ({start["lat"]:.1f}°N, {start["lon"]:.1f}°E)', zorder=10)
        
        # 종료점
        ax.plot(end['lon'], end['lat'], 'ro', markersize=15, 
               markeredgecolor='black', markeredgewidth=2,
               label=f'종료 ({end["lat"]:.1f}°N, {end["lon"]:.1f}°E)', zorder=10)
        
        # 궤적선
        ax.annotate('', xy=(end['lon'], end['lat']), 
                   xytext=(start['lon'], start['lat']),
                   arrowprops=dict(arrowstyle='->', color='blue', lw=3, alpha=0.7),
                   zorder=5)
        
        # 정보 텍스트
        info_text = (f'이동 거리: {result["total_distance"]:.1f} km\n'
                    f'고도 변화: {result["height_change"]:+.0f} m\n'
                    f'평균 속도: {result["avg_speed"]:.1f} km/h\n'
                    f'방향: {result["direction"]}')
        
        ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
               fontsize=10, va='top', ha='left',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='white', 
                        edgecolor='gray', alpha=0.9))
        
        ax.legend(loc='lower right', fontsize=10)
        
        # 저장
        output_file = output_dir / f"trajectory_{location_name}.png"
        plt.tight_layout()
        plt.savefig(output_file, dpi=200, bbox_inches='tight')
        plt.close()
        
        print(f"  ✅ {location_name}: {output_file.name}")


def plot_distance_comparison(results: dict, output_file: Path):
    """이동 거리 비교 막대 그래프."""
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # 데이터 준비
    locations = []
    distances = []
    colors_list = []
    
    colors = {
        '서울': '#FF4444', '부산': '#FF8844', '제주': '#FFCC44',
        '도쿄': '#44FF44', '오사카': '#44FFAA',
        '베이징': '#4444FF', '상하이': '#8844FF',
        '타이베이': '#FF44FF'
    }
    
    for location_name, result in results.items():
        if result is None:
            continue
        
        locations.append(location_name)
        distances.append(result['total_distance'])
        colors_list.append(colors.get(location_name, '#888888'))
    
    # 막대 그래프
    bars = ax.bar(locations, distances, color=colors_list, 
                  edgecolor='black', linewidth=1.5)
    
    # 값 표시
    for bar, dist in zip(bars, distances):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{dist:.0f} km',
               ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax.set_ylabel('이동 거리 (km)', fontsize=12)
    ax.set_title('지역별 24시간 역추적 이동 거리 비교', fontsize=14, fontweight='bold')
    ax.grid(axis='y', linestyle='--', alpha=0.3)
    
    # 평균선
    avg_distance = np.mean(distances)
    ax.axhline(y=avg_distance, color='red', linestyle='--', linewidth=2, 
              label=f'평균: {avg_distance:.0f} km')
    ax.legend(fontsize=10)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=200, bbox_inches='tight')
    print(f"✅ 저장: {output_file}")
    
    return fig


def plot_speed_comparison(results: dict, output_file: Path):
    """평균 속도 비교 막대 그래프."""
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # 데이터 준비
    locations = []
    speeds = []
    colors_list = []
    
    colors = {
        '서울': '#FF4444', '부산': '#FF8844', '제주': '#FFCC44',
        '도쿄': '#44FF44', '오사카': '#44FFAA',
        '베이징': '#4444FF', '상하이': '#8844FF',
        '타이베이': '#FF44FF'
    }
    
    for location_name, result in results.items():
        if result is None:
            continue
        
        locations.append(location_name)
        speeds.append(result['avg_speed'])
        colors_list.append(colors.get(location_name, '#888888'))
    
    # 막대 그래프
    bars = ax.bar(locations, speeds, color=colors_list, 
                  edgecolor='black', linewidth=1.5)
    
    # 값 표시
    for bar, speed in zip(bars, speeds):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'{speed:.1f}',
               ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax.set_ylabel('평균 속도 (km/h)', fontsize=12)
    ax.set_title('지역별 24시간 역추적 평균 속도 비교', fontsize=14, fontweight='bold')
    ax.grid(axis='y', linestyle='--', alpha=0.3)
    
    # 평균선
    avg_speed = np.mean(speeds)
    ax.axhline(y=avg_speed, color='red', linestyle='--', linewidth=2, 
              label=f'평균: {avg_speed:.1f} km/h')
    ax.legend(fontsize=10)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=200, bbox_inches='tight')
    print(f"✅ 저장: {output_file}")
    
    return fig


def main():
    """메인 함수."""
    
    print("\n" + "="*80)
    print("  극동아시아 다중 지역 24시간 역추적 궤적 시각화")
    print("="*80 + "\n")
    
    # 데이터 로드
    print("[1/5] 데이터 로드 중...")
    results = load_trajectory_data()
    
    if results is None:
        return
    
    print(f"  ✓ {len(results)} 지역 로드 완료")
    
    # 출력 디렉토리
    output_dir = Path("tests/integration/trajectory_plots")
    output_dir.mkdir(exist_ok=True)
    
    # 1. 전체 궤적 지도
    print("\n[2/5] 전체 궤적 지도 생성 중...")
    plot_all_trajectories(results, output_dir / "all_trajectories.png")
    
    # 2. 개별 궤적
    print("\n[3/5] 개별 궤적 생성 중...")
    plot_individual_trajectories(results, output_dir / "individual")
    
    # 3. 이동 거리 비교
    print("\n[4/5] 이동 거리 비교 그래프 생성 중...")
    plot_distance_comparison(results, output_dir / "distance_comparison.png")
    
    # 4. 평균 속도 비교
    print("\n[5/5] 평균 속도 비교 그래프 생성 중...")
    plot_speed_comparison(results, output_dir / "speed_comparison.png")
    
    print("\n" + "="*80)
    print("  완료!")
    print("="*80 + "\n")
    
    print(f"생성된 파일:")
    print(f"  📁 {output_dir}/")
    print(f"    📊 all_trajectories.png         - 전체 궤적 지도")
    print(f"    📊 distance_comparison.png      - 이동 거리 비교")
    print(f"    📊 speed_comparison.png         - 평균 속도 비교")
    print(f"    📁 individual/                  - 개별 궤적 (8개)")
    print(f"       📊 trajectory_서울.png")
    print(f"       📊 trajectory_부산.png")
    print(f"       📊 ... (총 8개)")
    
    print(f"\n이미지 확인:")
    print(f"  탐색기에서 열기: {output_dir.absolute()}")


if __name__ == "__main__":
    main()
