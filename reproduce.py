#!/usr/bin/env python3
"""Reproduce results from arXiv:2604.03813.

"Partial NTT Masking in PQC Hardware: A Security Margin Analysis"
Ray Iskander, Khaled Kirah

Usage:
    python reproduce.py --verify   # ~1 min: check evidence files match paper claims
    python reproduce.py --quick    # ~15 min: analytical exps + proofs + FIPS 203 check
    python reproduce.py --medium   # ~2 hours: adds BP demo runs
    python reproduce.py --full     # ~24 hours: all experiments (sweep, ablation, NC1, etc.)
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence"


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
    """Check that evidence JSON files match key paper claims."""
    results: list[tuple[str, bool]] = []

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

        consec = ablation_by_config.get("L1-L4")
        if consec:
            check(
                "Ablation: L1-L4 (consecutive) has 0 recovery",
                consec["full_key_recovery_rate"] == 0.0,
                f"rate={consec['full_key_recovery_rate']}"
            )
        else:
            check("Ablation: L1-L4 config exists", False)

        # Check {1,4,7} fails (NC4 counter-example in ablation)
        l147 = ablation_by_config.get("L1+L4+L7")
        if l147:
            check(
                "Ablation: L1+L4+L7 (k=3) fails recovery",
                l147["full_key_recovery_rate"] == 0.0,
                f"rate={l147['full_key_recovery_rate']}"
            )
        else:
            check("Ablation: L1+L4+L7 config exists", False)

    except FileNotFoundError:
        check("ablation_results.json exists", False)

    # --- NC1 moonshot ---
    step(3, 6, "NC1 barrier (evidence/nc1_moonshot_results.json)")
    try:
        nc1 = load_json("nc1_moonshot_results.json")
        all_zero_mi = all(e["mi_bp"] == 0.0 for e in nc1)
        all_no_fk = all(not e["full_key"] for e in nc1)
        check(
            "NC1: all no-L1 configs have MI = 0",
            all_zero_mi,
            f"{sum(1 for e in nc1 if e['mi_bp'] == 0.0)}/{len(nc1)} have MI=0"
        )
        check(
            "NC1: no full-key recovery without L1",
            all_no_fk,
            f"{sum(1 for e in nc1 if not e['full_key'])}/{len(nc1)} failed recovery"
        )
    except FileNotFoundError:
        check("nc1_moonshot_results.json exists", False)

    # --- NC4 validation ---
    step(4, 6, "NC4 validation (evidence/nc4_validation.json)")
    try:
        nc4 = load_json("nc4_validation.json")
        nc4_by_config = {e["config"]: e for e in nc4}

        l1347 = nc4_by_config.get("L1+L3+L4+L7")
        if l1347:
            check(
                "NC4: {1,3,4,7} achieves recovery (k=4 sufficient)",
                l1347["full_key_recovery_rate"] > 0.5,
                f"rate={l1347['full_key_recovery_rate']}, "
                f"n_full_key={l1347['n_full_key']}/{l1347['n_seeds']}"
            )
        else:
            check("NC4: {1,3,4,7} config exists", False)

    except FileNotFoundError:
        check("nc4_validation.json exists", False)

    # --- Convergence ---
    step(5, 6, "Convergence (evidence/convergence_results.json)")
    try:
        conv = load_json("convergence_results.json")
        check(
            "Convergence data exists",
            len(conv) > 0,
            f"{len(conv)} convergence traces"
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
        check(
            "Damping sensitivity data exists",
            len(damp) > 0,
            f"{len(damp)} damping configurations tested"
        )
    except FileNotFoundError:
        check("damping_sensitivity.json exists", False)

    return results


# ---------------------------------------------------------------------------
# --quick mode
# ---------------------------------------------------------------------------

def run_quick() -> list[tuple[str, bool]]:
    """Run fast experiments (~15 min)."""
    results: list[tuple[str, bool]] = []
    scripts = [
        ("Exp D: RTL Constants", "experiments/exp_d_rtl_constants.py", 120),
        ("Exp E: Template Bridge", "experiments/exp_e_template_bridge.py", 120),
        ("Exp A: Factor Graph Construction", "experiments/exp_a_factor_graph.py", 120),
        ("Exp G: Composite Margin", "experiments/exp_g_composite_margin.py", 120),
        ("Exp I: FIPS 203 Verification", "experiments/exp_i_fips203_verify.py", 120),
        ("Formal Proofs (T1-T6)", "proofs/paper_formal_proofs.py", 300),
        ("NC3 Fourier Contraction Proof", "proofs/nc3_fourier_contraction.py", 120),
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
    """Run medium experiments (~2 hours)."""
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
    """Run all experiments (~24 hours)."""
    results: list[tuple[str, bool]] = []
    scripts = [
        ("Exp I: Full-Scale Sweep (120 trials)", "experiments/exp_i_full_scale_sweep.py", 7 * 3600),
        ("Exp I: Ablation (500+ trials)", "experiments/exp_i_ablation.py", 12 * 3600),
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
                       help="~1 min: check evidence files match paper claims")
    group.add_argument("--quick", action="store_true",
                       help="~15 min: analytical exps + proofs + FIPS 203 check")
    group.add_argument("--medium", action="store_true",
                       help="~2 hours: adds BP demo runs")
    group.add_argument("--full", action="store_true",
                       help="~24 hours: all experiments")

    args = parser.parse_args()
    all_results: list[tuple[str, bool]] = []

    start = time.time()

    if args.verify:
        header("VERIFY MODE — Checking evidence files (~1 min)")
        all_results.extend(verify_evidence())

    elif args.quick:
        header("QUICK MODE — Analytical experiments + proofs (~15 min)")
        header("Phase 1: Evidence verification")
        all_results.extend(verify_evidence())
        header("Phase 2: Quick experiments")
        all_results.extend(run_quick())

    elif args.medium:
        header("MEDIUM MODE — All quick + BP demos (~2 hours)")
        header("Phase 1: Evidence verification")
        all_results.extend(verify_evidence())
        header("Phase 2: Quick experiments")
        all_results.extend(run_quick())
        header("Phase 3: Medium experiments (BP demos)")
        all_results.extend(run_medium())

    elif args.full:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}"
              "WARNING: Full reproduction will take approximately 24 hours."
              f"{Colors.RESET}")
        response = input("Continue? [y/N] ").strip().lower()
        if response != "y":
            print("Aborted.")
            return 0

        header("FULL MODE — All experiments (~24 hours)")
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
