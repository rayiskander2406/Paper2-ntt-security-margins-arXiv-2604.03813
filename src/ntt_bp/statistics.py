"""Statistical utilities for attack evaluation.

Provides Wilson score confidence intervals for binomial success rates
and Monte Carlo mutual information estimation for the circular-Gaussian
observation model on Z_q.
"""

import math

import numpy as np

from .constants import MLKEM_Q


def wilson_ci(
    successes: int, total: int, z: float = 1.96
) -> tuple[float, float]:
    """Wilson score confidence interval for a binomial proportion.

    Parameters
    ----------
    successes : int
        Number of successes.
    total : int
        Number of trials.
    z : float
        Z-score for desired confidence level (default 1.96 for 95%).

    Returns
    -------
    tuple[float, float]
        (lower, upper) bounds of the confidence interval.
    """
    if total == 0:
        return 0.0, 1.0
    p_hat = successes / total
    denom = 1 + z * z / total
    center = (p_hat + z * z / (2 * total)) / denom
    spread = z * math.sqrt((p_hat * (1 - p_hat) + z * z / (4 * total)) / total) / denom
    lo = max(0.0, center - spread)
    hi = min(1.0, center + spread)
    return lo, hi


def compute_exact_mi_numerical(
    snr_n: float,
    q: int = MLKEM_Q,
    n_mc: int = 100_000,
    seed: int = 42,
) -> dict:
    """Estimate mutual information I(X; Y) via Monte Carlo.

    Uses the circular-Gaussian observation model on Z_q with effective
    variance sigma^2_eff = (q^2/12) / (SNR * N).

    Parameters
    ----------
    snr_n : float
        Product of SNR and number of traces.
    q : int
        Modulus (default 3329).
    n_mc : int
        Number of Monte Carlo samples.
    seed : int
        RNG seed.

    Returns
    -------
    dict
        Dictionary with MI estimate, Gaussian bound, shaping loss,
        and auxiliary statistics.
    """
    rng = np.random.default_rng(seed)
    snr = 1.0
    n_traces = int(snr_n / snr)
    sigma2_eff = (q * q / 12.0) / (snr * n_traces)
    sigma_eff = math.sqrt(sigma2_eff)
    H_X = math.log2(q)
    all_vals = np.arange(q, dtype=np.float64)

    conditional_entropies = []
    for _ in range(n_mc):
        x = rng.integers(0, q)
        noisy_center = (x + rng.normal(0, sigma_eff)) % q
        diff = all_vals - noisy_center
        diff = diff - q * np.round(diff / q)
        log_lik = -0.5 * diff**2 / sigma2_eff
        log_lik -= np.max(log_lik)
        lik = np.exp(log_lik)
        posterior = lik / np.sum(lik)
        p_safe = np.maximum(posterior, 1e-30)
        h_xy = -float(np.sum(posterior * np.log2(p_safe)))
        conditional_entropies.append(h_xy)

    E_H_XY = float(np.mean(conditional_entropies))
    std_H_XY = float(np.std(conditional_entropies)) / math.sqrt(n_mc)
    MI = H_X - E_H_XY
    mi_gaussian = min(0.5 * math.log2(1 + snr_n), H_X)

    return {
        "snr_n": snr_n,
        "q": q,
        "sigma2_eff": round(sigma2_eff, 4),
        "sigma_eff": round(sigma_eff, 4),
        "H_X": round(H_X, 4),
        "E_H_XY": round(E_H_XY, 4),
        "E_H_XY_stderr": round(std_H_XY, 6),
        "MI_exact": round(MI, 4),
        "MI_gaussian": round(mi_gaussian, 4),
        "shaping_loss": round(mi_gaussian - MI, 4),
        "n_mc_samples": n_mc,
    }
