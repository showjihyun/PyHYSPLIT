"""Verification module for comparing Python trajectories with HYSPLIT output.

Provides geodesic distance error calculation, summary statistics (mean, max,
RMSE), and optional map visualisation using matplotlib/cartopy.

Requirements: 16.1, 16.2, 16.3, 16.4, 16.5
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from pyhysplit.data.output_writer import TdumpWriter, TdumpData, TrajectoryPoint


# ---------------------------------------------------------------------------
# Geodesic helpers
# ---------------------------------------------------------------------------

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in metres between two points (degrees)."""
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------

class Verifier:
    """Compare Python trajectory results against HYSPLIT tdump output.

    Typical workflow::

        v = Verifier()
        hysplit = v.load_tdump("hysplit_tdump.txt")
        stats = v.compare(python_traj, hysplit)
        print(v.summary_stats())
    """

    def __init__(self) -> None:
        self.errors: list[float] = []

    # -- I/O ----------------------------------------------------------------

    @staticmethod
    def load_tdump(filepath: str) -> list[dict[str, Any]]:
        """Load an HYSPLIT tdump file and return a list of point dicts.

        Each dict has keys: ``traj_id``, ``age``, ``lat``, ``lon``, ``height``.
        """
        data: TdumpData = TdumpWriter.read(filepath)
        result: list[dict[str, Any]] = []
        for pt in data.points:
            result.append({
                "traj_id": pt.traj_id,
                "age": pt.age,
                "lat": pt.lat,
                "lon": pt.lon,
                "height": pt.height,
            })
        return result


    # -- Comparison ----------------------------------------------------------

    def compare(
        self,
        python_traj: list[tuple[float, float, float]],
        hysplit_traj: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Compute per-point geodesic distance errors.

        Parameters
        ----------
        python_traj : list[tuple[float, float, float]]
            Python trajectory as ``(lat, lon, height)`` tuples, one per time
            step, ordered by increasing age.
        hysplit_traj : list[dict]
            HYSPLIT trajectory points (as returned by :meth:`load_tdump`),
            filtered to a single ``traj_id`` and ordered by age.

        Returns
        -------
        dict
            ``"distances"`` – list of per-point horizontal errors (m),
            ``"vertical_errors"`` – list of per-point vertical errors (m),
            ``"n_points"`` – number of compared points.
        """
        n = min(len(python_traj), len(hysplit_traj))
        distances: list[float] = []
        vertical_errors: list[float] = []

        for i in range(n):
            py_lat, py_lon, py_z = python_traj[i]
            hy = hysplit_traj[i]
            d = _haversine(py_lat, py_lon, hy["lat"], hy["lon"])
            distances.append(d)
            vertical_errors.append(abs(py_z - hy["height"]))

        self.errors.extend(distances)

        return {
            "distances": distances,
            "vertical_errors": vertical_errors,
            "n_points": n,
        }

    # -- Statistics ----------------------------------------------------------

    def summary_stats(self) -> dict[str, float]:
        """Return mean, max, and RMSE of accumulated horizontal errors (m)."""
        if not self.errors:
            return {"mean": 0.0, "max": 0.0, "rmse": 0.0}
        arr = np.asarray(self.errors, dtype=np.float64)
        return {
            "mean": float(np.mean(arr)),
            "max": float(np.max(arr)),
            "rmse": float(np.sqrt(np.mean(arr ** 2))),
        }

    # -- Visualisation -------------------------------------------------------

    def plot_comparison(
        self,
        python_traj: list[tuple[float, float, float]],
        hysplit_traj: list[dict[str, Any]],
        output_path: str | None = None,
    ) -> None:
        """Plot Python and HYSPLIT trajectories on a map.

        Requires ``matplotlib`` and optionally ``cartopy`` for map projection.
        If *output_path* is given the figure is saved; otherwise ``plt.show()``
        is called.
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:  # pragma: no cover
            raise ImportError("matplotlib is required for plot_comparison")

        fig, ax = plt.subplots(figsize=(10, 7))

        # Try cartopy for map projection
        try:
            import cartopy.crs as ccrs
            import cartopy.feature as cfeature

            ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
            ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
            ax.add_feature(cfeature.BORDERS, linewidth=0.3)
            ax.gridlines(draw_labels=True)
            use_cartopy = True
        except ImportError:
            use_cartopy = False

        # Python trajectory
        py_lats = [p[0] for p in python_traj]
        py_lons = [p[1] for p in python_traj]
        ax.plot(py_lons, py_lats, "b-o", markersize=3, label="Python")

        # HYSPLIT trajectory
        hy_lats = [p["lat"] for p in hysplit_traj]
        hy_lons = [p["lon"] for p in hysplit_traj]
        ax.plot(hy_lons, hy_lats, "r--s", markersize=3, label="HYSPLIT")

        # Per-point error annotations
        n = min(len(python_traj), len(hysplit_traj))
        for i in range(n):
            d = _haversine(py_lats[i], py_lons[i], hy_lats[i], hy_lons[i])
            mid_lon = (py_lons[i] + hy_lons[i]) / 2
            mid_lat = (py_lats[i] + hy_lats[i]) / 2
            if d > 1000:  # only annotate errors > 1 km
                ax.annotate(
                    f"{d / 1000:.1f}km",
                    (mid_lon, mid_lat),
                    fontsize=6,
                    color="gray",
                )

        ax.legend()
        ax.set_title("Trajectory Comparison")

        if output_path:
            fig.savefig(output_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
        else:
            plt.show()
