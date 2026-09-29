from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import numpy as np


MAX_SIMILAR_PAPERS = 5
SUBTOPIC_MIN_SIZE = 8
# Below this size UMAP neighbourhoods are too unstable for density clustering.
DENSITY_MIN_N = 30
UMAP_CLUSTER_DIMS = 10
PILLAR_Z = 0.75
NICHE_Z = -0.75
HEATMAP_RESOLUTION = 32
EDGE_PERCENTILE = 80.0
# Mean pairwise cosine after centering; real topics measured 0.11+, chance groupings ~0.03.
MIN_CENTERED_COHESION = 0.07


@dataclass(frozen=True, slots=True)
class NodeMetrics:
    centrality: float
    influence: float
    role: str
    z_score: float


def center_embeddings(matrix: np.ndarray) -> np.ndarray:
    """Remove the direction every paper shares so topical differences dominate cosine."""
    if len(matrix) < 3:
        return matrix
    centered = matrix - matrix.mean(axis=0, keepdims=True)
    norms = np.linalg.norm(centered, axis=1, keepdims=True)
    norms[norms < 1e-9] = 1.0
    return (centered / norms).astype(np.float32, copy=False)


def cosine_distances(matrix: np.ndarray) -> np.ndarray:
    distances = np.clip(1.0 - matrix @ matrix.T, 0.0, 2.0)
    np.fill_diagonal(distances, 0.0)
    return distances


def adaptive_min_cluster_size(count: int) -> int:
    if count <= 6:
        return max(2, count)
    return int(max(3, min(10, round(count**0.45))))


