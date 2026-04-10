#!/usr/bin/env python3
"""
Experiment C: RSI vs Full RP Shuffling Overhead Simulation

Measures trace complexity overhead of Adams Bridge RSI shuffling (S=64)
versus full random permutation under:
  (1) idealized identical leakage (no position fingerprint)
  (2) position-dependent leakage (hardware-realistic)

Uses analytical + Monte Carlo success-probability model (exact under
Gaussian assumptions). Runs in minutes on a laptop.

Reference: arXiv:2604.03813, Section 4.8.3.
"""

import json
import math
import time
import sys
import os
from dataclasses import dataclass, asdict
from typing import List, Tuple, Optional

import numpy as np
from scipy import stats

# --- Constants ----------------------------------------------------------------
MLDSA_Q = 8_380_417       # ML-DSA modulus
COEFF_BITS = 23           # bit width of coefficients
S = 64                    # Adams Bridge RSI search space
H = MLDSA_Q              # number of key hypotheses
H_WRONG = H - 1
SEED = 42
N_MC = 10_000            # Monte Carlo reps per success_probability call
N_CAL = 10_000           # calibration traces for empirical rho
N_TRIALS = 100           # trials per configuration
N_OFFSET_MC = 5_000      # MC reps for offset recovery probability

# Binary search bounds for N_80
N_MIN_LOG2 = 0
N_MAX_LOG2 = 24          # 2^24 ~ 16M traces (generous upper bound)


def hamming_weight_23bit(x: int) -> int:
    """Hamming weight of 23-bit representation."""
    return bin(x & ((1 << COEFF_BITS) - 1)).count('1')


def hw_variance_23bit(rng: np.random.Generator, n_samples: int = 100_000) -> float:
    """Compute Var[HW] for uniform 23-bit values."""
    samples = rng.integers(0, MLDSA_Q, size=n_samples)
    hws = np.array([hamming_weight_23bit(int(x)) for x in samples])
    return float(np.var(hws))


def analytical_rho(var_hw: float, sigma: float) -> float:
    """Analytical correlation: rho = sqrt(Var[HW] / (Var[HW] + sigma^2))."""
    return math.sqrt(var_hw / (var_hw + sigma ** 2))


def empirical_rho(rng: np.random.Generator, sigma: float,
                  n_traces: int = N_CAL) -> float:
    """Compute empirical rho from simulated CPA traces."""
    a_secret = int(rng.integers(0, MLDSA_Q))
    omega_inv = int(rng.integers(1, MLDSA_Q))  # random twiddle

    b_vals = rng.integers(0, MLDSA_Q, size=n_traces)
    intermediates = np.array([
        ((a_secret - int(b)) * omega_inv) % MLDSA_Q for b in b_vals
    ])
    hws = np.array([hamming_weight_23bit(int(x)) for x in intermediates])
    noise = rng.normal(0, sigma, size=n_traces)
    leakage = hws + noise

    return float(np.corrcoef(hws, leakage)[0, 1])


def success_probability(rho_eff: float, N: int, H_wrong: int = H_WRONG,
                        n_mc: int = N_MC,
                        rng: Optional[np.random.Generator] = None) -> float:
    """
    Pr(correct key ranks #1) via Monte Carlo.

    Correct key: test stat ~ N(rho_eff * sqrt(N), 1)
    Wrong keys: test stats ~ i.i.d. N(0, 1)
    CDF trick: Pr(max of H_wrong N(0,1) < x) = Phi(x)^H_wrong
    """
    if rng is None:
        rng = np.random.default_rng()

    if rho_eff <= 0 or N <= 0:
        return 0.0

    mu_correct = rho_eff * math.sqrt(N)
    correct_samples = rng.normal(mu_correct, 1.0, size=n_mc)

    # Use log-space for numerical stability with large H_wrong
    log_p_win = H_wrong * stats.norm.logcdf(correct_samples)
    p_win = np.exp(log_p_win)

    # Bernoulli draw: does correct key win?
    wins = rng.random(size=n_mc) < p_win
    return float(np.mean(wins))


