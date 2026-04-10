#!/usr/bin/env python3
"""
Experiment B: BKZ Lattice Reduction Sensitivity
Companion code for arXiv:2604.03813 §4.8.2

Implements Qiao et al. (ePrint 2023/1866) NTT divide-and-conquer attack:
NTT256 decomposes via radix-4 Cooley-Tukey into 4 independent 64-dim SIS
sub-problems. Each sub-problem is solved with BKZ lattice reduction + CVP.

Decomposition:
  hat_s[k] = sum_{r=0}^{3} zeta^((2k+1)*r) * T_r(k)
  where T_r(k) = sum_{m=0}^{63} omega_k^m * s_r[m], s_r[m] = s[4m+r]
  and omega_k = zeta^(4*(2k+1)) mod q.

  Key property: omega_k = omega_{k+64} (period 64 in k).
  So NTT indices {k, k+64, k+128, k+192} share the same omega_k,
  giving a 4x4 Vandermonde system to recover T_0(k)..T_3(k).

  Each sub-problem r then has G equations (one per complete group)
  in 64 unknowns, forming a 64-dim q-ary lattice solvable via CVP.

Lattice method:
  - Build kernel lattice L_q^perp(A) = {x in Z^64 : Ax = 0 mod q}
  - Compute particular solution x0 (Ax0 = b mod q)
  - LLL/BKZ reduce the kernel lattice
  - Babai nearest-plane CVP to find lattice vector closest to x0
  - Secret = x0 - closest (centered mod q)

Usage:
  python experiments/exp_b_lattice.py           # Full sweep (requires fpylll)
  python experiments/exp_b_lattice.py --quick   # Demo mode (fewer trials)

Note: This experiment requires fpylll (pip install fpylll), which depends
on the FPLLL C library. If unavailable, see the paper for pre-computed results.
"""

import argparse
import json
import math
import time
import random
from pathlib import Path

import numpy as np

try:
    from fpylll import IntegerMatrix, LLL, BKZ, GSO
    FPYLLL_AVAILABLE = True
except ImportError:
    FPYLLL_AVAILABLE = False

Q = 8_380_417
N = 256
ETA = 2
ZETA = 1753  # primitive 512th root of unity mod q


def _precompute():
    """Precompute NTT matrices and sub-problem data."""
    assert pow(ZETA, 512, Q) == 1, f"ZETA^512 != 1 mod Q"
    assert pow(ZETA, 256, Q) != 1, f"ZETA^256 == 1 mod Q (not primitive)"
    print(f"ZETA={ZETA} verified as primitive 512th root of unity mod {Q}")

    # Full 256x256 NTT matrix
    # hat_s[k] = sum_{j=0}^{255} zeta^((2k+1)*j) * s[j] mod q
    ntt_mat = np.zeros((N, N), dtype=np.int64)
    for i in range(N):
        for j in range(N):
            ntt_mat[i, j] = pow(ZETA, ((2 * i + 1) * j) % (2 * N), Q)

    # omega values for each group k=0..63
    omega = [pow(ZETA, (4 * (2 * k + 1)) % (2 * N), Q) for k in range(64)]

    # 64x64 sub-problem matrices for each group k
    sub_mat = {}
    for k in range(64):
        sub_mat[k] = [pow(omega[k], m, Q) for m in range(64)]

    return ntt_mat, omega, sub_mat


def ntt_forward(s, ntt_mat):
    """Compute NTT of secret s using matrix multiplication. Exact for int64."""
    sv = np.array(s, dtype=np.int64)
    # Safe: max |sum| = 256 * 8.4M * 2 ~ 4.3G < 2^63
    raw = ntt_mat @ sv
    return [int(v) % Q for v in raw]


def gen_secret():
    """Generate random ML-DSA-44 secret: 256 coefficients in {-2,...,2}."""
    return [random.randint(-ETA, ETA) for _ in range(N)]


def solve_4x4_mod(V, b, q):
    """Solve V*x = b mod q for 4x4 system. Returns list of 4 values or None."""
    aug = [list(V[j]) + [b[j] % q] for j in range(4)]
    for col in range(4):
        piv = -1
        for r in range(col, 4):
            if aug[r][col] % q != 0:
                piv = r
                break
        if piv == -1:
            return None
        aug[col], aug[piv] = aug[piv], aug[col]
        inv = pow(aug[col][col] % q, -1, q)
        aug[col] = [(x * inv) % q for x in aug[col]]
        for r in range(4):
            if r != col and aug[r][col] % q != 0:
                f = aug[r][col]
                aug[r] = [(aug[r][c] - f * aug[col][c]) % q for c in range(5)]
    return [aug[r][4] % q for r in range(4)]


