"""Pure array computations for the fixed-panel audit (MIT; see LICENSE).

Adapted from the study's verified formulas.py: one-hot construction,
participation ratio, residual Gram normalization, and Kish conversion.
Degenerate inputs are reported explicitly, never replaced by a fabricated
correlation. The human distribution is an empirical reference, not latent truth.
"""
from __future__ import annotations

import numpy as np


def onehot_panel(idx, n_labels):
    """Convert integer label indices of shape (judges, items) to one-hot votes."""
    idx = np.asarray(idx)
    if idx.ndim != 2 or min(idx.shape) < 1 or not np.issubdtype(idx.dtype, np.integer):
        raise ValueError("idx must be a nonempty integer judges-by-items array")
    if n_labels < 2 or np.any(idx < 0) or np.any(idx >= n_labels):
        raise ValueError("label index outside the vocabulary")
    return np.eye(n_labels)[idx]


def contrast_basis(n_labels):
    """Orthonormal zero-sum basis; NLI uses the study's named polarity/neutral axes."""
    if n_labels == 3:
        basis = np.array([[1., 0., -1.], [-1., 2., -1.]]).T
    else:
        basis = np.zeros((n_labels, n_labels - 1))
        for t in range(n_labels - 1):
            basis[:t + 1, t], basis[t + 1, t] = 1., -(t + 1.)
    return basis / np.linalg.norm(basis, axis=0, keepdims=True)


def participation_ratio(correlation):
    """Spectral PR of a positive semidefinite, unit-diagonal matrix."""
    eigenvalues = np.clip(np.linalg.eigvalsh(correlation), 0., None)
    return float(correlation.shape[0] ** 2 / np.sum(eigenvalues ** 2))


def residual_gram(residual):
    """Return uncentered K and unit-diagonal C; zero residual energy is invalid."""
    r = np.asarray(residual, dtype=float)
    if r.ndim != 3 or min(r.shape) < 1 or not np.isfinite(r).all():
        raise ValueError("residual must be a finite, nonempty 3-D array")
    gram = np.einsum("ail,bil->ab", r, r) / r.shape[1]
    energy = np.diag(gram)
    if np.any(energy <= 0.):
        raise ValueError("PR undefined: at least one judge has zero residual energy")
    correlation = gram / np.sqrt(np.outer(energy, energy))
    np.fill_diagonal(correlation, 1.)
    return gram, correlation


def panel_metrics(idx, human, gold):
    """Return PR, reference MSE, nu_MSE, centered common-mode share and n_eff.

    gamma_co_all uses the unscaled residuals centered over items. The full
    one-hot space is equivalent to any orthonormal zero-sum basis. n_eff
    uses Pearson correlations of binary errors against supplied gold labels.
    Undefined auxiliary metrics are null with an explicit status.
    """
    idx, human, gold = np.asarray(idx), np.asarray(human, float), np.asarray(gold)
    if human.ndim != 2 or not np.isfinite(human).all() or np.any(human < 0.):
        raise ValueError("human must be a finite, nonnegative probability matrix")
    if not np.allclose(human.sum(axis=1), 1., atol=1e-12, rtol=0.):
        raise ValueError("human probabilities must sum to one")
    votes = onehot_panel(idx, human.shape[1])
    k, n, n_labels = votes.shape
    if k < 2 or n < 2 or human.shape != (n, n_labels) or gold.shape != (n,):
        raise ValueError("need at least two judges/items and aligned human/gold arrays")
    if not np.issubdtype(gold.dtype, np.integer) or np.any(gold < 0) or np.any(gold >= n_labels):
        raise ValueError("gold label outside the vocabulary")
    residual = votes - human[None, :, :]
    _, correlation = residual_gram(residual)
    pr = participation_ratio(correlation)
    error = float(np.mean(np.sum(residual.mean(axis=0) ** 2, axis=1)))
    human_variance = float(np.mean(1. - np.sum(human ** 2, axis=1)))
    centered = residual - residual.mean(axis=1, keepdims=True)
    total_variance = float(np.sum(centered ** 2))
    gamma = (float(np.sum(centered.sum(axis=0) ** 2) / k / total_variance)
             if total_variance > 0. else None)
    binary = (idx != gold[None, :]).astype(float)
    binary -= binary.mean(axis=1, keepdims=True)
    variance = np.sum(binary ** 2, axis=1)
    phi_bar, n_eff = None, None
    if np.any(variance <= 0.):
        n_eff_status = "undefined_zero_binary_error_variance"
    else:
        phi = (binary @ binary.T) / np.sqrt(np.outer(variance, variance))
        phi_bar = float(phi[np.triu_indices(k, 1)].mean())
        denominator = 1. + (k - 1) * phi_bar
        n_eff_status = "ok" if denominator > 1e-14 else "undefined_nonpositive_denominator"
        if n_eff_status == "ok":
            n_eff = float(k / denominator)
    mse_status = ("undefined_degenerate_human_reference" if human_variance <= 0. else
                  "undefined_zero_panel_MSE" if error <= 0. else "ok")
    return {"k": k, "n_items": n, "PR": pr, "E": error, "J": human_variance,
            "nu_MSE": human_variance / error if mse_status == "ok" else None,
            "nu_MSE_status": mse_status,
            "gamma_co_all": gamma,
            "gamma_co_status": "ok" if gamma is not None else "undefined_zero_centered_variance",
            "phi_bar": phi_bar, "n_eff": n_eff, "n_eff_status": n_eff_status}


