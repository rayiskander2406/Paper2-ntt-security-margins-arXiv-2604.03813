#!/usr/bin/env python3
"""Experiment I (Damping): BP convergence sensitivity to damping factor.

Tests BP at SNR*N = 3000 (the recovery threshold) with damping values
{0.1, 0.3, 0.5, 0.7, 0.9}, 5 seeds each. Since simulate_attack()
hardcodes damping=0.5, this script calls lower-level components directly.

Reference: arXiv:2604.03813, Section 4.8.9.
"""

import argparse
import json
import math
import multiprocessing
import time
from pathlib import Path

import numpy as np

from ntt_bp import (
    MLKEM_N,
    MLKEM_Q,
    N_LAYERS,
    build_full_intt_factor_graph,
    compute_full_intt,
    generate_observations,
    run_bp,
    warmup_numba,
    wilson_ci,
)

OUT_DIR = Path(__file__).parent.parent / "evidence"
OUT_FILE = OUT_DIR / "damping_sensitivity.json"

MAX_BP_ITER = 30
N_WORKERS = 4
SNR_N = 3000
N_SEEDS = 5
DAMPING_VALUES = [0.1, 0.3, 0.5, 0.7, 0.9]


def _simulate_attack_custom_damping(
    snr_n: float,
    seed: int,
    max_bp_iter: int,
    damping: float,
    observe_layers: list[int] | None = None,
    verbose: bool = False,
) -> dict:
    """Reproduce simulate_attack logic but with configurable damping."""
    rng = np.random.default_rng(seed)
    q = MLKEM_Q
    n = MLKEM_N
    n_layers = N_LAYERS
    snr = 1.0
    n_traces = int(snr_n / snr)

    secret_ntt = rng.integers(0, q, size=n).astype(np.int64)
    intermediates = compute_full_intt(secret_ntt, n, n_layers)

    true_values = {}
    for layer_idx in range(n_layers + 1):
        for i in range(n):
            true_values[layer_idx * n + i] = int(intermediates[layer_idx][i])

    factors = build_full_intt_factor_graph(n, n_layers)

    if observe_layers is None:
        observe_layers = list(range(1, n_layers + 1))

    observed_vars = {}
    for layer_idx in observe_layers:
        for i in range(n):
            observed_vars[layer_idx * n + i] = true_values[layer_idx * n + i]

    observations = generate_observations(observed_vars, snr, n_traces, rng, q)

    n_vars = (n_layers + 1) * n
    t0 = time.time()
    beliefs, n_iter, entropy_hist = run_bp(
        n_vars, factors, observations,
        max_iterations=max_bp_iter, damping=damping, q=q,
        verbose=verbose, n_coeffs=n,
    )
    bp_time = time.time() - t0

    # Evaluate Layer 0
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

    return {
        "snr_n": snr_n,
        "seed": seed,
        "damping": damping,
        "bp_iterations": n_iter,
        "bp_time_s": round(bp_time, 1),
        "l0_bsr": round(l0_correct / n, 4),
        "l0_avg_entropy": round(float(np.mean(l0_entropies)), 2),
        "l0_median_rank": round(float(np.median(l0_ranks)), 1),
    }


def _run_one_seed(args):
    """Worker: run one (seed, damping) trial."""
    seed, damping, snr_n, max_bp_iter = args
    log2q = math.log2(MLKEM_Q)
    t0 = time.time()
    r = _simulate_attack_custom_damping(
        snr_n=snr_n, seed=seed, max_bp_iter=max_bp_iter,
        damping=damping, verbose=False,
    )
    dt = time.time() - t0
    mi = max(0, log2q - r["l0_avg_entropy"])
    return {
        "seed": seed,
        "damping": damping,
        "bsr": r["l0_bsr"],
        "mi_bp": round(mi, 2),
        "entropy": round(r["l0_avg_entropy"], 2),
        "bp_iterations": r["bp_iterations"],
        "time_s": round(dt, 1),
    }


def _init_worker():
    warmup_numba()