def decompose_ntt_groups(hat_s, known_groups):
    """
    Qiao radix-4 decomposition: for each complete group k, solve the 4x4
    Vandermonde system to recover T_r(k) for r=0..3.

    Group k uses NTT indices {k, k+64, k+128, k+192}.
    V[j,r] = zeta^((2*(k+64*j)+1)*r) for j=0..3, r=0..3.
    V * [T_0(k), T_1(k), T_2(k), T_3(k)]^T = [hat_s[k], ..., hat_s[k+192]]^T

    Returns: dict r -> list of (group_k, T_r_value) pairs
    """
    result = {r: [] for r in range(4)}
    for k in known_groups:
        V = [[0] * 4 for _ in range(4)]
        b = [0] * 4
        for j in range(4):
            idx = k + 64 * j
            b[j] = hat_s[idx]
            for r in range(4):
                V[j][r] = pow(ZETA, ((2 * idx + 1) * r) % (2 * N), Q)

        T_r = solve_4x4_mod(V, b, Q)
        if T_r is None:
            print(f"  WARNING: Vandermonde singular at group {k}")
            continue
        for r in range(4):
            result[r].append((k, T_r[r]))
    return result


def build_kernel_lattice(A, b_vec, dim, q):
    """
    Build kernel lattice L_q^perp(A) and particular solution x0.

    L_q^perp(A) = {x in Z^dim : Ax = 0 mod q}

    Method: row-reduce A mod q to echelon form [I_G | A'], then:
    - Pivot columns get basis vectors q * e_{p_i}
    - Non-pivot columns get basis vectors e_{c_j} - A'[:,j]^T projected
      onto pivot columns

    Returns: (IntegerMatrix basis, list x0)
    """
    G = len(b_vec)

    # Gaussian elimination mod q to echelon form
    M = [list(A[i]) for i in range(G)]
    b = [v % q for v in b_vec]
    pivot_cols = []
    pivot_row = 0
    for col in range(dim):
        if pivot_row >= G:
            break
        piv = -1
        for row in range(pivot_row, G):
            if M[row][col] % q != 0:
                piv = row
                break
        if piv == -1:
            continue
        M[pivot_row], M[piv] = M[piv], M[pivot_row]
        b[pivot_row], b[piv] = b[piv], b[pivot_row]
        inv = pow(M[pivot_row][col] % q, -1, q)
        M[pivot_row] = [(x * inv) % q for x in M[pivot_row]]
        b[pivot_row] = (b[pivot_row] * inv) % q
        for row in range(G):
            if row != pivot_row and M[row][col] % q != 0:
                f = M[row][col]
                M[row] = [(M[row][c] - f * M[pivot_row][c]) % q
                          for c in range(dim)]
                b[row] = (b[row] - f * b[pivot_row]) % q
        pivot_cols.append(col)
        pivot_row += 1

    non_pivot = [c for c in range(dim) if c not in pivot_cols]

    # Build basis for L_q^perp(A)
    B = IntegerMatrix(dim, dim)
    # Pivot rows: q * e_{p_i} (multiples of q along pivot dimensions)
    for i, p in enumerate(pivot_cols):
        B[i, p] = q
    # Non-pivot rows: e_{c_j} - dependency on pivot columns
    for j, c in enumerate(non_pivot):
        row_idx = len(pivot_cols) + j
        B[row_idx, c] = 1  # Unit vector for free variable
        for i, p in enumerate(pivot_cols):
            val = (-M[i][c]) % q
            if val > q // 2:
                val -= q
            B[row_idx, p] = val

    # Particular solution x0: Ax0 = b mod q
    x0 = [0] * dim
    for i, p in enumerate(pivot_cols):
        x0[p] = b[i] % q

    return B, x0