def closed_form_delta(human):
    """Null mean squared correlation of the analytic human reference, Eq. (5).

    delta = <s2 - 2 s3 + s2^2>_i / (n <1 - s2>_i^2) with s2 = sum_l h_il^2 and
    s3 = sum_l h_il^3; n is the number of items.
    """
    human = np.asarray(human, float)
    s2, s3 = np.sum(human ** 2, axis=1), np.sum(human ** 3, axis=1)
    return float(np.mean(s2 - 2. * s3 + s2 ** 2) / (human.shape[0] * np.mean(1. - s2) ** 2))


def nu_closed_form(pr, delta):
    """Invert PR0(m) = m / (1 + (m-1) delta), Eq. (6); NaN where PR >= 1/delta."""
    pr = np.asarray(pr, float)
    denominator = 1. - pr * delta
    with np.errstate(divide="ignore", invalid="ignore"):
        nu = np.where(denominator > 0., pr * (1. - delta) / denominator, np.nan)
    return float(nu) if nu.ndim == 0 else nu


def pool_asymptote(idx, human, k_project=64):
    """Fixed-pool extrapolations of the distributional error, Section 4.2 and Appendix C.

    Centered: hold mu2 = ||mean residual||^2, mean member variance v_bar and mean
    centered covariance rho_bar fixed, so E(m) = mu2 + v_bar (1/m + (1 - 1/m) rho_bar)
    and E_inf = mu2 + v_bar rho_bar. Uncentered: hold the mean diagonal omega_bar and
    mean off-diagonal c_K of the Gram matrix fixed, whose limit is c_K.
    """
    human = np.asarray(human, float)
    residual = onehot_panel(idx, human.shape[1]) - human[None, :, :]
    k, n, _ = residual.shape
    gram = np.einsum("ail,bil->ab", residual, residual) / n
    mu = residual.mean(axis=1)
    mu2 = float(np.sum(mu.mean(axis=0) ** 2))
    delta_mu = float(np.mean(np.sum((mu - mu.mean(axis=0)) ** 2, axis=1)))
    error = float(gram.sum()) / k ** 2
    centered = residual - mu[:, None, :]
    gamma = float(k * np.mean(np.sum(centered.mean(axis=0) ** 2, axis=1))
                  / np.sum(np.mean(np.sum(centered ** 2, axis=2), axis=1)))
    v_bar, rho_bar = (error - mu2) / gamma, (k * gamma - 1.) / (k - 1)
    human_variance = float(np.mean(1. - np.sum(human ** 2, axis=1)))
    omega_bar = float(np.mean(np.diag(gram)))
    c_k = (k * error - omega_bar) / (k - 1)
    e_inf = mu2 + v_bar * rho_bar
    e_proj = mu2 + v_bar * (1. / k_project + (1. - 1. / k_project) * rho_bar)
    return {"k": k, "J": human_variance, "E": error, "mu2": mu2, "gamma_co_all": gamma,
            "v_bar": v_bar, "rho_bar": rho_bar, "omega_bar": omega_bar, "c_K": c_k,
            "delta_mu": delta_mu,
            "nu_MSE_inf_centered": human_variance / e_inf,
            "nu_MSE_inf_uncentered": human_variance / c_k,
            "E_gap_rel_pct": 100. * (delta_mu / (k - 1)) / c_k,
            "observed_share_of_centered_pct": 100. * e_inf / error,
            "k_project": k_project,
            "nu_MSE_gain_at_k_project": human_variance / e_proj - human_variance / error}


def solve_human_equivalent(ms, pr_means, target):
    """Invert a strictly increasing saved mean-PR curve without extrapolation."""
    ms, ys = np.asarray(ms, float), np.asarray(pr_means, float)
    if (ms.ndim != 1 or ys.shape != ms.shape or len(ms) < 2
            or not np.isfinite(ms).all() or not np.isfinite(ys).all()
            or not np.isfinite(target) or np.any(np.diff(ms) <= 0.)
            or np.any(np.diff(ys) <= 0.)):
        raise ValueError("calibration requires finite, strictly increasing sizes and mean PR")
    if target <= ys[0]:
        return float(ms[0]), "nu_H_le_first_grid"
    if target > ys[-1]:
        return None, "above_calibration_range"
    return float(np.interp(target, ys, ms)), "ok"
