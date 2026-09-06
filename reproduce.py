#!/usr/bin/env python3
"""Reproduce results from arXiv:2604.03813.

"Partial NTT Masking in PQC Hardware: A Security Margin Analysis"
Ray Iskander, Khaled Kirah

Usage:
    python reproduce.py --verify   # check evidence files match paper claims
    python reproduce.py --quick    # analytical exps + proofs + FIPS 203 check
    python reproduce.py --medium   # adds BP demo runs
    python reproduce.py --full     # all experiments (sweep, ablation, NC1, etc.)

No runtimes are stated here; the archived `time_s` fields in evidence/*.json record the
wall-clock of the archived runs.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence"

# The v3 corrected corpus. `evidence/` was generated under a convergence check that
# evaluated its delta over Layer-0 variables only, so any configuration whose observed
# layers sit >=2 butterfly hops from L0 early-exited at iteration 1 and was recorded as
# MI=0 / no-recovery. That is the NC1 artifact, retracted in v3. Every assertion below
# that touches a no-L1 configuration resolves against this corpus instead.
CORRECTED = ROOT / "paper" / "arxiv" / "v3_correction_evidence" / "rederivation_results.json"

# The two pre-correction NC1 files, kept in-tree as the retracted record. They are
# asserted to CARRY the early-exit signature, never used as evidence for a barrier.
NC1_SUPERSEDED = ("nc1_moonshot_results.json", "nc1_tier1_expansion_results.json")
NC1_SUPERSEDED_TRIALS = 160


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def header(msg: str) -> None:
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {msg}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}\n")


def step(num: int, total: int, name: str) -> None:
    print(f"\n{Colors.BOLD}[{num}/{total}] {name}{Colors.RESET}")
    print("-" * 50)


def ok(msg: str) -> None:
    print(f"  {Colors.GREEN}PASS{Colors.RESET}  {msg}")


def fail(msg: str) -> None:
    print(f"  {Colors.RED}FAIL{Colors.RESET}  {msg}")


def warn(msg: str) -> None:
    print(f"  {Colors.YELLOW}WARN{Colors.RESET}  {msg}")


def load_json(name: str) -> list | dict:
    path = EVIDENCE / name
    if not path.exists():
        raise FileNotFoundError(f"Evidence file not found: {path}")
    with open(path) as f:
        return json.load(f)


def load_corrected() -> dict:
    """Load the v3 corrected corpus, failing loudly rather than degrading to a pass.

    Raises rather than returning a sentinel: a missing corrected corpus must not let
    verify_evidence() fall back to the superseded `evidence/` numbers.
    """
    if not CORRECTED.exists():
        raise FileNotFoundError(f"v3 corrected corpus not found: {CORRECTED}")
    with open(CORRECTED) as f:
        corpus = json.load(f)
    # Self-consistency of the corpus itself. If these trip, the corpus moved and every
    # corrected assertion below is measuring against an unknown substrate.
    if len(corpus["runs"]) != corpus["n_runs"]:
        raise ValueError(
            f"corrected corpus: n_runs={corpus['n_runs']} but {len(corpus['runs'])} runs present"
        )
    if len(corpus["aggregates"]) != corpus["n_aggregates"]:
        raise ValueError(
            f"corrected corpus: n_aggregates={corpus['n_aggregates']} "
            f"but {len(corpus['aggregates'])} aggregates present"
        )
    return corpus


def aggregate(corpus: dict, config: str, snr_n: int) -> dict | None:
    """Fetch one (config, SNR*N) aggregate from the corrected corpus."""
    for a in corpus["aggregates"]:
        if a["config"] == config and a["snr_n"] == snr_n:
            return a
    return None


def run_script(script: str, timeout: int | None = None) -> bool:
    """Run a Python script as a subprocess. Returns True on success."""
    path = ROOT / script
    if not path.exists():
        warn(f"Script not found: {script}")
        return False
    cmd = [sys.executable, str(path)]
    try:
        result = subprocess.run(
            cmd, cwd=str(ROOT), timeout=timeout,
            capture_output=True, text=True
        )
        if result.returncode == 0:
            ok(f"{script} completed successfully")
            return True
        else:
            fail(f"{script} exited with code {result.returncode}")
            if result.stderr:
                for line in result.stderr.strip().splitlines()[-5:]:
                    print(f"         {line}")
            return False
    except subprocess.TimeoutExpired:
        fail(f"{script} timed out")
        return False
    except Exception as e:
        fail(f"{script} error: {e}")
        return False


def run_pytest(timeout: int = 300) -> bool:
    """Run pytest on the test suite. Returns True on success."""
    cmd = [sys.executable, "-m", "pytest", str(ROOT / "tests"), "-v"]
    try:
        result = subprocess.run(
            cmd, cwd=str(ROOT), timeout=timeout,
            capture_output=True, text=True
        )
        if result.returncode == 0:
            ok("pytest: all tests passed")
            return True
        else:
            fail(f"pytest exited with code {result.returncode}")
            if result.stdout:
                # Print last few lines which contain the summary
                for line in result.stdout.strip().splitlines()[-10:]:
                    print(f"         {line}")
            return False
    except subprocess.TimeoutExpired:
        fail("pytest timed out")
        return False
    except Exception as e:
        fail(f"pytest error: {e}")
        return False


# ---------------------------------------------------------------------------
# --verify mode
# ---------------------------------------------------------------------------

def verify_evidence() -> list[tuple[str, bool]]:
    """Check that evidence files match the claims v3 actually makes.

    Two corpora are in play. `evidence/` is the v1-v2 generation; the v3 corrected
    corpus lives at CORRECTED. Where v3 retracts a v1-v2 result, the assertion below
    resolves against the corrected corpus and additionally asserts the retracted record
    still carries its diagnostic signature -- so neither half can drift unnoticed.
    """
    results: list[tuple[str, bool]] = []

    # Hard dependency, loaded before anything else: a missing or self-inconsistent
    # corrected corpus must abort, never degrade into a pass over the superseded files.
    corrected = load_corrected()

    def check(name: str, condition: bool, detail: str = ""):
        results.append((name, condition))
        if condition:
            ok(name + (f" ({detail})" if detail else ""))
        else:
            fail(name + (f" ({detail})" if detail else ""))

    # --- Sweep results ---
    step(1, 6, "Sweep results (evidence/sweep_results.json)")
    try:
        sweep = load_json("sweep_results.json")
        snr3000 = [e for e in sweep if e["snr_n"] == 3000]
        if snr3000:
            entry = snr3000[0]
            check(
                "SNR*N=3000: 10/10 full-key recovery",
                entry["n_100pct_bsr"] == entry["n_trials"] and entry["n_100pct_bsr"] >= 10,
                f"n_100pct={entry['n_100pct_bsr']}, n_trials={entry['n_trials']}"
            )
            check(
                "SNR*N=3000: mean BSR = 1.0",
                entry["mean_l0_bsr"] == 1.0,
                f"mean_bsr={entry['mean_l0_bsr']}"
            )
        else:
            check("SNR*N=3000 entry exists", False, "not found in sweep data")

        # Check monotonic improvement with SNR*N
        snr_sorted = sorted(sweep, key=lambda e: e["snr_n"])
        bsr_values = [e["mean_l0_bsr"] for e in snr_sorted]
        check(
            "Sweep: BSR increases with SNR*N",
            all(bsr_values[i] <= bsr_values[i + 1] + 0.01
                for i in range(len(bsr_values) - 1)),
            f"BSR progression: {[f'{b:.2f}' for b in bsr_values]}"
        )
    except FileNotFoundError:
        check("sweep_results.json exists", False)

    # --- Ablation results ---
    step(2, 6, "Ablation results (evidence/ablation_results.json)")
    try:
        ablation = load_json("ablation_results.json")
        ablation_by_config = {e["config"]: e for e in ablation}

        spread = ablation_by_config.get("L1+L3+L5+L7")
        if spread:
            check(
                "Ablation: L1+L3+L5+L7 has perfect recovery",
                spread["full_key_recovery_rate"] == 1.0,
                f"rate={spread['full_key_recovery_rate']}"
            )
        else:
            check("Ablation: L1+L3+L5+L7 config exists", False)

        # v3: "0% for 4 consecutive layers" is a point at SNR*N=5,000, not a topological
        # law -- L1-L4 recovers 100% full-key at SNR*N=500,000. The label
        # carries the budget so the number cannot be re-read as a barrier.
        consec = ablation_by_config.get("L1-L4")
        if consec:
            check(
                "Ablation: L1-L4 (consecutive) has 0 recovery AT SNR*N=5,000 "
                "(trace-cost, not a barrier: 100% at 500,000)",
                consec["full_key_recovery_rate"] == 0.0,
                f"rate={consec['full_key_recovery_rate']}"
            )
        else:
            check("Ablation: L1-L4 config exists", False)

        # v3 CORRECTION: the superseded file records 0/10 for {1,4,7}; the corrected
        # corpus records 2/8 = 0.25 at the same budget. Both are asserted, so the check
        # fails if either the retracted figure or its correction moves.
        l147 = ablation_by_config.get("L1+L4+L7")
        l147_corr = aggregate(corrected, "L1+L4+L7", 5000)
        if l147 and l147_corr:
            check(
                "Ablation: L1+L4+L7 (k=3) is budget-limited at SNR*N=5,000 "
                "(superseded 0/10; corrected 2/8)",
                l147["full_key_recovery_rate"] == 0.0
                and l147_corr["n_full_key"] == 2
                and l147_corr["n_seeds"] == 8,
                f"superseded={l147['full_key_recovery_rate']}, corrected="
                f"{l147_corr['n_full_key']}/{l147_corr['n_seeds']}"
            )
        else:
            check("Ablation: L1+L4+L7 config exists (both corpora)", False)

    except FileNotFoundError:
        check("ablation_results.json exists", False)

    # --- NC1 barrier: RETRACTED in v3 ---
    # v1-v2 asserted "MI ~ 0 across 160 no-L1 trials, regardless of trace count". That was
    # an artifact of the Layer-0-only convergence check: with L1 unobserved the nearest
    # observation sits >=2 butterfly hops from L0, so iteration 1 left L0 untouched, the
    # delta read 0, and BP early-exited at a uniform posterior. Run to convergence over
    # ALL variables, the same solver recovers the full key. This step now asserts the
    # RETRACTION -- both halves, so it fails if either the artifact record or its
    # correction moves.
    step(3, 6, "NC1 barrier RETRACTION (v3 corrected corpus)")
    try:
        superseded = []
        for name in NC1_SUPERSEDED:
            superseded.extend(load_json(name))
        at_iter_1 = sum(1 for e in superseded if e.get("bp_iterations") == 1)
        check(
            "NC1 (retracted): all 160 superseded trials bear the L0-only early-exit "
            "signature (bp_iterations == 1)",
            len(superseded) == NC1_SUPERSEDED_TRIALS and at_iter_1 == len(superseded),
            f"{at_iter_1}/{len(superseded)} stopped at iteration 1"
        )

        nc1_aggs = [a for a in corrected["aggregates"] if a["config"].startswith("NC1-")]
        recovered = [a for a in nc1_aggs if a["full_key_rate"] == 1.0]
        check(
            "NC1 (corrected): no-L1 configs DO recover the full key",
            len(nc1_aggs) == 8 and len(recovered) == 7,
            f"{len(recovered)}/{len(nc1_aggs)} aggregates at full-key rate 1.0 "
            f"(the eighth, NC1-F_L3+L5+L7, reaches 0.6)"
        )
        check(
            "NC1 (corrected): no-L1 MI_BP is ~11.7 bits, NOT 0",
            bool(nc1_aggs) and all(a["mean_mi_bp"] > 10.0 for a in nc1_aggs),
            f"min MI_BP = {min(a['mean_mi_bp'] for a in nc1_aggs):.4f} bits "
            f"across {len(nc1_aggs)} aggregates"
        )
        check(
            "NC1: every superseded aggregate is flagged was_artifact with committed rate 0",
            all(a["was_artifact"] and a["committed"]["fk_rate"] == 0.0 for a in nc1_aggs)
            and sum(a["committed"]["n_seeds"] for a in nc1_aggs) == NC1_SUPERSEDED_TRIALS,
            f"{sum(a['committed']['n_seeds'] for a in nc1_aggs)} superseded trials, "
            f"all committed full-key rate 0.0"
        )
    except FileNotFoundError as e:
        check(f"NC1 retraction inputs present ({e})", False)

    # --- NC4 validation ---
    step(4, 6, "NC4 validation (evidence/nc4_validation.json)")
    try:
        nc4 = load_json("nc4_validation.json")
        nc4_by_config = {e["config"]: e for e in nc4}

        # v3: NC4 is a trace-cost multiplier, not a "k>=4 is necessary" law.
        # The label no longer asserts sufficiency of k=4.
        l1347 = nc4_by_config.get("L1+L3+L4+L7")
        l1347_corr = aggregate(corrected, "L1+L3+L4+L7", 5000)
        if l1347 and l1347_corr:
            check(
                "NC4: {1,3,4,7} achieves recovery at SNR*N=5,000 "
                "(superseded 9/10; corrected 8/8)",
                l1347["full_key_recovery_rate"] > 0.5
                and l1347_corr["full_key_rate"] == 1.0,
                f"superseded={l1347['n_full_key']}/{l1347['n_seeds']}, "
                f"corrected={l1347_corr['n_full_key']}/{l1347_corr['n_seeds']}"
            )
        else:
            check("NC4: {1,3,4,7} config exists (both corpora)", False)

        # Provenance guard for Table 8's {1,3,4,7} row. TWO committed runs of this config
        # exist at SNR*N=5,000 and they legitimately differ because their seed counts
        # differ: nc4_validation.json is 10 seeds (9/10, MI 11.2) and all_k4_configs.json
        # is 50 seeds (45/50, MI 11.31). Asserting both pins each run to its own seed
        # count, so the two cannot be mixed within one row.
        try:
            k4 = load_json("all_k4_configs.json")
            k4_row = next(
                (e for e in k4 if e.get("config_name") == "L1+L3+L4+L7"
                 and e.get("snr_n") == 5000), None
            )
            check(
                "NC4: {1,3,4,7} has two archived runs at SNR*N=5,000 with distinct seed "
                "counts (10-seed 9/10, MI 11.2; 50-seed 45/50, MI 11.31)",
                bool(k4_row)
                and l1347["n_seeds"] == 10 and l1347["mean_mi_bp"] == 11.2
                and k4_row["n_seeds"] == 50 and k4_row["mean_mi"] == 11.31,
                f"10-seed MI={l1347['mean_mi_bp']} ({l1347['n_full_key']}/{l1347['n_seeds']}), "
                f"50-seed MI={k4_row['mean_mi'] if k4_row else 'ABSENT'} "
                f"({k4_row['n_full_key']}/{k4_row['n_seeds']})" if k4_row else "ABSENT"
            )
        except FileNotFoundError:
            check("all_k4_configs.json exists", False)

    except FileNotFoundError:
        check("nc4_validation.json exists", False)

    # --- Convergence ---
    step(5, 6, "Convergence (evidence/convergence_results.json)")
    try:
        conv = load_json("convergence_results.json")
        # Was a bare len>0 test, which could not fail on content. Bound to the claim the
        # paper actually makes about this file.
        check(
            "Convergence: every trace records a positive iteration count and a BSR in [0,1]",
            len(conv) > 0
            and all(e["bp_iterations"] >= 1 for e in conv)
            and all(0.0 <= e["final_bsr"] <= 1.0 for e in conv),
            f"{len(conv)} traces, iterations "
            f"{min(e['bp_iterations'] for e in conv)}-{max(e['bp_iterations'] for e in conv)}"
        )
        # Check all converge to BSR=1.0 at SNR*N=3000
        snr3000_conv = [e for e in conv if e["snr_n"] == 3000]
        if snr3000_conv:
            all_converged = all(e["final_bsr"] == 1.0 for e in snr3000_conv)
            check(
                "Convergence: all SNR*N=3000 traces reach BSR=1.0",
                all_converged,
                f"{sum(1 for e in snr3000_conv if e['final_bsr'] == 1.0)}/{len(snr3000_conv)}"
            )
    except FileNotFoundError:
        check("convergence_results.json exists", False)

    # --- Damping sensitivity ---
    step(6, 6, "Damping sensitivity (evidence/damping_sensitivity.json)")
    try:
        damp = load_json("damping_sensitivity.json")
        by_damping = {e["damping"]: e for e in damp}
        # Was a bare len>0 test. Bound to point values, NOT to a monotone trend: full-key
        # reliability is non-monotone in damping (0.1 and 0.7 both reach 5/5, 0.3 and 0.5
        # sit at 4/5, 0.9 collapses to 1/5), so any "lower damping is better" assertion
        # would be false against this same file.
        check(
            "Damping: 0.1 converges fastest at full reliability, 0.9 degrades recovery",
            len(damp) == 5
            and by_damping[0.1]["full_key_rate"] == 1.0
            and by_damping[0.1]["mean_bp_iters"] < by_damping[0.5]["mean_bp_iters"]
            and by_damping[0.9]["full_key_rate"] < 0.5,
            f"0.1 -> {by_damping[0.1]['n_full_key']}/{by_damping[0.1]['n_seeds']} at "
            f"{by_damping[0.1]['mean_bp_iters']} iters; "
            f"0.9 -> {by_damping[0.9]['n_full_key']}/{by_damping[0.9]['n_seeds']}"
        )
    except FileNotFoundError:
        check("damping_sensitivity.json exists", False)

    return results


# ---------------------------------------------------------------------------
# --quick mode
# ---------------------------------------------------------------------------

def run_quick() -> list[tuple[str, bool]]:
    """Run fast experiments."""
    results: list[tuple[str, bool]] = []
    scripts = [
        ("Exp D: RTL Constants", "experiments/exp_d_rtl_constants.py", 120),
        ("Exp E: Template Bridge", "experiments/exp_e_template_bridge.py", 120),
        ("Exp A: Factor Graph Construction", "experiments/exp_a_factor_graph.py", 120),
        ("Exp G: Composite Margin", "experiments/exp_g_composite_margin.py", 120),
        ("Exp I: FIPS 203 Verification", "experiments/exp_i_fips203_verify.py", 120),
        ("Formal Proofs (paper_formal_proofs.py, T1-T18)", "proofs/paper_formal_proofs.py", 300),
    ]

    total = len(scripts) + 1  # +1 for pytest

    for i, (name, script, timeout) in enumerate(scripts, 1):
        step(i, total, name)
        passed = run_script(script, timeout=timeout)
        results.append((name, passed))

    step(total, total, "Unit Tests (pytest)")
    passed = run_pytest(timeout=600)
    results.append(("Unit Tests", passed))

    return results


# ---------------------------------------------------------------------------
# --medium mode
# ---------------------------------------------------------------------------

def run_medium() -> list[tuple[str, bool]]:
    """Run medium experiments."""
    results: list[tuple[str, bool]] = []
    scripts = [
        ("Exp F: 2-Layer BP Demo", "experiments/exp_f_2layer_bp.py", 3600),
        ("Exp H: Monte Carlo Validation", "experiments/exp_h_monte_carlo.py", 3600),
    ]

    total = len(scripts)
    for i, (name, script, timeout) in enumerate(scripts, 1):
        step(i, total, name)
        passed = run_script(script, timeout=timeout)
        results.append((name, passed))

    return results


# ---------------------------------------------------------------------------
# --full mode
# ---------------------------------------------------------------------------

def run_full() -> list[tuple[str, bool]]:
    """Run all experiments."""
    results: list[tuple[str, bool]] = []
    scripts = [
        ("Exp I: Full-Scale Sweep (120 trials)", "experiments/exp_i_full_scale_sweep.py", 7 * 3600),
        ("Exp I: Ablation", "experiments/exp_i_ablation.py", 12 * 3600),
        ("Exp I: Convergence", "experiments/exp_i_convergence.py", 3 * 3600),
        ("Exp I: NC1 Barrier", "experiments/exp_i_nc1_barrier.py", 4 * 3600),
        ("Exp I: NC4 Validation", "experiments/exp_i_nc4_validation.py", 2 * 3600),
        ("Exp I: Damping Sensitivity", "experiments/exp_i_damping.py", 2 * 3600),
        ("Exp I: Key Enumeration", "experiments/exp_i_key_enumeration.py", 3 * 3600),
        ("Exp B: Lattice Sensitivity", "experiments/exp_b_lattice.py", 3600),
        ("Exp C: RSI Shuffling", "experiments/exp_c_rsi_shuffling.py", 1800),
    ]

    total = len(scripts)
    for i, (name, script, timeout) in enumerate(scripts, 1):
        step(i, total, name)
        passed = run_script(script, timeout=timeout)
        results.append((name, passed))

    return results


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(results: list[tuple[str, bool]]) -> int:
    """Print final summary table. Returns 0 if all passed, 1 otherwise."""
    n_pass = sum(1 for _, p in results if p)
    n_fail = len(results) - n_pass

    header("SUMMARY")

    for name, passed in results:
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if passed else f"{Colors.RED}FAIL{Colors.RESET}"
        print(f"  [{status}]  {name}")

    print()
    if n_fail == 0:
        print(f"{Colors.BOLD}{Colors.GREEN}"
              f"  All {n_pass}/{len(results)} checks passed."
              f"{Colors.RESET}")
    else:
        print(f"{Colors.BOLD}{Colors.RED}"
              f"  {n_fail}/{len(results)} checks FAILED, "
              f"{n_pass}/{len(results)} passed."
              f"{Colors.RESET}")

    return 0 if n_fail == 0 else 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reproduce results from arXiv:2604.03813.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--verify", action="store_true",
                       help="check evidence files match paper claims")
    group.add_argument("--quick", action="store_true",
                       help="analytical exps + proofs + FIPS 203 check")
    group.add_argument("--medium", action="store_true",
                       help="adds BP demo runs")
    group.add_argument("--full", action="store_true",
                       help="all experiments")

    args = parser.parse_args()
    all_results: list[tuple[str, bool]] = []

    start = time.time()

    if args.verify:
        header("VERIFY MODE — Checking evidence files")
        all_results.extend(verify_evidence())

    elif args.quick:
        header("QUICK MODE — Analytical experiments + proofs")
        header("Phase 1: Evidence verification")
        all_results.extend(verify_evidence())
        header("Phase 2: Quick experiments")
        all_results.extend(run_quick())

    elif args.medium:
        header("MEDIUM MODE — All quick + BP demos")
        header("Phase 1: Evidence verification")
        all_results.extend(verify_evidence())
        header("Phase 2: Quick experiments")
        all_results.extend(run_quick())
        header("Phase 3: Medium experiments (BP demos)")
        all_results.extend(run_medium())

    elif args.full:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}"
              "WARNING: Full reproduction re-runs every experiment."
              f"{Colors.RESET}")
        response = input("Continue? [y/N] ").strip().lower()
        if response != "y":
            print("Aborted.")
            return 0

        header("FULL MODE — All experiments")
        header("Phase 1: Evidence verification")
        all_results.extend(verify_evidence())
        header("Phase 2: Quick experiments")
        all_results.extend(run_quick())
        header("Phase 3: Medium experiments")
        all_results.extend(run_medium())
        header("Phase 4: Full-scale experiments")
        all_results.extend(run_full())

    elapsed = time.time() - start
    minutes = elapsed / 60

    rc = print_summary(all_results)
    print(f"\n  Total time: {minutes:.1f} minutes\n")
    return rc


if __name__ == "__main__":
    sys.exit(main())
