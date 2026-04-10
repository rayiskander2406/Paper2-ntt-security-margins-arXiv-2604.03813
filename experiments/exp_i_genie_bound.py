#!/usr/bin/env python3
"""Experiment I (Genie Bound): Upper bound on BP mutual information.

The genie-aided bound assumes perfect knowledge of all intermediate
layers. Each observed layer then provides independent information about
the Layer 0 coefficients, giving:

  MI_genie = min(log2(q), N_layers * MI_1_layer(snr_n))

This tells us the maximum MI that any BP algorithm could extract,
and lets us measure BP efficiency = MI_BP / MI_genie.

Reference: arXiv:2604.03813, Section 4.8.9 genie-aided bound.
"""

import json
import math
from pathlib import Path

import numpy as np

from ntt_bp import MLKEM_Q, N_LAYERS
from ntt_bp.statistics import compute_exact_mi_numerical

OUT_DIR = Path(__file__).parent.parent / "evidence"
LOG2Q = math.log2(MLKEM_Q)


def compute_genie_bound(snr_n: float, n_layers: int = N_LAYERS) -> dict:
    """Compute genie-aided MI bound.

    The genie gives perfect knowledge of all intermediate variables.
    Each observed layer then provides independent information about
    the Layer 0 coefficients.
    """
    # Single-layer MI
    mi_data = compute_exact_mi_numerical(snr_n, n_mc=200000, seed=42)
    mi_1_layer = mi_data["MI_exact"]

    # With genie aid from all layers, total MI is bounded by:
    # sum of MI from each layer (independent given genie)
    mi_genie_sum = n_layers * mi_1_layer

    # Capped at log2(q)
    mi_genie = min(LOG2Q, mi_genie_sum)

    # For partial layer counts
    partial_bounds = {}
    for k in range(1, n_layers + 1):
        mi_k = min(LOG2Q, k * mi_1_layer)
        partial_bounds[str(k)] = round(mi_k, 4)

    # BSR bound: if MI_genie > log2(q) - 1, MAP decoder likely succeeds
    bsr_threshold = LOG2Q - 1  # ~10.7 bits

    return {
        "snr_n": snr_n,
        "MI_1_layer": round(mi_1_layer, 4),
        "MI_genie_7_layers": round(mi_genie, 4),
        "MI_genie_sum_raw": round(mi_genie_sum, 4),
        "MI_max": round(LOG2Q, 4),
        "fraction_of_max": round(mi_genie / LOG2Q, 4),
        "partial_bounds_by_n_layers": partial_bounds,
        "recovery_possible": mi_genie > bsr_threshold,
        "snr_n_for_full_recovery": None,  # filled below
    }


def find_critical_snr_n() -> float:
    """Find SNR*N where genie bound first reaches log2(q).

    7 * MI_1(snr_n) >= log2(q)
    MI_1(snr_n) >= log2(q) / 7 = 11.70 / 7 = 1.671 bits

    Binary search for the SNR*N where MI_1_layer = log2(q)/7.
    """
    target = LOG2Q / N_LAYERS

    lo, hi = 1.0, 100000.0
    while hi - lo > 1:
        mid = (lo + hi) / 2
        mi = compute_exact_mi_numerical(mid, n_mc=50000, seed=42)["MI_exact"]
        if mi < target:
            lo = mid
        else:
            hi = mid

    return round((lo + hi) / 2, 0)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("GENIE-AIDED BOUND")
    print("=" * 70)
    print(f"  log2(q) = {LOG2Q:.4f} bits")
    print(f"  Target MI per layer = {LOG2Q / N_LAYERS:.4f} bits")

    # Find critical SNR*N
    print("\nFinding critical SNR*N (genie bound reaches log2(q))...")
    critical_snr_n = find_critical_snr_n()
    print(f"  Critical SNR*N = {critical_snr_n:.0f}")
    print(f"  (7 layers x {LOG2Q/N_LAYERS:.2f} bits/layer = {LOG2Q:.2f} bits)")

    # Compute bounds at standard SNR points
    snr_n_values = [300, 500, 1000, 1500, 2000, 2500, 3000, 5000, 7000, 10000]

    results = []
    print(f"\n{'SNR*N':>8} | {'MI_1':>7} | {'MI_genie':>8} | {'MI_max':>7} | {'%max':>5} | {'Recovery':>8}")
    print("-" * 65)

    for snr_n in snr_n_values:
        r = compute_genie_bound(snr_n)
        r["snr_n_for_full_recovery"] = critical_snr_n
        results.append(r)

        print(f"{snr_n:>8.0f} | {r['MI_1_layer']:>7.2f} | {r['MI_genie_7_layers']:>8.2f} | "
              f"{r['MI_max']:>7.2f} | {r['fraction_of_max']*100:>4.0f}% | "
              f"{'YES' if r['recovery_possible'] else 'no':>8}")

    # Compute the BP gain = MI_BP / MI_genie for comparison with actual BP results
    print(f"\nGenie-aided bound interpretation:")
    print(f"  - At SNR*N >= {critical_snr_n:.0f}, the genie bound reaches log2(q)")
    print(f"  - Below this, even perfect BP cannot recover all coefficients")
    print(f"  - The actual BP achieves MI_BP < MI_genie (loopy BP is suboptimal)")
    print(f"  - BP efficiency = MI_BP / MI_genie measures how close BP is to optimal")

    # Layer count analysis
    print(f"\nMinimum layers needed for recovery (genie bound):")
    for snr_n in [1000, 2000, 3000, 5000, 10000]:
        mi1 = compute_exact_mi_numerical(snr_n, n_mc=100000, seed=42)["MI_exact"]
        min_layers = math.ceil(LOG2Q / mi1) if mi1 > 0 else float('inf')
        print(f"  SNR*N={snr_n:>6.0f}: MI_1={mi1:.2f}b, need >= {min_layers} layers "
              f"({'achievable' if min_layers <= 7 else 'not achievable with 7 layers'})")

    # Save
    output = {
        "critical_snr_n": critical_snr_n,
        "log2_q": round(LOG2Q, 4),
        "n_layers": N_LAYERS,
        "target_mi_per_layer": round(LOG2Q / N_LAYERS, 4),
        "results": results,
    }
    out_file = OUT_DIR / "genie_bound.json"
    with open(out_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to {out_file}")


if __name__ == "__main__":
    main()