def expected_posterior_true_offset(sigma_bias: float, sigma_noise: float,
                                  rng: np.random.Generator,
                                  n_mc: int = N_OFFSET_MC) -> float:
    """
    E[P(c_true | L, delta)] -- expected posterior probability of the true offset.

    Attacker computes Bayesian posterior from profiled bias pattern:
      P(c | L) proportional to exp(-sum_j (L_j - delta_{(j-c) mod S})^2 / (2*sigma^2))

    Returns E[P(c_true | L)] averaged over noise realizations.
    This is the correct quantity for soft-decision weighted CPA:
      rho_eff = rho * E[P(c_true | L)]
    which correctly gives rho/S when sigma_bias=0 (overhead = S^2).
    """
    if sigma_bias == 0:
        return 1.0 / S  # uniform posterior -> 1/S

    total_p_true = 0.0
    for _ in range(n_mc):
        # Generate position biases (profiled, fixed per trial)
        delta = rng.normal(0, sigma_bias, size=S)
        # Generate leakage at true offset c=0 (WLOG)
        noise = rng.normal(0, sigma_noise, size=S)
        L = delta + noise

        # Log-posterior for each candidate offset
        log_posteriors = np.zeros(S)
        for c in range(S):
            shifted_delta = np.roll(delta, c)
            residual = L - shifted_delta
            log_posteriors[c] = -np.sum(residual ** 2) / (2 * sigma_noise ** 2)

        # Softmax for numerical stability
        log_posteriors -= np.max(log_posteriors)
        posteriors = np.exp(log_posteriors)
        posteriors /= np.sum(posteriors)

        total_p_true += posteriors[0]  # P(c_true=0 | L)

    return total_p_true / n_mc


def compute_rho_eff_rsi(rho: float, e_p_correct: float) -> float:
    """
    Effective correlation for RSI with soft offset recovery.

    rho_eff = rho * E[P(c_true | L)]

    When offset fully recovered (E[P]=1): rho_eff = rho -> overhead = 1
    When offset unknown (E[P]=1/S):       rho_eff = rho/S -> overhead = S^2
    """
    return rho * e_p_correct


