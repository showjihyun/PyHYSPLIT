"""24시간 테스트 간편 실행 스크립트.

이 스크립트는:
1. 기존 GFS 캐시를 24시간으로 확장
2. 24시간 비교 테스트 실행
3. 결과 요약 출력

사용법:
    python tests/integration/run_24h_test.py
"""

import subprocess
import sys
from pathlib import Path


def main():
    """메인 함수."""
    print(f"\n{'='*80}")
    print(f"  24시간 역궤적 테스트 실행")
    print(f"{'='*80}\n")
    
    script_dir = Path(__file__).parent
    
    # 1단계: GFS 캐시 확장
    print(f"1단계: GFS 캐시를 24시간으로 확장")
    print(f"{'='*80}\n")
    
    gfs_cache_dir = script_dir / "gfs_cache"
    extended_cache = gfs_cache_dir / "gfs_24h_extended.nc"
    
    if extended_cache.exists():
        print(f"✓ 24시간 GFS 캐시가 이미 존재합니다: {extended_cache.name}")
        
        response = input(f"\n다시 생성하시겠습니까? (y/N): ").strip().lower()
        if response == 'y':
            print(f"\nGFS 캐시 재생성 중...")
            result = subprocess.run(
                [sys.executable, str(script_dir / "extend_gfs_to_24h.py")],
                capture_output=False
            )
            if result.returncode != 0:
                print(f"\n❌ GFS 캐시 확장 실패")
                return
    else:
        print(f"24시간 GFS 캐시를 생성합니다...")
        result = subprocess.run(
            [sys.executable, str(script_dir / "extend_gfs_to_24h.py")],
            capture_output=False
        )
        if result.returncode != 0:
            print(f"\n❌ GFS 캐시 확장 실패")
            print(f"   먼저 기존 테스트를 실행하여 GFS 캐시를 생성하세요:")
            print(f"   python -m pytest tests/integration/test_hysplit_web_comparison.py -v -s")
            return
    
    # 2단계: 24시간 테스트 실행
    print(f"\n{'='*80}")
    print(f"2단계: 24시간 비교 테스트 실행")
    print(f"{'='*80}\n")
    
    result = subprocess.run(
        [sys.executable, str(script_dir / "test_24hour_comparison.py")],
        capture_output=False
    )
    
    if result.returncode != 0:
        print(f"\n❌ 24시간 테스트 실패")
        return
    
    # 3단계: 결과 요약
    print(f"\n{'='*80}")
    print(f"3단계: 결과 요약")
    print(f"{'='*80}\n")
    
    report_file = script_dir / "HYSPLIT_WEB_24H_COMPARISON.md"
    viz_file = script_dir / "comparison_24h_visualization.png"
    
    if report_file.exists():
        print(f"✓ 상세 리포트: {report_file}")
        
        # 주요 통계 추출
        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 평균 수평 거리 찾기
            import re
            h_match = re.search(r'평균 수평 거리 차이.*?(\d+\.?\d*)\s*km', content)
            v_match = re.search(r'평균 고도 차이.*?(\d+\.?\d*)\s*m', content)
            
            if h_match and v_match:
                h_dist = float(h_match.group(1))
                v_dist = float(v_match.group(1))
                
                print(f"\n주요 결과:")
                print(f"  평균 수평 거리: {h_dist:.2f} km")
                print(f"  평균 고도 차이: {v_dist:.1f} m")
                
                # 평가
                if h_dist < 20:
                    print(f"  평가: ✓ 매우 우수 (99%+ 일치)")
                elif h_dist < 50:
                    print(f"  평가: ✓ 우수 (97-99% 일치)")
                elif h_dist < 100:
                    print(f"  평가: ✓ 양호 (95-97% 일치)")
                else:
                    print(f"  평가: ⚠ 개선 필요 (<95% 일치)")
        except Exception as e:
            print(f"  ⚠ 통계 추출 실패: {e}")
    
    if viz_file.exists():
        print(f"✓ 시각화: {viz_file}")
    
    print(f"\n{'='*80}")
    print(f"  완료!")
    print(f"{'='*80}\n")
    
    print(f"다음 단계:")
    print(f"  1. 리포트 확인: cat {report_file}")
    print(f"  2. 시각화 확인: (이미지 뷰어로 {viz_file} 열기)")
    print(f"  3. 파라미터 최적화: python tests/integration/quick_optimize.py")


if __name__ == "__main__":
    main()
