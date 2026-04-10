#!/usr/bin/env python3
"""Experiment I (NC1 Barrier): Is the input-layer barrier truly absolute?

Every "no L1" config tested so far gives MI=0 at SNR*N=5000.
This experiment tests at SNR*N=50,000 to determine if the barrier
is structural or merely a trace-cost multiplier.

Configs:
  NC1-A: L2+L3+L4+L5+L6+L7 (k=6, no L1) -- maximum info, just missing L1
  NC1-B: L2+L4+L6+L7 (k=4, no L1) -- typical config without L1

10 seeds each, SNR*N=50,000.

Reference: arXiv:2604.03813, Section 4.8.9.
"""

import json
import math
import multiprocessing
import time
from pathlib import Path

import numpy as np

from ntt_bp import (
    MLKEM_Q,
    simulate_attack,
    warmup_numba,
    wilson_ci,
)

try:
    from scipy.stats import beta as beta_dist

    def clopper_pearson_ci(k, n, alpha=0.05):
        if n == 0:
            return (0.0, 1.0)
        lo = float(beta_dist.ppf(alpha / 2, k, n - k + 1)) if k > 0 else 0.0
        hi = float(beta_dist.ppf(1 - alpha / 2, k + 1, n - k)) if k < n else 1.0
        return (round(lo, 4), round(hi, 4))
except ImportError:

    def clopper_pearson_ci(k, n, alpha=0.05):
        lo, hi = wilson_ci(k, n)
        return (round(lo, 4), round(hi, 4))


OUT_DIR = Path(__file__).parent.parent / "evidence"
SEED_BASE = 3_000_000


def _init_worker():
    warmup_numba()


def _run_trial(args):
    config_name, layers, seed, snr_n = args
    t0 = time.time()
    r = simulate_attack(snr_n=snr_n, seed=seed, max_bp_iter=30, observe_layers=layers)
    dt = time.time() - t0
    mi = max(0, math.log2(MLKEM_Q) - r["l0_avg_entropy"])
    return {
        "config": config_name,
        "layers": layers,
        "seed": seed,
        "snr_n": snr_n,
        "bsr": r["l0_bsr"],
        "full_key": r["l0_bsr"] == 1.0,
        "mi_bp": round(mi, 2),
        "entropy": round(r["l0_avg_entropy"], 2),
        "bp_iterations": r["bp_iterations"],
        "time_s": round(dt, 1),
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    progress_file = OUT_DIR / "nc1_moonshot_progress.json"

    # Load existing progress
    if progress_file.exists():
        with open(progress_file) as f:
            progress = json.load(f)
    else:
        progress = {"results": [], "completed_keys": set()}

    completed = {(r["config"], r["seed"]) for r in progress["results"]}

    configs = [
        ("NC1-A_L2-L7", [2, 3, 4, 5, 6, 7]),  # k=6, everything except L1
        ("NC1-B_L2+L4+L6+L7", [2, 4, 6, 7]),  # k=4, no L1
    ]

    jobs = []
    for name, layers in configs:
        for i in range(10):
            seed = SEED_BASE + i * 1000 + sum(l * 10 for l in layers)
            if (name, seed) not in completed:
                jobs.append((name, layers, seed, 50000))

    print("=" * 70)
    print("NC1 BARRIER: Is the input-layer barrier truly absolute?")
    print("=" * 70)
    print(f"  Configs: {len(configs)}")
    print(f"  Seeds per config: 10")
    print(f"  SNR*N: 50,000")
    print(f"  Pending: {len(jobs)} / 20 jobs")
    print(f"  Workers: 6")
    print()

    if not jobs:
        print("  All jobs complete!")
        _print_summary(progress["results"])
        return 0

    print("Warming up Numba JIT...")
    warmup_numba()

    ctx = multiprocessing.get_context("fork")
    t0 = time.time()
    n_done = len(progress["results"])
    n_total = 20

    with ctx.Pool(6, initializer=_init_worker) as pool:
        for result in pool.imap_unordered(_run_trial, jobs):
            n_done += 1
            elapsed = time.time() - t0
            remaining = n_total - n_done
            eta = elapsed / (n_done - len(completed)) * remaining if n_done > len(completed) else 0

            fk_str = "FK" if result["full_key"] else (
                f"BSR={result['bsr']:.1%}" if result["bsr"] > 0 else "MI=0"
            )
            print(f"  [{n_done}/{n_total}] {result['config']} "
                  f"seed={result['seed']}: "
                  f"BSR={result['bsr']:.1%} MI={result['mi_bp']:.2f} "
                  f"{result['time_s']:.0f}s [{fk_str}] "
                  f"(ETA: {eta/3600:.1f}h)")

            progress["results"].append(result)
            with open(progress_file, "w") as f:
                json.dump(progress, f, indent=2, default=str)

    total_time = time.time() - t0
    print(f"\n  Total: {total_time/3600:.1f}h")

    _print_summary(progress["results"])

    # Save final output
    out_file = OUT_DIR / "nc1_moonshot_results.json"
    with open(out_file, "w") as f:
        json.dump(progress["results"], f, indent=2, default=str)
    print(f"\n  Saved: {out_file}")

    return 0


def _print_summary(results):
    print("\n" + "=" * 70)
    print("NC1 BARRIER RESULTS")
    print("=" * 70)
    by_config = {}
    for r in results:
        by_config.setdefault(r["config"], []).append(r)

    for config, cr in sorted(by_config.items()):
        n = len(cr)
        fk = sum(1 for r in cr if r["full_key"])
        avg_mi = sum(r["mi_bp"] for r in cr) / n
        cp_ci = clopper_pearson_ci(fk, n)
        print(f"  {config}: {fk}/{n} FK [{cp_ci[0]:.1%}-{cp_ci[1]:.1%}] MI={avg_mi:.2f}")

    all_fk = sum(1 for r in results if r["full_key"])
    if all_fk == 0:
        print("\n  VERDICT: NC1 holds at SNR*N=50K. Input layer is a TRUE STRUCTURAL BARRIER.")
        print("  Claim: 'One absolute barrier exists -- the input layer must be observed.'")
    else:
        print(f"\n  VERDICT: NC1 BREAKS at SNR*N=50K ({all_fk}/{len(results)} FK).")
        print("  Claim: 'No barriers are absolute -- all are trace-cost multipliers.'")


if __name__ == "__main__":
    raise SystemExit(main())