def solve_subproblem(r, group_T_pairs, block_size, sub_mat):
    """
    Build and solve 64-dim q-ary SIS lattice for sub-problem r.

    s_r[m] = s[4m + r] for m=0..63
    T_r(k) = sum_{m=0}^{63} omega_k^m * s_r[m] mod q

    Build kernel lattice L_q^perp(A), reduce with LLL/BKZ,
    then Babai nearest-plane CVP to recover the short secret vector.

    Returns: (recovered_64_coefficients, wall_clock_seconds)
    """
    G = len(group_T_pairs)
    dim = 64

    # Build constraint matrix A (G x 64) and RHS b (G)
    A = [[0] * dim for _ in range(G)]
    b = [0] * G
    for i, (k, T_val) in enumerate(group_T_pairs):
        A[i] = list(sub_mat[k])  # omega_k^m for m=0..63
        b[i] = T_val

    # Build kernel lattice and particular solution
    B, x0 = build_kernel_lattice(A, b, dim, Q)

    # Lattice reduction
    t0 = time.time()
    LLL.reduction(B)
    if block_size > 2:
        bs = min(block_size, dim)
        par = BKZ.Param(block_size=bs, max_loops=8,
                        flags=BKZ.AUTO_ABORT | BKZ.MAX_LOOPS)
        BKZ.reduction(B, par)

    # Babai nearest-plane CVP (polynomial time)
    M_gso = GSO.Mat(B)
    M_gso.update_gso()
    coords = M_gso.babai(x0)

    # Convert Babai coordinates to lattice vector
    closest = [0] * dim
    for i in range(dim):
        for j in range(dim):
            closest[j] += coords[i] * int(B[i, j])

    elapsed = time.time() - t0

    # Recover sub-sequence: s_r = x0 - closest (centered mod q)
    recovered = [0] * dim
    for m in range(dim):
        v = (x0[m] - closest[m]) % Q
        if v > Q // 2:
            v -= Q
        recovered[m] = v

    return recovered, elapsed


def attempt_recovery(s, known_groups, hat_s_noisy, block_size, sub_mat):
    """
    Full Qiao divide-and-conquer recovery:
    1. Vandermonde decomposition -> 4 sets of T_r values
    2. Build and solve 4 independent 64-dim lattice problems
    3. Recombine to get full 256-coefficient secret
    """
    T_data = decompose_ntt_groups(hat_s_noisy, known_groups)

    full_recovered = [0] * N
    total_time = 0

    for r in range(4):
        if not T_data[r]:
            return {"success": False, "small": False, "time_s": 0}

        sub_recovered, sub_time = solve_subproblem(
            r, T_data[r], block_size, sub_mat
        )
        total_time += sub_time

        # Map back: s_r[m] -> s[4m + r]
        for m in range(64):
            full_recovered[4 * m + r] = sub_recovered[m]

    exact = (full_recovered == list(s))
    small = all(abs(v) <= ETA for v in full_recovered)

    return {"success": exact, "small": small, "time_s": round(total_time, 3)}


def run_single_trial(error_rate, block_size, num_groups, trial_id,
                     ntt_mat, sub_mat):
    """
    Run single trial:
    - Generate random secret
    - Compute exact NTT
    - Select num_groups random complete groups (4 NTT indices each)
    - Inject per-coefficient errors (uniform random mod q)
    - Attempt Qiao recovery
    """
    s = gen_secret()
    hat_s = ntt_forward(s, ntt_mat)

    # Select random groups (each group = 4 NTT indices)
    all_groups = list(range(64))
    random.shuffle(all_groups)
    groups = sorted(all_groups[:num_groups])

    # Inject errors at individual coefficient level
    hat_s_noisy = list(hat_s)
    n_err = 0
    for k in groups:
        for j in range(4):
            idx = k + 64 * j
            if random.random() < error_rate:
                hat_s_noisy[idx] = random.randint(0, Q - 1)
                n_err += 1

    result = attempt_recovery(s, groups, hat_s_noisy, block_size, sub_mat)

    return {
        "trial_id": trial_id, "error_rate": error_rate,
        "block_size": block_size, "num_groups": num_groups,
        "num_coefficients": num_groups * 4,
        "n_errors": n_err, "success": result["success"],
        "small": result["small"], "time_s": result["time_s"],
    }


def wilson_ci(s, n, z=1.96):
    """Wilson score confidence interval for binomial proportion."""
    if n == 0:
        return (0.0, 1.0)
    p = s / n
    d = 1 + z**2 / n
    c = (p + z**2 / (2 * n)) / d
    w = z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / d
    return (max(0, c - w), min(1, c + w))


def gaussian_heuristic_gap(G, dim=64):
    """
    Compute Gaussian heuristic gap ratio for G equations in dim unknowns.
    lambda_1 ~ sqrt(dim / (2*pi*e)) * det^(1/dim)
    det(L_q^perp) = q^G, ||s|| ~ sqrt(dim * E[s_i^2])
    """
    # E[x^2] for uniform {-2,-1,0,1,2} = (4+1+0+1+4)/5 = 2
    s_norm = math.sqrt(dim * 2.0)
    lambda1 = math.sqrt(dim / (2 * math.pi * math.e)) * (Q ** (G / dim))
    return lambda1 / s_norm


