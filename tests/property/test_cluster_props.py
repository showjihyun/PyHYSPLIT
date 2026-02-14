"""Property-based tests for TrajectoryClusterAnalysis.

Properties 36-37 from the design document.
"""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings, strategies as st

from pyhysplit.cluster_analysis import TrajectoryClusterAnalysis


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

def _trajectory_strategy(n_traj: int, n_steps: int):
    """Build a list of *n_traj* trajectories each with *n_steps* points."""
    # lat in [-80, 80], lon in [-170, 170] to stay well inside bounds
    point = st.tuples(
        st.floats(min_value=-80, max_value=80, allow_nan=False, allow_infinity=False),
        st.floats(min_value=-170, max_value=170, allow_nan=False, allow_infinity=False),
    )
    single_traj = st.lists(point, min_size=n_steps, max_size=n_steps).map(
        lambda pts: np.array(pts, dtype=np.float64)
    )
    return st.lists(single_traj, min_size=n_traj, max_size=n_traj)


# ---------------------------------------------------------------------------
# Property 36: 거리 행렬 대칭성 (Distance Matrix Symmetry)
# ---------------------------------------------------------------------------

@given(trajs=_trajectory_strategy(n_traj=4, n_steps=5))
@settings(max_examples=100)
def test_property_36_distance_matrix_symmetry(trajs):
    """Feature: hysplit-trajectory-engine, Property 36: 거리 행렬 대칭성

    For any set of trajectories, compute_distance_matrix must return a
    symmetric matrix with zero diagonal.  The distance between identical
    trajectories must also be zero.

    **Validates: Requirements 18.1**
    """
    ca = TrajectoryClusterAnalysis(trajs)
    D = ca.compute_distance_matrix()

    # Symmetric
    np.testing.assert_allclose(D, D.T, atol=1e-10)

    # Diagonal is zero
    np.testing.assert_allclose(np.diag(D), 0.0, atol=1e-10)

    # Non-negative
    assert np.all(D >= -1e-10)

    # Self-distance: duplicate first trajectory and verify distance == 0
    dup = trajs + [trajs[0].copy()]
    ca2 = TrajectoryClusterAnalysis(dup)
    D2 = ca2.compute_distance_matrix()
    # Distance between original index 0 and the duplicate (last)
    np.testing.assert_allclose(D2[0, -1], 0.0, atol=1e-10)


# ---------------------------------------------------------------------------
# Property 37: 클러스터 평균 중심성 (Cluster Mean Centrality)
# ---------------------------------------------------------------------------

@given(trajs=_trajectory_strategy(n_traj=6, n_steps=4))
@settings(max_examples=100)
def test_property_37_cluster_mean_centrality(trajs):
    """Feature: hysplit-trajectory-engine, Property 37: 클러스터 평균 중심성

    For any clustering result, the mean trajectory of each cluster must
    equal the arithmetic mean of its member trajectories.

    **Validates: Requirements 18.4**
    """
    ca = TrajectoryClusterAnalysis(trajs)
    n_clusters = min(3, len(trajs))
    labels = ca.ward_clustering(n_clusters)
    means = ca.cluster_means(labels)

    idx = 0
    for k in sorted(np.unique(labels)):
        member_indices = [i for i in range(len(trajs)) if labels[i] == k]
        expected = np.mean([trajs[i] for i in member_indices], axis=0)
        np.testing.assert_allclose(means[idx], expected, atol=1e-10)
        idx += 1
