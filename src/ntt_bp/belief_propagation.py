"""Loopy sum-product belief propagation on the INTT factor graph.

Implements O(q^2) Numba-accelerated message passing for Gentleman-Sande
butterfly factors, with profiled circular-Gaussian observation model
and damped message updates for convergence.
"""

import math
import time

import numpy as np
from numba import njit, prange

from .constants import MLKEM_N, MLKEM_Q, N_LAYERS
from .factor_graph import ButterflyFactor, build_full_intt_factor_graph, compute_full_intt

# ---------------------------------------------------------------------------
# Precomputed sum tables for O(1) modular addition lookups
# ---------------------------------------------------------------------------

_SUM_TAB: np.ndarray | None = None
_SUM_TAB_T: np.ndarray | None = None


def _init_tables() -> None:
    """Lazily initialize the (u+v) mod q lookup tables."""
    global _SUM_TAB, _SUM_TAB_T
    if _SUM_TAB is not None:
        return
    q = MLKEM_Q
    tab = np.empty((q, q), dtype=np.int32)
    for u in range(q):
        for v in range(q):
            tab[u, v] = (u + v) % q
    _SUM_TAB = tab
    _SUM_TAB_T = tab.T.copy()


# ---------------------------------------------------------------------------
# Numba-JIT message kernels
# ---------------------------------------------------------------------------


@njit(parallel=True, cache=True)
def _msg_uin_numba(py, pz, pw, sum_tab, q_val, zeta_val):
    """Message to u_in: sum_v py[v] * pz[(u+v)%q] * pw[zeta*(v-u)%q]"""
    result = np.zeros(q_val)
    for u in prange(q_val):
        s = 0.0
        for v in range(q_val):
            uo = sum_tab[u, v]
            vo = (zeta_val * ((v - u) % q_val)) % q_val
            s += py[v] * pz[uo] * pw[vo]
        result[u] = s
    return result


@njit(parallel=True, cache=True)
def _msg_vin_numba(px, pz, pw, sum_tab_T, q_val, zeta_val):
    """Message to v_in: sum_u px[u] * pz[(u+v)%q] * pw[zeta*(v-u)%q]"""
    result = np.zeros(q_val)
    for v in prange(q_val):
        s = 0.0
        for u in range(q_val):
            uo = sum_tab_T[v, u]
            vo = (zeta_val * ((v - u) % q_val)) % q_val
            s += px[u] * pz[uo] * pw[vo]
        result[v] = s
    return result


@njit(parallel=True, cache=True)
def _msg_uout_numba(px, py, pw, q_val, zeta_val):
    """Message to u_out: for each u_out, sum over u_in."""
    result = np.zeros(q_val)
    for uo in prange(q_val):
        s = 0.0
        for ui in range(q_val):
            vi = (uo - ui) % q_val
            vo = (zeta_val * ((vi - ui) % q_val)) % q_val
            s += px[ui] * py[vi] * pw[vo]
        result[uo] = s
    return result


@njit(parallel=True, cache=True)
def _msg_vout_numba(px, py, pz, q_val, zeta_inv_val):
    """Message to v_out: for each v_out, sum over u_in."""
    result = np.zeros(q_val)
    for vo in prange(q_val):
        d = (zeta_inv_val * vo) % q_val
        s = 0.0
        for ui in range(q_val):
            vi = (ui + d) % q_val
            uo = (ui + vi) % q_val
            s += px[ui] * py[vi] * pz[uo]
        result[vo] = s
    return result


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def warmup_numba() -> None:
    """Force JIT compilation of all message kernels with dummy data."""
    _init_tables()
    q = MLKEM_Q
    dummy = np.ones(q, dtype=np.float64) / q
    tab = _SUM_TAB
    tab_t = _SUM_TAB_T
    _msg_uin_numba(dummy, dummy, dummy, tab, q, 1)
    _msg_vin_numba(dummy, dummy, dummy, tab_t, q, 1)
    _msg_uout_numba(dummy, dummy, dummy, q, 1)
    _msg_vout_numba(dummy, dummy, dummy, q, 1)


def generate_observations(
    true_values: dict[int, int],
    snr: float,
    n_traces: int,
    rng: np.random.Generator,
    q: int = MLKEM_Q,
) -> dict[int, np.ndarray]:
    """Generate profiled circular-Gaussian observations on Z_q.

    For each observed variable, produces a posterior distribution over
    Z_q from *n_traces* noisy measurements at the given SNR.

    Parameters
    ----------
    true_values : dict[int, int]
        Mapping from variable index to true value in Z_q.
    snr : float
        Signal-to-noise ratio per trace.
    n_traces : int
        Number of traces averaged.
    rng : np.random.Generator
        Random number generator.
    q : int
        Modulus (default MLKEM_Q = 3329).

    Returns
    -------
    dict[int, np.ndarray]
        Mapping from variable index to posterior distribution (length q).
    """
    sigma2_eff = (q * q / 12.0) / (snr * n_traces)
    observations = {}
    all_vals = np.arange(q, dtype=np.float64)
    for var, true_val in true_values.items():
        noisy = (true_val + rng.normal(0, math.sqrt(sigma2_eff))) % q
        diff = all_vals - noisy
        diff = diff - q * np.round(diff / q)
        log_lik = -0.5 * diff**2 / sigma2_eff
        log_lik -= np.max(log_lik)
        lik = np.exp(log_lik)
        observations[var] = lik / np.sum(lik)
    return observations


