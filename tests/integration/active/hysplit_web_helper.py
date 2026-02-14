"""HYSPLIT Web 실행 도우미 스크립트.

HYSPLIT Web에서 복사-붙여넣기할 수 있는 설정 값을 출력합니다.

사용법:
    python tests/integration/hysplit_web_helper.py
"""

from pathlib import Path

# 테스트 지역
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


def print_hysplit_web_guide():
    """HYSPLIT Web 실행 가이드 출력."""
    
    print("\n" + "="*80)
    print("  HYSPLIT Web 실행 가이드")
    print("="*80 + "\n")
    
    print("웹사이트: https://www.ready.noaa.gov/HYSPLIT_traj.php\n")
    
    print("="*80)
    print("  공통 설정 (모든 지역에 동일하게 적용)")
    print("="*80 + "\n")
    
    print("Meteorology:")
    print("  Model: GFS (0.25 degree)")
    print("  Start Time: 2026-02-14 00:00 UTC")
    print("    Year: 2026")
    print("    Month: 02")
    print("    Day: 14")
    print("    Hour: 00")
    print("    Minute: 00")
    
    print("\nTrajectory:")
    print("  Direction: Backward")
    print("  Duration: 24 hours")
    print("  Vertical Motion: Model Vertical Velocity")
    
    print("\nOutput:")
    print("  Interval: 1 hour")
    
    print("\n" + "="*80)
    print("  각 지역별 설정 (8개 지역)")
    print("="*80 + "\n")
    
    for i, (location_name, info) in enumerate(TEST_LOCATIONS.items(), 1):
        print(f"\n{'='*80}")
        print(f"  [{i}/8] {location_name} ({info['region']})")
        print(f"{'='*80}\n")
        
        print(f"Start Location:")
        print(f"  Latitude:  {info['lat']}")
        print(f"  Longitude: {info['lon']}")
        print(f"  Height:    {info['height']} meters AGL")
        
        print(f"\n실행 순서:")
        print(f"  1. 위 값들을 HYSPLIT Web에 입력")
        print(f"  2. 'Run' 버튼 클릭")
        print(f"  3. 계산 완료 대기 (1-2분)")
        print(f"  4. 'Trajectory Endpoints' 다운로드")
        print(f"  5. 파일명을 'tdump_{location_name}.txt'로 변경")
        print(f"  6. 'tests\\integration\\hysplit_web_data\\' 폴더에 저장")
        
        if i < len(TEST_LOCATIONS):
            print(f"\n다음 지역으로 이동 →")
    
    print(f"\n\n{'='*80}")
    print(f"  모든 지역 완료 후")
    print(f"{'='*80}\n")
    
    print(f"저장된 파일 확인:")
    print(f"  tests\\integration\\hysplit_web_data\\")
    print(f"    ├── tdump_서울.txt")
    print(f"    ├── tdump_부산.txt")
    print(f"    ├── tdump_제주.txt")
    print(f"    ├── tdump_도쿄.txt")
    print(f"    ├── tdump_오사카.txt")
    print(f"    ├── tdump_베이징.txt")
    print(f"    ├── tdump_상하이.txt")
    print(f"    └── tdump_타이베이.txt")
    
    print(f"\n비교 실행:")
    print(f"  python tests\\integration\\multi_location_24h_comparison.py --compare")
    
    print(f"\n{'='*80}")
    print(f"  예상 소요 시간")
    print(f"{'='*80}\n")
    
    print(f"각 지역당: 3-5분 (입력 + 계산 + 다운로드)")
    print(f"총 소요 시간: 30-60분 (8개 지역)")
    print(f"비교 실행: 1분")


def print_quick_reference():
    """빠른 참조 테이블 출력."""
    
    print("\n\n" + "="*80)
    print("  빠른 참조 테이블 (복사-붙여넣기용)")
    print("="*80 + "\n")
    
    print("| 지역 | 위도 | 경도 | 고도 | 저장 파일명 |")
    print("|------|------|------|------|------------|")
    
    for location_name, info in TEST_LOCATIONS.items():
        print(f"| {location_name:6s} | {info['lat']:5.1f} | {info['lon']:6.1f} | {info['height']:4.0f} | tdump_{location_name}.txt |")
    
    print("\n공통 설정:")
    print("  - Model: GFS (0.25 degree)")
    print("  - Start: 2026-02-14 00:00 UTC")
    print("  - Direction: Backward")
    print("  - Duration: 24 hours")
    print("  - Vertical Motion: Model Vertical Velocity")
    print("  - Interval: 1 hour")


