"""고위도 위치에서 PyHYSPLIT vs HYSPLIT 상세 비교.

목적: 단계별로 차이점을 추적하여 고위도 경계 오류의 원인 파악

비교 항목:
1. 초기 조건 (시작 위치, 고도, 시간)
2. 시간별 위치 변화
3. 수직 운동 패턴
4. 풍속장 보간 차이
5. 적분 방법 차이
6. 경계 처리 방식

사용법:
    python tests/integration/diagnose_high_latitude_differences.py
"""

import json
from datetime import datetime
from pathlib import Path
import numpy as np

from pyhysplit.models import StartLocation, SimulationConfig
from pyhysplit.engine import TrajectoryEngine
from pyhysplit.met_reader import NetCDFReader


def load_hysplit_tdump(filepath):
    """HYSPLIT tdump 파일 로드."""
    
    if not Path(filepath).exists():
        return None
    
    points = []
    with open(filepath, 'r') as f:
        lines = f.readlines()
        
        # Skip header lines
        data_start = 0
        for i, line in enumerate(lines):
            if line.strip() and not line.startswith('#'):
                # Check if this is a data line
                parts = line.split()
                if len(parts) >= 9:
                    data_start = i
                    break
        
        # Parse data lines
        for line in lines[data_start:]:
            parts = line.split()
            if len(parts) >= 9:
                try:
                    # HYSPLIT tdump format:
                    # 1:forecast_hour 2:grid 3:year 4:month 5:day 6:hour 7:minute
                    # 8:forecast_hour 9:age 10:lat 11:lon 12:height
                    age = float(parts[8])  # hours
                    lat = float(parts[9])
                    lon = float(parts[10])
                    height = float(parts[11])  # meters AGL
                    
                    points.append({
                        'hour': -age,  # negative for backward
                        'lat': lat,
                        'lon': lon,
                        'height': height
                    })
                except (ValueError, IndexError):
                    continue
    
    return points


def calculate_differences(pyhysplit_traj, hysplit_traj):
    """두 궤적 간의 차이 계산."""
    
    if not hysplit_traj:
        return None
    
    # Match by hour
    differences = []
    
    for py_point in pyhysplit_traj:
        hour = py_point['hour']
        
        # Find matching HYSPLIT point
        hy_point = None
        for h in hysplit_traj:
            if abs(h['hour'] - hour) < 0.1:  # within 6 minutes
                hy_point = h
                break
        
        if hy_point:
            # Calculate distance
            lat1, lon1 = py_point['lat'], py_point['lon']
            lat2, lon2 = hy_point['lat'], hy_point['lon']
            
            # Haversine distance
            lat1_rad, lon1_rad = np.radians(lat1), np.radians(lon1)
            lat2_rad, lon2_rad = np.radians(lat2), np.radians(lon2)
            
            dlat = lat2_rad - lat1_rad
            dlon = lon2_rad - lon1_rad
            a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
            c = 2 * np.arcsin(np.sqrt(a))
            distance = 6371.0 * c
            
            # Height difference
            height_diff = abs(py_point.get('height', 0) - hy_point.get('height', 0))
            
            differences.append({
                'hour': hour,
                'distance_km': distance,
                'height_diff_m': height_diff,
                'pyhysplit': py_point,
                'hysplit': hy_point
            })
    
    return differences


def analyze_vertical_motion(trajectory):
    """수직 운동 패턴 분석."""
    
    if len(trajectory) < 2:
        return None
    
    vertical_changes = []
    
    for i in range(1, len(trajectory)):
        prev = trajectory[i-1]
        curr = trajectory[i]
        
        if 'pressure' in prev and 'pressure' in curr:
            dp = curr['pressure'] - prev['pressure']
            dt = (curr['hour'] - prev['hour']) * 3600  # seconds
            
            if dt > 0:
                dp_dt = dp / dt  # hPa/s
                vertical_changes.append({
                    'hour': curr['hour'],
                    'dp_dt': dp_dt,
                    'pressure': curr['pressure']
                })
    
    return vertical_changes


