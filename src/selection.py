"""Panel selection in the fixed pool, Sections 3.6 and 4.10 (MIT; see LICENSE).

Every reading is exact on the observed items: accuracy is an integer sum of tie
scores scaled by 6, nu_H inverts the analytic reference of Eq. (6), and E uses the
residual Gram identity. The candidate set and all tie-breaking follow the order
documented in REPRODUCE.md, so the selected panels are deterministic.
"""
from __future__ import annotations

import itertools
import math

import numpy as np

if __package__:
    from .formulas import closed_form_delta, nu_closed_form, onehot_panel, residual_gram
else:
    from formulas import closed_form_delta, nu_closed_form, onehot_panel, residual_gram

LUT_SCALE = 6
BLOCK = 10000


class Pool:
    """Pool-level quantities shared by every panel drawn from the same votes."""

    def __init__(self, idx, human, gold, judges):
        self.idx, self.human = np.asarray(idx, int), np.asarray(human, float)
        self.gold, self.judges = np.asarray(gold, int), list(judges)
        self.size, self.n = self.idx.shape
        self.n_labels = self.human.shape[1]
        if self.n_labels > 3:
            raise ValueError("integer accuracy sums need at most three labels")
        residual = onehot_panel(self.idx, self.n_labels) - self.human[None, :, :]
        self.gram, correlation = residual_gram(residual)
        self.q_weights = correlation ** 2
        np.fill_diagonal(self.q_weights, 0.)
        self.delta = closed_form_delta(self.human)
        self.J = float(np.mean(1. - np.sum(self.human ** 2, axis=1)))
        self.judge_acc = (self.idx == self.gold[None, :]).mean(axis=1)
        self.acc_order = sorted(range(self.size), key=lambda j: (-self.judge_acc[j], self.judges[j]))
        self.acc_rank = {j: r + 1 for r, j in enumerate(self.acc_order)}
        self.gold_first = (self.idx - self.gold[None, :]) % self.n_labels
        self._packs = {}

    def top_k(self, k):
        """Baseline S0: the k best single-judge accuracies, ties by judge key."""
        return sorted(self.acc_order[:k])

    def _pack(self, k):
        if k not in self._packs:
            base = k + 1
            codes = (base ** self.gold_first).astype(np.int32)
            lut = np.zeros(k * base ** (self.n_labels - 1) + 1, np.int8)
            for counts in itertools.product(range(k + 1), repeat=self.n_labels):
                if sum(counts) == k and counts[0] == max(counts):
                    lut[sum(c * base ** l for l, c in enumerate(counts))] = \
                        LUT_SCALE // counts.count(max(counts))
            self._packs[k] = codes, lut
        return self._packs[k]

    def readings(self, combos):
        """Integer accuracy sum, q_bar, PR and nu_H for panels given as (N, k) indices."""
        combos = np.asarray(combos, np.int64)
        k = combos.shape[1]
        codes, lut = self._pack(k)
        acc_int = np.empty(len(combos), np.int64)
        q_bar = np.zeros(len(combos))
        for start in range(0, len(combos), BLOCK):
            block = combos[start:start + BLOCK]
            code = codes[block[:, 0]].copy()
            for j in range(1, k):
                code += codes[block[:, j]]
            acc_int[start:start + BLOCK] = lut[code].sum(axis=1, dtype=np.int64)
            for a in range(k):
                for b in range(a + 1, k):
                    q_bar[start:start + BLOCK] += self.q_weights[block[:, a], block[:, b]]
        q_bar /= k * (k - 1) / 2.
        pr = k / (1. + (k - 1) * q_bar)
        return acc_int, q_bar, pr, nu_closed_form(pr, self.delta)

    def distribution(self, combos):
        """Distributional error E and mean member energy omega_bar per panel."""
        combos = np.asarray(combos, np.int64)
        k = combos.shape[1]
        energy = np.einsum("nab->n", self.gram[combos[:, :, None], combos[:, None, :]]) / k ** 2
        omega_bar = np.diag(self.gram)[combos].mean(axis=1)
        return energy, omega_bar

    def acc(self, acc_int):
        return np.asarray(acc_int) / (LUT_SCALE * self.n)


def neighborhood(s0, pool_size, swaps):
    """Panels exactly `swaps` members away from S0, swap-out major, swap-in minor."""
    s0 = sorted(s0)
    outside = [j for j in range(pool_size) if j not in set(s0)]
    rows = []
    for out in itertools.combinations(s0, swaps):
        keep = [x for x in s0 if x not in out]
        for into in itertools.combinations(outside, swaps):
            rows.append(sorted(keep + list(into)))
    assert len(rows) == math.comb(len(s0), swaps) * math.comb(pool_size - len(s0), swaps)
    return np.asarray(rows, np.int64)


