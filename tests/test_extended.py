"""Tests for the calibration, asymptote and selection code; synthetic data only."""
import itertools
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src import civil_comments
from src.formulas import closed_form_delta, nu_closed_form, panel_metrics, pool_asymptote
from src.selection import Pool, neighborhood, select


def synthetic_pool(size=8, n=60, n_labels=3, seed=0):
    rng = np.random.default_rng(seed)
    human = rng.dirichlet(np.ones(n_labels), size=n)
    gold = human.argmax(axis=1)
    idx = np.array([[rng.choice(n_labels, p=row) for row in human] for _ in range(size)])
    return idx, human, gold, [f"judge{j:02d}" for j in range(size)]


def plurality_accuracy(idx, gold, n_labels):
    scores = []
    for item in range(idx.shape[1]):
        counts = np.bincount(idx[:, item], minlength=n_labels)
        tied = np.flatnonzero(counts == counts.max())
        scores.append((gold[item] in tied) / len(tied))
    return float(np.mean(scores))


class CalibrationTests(unittest.TestCase):
    def test_closed_form_inverts_the_reference_curve(self):
        delta = 1.9e-3
        m = np.array([1., 2., 5., 50., 400.])
        np.testing.assert_allclose(nu_closed_form(m / (1. + (m - 1.) * delta), delta), m, rtol=1e-12)
        self.assertTrue(math.isnan(nu_closed_form(1.0001 / delta, delta)))
        self.assertTrue(math.isnan(nu_closed_form(2. / delta, delta)))

    def test_balanced_binary_delta_is_one_over_n(self):
        for n in (10, 1000):
            self.assertAlmostEqual(closed_form_delta(np.full((n, 2), .5)), 1. / n)


class AsymptoteTests(unittest.TestCase):
    def setUp(self):
        self.idx, self.human, self.gold, _ = synthetic_pool(size=6, n=80)
        self.result = pool_asymptote(self.idx, self.human)

    def test_matches_fixed_panel_error_and_gamma(self):
        fixed = panel_metrics(self.idx, self.human, self.gold)
        self.assertAlmostEqual(self.result["E"], fixed["E"])
        self.assertAlmostEqual(self.result["gamma_co_all"], fixed["gamma_co_all"])

    def test_centered_curve_passes_through_the_observed_panel(self):
        r = self.result
        k = r["k"]
        self.assertAlmostEqual(r["mu2"] + r["v_bar"] * (1. / k + (1. - 1. / k) * r["rho_bar"]), r["E"])
        self.assertAlmostEqual(r["observed_share_of_centered_pct"],
                               100. * (r["mu2"] + r["v_bar"] * r["rho_bar"]) / r["E"])
        self.assertAlmostEqual(r["nu_MSE_inf_uncentered"], r["J"] / r["c_K"])

    def test_projection_at_observed_size_adds_nothing(self):
        self.assertAlmostEqual(pool_asymptote(self.idx, self.human, k_project=6)["nu_MSE_gain_at_k_project"], 0.)


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.idx, self.human, self.gold, self.judges = synthetic_pool()
        self.pool = Pool(self.idx, self.human, self.gold, self.judges)

    def test_readings_match_brute_force(self):
        combos = list(itertools.combinations(range(self.pool.size), 3))
        acc_int, _, pr, _ = self.pool.readings(combos)
        energy, _ = self.pool.distribution(combos)
        for c, a, p, e in zip(combos, acc_int, pr, energy):
            panel = self.idx[list(c)]
            self.assertAlmostEqual(self.pool.acc(a), plurality_accuracy(panel, self.gold, 3))
            fixed = panel_metrics(panel, self.human, self.gold)
            self.assertAlmostEqual(p, fixed["PR"])
            self.assertAlmostEqual(e, fixed["E"])

    def test_neighborhood_order_and_size(self):
        rows = neighborhood([1, 4, 6], 8, 2)
        self.assertEqual(len(rows), math.comb(3, 2) * math.comb(5, 2))
        self.assertEqual(rows[0].tolist(), [0, 2, 6])
        self.assertTrue(all(len(set(r)) == 3 and len(set(r) & {1, 4, 6}) == 1 for r in rows.tolist()))

    def test_rules_and_enumeration_agree_with_brute_force(self):
        k = 3
        out = select(self.pool, k)
        s0 = out["panels"]["S0"]
        acc = self.pool.judge_acc
        self.assertEqual(s0["members"], sorted(sorted(range(8), key=lambda j: (-acc[j], self.judges[j]))[:k]))
        cand = np.vstack([neighborhood(s0["members"], 8, 1), neighborhood(s0["members"], 8, 2)])
        a, _, _, nu = self.pool.readings(cand)
        energy, _ = self.pool.distribution(cand)
        feasible = a > s0["acc_int_sum_lut6"]
        self.assertAlmostEqual(out["panels"]["A"]["nu_H"], np.nanmax(nu[feasible]))
        self.assertAlmostEqual(out["panels"]["E"]["E"], energy[feasible].min())
        self.assertEqual(out["panels"]["D"]["acc_int_sum_lut6"], a.max())
        self.assertGreater(out["panels"]["A"]["acc"], s0["acc"])

        combos = list(itertools.combinations(range(8), k))
        a_all, _, _, nu_all = self.pool.readings(combos)
        enum = out["enumeration"]
        better = a_all > s0["acc_int_sum_lut6"]
        self.assertEqual(enum["n_panels"], math.comb(8, k))
        self.assertEqual(enum["n_acc_gt_S0"], int(better.sum()))
        self.assertEqual(enum["n_acc_gt_and_nu_H_gt_S0"], int((better & (nu_all > s0["nu_H"])).sum()))
        self.assertAlmostEqual(enum["max_acc"], self.pool.acc(a_all.max()))


class CivilCommentsInputTests(unittest.TestCase):
    def test_curve_hash_is_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "calibration_curve_civil_comments.csv").write_text("m,pr_mean\n2,1.9\n")
            with self.assertRaisesRegex(ValueError, "hash"):
                civil_comments.load_curve(Path(tmp), "0" * 64)


if __name__ == "__main__":
    unittest.main()