def find_n80(rho_eff: float, rng: np.random.Generator) -> Optional[int]:
    """
    Binary search for N_80: minimum N where success_probability >= 0.80.

    Uses geometric search (powers of 2) then bisection.
    Returns None if N > 2^N_MAX_LOG2 needed.
    """
    if rho_eff <= 0:
        return None

    # Phase 1: geometric search to bracket
    n_low, n_high = None, None
    for k in range(N_MIN_LOG2, N_MAX_LOG2 + 1):
        N = 1 << k
        p = success_probability(rho_eff, N, rng=rng)
        if p >= 0.80:
            n_high = N
            n_low = (1 << (k - 1)) if k > 0 else 1
            break

    if n_high is None:
        return None  # even 2^N_MAX_LOG2 not enough

    # Phase 2: bisection between n_low and n_high
    while n_high - n_low > max(1, n_low // 10):
        n_mid = (n_low + n_high) // 2
        p = success_probability(rho_eff, n_mid, rng=rng)
        if p >= 0.80:
            n_high = n_mid
        else:
            n_low = n_mid

    return n_high


@dataclass
class TrialResult:
    sigma_noise: float
    sigma_bias: float
    mode: str          # "known", "rsi", "rp"
    trial: int
    rho: float
    rho_eff: float
    p_offset: Optional[float]
    n80: Optional[int]


@dataclass
class ConfigResult:
    sigma_noise: float
    sigma_bias: float
    mode: str
    n_trials: int
    n80_median: Optional[float]
    n80_p5: Optional[float]
    n80_p95: Optional[float]
    rho_eff_median: float
    overhead_median: Optional[float]
    overhead_p5: Optional[float]
    overhead_p95: Optional[float]
    p_offset_median: Optional[float]


def run_experiment():
    """Run the full RSI vs RP shuffling overhead simulation."""
    print("=" * 70)
    print("EXPERIMENT C: RSI vs Full RP Shuffling Overhead Simulation")
    print("=" * 70)
    print(f"S = {S} (Adams Bridge RSI)")
    print(f"S^2 = {S**2}")
    print(f"H = {H:,} (ML-DSA q)")
    print(f"Trials per config: {N_TRIALS}")
    print(f"MC reps per success_probability: {N_MC}")
    print(f"Seed: {SEED}")
    print()

    rng = np.random.default_rng(SEED)
    t_start = time.time()

    # --- Phase 1: Signal calibration ---
    print("Phase 1: Signal calibration")
    print("-" * 40)

    var_hw = hw_variance_23bit(rng)
    print(f"  Var[HW] for 23-bit uniform: {var_hw:.4f}")
    print(f"  (theoretical for uniform bits: 23 * 0.25 = 5.75)")

    noise_levels = [0.1, 0.5, 1.0, 2.0, 5.0]
    rho_table = {}
    for sigma in noise_levels:
        rho_a = analytical_rho(var_hw, sigma)
        rho_e = empirical_rho(rng, sigma)
        rho_table[sigma] = rho_a
        print(f"  sigma={sigma:<4} -> rho_analytical={rho_a:.6f}, rho_empirical={rho_e:.6f}, "
              f"diff={abs(rho_a - rho_e):.6f}")

    print()

    # --- Phase 2: Configuration matrix ---
    configs = []

    # Table 1: idealized sweep
    for sigma in noise_levels:
        for mode in ["known", "rsi", "rp"]:
            configs.append((sigma, 0.0, mode))

    # Table 2: position leakage sweep at sigma=1.0
    bias_levels = [0.1, 0.3, 0.5, 1.0, 2.0]
    for sb in bias_levels:
        for mode in ["rsi", "rp"]:
            configs.append((1.0, sb, mode))

    # Cross-configurations
    cross_configs = [(0.5, 0.5), (2.0, 1.0)]
    for sigma, sb in cross_configs:
        for mode in ["rsi", "rp"]:
            configs.append((sigma, sb, mode))

    # Deduplicate
    configs = list(dict.fromkeys(configs))

    print(f"Phase 2: Running {len(configs)} configurations x {N_TRIALS} trials")
    print("-" * 40)

    all_trials: List[TrialResult] = []
    config_results: List[ConfigResult] = []

    # Pre-compute offset recovery probabilities
    offset_cache = {}

    for i, (sigma, sigma_bias, mode) in enumerate(configs):
        rho = rho_table[sigma]
        n80_vals = []
        rho_eff_vals = []
        p_offset_vals = []

        for trial in range(N_TRIALS):
            trial_rng = np.random.default_rng(SEED + trial * 1000 + i * 100000)

            if mode == "known":
                rho_eff = rho
                p_offset = None
            elif mode == "rp":
                rho_eff = rho / S
                p_offset = None
            else:  # rsi
                cache_key = (sigma, sigma_bias)
                if cache_key not in offset_cache:
                    p_off = expected_posterior_true_offset(
                        sigma_bias, sigma, trial_rng, n_mc=N_OFFSET_MC
                    )
                    offset_cache[cache_key] = p_off

                p_offset = offset_cache[cache_key]
                rho_eff = compute_rho_eff_rsi(rho, p_offset)

            n80 = find_n80(rho_eff, trial_rng)
            n80_vals.append(n80)
            rho_eff_vals.append(rho_eff)
            if p_offset is not None:
                p_offset_vals.append(p_offset)

            all_trials.append(TrialResult(
                sigma_noise=sigma, sigma_bias=sigma_bias, mode=mode,
                trial=trial, rho=rho, rho_eff=rho_eff,
                p_offset=p_offset, n80=n80
            ))

        # Compute summary statistics
        valid_n80 = [n for n in n80_vals if n is not None]
        if valid_n80:
            n80_med = float(np.median(valid_n80))
            n80_p5 = float(np.percentile(valid_n80, 5))
            n80_p95 = float(np.percentile(valid_n80, 95))
        else:
            n80_med = n80_p5 = n80_p95 = None

        rho_eff_med = float(np.median(rho_eff_vals))
        p_off_med = float(np.median(p_offset_vals)) if p_offset_vals else None

        cr = ConfigResult(
            sigma_noise=sigma, sigma_bias=sigma_bias, mode=mode,
            n_trials=N_TRIALS, n80_median=n80_med,
            n80_p5=n80_p5, n80_p95=n80_p95,
            rho_eff_median=rho_eff_med,
            overhead_median=None, overhead_p5=None, overhead_p95=None,
            p_offset_median=p_off_med,
        )
        config_results.append(cr)

        status = f"  [{i+1}/{len(configs)}] sigma={sigma}, sigma_bias={sigma_bias}, {mode:>5}: "
        if n80_med is not None:
            status += f"N80={n80_med:,.0f} [CI: {n80_p5:,.0f}-{n80_p95:,.0f}], rho_eff={rho_eff_med:.6f}"
        else:
            status += f"N80=INFEASIBLE, rho_eff={rho_eff_med:.6f}"
        if p_off_med is not None:
            status += f", P_offset={p_off_med:.4f}"
        print(status)

    print()

    # --- Phase 3: Compute overhead factors ---
    print("Phase 3: Computing overhead factors")
    print("-" * 40)

    cr_lookup = {}
    for cr in config_results:
        cr_lookup[(cr.sigma_noise, cr.sigma_bias, cr.mode)] = cr

    for cr in config_results:
        key_known = (cr.sigma_noise, 0.0, "known")
        if key_known in cr_lookup and cr_lookup[key_known].n80_median:
            n80_known = cr_lookup[key_known].n80_median
            if cr.n80_median is not None and n80_known > 0:
                cr.overhead_median = cr.n80_median / n80_known
                if cr.n80_p5 is not None:
                    cr.overhead_p5 = cr.n80_p5 / n80_known
                if cr.n80_p95 is not None:
                    cr.overhead_p95 = cr.n80_p95 / n80_known

    t_total = time.time() - t_start
    print(f"\nTotal runtime: {t_total:.1f}s")

    return config_results, all_trials, rho_table, var_hw, t_total


def print_tables(config_results, rho_table):
    """Print formatted results tables."""
    cr_lookup = {}
    for cr in config_results:
        cr_lookup[(cr.sigma_noise, cr.sigma_bias, cr.mode)] = cr

    print("\n" + "=" * 70)
    print("TABLE 1: Idealized (sigma_bias = 0) -- RSI = RP validation")
    print("=" * 70)
    print(f"{'sigma':>7} | {'N80(known)':>12} | {'N80(RSI)':>12} | {'RSI OH':>8} | "
          f"{'N80(RP)':>12} | {'RP OH':>8} | {'S^2':>6}")
    print("-" * 80)

    for sigma in [0.1, 0.5, 1.0, 2.0, 5.0]:
        known = cr_lookup.get((sigma, 0.0, "known"))
        rsi = cr_lookup.get((sigma, 0.0, "rsi"))
        rp = cr_lookup.get((sigma, 0.0, "rp"))

        def fmt_n80(cr):
            return f"{cr.n80_median:>12,.0f}" if cr and cr.n80_median else f"{'N/A':>12}"

        def fmt_oh(cr):
            return f"{cr.overhead_median:>8.1f}x" if cr and cr.overhead_median else f"{'N/A':>8}"

        print(f"{sigma:>7.1f} | {fmt_n80(known)} | {fmt_n80(rsi)} | {fmt_oh(rsi)} | "
              f"{fmt_n80(rp)} | {fmt_oh(rp)} | {S**2:>6,}")

    print("\n" + "=" * 70)
    print("TABLE 2: Position leakage sweep (sigma_noise = 1.0)")
    print("=" * 70)
    print(f"{'sigma_bias':>10} | {'ratio':>8} | {'P_offset':>8} | {'RSI OH':>10} | "
          f"{'RP OH':>10} | {'RSI/RP':>8}")
    print("-" * 65)

    for sb in [0.0, 0.1, 0.3, 0.5, 1.0, 2.0]:
        rsi = cr_lookup.get((1.0, sb, "rsi"))
        rp = cr_lookup.get((1.0, sb, "rp"))

        rsi_oh = rsi.overhead_median if rsi and rsi.overhead_median else None
        rp_oh = rp.overhead_median if rp and rp.overhead_median else None
        p_off = rsi.p_offset_median if rsi else None

        ratio = rsi_oh / rp_oh if (rsi_oh and rp_oh and rp_oh > 0) else None

        p_off_s = f"{p_off:>8.4f}" if p_off is not None else f"{'--':>8}"
        rsi_s = f"{rsi_oh:>9.1f}x" if rsi_oh else f"{'N/A':>10}"
        rp_s = f"{rp_oh:>9.1f}x" if rp_oh else f"{'N/A':>10}"
        ratio_s = f"{ratio:>7.3f}x" if ratio else f"{'--':>8}"

        print(f"{sb:>10.1f} | {sb/1.0:>8.1f} | {p_off_s} | {rsi_s} | {rp_s} | {ratio_s}")

    # Cross-configurations
    print("\n" + "=" * 70)
    print("CROSS-CONFIGURATIONS")
    print("=" * 70)
    cross = [(0.5, 0.5), (2.0, 1.0)]
    for sigma, sb in cross:
        rsi = cr_lookup.get((sigma, sb, "rsi"))
        rp = cr_lookup.get((sigma, sb, "rp"))
        if rsi and rp:
            rsi_oh = rsi.overhead_median
            rp_oh = rp.overhead_median
            print(f"  sigma={sigma}, sigma_bias={sb} (ratio={sb/sigma:.1f}): "
                  f"RSI={rsi_oh:.1f}x RP={rp_oh:.1f}x")


def save_results(config_results, all_trials, rho_table, var_hw, runtime,
                 output_dir):
    """Save JSON results."""
    os.makedirs(output_dir, exist_ok=True)

    data = {
        "experiment": "C: RSI vs Full RP Shuffling Overhead",
        "reference": "arXiv:2604.03813, Section 4.8.3",
        "parameters": {
            "S": S, "S_squared": S ** 2,
            "q": MLDSA_Q, "H": H, "coeff_bits": COEFF_BITS,
            "var_hw": var_hw, "seed": SEED,
            "n_mc": N_MC, "n_trials": N_TRIALS,
            "n_offset_mc": N_OFFSET_MC,
        },
        "rho_table": {str(k): v for k, v in rho_table.items()},
        "config_results": [asdict(cr) for cr in config_results],
        "runtime_seconds": runtime,
    }

    json_path = os.path.join(output_dir, "shuffling_overhead.json")
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"\nJSON saved: {json_path}")


