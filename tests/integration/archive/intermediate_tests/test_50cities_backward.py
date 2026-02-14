"""전 세계 50개 도시에서 오늘(2026-02-13) GFS 데이터로 24h backward trajectory 테스트.

하나의 글로벌 GFS 데이터셋을 다운로드한 뒤, 50개 도시 각각에서
24시간 backward trajectory를 계산하고 결과를 검증한다.

실행:
    python -m pytest tests/integration/test_50cities_backward.py -v -s
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest

from pyhysplit.models import MetData, SimulationConfig, StartLocation
from pyhysplit.engine import TrajectoryEngine
from pyhysplit.met_reader import convert_omega_to_w


# ---------------------------------------------------------------------------
# 50개 도시 정의 (이름, 위도, 경도)
# ---------------------------------------------------------------------------
CITIES_50 = [
    # 동아시아 (10)
    ("Seoul", 37.57, 126.98),
    ("Tokyo", 35.68, 139.69),
    ("Beijing", 39.90, 116.40),
    ("Shanghai", 31.23, 121.47),
    ("Taipei", 25.03, 121.57),
    ("HongKong", 22.32, 114.17),
    ("Osaka", 34.69, 135.50),
    ("Busan", 35.18, 129.08),
    ("Ulaanbaatar", 47.92, 106.91),
    ("Vladivostok", 43.12, 131.87),
    # 동남아시아 (5)
    ("Bangkok", 13.76, 100.50),
    ("Singapore", 1.35, 103.82),
    ("Manila", 14.60, 120.98),
    ("Hanoi", 21.03, 105.85),
    ("Jakarta", -6.21, 106.85),
    # 남아시아 (5)
    ("Delhi", 28.61, 77.21),
    ("Mumbai", 19.08, 72.88),
    ("Kolkata", 22.57, 88.36),
    ("Dhaka", 23.81, 90.41),
    ("Karachi", 24.86, 67.01),
    # 중동 (3)
    ("Dubai", 25.20, 55.27),
    ("Riyadh", 24.69, 46.72),
    ("Tehran", 35.69, 51.39),
    # 유럽 (10)
    ("London", 51.51, -0.13),
    ("Paris", 48.86, 2.35),
    ("Berlin", 52.52, 13.41),
    ("Madrid", 40.42, -3.70),
    ("Rome", 41.90, 12.50),
    ("Moscow", 55.76, 37.62),
    ("Istanbul", 41.01, 28.98),
    ("Warsaw", 52.23, 21.01),
    ("Stockholm", 59.33, 18.07),
    ("Athens", 37.98, 23.73),
    # 아프리카 (5)
    ("Cairo", 30.04, 31.24),
    ("Lagos", 6.52, 3.38),
    ("Nairobi", -1.29, 36.82),
    ("Johannesburg", -26.20, 28.05),
    ("Casablanca", 33.57, -7.59),
    # 북미 (5)
    ("NewYork", 40.71, -74.01),
    ("LosAngeles", 34.05, -118.24),
    ("Chicago", 41.88, -87.63),
    ("MexicoCity", 19.43, -99.13),
    ("Toronto", 43.65, -79.38),
    # 남미 (5)
    ("SaoPaulo", -23.55, -46.63),
    ("BuenosAires", -34.60, -58.38),
    ("Lima", -12.05, -77.04),
    ("Bogota", 4.71, -74.07),
    ("Santiago", -33.45, -70.67),
    # 오세아니아 (2)
    ("Sydney", -33.87, 151.21),
    ("Auckland", -36.85, 174.76),
]

assert len(CITIES_50) == 50, f"도시 수: {len(CITIES_50)}"

# GFS 날짜 (오늘)
GFS_DATE = "20260213"

# ---------------------------------------------------------------------------
# GFS 다운로드 헬퍼
# ---------------------------------------------------------------------------

def _check_netcdf4():
    try:
        import netCDF4  # noqa: F401
    except ImportError:
        pytest.skip("netCDF4 not installed")


def _check_gfs(date_str: str):
    import netCDF4
    url = f"https://nomads.ncep.noaa.gov/dods/gfs_0p25/gfs{date_str}/gfs_0p25_00z"
    try:
        ds = netCDF4.Dataset(url)
        ds.close()
    except Exception:
        pytest.skip(f"GFS {date_str} 데이터에 접근할 수 없음")


def _download_gfs_region(
    date_str: str,
    lat_range: tuple[float, float],
    lon_range: tuple[float, float],
    lev_indices: list[int] | None = None,
    time_indices: list[int] | None = None,
) -> MetData:
    """GFS OPeNDAP에서 지정 영역의 기상 데이터를 다운로드한다.

    GFS 경도는 0~360 범위이므로, 다운로드 후 lon > 180인 경우
    -180~180 체계로 변환하여 boundary handler와 호환되게 한다.
    """
    import netCDF4

    url = f"https://nomads.ncep.noaa.gov/dods/gfs_0p25/gfs{date_str}/gfs_0p25_00z"
    ds = netCDF4.Dataset(url)
    try:
        all_lat = np.array(ds.variables["lat"][:])
        all_lon = np.array(ds.variables["lon"][:])
        all_lev = np.array(ds.variables["lev"][:])
        all_time = np.array(ds.variables["time"][:])

        lat_mask = (all_lat >= lat_range[0]) & (all_lat <= lat_range[1])
        lon_mask = (all_lon >= lon_range[0]) & (all_lon <= lon_range[1])
        j_start, j_end = np.where(lat_mask)[0][[0, -1]]
        i_start, i_end = np.where(lon_mask)[0][[0, -1]]

        if lev_indices is None:
            lev_indices = list(range(19))  # 1000~200 hPa
        if time_indices is None:
            time_indices = list(range(0, min(9, len(all_time))))  # 0~24h

        lat_grid = all_lat[j_start:j_end + 1]
        lon_grid = all_lon[i_start:i_end + 1]
        lev_grid = all_lev[lev_indices]
        time_raw = all_time[time_indices]
        t_grid = (time_raw - time_raw[0]) * 86400.0

        j_sl = slice(j_start, j_end + 1)
        i_sl = slice(i_start, i_end + 1)
        ny, nx = j_end - j_start + 1, i_end - i_start + 1

        print(f"    영역: lat[{lat_grid[0]:.1f},{lat_grid[-1]:.1f}] "
              f"lon[{lon_grid[0]:.1f},{lon_grid[-1]:.1f}] "
              f"{len(time_indices)}t×{len(lev_indices)}z×{ny}y×{nx}x")

        u = np.array(ds.variables["ugrdprs"][time_indices, lev_indices, j_sl, i_sl], dtype=np.float64)
        v = np.array(ds.variables["vgrdprs"][time_indices, lev_indices, j_sl, i_sl], dtype=np.float64)
        omega = np.array(ds.variables["vvelprs"][time_indices, lev_indices, j_sl, i_sl], dtype=np.float64)
        t_field = np.array(ds.variables["tmpprs"][time_indices, lev_indices, j_sl, i_sl], dtype=np.float64)
        hgt = np.array(ds.variables["hgtprs"][time_indices, lev_indices, j_sl, i_sl], dtype=np.float64)

        P_3d = np.broadcast_to(
            lev_grid[np.newaxis, :, np.newaxis, np.newaxis] * 100.0,
            omega.shape,
        )
        w = convert_omega_to_w(omega, t_field, P_3d)
        terrain = np.zeros((ny, nx))

        # z_grid 오름차순 보장
        if len(lev_grid) > 1 and lev_grid[0] > lev_grid[-1]:
            lev_grid = lev_grid[::-1]
            u, v, w = u[:, ::-1], v[:, ::-1], w[:, ::-1]
            t_field, hgt = t_field[:, ::-1], hgt[:, ::-1]
        # lat_grid 오름차순 보장
        if len(lat_grid) > 1 and lat_grid[0] > lat_grid[-1]:
            lat_grid = lat_grid[::-1]
            u, v, w = u[:, :, ::-1], v[:, :, ::-1], w[:, :, ::-1]
            t_field, hgt = t_field[:, :, ::-1], hgt[:, :, ::-1]
            terrain = terrain[::-1, :]

        # GFS 경도(0~360) → -180~180 변환 (boundary handler 호환)
        lon_grid = np.where(lon_grid > 180.0, lon_grid - 360.0, lon_grid)
        # 변환 후 정렬이 깨질 수 있으므로 정렬
        if len(lon_grid) > 1 and lon_grid[0] > lon_grid[-1]:
            sort_idx = np.argsort(lon_grid)
            lon_grid = lon_grid[sort_idx]
            u = u[:, :, :, sort_idx]
            v = v[:, :, :, sort_idx]
            w = w[:, :, :, sort_idx]
            t_field = t_field[:, :, :, sort_idx]
            hgt = hgt[:, :, :, sort_idx]
            terrain = terrain[:, sort_idx]

        return MetData(
            u=u, v=v, w=w, t_field=t_field, rh=None, hgt=hgt,
            precip=None, pbl_height=None, terrain=terrain,
            lon_grid=lon_grid, lat_grid=lat_grid,
            z_grid=lev_grid, t_grid=t_grid,
            z_type="pressure", source="GFS_NC",
        )
    finally:
        ds.close()


def _get_gfs_region_for_city(lat: float, lon: float) -> tuple[tuple[float, float], list[tuple[float, float]]]:
    """도시 좌표를 기반으로 GFS 다운로드 영역을 결정한다.

    Returns
    -------
    lat_range : tuple
    lon_ranges : list of tuple
        하나 또는 두 개의 GFS 경도 범위. 경도 0° 근처 도시는
        두 영역(340~359.75, 0~40)을 반환한다.
    """
    margin = 20.0
    lat_range = (max(-60.0, lat - margin), min(70.0, lat + margin))

    # GFS 경도: 0~359.75
    gfs_lon = lon if lon >= 0 else lon + 360.0
    lon_lo = gfs_lon - margin
    lon_hi = gfs_lon + margin

    # 경도 범위가 0을 걸치는 경우 (예: 런던 gfs_lon=359.87, lon_lo=339.87, lon_hi=379.87)
    # → 두 영역으로 분할: (339.87, 359.75) + (0, 19.87)
    if lon_hi > 359.75 and lon_lo < 359.75:
        ranges = [
            (max(0.0, lon_lo), 359.75),
            (0.0, min(359.75, lon_hi - 360.0)),
        ]
        return lat_range, ranges

    # 경도 범위가 0 미만인 경우 (서반구 도시에서 마진이 0을 넘을 때)
    if lon_lo < 0:
        ranges = [
            (360.0 + lon_lo, 359.75),
            (0.0, min(359.75, lon_hi)),
        ]
        return lat_range, ranges

    # 일반적인 경우: 단일 영역
    lon_lo = max(0.0, lon_lo)
    lon_hi = min(359.75, lon_hi)

    # 최소 폭 보장
    if lon_hi - lon_lo < 10.0:
        center = (lon_lo + lon_hi) / 2.0
        lon_lo = max(0.0, center - 20.0)
        lon_hi = min(359.75, center + 20.0)

    return lat_range, [(lon_lo, lon_hi)]


def _merge_met_data(met1: MetData, met2: MetData) -> MetData:
    """두 MetData를 경도 축으로 합친다.

    met1의 lon_grid가 met2보다 작은(서쪽) 값이어야 한다.
    합친 후 lon_grid가 오름차순이 되도록 정렬한다.
    """
    # 두 데이터의 lon_grid를 합치기
    lon_combined = np.concatenate([met1.lon_grid, met2.lon_grid])
    sort_idx = np.argsort(lon_combined)
    lon_combined = lon_combined[sort_idx]

    # 데이터 배열 합치기 (경도 축 = axis 3)
    def merge_field(f1, f2):
        if f1 is None or f2 is None:
            return None
        combined = np.concatenate([f1, f2], axis=3)
        return combined[:, :, :, sort_idx]

    u = merge_field(met1.u, met2.u)
    v = merge_field(met1.v, met2.v)
    w = merge_field(met1.w, met2.w)
    t_field = merge_field(met1.t_field, met2.t_field)
    hgt = merge_field(met1.hgt, met2.hgt)

    terrain = np.concatenate([met1.terrain, met2.terrain], axis=1)
    terrain = terrain[:, sort_idx]

    return MetData(
        u=u, v=v, w=w, t_field=t_field, rh=None, hgt=hgt,
        precip=None, pbl_height=None, terrain=terrain,
        lon_grid=lon_combined, lat_grid=met1.lat_grid,
        z_grid=met1.z_grid, t_grid=met1.t_grid,
        z_type=met1.z_type, source=met1.source,
    )


def _run_backward_24h(met: MetData, lat: float, lon: float) -> list[tuple]:
    """24시간 backward trajectory 실행.

    met 데이터의 lon_grid가 이미 -180~180으로 변환되어 있으므로
    도시의 원래 경도를 그대로 사용한다.
    """
    start = StartLocation(lat=lat, lon=lon, height=850.0)
    config = SimulationConfig(
        start_time=datetime(2026, 1, 1),
        num_start_locations=1,
        start_locations=[start],
        total_run_hours=-24,
        vertical_motion=0,
        model_top=10000.0,
        met_files=[],
        turbulence_on=False,
        dt_max=3600.0,
    )
    engine = TrajectoryEngine(config, met)
    return engine.run(output_interval_s=3600.0)[0]


# ---------------------------------------------------------------------------
# 지역별 도시 그룹핑 (같은 지역 도시들은 하나의 GFS 데이터셋 공유)
# ---------------------------------------------------------------------------

REGIONS = {
    "east_asia": {
        "cities": CITIES_50[0:10],
        "lat_range": (15.0, 60.0),
        "lon_range": (90.0, 155.0),
    },
    "southeast_asia": {
        "cities": CITIES_50[10:15],
        "lat_range": (-15.0, 30.0),
        "lon_range": (85.0, 130.0),
    },
    "south_asia": {
        "cities": CITIES_50[15:20],
        "lat_range": (10.0, 40.0),
        "lon_range": (55.0, 100.0),
    },
    "middle_east": {
        "cities": CITIES_50[20:23],
        "lat_range": (15.0, 45.0),
        "lon_range": (35.0, 65.0),
    },
    "europe": {
        "cities": CITIES_50[23:33],
        "lat_range": (30.0, 70.0),
        "lon_range": (340.0, 359.75),  # 서유럽 (음수 경도 → GFS 340~360)
        # 유럽은 경도가 -3.7~37.6 범위라 두 영역 필요
    },
    "africa": {
        "cities": CITIES_50[33:38],
        "lat_range": (-35.0, 45.0),
        "lon_range": (340.0, 359.75),  # placeholder, 개별 다운로드
    },
    "north_america": {
        "cities": CITIES_50[38:43],
        "lat_range": (10.0, 55.0),
        "lon_range": (240.0, 300.0),  # -120~-60 → GFS 240~300
    },
    "south_america": {
        "cities": CITIES_50[43:48],
        "lat_range": (-45.0, 15.0),
        "lon_range": (280.0, 320.0),  # -80~-40 → GFS 280~320
    },
    "oceania": {
        "cities": CITIES_50[48:50],
        "lat_range": (-45.0, -25.0),
        "lon_range": (140.0, 185.0),
    },
}


# ---------------------------------------------------------------------------
# 테스트 클래스
# ---------------------------------------------------------------------------

# 도시별 파라미터 생성
_city_params = [(name, lat, lon) for name, lat, lon in CITIES_50]


class Test50CitiesBackward:
    """전 세계 50개 도시에서 GFS 2026-02-13 데이터로 24h backward trajectory."""

    # 지역별 캐시된 MetData
    _met_cache: dict[str, MetData] = {}

    @classmethod
    def _get_met_for_city(cls, city_name: str, lat: float, lon: float) -> MetData:
        """도시에 맞는 MetData를 캐시에서 가져오거나 다운로드한다."""
        lat_range, lon_ranges = _get_gfs_region_for_city(lat, lon)
        cache_key = f"{lat_range}_{lon_ranges}"

        if cache_key not in cls._met_cache:
            if len(lon_ranges) == 1:
                print(f"\n  [{city_name}] GFS 다운로드: lat{lat_range} lon{lon_ranges[0]}")
                met = _download_gfs_region(
                    GFS_DATE,
                    lat_range=lat_range,
                    lon_range=lon_ranges[0],
                )
            else:
                # 두 영역 다운로드 후 합치기 (경도 0° 근처 도시)
                print(f"\n  [{city_name}] GFS 다운로드 (2영역): lat{lat_range} "
                      f"lon{lon_ranges[0]} + lon{lon_ranges[1]}")
                met1 = _download_gfs_region(
                    GFS_DATE,
                    lat_range=lat_range,
                    lon_range=lon_ranges[0],
                )
                met2 = _download_gfs_region(
                    GFS_DATE,
                    lat_range=lat_range,
                    lon_range=lon_ranges[1],
                )
                met = _merge_met_data(met1, met2)

            cls._met_cache[cache_key] = met

        return cls._met_cache[cache_key]

    @pytest.fixture(autouse=True)
    def check_prerequisites(self):
        _check_netcdf4()
        _check_gfs(GFS_DATE)

    @pytest.mark.parametrize("city_name,lat,lon", _city_params,
                             ids=[c[0] for c in _city_params])
    def test_backward_24h(self, city_name: str, lat: float, lon: float):
        """각 도시에서 24시간 backward trajectory를 계산하고 검증한다."""
        met = self._get_met_for_city(city_name, lat, lon)
        traj = _run_backward_24h(met, lat, lon)

        # 기본 검증
        assert len(traj) >= 2, f"{city_name}: 궤적 포인트 부족 ({len(traj)})"

        # backward → 시간 감소
        assert traj[-1][0] <= traj[0][0], f"{city_name}: 시간이 감소해야 함"

        # 시작점 확인
        assert abs(traj[0][2] - lat) < 0.1, \
            f"{city_name}: 시작 위도 불일치 ({traj[0][2]} vs {lat})"
        assert abs(traj[0][1] - lon) < 0.1, \
            f"{city_name}: 시작 경도 불일치 ({traj[0][1]} vs {lon})"

        # 궤적 요약 출력
        t_start, lon0, lat0, z0 = traj[0]
        t_end, lon_e, lat_e, z_e = traj[-1]
        d_lat = lat_e - lat0
        d_lon = lon_e - lon0
        print(f"  {city_name:15s} | {len(traj):3d}pts | "
              f"start=({lat0:6.2f},{lon0:7.2f}) → end=({lat_e:6.2f},{lon_e:7.2f}) | "
              f"Δ=({d_lat:+6.2f},{d_lon:+7.2f})")


# ---------------------------------------------------------------------------
# 요약 테이블 출력 (전체 테스트 후)
# ---------------------------------------------------------------------------

def test_summary_table():
    """50개 도시 테스트 결과 요약 (이 테스트는 단독 실행 시 skip)."""
    # 이 테스트는 parametrize 테스트들이 모두 통과한 후 정보 제공용
    print("\n" + "=" * 80)
    print("  50개 도시 24h Backward Trajectory 테스트 완료")
    print("=" * 80)
    print(f"  GFS 날짜: {GFS_DATE}")
    print(f"  도시 수: {len(CITIES_50)}")
    print(f"  시작 고도: 850 hPa")
    print(f"  역추적 시간: 24시간")
    print("=" * 80)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
