#!/usr/bin/env python3
"""Experiment I (Key Enumeration): Recover full keys from partial BP successes.

At SNR*N = 1500, BP achieves ~85% full-key recovery. For the ~15% failures,
this experiment tests whether key enumeration (brute-forcing the most uncertain
coefficients) can push the success rate higher.

Approach:
  1. Run BP (30 iterations, damping 0.5)
  2. If BSR < 1.0: extract posterior for each Layer 0 coefficient
  3. Sort by posterior entropy (descending = most uncertain first)
  4. For top-K most uncertain coefficients, take top-M candidates from posterior
  5. Enumerate all M^K combinations (up to budget), verify each by computing
     INTT and checking Layer 7 output against ground truth

Parameters:
  K_max = 20 (max coefficients to enumerate over)
  M = 3 (top candidates per uncertain coefficient)
  budget = 2^20 (max enumeration attempts)

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
OUT_FILE = OUT_DIR / "key_enumeration_results.json"

MAX_BP_ITER = 30
N_WORKERS = 3
SNR_N = 1500
N_TRIALS = 20
K_MAX = 20     # Max coefficients to enumerate
M_CAND = 3     # Top candidates per coefficient
BUDGET = 2**20  # Max enumeration operations


def _run_single_trial(args):
    """Worker: run one trial with BP + optional key enumeration."""
    trial_idx, seed, snr_n = args
    rng = np.random.default_rng(seed)
    q = MLKEM_Q
    n = MLKEM_N
    n_layers = N_LAYERS
    log2q = math.log2(q)
    snr = 1.0
    n_traces = int(snr_n / snr)

    t0_total = time.time()

    # Generate secret and compute INTT
    secret_ntt = rng.integers(0, q, size=n).astype(np.int64)
    intermediates = compute_full_intt(secret_ntt, n, n_layers)

    true_values = {}
    for layer_idx in range(n_layers + 1):
        for i in range(n):
            true_values[layer_idx * n + i] = int(intermediates[layer_idx][i])

    factors = build_full_intt_factor_graph(n, n_layers)

    # Observe all layers 1-7
    observe_layers = list(range(1, n_layers + 1))
    observed_vars = {}
    for layer_idx in observe_layers:
        for i in range(n):
            observed_vars[layer_idx * n + i] = true_values[layer_idx * n + i]

    observations = generate_observations(observed_vars, snr, n_traces, rng, q)

    # Run BP
    n_vars = (n_layers + 1) * n
    t0_bp = time.time()
    beliefs, n_iter, entropy_hist = run_bp(
        n_vars, factors, observations,
        max_iterations=MAX_BP_ITER, damping=0.5, q=q,
        verbose=False, n_coeffs=n,
    )
    bp_time = time.time() - t0_bp

    # Evaluate Layer 0 after BP
    l0_map = np.zeros(n, dtype=np.int64)
    l0_entropies = np.zeros(n)
    l0_correct_mask = np.zeros(n, dtype=bool)

    for i in range(n):
        b = beliefs[i]
        l0_map[i] = int(np.argmax(b))
        l0_correct_mask[i] = (l0_map[i] == true_values[i])
        p_safe = np.maximum(b, 1e-30)
        l0_entropies[i] = -float(np.sum(b * np.log2(p_safe)))

    bp_bsr = float(np.mean(l0_correct_mask))
    bp_mi = max(0, log2q - float(np.mean(l0_entropies)))
    n_wrong = int(np.sum(~l0_correct_mask))

    result = {
        "trial": trial_idx,
        "seed": seed,
        "snr_n": snr_n,
        "bp_bsr": round(bp_bsr, 4),
        "bp_mi": round(bp_mi, 2),
        "bp_iterations": n_iter,
        "bp_time_s": round(bp_time, 1),
        "n_wrong_after_bp": n_wrong,
        "bp_full_key": bp_bsr == 1.0,
    }

    if bp_bsr == 1.0:
        # BP-only success -- no enumeration needed
        result["enumeration_attempted"] = False
        result["final_success"] = True
        result["total_time_s"] = round(time.time() - t0_total, 1)
        return result

    # --- Key Enumeration ---
    result["enumeration_attempted"] = True

    # Sort coefficients by entropy (highest first = most uncertain)
    entropy_order = np.argsort(-l0_entropies)

    # Find wrong coefficients in entropy order
    wrong_indices = []
    for idx in entropy_order:
        if not l0_correct_mask[idx]:
            wrong_indices.append(int(idx))
        if len(wrong_indices) >= K_MAX:
            break

    uncertain_wrong = wrong_indices[:K_MAX]
    k_actual = len(uncertain_wrong)

    if k_actual == 0:
        result["final_success"] = True
        result["enumeration_budget_needed"] = 0
        result["enumeration_budget_used"] = 0
        result["k_enumerated"] = 0
        result["total_time_s"] = round(time.time() - t0_total, 1)
        return result

    # Determine effective K: how many coefficients can we enumerate within budget?
    k_feasible = 0
    for k in range(1, k_actual + 1):
        if M_CAND ** k > BUDGET:
            break
        k_feasible = k

    if k_feasible == 0:
        result["final_success"] = False
        result["enumeration_budget_needed"] = M_CAND ** k_actual
        result["enumeration_budget_used"] = 0
        result["k_enumerated"] = 0
        result["k_wrong_total"] = n_wrong
        result["total_time_s"] = round(time.time() - t0_total, 1)
        return result

    # Get top-M candidates for each uncertain coefficient
    enum_indices = uncertain_wrong[:k_feasible]
    candidates_per_coeff = []
    for coeff_idx in enum_indices:
        b = beliefs[coeff_idx]
        top_m = np.argsort(-b)[:M_CAND]
        candidates_per_coeff.append(top_m.tolist())

    # Ground truth Layer 7
    ground_truth_l7 = intermediates[n_layers].copy()

    # Build base candidate (MAP estimates for all coefficients)
    candidate_l0 = l0_map.copy()

    # Enumerate all M^k_feasible combinations
    t0_enum = time.time()
    total_combinations = M_CAND ** k_feasible
    enumeration_success = False
    budget_used = 0

    for combo_idx in range(total_combinations):
        if budget_used >= BUDGET:
            break
        budget_used += 1

        # Decode combo_idx into candidate choices
        tmp = combo_idx
        test_l0 = candidate_l0.copy()
        for j in range(k_feasible):
            choice = tmp % M_CAND
            tmp //= M_CAND
            test_l0[enum_indices[j]] = candidates_per_coeff[j][choice]

        # Verify: compute INTT from candidate Layer 0 and check Layer 7
        test_intermediates = compute_full_intt(test_l0, n, n_layers)
        test_l7 = test_intermediates[n_layers]

        if np.array_equal(test_l7, ground_truth_l7):
            enumeration_success = True
            l0_match = np.array_equal(test_l0, intermediates[0])
            result["l0_exact_match"] = bool(l0_match)
            break

    enum_time = time.time() - t0_enum

    result["final_success"] = enumeration_success
    result["k_enumerated"] = k_feasible
    result["k_wrong_total"] = n_wrong
    result["enumeration_budget_needed"] = total_combinations
    result["enumeration_budget_used"] = budget_used
    result["enumeration_time_s"] = round(enum_time, 1)
    result["log2_budget_used"] = round(math.log2(max(budget_used, 1)), 2)
    result["total_time_s"] = round(time.time() - t0_total, 1)

    result["enum_coeff_entropies"] = [
        round(float(l0_entropies[idx]), 2) for idx in enum_indices
    ]

    return result


def _init_worker():
    warmup_numba()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true",
                        help="Demo mode: 5 trials instead of 20")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    n_trials = 5 if args.quick else N_TRIALS
    out_file = OUT_FILE

    # Load existing results if resuming
    results = []
    if out_file.exists():
        with open(out_file) as f:
            existing = json.load(f)
            if isinstance(existing, dict) and "trials" in existing:
                results = existing["trials"]
            elif isinstance(existing, list):
                results = existing
    completed_trials = {r["trial"] for r in results}

    print("=" * 70)
    print("KEY ENUMERATION AFTER BP")
    print(f"  SNR*N = {SNR_N} (~85% BP success, ~15% need enumeration)")
    print(f"  Trials: {n_trials}")
    print(f"  Enumeration: K_max={K_MAX} coefficients, M={M_CAND} candidates")
    print(f"  Budget: 2^{math.log2(BUDGET):.0f} = {BUDGET:,} operations")
    print("=" * 70)

    print("\nWarming up Numba JIT...")
    warmup_numba()
    build_full_intt_factor_graph()

    ctx = multiprocessing.get_context("fork")

    # Build trial args
    trial_args = []
    for i in range(n_trials):
        if i in completed_trials:
            continue
        seed = i * 100_000 + int(SNR_N) + 8_000_000
        trial_args.append((i, seed, SNR_N))

    if not trial_args:
        print("\nAll trials already complete!")
    else:
        print(f"\n  Running {len(trial_args)} trials ({len(completed_trials)} already done)...")

        with ctx.Pool(N_WORKERS, initializer=_init_worker) as pool:
            for result in pool.imap_unordered(_run_single_trial, trial_args):
                trial_idx = result["trial"]
                if result["bp_full_key"]:
                    print(f"  Trial {trial_idx+1}/{n_trials}: BP SUCCESS "
                          f"(BSR=100%, MI={result['bp_mi']:.2f}, "
                          f"{result['total_time_s']:.0f}s)")
                elif result.get("final_success"):
                    print(f"  Trial {trial_idx+1}/{n_trials}: ENUM SUCCESS "
                          f"(BP BSR={result['bp_bsr']:.1%}, "
                          f"{result['n_wrong_after_bp']} wrong, "
                          f"enum k={result['k_enumerated']}, "
                          f"budget={result['enumeration_budget_used']:,}, "
                          f"{result['total_time_s']:.0f}s)")
                else:
                    print(f"  Trial {trial_idx+1}/{n_trials}: ENUM FAIL "
                          f"(BP BSR={result['bp_bsr']:.1%}, "
                          f"{result['n_wrong_after_bp']} wrong, "
                          f"k_feasible={result.get('k_enumerated', 0)}, "
                          f"budget={result.get('enumeration_budget_used', 0):,}, "
                          f"{result['total_time_s']:.0f}s)")

                results.append(result)
                _save_results(results, out_file)

    # Sort by trial index
    results.sort(key=lambda r: r["trial"])
    _save_results(results, out_file)

    _print_summary(results)


def _save_results(results, out_file):
    """Save results with metadata."""
    n_bp_only = sum(1 for r in results if r["bp_full_key"])
    n_bp_fail = sum(1 for r in results if not r["bp_full_key"])
    n_enum_success = sum(1 for r in results
                         if not r["bp_full_key"] and r.get("final_success", False))
    n_enum_fail = sum(1 for r in results
                      if not r["bp_full_key"] and not r.get("final_success", False))
    total = len(results)

    bp_rate = n_bp_only / total if total > 0 else 0
    combined_rate = (n_bp_only + n_enum_success) / total if total > 0 else 0

    ci_bp = wilson_ci(n_bp_only, total)
    ci_combined = wilson_ci(n_bp_only + n_enum_success, total)

    output = {
        "experiment": "Key Enumeration After BP",
        "snr_n": SNR_N,
        "n_trials": total,
        "k_max": K_MAX,
        "m_candidates": M_CAND,
        "budget": BUDGET,
        "summary": {
            "bp_only_success": n_bp_only,
            "bp_only_rate": round(bp_rate, 4),
            "bp_only_ci_95": [round(ci_bp[0], 4), round(ci_bp[1], 4)],
            "enumeration_attempted": n_bp_fail,
            "enumeration_success": n_enum_success,
            "enumeration_fail": n_enum_fail,
            "combined_success": n_bp_only + n_enum_success,
            "combined_rate": round(combined_rate, 4),
            "combined_ci_95": [round(ci_combined[0], 4), round(ci_combined[1], 4)],
        },
        "trials": results,
    }

    with open(out_file, "w") as f:
        json.dump(output, f, indent=2)


def _print_summary(results):
    total = len(results)
    if total == 0:
        print("\nNo results to summarize.")
        return

    n_bp_only = sum(1 for r in results if r["bp_full_key"])
    n_bp_fail = sum(1 for r in results if not r["bp_full_key"])
    n_enum_success = sum(1 for r in results
                         if not r["bp_full_key"] and r.get("final_success", False))
    n_enum_fail = sum(1 for r in results
                      if not r["bp_full_key"] and not r.get("final_success", False))

    bp_rate = n_bp_only / total
    combined_rate = (n_bp_only + n_enum_success) / total

    ci_bp = wilson_ci(n_bp_only, total)
    ci_combined = wilson_ci(n_bp_only + n_enum_success, total)

    print(f"\n{'='*70}")
    print("KEY ENUMERATION SUMMARY")
    print(f"{'='*70}")
    print(f"  SNR*N = {SNR_N}, {total} trials")
    print()
    print(f"  BP-only success:     {n_bp_only}/{total} ({bp_rate:.0%}), "
          f"CI=[{ci_bp[0]:.1%},{ci_bp[1]:.1%}]")
    print(f"  BP+enum success:     {n_bp_only + n_enum_success}/{total} "
          f"({combined_rate:.0%}), CI=[{ci_combined[0]:.1%},{ci_combined[1]:.1%}]")
    print(f"  Enumeration tried:   {n_bp_fail}")
    print(f"    Succeeded:         {n_enum_success}")
    print(f"    Failed:            {n_enum_fail}")

    if n_enum_success > 0:
        enum_budgets = [r["enumeration_budget_used"] for r in results
                        if not r["bp_full_key"] and r.get("final_success", False)]
        enum_ks = [r["k_enumerated"] for r in results
                   if not r["bp_full_key"] and r.get("final_success", False)]
        print(f"\n  Successful enumerations:")
        print(f"    Mean budget used:  {np.mean(enum_budgets):,.0f} "
              f"(2^{np.mean([math.log2(max(b,1)) for b in enum_budgets]):.1f})")
        print(f"    Mean k enumerated: {np.mean(enum_ks):.1f}")

    if n_bp_fail > 0:
        wrong_counts = [r["n_wrong_after_bp"] for r in results if not r["bp_full_key"]]
        print(f"\n  BP failure analysis:")
        print(f"    Mean wrong coefficients: {np.mean(wrong_counts):.1f}")
        print(f"    Median wrong:           {np.median(wrong_counts):.0f}")
        print(f"    Max wrong:              {max(wrong_counts)}")

    print(f"\n  Effective threshold:")
    print(f"    Without enumeration: ~85% at SNR*N={SNR_N}")
    print(f"    With enumeration:    {combined_rate:.0%} at SNR*N={SNR_N}")
    if combined_rate > bp_rate:
        print(f"    Improvement: +{(combined_rate - bp_rate)*100:.0f}pp")
    else:
        print(f"    No improvement from enumeration")

    print(f"\nResults: {OUT_FILE}")


if __name__ == "__main__":
    main()
