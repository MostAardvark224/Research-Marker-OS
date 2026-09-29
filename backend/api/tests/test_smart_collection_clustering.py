from django.test import SimpleTestCase
import numpy as np

from api.arxiv import search_arxiv
from api.smart_collections.clustering import (
    _dissolve_weak_clusters,
    adaptive_min_cluster_size,
    agglomerative_labels,
    cluster_embeddings,
    compute_node_metrics,
    influence_heatmap,
    place_ghost,
    soft_assign_noise,
)
from api.smart_collections.service import (
    _fallback_gaps,
    _keyword_label,
    _quota_exhausted,
    _retryable_generation_error,
    _topic_keywords,
)


def _normalize(points: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(points, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return (points / norms).astype(np.float32)


class AdaptiveClusterSizeTests(SimpleTestCase):
    def test_grows_slowly_with_library_size(self):
        self.assertEqual(adaptive_min_cluster_size(4), 4)
        self.assertGreaterEqual(adaptive_min_cluster_size(20), 3)
        self.assertLessEqual(adaptive_min_cluster_size(40), 5)
        self.assertLessEqual(adaptive_min_cluster_size(200), 10)


class SoftAssignTests(SimpleTestCase):
    def test_assigns_nearby_noise_to_nearest_cluster(self):
        matrix = _normalize(
            np.array(
                [
                    [1.0, 0.0, 0.0],
                    [0.98, 0.1, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.97, 0.1],
                    [0.9, 0.2, 0.0],
                ],
                dtype=np.float32,
            )
        )
        labels = np.array([0, 0, 1, 1, -1], dtype=int)
        assigned = soft_assign_noise(labels, matrix)
        self.assertEqual(int(assigned[4]), 0)


class ClusteringTests(SimpleTestCase):
    def test_small_n_separates_two_blobs(self):
        rng = np.random.default_rng(0)
        left = rng.normal([1.0, 0.0], 0.04, size=(5, 2))
        right = rng.normal([0.0, 1.0], 0.04, size=(5, 2))
        matrix = _normalize(np.vstack([left, right]))
        result = cluster_embeddings(list(range(10)), matrix)
        left_labels = {result[i]["major"] for i in range(5)}
        right_labels = {result[i]["major"] for i in range(5, 10)}
        self.assertEqual(len(left_labels), 1)
        self.assertEqual(len(right_labels), 1)
        self.assertNotEqual(next(iter(left_labels)), next(iter(right_labels)))

    def test_agglomerative_chooses_two_well_separated_groups(self):
        rng = np.random.default_rng(1)
        matrix = _normalize(
            np.vstack(
                [
                    rng.normal([1, 0, 0, 0], 0.05, size=(6, 4)),
                    rng.normal([0, 0, 1, 0], 0.05, size=(6, 4)),
                ]
            )
        )
        labels = agglomerative_labels(matrix)
        self.assertEqual(len(set(int(label) for label in labels)), 2)
        self.assertEqual(len(set(int(label) for label in labels[:6])), 1)

    def test_topics_sharing_a_common_direction_still_separate(self):
        rng = np.random.default_rng(2)
        shared = np.array([3.0, 0, 0, 0, 0, 0])
        groups = [
            shared + rng.normal([0, 1, 0, 0, 0, 0], 0.08, size=(6, 6)),
            shared + rng.normal([0, 0, 1, 0, 0, 0], 0.08, size=(6, 6)),
            shared + rng.normal([0, 0, 0, 1, 0, 0], 0.08, size=(6, 6)),
        ]
        matrix = _normalize(np.vstack(groups))
        result = cluster_embeddings(list(range(18)), matrix)
        for start in (0, 6, 12):
            self.assertEqual(len({result[i]["major"] for i in range(start, start + 6)}), 1)
        self.assertEqual(len({result[i]["major"] for i in (0, 6, 12)}), 3)


class CentralityTests(SimpleTestCase):
    def test_marks_interior_node_as_pillar_and_outlier_as_niche(self):
        core = np.array(
            [
                [1.0, 0.0, 0.0],
                [0.97, 0.1, 0.0],
                [0.97, -0.1, 0.0],
                [0.96, 0.05, 0.08],
                [0.4, 0.9, 0.0],
            ],
            dtype=np.float32,
        )
        matrix = _normalize(core)
        ids = [1, 2, 3, 4, 5]
        cluster_map = {item: {"major": 0, "sub": None} for item in ids}
        metrics = compute_node_metrics(ids, cluster_map, matrix)
        roles = {item: metrics[item].role for item in ids}
        self.assertIn("pillar", roles.values())
        self.assertEqual(metrics[5].role, "niche")
        pillar_id = max((item for item in ids if item != 5), key=lambda item: metrics[item].centrality)
        self.assertEqual(metrics[pillar_id].role, "pillar")
        self.assertGreater(metrics[pillar_id].centrality, metrics[5].centrality)
        self.assertGreater(metrics[pillar_id].influence, metrics[5].influence)


class HeatmapTests(SimpleTestCase):
    def test_peaks_near_high_influence_points(self):
        heatmap = influence_heatmap(
            [0.0, 10.0],
            [0.0, 10.0],
            [1.0, 0.1],
            resolution=12,
        )
        values = np.array(heatmap["values"])
        self.assertEqual(values.shape, (12, 12))
        self.assertGreater(float(values.max()), 0.5)

    def test_place_ghost_pushes_outward_from_centroid(self):
        placed = place_ghost([[2.0, 0.0], [2.2, 0.1]], [0.0, 0.0], 1.0)
        self.assertGreater(placed[0], 2.0)


class ArxivSearchTests(SimpleTestCase):
    def test_empty_query_short_circuits(self):
        self.assertEqual(search_arxiv("   "), [])


class WeakClusterTests(SimpleTestCase):
    def test_chance_grouping_is_dissolved(self):
        centered = _normalize(np.eye(6, dtype=np.float32))
        labels = _dissolve_weak_clusters(np.array([0, 0, 0, 1, 1, 1]), centered)
        self.assertTrue(all(int(label) == -1 for label in labels))

    def test_tight_group_is_kept(self):
        rng = np.random.default_rng(3)
        centered = _normalize(rng.normal([1, 0, 0, 0], 0.05, size=(4, 4)))
        labels = _dissolve_weak_clusters(np.array([0, 0, 0, 0]), centered)
        self.assertTrue(all(int(label) == 0 for label in labels))


class KeywordFallbackTests(SimpleTestCase):
    def test_keywords_distinguish_topics(self):
        keywords = _topic_keywords(
            {
                "a": "black holes black holes general relativity spacetime black holes",
                "b": "reinforcement learning policy gradient reinforcement learning agents",
                "c": "protein folding molecular dynamics protein folding",
            }
        )
        self.assertIn("black holes", keywords["a"])
        self.assertIn("reinforcement learning", keywords["b"])
        self.assertNotIn("black holes", keywords["b"])

    def test_label_falls_back_when_no_terms(self):
        self.assertEqual(_keyword_label([], "Research Topic 1"), "Research Topic 1")
        self.assertEqual(
            _keyword_label(["black holes", "spacetime"], "x"), "Black Holes & Spacetime"
        )

    def test_fallback_gaps_search_keywords_not_labels(self):
        gaps = _fallback_gaps(
            {"Physics": ["A", "B"], "Uncategorized": ["C"]},
            {"Physics": ["black holes", "spacetime", "extra"]},
        )
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["query"], "black holes spacetime")
        self.assertEqual(gaps[0]["cluster"], "Physics")


class GenerationRetryTests(SimpleTestCase):
    def test_daily_quota_is_not_retried(self):
        error = RuntimeError(
            "429 RESOURCE_EXHAUSTED. You exceeded your current quota, please check your plan"
        )
        self.assertTrue(_quota_exhausted(error))
        self.assertFalse(_retryable_generation_error(error))

    def test_transient_overload_is_retried(self):
        error = RuntimeError("503 UNAVAILABLE. This model is currently experiencing high demand.")
        self.assertFalse(_quota_exhausted(error))
        self.assertTrue(_retryable_generation_error(error))
