"""Property-based tests for the Output Writer module.

Property 28 from the HYSPLIT Trajectory Engine design document.
"""

from __future__ import annotations

from hypothesis import given, settings, assume, strategies as st

from pyhysplit.models import StartLocation
from pyhysplit.output_writer import (
    TdumpWriter,
    TrajectoryPoint,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

valid_lat = st.floats(min_value=-89.0, max_value=89.0,
                      allow_nan=False, allow_infinity=False)
valid_lon = st.floats(min_value=-179.0, max_value=179.0,
                      allow_nan=False, allow_infinity=False)
valid_height = st.floats(min_value=0.0, max_value=25000.0,
                         allow_nan=False, allow_infinity=False)

# Diagnostic variable values — kept within a range that formats cleanly
diag_value = st.floats(min_value=-9999.0, max_value=99999.0,
                       allow_nan=False, allow_infinity=False)

diag_var_names_st = st.just(["PRESSURE", "THETA", "AIR_TEMP"])

start_location_st = st.builds(
    StartLocation,
    lat=valid_lat,
    lon=valid_lon,
    height=valid_height,
)

met_info_st = st.just([{
    "model_id": "GDAS1",
    "year": 20,
    "month": 1,
    "day": 15,
    "hour": 0,
    "forecast_hour": 0,
}])


def trajectory_point_st(traj_id: int = 1):
    """Strategy for a single TrajectoryPoint with diagnostic variables."""
    return st.builds(
        TrajectoryPoint,
        traj_id=st.just(traj_id),
        grid_id=st.just(1),
        year=st.integers(min_value=0, max_value=99),
        month=st.integers(min_value=1, max_value=12),
        day=st.integers(min_value=1, max_value=28),
        hour=st.integers(min_value=0, max_value=23),
        minute=st.integers(min_value=0, max_value=59),
        forecast_hour=st.floats(min_value=0.0, max_value=240.0,
                                allow_nan=False, allow_infinity=False),
        age=st.floats(min_value=0.0, max_value=8760.0,
                      allow_nan=False, allow_infinity=False),
        lat=valid_lat,
        lon=valid_lon,
        height=valid_height,
        diag_vars=st.fixed_dictionaries({
            "PRESSURE": diag_value,
            "THETA": diag_value,
            "AIR_TEMP": diag_value,
        }),
    )


# Strategy for a single trajectory (list of points)
single_trajectory_st = st.lists(
    trajectory_point_st(traj_id=1),
    min_size=1,
    max_size=5,
)


# ---------------------------------------------------------------------------
# Property 28: tdump Round Trip
# Validates: Requirements 12.1, 12.4, 12.5
# ---------------------------------------------------------------------------

@given(
    traj_points=single_trajectory_st,
    start_loc=start_location_st,
    met_info=met_info_st,
    diag_names=diag_var_names_st,
)
@settings(max_examples=100)
def test_property_28_tdump_round_trip(traj_points, start_loc, met_info, diag_names):
    """**Validates: Requirements 12.1, 12.4, 12.5**

    Feature: hysplit-trajectory-engine, Property 28: tdump Round Trip
    write_string → read_string must recover the original trajectory data
    including diagnostic variables.
    """
    trajectories = [traj_points]
    start_locations = [start_loc]

    # Write to string
    text = TdumpWriter.write_string(
        trajectories=trajectories,
        met_info=met_info,
        start_locations=start_locations,
        diag_var_names=diag_names,
    )

    # Read back
    result = TdumpWriter.read_string(text)

    # --- Verify met grids ---
    assert len(result.met_grids) == len(met_info)
    for orig, parsed in zip(met_info, result.met_grids):
        assert parsed["model_id"] == orig["model_id"]
        assert parsed["year"] == orig["year"]
        assert parsed["month"] == orig["month"]
        assert parsed["day"] == orig["day"]
        assert parsed["hour"] == orig["hour"]
        assert parsed["forecast_hour"] == orig["forecast_hour"]

    # --- Verify start info ---
    assert len(result.start_info) == 1
    si = result.start_info[0]
    assert abs(si["lat"] - start_loc.lat) < 0.01
    assert abs(si["lon"] - start_loc.lon) < 0.01
    assert abs(si["height"] - start_loc.height) < 0.15

    # --- Verify diagnostic variable names ---
    assert result.diag_var_names == diag_names

    # --- Verify trajectory points ---
    assert len(result.points) == len(traj_points)
    for orig_pt, parsed_pt in zip(traj_points, result.points):
        assert parsed_pt.traj_id == orig_pt.traj_id
        assert parsed_pt.grid_id == orig_pt.grid_id
        assert parsed_pt.year == orig_pt.year
        assert parsed_pt.month == orig_pt.month
        assert parsed_pt.day == orig_pt.day
        assert parsed_pt.hour == orig_pt.hour
        assert parsed_pt.minute == orig_pt.minute

        # Floating-point values go through fixed-width formatting,
        # so we compare with the precision of the format string (%9.1f etc.)
        assert abs(parsed_pt.forecast_hour - orig_pt.forecast_hour) < 0.15
        assert abs(parsed_pt.age - orig_pt.age) < 0.15
        assert abs(parsed_pt.lat - orig_pt.lat) < 0.0015
        assert abs(parsed_pt.lon - orig_pt.lon) < 0.0015
        assert abs(parsed_pt.height - orig_pt.height) < 0.15

        # Diagnostic variables
        for vn in diag_names:
            orig_val = orig_pt.diag_vars.get(vn, 0.0)
            parsed_val = parsed_pt.diag_vars.get(vn, 0.0)
            assert abs(parsed_val - orig_val) < 0.15, (
                f"Diag var {vn}: expected ~{orig_val}, got {parsed_val}"
            )