# ---------------------------------------------------------------------------
# Core BP loop
# ---------------------------------------------------------------------------


def run_bp(
    n_vars: int,
    factors: list[ButterflyFactor],
    observations: dict[int, np.ndarray],
    max_iterations: int = 50,
    damping: float = 0.5,
    q: int = MLKEM_Q,
    verbose: bool = False,
    convergence_tol: float = 1e-4,
    n_coeffs: int = MLKEM_N,
) -> tuple[dict[int, np.ndarray], int, list[float]]:
    """Run loopy sum-product belief propagation.

    Parameters
    ----------
    n_vars : int
        Total number of variable nodes.
    factors : list[ButterflyFactor]
        Factor graph (typically 896 butterfly factors).
    observations : dict[int, np.ndarray]
        Observation distributions keyed by variable index.
    max_iterations : int
        Maximum BP iterations.
    damping : float
        Message damping coefficient in [0, 1).
    q : int
        Modulus.
    verbose : bool
        Print per-iteration diagnostics.
    convergence_tol : float
        Stop when max belief change falls below this threshold.
    n_coeffs : int
        Number of L0 coefficients to track for entropy.

    Returns
    -------
    beliefs : dict[int, np.ndarray]
        Final marginal beliefs for every variable.
    n_iter : int
        Number of iterations executed.
    entropy_history : list[float]
        Average L0 entropy (bits) per iteration.
    """
    _init_tables()
    uniform = np.ones(q, dtype=np.float64) / q

    # Build adjacency: var -> list of (factor_index, slot)
    var_to_factors: dict[int, list[tuple[int, int]]] = {}
    for fi, f in enumerate(factors):
        for slot, var in enumerate([f.u_in, f.v_in, f.u_out, f.v_out]):
            var_to_factors.setdefault(var, []).append((fi, slot))

    n_factors = len(factors)
    f2v = np.full((n_factors * 4, q), 1.0 / q, dtype=np.float64)

    beliefs = np.full((n_vars, q), 1.0 / q, dtype=np.float64)
    for i, obs in observations.items():
        beliefs[i] = obs.copy()

    f_uin = np.array([f.u_in for f in factors], dtype=np.int32)
    f_vin = np.array([f.v_in for f in factors], dtype=np.int32)
    f_uout = np.array([f.u_out for f in factors], dtype=np.int32)
    f_vout = np.array([f.v_out for f in factors], dtype=np.int32)
    f_zeta = np.array([f.zeta for f in factors], dtype=np.int64)
    f_zeta_inv = np.array([f.zeta_inv for f in factors], dtype=np.int64)

    entropy_history: list[float] = []

    for iteration in range(max_iterations):
        old_beliefs = beliefs.copy()
        t_iter = time.time()

        for fi in range(n_factors):
            vars_fi = [f_uin[fi], f_vin[fi], f_uout[fi], f_vout[fi]]
            z = int(f_zeta[fi])
            z_inv = int(f_zeta_inv[fi])

            cavities = []
            for slot in range(4):
                var = vars_fi[slot]
                b = beliefs[var]
                old_msg = f2v[fi * 4 + slot]
                safe_old = np.maximum(old_msg, 1e-30)
                cavity = b / safe_old
                s = np.sum(cavity)
                cavities.append(cavity / s if s > 0 else uniform.copy())

            c_ui, c_vi, c_uo, c_vo = cavities

            new_msgs = [
                _msg_uin_numba(c_vi, c_uo, c_vo, _SUM_TAB, q, z),
                _msg_vin_numba(c_ui, c_uo, c_vo, _SUM_TAB_T, q, z),
                _msg_uout_numba(c_ui, c_vi, c_vo, q, z),
                _msg_vout_numba(c_ui, c_vi, c_uo, q, z_inv),
            ]

            for slot in range(4):
                s = np.sum(new_msgs[slot])
                if s > 0:
                    new_msgs[slot] /= s
                else:
                    new_msgs[slot] = uniform.copy()
                idx = fi * 4 + slot
                f2v[idx] = (1 - damping) * new_msgs[slot] + damping * f2v[idx]

        beliefs[:] = 1.0
        for i in range(n_vars):
            if i in observations:
                beliefs[i] = observations[i].copy()
            for fi, slot in var_to_factors.get(i, []):
                beliefs[i] *= f2v[fi * 4 + slot]
            s = np.sum(beliefs[i])
            if s > 0:
                beliefs[i] /= s
            else:
                beliefs[i] = uniform

        l0_ent = 0.0
        for i in range(n_coeffs):
            p = np.maximum(beliefs[i], 1e-30)
            l0_ent -= float(np.sum(beliefs[i] * np.log2(p)))
        l0_ent /= n_coeffs
        entropy_history.append(l0_ent)

        l0_vars = list(range(min(50, n_coeffs)))
        max_diff = (
            max(np.max(np.abs(beliefs[i] - old_beliefs[i])) for i in l0_vars)
            if l0_vars
            else 0
        )

        if verbose:
            print(
                f"  iter {iteration + 1:3d}: L0 H={l0_ent:.2f}b, "
                f"delta={max_diff:.6f}, {time.time() - t_iter:.1f}s"
            )

        if max_diff < convergence_tol:
            return (
                {i: beliefs[i] for i in range(n_vars)},
                iteration + 1,
                entropy_history,
            )

    return {i: beliefs[i] for i in range(n_vars)}, max_iterations, entropy_history


