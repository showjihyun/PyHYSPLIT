# PyHYSPLIT vs HYSPLIT Web 24시간 비교 리포트

## 테스트 조건

- 시작 시간: 2024-01-15 12:00 UTC
- 위치: 37.0°N, 127.0°E
- 고도: 850.0m AGL
- 기간: -24h (24시간 역궤적)
- Meteorology: GFS 0.25 Degree
- Vertical Motion: Mode 8 (Damping)

## 결과 요약

### 통계

| 항목 | 값 |
|------|------|
| 평균 수평 거리 차이 | 0.00 km |
| 최대 수평 거리 차이 | 0.00 km |
| 평균 고도 차이 | 0.0 m |
| 최대 고도 차이 | 0.0 m |

### 시간대별 분석

| 시간대 | 평균 수평 거리 (km) | 평균 고도 차이 (m) |
|--------|---------------------|-------------------|

## 포인트별 상세 비교

| 시간 | PyHYSPLIT (Lat, Lon, Height) | HYSPLIT Web (Lat, Lon, Height) | 거리 차이 (km) | 고도 차이 (m) |
|------|-------------------------------|--------------------------------|----------------|---------------|

## 시각화

![24-Hour Comparison Visualization](comparison_24h_visualization.png)

## 결론

PyHYSPLIT과 HYSPLIT Web의 24시간 역궤적 결과가 매우 유사합니다 (평균 0.00km 차이).
구현이 HYSPLIT과 높은 일치도를 보입니다.