def main():
    config_results, all_trials, rho_table, var_hw, runtime = run_experiment()
    print_tables(config_results, rho_table)

    output_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "evidence", "experiments", "rsi_vs_rp"
    )
    save_results(config_results, all_trials, rho_table, var_hw, runtime, output_dir)

    # --- Success criteria check ---
    print("\n" + "=" * 70)
    print("SUCCESS CRITERIA CHECK")
    print("=" * 70)

    cr_lookup = {}
    for cr in config_results:
        cr_lookup[(cr.sigma_noise, cr.sigma_bias, cr.mode)] = cr

    # 1. Idealized: RSI ~ RP ~ S^2
    rsi_0 = cr_lookup.get((1.0, 0.0, "rsi"))
    rp_0 = cr_lookup.get((1.0, 0.0, "rp"))
    if rsi_0 and rp_0 and rsi_0.overhead_median and rp_0.overhead_median:
        rsi_r = rsi_0.overhead_median / (S ** 2)
        rp_r = rp_0.overhead_median / (S ** 2)
        pass1 = 0.5 < rsi_r < 2.0 and 0.5 < rp_r < 2.0
        print(f"  1. Idealized (RSI~RP~S^2): RSI={rsi_r:.2f}xS^2, RP={rp_r:.2f}xS^2 -> "
              f"{'PASS' if pass1 else 'FAIL'}")

    # 2. RSI degradation monotonic
    rsi_overheads = []
    for sb in [0.0, 0.1, 0.3, 0.5, 1.0, 2.0]:
        rsi = cr_lookup.get((1.0, sb, "rsi"))
        if rsi and rsi.overhead_median:
            rsi_overheads.append(rsi.overhead_median)
    if len(rsi_overheads) >= 2:
        monotonic = all(rsi_overheads[i] >= rsi_overheads[i + 1]
                        for i in range(len(rsi_overheads) - 1))
        print(f"  2. RSI monotonic degradation: {rsi_overheads} -> "
              f"{'PASS' if monotonic else 'FAIL'}")

    # 3. RP stable
    rp_ohs = []
    for sb in [0.0, 0.1, 0.3, 0.5, 1.0, 2.0]:
        rp = cr_lookup.get((1.0, sb, "rp"))
        if rp and rp.overhead_median:
            rp_ohs.append(rp.overhead_median)
    if rp_ohs:
        rp_stable = max(rp_ohs) / min(rp_ohs) < 1.5
        print(f"  3. RP stable: range {min(rp_ohs):,.0f}-{max(rp_ohs):,.0f}x -> "
              f"{'PASS' if rp_stable else 'FAIL'}")

    # 4. Separation at sigma_bias/sigma >= 0.3
    rsi_03 = cr_lookup.get((1.0, 0.3, "rsi"))
    rp_03 = cr_lookup.get((1.0, 0.3, "rp"))
    if rsi_03 and rp_03 and rsi_03.overhead_median and rp_03.overhead_median:
        gap = rp_03.overhead_median / rsi_03.overhead_median
        print(f"  4. Separation at sigma_bias/sigma=0.3: RP/RSI = {gap:.1f}x -> "
              f"{'PASS' if gap > 1.5 else 'FAIL'}")

    print()


if __name__ == "__main__":
    main()
