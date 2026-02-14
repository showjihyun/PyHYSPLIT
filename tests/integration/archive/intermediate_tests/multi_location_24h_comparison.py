"""극동아시아 주요 지역 24시간 역추적 비교.

PyHYSPLIT과 HYSPLIT Web을 여러 지역에서 비교합니다.

사용법:
    # PyHYSPLIT만 실행 (HYSPLIT Web 데이터 없이)
    python tests/integration/multi_location_24h_comparison.py
    
    # HYSPLIT Web 데이터와 비교
    python tests/integration/multi_location_24h_comparison.py --compare
"""

from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
import netCDF4
import sys
import json
from math import radians, sin, cos, sqrt, atan2

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pyhysplit.models import StartLocation, SimulationConfig, MetData
from pyhysplit.engine import TrajectoryEngine
from pyhysplit.coordinate_converter import CoordinateConverter
from pyhysplit.interpolator import Interpolator


# 테스트 지역 정의
TEST_LOCATIONS = {
    "서울": {"lat": 37.5, "lon": 127.0, "height": 850.0, "region": "한국"},
    "부산": {"lat": 35.1, "lon": 129.0, "height": 850.0, "region": "한국"},
    "제주": {"lat": 33.5, "lon": 126.5, "height": 850.0, "region": "한국"},
    "도쿄": {"lat": 35.7, "lon": 139.7, "height": 850.0, "region": "일본"},
    "오사카": {"lat": 34.7, "lon": 135.5, "height": 850.0, "region": "일본"},
    "베이징": {"lat": 39.9, "lon": 116.4, "height": 850.0, "region": "중국"},
    "상하이": {"lat": 31.2, "lon": 121.5, "height": 850.0, "region": "중국"},
    "타이베이": {"lat": 25.0, "lon": 121.5, "height": 850.0, "region": "대만"},
}


def haversine(lat1, lon1, lat2, lon2):
    """두 지점 간 거리 계산 (km)."""
    R = 6371.0
    lat1_rad, lat2_rad = radians(lat1), radians(lat2)
    dlon = radians(lon2 - lon1)
    dlat = lat2_rad - lat1_rad
    
    a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c


def load_gfs_data(gfs_file: Path):
    """GFS 데이터 로드 및 omega → w 변환."""
    ds = netCDF4.Dataset(str(gfs_file))
    
    u_data = np.array(ds.variables['u'][:])
    v_data = np.array(ds.variables['v'][:])
    omega_data = np.array(ds.variables['w'][:])  # omega (Pa/s)
    t_data = np.array(ds.variables['t'][:])
    
    lat_grid = np.array(ds.variables['latitude'][:])
    lon_grid = np.array(ds.variables['longitude'][:])
    lev_grid = np.array(ds.variables['level'][:])  # hPa
    time_grid = np.array(ds.variables['time'][:])
    
    ds.close()
    
    # 시간 그리드 정렬
    if time_grid[0] > time_grid[-1]:
        time_indices = np.argsort(time_grid)
        time_grid = time_grid[time_indices]
        u_data = u_data[time_indices]
        v_data = v_data[time_indices]
        omega_data = omega_data[time_indices]
        t_data = t_data[time_indices]
    
    # 압력 좌표계에서는 omega (Pa/s)를 hPa/s로 변환
    # HYSPLIT은 압력 좌표계에서 omega를 직접 사용 (단위: hPa/s)
    # GFS omega는 Pa/s 단위이므로 hPa/s로 변환
    w_data = omega_data / 100.0  # Pa/s → hPa/s
    
    met_data = MetData(
        u=u_data, v=v_data, w=w_data, t_field=t_data,
        lat_grid=lat_grid, lon_grid=lon_grid,
        z_grid=lev_grid, t_grid=time_grid,
        z_type="pressure", source="GFS_NC"
    )
    
    return met_data


