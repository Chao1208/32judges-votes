"""Contract and analytic tests; no model calls or upstream data required."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src import layout
from src.formulas import contrast_basis, panel_metrics, residual_gram, solve_human_equivalent
from src.votes_io import fingerprint, load_panel, load_saved_calibration, sha256


class AnalyticalTests(unittest.TestCase):
    def setUp(self):
        self.human = np.full((4, 2), .5)
        self.gold = np.zeros(4, dtype=int)

    def test_orthogonal_balanced_panel(self):
        result = panel_metrics(np.array([[0, 0, 1, 1], [0, 1, 0, 1]]), self.human, self.gold)
        for metric, expected in {"PR": 2., "E": .25, "J": .5, "nu_MSE": 2.,
                                 "gamma_co_all": .5, "n_eff": 2.}.items():
            self.assertAlmostEqual(result[metric], expected)

    def test_duplication_and_cancellation_have_equal_pr_different_loss(self):
        identical = panel_metrics(np.array([[0, 0, 1, 1]] * 2), self.human, self.gold)
        opposite = panel_metrics(np.array([[0, 0, 1, 1], [1, 1, 0, 0]]), self.human, self.gold)
        self.assertAlmostEqual(identical["PR"], 1.)
        self.assertAlmostEqual(opposite["PR"], 1.)
        self.assertAlmostEqual(identical["E"], .5)
        self.assertAlmostEqual(opposite["E"], 0.)
        self.assertEqual(opposite["nu_MSE_status"], "undefined_zero_panel_MSE")
        self.assertIsNone(opposite["nu_MSE"])
        self.assertIsNone(opposite["n_eff"])
        self.assertAlmostEqual(identical["gamma_co_all"], 1.)
        self.assertAlmostEqual(opposite["gamma_co_all"], 0.)

    def test_centered_gamma_excludes_constant_residual_bias(self):
        idx = np.array([[0, 0, 1, 1], [0, 1, 0, 1]])
        shifted = np.tile([.3, .7], (4, 1))
        a, b = [panel_metrics(idx, human, self.gold) for human in (self.human, shifted)]
        self.assertAlmostEqual(a["gamma_co_all"], b["gamma_co_all"])
        self.assertGreater(b["E"], a["E"])
        self.assertGreater(abs(a["PR"] - b["PR"]), .01)

    def test_zero_variance_is_explicit(self):
        result = panel_metrics(np.array([[0, 0, 0, 0], [0, 1, 0, 1]]), self.human, self.gold)
        self.assertIsNone(result["n_eff"])
        self.assertEqual(result["n_eff_status"], "undefined_zero_binary_error_variance")
        with self.assertRaisesRegex(ValueError, "zero residual energy"):
            residual_gram(np.zeros((2, 4, 2)))
        degenerate = panel_metrics(np.ones((2, 4), dtype=int), np.tile([1., 0.], (4, 1)), self.gold)
        self.assertIsNone(degenerate["nu_MSE"])
        self.assertEqual(degenerate["nu_MSE_status"], "undefined_degenerate_human_reference")
        self.assertIsNone(degenerate["gamma_co_all"])
        self.assertEqual(degenerate["gamma_co_status"], "undefined_zero_centered_variance")

    def test_contrast_basis_is_orthonormal_and_zero_sum(self):
        for n_labels in (2, 3, 4, 5):
            basis = contrast_basis(n_labels)
            np.testing.assert_allclose(basis.T @ basis, np.eye(n_labels - 1), atol=1e-14)
            np.testing.assert_allclose(basis.sum(axis=0), 0., atol=1e-14)
            idx = np.array([[0, 0, 1, 1], [0, 1, 0, 1]])
            residual = np.eye(n_labels)[idx] - 1. / n_labels
            projected = residual @ basis
            gram_full, _ = residual_gram(residual)
            gram_projected, _ = residual_gram(projected)
            np.testing.assert_allclose(gram_full, gram_projected, atol=1e-14)

    def test_calibration_bounds_and_monotonicity(self):
        value, status = solve_human_equivalent([2, 4, 8], [1.9, 3.7, 6.9], 2.8)
        self.assertAlmostEqual(value, 3.)
        self.assertEqual(status, "ok")
        self.assertEqual(solve_human_equivalent([2, 4], [1.9, 3.7], 1.), (2., "nu_H_le_first_grid"))
        self.assertEqual(solve_human_equivalent([2, 4], [1.9, 3.7], 4.), (None, "above_calibration_range"))
        for ys in ([2., 2.], [3., 2.], [2., float("nan")]):
            with self.assertRaises(ValueError):
                solve_human_equivalent([2, 4], ys, 2.)


class InputContractTests(unittest.TestCase):
    VOTES = "datasets/chaosnli-mnli-m/votes/baseline"

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in ("datasets/chaosnli-mnli-m/items", self.VOTES, "panel", "reference"):
            (self.root / name).mkdir(parents=True)
        (self.root / "datasets/chaosnli-mnli-m/items/uids.txt").write_text("u3\nu1\nu2\n")
        (self.root / "datasets/chaosnli-mnli-m/manifest.json").write_text(json.dumps(
            {"dataset_id": "chaosnli-mnli-m", "panel": {"file": "panel/panel-test.json", "k": 2}}))
        (self.root / "panel/panel-test.json").write_text(json.dumps(
            {"panel_id": "test", "k": 2, "judges": [{"judge_key": "a"}, {"judge_key": "b"}]}))
        self.human_path = self.root / "human.jsonl"
        self.human_rows = [{"uid": "u1", "label_counter": {"e": 50, "n": 50}, "majority_label": "n"},
                           {"uid": "u2", "label_counter": {"e": 100}, "majority_label": "e"},
                           {"uid": "u3", "label_counter": {"c": 100}, "majority_label": "c"}]
        self.write(self.human_path, self.human_rows)
        self.vote_rows = [{"uid": u, "label": label, "parse_fail": failed}
                          for u, label, failed in [("u1", "e", False), ("u2", "n", True), ("u3", "c", False)]]
        for judge in ["a", "b"]:
            self.write(self.root / f"{self.VOTES}/{judge}.jsonl", self.vote_rows)

    @staticmethod
    def write(path, records):
        path.write_text("".join(json.dumps(row) + "\n" for row in records))

    def load(self, policy="drop-items"):
        return load_panel(self.root, "mnli_m", self.human_path, policy)

    def test_join_order_gold_tie_and_union_failure_policy(self):
        clean, retained = self.load(), self.load("paper-retained")
        self.assertEqual(retained.uids, ["u3", "u1", "u2"])
        self.assertEqual(retained.gold.tolist(), [2, 1, 0])  # tie stays n, not argmax e
        self.assertEqual(clean.uids, ["u3", "u1"])
        self.assertEqual(clean.provenance["parse_fail_cells"], 2)
        self.assertEqual(clean.provenance["dropped_items"], 1)  # union, not cells
        self.assertEqual(retained.provenance["dropped_items"], 0)

    def test_votes_never_silently_intersect_or_overwrite(self):
        path = self.root / f"{self.VOTES}/a.jsonl"
        for records in (self.vote_rows[:-1], self.vote_rows + [self.vote_rows[0]],
                        self.vote_rows + [{"uid": "other", "label": "e", "parse_fail": False}]):
            self.write(path, records)
            with self.assertRaises(ValueError):
                self.load()

    def test_rejects_invalid_labels_and_presentation_data(self):
        path = self.root / f"{self.VOTES}/a.jsonl"
        for patch in ({"label": "x"}, {"parse_fail": "false"}, {"variant": 0}):
            records = [dict(row) for row in self.vote_rows]
            records[0].update(patch)
            self.write(path, records)
            with self.assertRaises(ValueError):
                self.load()

    def test_human_missing_duplicate_noninteger_and_wrong_total_rejected(self):
        invalid = [self.human_rows[:-1], self.human_rows + [self.human_rows[0]]]
        for counter in ({"e": 99}, {"e": -1, "n": 101}, {"e": 100.0}, {"e": True, "n": 99}, {"x": 100}):
            modified = [dict(row) for row in self.human_rows]
            modified[0]["label_counter"] = counter
            invalid.append(modified)
        for records in invalid:
            self.write(self.human_path, records)
            with self.assertRaises(ValueError):
                self.load()

    def test_panel_roster_is_the_only_judge_source(self):
        """The pinned panel file decides who is in the panel; an extra vote file is an error."""
        self.assertEqual(layout.dataset_id("mnli_m"), "chaosnli-mnli-m")
        self.assertEqual(layout.chaosnli_key("chaosnli-mnli-m"), "mnli_m")
        self.assertIsNone(layout.chaosnli_key("civil-comments-1000"))
        self.assertEqual(layout.panel_judges(self.root, "mnli_m"), ["a", "b"])
        self.write(self.root / f"{self.VOTES}/c.jsonl", self.vote_rows)
        with self.assertRaises(ValueError):
            self.load()

    def test_saved_curve_requires_same_items_and_counts(self):
        panel = self.load("paper-retained")
        directory = self.root / "reference"
        curve = directory / "calibration_curves.csv"
        curve.write_text("dataset,anchor,m,PR_mean\nmnli_m,h,2,1.9\nmnli_m,h,4,3.7\n")
        manifest = {"calibration_curves_sha256": sha256(curve), "datasets": {"mnli_m": {
            key: panel.provenance[key] for key in ("roster_sha256", "human_reference_sha256")}}}
        (directory / "calibration_manifest.json").write_text(json.dumps(manifest))
        self.assertEqual(load_saved_calibration(directory, "mnli_m", panel.provenance)[1], "saved_curve")
        self.assertEqual(load_saved_calibration(directory, "mnli_m", self.load().provenance)[1],
                         "unavailable_changed_item_set")
        changed = dict(panel.provenance, human_reference_sha256=fingerprint("changed counts"))
        self.assertEqual(load_saved_calibration(directory, "mnli_m", changed)[1], "unavailable_reference_mismatch")
        curve.write_text(curve.read_text() + "mnli_m,h,8,6.9\n")
        with self.assertRaisesRegex(ValueError, "manifest hash"):
            load_saved_calibration(directory, "mnli_m", panel.provenance)


if __name__ == "__main__":
    unittest.main()