def run_experiment(quick=False):
    print("=" * 70)
    print("EXPERIMENT B: BKZ Lattice Reduction Sensitivity")
    print("  Qiao radix-4 decomposition -> 4 x 64-dim SIS lattice")
    print("  Kernel lattice L_q^perp(A) + Babai nearest-plane CVP")
    print("=" * 70)
    print(f"Parameters: n={N}, q={Q}, eta={ETA}, zeta={ZETA}")
    print(f"Sub-problem dimension: 64")
    if quick:
        print("MODE: --quick (reduced trial counts for demo)")
    print()

    ntt_mat, _omega, sub_mat = _precompute()

    # Print gap analysis
    print("=== Gaussian Heuristic Gap Analysis ===")
    for ng in [8, 12, 16, 32, 48]:
        gap = gaussian_heuristic_gap(ng)
        print(f"  {ng} groups ({ng * 4}c): gap = {gap:.1f}")
    print()

    # ===== GATE TEST =====
    print(">>> GATE TEST: LLL, 0% error, 16 groups (64 coefficients)")
    print("    (Qiao's BKZ-60 is infeasible on 64-dim; LLL suffices at gap=9.3)")
    gate_ok = 0
    gate_n = 3 if quick else 5
    for t in range(gate_n):
        r = run_single_trial(0.0, 2, 16, t, ntt_mat, sub_mat)
        gate_ok += r["success"]
        print(f"  Gate [{t + 1}/{gate_n}]: success={r['success']}, "
              f"small={r['small']}, {r['time_s']}s")

    print(f"\n  GATE RESULT: {gate_ok}/{gate_n}")
    if gate_ok < (2 if quick else 4):  # Need >= 80%
        print("  *** GATE FAILED *** LLL+Babai at 0% error not working.")
        print("  Check lattice construction before proceeding.")
        return []
    print("  GATE PASSED")
    print()

    # ===== FULL SWEEP =====
    # (error_rate, block_size, num_groups, trials, label)
    if quick:
        configs = [
            (0.0, 2, 8, 5, "LLL-32c-0%"),
            (0.0, 2, 16, 10, "LLL-64c-0%"),
            (0.01, 2, 16, 10, "LLL-64c-1%"),
            (0.05, 2, 16, 10, "LLL-64c-5%"),
            (0.10, 2, 16, 10, "LLL-64c-10%"),
            (0.05, 2, 32, 10, "LLL-128c-5%"),
            (0.10, 2, 32, 10, "LLL-128c-10%"),
        ]
    else:
        configs = [
            # Minimum coefficients: gap analysis
            (0.0, 2, 8, 20, "LLL-32c-0%"),
            (0.0, 2, 12, 50, "LLL-48c-0%"),
            (0.0, 2, 16, 100, "LLL-64c-0%"),
            (0.0, 20, 16, 20, "BKZ20-64c-0%"),
            (0.0, 2, 32, 20, "LLL-128c-0%"),
            # Error sensitivity sweep: 64 coefficients (16 groups)
            (0.01, 2, 16, 100, "LLL-64c-1%"),
            (0.02, 2, 16, 100, "LLL-64c-2%"),
            (0.05, 2, 16, 100, "LLL-64c-5%"),
            (0.05, 20, 16, 30, "BKZ20-64c-5%"),
            (0.10, 2, 16, 50, "LLL-64c-10%"),
            (0.10, 20, 16, 30, "BKZ20-64c-10%"),
            (0.15, 2, 16, 50, "LLL-64c-15%"),
            (0.20, 2, 16, 50, "LLL-64c-20%"),
            # More coefficients at error rates
            (0.05, 2, 32, 30, "LLL-128c-5%"),
            (0.10, 2, 32, 30, "LLL-128c-10%"),
            (0.20, 2, 32, 30, "LLL-128c-20%"),
            (0.30, 2, 32, 30, "LLL-128c-30%"),
            (0.10, 2, 48, 20, "LLL-192c-10%"),
            (0.20, 2, 48, 20, "LLL-192c-20%"),
            (0.30, 2, 48, 20, "LLL-192c-30%"),
        ]

    results = []
    for er, bs, ng, nt, label in configs:
        bsn = "LLL" if bs <= 2 else f"BKZ-{bs}"
        nc = ng * 4
        print(f"\n--- {label}: {bsn}, err={er * 100:.0f}%, "
              f"{nc}c ({ng}g), {nt}t ---")

        ok = 0
        times = []
        for t in range(nt):
            r = run_single_trial(er, bs, ng, t, ntt_mat, sub_mat)
            results.append(r)
            if r["success"]:
                ok += 1
            times.append(r["time_s"])
            print(f"  [{t + 1}/{nt}] ok={r['success']}, small={r['small']}, "
                  f"nerr={r['n_errors']}, {r['time_s']}s")

        lo, hi = wilson_ci(ok, nt)
        pct = ok * 100 // nt if nt > 0 else 0
        avg_t = sum(times) / len(times) if times else 0
        print(f"  => {ok}/{nt} = {pct}% [{lo * 100:.0f}%,{hi * 100:.0f}%]  "
              f"avg={avg_t:.1f}s")

    return results


