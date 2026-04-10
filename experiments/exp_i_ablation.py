#!/usr/bin/env python3
"""Experiment I (Ablation): Multi-seed layer ablation study with multiprocessing.

Tests 14 layer configurations at SNR*N=5000, 10 seeds each, to determine
which layers are necessary for full-key recovery. Uses multiprocessing
for ~4x speedup.

Resumes from existing results. Each config's seeds run in parallel,
then results are saved incrementally before moving to the next config.

Use --quick for a demo run: 4 key configs x 3 seeds.

Reference: arXiv:2604.03813, Section 4.8.9, Table 8.
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
    simulate_attack,
    warmup_numba,
    wilson_ci,
)

OUT_DIR = Path(__file__).parent.parent / "evidence"

SNR_N = 5000
N_SEEDS = 10
MAX_BP_ITER = 30
N_WORKERS = 4  # 4 parallel workers; ~400 MB total (100 MB x 4)

CONFIGS = [
    ("L7 only", [7]),
    ("L1 only", [1]),
    ("L4 only", [4]),
    ("L1+L7", [1, 7]),
    ("L1+L4+L7", [1, 4, 7]),
    ("L1+L3+L5+L7", [1, 3, 5, 7]),
    ("L5-L7", [5, 6, 7]),
    ("L1-L3", [1, 2, 3]),
    ("L1-L4", [1, 2, 3, 4]),
    ("L1-L5", [1, 2, 3, 4, 5]),
    ("L1-L6", [1, 2, 3, 4, 5, 6]),
    ("All (L1-L7)", [1, 2, 3, 4, 5, 6, 7]),
    ("L1+L2+L3+L7", [1, 2, 3, 7]),
    ("L2+L4+L6", [2, 4, 6]),
]

QUICK_CONFIGS = [
    ("L1+L3+L5+L7", [1, 3, 5, 7]),
    ("L1-L4", [1, 2, 3, 4]),
    ("All (L1-L7)", [1, 2, 3, 4, 5, 6, 7]),
    ("L2+L4+L6", [2, 4, 6]),
]


def _run_one_seed(args):
    """Worker function: run one (config, seed) trial."""
    seed, layers, snr_n, max_bp_iter = args
    log2q = math.log2(MLKEM_Q)
    t0 = time.time()
    r = simulate_attack(
        snr_n=snr_n,
        seed=seed,
        max_bp_iter=max_bp_iter,
        observe_layers=layers,
        verbose=False,
    )
    dt = time.time() - t0
    mi = max(0, log2q - r["l0_avg_entropy"])
    return {
        "seed": seed,
        "bsr": r["l0_bsr"],
        "mi_bp": round(mi, 2),
        "entropy": round(r["l0_avg_entropy"], 2),
        "map_error": r["l0_map_error"],
        "bp_iterations": r["bp_iterations"],
        "time_s": round(dt, 1),
    }


def _init_worker():
    """Per-worker initializer: warm up Numba JIT in each subprocess."""
    warmup_numba()


def load_existing(results_file):
    if results_file.exists():
        with open(results_file) as f:
            return json.load(f)
    return []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true",
                        help="Demo mode: 4 key configs x 3 seeds")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.quick:
        configs = QUICK_CONFIGS
        n_seeds = 3
        out_file = OUT_DIR / "ablation_results_quick.json"
        print("\n*** QUICK MODE: 4 configs x 3 seeds ***\n")
    else:
        configs = CONFIGS
        n_seeds = N_SEEDS
        out_file = OUT_DIR / "ablation_results.json"

    # Warm up Numba in main process (also builds factor graph cache)
    print("Warming up Numba JIT in main process...")
    warmup_numba()
    factors = build_full_intt_factor_graph()
    print(f"Factor graph: {len(factors)} factors, "
          f"{(N_LAYERS + 1) * MLKEM_N} variables")

    existing = load_existing(out_file)
    completed_configs = {r["config"] for r in existing}
    remaining = [(i, name, layers) for i, (name, layers) in enumerate(configs)
                 if name not in completed_configs]

    print(f"\nResuming: {len(completed_configs)}/{len(configs)} configs complete")
    if completed_configs:
        print(f"Completed: {sorted(completed_configs)}")
    print(f"Remaining: {len(remaining)} configs, {len(remaining) * n_seeds} trials")
    print(f"Workers: {N_WORKERS}, estimated time: "
          f"~{len(remaining) * n_seeds * 10 / N_WORKERS / 60:.1f} hours")

    all_results = list(existing)

    print(f"\n{'=' * 80}")
    print(f"PARALLEL MULTI-SEED ABLATION STUDY")
    print(f"  SNR*N = {SNR_N}, {n_seeds} seeds/config, "
          f"{MAX_BP_ITER} BP iters, {N_WORKERS} workers")
    print(f"{'=' * 80}")

    # Use 'fork' start method to share Numba JIT cache with workers
    ctx = multiprocessing.get_context("fork")

    for ci, name, layers in remaining:
        print(f"\n--- {name} ({ci+1}/{len(configs)}): layers={layers} ---")

        # Build seed args for this config
        seed_args = []
        for seed_idx in range(n_seeds):
            seed = seed_idx * 100_000 + SNR_N + ci * 7919
            seed_args.append((seed, layers, SNR_N, MAX_BP_ITER))

        t_config = time.time()

        # Run seeds in parallel
        with ctx.Pool(N_WORKERS, initializer=_init_worker) as pool:
            seed_results = []
            for i, result in enumerate(pool.imap_unordered(_run_one_seed, seed_args)):
                status = "OK" if result["bsr"] == 1.0 else f"PARTIAL({result['bsr']:.0%})"
                print(f"  Seed {i+1}/{n_seeds}: BSR={result['bsr']:.1%}, "
                      f"MI={result['mi_bp']:.2f}, {result['time_s']:.0f}s [{status}]")
                seed_results.append(result)

        # Sort by seed for reproducibility
        seed_results.sort(key=lambda x: x["seed"])

        dt_config = time.time() - t_config

        # Aggregate
        bsrs = [sr["bsr"] for sr in seed_results]
        mis = [sr["mi_bp"] for sr in seed_results]
        entropies = [sr["entropy"] for sr in seed_results]
        n_full_key = sum(1 for b in bsrs if b == 1.0)
        ci_lo, ci_hi = wilson_ci(n_full_key, n_seeds)

        is_consecutive = (layers == list(range(1, len(layers) + 1)))

        config_result = {
            "config": name,
            "layers": layers,
            "n_layers": len(layers),
            "consecutive_from_l1": is_consecutive,
            "snr_n": SNR_N,
            "n_seeds": n_seeds,
            "mean_bsr": round(float(np.mean(bsrs)), 4),
            "std_bsr": round(float(np.std(bsrs)), 4),
            "mean_mi_bp": round(float(np.mean(mis)), 2),
            "std_mi_bp": round(float(np.std(mis)), 2),
            "mean_entropy": round(float(np.mean(entropies)), 2),
            "full_key_recovery_rate": round(n_full_key / n_seeds, 4),
            "n_full_key": n_full_key,
            "wilson_ci_95": [round(ci_lo, 4), round(ci_hi, 4)],
            "per_seed": seed_results,
        }
        all_results.append(config_result)

        print(f"  => mean BSR={config_result['mean_bsr']:.1%} +/- "
              f"{config_result['std_bsr']:.3f}, "
              f"MI={config_result['mean_mi_bp']:.2f} +/- "
              f"{config_result['std_mi_bp']:.2f}, "
              f"full-key={n_full_key}/{n_seeds} "
              f"CI=[{ci_lo:.1%}, {ci_hi:.1%}]  "
              f"({dt_config:.0f}s wall, {dt_config/60:.1f}min)")

        # Save incrementally
        with open(out_file, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"  Saved ({len(all_results)}/{len(configs)} configs)")

    # Final summary
    print(f"\n{'=' * 100}")
    print("MULTI-SEED ABLATION SUMMARY")
    print(f"{'=' * 100}")
    print(f"{'Config':>20} | {'Layers':>12} | {'N':>2} | {'Consec':>6} | "
          f"{'Mean BSR':>9} | {'Std':>6} | {'Full-Key':>8} | "
          f"{'Wilson CI':>18} | {'MI':>6}")
    print("-" * 100)
    for r in all_results:
        layers_str = ",".join(str(l) for l in r["layers"])
        ci = r["wilson_ci_95"]
        print(f"{r['config']:>20} | {layers_str:>12} | {r['n_layers']:>2} | "
              f"{'Yes' if r['consecutive_from_l1'] else 'No':>6} | "
              f"{r['mean_bsr']:>8.1%} | {r['std_bsr']:>5.3f} | "
              f"{r['n_full_key']:>3}/{r['n_seeds']:<2}   | "
              f"[{ci[0]:.1%},{ci[1]:.1%}] | "
              f"{r['mean_mi_bp']:>5.2f}")

    # Key comparison: Diversity vs Locality
    print(f"\n{'=' * 80}")
    print("KEY COMPARISON: Diversity vs Locality")
    print(f"{'=' * 80}")
    for name in ["L1+L3+L5+L7", "L1+L2+L3+L7", "L1-L4", "L1-L6",
                  "All (L1-L7)", "L2+L4+L6"]:
        matches = [r for r in all_results if r["config"] == name]
        if matches:
            r = matches[0]
            print(f"  {r['config']:>20}: full-key={r['n_full_key']}/{r['n_seeds']} "
                  f"({r['full_key_recovery_rate']:.0%}), "
                  f"mean BSR={r['mean_bsr']:.1%}, MI={r['mean_mi_bp']:.2f}")
        else:
            print(f"  {name:>20}: NOT RUN")

    print(f"\nResults saved to {out_file}")


if __name__ == "__main__":
    main()