def agglomerative_labels(matrix: np.ndarray, target_k: int | None = None) -> np.ndarray:
    """Average-linkage cosine clustering with silhouette-selected k."""
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import silhouette_score

    count = len(matrix)
    if count < 3:
        return np.zeros(count, dtype=int)
    distances = cosine_distances(matrix)

    def fit(k: int) -> np.ndarray:
        return np.asarray(
            AgglomerativeClustering(
                n_clusters=k, metric="precomputed", linkage="average"
            ).fit_predict(distances),
            dtype=int,
        )

    max_k = max(2, min(10, count // 2))
    if target_k is not None:
        return fit(max(2, min(int(target_k), max_k, count - 1)))

    best_labels = np.zeros(count, dtype=int)
    best_score = -1.0
    for k in range(2, max_k + 1):
        labels = fit(k)
        sizes = np.bincount(labels)
        if len(sizes) < 2:
            continue
        score = float(silhouette_score(distances, labels, metric="precomputed"))
        # Penalise solutions that are mostly singletons; they read as noise, not topics.
        singleton_share = float((sizes == 1).sum()) / len(sizes)
        score -= 0.15 * singleton_share
        if score > best_score:
            best_score = score
            best_labels = labels
    return best_labels


def reduce_for_clustering(matrix: np.ndarray, random_state: int = 42) -> np.ndarray:
    count, dims = matrix.shape
    if count < 4 or dims <= UMAP_CLUSTER_DIMS:
        return matrix
    import umap

    components = max(2, min(UMAP_CLUSTER_DIMS, count - 2, dims))
    reducer = umap.UMAP(
        n_components=components,
        n_neighbors=max(2, min(15, count - 1)),
        metric="cosine",
        min_dist=0.0,
        random_state=random_state,
        n_jobs=1,
    )
    return np.asarray(reducer.fit_transform(matrix), dtype=np.float32)


def hdbscan_labels(reduced: np.ndarray, min_cluster_size: int) -> np.ndarray:
    import hdbscan

    size = max(2, min(int(min_cluster_size), len(reduced)))
    labels = hdbscan.HDBSCAN(
        min_cluster_size=size,
        min_samples=max(1, min(3, size - 1)),
        metric="euclidean",
        cluster_selection_method="leaf" if len(reduced) < 150 else "eom",
    ).fit_predict(reduced)
    return np.asarray(labels, dtype=int)


def cluster_quality(labels: np.ndarray) -> tuple[int, float]:
    clustered = [int(label) for label in labels if int(label) >= 0]
    n_clusters = len(set(clustered))
    noise_frac = 1.0 - (len(clustered) / max(len(labels), 1))
    return n_clusters, noise_frac


def _relabel_dense(labels: np.ndarray) -> np.ndarray:
    mapping: dict[int, int] = {}
    output = np.array(labels, dtype=int, copy=True)
    for index, label in enumerate(labels):
        value = int(label)
        if value < 0:
            continue
        if value not in mapping:
            mapping[value] = len(mapping)
        output[index] = mapping[value]
    return output


def soft_assign_noise(labels: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Attach outliers to the nearest topic when they are about as close as its members."""
    assigned = np.array(labels, dtype=int, copy=True)
    clustered_idx = np.where(assigned >= 0)[0]
    noise_idx = np.where(assigned < 0)[0]
    if clustered_idx.size == 0 or noise_idx.size == 0:
        return assigned

    centroid_ids: list[int] = []
    centroids: list[np.ndarray] = []
    floors: list[float] = []
    for cluster_id in sorted(set(int(label) for label in assigned[clustered_idx])):
        members = matrix[assigned == cluster_id]
        centroid = members.mean(axis=0)
        centroid = centroid / max(float(np.linalg.norm(centroid)), 1e-9)
        member_sims = members @ centroid
        centroid_ids.append(cluster_id)
        centroids.append(centroid)
        floors.append(float(member_sims.min()) - 0.05)

    similarities = matrix[noise_idx] @ np.stack(centroids).T
    for offset, noise_i in enumerate(noise_idx):
        best = int(similarities[offset].argmax())
        if float(similarities[offset, best]) >= floors[best]:
            assigned[noise_i] = centroid_ids[best]
    return assigned


def _dissolve_weak_clusters(labels: np.ndarray, centered: np.ndarray) -> np.ndarray:
    """Singletons and groups no tighter than chance are outliers, not topics."""
    output = np.array(labels, dtype=int, copy=True)
    for label in sorted(set(int(value) for value in output if int(value) >= 0)):
        indices = [int(index) for index in np.where(output == label)[0]]
        if len(indices) == 1 or cluster_cohesion(centered, indices) < MIN_CENTERED_COHESION:
            output[indices] = -1
    return output


def cluster_major(matrix: np.ndarray) -> tuple[np.ndarray, str]:
    count = len(matrix)
    if count < 4:
        return np.zeros(count, dtype=int), "single"

    labels: np.ndarray | None = None
    method = "agglomerative"
    if count >= DENSITY_MIN_N:
        reduced = reduce_for_clustering(matrix)
        candidate = hdbscan_labels(reduced, adaptive_min_cluster_size(count))
        n_clusters, noise_frac = cluster_quality(candidate)
        if n_clusters >= 2 and noise_frac <= 0.4:
            labels = candidate
            method = "umap_hdbscan"
    if labels is None:
        labels = agglomerative_labels(matrix)

    labels = soft_assign_noise(_dissolve_weak_clusters(labels, matrix), matrix)
    return _relabel_dense(labels), method


def assign_subtopics(major_labels: np.ndarray, matrix: np.ndarray) -> list[int | None]:
    subs: list[int | None] = [None] * len(major_labels)
    for major in sorted({int(label) for label in major_labels if int(label) >= 0}):
        indices = [index for index, label in enumerate(major_labels) if int(label) == major]
        if len(indices) < SUBTOPIC_MIN_SIZE:
            continue
        sub_labels = agglomerative_labels(center_embeddings(matrix[indices]))
        if len(set(int(label) for label in sub_labels)) < 2:
            continue
        for relative, sub_label in enumerate(sub_labels):
            subs[indices[relative]] = int(sub_label)
    return subs


def cluster_embeddings_with_method(
    ids: list[int], matrix: np.ndarray
) -> tuple[dict[int, dict[str, int | None]], str]:
    if len(ids) < 4:
        return {annotation_id: {"major": 0, "sub": None} for annotation_id in ids}, "single"

    majors, method = cluster_major(center_embeddings(matrix))
    subs = assign_subtopics(majors, matrix)
    return {
        annotation_id: {"major": int(majors[index]), "sub": subs[index]}
        for index, annotation_id in enumerate(ids)
    }, method


def cluster_embeddings(
    ids: list[int], matrix: np.ndarray
) -> dict[int, dict[str, int | None]]:
    return cluster_embeddings_with_method(ids, matrix)[0]


def edge_threshold(matrix: np.ndarray) -> float:
    if len(matrix) < 3:
        return 0.0
    similarities = matrix @ matrix.T
    upper = similarities[np.triu_indices(len(matrix), k=1)]
    return float(np.percentile(upper, EDGE_PERCENTILE))


def cluster_cohesion(matrix: np.ndarray, indices: list[int]) -> float:
    if len(indices) < 2:
        return 0.0
    members = matrix[indices]
    similarities = members @ members.T
    total = float(similarities.sum() - np.trace(similarities))
    return total / (len(indices) * (len(indices) - 1))


def _minmax(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return values
    low, high = float(values.min()), float(values.max())
    if high - low < 1e-9:
        return np.full_like(values, 0.5, dtype=np.float64)
    return (values - low) / (high - low)


def compute_node_metrics(
    ids: list[int],
    cluster_map: dict[int, dict[str, int | None]],
    matrix: np.ndarray,
) -> dict[int, NodeMetrics]:
    """Pillar/niche roles from how similar each paper is to the rest of its topic."""
    centered = center_embeddings(matrix)
    similarities = centered @ centered.T
    np.fill_diagonal(similarities, 0.0)
    raw_similarities = matrix @ matrix.T
    np.fill_diagonal(raw_similarities, -1.0)

    groups: dict[int, list[int]] = defaultdict(list)
    for index, annotation_id in enumerate(ids):
        major = cluster_map[annotation_id]["major"]
        groups[int(major if major is not None else -1)].append(index)

    centrality = np.full(len(ids), 0.5, dtype=np.float64)
    affinity = np.zeros(len(ids), dtype=np.float64)
    z_scores = np.zeros(len(ids), dtype=np.float64)
    roles = ["core"] * len(ids)

    for major, members in groups.items():
        member_idx = np.array(members, dtype=int)
        if len(members) == 1:
            roles[members[0]] = "niche" if major < 0 else "core"
            continue
        means = similarities[np.ix_(member_idx, member_idx)].sum(axis=1) / (len(members) - 1)
        affinity[member_idx] = means
        centrality[member_idx] = _minmax(means)
        std = float(means.std())
        z = (means - float(means.mean())) / std if std > 1e-9 else np.zeros(len(members))
        z_scores[member_idx] = z
        if major < 0:
            for index in member_idx:
                roles[int(index)] = "niche"
            continue
        if len(members) < 3:
            continue
        strongest = int(member_idx[int(np.argmax(means))])
        weakest = int(member_idx[int(np.argmin(means))])
        for relative, index in enumerate(member_idx):
            score = float(z[relative])
            if score >= PILLAR_Z or int(index) == strongest:
                roles[int(index)] = "pillar"
            elif score <= NICHE_Z or int(index) == weakest:
                roles[int(index)] = "niche"

    threshold = edge_threshold(matrix)
    degree = (raw_similarities >= threshold).sum(axis=1).astype(np.float64)
    influence = _minmax(0.6 * _minmax(affinity) + 0.4 * _minmax(degree))

    return {
        annotation_id: NodeMetrics(
            centrality=round(float(centrality[index]), 4),
            influence=round(float(influence[index]), 4),
            role=roles[index],
            z_score=round(float(z_scores[index]), 4),
        )
        for index, annotation_id in enumerate(ids)
    }


def similar_papers(ids: list[int], matrix: np.ndarray) -> dict[int, list[int]]:
    """Nearest neighbours above a library-relative threshold; always keep the closest one."""
    similarities = matrix @ matrix.T
    threshold = edge_threshold(matrix)
    output: dict[int, list[int]] = {}
    for index, annotation_id in enumerate(ids):
        ranked = [int(candidate) for candidate in np.argsort(similarities[index])[::-1] if int(candidate) != index]
        neighbors = [
            ids[candidate]
            for candidate in ranked
            if float(similarities[index, candidate]) >= threshold
        ][:MAX_SIMILAR_PAPERS]
        if not neighbors and ranked:
            neighbors = [ids[ranked[0]]]
        output[annotation_id] = neighbors
    return output


def project_coordinates(ids: list[int], matrix: np.ndarray) -> dict[int, list[float]]:
    import umap

    count = len(ids)
    if count == 1:
        return {ids[0]: [0.0, 0.0]}
    if count == 2:
        return {ids[0]: [-1.0, 0.0], ids[1]: [1.0, 0.0]}
    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=max(2, min(15, count - 1)),
        metric="cosine",
        min_dist=0.1,
        random_state=42,
        n_jobs=1,
    )
    result = np.asarray(reducer.fit_transform(matrix), dtype=np.float32)
    return {
        annotation_id: [float(result[index][0]), float(result[index][1])]
        for index, annotation_id in enumerate(ids)
    }


def influence_heatmap(
    xs: list[float],
    ys: list[float],
    weights: list[float],
    resolution: int = HEATMAP_RESOLUTION,
) -> dict[str, Any]:
    if not xs:
        return {
            "resolution": resolution,
            "x_min": 0.0,
            "x_max": 1.0,
            "y_min": 0.0,
            "y_max": 1.0,
            "values": [],
        }
    x_arr = np.asarray(xs, dtype=np.float64)
    y_arr = np.asarray(ys, dtype=np.float64)
    w_arr = np.asarray(weights, dtype=np.float64)
    x_min, x_max = float(x_arr.min()), float(x_arr.max())
    y_min, y_max = float(y_arr.min()), float(y_arr.max())
    if x_max == x_min:
        x_max = x_min + 1.0
    if y_max == y_min:
        y_max = y_min + 1.0
    pad_x = (x_max - x_min) * 0.2
    pad_y = (y_max - y_min) * 0.2
    x_min -= pad_x
    x_max += pad_x
    y_min -= pad_y
    y_max += pad_y
    sigma_x = max((x_max - x_min) / 10.0, 1e-6)
    sigma_y = max((y_max - y_min) / 10.0, 1e-6)
    grid_x = np.linspace(x_min, x_max, resolution)
    grid_y = np.linspace(y_min, y_max, resolution)
    gx, gy = np.meshgrid(grid_x, grid_y)
    values = np.zeros((resolution, resolution), dtype=np.float64)
    for x, y, weight in zip(x_arr, y_arr, w_arr):
        if weight <= 0:
            continue
        values += float(weight) * np.exp(
            -0.5
            * ((((gx - x) / sigma_x) ** 2) + (((gy - y) / sigma_y) ** 2))
        )
    peak = float(values.max())
    if peak > 0:
        values = values / peak
    return {
        "resolution": resolution,
        "x_min": x_min,
        "x_max": x_max,
        "y_min": y_min,
        "y_max": y_max,
        "values": np.round(values, 4).tolist(),
    }


def place_ghost(
    neighbor_coords: list[list[float]],
    centroid: list[float],
    spread: float,
) -> list[float]:
    if not neighbor_coords:
        return [centroid[0] + max(spread, 0.4), centroid[1]]
    avg = np.mean(np.asarray(neighbor_coords, dtype=np.float64), axis=0)
    direction = avg - np.asarray(centroid, dtype=np.float64)
    norm = float(np.linalg.norm(direction))
    if norm < 1e-6:
        direction = np.array([1.0, 0.0], dtype=np.float64)
        norm = 1.0
    pushed = avg + (direction / norm) * max(spread * 0.45, 0.25)
    return [float(pushed[0]), float(pushed[1])]