def check_existing_files():
    """이미 다운로드된 파일 확인."""
    
    print("\n\n" + "="*80)
    print("  다운로드 상태 확인")
    print("="*80 + "\n")
    
    hysplit_web_dir = Path("tests/integration/hysplit_web_data")
    
    if not hysplit_web_dir.exists():
        print(f"❌ 디렉토리가 없습니다: {hysplit_web_dir}")
        print(f"   디렉토리를 생성합니다...")
        hysplit_web_dir.mkdir(parents=True, exist_ok=True)
        print(f"   ✓ 생성 완료")
    
    print(f"디렉토리: {hysplit_web_dir}\n")
    
    completed = 0
    missing = []
    
    for location_name in TEST_LOCATIONS.keys():
        tdump_file = hysplit_web_dir / f"tdump_{location_name}.txt"
        
        if tdump_file.exists():
            size = tdump_file.stat().st_size
            print(f"  ✓ {location_name:8s} - {tdump_file.name} ({size:,} bytes)")
            completed += 1
        else:
            print(f"  ❌ {location_name:8s} - {tdump_file.name} (없음)")
            missing.append(location_name)
    
    print(f"\n진행 상황: {completed}/{len(TEST_LOCATIONS)} 완료 ({completed/len(TEST_LOCATIONS)*100:.0f}%)")
    
    if missing:
        print(f"\n아직 다운로드하지 않은 지역:")
        for loc in missing:
            info = TEST_LOCATIONS[loc]
            print(f"  - {loc}: {info['lat']}, {info['lon']}, {info['height']}m")
    else:
        print(f"\n✅ 모든 지역 다운로드 완료!")
        print(f"\n다음 단계:")
        print(f"  python tests\\integration\\multi_location_24h_comparison.py --compare")


def create_checklist():
    """체크리스트 파일 생성."""
    
    checklist_file = Path("tests/integration/hysplit_web_data/CHECKLIST.txt")
    
    with open(checklist_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("HYSPLIT Web 다운로드 체크리스트\n")
        f.write("="*80 + "\n\n")
        
        f.write("웹사이트: https://www.ready.noaa.gov/HYSPLIT_traj.php\n\n")
        
        f.write("공통 설정:\n")
        f.write("  [ ] Model: GFS (0.25 degree)\n")
        f.write("  [ ] Start: 2026-02-14 00:00 UTC\n")
        f.write("  [ ] Direction: Backward\n")
        f.write("  [ ] Duration: 24 hours\n")
        f.write("  [ ] Vertical Motion: Model Vertical Velocity\n")
        f.write("  [ ] Interval: 1 hour\n\n")
        
        f.write("각 지역별 다운로드:\n\n")
        
        for i, (location_name, info) in enumerate(TEST_LOCATIONS.items(), 1):
            f.write(f"[{i}/8] {location_name} ({info['region']})\n")
            f.write(f"  [ ] Latitude: {info['lat']}\n")
            f.write(f"  [ ] Longitude: {info['lon']}\n")
            f.write(f"  [ ] Height: {info['height']} meters AGL\n")
            f.write(f"  [ ] Run 클릭\n")
            f.write(f"  [ ] 계산 완료 대기\n")
            f.write(f"  [ ] Trajectory Endpoints 다운로드\n")
            f.write(f"  [ ] tdump_{location_name}.txt로 저장\n\n")
        
        f.write("\n비교 실행:\n")
        f.write("  [ ] python tests\\integration\\multi_location_24h_comparison.py --compare\n")
    
    print(f"\n✅ 체크리스트 생성: {checklist_file}")


def main():
    """메인 함수."""
    
    print_hysplit_web_guide()
    print_quick_reference()
    check_existing_files()
    create_checklist()
    
    print("\n\n" + "="*80)
    print("  완료!")
    print("="*80 + "\n")
    
    print("다음 단계:")
    print("  1. https://www.ready.noaa.gov/HYSPLIT_traj.php 접속")
    print("  2. 위 가이드를 참고하여 8개 지역 실행")
    print("  3. tdump 파일을 tests\\integration\\hysplit_web_data\\에 저장")
    print("  4. python tests\\integration\\multi_location_24h_comparison.py --compare")
    
    print("\n도움말:")
    print("  - 체크리스트: tests\\integration\\hysplit_web_data\\CHECKLIST.txt")
    print("  - 상세 가이드: tests\\integration\\HYSPLIT_WEB_BATCH_GUIDE.md")
    print("  - 다음 단계: tests\\integration\\NEXT_STEPS.md")


if __name__ == "__main__":
    main()
