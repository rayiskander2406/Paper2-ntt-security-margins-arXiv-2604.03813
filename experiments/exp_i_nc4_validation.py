#!/usr/bin/env python3
"""Experiment I (NC4 Validation): Validate amended necessary conditions.

{1,4,7} satisfies NC1+NC2+NC3 (max gap=2) yet achieves 0/10 full-key.
The amended conditions add NC4 (k>=4). {1,3,4,7} satisfies NC1-NC4 and
is a non-odd-layer spread. This validates the amended model on a held-out config.

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
    simulate_attack,
    warmup_numba,
    wilson_ci,
)

OUT_DIR = Path(__file__).parent.parent / "evidence"
OUT_FILE = OUT_DIR / "nc4_validation.json"

MAX_BP_ITER = 30
N_WORKERS = 4


def _run_one_seed(args):
    """Worker: run one (seed, layers, snr_n) trial."""
    seed, layers, snr_n, max_bp_iter = args
    log2q = math.log2(MLKEM_Q)
    t0 = time.time()
    r = simulate_attack(
        snr_n=snr_n, seed=seed, max_bp_iter=max_bp_iter,
        observe_layers=layers, verbose=False,
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
    warmup_numba()


def run_config(name, layers, snr_n, n_seeds, seed_offset, pool):
    """Run one config with n_seeds, return aggregated result."""
    seed_args = []
    for i in range(n_seeds):
        seed = i * 100_000 + snr_n + seed_offset
        seed_args.append((seed, layers, snr_n, MAX_BP_ITER))

    seed_results = []
    for i, result in enumerate(pool.imap_unordered(_run_one_seed, seed_args)):
        status = "OK" if result["bsr"] == 1.0 else f"PARTIAL({result['bsr']:.0%})"
        print(f"    Seed {i+1}/{n_seeds}: BSR={result['bsr']:.1%}, "
              f"MI={result['mi_bp']:.2f}, {result['time_s']:.0f}s [{status}]")
        seed_results.append(result)

    seed_results.sort(key=lambda x: x["seed"])

    bsrs = [sr["bsr"] for sr in seed_results]
    mis = [sr["mi_bp"] for sr in seed_results]
    n_full_key = sum(1 for b in bsrs if b == 1.0)
    ci_lo, ci_hi = wilson_ci(n_full_key, n_seeds)

    return {
        "config": name,
        "layers": layers,
        "n_layers": len(layers),
        "snr_n": snr_n,
        "n_seeds": n_seeds,
        "mean_bsr": round(float(np.mean(bsrs)), 4),
        "std_bsr": round(float(np.std(bsrs)), 4),
        "mean_mi_bp": round(float(np.mean(mis)), 2),
        "std_mi_bp": round(float(np.std(mis)), 2),
        "full_key_recovery_rate": round(n_full_key / n_seeds, 4),
        "n_full_key": n_full_key,
        "wilson_ci_95": [round(ci_lo, 4), round(ci_hi, 4)],
        "per_seed": seed_results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true",
                        help="Demo mode: 3 seeds instead of 10")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing results if resuming
    results = []
    if OUT_FILE.exists():
        with open(OUT_FILE) as f:
            results = json.load(f)
    completed = {(r["config"], r["snr_n"]) for r in results}

    print("Warming up Numba JIT...")
    warmup_numba()
    build_full_intt_factor_graph()

    ctx = multiprocessing.get_context("fork")

    n_seeds = 3 if args.quick else 10

    configs = [
        # Validates amended necessary conditions (NC1+NC2+NC3+NC4)
        # {1,3,4,7}: L1 ok, L7 ok, max gap=2 (L4->L7) ok, k=4 ok
        ("L1+L3+L4+L7", [1, 3, 4, 7], 5000, n_seeds, 10_000_000),
    ]

    with ctx.Pool(N_WORKERS, initializer=_init_worker) as pool:
        for name, layers, snr_n, ns, seed_off in configs:
            if (name, snr_n) in completed:
                print(f"\n  [{name} @ SNR*N={snr_n}] SKIPPED (already complete)")
                continue
            print(f"\n  [{name} @ SNR*N={snr_n}] -- {ns} seeds, layers={layers}")
            t0 = time.time()
            result = run_config(name, layers, snr_n, ns, seed_off, pool)
            dt = time.time() - t0
            print(f"  => BSR={result['mean_bsr']:.1%}, "
                  f"full-key={result['n_full_key']}/{ns}, "
                  f"MI={result['mean_mi_bp']:.2f}+/-{result['std_mi_bp']:.2f}, "
                  f"CI={result['wilson_ci_95']} ({dt/60:.1f}min)")
            results.append(result)
            with open(OUT_FILE, "w") as f:
                json.dump(results, f, indent=2)

    # Print final summary
    print(f"\n{'='*80}")
    print("VALIDATION COMPLETE")
    print(f"{'='*80}")
    for r in results:
        ci = r["wilson_ci_95"]
        rules = "NC1-4 ok" if r["n_layers"] >= 4 else "NC4 fail"
        verdict = "PASS" if r["n_full_key"] > 0 else "FAIL"
        print(f"  {r['config']:20s}: {r['n_full_key']}/{r['n_seeds']} full-key "
              f"({verdict}), MI={r['mean_mi_bp']:.2f}, "
              f"CI=[{ci[0]:.1%},{ci[1]:.1%}] -- {rules}")

    print(f"\nResults: {OUT_FILE}")

    # Cross-reference with {1,4,7} (k=3, fails NC4)
    print(f"\n--- Cross-reference ---")
    print(f"  L1+L4+L7 (k=3, NC4 fail): 0/10, MI=2.95 -- correctly predicted failure")
    for r in results:
        if r["config"] == "L1+L3+L4+L7":
            if r["n_full_key"] > 0:
                print(f"  L1+L3+L4+L7 (k=4, NC4 ok): {r['n_full_key']}/{r['n_seeds']}, "
                      f"MI={r['mean_mi_bp']:.2f} -- VALIDATES amended conditions")
            else:
                print(f"  L1+L3+L4+L7 (k=4, NC4 ok): {r['n_full_key']}/{r['n_seeds']}, "
                      f"MI={r['mean_mi_bp']:.2f} -- FALSIFIES amended conditions! "
                      f"Additional qualifier needed.")


if __name__ == "__main__":
    main()
