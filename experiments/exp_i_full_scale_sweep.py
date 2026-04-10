#!/usr/bin/env python3
"""Experiment I (Sweep): Full-scale BP attack on ML-KEM INTT.

120 trials across 8 SNR*N points with 30 BP iterations.
Measures bit success rate, mutual information extraction, and BP gain
over single-layer observation across the full transition region.

Estimated runtime: ~5 hours on Apple M2 (sequential).
Use --quick for a demo run (~20 min): 3 points x 2 trials x 10 iters.

Reference: arXiv:2604.03813, Section 4.8.9, Table 7.
"""

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np

from ntt_bp import (
    MLKEM_N,
    MLKEM_Q,
    N_LAYERS,
    build_full_intt_factor_graph,
    compute_exact_mi_numerical,
    simulate_attack,
    warmup_numba,
    wilson_ci,
)

OUT_DIR = Path(__file__).parent.parent / "evidence"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true",
                        help="Demo mode: 3 SNR*N points x 2 trials x 10 BP iters (~20 min)")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    log2q = math.log2(MLKEM_Q)

    warmup_numba()

    # Verify factor graph
    factors = build_full_intt_factor_graph()
    print(f"Factor graph: {len(factors)} factors, "
          f"{(N_LAYERS + 1) * MLKEM_N} variables")

    if args.quick:
        snr_n_values = [1000, 3000, 10000]
        trials_per_point = {s: 2 for s in snr_n_values}
        max_bp_iter = 10
        out_file = OUT_DIR / "sweep_results_quick.json"
        print("\n*** QUICK MODE: 3 points x 2 trials x 10 BP iters ***\n")
    else:
        snr_n_values = [500, 1000, 1500, 2000, 2500, 3000, 5000, 10000]
        trials_per_point = {
            500: 10, 1000: 20, 1500: 20, 2000: 20,
            2500: 20, 3000: 10, 5000: 10, 10000: 10,
        }
        max_bp_iter = 30
        out_file = OUT_DIR / "sweep_results.json"

    print("=" * 70)
    print("FULL-SCALE BP SWEEP (FIPS 203 twiddle factors)")
    print(f"  {len(snr_n_values)} SNR*N points x {max_bp_iter} BP iters")
    print("=" * 70)

    # Pre-compute exact MI for all points
    print("\nComputing exact single-layer MI...")
    mi_exact = {}
    for snr_n in snr_n_values:
        r = compute_exact_mi_numerical(snr_n, n_mc=100000, seed=42)
        mi_exact[snr_n] = r["MI_exact"]
        print(f"  SNR*N={snr_n:>6.0f}: MI_1-layer = {r['MI_exact']:.4f} bits")

    all_results = []

    for si, snr_n in enumerate(snr_n_values):
        print(f"\n--- SNR*N = {snr_n:.0f} ({si+1}/{len(snr_n_values)}) ---")
        trial_results = []

        n_trials = trials_per_point[snr_n]
        for trial in range(n_trials):
            seed = trial * 100_000 + int(snr_n)
            t0 = time.time()
            result = simulate_attack(
                snr_n=snr_n, seed=seed, max_bp_iter=max_bp_iter,
                verbose=(trial == 0),
            )
            t_trial = time.time() - t0
            trial_results.append(result)
            mi_bp = max(0, log2q - result["l0_avg_entropy"])
            print(f"  Trial {trial+1}/{n_trials}: "
                  f"err={result['l0_map_error']:.1%}, "
                  f"H={result['l0_avg_entropy']:.1f}b, "
                  f"MI_BP={mi_bp:.2f}, "
                  f"BSR={result['l0_bsr']:.1%}, "
                  f"{t_trial:.0f}s")

        errors = [r["l0_map_error"] for r in trial_results]
        entropies = [r["l0_avg_entropy"] for r in trial_results]
        bsrs = [r["l0_bsr"] for r in trial_results]
        mi_bp_mean = max(0, log2q - float(np.mean(entropies)))
        mi_1 = mi_exact[snr_n]
        bp_gain = mi_bp_mean / mi_1 if mi_1 > 0 else 0

        n_success_100 = sum(1 for b in bsrs if b == 1.0)
        ci_low, ci_high = wilson_ci(n_success_100, n_trials)

        point = {
            "snr_n": snr_n,
            "n_trials": n_trials,
            "mean_l0_error": round(float(np.mean(errors)), 4),
            "std_l0_error": round(float(np.std(errors)), 4),
            "mean_l0_entropy": round(float(np.mean(entropies)), 2),
            "std_l0_entropy": round(float(np.std(entropies)), 2),
            "mean_l0_bsr": round(float(np.mean(bsrs)), 4),
            "mi_bp": round(mi_bp_mean, 4),
            "mi_1_layer": round(mi_1, 4),
            "bp_gain": round(bp_gain, 2),
            "n_100pct_bsr": n_success_100,
            "wilson_ci_95_100pct": [round(ci_low, 4), round(ci_high, 4)],
            "per_trial": [
                {
                    "trial": t,
                    "seed": trial_results[t]["seed"],
                    "l0_bsr": trial_results[t]["l0_bsr"],
                    "l0_map_error": trial_results[t]["l0_map_error"],
                    "l0_avg_entropy": trial_results[t]["l0_avg_entropy"],
                    "bp_iterations": trial_results[t]["bp_iterations"],
                }
                for t in range(n_trials)
            ],
        }
        all_results.append(point)

        print(f"  => err={point['mean_l0_error']:.1%}, "
              f"H={point['mean_l0_entropy']:.1f}b, "
              f"MI_BP={point['mi_bp']:.2f}, "
              f"MI_1={point['mi_1_layer']:.2f}, "
              f"gain={point['bp_gain']:.2f}x, "
              f"BSR={point['mean_l0_bsr']:.1%}")

        # Save incrementally
        with open(out_file, "w") as f:
            json.dump(all_results, f, indent=2)

    # Final summary table
    print("\n" + "=" * 90)
    print("RESULTS SUMMARY")
    print("=" * 90)
    print(f"{'SNR*N':>8} | {'Error':>8} | {'Entropy':>8} | "
          f"{'MI_BP':>8} | {'MI_1':>8} | {'BP Gain':>8} | {'BSR':>8}")
    print("-" * 90)
    for r in all_results:
        print(f"{r['snr_n']:>8.0f} | {r['mean_l0_error']:>7.1%} | "
              f"{r['mean_l0_entropy']:>8.1f} | "
              f"{r['mi_bp']:>8.2f} | {r['mi_1_layer']:>8.2f} | "
              f"{r['bp_gain']:>7.2f}x | {r['mean_l0_bsr']:>7.1%}")

    print(f"\nResults saved to {out_file}")


if __name__ == "__main__":
    main()