def run_damping_config(damping, snr_n, n_seeds, pool):
    """Run one damping value with n_seeds, return aggregated result."""
    seed_args = []
    for i in range(n_seeds):
        seed = i * 100_000 + int(snr_n) + int(damping * 1000)
        seed_args.append((seed, damping, snr_n, MAX_BP_ITER))

    seed_results = []
    for i, result in enumerate(pool.imap_unordered(_run_one_seed, seed_args)):
        status = "OK" if result["bsr"] == 1.0 else f"PARTIAL({result['bsr']:.0%})"
        print(f"    Seed {i+1}/{n_seeds}: damping={damping}, BSR={result['bsr']:.1%}, "
              f"MI={result['mi_bp']:.2f}, iters={result['bp_iterations']}, "
              f"{result['time_s']:.0f}s [{status}]")
        seed_results.append(result)

    seed_results.sort(key=lambda x: x["seed"])

    bsrs = [sr["bsr"] for sr in seed_results]
    mis = [sr["mi_bp"] for sr in seed_results]
    iters = [sr["bp_iterations"] for sr in seed_results]
    n_full_key = sum(1 for b in bsrs if b == 1.0)
    ci_lo, ci_hi = wilson_ci(n_full_key, n_seeds)

    return {
        "damping": damping,
        "snr_n": snr_n,
        "n_seeds": n_seeds,
        "mean_bsr": round(float(np.mean(bsrs)), 4),
        "full_key_rate": round(n_full_key / n_seeds, 4),
        "n_full_key": n_full_key,
        "wilson_ci_95": [round(ci_lo, 4), round(ci_hi, 4)],
        "mean_mi": round(float(np.mean(mis)), 2),
        "mean_bp_iters": round(float(np.mean(iters)), 1),
        "per_seed": seed_results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true",
                        help="Demo mode: 3 damping values x 2 seeds")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.quick:
        damping_values = [0.3, 0.5, 0.7]
        n_seeds = 2
        out_file = OUT_DIR / "damping_sensitivity_quick.json"
        print("\n*** QUICK MODE: 3 damping values x 2 seeds ***\n")
    else:
        damping_values = DAMPING_VALUES
        n_seeds = N_SEEDS
        out_file = OUT_FILE

    # Load existing results if resuming
    results = []
    if out_file.exists():
        with open(out_file) as f:
            results = json.load(f)
    completed_dampings = {r["damping"] for r in results}

    print("=" * 70)
    print(f"DAMPING SENSITIVITY @ SNR*N = {SNR_N}")
    print(f"  Damping values: {damping_values}")
    print(f"  Seeds per value: {n_seeds}")
    print(f"  Total trials: {len(damping_values) * n_seeds}")
    print("=" * 70)

    print("\nWarming up Numba JIT...")
    warmup_numba()
    build_full_intt_factor_graph()

    ctx = multiprocessing.get_context("fork")

    with ctx.Pool(N_WORKERS, initializer=_init_worker) as pool:
        for damping in damping_values:
            if damping in completed_dampings:
                print(f"\n  [damping={damping}] SKIPPED (already complete)")
                continue
            print(f"\n  [damping={damping}] -- {n_seeds} seeds @ SNR*N={SNR_N}")
            t0 = time.time()
            result = run_damping_config(damping, SNR_N, n_seeds, pool)
            dt = time.time() - t0
            print(f"  => BSR={result['mean_bsr']:.1%}, "
                  f"full-key={result['n_full_key']}/{n_seeds}, "
                  f"MI={result['mean_mi']:.2f}, "
                  f"mean_iters={result['mean_bp_iters']:.1f}, "
                  f"CI={result['wilson_ci_95']} ({dt/60:.1f}min)")
            results.append(result)
            with open(out_file, "w") as f:
                json.dump(results, f, indent=2)

    # Print summary table
    results.sort(key=lambda x: x["damping"])
    print(f"\n{'='*70}")
    print("DAMPING SENSITIVITY SUMMARY")
    print(f"{'='*70}")
    print(f"  {'Damping':>8} {'BSR':>8} {'Full-Key':>10} {'MI':>6} {'Iters':>6} {'CI 95%':>20}")
    print(f"  {'-'*8} {'-'*8} {'-'*10} {'-'*6} {'-'*6} {'-'*20}")
    for r in results:
        ci = r["wilson_ci_95"]
        print(f"  {r['damping']:>8.1f} {r['mean_bsr']:>7.1%} "
              f"{r['n_full_key']}/{r['n_seeds']:>3}      "
              f"{r['mean_mi']:>5.2f} {r['mean_bp_iters']:>5.1f} "
              f"[{ci[0]:.1%},{ci[1]:.1%}]")

    # Key finding
    best = max(results, key=lambda r: r["mean_bsr"])
    print(f"\n  Best damping: {best['damping']} "
          f"(BSR={best['mean_bsr']:.1%}, MI={best['mean_mi']:.2f})")

    default = next((r for r in results if r["damping"] == 0.5), None)
    if default:
        print(f"  Default (0.5): BSR={default['mean_bsr']:.1%}, MI={default['mean_mi']:.2f}")
        if best["damping"] != 0.5:
            delta = best["mean_bsr"] - default["mean_bsr"]
            print(f"  Delta: {delta:+.1%} BSR improvement with damping={best['damping']}")
        else:
            print(f"  Default is optimal (or tied for best)")

    print(f"\nResults: {out_file}")


if __name__ == "__main__":
    main()
