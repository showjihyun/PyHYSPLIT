"""정방향 궤적 테스트 (Forward Trajectory Test).

역궤적 대신 정방향 궤적을 계산하여 HYSPLIT과 비교합니다.
"""

from datetime import datetime
from pathlib import Path
import json
import numpy as np

from pyhysplit.engine import TrajectoryEngine
from pyhysplit.met_reader import NetCDFReader
from pyhysplit.models import SimulationConfig, StartLocation


def test_forward_trajectory():
    """정방향 24시간 궤적 테스트."""
    
    print("\n" + "="*80)
    print("  정방향 궤적 테스트 (Forward Trajectory)")
    print("="*80 + "\n")
    
    # GFS 데이터 로드
    gfs_file = Path("tests/integration/gfs_cache/gfs_eastasia_24h_very_wide.nc")
    
    if not gfs_file.exists():
        print(f"❌ GFS 데이터 파일이 없습니다: {gfs_file}")
        print("   다음 명령으로 다운로드하세요:")
        print("   python tests/integration/active/download_gfs_west_extension.py")
        print("   python tests/integration/active/merge_gfs_data.py")
        return
    
    print(f"GFS 데이터 로드 중: {gfs_file.name}")
    reader = NetCDFReader()
    met = reader.read(str(gfs_file))
    print(f"✓ 데이터 로드 완료")
    print(f"  범위: {met.lon_grid[0]:.1f}-{met.lon_grid[-1]:.1f}°E, "
          f"{met.lat_grid[0]:.1f}-{met.lat_grid[-1]:.1f}°N")
    print(f"  레벨: {met.z_grid[0]:.0f}-{met.z_grid[-1]:.0f} hPa")
    
    # 테스트 위치들
    test_locations = [
        {"name": "서울", "lat": 37.5, "lon": 127.0},
        {"name": "베이징", "lat": 39.9, "lon": 116.4},
        {"name": "도쿄", "lat": 35.7, "lon": 139.7},
        {"name": "부산", "lat": 35.2, "lon": 129.1},
    ]
    
    results = []
    
    for loc_info in test_locations:
        print(f"\n{'─'*80}")
        print(f"위치: {loc_info['name']} ({loc_info['lat']}°N, {loc_info['lon']}°E)")
        print(f"{'─'*80}")
        
        # 정방향 궤적 설정 (total_run_hours = +24)
        config = SimulationConfig(
            start_time=datetime(2026, 2, 12, 0, 0),
            num_start_locations=1,
            start_locations=[
                StartLocation(
                    lat=loc_info['lat'],
                    lon=loc_info['lon'],
                    height=850.0,
                    height_type="pressure"
                )
            ],
            total_run_hours=+24,  # 정방향 24시간
            vertical_motion=7,
            model_top=10000.0,
            met_files=[],
            auto_vertical_mode=True,
            enable_dynamic_subgrid=True,
            tratio=0.75,
        )
        
        # 궤적 계산
        print(f"\n정방향 24시간 궤적 계산 중...")
        engine = TrajectoryEngine(config, met)
        trajectories = engine.run(output_interval_s=3600.0)
        
        trajectory = trajectories[0]
        
        # 결과 분석
        total_points = len(trajectory)
        expected_points = 25  # 0, 1, 2, ..., 24시간 = 25개
        completion_rate = (total_points / expected_points) * 100
        
        print(f"\n결과:")
        print(f"  총 포인트: {total_points}/{expected_points}")
        print(f"  완료율: {completion_rate:.1f}%")
        
        # 시작점과 끝점
        t0, lon0, lat0, z0 = trajectory[0]
        t_end, lon_end, lat_end, z_end = trajectory[-1]
        
        print(f"\n시작점 (t=0h):")
        print(f"  위치: {lat0:.2f}°N, {lon0:.2f}°E")
        print(f"  압력: {z0:.1f} hPa")
        
        print(f"\n끝점 (t={t_end/3600:.1f}h):")
        print(f"  위치: {lat_end:.2f}°N, {lon_end:.2f}°E")
        print(f"  압력: {z_end:.1f} hPa")
        
        # 이동 거리 계산 (Haversine)
        R = 6371.0  # 지구 반지름 (km)
        lat1_rad, lon1_rad = np.radians(lat0), np.radians(lon0)
        lat2_rad, lon2_rad = np.radians(lat_end), np.radians(lon_end)
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        distance_km = R * c
        
        print(f"\n이동 거리: {distance_km:.1f} km")
        print(f"평균 속도: {distance_km/24:.1f} km/h")
        
        # 방향 계산
        delta_lon = lon_end - lon0
        delta_lat = lat_end - lat0
        
        if abs(delta_lon) > abs(delta_lat):
            direction = "동쪽" if delta_lon > 0 else "서쪽"
        else:
            direction = "북쪽" if delta_lat > 0 else "남쪽"
        
        print(f"주 이동 방향: {direction}")
        
        # 동적 서브그리드 통계
        if engine.dynamic_subgrid:
            stats = engine.dynamic_subgrid.get_expansion_stats()
            print(f"\n동적 서브그리드:")
            print(f"  확장 감지: {stats['expansion_count']}회")
            if stats['expansion_count'] > 0:
                print(f"  확장 이력:")
                for i, exp in enumerate(stats['expansion_history'], 1):
                    print(f"    {i}. 위치: ({exp['position'][0]:.2f}°E, {exp['position'][1]:.2f}°N)")
                    print(f"       풍속: {exp['wind_speed']:.1f} m/s")
                    print(f"       예상 범위: {exp['predicted_range'][0]:.1f}-{exp['predicted_range'][1]:.1f}°E")
        
        # 상태 판정
        if completion_rate >= 100:
            status = "✅ 완료"
        elif completion_rate >= 80:
            status = "⚠️ 부분 완료"
        else:
            status = "❌ 실패"
        
        print(f"\n상태: {status}")
        
        # 결과 저장
        results.append({
            "name": loc_info['name'],
            "lat": loc_info['lat'],
            "lon": loc_info['lon'],
            "total_points": total_points,
            "expected_points": expected_points,
            "completion_rate": completion_rate,
            "start": {"lat": lat0, "lon": lon0, "pressure": z0},
            "end": {"lat": lat_end, "lon": lon_end, "pressure": z_end},
            "distance_km": distance_km,
            "direction": direction,
            "status": status,
            "trajectory": [
                {"time_h": t/3600, "lat": lat, "lon": lon, "pressure": z}
                for t, lon, lat, z in trajectory
            ]
        })
    
    # 전체 요약
    print(f"\n{'='*80}")
    print(f"  전체 요약")
    print(f"{'='*80}\n")
    
    completed = sum(1 for r in results if r['completion_rate'] >= 100)
    partial = sum(1 for r in results if 80 <= r['completion_rate'] < 100)
    failed = sum(1 for r in results if r['completion_rate'] < 80)
    
    print(f"완료: {completed}/{len(results)}")
    print(f"부분 완료: {partial}/{len(results)}")
    print(f"실패: {failed}/{len(results)}")
    
    avg_completion = np.mean([r['completion_rate'] for r in results])
    print(f"\n평균 완료율: {avg_completion:.1f}%")
    
    avg_distance = np.mean([r['distance_km'] for r in results])
    print(f"평균 이동 거리: {avg_distance:.1f} km")
    
    # 결과 저장
    output_file = Path("tests/integration/results/forward_trajectory_results.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test_date": "2026-02-14",
            "test_type": "forward_trajectory",
            "duration_hours": 24,
            "summary": {
                "total_locations": len(results),
                "completed": completed,
                "partial": partial,
                "failed": failed,
                "avg_completion_rate": avg_completion,
                "avg_distance_km": avg_distance,
            },
            "locations": results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n결과 저장: {output_file}")
    
    # 최종 판정
    if completed == len(results):
        print(f"\n🎉 모든 위치에서 정방향 궤적 계산 성공!")
    elif completed + partial == len(results):
        print(f"\n✅ 대부분의 위치에서 정방향 궤적 계산 성공")
    else:
        print(f"\n⚠️ 일부 위치에서 정방향 궤적 계산 실패")
    
    return results


if __name__ == "__main__":
    test_forward_trajectory()
