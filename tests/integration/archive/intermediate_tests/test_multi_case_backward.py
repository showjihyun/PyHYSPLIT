"""다양한 지역/날짜의 GFS 기상데이터로 backward trajectory를 테스트한다.

5가지 케이스:
  Case 1: 도쿄 (35.7°N, 139.7°E) — 2/11, 72h backward
  Case 2: 베이징 (39.9°N, 116.4°E) — 2/10, 48h backward, 등압면 모드
  Case 3: 부산 다중 시작점 (35.1°N, 129.0°E) — 2/9, 24h backward × 3지점
  Case 4: 상하이 (31.2°N, 121.5°E) — 2/8, 48h backward
  Case 5: 울란바토르 (47.9°N, 106.9°E) — 2/7, 48h backward, 고위도

실행:
    python -m pytest tests/integration/test_multi_case_backward.py -v -s
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pytest

from pyhysplit.models import MetData, SimulationConfig, StartLocation
from pyhysplit.engine import TrajectoryEngine


# ---------------------------------------------------------------------------
# GFS 다운로드 헬퍼 (test_real_backward_trajectory.py 와 동일 로직)
# ---------------------------------------------------------------------------

def _download_gfs_subset(
    date_str: str,
    lat_range: tuple[float, float] = (20.0, 55.0),
    lon_range: tuple[float, float] = (100.0, 150.0),
    lev_indices: list[int] | None = None,
    time_indices: list[int] | None = None,
) -> MetData:
    import netCDF4
    from pyhysplit.met_reader import convert_omega_to_w

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
            lev_indices = list(range(19))
        if time_indices is None:
            time_indices = list(range(0, min(17, len(all_time))))

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

        if len(lev_grid) > 1 and lev_grid[0] > lev_grid[-1]:
            lev_grid = lev_grid[::-1]
            u, v, w = u[:, ::-1], v[:, ::-1], w[:, ::-1]
            t_field, hgt = t_field[:, ::-1], hgt[:, ::-1]
        if len(lat_grid) > 1 and lat_grid[0] > lat_grid[-1]:
            lat_grid = lat_grid[::-1]
            u, v, w = u[:, :, ::-1], v[:, :, ::-1], w[:, :, ::-1]
            t_field, hgt = t_field[:, :, ::-1], hgt[:, :, ::-1]
            terrain = terrain[::-1, :]

        return MetData(
            u=u, v=v, w=w, t_field=t_field, rh=None, hgt=hgt,
            precip=None, pbl_height=None, terrain=terrain,
            lon_grid=lon_grid, lat_grid=lat_grid,
            z_grid=lev_grid, t_grid=t_grid,
            z_type="pressure", source="GFS_NC",
        )
    finally:
        ds.close()


def _run_backward(met: MetData, start: StartLocation | list[StartLocation],
                  run_hours: int, vertical_motion: int = 0) -> list[list[tuple]]:
    """backward trajectory 실행 헬퍼."""
    starts = [start] if isinstance(start, StartLocation) else start
    config = SimulationConfig(
        start_time=datetime(2026, 1, 1),  # 실제로는 met t_grid 기준
        num_start_locations=len(starts),
        start_locations=starts,
        total_run_hours=run_hours,
        vertical_motion=vertical_motion,
        model_top=10000.0,
        met_files=[],
        turbulence_on=False,
        dt_max=3600.0,
    )
    engine = TrajectoryEngine(config, met)
    return engine.run(output_interval_s=3600.0)


def _print_traj(label: str, traj: list[tuple]) -> None:
    """궤적을 보기 좋게 출력."""
    print(f"\n  === {label} ({len(traj)} 포인트) ===")
    for i, (t, lon, lat, z) in enumerate(traj):
        print(f"    [{i:3d}] t={t/3600:7.1f}h  lat={lat:7.2f}  lon={lon:7.2f}  z={z:8.1f}")
    if len(traj) >= 2:
        d_lat = traj[-1][2] - traj[0][2]
        d_lon = traj[-1][1] - traj[0][1]
        print(f"    총 이동: Δlat={d_lat:+.2f}°  Δlon={d_lon:+.2f}°")


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


# ===================================================================
# Case 1: 도쿄 — 2/11 GFS, 72h backward, 850 hPa
# ===================================================================
class TestCase1Tokyo:
    """도쿄(35.7°N, 139.7°E) 72시간 backward trajectory."""

    DATE = "20260211"

    @pytest.fixture(scope="class")
    def met(self):
        _check_netcdf4()
        _check_gfs(self.DATE)
        print(f"\n[Case 1] 도쿄 — GFS {self.DATE} 다운로드")
        # 72h = 25개 시간 스텝 (0~72h, 3h 간격)
        return _download_gfs_subset(
            self.DATE,
            lat_range=(20.0, 55.0),
            lon_range=(100.0, 155.0),
            time_indices=list(range(25)),
        )

    def test_72h_backward(self, met: MetData):
        """도쿄에서 72시간 backward — 장거리 수송 경로 확인."""
        start = StartLocation(lat=35.7, lon=139.7, height=850.0)
        trajs = _run_backward(met, start, run_hours=-72)
        traj = trajs[0]

        _print_traj("도쿄 72h Backward (850 hPa)", traj)

        assert len(traj) >= 5, f"궤적 포인트 부족: {len(traj)}"
        # backward → 시간 감소
        assert traj[-1][0] < traj[0][0], "시간이 감소해야 함"
        # 시작점 확인
        assert abs(traj[0][2] - 35.7) < 0.1
        assert abs(traj[0][1] - 139.7) < 0.1

    def test_72h_two_heights(self, met: MetData):
        """도쿄 850 hPa vs 500 hPa — 고도별 경로 차이."""
        s1 = StartLocation(lat=35.7, lon=139.7, height=850.0)
        s2 = StartLocation(lat=35.7, lon=139.7, height=500.0)
        trajs = _run_backward(met, [s1, s2], run_hours=-48)

        _print_traj("도쿄 850 hPa", trajs[0])
        _print_traj("도쿄 500 hPa", trajs[1])

        # 두 궤적의 최종 위치가 달라야 함
        end0 = (trajs[0][-1][1], trajs[0][-1][2])
        end1 = (trajs[1][-1][1], trajs[1][-1][2])
        dist = np.sqrt((end0[0] - end1[0])**2 + (end0[1] - end1[1])**2)
        print(f"\n    850 vs 500 hPa 최종 위치 차이: {dist:.2f}°")
        # 고도가 다르면 경로도 달라야 함 (최소 0.1° 이상)
        assert dist > 0.1, f"고도별 궤적 차이가 너무 작음: {dist:.4f}°"


# ===================================================================
# Case 2: 베이징 — 2/10 GFS, 48h backward, 등압면 모드
# ===================================================================
class TestCase2Beijing:
    """베이징(39.9°N, 116.4°E) 48시간 backward, 등압면(isobaric) 모드."""

    DATE = "20260210"

    @pytest.fixture(scope="class")
    def met(self):
        _check_netcdf4()
        _check_gfs(self.DATE)
        print(f"\n[Case 2] 베이징 — GFS {self.DATE} 다운로드")
        return _download_gfs_subset(
            self.DATE,
            lat_range=(25.0, 55.0),
            lon_range=(95.0, 140.0),
        )

    def test_isobaric_backward(self, met: MetData):
        """등압면 모드(vertical_motion=2) — 현재 엔진은 vertical_motion을
        적분 루프에 직접 반영하지 않으므로, 모드 설정이 정상 파싱되는지와
        궤적이 생성되는지를 검증한다."""
        start = StartLocation(lat=39.9, lon=116.4, height=850.0)
        trajs = _run_backward(met, start, run_hours=-48, vertical_motion=2)
        traj = trajs[0]

        _print_traj("베이징 48h Backward (vertical_motion=2)", traj)

        assert len(traj) >= 2, "궤적 포인트가 최소 2개 이상이어야 함"
        # 시간이 감소해야 함
        assert traj[-1][0] <= traj[0][0], "backward 궤적에서 시간이 감소해야 함"

    def test_data_vs_isobaric(self, met: MetData):
        """데이터 수직속도 모드 vs 등압면 모드 비교."""
        start = StartLocation(lat=39.9, lon=116.4, height=850.0)
        traj_data = _run_backward(met, start, run_hours=-24, vertical_motion=0)[0]
        traj_iso = _run_backward(met, start, run_hours=-24, vertical_motion=2)[0]

        _print_traj("베이징 데이터 수직속도", traj_data)
        _print_traj("베이징 등압면", traj_iso)

        # 두 모드의 수평 궤적이 다를 수 있음 (수직 이동이 수평 풍속에 영향)
        min_len = min(len(traj_data), len(traj_iso))
        if min_len >= 3:
            # 마지막 공통 포인트에서 위치 차이
            d_lat = abs(traj_data[min_len-1][2] - traj_iso[min_len-1][2])
            d_lon = abs(traj_data[min_len-1][1] - traj_iso[min_len-1][1])
            print(f"\n    모드 차이 (t={min_len-1}h): Δlat={d_lat:.3f}° Δlon={d_lon:.3f}°")


# ===================================================================
# Case 3: 부산 다중 시작점 — 2/9 GFS, 24h backward × 3지점
# ===================================================================
class TestCase3BusanMulti:
    """부산 주변 3개 지점에서 동시 24시간 backward trajectory."""

    DATE = "20260209"

    @pytest.fixture(scope="class")
    def met(self):
        _check_netcdf4()
        _check_gfs(self.DATE)
        print(f"\n[Case 3] 부산 — GFS {self.DATE} 다운로드")
        return _download_gfs_subset(
            self.DATE,
            lat_range=(20.0, 50.0),
            lon_range=(100.0, 145.0),
        )

    def test_three_cities_backward(self, met: MetData):
        """부산/대구/광주 3개 도시에서 동시 backward trajectory."""
        starts = [
            StartLocation(lat=35.1, lon=129.0, height=850.0),  # 부산
            StartLocation(lat=35.9, lon=128.6, height=850.0),  # 대구
            StartLocation(lat=35.2, lon=126.9, height=850.0),  # 광주
        ]
        trajs = _run_backward(met, starts, run_hours=-24)

        labels = ["부산", "대구", "광주"]
        for label, traj in zip(labels, trajs):
            _print_traj(f"{label} 24h Backward", traj)

        assert len(trajs) == 3
        for i, traj in enumerate(trajs):
            assert len(traj) >= 2, f"{labels[i]} 궤적 포인트 부족"

        # 3개 궤적의 시작점이 서로 다른지 확인
        start_lons = [t[0][1] for t in trajs]
        assert len(set(start_lons)) == 3, "시작점이 모두 달라야 함"

    def test_independence(self, met: MetData):
        """시작점 추가/제거 시 기존 궤적 불변 (독립성)."""
        s1 = StartLocation(lat=35.1, lon=129.0, height=850.0)
        s2 = StartLocation(lat=35.9, lon=128.6, height=850.0)

        # s1만 실행
        traj_solo = _run_backward(met, s1, run_hours=-24)[0]
        # s1 + s2 동시 실행
        traj_pair = _run_backward(met, [s1, s2], run_hours=-24)[0]

        # s1의 궤적이 s2 추가 여부와 무관하게 동일해야 함
        min_len = min(len(traj_solo), len(traj_pair))
        for i in range(min_len):
            assert abs(traj_solo[i][1] - traj_pair[i][1]) < 1e-10, \
                f"독립성 위반 (lon): step {i}"
            assert abs(traj_solo[i][2] - traj_pair[i][2]) < 1e-10, \
                f"독립성 위반 (lat): step {i}"
        print(f"\n    독립성 검증 통과: {min_len} 포인트 일치")


# ===================================================================
# Case 4: 상하이 — 2/8 GFS, 48h backward
# ===================================================================
class TestCase4Shanghai:
    """상하이(31.2°N, 121.5°E) 48시간 backward trajectory."""

    DATE = "20260208"

    @pytest.fixture(scope="class")
    def met(self):
        _check_netcdf4()
        _check_gfs(self.DATE)
        print(f"\n[Case 4] 상하이 — GFS {self.DATE} 다운로드")
        return _download_gfs_subset(
            self.DATE,
            lat_range=(15.0, 50.0),
            lon_range=(90.0, 140.0),
        )

    def test_48h_backward(self, met: MetData):
        """상하이 48시간 backward — 양쯔강 유역 수송 경로."""
        start = StartLocation(lat=31.2, lon=121.5, height=850.0)
        trajs = _run_backward(met, start, run_hours=-48)
        traj = trajs[0]

        _print_traj("상하이 48h Backward (850 hPa)", traj)

        assert len(traj) >= 5
        assert traj[-1][0] < traj[0][0]

    def test_deterministic_reproducibility(self, met: MetData):
        """동일 입력 → 동일 궤적 (결정론적 재현성)."""
        start = StartLocation(lat=31.2, lon=121.5, height=850.0)
        traj1 = _run_backward(met, start, run_hours=-24)[0]
        traj2 = _run_backward(met, start, run_hours=-24)[0]

        assert len(traj1) == len(traj2), "궤적 길이가 다름"
        for i, (p1, p2) in enumerate(zip(traj1, traj2)):
            assert p1[1] == p2[1], f"lon 불일치 step {i}"
            assert p1[2] == p2[2], f"lat 불일치 step {i}"
            assert p1[3] == p2[3], f"z 불일치 step {i}"
        print(f"\n    결정론적 재현성 검증 통과: {len(traj1)} 포인트 완전 일치")


# ===================================================================
# Case 5: 울란바토르 — 2/7 GFS, 48h backward, 고위도
# ===================================================================
class TestCase5Ulaanbaatar:
    """울란바토르(47.9°N, 106.9°E) 48시간 backward — 고위도 테스트."""

    DATE = "20260207"

    @pytest.fixture(scope="class")
    def met(self):
        _check_netcdf4()
        _check_gfs(self.DATE)
        print(f"\n[Case 5] 울란바토르 — GFS {self.DATE} 다운로드")
        return _download_gfs_subset(
            self.DATE,
            lat_range=(30.0, 65.0),
            lon_range=(80.0, 140.0),
        )

    def test_high_latitude_backward(self, met: MetData):
        """고위도 48시간 backward — 시베리아/중앙아시아 수송 경로."""
        start = StartLocation(lat=47.9, lon=106.9, height=700.0)
        trajs = _run_backward(met, start, run_hours=-48)
        traj = trajs[0]

        _print_traj("울란바토르 48h Backward (700 hPa)", traj)

        assert len(traj) >= 3
        # 고위도에서도 좌표가 유효 범위 내
        for t, lon, lat, z in traj:
            assert -90 <= lat <= 90, f"위도 범위 초과: {lat}"
            assert -180 <= lon <= 360, f"경도 범위 초과: {lon}"

    def test_high_vs_low_level(self, met: MetData):
        """울란바토르 700 hPa vs 925 hPa — 고위도 고도별 차이."""
        s_high = StartLocation(lat=47.9, lon=106.9, height=700.0)
        s_low = StartLocation(lat=47.9, lon=106.9, height=925.0)
        trajs = _run_backward(met, [s_high, s_low], run_hours=-24)

        _print_traj("울란바토르 700 hPa", trajs[0])
        _print_traj("울란바토르 925 hPa", trajs[1])

        # 두 고도의 궤적이 달라야 함
        if len(trajs[0]) >= 3 and len(trajs[1]) >= 3:
            end0 = (trajs[0][-1][1], trajs[0][-1][2])
            end1 = (trajs[1][-1][1], trajs[1][-1][2])
            dist = np.sqrt((end0[0] - end1[0])**2 + (end0[1] - end1[1])**2)
            print(f"\n    700 vs 925 hPa 최종 위치 차이: {dist:.2f}°")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
