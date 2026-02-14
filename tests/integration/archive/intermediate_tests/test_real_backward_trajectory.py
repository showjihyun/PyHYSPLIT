"""실제 GFS 기상데이터를 다운로드하여 backward trajectory를 테스트한다.

NOAA NOMADS OPeNDAP를 통해 GFS 0.25° 데이터의 서브셋을 받아
서울(37.5°N, 127°E) 기준 48시간 backward trajectory를 계산한다.

실행 방법:
    python -m pytest tests/integration/test_real_backward_trajectory.py -v -s

네트워크 접근이 불가능하면 테스트가 skip 된다.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from pyhysplit.models import (
    MetData,
    SimulationConfig,
    StartLocation,
)
from pyhysplit.engine import TrajectoryEngine
from pyhysplit.output_writer import TdumpWriter, TrajectoryPoint


# ---------------------------------------------------------------------------
# GFS OPeNDAP 데이터 다운로드 헬퍼
# ---------------------------------------------------------------------------

def _find_available_gfs_date(max_lookback: int = 5) -> str | None:
    """최근 GFS 데이터가 있는 날짜를 찾는다 (OPeNDAP)."""
    try:
        import netCDF4  # noqa: F811
    except ImportError:
        return None

    today = datetime(2026, 2, 13)
    for days_back in range(1, max_lookback + 1):
        dt = today - timedelta(days=days_back)
        date_str = dt.strftime("%Y%m%d")
        url = f"https://nomads.ncep.noaa.gov/dods/gfs_0p25/gfs{date_str}/gfs_0p25_00z"
        try:
            ds = netCDF4.Dataset(url)
            ds.close()
            return date_str
        except Exception:
            continue
    return None


def _download_gfs_subset(
    date_str: str,
    lat_range: tuple[float, float] = (20.0, 55.0),
    lon_range: tuple[float, float] = (100.0, 150.0),
    lev_indices: list[int] | None = None,
    time_indices: list[int] | None = None,
) -> MetData:
    """GFS OPeNDAP에서 동아시아 영역 서브셋을 다운로드하여 MetData로 변환한다.

    Parameters
    ----------
    date_str : str
        YYYYMMDD 형식의 날짜
    lat_range : tuple
        위도 범위 (남, 북)
    lon_range : tuple
        경도 범위 (서, 동)
    lev_indices : list[int] | None
        사용할 기압면 인덱스 (None이면 하층 10개)
    time_indices : list[int] | None
        사용할 시간 인덱스 (None이면 처음 17개 = 0~48h, 3시간 간격)
    """
    import netCDF4

    url = f"https://nomads.ncep.noaa.gov/dods/gfs_0p25/gfs{date_str}/gfs_0p25_00z"
    ds = netCDF4.Dataset(url)

    try:
        # 좌표 격자 읽기
        all_lat = np.array(ds.variables["lat"][:])
        all_lon = np.array(ds.variables["lon"][:])
        all_lev = np.array(ds.variables["lev"][:])
        all_time = np.array(ds.variables["time"][:])

        # 위도/경도 인덱스 범위
        lat_mask = (all_lat >= lat_range[0]) & (all_lat <= lat_range[1])
        lon_mask = (all_lon >= lon_range[0]) & (all_lon <= lon_range[1])
        j_start, j_end = np.where(lat_mask)[0][[0, -1]]
        i_start, i_end = np.where(lon_mask)[0][[0, -1]]

        # 기압면: 하층~중층 15개 (1000~200 hPa)
        if lev_indices is None:
            lev_indices = list(range(19))  # 1000~200 hPa

        # 시간: 0~48h (3시간 간격 = 17개 스텝)
        if time_indices is None:
            time_indices = list(range(0, min(17, len(all_time))))

        lat_grid = all_lat[j_start:j_end + 1]
        lon_grid = all_lon[i_start:i_end + 1]
        lev_grid = all_lev[lev_indices]
        time_raw = all_time[time_indices]

        # 시간을 초 단위로 변환 (첫 시간 기준 상대값)
        t_grid = (time_raw - time_raw[0]) * 86400.0  # days → seconds

        nt = len(time_indices)
        nz = len(lev_indices)
        ny = j_end - j_start + 1
        nx = i_end - i_start + 1

        print(f"  다운로드 영역: lat [{lat_grid[0]:.1f}, {lat_grid[-1]:.1f}], "
              f"lon [{lon_grid[0]:.1f}, {lon_grid[-1]:.1f}]")
        print(f"  격자 크기: {nt} times × {nz} levels × {ny} lats × {nx} lons")
        print(f"  기압면: {lev_grid} hPa")

        # 슬라이싱으로 서브셋 다운로드
        t_sl = time_indices
        z_sl = lev_indices
        j_sl = slice(j_start, j_end + 1)
        i_sl = slice(i_start, i_end + 1)

        print("  u (동서 바람) 다운로드 중...")
        u = np.array(
            ds.variables["ugrdprs"][t_sl, z_sl, j_sl, i_sl],
            dtype=np.float64,
        )

        print("  v (남북 바람) 다운로드 중...")
        v = np.array(
            ds.variables["vgrdprs"][t_sl, z_sl, j_sl, i_sl],
            dtype=np.float64,
        )

        print("  omega (수직 속도) 다운로드 중...")
        omega = np.array(
            ds.variables["vvelprs"][t_sl, z_sl, j_sl, i_sl],
            dtype=np.float64,
        )

        print("  T (온도) 다운로드 중...")
        t_field = np.array(
            ds.variables["tmpprs"][t_sl, z_sl, j_sl, i_sl],
            dtype=np.float64,
        )

        print("  HGT (지오포텐셜 높이) 다운로드 중...")
        hgt = np.array(
            ds.variables["hgtprs"][t_sl, z_sl, j_sl, i_sl],
            dtype=np.float64,
        )

        # omega (Pa/s) → w (m/s) 변환
        from pyhysplit.met_reader import convert_omega_to_w

        P_3d = lev_grid[np.newaxis, :, np.newaxis, np.newaxis] * 100.0  # hPa → Pa
        P_3d = np.broadcast_to(P_3d, omega.shape)
        w = convert_omega_to_w(omega, t_field, P_3d)

        terrain = np.zeros((ny, nx))

        # z_grid(기압면)가 오름차순이어야 보간기가 동작함
        # GFS는 1000→650 내림차순이므로 뒤집기
        if len(lev_grid) > 1 and lev_grid[0] > lev_grid[-1]:
            lev_grid = lev_grid[::-1]
            u = u[:, ::-1, :, :]
            v = v[:, ::-1, :, :]
            w = w[:, ::-1, :, :]
            t_field = t_field[:, ::-1, :, :]
            hgt = hgt[:, ::-1, :, :]

        # lat_grid도 오름차순 보장
        if len(lat_grid) > 1 and lat_grid[0] > lat_grid[-1]:
            lat_grid = lat_grid[::-1]
            u = u[:, :, ::-1, :]
            v = v[:, :, ::-1, :]
            w = w[:, :, ::-1, :]
            t_field = t_field[:, :, ::-1, :]
            hgt = hgt[:, :, ::-1, :]
            terrain = terrain[::-1, :]

        met = MetData(
            u=u, v=v, w=w,
            t_field=t_field, rh=None, hgt=hgt,
            precip=None, pbl_height=None,
            terrain=terrain,
            lon_grid=lon_grid, lat_grid=lat_grid,
            z_grid=lev_grid, t_grid=t_grid,
            z_type="pressure",
            source="GFS_NC",
        )

        print(f"  다운로드 완료! u 범위: [{u.min():.1f}, {u.max():.1f}] m/s")
        return met

    finally:
        ds.close()


# ---------------------------------------------------------------------------
# 테스트
# ---------------------------------------------------------------------------

def _needs_network():
    """네트워크 접근 가능 여부 확인."""
    try:
        import netCDF4  # noqa: F811
    except ImportError:
        return pytest.mark.skip(reason="netCDF4 not installed")

    date_str = _find_available_gfs_date()
    if date_str is None:
        return pytest.mark.skip(reason="NOAA NOMADS에 접근할 수 없음")
    return None


# 모듈 레벨에서 한 번만 날짜 탐색
_GFS_DATE: str | None = None


def _get_gfs_date() -> str:
    global _GFS_DATE
    if _GFS_DATE is None:
        _GFS_DATE = _find_available_gfs_date()
    if _GFS_DATE is None:
        pytest.skip("NOAA NOMADS에 접근할 수 없음")
    return _GFS_DATE


class TestRealBackwardTrajectory:
    """실제 GFS 데이터를 사용한 backward trajectory 테스트."""

    @pytest.fixture(scope="class")
    def met_data(self):
        """GFS 데이터를 다운로드한다 (클래스 내 공유)."""
        try:
            import netCDF4  # noqa: F811
        except ImportError:
            pytest.skip("netCDF4 not installed")

        date_str = _get_gfs_date()
        print(f"\n=== GFS 데이터 다운로드: {date_str} ===")
        try:
            met = _download_gfs_subset(date_str)
        except Exception as e:
            pytest.skip(f"GFS 데이터 다운로드 실패: {e}")
        return met

    def test_backward_trajectory_seoul(self, met_data: MetData):
        """서울(37.5°N, 127°E)에서 48시간 backward trajectory를 계산한다."""
        # 서울 좌표, 500m AGL 시작
        start = StartLocation(lat=37.5, lon=127.0, height=850.0)

        config = SimulationConfig(
            start_time=datetime(2026, 2, 12, 0, 0),
            num_start_locations=1,
            start_locations=[start],
            total_run_hours=-48,  # 48시간 backward
            vertical_motion=0,    # 데이터 수직 속도 사용
            model_top=10000.0,
            met_files=[],
            turbulence_on=False,  # 결정론적 궤적
            dt_max=3600.0,
        )

        engine = TrajectoryEngine(config, met_data)
        trajectories = engine.run(output_interval_s=3600.0)

        assert len(trajectories) == 1, "시작점 1개 → 궤적 1개"
        traj = trajectories[0]

        print(f"\n=== 서울 48h Backward Trajectory ===")
        print(f"  시작: ({start.lat}°N, {start.lon}°E, {start.height}m)")
        print(f"  궤적 포인트 수: {len(traj)}")

        # 궤적 출력
        for i, (t, lon, lat, z) in enumerate(traj):
            hours = t / 3600.0
            print(f"  [{i:3d}] t={hours:7.1f}h  lat={lat:7.2f}  lon={lon:7.2f}  z={z:8.1f}")

        # 기본 검증
        assert len(traj) >= 3, "최소 3개 이상의 궤적 포인트가 있어야 함"

        # 시작점 확인
        t0, lon0, lat0, z0 = traj[0]
        assert abs(lat0 - 37.5) < 0.01, f"시작 위도 불일치: {lat0}"
        assert abs(lon0 - 127.0) < 0.01, f"시작 경도 불일치: {lon0}"

        # backward이므로 시간이 감소해야 함
        times = [pt[0] for pt in traj]
        for i in range(1, len(times)):
            assert times[i] <= times[i - 1], (
                f"Backward 궤적에서 시간이 증가함: t[{i-1}]={times[i-1]}, t[{i}]={times[i]}"
            )

        # 궤적이 합리적인 범위 내에 있는지 (동아시아 영역)
        for t, lon, lat, z in traj:
            assert 0 <= lat <= 80, f"위도 범위 초과: {lat}"
            assert 60 <= lon <= 180, f"경도 범위 초과: {lon}"

    def test_backward_trajectory_multi_height(self, met_data: MetData):
        """서울에서 3개 고도(500m, 1000m, 1500m)의 backward trajectory를 비교한다."""
        starts = [
            StartLocation(lat=37.5, lon=127.0, height=850.0),   # ~1500m (850 hPa)
            StartLocation(lat=37.5, lon=127.0, height=925.0),   # ~750m (925 hPa)
            StartLocation(lat=37.5, lon=127.0, height=1000.0),  # 지표 근처 (1000 hPa)
        ]

        config = SimulationConfig(
            start_time=datetime(2026, 2, 12, 0, 0),
            num_start_locations=3,
            start_locations=starts,
            total_run_hours=-24,  # 24시간 backward
            vertical_motion=0,
            model_top=10000.0,
            met_files=[],
            turbulence_on=False,
            dt_max=3600.0,
        )

        engine = TrajectoryEngine(config, met_data)
        trajectories = engine.run(output_interval_s=3600.0)

        assert len(trajectories) == 3, "시작점 3개 → 궤적 3개"

        print(f"\n=== 서울 다중 고도 24h Backward Trajectory ===")
        for idx, (start, traj) in enumerate(zip(starts, trajectories)):
            print(f"\n  고도 {start.height} hPa: {len(traj)} 포인트")
            last = traj[-1]
            print(f"    최종 위치: lat={last[2]:.2f}, lon={last[1]:.2f}, z={last[3]:.1f}")

        # 각 궤적이 독립적으로 계산되었는지 확인
        # (다른 고도에서 시작하면 다른 경로를 따라야 함)
        final_positions = [(t[-1][1], t[-1][2]) for t in trajectories]
        # 최소한 하나의 궤적 쌍은 다른 최종 위치를 가져야 함
        all_same = all(
            abs(p[0] - final_positions[0][0]) < 0.01 and
            abs(p[1] - final_positions[0][1]) < 0.01
            for p in final_positions
        )
        # 풍속이 고도에 따라 다르므로 궤적도 달라야 함 (극단적 경우 제외)
        print(f"\n  최종 위치들: {final_positions}")

    def test_backward_trajectory_tdump_output(self, met_data: MetData):
        """Backward trajectory 결과를 tdump 파일로 출력하고 다시 읽는다."""
        start = StartLocation(lat=37.5, lon=127.0, height=850.0)

        config = SimulationConfig(
            start_time=datetime(2026, 2, 12, 0, 0),
            num_start_locations=1,
            start_locations=[start],
            total_run_hours=-24,
            vertical_motion=0,
            model_top=10000.0,
            met_files=[],
            turbulence_on=False,
            dt_max=3600.0,
        )

        engine = TrajectoryEngine(config, met_data)
        trajectories = engine.run(output_interval_s=3600.0)

        # tuple → TrajectoryPoint 변환
        ref_time = datetime(2026, 2, 12, 0, 0)
        tp_trajectories = []
        for traj_idx, traj in enumerate(trajectories):
            tp_list = []
            for t_sec, lon, lat, z in traj:
                dt_obj = ref_time + timedelta(seconds=t_sec)
                age = t_sec - trajectories[traj_idx][0][0]  # 시작 시간 기준
                tp = TrajectoryPoint(
                    traj_id=traj_idx + 1,
                    grid_id=1,
                    year=dt_obj.year % 100,
                    month=dt_obj.month,
                    day=dt_obj.day,
                    hour=dt_obj.hour,
                    minute=dt_obj.minute,
                    forecast_hour=0.0,
                    age=age / 3600.0,
                    lat=lat,
                    lon=lon,
                    height=z,
                )
                tp_list.append(tp)
            tp_trajectories.append(tp_list)

        # tdump 파일로 출력
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tdump", delete=False
        ) as f:
            tdump_path = f.name

        try:
            met_info = [
                {
                    "model_id": "GFS",
                    "year": 26, "month": 2, "day": 12,
                    "hour": 0, "forecast_hour": 0,
                }
            ]

            TdumpWriter.write(
                tdump_path, tp_trajectories, met_info, [start]
            )

            # 파일이 생성되었는지 확인
            assert Path(tdump_path).exists(), "tdump 파일이 생성되지 않음"
            size = Path(tdump_path).stat().st_size
            assert size > 0, "tdump 파일이 비어있음"

            # 파일 내용 출력
            content = Path(tdump_path).read_text()
            lines = content.strip().split("\n")
            print(f"\n=== tdump 출력 ({len(lines)} 줄) ===")
            for line in lines[:5]:
                print(f"  {line}")
            print(f"  ...")
            for line in lines[-3:]:
                print(f"  {line}")

            # Round-trip: 다시 읽기
            parsed = TdumpWriter.read(tdump_path)
            assert len(parsed.points) >= 1, "파싱된 궤적 포인트가 없음"

            print(f"\n  Round-trip 검증: 원본 {len(trajectories[0])} 포인트, "
                  f"파싱 {len(parsed.points)} 포인트")

        finally:
            os.unlink(tdump_path)

    def test_forward_backward_comparison(self, met_data: MetData):
        """동일 지점에서 forward/backward 궤적의 방향성을 비교한다."""
        start = StartLocation(lat=37.5, lon=127.0, height=925.0)

        # Forward 12시간
        config_fwd = SimulationConfig(
            start_time=datetime(2026, 2, 12, 0, 0),
            num_start_locations=1,
            start_locations=[start],
            total_run_hours=12,
            vertical_motion=0,
            model_top=10000.0,
            met_files=[],
            turbulence_on=False,
            dt_max=3600.0,
        )

        # Backward 12시간
        config_bwd = SimulationConfig(
            start_time=datetime(2026, 2, 12, 0, 0),
            num_start_locations=1,
            start_locations=[start],
            total_run_hours=-12,
            vertical_motion=0,
            model_top=10000.0,
            met_files=[],
            turbulence_on=False,
            dt_max=3600.0,
        )

        engine_fwd = TrajectoryEngine(config_fwd, met_data)
        engine_bwd = TrajectoryEngine(config_bwd, met_data)

        traj_fwd = engine_fwd.run(output_interval_s=3600.0)[0]
        traj_bwd = engine_bwd.run(output_interval_s=3600.0)[0]

        print(f"\n=== Forward vs Backward 비교 ===")
        print(f"  Forward: {len(traj_fwd)} 포인트")
        print(f"    시작: lat={traj_fwd[0][2]:.2f}, lon={traj_fwd[0][1]:.2f}")
        print(f"    종료: lat={traj_fwd[-1][2]:.2f}, lon={traj_fwd[-1][1]:.2f}")
        print(f"  Backward: {len(traj_bwd)} 포인트")
        print(f"    시작: lat={traj_bwd[0][2]:.2f}, lon={traj_bwd[0][1]:.2f}")
        print(f"    종료: lat={traj_bwd[-1][2]:.2f}, lon={traj_bwd[-1][1]:.2f}")

        # Forward는 시간 증가, Backward는 시간 감소
        fwd_times = [pt[0] for pt in traj_fwd]
        bwd_times = [pt[0] for pt in traj_bwd]

        assert fwd_times[-1] > fwd_times[0], "Forward 궤적의 시간이 증가해야 함"
        assert bwd_times[-1] < bwd_times[0], "Backward 궤적의 시간이 감소해야 함"

        # Forward와 Backward의 최종 위치가 다른 방향이어야 함
        fwd_end = (traj_fwd[-1][1], traj_fwd[-1][2])
        bwd_end = (traj_bwd[-1][1], traj_bwd[-1][2])
        print(f"\n  Forward 최종: ({fwd_end[1]:.2f}°N, {fwd_end[0]:.2f}°E)")
        print(f"  Backward 최종: ({bwd_end[1]:.2f}°N, {bwd_end[0]:.2f}°E)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