# ---------------------------------------------------------------------------
# High-level attack simulation
# ---------------------------------------------------------------------------


def simulate_attack(
    snr_n: float,
    seed: int = 42,
    max_bp_iter: int = 50,
    observe_layers: list[int] | None = None,
    verbose: bool = False,
) -> dict:
    """Run a complete SASCA-style attack simulation.

    Generates a random ML-KEM secret, computes the INTT, creates noisy
    observations on the specified layers, runs BP, and evaluates
    secret-key recovery at L0.

    Parameters
    ----------
    snr_n : float
        Product of SNR and number of traces (effective observation
        quality).
    seed : int
        RNG seed for reproducibility.
    max_bp_iter : int
        Maximum BP iterations.
    observe_layers : list[int] or None
        Which INTT layers to observe (1-indexed).  Default: all
        intermediate layers [1..7].
    verbose : bool
        Print per-iteration BP diagnostics.

    Returns
    -------
    dict
        Attack results including BSR, entropy, rank statistics.
    """
    rng = np.random.default_rng(seed)
    q = MLKEM_Q
    n = MLKEM_N
    n_layers = N_LAYERS
    snr = 1.0
    n_traces = int(snr_n / snr)

    secret_ntt = rng.integers(0, q, size=n).astype(np.int64)
    intermediates = compute_full_intt(secret_ntt, n, n_layers)

    true_values: dict[int, int] = {}
    for layer_idx in range(n_layers + 1):
        for i in range(n):
            true_values[layer_idx * n + i] = int(intermediates[layer_idx][i])

    factors = build_full_intt_factor_graph(n, n_layers)

    if observe_layers is None:
        observe_layers = list(range(1, n_layers + 1))

    observed_vars: dict[int, int] = {}
    for layer_idx in observe_layers:
        for i in range(n):
            observed_vars[layer_idx * n + i] = true_values[layer_idx * n + i]

    observations = generate_observations(observed_vars, snr, n_traces, rng, q)

    n_vars = (n_layers + 1) * n
    t0 = time.time()
    beliefs, n_iter, entropy_hist = run_bp(
        n_vars,
        factors,
        observations,
        max_iterations=max_bp_iter,
        damping=0.5,
        q=q,
        verbose=verbose,
        n_coeffs=n,
    )
    bp_time = time.time() - t0

    l0_correct = 0
    l0_entropies = []
    l0_ranks = []
    for i in range(n):
        true_val = true_values[i]
        b = beliefs[i]
        if int(np.argmax(b)) == true_val:
            l0_correct += 1
        p_safe = np.maximum(b, 1e-30)
        ent = -float(np.sum(b * np.log2(p_safe)))
        l0_entropies.append(ent)
        rank = int(np.where(np.argsort(-b) == true_val)[0][0]) + 1
        l0_ranks.append(rank)

    l0_map_error = 1.0 - l0_correct / n
    mid_layer = n_layers // 2 + 1
    mid_correct = sum(
        1
        for i in range(n)
        if int(np.argmax(beliefs[mid_layer * n + i]))
        == true_values[mid_layer * n + i]
    )

    return {
        "snr_n": snr_n,
        "seed": seed,
        "bp_iterations": n_iter,
        "bp_time_s": round(bp_time, 1),
        "l0_map_error": round(l0_map_error, 4),
        "l0_bsr": round(l0_correct / n, 4),
        "l0_avg_entropy": round(float(np.mean(l0_entropies)), 2),
        "l0_median_rank": round(float(np.median(l0_ranks)), 1),
        "l0_mean_log2_rank": round(
            float(np.mean([math.log2(max(r, 1)) for r in l0_ranks])), 2
        ),
        "mid_layer_bsr": round(mid_correct / n, 4),
        "entropy_history": [round(e, 3) for e in entropy_hist],
        "n_coeffs": n,
        "n_layers": n_layers,
    }
