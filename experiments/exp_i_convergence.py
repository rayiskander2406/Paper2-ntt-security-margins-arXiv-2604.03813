#!/usr/bin/env python3
"""Experiment I (Convergence): Multi-seed BP convergence analysis.

Validates that 30 BP iterations are sufficient for convergence across
the full SNR*N range. Records entropy trajectories and measures
iterations to convergence (delta < threshold) and iterations to
90%/95%/99% of final MI extraction.

Reference: arXiv:2604.03813, Section 4.8.9.
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
    simulate_attack,
    warmup_numba,
)

OUT_DIR = Path(__file__).parent.parent / "evidence"
OUT_FILE = OUT_DIR / "convergence_results.json"

LOG2Q = math.log2(MLKEM_Q)  # ~11.70

# 6 SNR*N points spanning the full transition region + plateau
SNR_N_VALUES = [500, 1000, 2000, 3000, 5000, 10000]
N_SEEDS = 3
MAX_BP_ITER = 30


def entropy_to_mi(entropy: float) -> float:
    """Convert L0 average entropy to mutual information."""
    return max(0.0, LOG2Q - entropy)


def find_convergence_iteration(entropy_history: list[float],
                                delta_threshold: float = 1e-2) -> int | None:
    """Find first iteration where entropy change < threshold.

    Returns iteration number (1-indexed) or None if never converged.
    Uses absolute entropy change since entropy is in bits (bounded 0-11.7).
    """
    for i in range(1, len(entropy_history)):
        delta = abs(entropy_history[i] - entropy_history[i - 1])
        if delta < delta_threshold:
            return i + 1  # 1-indexed
    return None


def find_mi_fraction_iteration(entropy_history: list[float],
                                fraction: float) -> int | None:
    """Find first iteration where MI reaches given fraction of final MI.

    Returns iteration number (1-indexed) or None if never reached.
    """
    final_mi = entropy_to_mi(entropy_history[-1])
    if final_mi < 0.01:
        return None  # No MI extracted

    target_mi = fraction * final_mi
    for i, ent in enumerate(entropy_history):
        mi = entropy_to_mi(ent)
        if mi >= target_mi:
            return i + 1  # 1-indexed
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true",
                        help="Demo mode: 3 SNR*N points x 2 seeds x 10 iters")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    warmup_numba()
    # Pre-build factor graph (reused across all calls internally)
    factors = build_full_intt_factor_graph()
    print(f"Factor graph: {len(factors)} factors, "
          f"{(N_LAYERS + 1) * MLKEM_N} variables")

    if args.quick:
        snr_n_values = [1000, 3000, 10000]
        n_seeds = 2
        max_bp_iter = 10
        out_file = OUT_DIR / "convergence_results_quick.json"
        print("\n*** QUICK MODE: 3 points x 2 seeds x 10 iters ***\n")
    else:
        snr_n_values = SNR_N_VALUES
        n_seeds = N_SEEDS
        max_bp_iter = MAX_BP_ITER
        out_file = OUT_FILE

    all_results = []

    print(f"\n{'=' * 90}")
    print(f"MULTI-SEED CONVERGENCE ANALYSIS")
    print(f"  {len(snr_n_values)} SNR*N points, {n_seeds} seeds each, "
          f"{max_bp_iter} max iterations")
    print(f"{'=' * 90}")

    for snr_n in snr_n_values:
        print(f"\n--- SNR*N = {snr_n} ---")
        trials = []

        for seed_idx in range(n_seeds):
            seed = seed_idx * 100_000 + int(snr_n) + 77777  # avoid sweep seeds
            t0 = time.time()
            r = simulate_attack(
                snr_n=snr_n, seed=seed, max_bp_iter=max_bp_iter, verbose=False,
            )
            dt = time.time() - t0

            eh = r["entropy_history"]
            final_mi = entropy_to_mi(eh[-1])

            # Convergence thresholds (entropy delta in bits)
            conv_001 = find_convergence_iteration(eh, 0.01)
            conv_01 = find_convergence_iteration(eh, 0.1)
            conv_05 = find_convergence_iteration(eh, 0.5)

            # MI fraction milestones
            mi_50 = find_mi_fraction_iteration(eh, 0.50)
            mi_80 = find_mi_fraction_iteration(eh, 0.80)
            mi_90 = find_mi_fraction_iteration(eh, 0.90)
            mi_95 = find_mi_fraction_iteration(eh, 0.95)
            mi_99 = find_mi_fraction_iteration(eh, 0.99)

            trial_data = {
                "seed": seed,
                "bsr": r["l0_bsr"],
                "bp_iterations": r["bp_iterations"],
                "final_entropy": round(eh[-1], 3),
                "final_mi": round(final_mi, 2),
                "entropy_history": eh,
                "iter_to_conv_delta_001": conv_001,
                "iter_to_conv_delta_01": conv_01,
                "iter_to_conv_delta_05": conv_05,
                "iter_to_mi_50pct": mi_50,
                "iter_to_mi_80pct": mi_80,
                "iter_to_mi_90pct": mi_90,
                "iter_to_mi_95pct": mi_95,
                "iter_to_mi_99pct": mi_99,
                "time_s": round(dt, 1),
            }
            trials.append(trial_data)

            status = "FULL" if r["l0_bsr"] == 1.0 else f"BSR={r['l0_bsr']:.0%}"
            print(f"  Seed {seed_idx+1}/{n_seeds}: {status}, "
                  f"MI={final_mi:.2f}b, "
                  f"conv(d<0.01)={conv_001 or '>30'}, "
                  f"90%MI@iter={mi_90 or 'N/A'}, "
                  f"{dt:.0f}s")

        # Aggregate per SNR*N
        def safe_stats(values):
            """Compute mean/std/min/max, filtering None values."""
            valid = [v for v in values if v is not None]
            if not valid:
                return {"mean": None, "std": None, "min": None, "max": None,
                        "n_valid": 0, "n_total": len(values)}
            return {
                "mean": round(float(np.mean(valid)), 1),
                "std": round(float(np.std(valid)), 1),
                "min": int(min(valid)),
                "max": int(max(valid)),
                "n_valid": len(valid),
                "n_total": len(values),
            }

        conv_001_vals = [t["iter_to_conv_delta_001"] for t in trials]
        conv_01_vals = [t["iter_to_conv_delta_01"] for t in trials]
        mi_90_vals = [t["iter_to_mi_90pct"] for t in trials]
        mi_95_vals = [t["iter_to_mi_95pct"] for t in trials]
        mi_99_vals = [t["iter_to_mi_99pct"] for t in trials]

        snr_result = {
            "snr_n": snr_n,
            "n_seeds": n_seeds,
            "mean_bsr": round(float(np.mean([t["bsr"] for t in trials])), 4),
            "n_full_recovery": sum(1 for t in trials if t["bsr"] == 1.0),
            "convergence_delta_001": safe_stats(conv_001_vals),
            "convergence_delta_01": safe_stats(conv_01_vals),
            "iter_to_90pct_mi": safe_stats(mi_90_vals),
            "iter_to_95pct_mi": safe_stats(mi_95_vals),
            "iter_to_99pct_mi": safe_stats(mi_99_vals),
            "per_seed": trials,
        }
        all_results.append(snr_result)

        # Print summary
        cs = snr_result["convergence_delta_001"]
        ms = snr_result["iter_to_90pct_mi"]
        conv_str = (f"{cs['mean']:.0f} +/- {cs['std']:.0f} "
                    f"({cs['n_valid']}/{cs['n_total']} converged)"
                    if cs["mean"] is not None else "did not converge")
        mi90_str = (f"{ms['mean']:.0f} +/- {ms['std']:.0f}"
                    if ms["mean"] is not None else "N/A")
        print(f"  => conv(d<0.01): {conv_str}")
        print(f"  => 90% MI reached at iter: {mi90_str}")

        # Save incrementally
        with open(out_file, "w") as f:
            json.dump(all_results, f, indent=2)

    # Final summary table
    print(f"\n{'=' * 100}")
    print("CONVERGENCE SUMMARY")
    print(f"{'=' * 100}")
    print(f"{'SNR*N':>8} | {'BSR':>6} | {'Full':>4} | "
          f"{'Conv d<0.01':>15} | {'Conv d<0.1':>15} | "
          f"{'90% MI':>10} | {'95% MI':>10} | {'99% MI':>10}")
    print("-" * 100)

    for r in all_results:
        def fmt(stats):
            if stats["mean"] is None:
                return f"{'N/C':>10}"
            return f"{stats['mean']:>5.0f}+/-{stats['std']:<4.0f}"

        c001 = fmt(r["convergence_delta_001"])
        c01 = fmt(r["convergence_delta_01"])
        m90 = fmt(r["iter_to_90pct_mi"])
        m95 = fmt(r["iter_to_95pct_mi"])
        m99 = fmt(r["iter_to_99pct_mi"])

        print(f"{r['snr_n']:>8} | {r['mean_bsr']:>5.0%} | "
              f"{r['n_full_recovery']:>2}/{r['n_seeds']:<1} | "
              f"{c001} | {c01} | {m90} | {m95} | {m99}")

    # Key findings
    print(f"\n{'=' * 80}")
    print("KEY FINDINGS")
    print(f"{'=' * 80}")

    # Check if 30 iterations is sufficient
    all_conv = []
    for r in all_results:
        for t in r["per_seed"]:
            if t["iter_to_conv_delta_001"] is not None:
                all_conv.append(t["iter_to_conv_delta_001"])

    if all_conv:
        print(f"\n1. Convergence (d<0.01 bits):")
        print(f"   Range: {min(all_conv)}-{max(all_conv)} iterations "
              f"(mean={np.mean(all_conv):.1f}, std={np.std(all_conv):.1f})")
        budget = max_bp_iter
        print(f"   {budget}-iteration budget "
              f"{'SUFFICIENT' if max(all_conv) <= budget else 'INSUFFICIENT'} "
              f"(max observed: {max(all_conv)})")
    else:
        print("\n1. No trials converged to d<0.01 -- check threshold or iteration budget")

    # MI extraction speed
    all_mi90 = []
    for r in all_results:
        for t in r["per_seed"]:
            if t["iter_to_mi_90pct"] is not None:
                all_mi90.append(t["iter_to_mi_90pct"])

    if all_mi90:
        print(f"\n2. MI extraction speed (90% of final):")
        print(f"   Range: {min(all_mi90)}-{max(all_mi90)} iterations "
              f"(mean={np.mean(all_mi90):.1f}, std={np.std(all_mi90):.1f})")

    # Per-regime summary
    print(f"\n3. Per-regime convergence:")
    for r in all_results:
        cs = r["convergence_delta_001"]
        if cs["mean"] is not None:
            print(f"   SNR*N={r['snr_n']:>5}: {cs['mean']:.0f} +/- {cs['std']:.0f} "
                  f"iterations ({cs['n_valid']}/{cs['n_total']} converged)")
        else:
            print(f"   SNR*N={r['snr_n']:>5}: did not converge within {max_bp_iter} iterations")

    print(f"\nResults saved to {out_file}")


if __name__ == "__main__":
    main()