def run_pyhysplit_trajectory(met_data: MetData, location_name: str, 
                             lat: float, lon: float, height_hpa: float,
                             duration_hours: int = -24):
    """PyHYSPLIT 궤적 계산."""
    
    start_time = datetime(2026, 2, 14, 0, 0)
    
    # CRITICAL: height_type="pressure"로 압력 레벨 직접 지정
    # HYSPLIT Web과 동일한 850 hPa 사용
    start_loc = StartLocation(
        lat=lat, 
        lon=lon, 
        height=height_hpa,
        height_type="pressure"
    )
    
    config = SimulationConfig(
        start_time=start_time,
        num_start_locations=1,
        start_locations=[start_loc],
        total_run_hours=duration_hours,
        vertical_motion=0,  # Data vertical velocity (이제 w가 m/s로 변환됨)
        model_top=10000.0,
        met_files=[],
        turbulence_on=False,
        dt_max=15.0,
        scale_height=8430.0,
        tratio=0.75
    )
    
    engine = TrajectoryEngine(config, met_data)
    trajectory = engine.run(output_interval_s=3600.0)[0]
    
    # 결과 변환 - 압력 좌표계에서는 압력(hPa)을 직접 사용
    results = []
    base_time = datetime(start_time.year, start_time.month, start_time.day, 0, 0)
    
    for pt in trajectory:
        t_seconds, lon_val, lat_val, pressure_hpa = pt
        dt = base_time + timedelta(seconds=t_seconds)
        
        # 압력 좌표계: height_val은 이미 hPa 단위
        # 표시용으로만 meters로 변환 (비교는 압력으로 수행)
        height_pa = pressure_hpa * 100.0
        
        try:
            interp = Interpolator(met_data)
            T = interp.interpolate_scalar(met_data.t_field, lon_val, lat_val, pressure_hpa, t_seconds)
            height_m = CoordinateConverter.pressure_to_height_hypsometric(
                np.array([height_pa]), np.array([T])
            )[0]
        except Exception:
            height_m = CoordinateConverter.pressure_to_height(np.array([height_pa]))[0]
        
        results.append({
            'time': dt,
            'lat': lat_val,
            'lon': lon_val,
            'height': height_m,  # meters (표시용)
            'pressure': pressure_hpa  # hPa (비교용)
        })
    
    return results


def analyze_trajectory(trajectory: list[dict], location_name: str):
    """궤적 분석."""
    if len(trajectory) < 2:
        return None
    
    start = trajectory[0]
    end = trajectory[-1]
    
    # 총 이동 거리
    total_distance = haversine(start['lat'], start['lon'], end['lat'], end['lon'])
    
    # 고도 변화
    height_change = end['height'] - start['height']
    
    # 평균 속도
    duration_hours = len(trajectory) - 1
    avg_speed = total_distance / duration_hours if duration_hours > 0 else 0
    
    # 주요 이동 방향
    dlat = end['lat'] - start['lat']
    dlon = end['lon'] - start['lon']
    
    if abs(dlon) > abs(dlat):
        direction = "동쪽" if dlon > 0 else "서쪽"
    else:
        direction = "북쪽" if dlat > 0 else "남쪽"
    
    return {
        'location': location_name,
        'start': start,
        'end': end,
        'total_distance': total_distance,
        'height_change': height_change,
        'avg_speed': avg_speed,
        'direction': direction,
        'num_points': len(trajectory),
        'trajectory': trajectory
    }