def diagnose_location(location_name, lat, lon):
    """특정 위치에 대한 상세 진단."""
    
    print(f"\n{'='*80}")
    print(f"진단: {location_name} ({lat}°N, {lon}°E)")
    print(f"{'='*80}\n")
    
    # Load GFS data
    gfs_file = Path("tests/integration/gfs_cache/gfs_eastasia_24h_extended.nc")
    
    if not gfs_file.exists():
        print("❌ GFS data not found.")
        return
    
    met_reader = NetCDFReader()
    met_data = met_reader.read(str(gfs_file))
    
    # Run PyHYSPLIT
    print("1. PyHYSPLIT 궤적 계산...")
    
    config = SimulationConfig(
        start_time=datetime(2026, 2, 14, 0, 0),
        num_start_locations=1,
        start_locations=[
            StartLocation(
                lat=lat,
                lon=lon,
                height=850,
                height_type="pressure"
            )
        ],
        total_run_hours=-24,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[("tests/integration/gfs_cache", "gfs_eastasia_24h_extended.nc")],
        auto_vertical_mode=True,
    )
    
    engine = TrajectoryEngine(config, met_data)
    all_trajectories = engine.run()
    
    pyhysplit_traj = []
    if all_trajectories and len(all_trajectories) > 0:
        trajectory = all_trajectories[0]
        for t, lon_val, lat_val, z in trajectory:
            hour = -t / 3600.0
            pyhysplit_traj.append({
                'hour': hour,
                'lat': lat_val,
                'lon': lon_val,
                'pressure': z
            })
    
    print(f"   ✓ Completed: {len(pyhysplit_traj)} points")
    
    # Load HYSPLIT trajectory
    print("\n2. HYSPLIT 궤적 로드...")
    
    hysplit_file = Path(f"tests/integration/hysplit_web_data/high_latitude/tdump_{location_name.lower()}_850hpa.txt")
    hysplit_traj = load_hysplit_tdump(hysplit_file)
    
    if not hysplit_traj:
        print(f"   ⚠️ HYSPLIT 데이터 없음: {hysplit_file}")
        print(f"   다운로드 가이드:")
        print(f"   python tests/integration/download_hysplit_high_latitude.py")
        return
    
    print(f"   ✓ Loaded: {len(hysplit_traj)} points")
    
    # Calculate differences
    print("\n3. 차이 분석...")
    
    differences = calculate_differences(pyhysplit_traj, hysplit_traj)
    
    if not differences:
        print("   ⚠️ 비교 불가 (시간 불일치)")
        return
    
    # Statistics
    distances = [d['distance_km'] for d in differences]
    avg_distance = np.mean(distances)
    max_distance = np.max(distances)
    
    print(f"\n   평균 거리 차이: {avg_distance:.2f} km")
    print(f"   최대 거리 차이: {max_distance:.2f} km")
    
    # Find when divergence starts
    print("\n4. 발산 시점 분석...")
    
    divergence_threshold = 50  # km
    divergence_hour = None
    
    for d in differences:
        if d['distance_km'] > divergence_threshold:
            divergence_hour = d['hour']
            break
    
    if divergence_hour:
        print(f"   ⚠️ 발산 시작: {-divergence_hour:.1f}시간 후")
        print(f"   거리 차이: {[d['distance_km'] for d in differences if d['hour'] == divergence_hour][0]:.2f} km")
    else:
        print(f"   ✓ 발산 없음 (< {divergence_threshold} km)")
    
    # Vertical motion analysis
    print("\n5. 수직 운동 비교...")
    
    py_vertical = analyze_vertical_motion(pyhysplit_traj)
    hy_vertical = analyze_vertical_motion(hysplit_traj)
    
    if py_vertical and hy_vertical:
        py_avg_dp = np.mean([v['dp_dt'] for v in py_vertical])
        hy_avg_dp = np.mean([v['dp_dt'] for v in hy_vertical])
        
        print(f"   PyHYSPLIT 평균 dp/dt: {py_avg_dp:.6f} hPa/s")
        print(f"   HYSPLIT 평균 dp/dt: {hy_avg_dp:.6f} hPa/s")
        print(f"   차이: {abs(py_avg_dp - hy_avg_dp):.6f} hPa/s")
    
    # Detailed comparison at key points
    print("\n6. 주요 시점 상세 비교...")
    
    key_hours = [0, -6, -12, -18, -24]
    
    print(f"\n   {'Hour':<8} {'PyHYSPLIT Lat':<15} {'HYSPLIT Lat':<15} {'Δ Lat':<10} {'Δ Lon':<10} {'Distance':<12}")
    print(f"   {'-'*80}")
    
    for hour in key_hours:
        for d in differences:
            if abs(d['hour'] - hour) < 0.1:
                py = d['pyhysplit']
                hy = d['hysplit']
                
                dlat = py['lat'] - hy['lat']
                dlon = py['lon'] - hy['lon']
                dist = d['distance_km']
                
                print(f"   {hour:<8.1f} {py['lat']:<15.4f} {hy['lat']:<15.4f} {dlat:<10.4f} {dlon:<10.4f} {dist:<12.2f}")
                break
    
    # Save detailed results
    output_file = Path(f"tests/integration/diagnosis_{location_name.lower()}.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'location': location_name,
            'lat': lat,
            'lon': lon,
            'pyhysplit_points': len(pyhysplit_traj),
            'hysplit_points': len(hysplit_traj),
            'avg_distance_km': float(avg_distance),
            'max_distance_km': float(max_distance),
            'divergence_hour': float(divergence_hour) if divergence_hour else None,
            'differences': differences[:10]  # First 10 points
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n   ✓ 상세 결과 저장: {output_file}")
    
    # Recommendations
    print("\n7. 권장사항...")
    
    if avg_distance < 20:
        print("   ✅ 매우 좋은 일치 (평균 < 20 km)")
    elif avg_distance < 50:
        print("   ✓ 양호한 일치 (평균 < 50 km)")
    elif avg_distance < 100:
        print("   ⚠️ 보통 일치 (평균 < 100 km)")
    else:
        print("   ❌ 큰 차이 (평균 > 100 km)")
        print("   조사 필요:")
        print("   - 수직 운동 모드 차이")
        print("   - 보간 방법 차이")
        print("   - 시간 스텝 차이")


def main():
    """메인 함수."""
    
    print("\n" + "="*80)
    print("고위도 위치 상세 진단")
    print("="*80 + "\n")
    
    print("목적: PyHYSPLIT vs HYSPLIT 차이점 정밀 추적")
    print()
    
    # Test locations
    locations = [
        {"name": "서울", "lat": 37.5, "lon": 127.0},
        {"name": "베이징", "lat": 39.9, "lon": 116.4},
    ]
    
    for loc in locations:
        diagnose_location(loc['name'], loc['lat'], loc['lon'])
    
    print("\n" + "="*80)
    print("진단 완료")
    print("="*80 + "\n")
    
    print("다음 단계:")
    print("1. diagnosis_*.json 파일 확인")
    print("2. 발산 시점 및 원인 분석")
    print("3. 필요시 코드 수정")
    print()


if __name__ == "__main__":
    main()
