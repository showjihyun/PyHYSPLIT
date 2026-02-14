"""HYSPLIT Web 압력 변화 패턴 분석"""
from pathlib import Path

# HYSPLIT Web tdump 파일 읽기
tdump_file = Path("tests/integration/hysplit_web_data/tdump_서울.txt")

with open(tdump_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("="*80)
print("  HYSPLIT Web 압력 변화 패턴 분석 (서울)")
print("="*80)

# 데이터 파싱
points = []
for line in lines:
    parts = line.split()
    if len(parts) >= 13:
        try:
            int(parts[0])
            int(parts[1])
            int(parts[2])
            
            age = float(parts[8])
            lat = float(parts[9])
            lon = float(parts[10])
            height = float(parts[11])
            pressure = float(parts[12])
            
            points.append({
                'age': age,
                'lat': lat,
                'lon': lon,
                'height': height,
                'pressure': pressure
            })
        except (ValueError, IndexError):
            continue

print(f"\n총 {len(points)}개 포인트")
print(f"\n{'Age(h)':>7} {'Lat':>7} {'Lon':>8} {'Height(m)':>10} {'Pressure(hPa)':>14} {'dP(hPa)':>10}")
print("-"*70)

for i, pt in enumerate(points):
    if i == 0:
        dp = 0.0
    else:
        dp = pt['pressure'] - points[i-1]['pressure']
    
    print(f"{pt['age']:>7.1f} {pt['lat']:>7.3f} {pt['lon']:>8.3f} {pt['height']:>10.1f} {pt['pressure']:>14.1f} {dp:>10.1f}")

# 통계
pressures = [pt['pressure'] for pt in points]
dps = [points[i]['pressure'] - points[i-1]['pressure'] for i in range(1, len(points))]

print(f"\n압력 통계:")
print(f"  시작: {pressures[0]:.1f} hPa")
print(f"  종료: {pressures[-1]:.1f} hPa")
print(f"  변화: {pressures[-1] - pressures[0]:.1f} hPa")
print(f"  평균 dP/h: {(pressures[-1] - pressures[0]) / len(dps):.2f} hPa")

print(f"\n시간당 압력 변화 (dP):")
print(f"  평균: {sum(dps) / len(dps):.2f} hPa/h")
print(f"  최소: {min(dps):.2f} hPa/h")
print(f"  최대: {max(dps):.2f} hPa/h")
print(f"  표준편차: {(sum((dp - sum(dps)/len(dps))**2 for dp in dps) / len(dps))**0.5:.2f} hPa/h")

# 상승/하강 분석
ascending = sum(1 for dp in dps if dp < 0)
descending = sum(1 for dp in dps if dp > 0)

print(f"\n수직 운동:")
print(f"  상승 (dP < 0): {ascending}/{len(dps)} ({ascending/len(dps)*100:.1f}%)")
print(f"  하강 (dP > 0): {descending}/{len(dps)} ({descending/len(dps)*100:.1f}%)")

print(f"\n분석:")
print(f"  - 압력이 증가하면 하강 (고도 감소)")
print(f"  - 압력이 감소하면 상승 (고도 증가)")
print(f"  - HYSPLIT은 복잡한 수직 운동 패턴을 보임")
print(f"  - 단순 omega 적분으로는 재현 어려움")