def compare_with_hysplit_web(pyhysplit_results: dict, hysplit_web_dir: Path):
    """HYSPLIT Web 결과와 비교."""
    
    comparisons = {}
    
    for location_name, py_result in pyhysplit_results.items():
        # HYSPLIT Web tdump 파일 찾기
        tdump_file = hysplit_web_dir / f"tdump_{location_name}.txt"
        
        if not tdump_file.exists():
            print(f"  ⚠ {location_name}: HYSPLIT Web 데이터 없음 ({tdump_file.name})")
            continue
        
        # tdump 파일 파싱
        hysplit_points = []
        try:
            with open(tdump_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 데이터 라인 찾기 (숫자로 시작하고 충분한 컬럼이 있는 라인)
            for line in lines:
                parts = line.split()
                # tdump 형식: 1 1 POINT YEAR MO DA HR MN AGE LAT LON HEIGHT PRESSURE
                # 인덱스:      0 1   2    3   4  5  6  7   8   9   10    11      12
                if len(parts) >= 13:
                    try:
                        # 첫 3개 컬럼이 숫자인지 확인 (데이터 라인)
                        int(parts[0])
                        int(parts[1])
                        int(parts[2])
                        
                        # 위도, 경도, 고도, 압력 추출
                        lat = float(parts[9])
                        lon = float(parts[10])
                        height = float(parts[11])
                        pressure = float(parts[12])
                        hysplit_points.append({
                            'lat': lat, 
                            'lon': lon, 
                            'height': height,
                            'pressure': pressure
                        })
                    except (ValueError, IndexError):
                        continue
        except Exception as e:
            print(f"  ❌ {location_name}: tdump 파일 읽기 실패 - {e}")
            continue
        
        if len(hysplit_points) < 2:
            print(f"  ⚠ {location_name}: HYSPLIT Web 데이터 부족")
            continue
        
        # 비교 - 압력 좌표계에서는 압력으로 직접 비교
        py_traj = py_result['trajectory']
        min_len = min(len(py_traj), len(hysplit_points))
        
        horizontal_errors = []
        vertical_errors = []  # 압력 차이 (hPa)
        
        for i in range(min_len):
            py_pt = py_traj[i]
            hy_pt = hysplit_points[i]
            
            h_dist = haversine(py_pt['lat'], py_pt['lon'], hy_pt['lat'], hy_pt['lon'])
            
            # 압력 좌표계: 압력 차이로 비교 (hPa)
            v_diff = abs(py_pt['pressure'] - hy_pt['pressure'])
            
            horizontal_errors.append(h_dist)
            vertical_errors.append(v_diff)
        
        comparisons[location_name] = {
            'horizontal_errors': horizontal_errors,
            'vertical_errors': vertical_errors,
            'mean_horizontal': np.mean(horizontal_errors),
            'mean_vertical': np.mean(vertical_errors),
            'max_horizontal': np.max(horizontal_errors),
            'max_vertical': np.max(vertical_errors),
            'num_points': min_len
        }
    
    return comparisons


def print_results(results: dict, comparisons: dict = None):
    """결과 출력."""
    
    print("\n" + "="*100)
    print("  극동아시아 주요 지역 24시간 역추적 결과")
    print("="*100 + "\n")
    
    # 지역별 결과
    for location_name, result in results.items():
        if result is None:
            print(f"❌ {location_name}: 계산 실패")
            continue
        
        region = TEST_LOCATIONS[location_name]['region']
        
        print(f"\n📍 {location_name} ({region})")
        print(f"  시작: {result['start']['lat']:.2f}°N, {result['start']['lon']:.2f}°E, {result['start']['height']:.0f}m")
        print(f"  종료: {result['end']['lat']:.2f}°N, {result['end']['lon']:.2f}°E, {result['end']['height']:.0f}m")
        print(f"  이동: {result['total_distance']:.1f} km ({result['direction']})")
        print(f"  고도 변화: {result['height_change']:+.0f} m")
        print(f"  평균 속도: {result['avg_speed']:.1f} km/h")
        print(f"  포인트 수: {result['num_points']}")
        
        # HYSPLIT Web 비교
        if comparisons and location_name in comparisons:
            comp = comparisons[location_name]
            print(f"\n  🔍 HYSPLIT Web 비교:")
            print(f"    수평 오차: 평균 {comp['mean_horizontal']:.2f} km, 최대 {comp['max_horizontal']:.2f} km")
            print(f"    압력 오차: 평균 {comp['mean_vertical']:.1f} hPa, 최대 {comp['max_vertical']:.1f} hPa")
    
    # 전체 통계
    print(f"\n" + "="*100)
    print(f"  전체 통계")
    print(f"="*100 + "\n")
    
    valid_results = [r for r in results.values() if r is not None]
    
    if valid_results:
        distances = [r['total_distance'] for r in valid_results]
        heights = [r['height_change'] for r in valid_results]
        speeds = [r['avg_speed'] for r in valid_results]
        
        print(f"이동 거리:")
        print(f"  평균: {np.mean(distances):.1f} km")
        print(f"  최소: {np.min(distances):.1f} km")
        print(f"  최대: {np.max(distances):.1f} km")
        
        print(f"\n고도 변화:")
        print(f"  평균: {np.mean(heights):+.0f} m")
        print(f"  최소: {np.min(heights):+.0f} m")
        print(f"  최대: {np.max(heights):+.0f} m")
        
        print(f"\n평균 속도:")
        print(f"  평균: {np.mean(speeds):.1f} km/h")
        print(f"  최소: {np.min(speeds):.1f} km/h")
        print(f"  최대: {np.max(speeds):.1f} km/h")
    
    # HYSPLIT Web 전체 통계
    if comparisons:
        print(f"\n" + "="*100)
        print(f"  HYSPLIT Web 비교 전체 통계")
        print(f"="*100 + "\n")
        
        all_h_errors = []
        all_v_errors = []
        
        for comp in comparisons.values():
            all_h_errors.extend(comp['horizontal_errors'])
            all_v_errors.extend(comp['vertical_errors'])
        
        if all_h_errors:
            print(f"수평 오차 (전체 {len(all_h_errors)} 포인트):")
            print(f"  평균: {np.mean(all_h_errors):.2f} km")
            print(f"  중앙값: {np.median(all_h_errors):.2f} km")
            print(f"  최대: {np.max(all_h_errors):.2f} km")
            print(f"  표준편차: {np.std(all_h_errors):.2f} km")
            
            print(f"\n압력 오차:")
            print(f"  평균: {np.mean(all_v_errors):.1f} hPa")
            print(f"  중앙값: {np.median(all_v_errors):.1f} hPa")
            print(f"  최대: {np.max(all_v_errors):.1f} hPa")
            print(f"  표준편차: {np.std(all_v_errors):.1f} hPa")
            
            # 일치율 (압력 좌표계: 20 hPa ≈ 200m)
            h_match = sum(1 for e in all_h_errors if e < 20.0)
            v_match = sum(1 for e in all_v_errors if e < 20.0)
            
            print(f"\n일치율 (수평 < 20km, 압력 < 20hPa):")
            print(f"  수평: {h_match}/{len(all_h_errors)} ({h_match/len(all_h_errors)*100:.1f}%)")
            print(f"  압력: {v_match}/{len(all_v_errors)} ({v_match/len(all_v_errors)*100:.1f}%)")


def save_results(results: dict, comparisons: dict, output_file: Path):
    """결과를 JSON 파일로 저장."""
    
    # 결과를 직렬화 가능한 형태로 변환
    serializable_results = {}
    for location_name, result in results.items():
        if result is None:
            continue
        
        serializable_results[location_name] = {
            'start': {
                'lat': result['start']['lat'],
                'lon': result['start']['lon'],
                'height': result['start']['height'],
                'time': result['start']['time'].isoformat()
            },
            'end': {
                'lat': result['end']['lat'],
                'lon': result['end']['lon'],
                'height': result['end']['height'],
                'time': result['end']['time'].isoformat()
            },
            'total_distance': result['total_distance'],
            'height_change': result['height_change'],
            'avg_speed': result['avg_speed'],
            'direction': result['direction'],
            'num_points': result['num_points']
        }
        
        # HYSPLIT Web 비교 추가
        if comparisons and location_name in comparisons:
            comp = comparisons[location_name]
            serializable_results[location_name]['hysplit_comparison'] = {
                'mean_horizontal_error': comp['mean_horizontal'],
                'mean_vertical_error': comp['mean_vertical'],
                'max_horizontal_error': comp['max_horizontal'],
                'max_vertical_error': comp['max_vertical']
            }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(serializable_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 결과 저장: {output_file}")


def main():
    """메인 함수."""
    
    print("\n" + "="*100)
    print("  극동아시아 주요 지역 24시간 역추적 비교")
    print("="*100 + "\n")
    
    # GFS 데이터 로드
    gfs_file = Path("tests/integration/gfs_cache/gfs_eastasia_24h_real.nc")
    
    if not gfs_file.exists():
        print(f"❌ GFS 데이터 파일이 없습니다: {gfs_file}")
        print(f"먼저 실행하세요: python tests/integration/download_gfs_real_eastasia.py")
        return
    
    print(f"[1/3] GFS 데이터 로드 중...")
    met_data = load_gfs_data(gfs_file)
    print(f"  ✓ 완료")
    
    # PyHYSPLIT 궤적 계산
    print(f"\n[2/3] PyHYSPLIT 궤적 계산 중...")
    results = {}
    
    for location_name, location_info in TEST_LOCATIONS.items():
        print(f"  계산 중: {location_name} ({location_info['region']})...", end=" ")
        
        try:
            trajectory = run_pyhysplit_trajectory(
                met_data, location_name,
                location_info['lat'], location_info['lon'], location_info['height']
            )
            
            result = analyze_trajectory(trajectory, location_name)
            results[location_name] = result
            
            if result:
                print(f"✓ ({result['num_points']} 포인트, {result['total_distance']:.0f} km)")
            else:
                print(f"❌ 분석 실패")
        
        except Exception as e:
            print(f"❌ 오류: {e}")
            results[location_name] = None
    
    # HYSPLIT Web 비교 (선택사항)
    comparisons = None
    if "--compare" in sys.argv:
        print(f"\n[3/3] HYSPLIT Web 비교 중...")
        hysplit_web_dir = Path("tests/integration/hysplit_web_data")
        
        if hysplit_web_dir.exists():
            comparisons = compare_with_hysplit_web(results, hysplit_web_dir)
            print(f"  ✓ {len(comparisons)} 지역 비교 완료")
        else:
            print(f"  ⚠ HYSPLIT Web 데이터 디렉토리 없음: {hysplit_web_dir}")
            print(f"  HYSPLIT Web 데이터를 {hysplit_web_dir}에 tdump_<지역명>.txt 형식으로 저장하세요.")
    else:
        print(f"\n[3/3] HYSPLIT Web 비교 건너뛰기 (--compare 옵션 사용 시 비교)")
    
    # 결과 출력
    print_results(results, comparisons)
    
    # 결과 저장
    output_file = Path("tests/integration/multi_location_24h_results.json")
    save_results(results, comparisons, output_file)
    
    print(f"\n" + "="*100)
    print(f"  완료!")
    print(f"="*100 + "\n")
    
    print(f"다음 단계:")
    print(f"  1. HYSPLIT Web에서 동일 조건으로 궤적 생성")
    print(f"  2. tdump 파일을 tests/integration/hysplit_web_data/tdump_<지역명>.txt로 저장")
    print(f"  3. 비교 실행: python {Path(__file__).name} --compare")


if __name__ == "__main__":
    main()