def save_results(results):
    out = Path(__file__).resolve().parent.parent / "evidence"
    out.mkdir(parents=True, exist_ok=True)

    with open(out / "lattice_sensitivity.json", "w") as f:
        json.dump({
            "experiment": "B",
            "description": "BKZ lattice reduction sensitivity (arXiv:2604.03813 §4.8.2)",
            "method": "Qiao radix-4, kernel lattice + Babai CVP",
            "parameters": {
                "n": N, "q": Q, "eta": ETA, "zeta": ZETA,
                "sub_dim": 64, "sub_problems": 4,
                "lattice": "kernel L_q^perp(A) via Gaussian elimination",
                "cvp": "Babai nearest-plane (GSO.Mat.babai)",
                "bkz_max_loops": 8, "bkz_flags": "AUTO_ABORT|MAX_LOOPS",
            },
            "results": results,
        }, f, indent=2)

    print(f"\nSaved to {out / 'lattice_sensitivity.json'}")


def _try_load_precomputed():
    """Attempt to load and display pre-computed results if available."""
    evidence_dir = Path(__file__).resolve().parent.parent / "evidence"
    results_file = evidence_dir / "lattice_sensitivity.json"
    if results_file.exists():
        print(f"\nFound pre-computed results: {results_file}")
        with open(results_file) as f:
            data = json.load(f)
        results = data.get("results", [])
        print(f"  Method: {data.get('method', 'N/A')}")
        print(f"  Total trials: {len(results)}")

        # Summarize by configuration
        summary = {}
        for r in results:
            key = (r["error_rate"], r["num_coefficients"], r["block_size"])
            if key not in summary:
                summary[key] = {"s": 0, "n": 0}
            summary[key]["n"] += 1
            if r["success"]:
                summary[key]["s"] += 1

        print(f"\n  {'Err%':>5} {'Coeffs':>7} {'Block':>6} {'Success':>10}")
        print(f"  {'-'*5} {'-'*7} {'-'*6} {'-'*10}")
        for key in sorted(summary.keys()):
            er, nc, bs = key
            d = summary[key]
            bn = "LLL" if bs <= 2 else f"BKZ-{bs}"
            rate = d["s"] / d["n"] * 100 if d["n"] else 0
            print(f"  {er*100:5.0f} {nc:7d} {bn:>6} "
                  f"{d['s']}/{d['n']} ({rate:.0f}%)")
        return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Experiment B: BKZ Lattice Reduction Sensitivity "
                    "(arXiv:2604.03813 §4.8.2)",
        epilog="Note: This experiment requires fpylll (pip install fpylll), "
               "which depends\non the FPLLL C library. If unavailable, see "
               "the paper for pre-computed results.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Demo mode with fewer trials (faster, less precise)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42)",
    )
    args = parser.parse_args()

    if not FPYLLL_AVAILABLE:
        print("ERROR: fpylll is not installed.")
        print()
        print("This experiment requires fpylll for lattice reduction (LLL/BKZ)")
        print("and the Babai nearest-plane CVP algorithm.")
        print()
        print("Install with:")
        print("  pip install fpylll")
        print()
        print("fpylll depends on the FPLLL C library. On Ubuntu/Debian:")
        print("  apt-get install libfplll-dev")
        print("On macOS with Homebrew:")
        print("  brew install fplll")
        print()

        if _try_load_precomputed():
            return
        else:
            print("No pre-computed results found in evidence/.")
            print("See arXiv:2604.03813 §4.8.2 for published results.")
        return

    random.seed(args.seed)
    results = run_experiment(quick=args.quick)
    if results:
        save_results(results)


if __name__ == "__main__":
    main()
