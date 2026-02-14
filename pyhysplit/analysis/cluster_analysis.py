"""Trajectory cluster analysis using Ward hierarchical clustering.

Implements SPVAR distance matrix computation, Ward clustering, TSV-based
optimal cluster number selection, and cluster mean trajectory calculation.

Requirements: 18.1, 18.2, 18.3, 18.4
"""

from __future__ import annotations

import numpy as np
from scipy.cluster.hierarchy import ward, fcluster
from scipy.spatial.distance import squareform


class TrajectoryClusterAnalysis:
    """Cluster analysis for multiple trajectories.

    Parameters
    ----------
    trajectories : list[np.ndarray]
        Each element is an ``(T, 2)`` array of ``(lat, lon)`` in degrees,
        where *T* is the number of time steps.  All trajectories must have
        the same length *T*.
    """

    def __init__(self, trajectories: list[np.ndarray]) -> None:
        if not trajectories:
            raise ValueError("At least one trajectory is required")
        self.trajectories = [np.asarray(t, dtype=np.float64) for t in trajectories]
        self._n = len(self.trajectories)
        self._T = self.trajectories[0].shape[0]
        # Validate uniform length
        for i, tr in enumerate(self.trajectories):
            if tr.shape[0] != self._T:
                raise ValueError(
                    f"Trajectory {i} has length {tr.shape[0]}, expected {self._T}"
                )

    # -- Distance matrix ----------------------------------------------------

    def compute_distance_matrix(self) -> np.ndarray:
        """Compute pairwise SPVAR distance matrix.

        SPVAR (spatial variance) between two trajectories *A* and *B* is
        defined as the mean squared great-circle distance across all time
        steps:

            D(A, B) = sqrt( (1/T) * Σ_t  d(A_t, B_t)² )

        Returns
        -------
        np.ndarray
            Symmetric ``(N, N)`` distance matrix with zero diagonal.
        """
        R = 6_371_000.0  # Earth radius in metres
        n = self._n
        dist = np.zeros((n, n), dtype=np.float64)

        for i in range(n):
            for j in range(i + 1, n):
                # Vectorised haversine over all T time steps
                lat1 = np.radians(self.trajectories[i][:, 0])
                lon1 = np.radians(self.trajectories[i][:, 1])
                lat2 = np.radians(self.trajectories[j][:, 0])
                lon2 = np.radians(self.trajectories[j][:, 1])

                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = (
                    np.sin(dlat / 2) ** 2
                    + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
                )
                gc = R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

                d = float(np.sqrt(np.mean(gc ** 2)))
                dist[i, j] = d
                dist[j, i] = d

        return dist


    # -- Clustering ---------------------------------------------------------

    def ward_clustering(self, n_clusters: int) -> np.ndarray:
        """Perform Ward hierarchical clustering.

        Parameters
        ----------
        n_clusters : int
            Desired number of clusters.

        Returns
        -------
        np.ndarray
            Integer cluster labels of shape ``(N,)``, values in ``[1, n_clusters]``.
        """
        dist = self.compute_distance_matrix()
        condensed = squareform(dist, checks=False)
        linkage = ward(condensed)
        labels = fcluster(linkage, t=n_clusters, criterion="maxclust")
        return labels

    # -- Optimal cluster number ---------------------------------------------

    def optimal_clusters(self, max_k: int = 10) -> int:
        """Determine optimal cluster count via TSV change rate.

        Computes total spatial variance (TSV) for *k* = 1 … *max_k* and
        returns the *k* where the relative increase in TSV from merging
        (going from *k* to *k-1*) is largest.

        Returns
        -------
        int
            Suggested number of clusters (≥ 2).
        """
        max_k = min(max_k, self._n)
        if max_k < 2:
            return 1

        dist = self.compute_distance_matrix()
        condensed = squareform(dist, checks=False)
        linkage = ward(condensed)

        tsv_values: list[float] = []
        for k in range(1, max_k + 1):
            labels = fcluster(linkage, t=k, criterion="maxclust")
            tsv = self._compute_tsv(labels)
            tsv_values.append(tsv)

        # Find largest TSV jump (k -> k-1 merge)
        best_k = 2
        max_delta = 0.0
        for i in range(1, len(tsv_values)):
            # tsv_values[i-1] is TSV for k=i, tsv_values[i] is TSV for k=i+1
            delta = tsv_values[i - 1] - tsv_values[i]
            if delta > max_delta:
                max_delta = delta
                best_k = i + 1  # the k value *before* the big jump

        return best_k

    def _compute_tsv(self, labels: np.ndarray) -> float:
        """Total spatial variance for a given clustering."""
        tsv = 0.0
        for k in np.unique(labels):
            members = [self.trajectories[i] for i in range(self._n) if labels[i] == k]
            if len(members) < 2:
                continue
            mean_traj = np.mean(members, axis=0)
            for m in members:
                diff = m - mean_traj
                tsv += float(np.sum(diff ** 2))
        return tsv

    # -- Cluster means ------------------------------------------------------

    def cluster_means(self, labels: np.ndarray) -> list[np.ndarray]:
        """Compute mean trajectory for each cluster.

        Parameters
        ----------
        labels : np.ndarray
            Cluster labels as returned by :meth:`ward_clustering`.

        Returns
        -------
        list[np.ndarray]
            One ``(T, 2)`` array per cluster, ordered by cluster label.
        """
        means: list[np.ndarray] = []
        for k in sorted(np.unique(labels)):
            members = [self.trajectories[i] for i in range(self._n) if labels[i] == k]
            means.append(np.mean(members, axis=0))
        return means