def enumerate_panels(pool, k):
    """All C(pool, k) panels in lexicographic order with their accuracy and nu_H."""
    total = math.comb(pool.size, k)
    acc_int, nu = np.empty(total, np.int64), np.empty(total)
    iterator = itertools.combinations(range(pool.size), k)
    for start in range(0, total, BLOCK * 20):
        block = np.asarray(list(itertools.islice(iterator, BLOCK * 20)), np.int64)
        a, _, _, v = pool.readings(block)
        acc_int[start:start + len(block)], nu[start:start + len(block)] = a, v
    return acc_int, nu


def _first_argmax(values, mask):
    positions = np.flatnonzero(mask & np.isfinite(values))
    return None if positions.size == 0 else int(positions[np.argmax(values[positions])])


def select(pool, k, enumerate_all=True):
    """Baseline, rules A/D/E and the existence readings for one panel size."""
    s0 = pool.top_k(k)
    a0, q0, pr0, nu0 = (x[0] for x in pool.readings([s0]))
    e0, w0 = (x[0] for x in pool.distribution([s0]))
    one = neighborhood(s0, pool.size, 1)
    cand = np.vstack([one, neighborhood(s0, pool.size, 2)])
    a, q, pr, nu = pool.readings(cand)
    energy, omega = pool.distribution(cand)
    feasible = a > a0
    joint = feasible & np.isfinite(nu) & (nu > nu0)
    is_one = np.arange(len(cand)) < len(one)
    i_a = _first_argmax(nu, feasible)
    i_a1 = _first_argmax(nu, feasible & is_one)
    top = np.flatnonzero(a == a.max())
    i_d = int(top[np.argmax(np.nan_to_num(nu[top], nan=-np.inf))])
    i_e = _first_argmax(-energy, feasible)
    one_on_front = sum(not np.any((a >= a[i]) & (nu >= nu[i]) & ((a > a[i]) | (nu > nu[i])))
                       for i in np.flatnonzero(is_one))

    def panel(i):
        members = [int(x) for x in cand[i]]
        return {"members": members, "judge_keys": [pool.judges[j] for j in members],
                "acc": float(pool.acc(a[i])), "acc_int_sum_lut6": int(a[i]),
                "q_bar": float(q[i]), "PR": float(pr[i]), "nu_H": float(nu[i]),
                "E": float(energy[i]), "nu_MSE": pool.J / float(energy[i]),
                "omega_bar": float(omega[i]), "in_D_S0": bool(joint[i]),
                "swapped_in_ranks": sorted(pool.acc_rank[j] for j in set(members) - set(s0)),
                "swapped_out_ranks": sorted(pool.acc_rank[j] for j in set(s0) - set(members))}

    out = {"k": k, "delta": pool.delta, "J": pool.J,
           "panels": {"S0": {"members": s0, "judge_keys": [pool.judges[j] for j in s0],
                             "acc": float(pool.acc(a0)), "acc_int_sum_lut6": int(a0),
                             "q_bar": float(q0), "PR": float(pr0), "nu_H": float(nu0),
                             "E": float(e0), "nu_MSE": pool.J / float(e0), "omega_bar": float(w0)},
                      "A": panel(i_a), "D": panel(i_d), "E": panel(i_e)},
           "rule_A_one_swap": panel(i_a1),
           "candidates": {"n_one_swap": int(len(one)), "n_candidates": int(len(cand)),
                          "n_one_swap_in_D_S0": int((joint & is_one).sum()),
                          "n_in_D_S0": int(joint.sum()),
                          "n_feasible": int((feasible & np.isfinite(nu)).sum()),
                          "n_one_swap_on_candidate_front": int(one_on_front),
                          "max_nu_H_feasible": float(np.nanmax(nu[feasible])),
                          "max_nu_MSE_feasible": pool.J / float(energy[feasible].min())}}
    if enumerate_all:
        acc_all, nu_all = enumerate_panels(pool, k)
        better = acc_all > a0
        both = better & np.isfinite(nu_all) & (nu_all > nu0)
        rep = _first_argmax(nu_all, both)
        rep_members = next(itertools.islice(itertools.combinations(range(pool.size), k), rep, None))
        out["enumeration"] = {
            "n_panels": int(len(acc_all)),
            "n_acc_gt_S0": int(better.sum()),
            "n_acc_gt_and_nu_H_gt_S0": int(both.sum()),
            "S0_nu_H_percentile_pct": float(np.mean(nu_all < nu0 - 1e-12) * 100.),
            "S0_on_pareto_front": not bool(np.any((acc_all >= a0) & (nu_all >= nu0)
                                                  & ((acc_all > a0) | (nu_all > nu0)))),
            "max_acc": float(pool.acc(acc_all.max())), "max_nu_H": float(np.nanmax(nu_all)),
            "max_nu_H_in_D_S0": {"judge_keys": [pool.judges[j] for j in rep_members],
                                 "acc": float(pool.acc(acc_all[rep])), "nu_H": float(nu_all[rep])}}
    return out
