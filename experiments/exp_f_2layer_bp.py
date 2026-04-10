#!/usr/bin/env python3
"""Experiment F: Belief Propagation on 2-layer NTT subgraph.

Demonstrates BP entropy reduction on a minimal NTT factor graph
(2 layers, 8 coefficients, 4 butterflies).

Reference: arXiv:2604.03813, Section 4.8.6.
"""

import json
import math
import time
from pathlib import Path

import numpy as np

from ntt_bp import (
    MLKEM_Q,
    build_full_intt_factor_graph,
    compute_full_intt,
    generate_observations,
    run_bp,
    warmup_numba,
)

OUT_DIR = Path(__file__).parent.parent / "evidence"
LOG2Q = math.log2(MLKEM_Q)

# Minimal subgraph parameters
N_SMALL = 8
N_LAYERS_SMALL = 2


def run_2layer_bp(snr_n: float, seed: int, max_bp_iter: int = 30) -> dict:
    """Run BP on a 2-layer, 8-coefficient INTT subgraph."""
    rng = np.random.default_rng(seed)
    q = MLKEM_Q
    n = N_SMALL
    n_layers = N_LAYERS_SMALL
    snr = 1.0
    n_traces = int(snr_n / snr)

    # Random secret in NTT domain
    secret_ntt = rng.integers(0, q, size=n).astype(np.int64)
    intermediates = compute_full_intt(secret_ntt, n, n_layers)

    true_values = {}
    for layer_idx in range(n_layers + 1):
        for i in range(n):
            true_values[layer_idx * n + i] = int(intermediates[layer_idx][i])

    factors = build_full_intt_factor_graph(n, n_layers)

    # Observe layers 1 and 2
    observe_layers = [1, 2]
    observed_vars = {}
    for layer_idx in observe_layers:
        for i in range(n):
            observed_vars[layer_idx * n + i] = true_values[layer_idx * n + i]

    observations = generate_observations(observed_vars, snr, n_traces, rng, q)

    n_vars = (n_layers + 1) * n
    t0 = time.time()
    beliefs, n_iter, entropy_hist = run_bp(
        n_vars, factors, observations,
        max_iterations=max_bp_iter, damping=0.5, q=q,
        verbose=False, n_coeffs=n,
    )
    bp_time = time.time() - t0

    # Evaluate Layer 0
    l0_correct = 0
    l0_entropies = []
    for i in range(n):
        true_val = true_values[i]
        b = beliefs[i]
        if int(np.argmax(b)) == true_val:
            l0_correct += 1
        p_safe = np.maximum(b, 1e-30)
        ent = -float(np.sum(b * np.log2(p_safe)))
        l0_entropies.append(ent)

    avg_entropy = float(np.mean(l0_entropies))
    mi_bp = max(0, LOG2Q - avg_entropy)

    return {
        "snr_n": snr_n,
        "seed": seed,
        "n_coeffs": n,
        "n_layers": n_layers,
        "n_factors": len(factors),
        "bp_iterations": n_iter,
        "bp_time_s": round(bp_time, 3),
        "l0_bsr": round(l0_correct / n, 4),
        "l0_avg_entropy": round(avg_entropy, 3),
        "mi_bp": round(mi_bp, 4),
        "mi_gain_over_prior": round(mi_bp, 4),  # prior is uniform = 0 MI
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    warmup_numba()

    # Verify factor graph size
    factors = build_full_intt_factor_graph(N_SMALL, N_LAYERS_SMALL)
    n_vars = (N_LAYERS_SMALL + 1) * N_SMALL
    print("=" * 60)
    print("EXPERIMENT F: 2-Layer BP on Minimal NTT Subgraph")
    print("=" * 60)
    print(f"  Coefficients: {N_SMALL}")
    print(f"  Layers: {N_LAYERS_SMALL}")
    print(f"  Factors: {len(factors)}")
    print(f"  Variables: {n_vars}")
    print(f"  log2(q) = {LOG2Q:.4f} bits")
    print()

    snr_n_values = [300, 1000, 3000, 10000, 30000]
    n_seeds = 5

    all_results = []

    print(f"{'SNR*N':>8} | {'Entropy':>8} | {'MI_BP':>8} | {'BSR':>8} | {'Time':>6}")
    print("-" * 50)

    for snr_n in snr_n_values:
        seed_results = []
        for s in range(n_seeds):
            seed = s * 1000 + int(snr_n)
            r = run_2layer_bp(snr_n, seed)
            seed_results.append(r)

        avg_entropy = float(np.mean([r["l0_avg_entropy"] for r in seed_results]))
        avg_mi = float(np.mean([r["mi_bp"] for r in seed_results]))
        avg_bsr = float(np.mean([r["l0_bsr"] for r in seed_results]))
        avg_time = float(np.mean([r["bp_time_s"] for r in seed_results]))

        point = {
            "snr_n": snr_n,
            "n_seeds": n_seeds,
            "mean_entropy": round(avg_entropy, 3),
            "mean_mi_bp": round(avg_mi, 4),
            "mean_bsr": round(avg_bsr, 4),
            "mean_time_s": round(avg_time, 3),
            "per_seed": seed_results,
        }
        all_results.append(point)

        print(f"{snr_n:>8} | {avg_entropy:>8.2f} | {avg_mi:>8.2f} | "
              f"{avg_bsr:>7.1%} | {avg_time:>5.3f}s")

    # Expected: ~3.9-bit gain at SNR*N=10^4
    high_snr = next((r for r in all_results if r["snr_n"] == 10000), None)
    if high_snr:
        print(f"\n  MI gain at SNR*N=10000: {high_snr['mean_mi_bp']:.2f} bits")
        print(f"  (Expected: ~3.9 bits for 2-layer subgraph)")

    # Save
    output = {
        "experiment": "F: 2-Layer BP on Minimal NTT Subgraph",
        "reference": "arXiv:2604.03813, Section 4.8.6",
        "parameters": {
            "n_coeffs": N_SMALL,
            "n_layers": N_LAYERS_SMALL,
            "q": MLKEM_Q,
            "log2_q": round(LOG2Q, 4),
        },
        "results": all_results,
    }
    out_file = OUT_DIR / "exp_f_2layer_bp.json"
    with open(out_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to {out_file}")


if __name__ == "__main__":
    main()
