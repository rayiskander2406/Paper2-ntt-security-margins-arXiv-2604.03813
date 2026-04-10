#!/usr/bin/env python3
"""Experiment I (FIPS 203 Verification): Verify INTT correctness.

Checks that compute_full_intt matches the FIPS 203 reference INTT
(Algorithm 10) exactly on random inputs, verifies butterfly constraint
consistency, and confirms NTT/INTT round-trip.

This is a fast verification test (< 10 seconds), not a long experiment.

Reference: FIPS 203, Algorithm 10 (NTT^{-1}).
"""

import numpy as np

from ntt_bp import compute_full_intt, build_full_intt_factor_graph
from ntt_bp.constants import MLKEM_Q, MLKEM_N, MLKEM_ZETA, FIPS203_ZETAS, _bitrev

Q = MLKEM_Q
N = MLKEM_N
ZETA = MLKEM_ZETA

# FIPS 203 zetas array: zetas[i] = zeta^{BitRev_7(i)} for i=0..127
ZETAS = FIPS203_ZETAS


def fips203_intt(f_hat_in: np.ndarray) -> np.ndarray:
    """Reference FIPS 203 Algorithm 10 INTT (without final n^{-1} scaling).

    We omit the final multiplication by 128^{-1} mod q to match our
    compute_full_intt which also omits it (the scaling is a single
    unary factor that doesn't affect the factor graph structure).
    """
    f = f_hat_in.copy().astype(np.int64)
    k = 127
    length = 2
    while length <= 128:
        for start in range(0, N, 2 * length):
            z = ZETAS[k]
            k -= 1
            for j in range(start, start + length):
                t = int(f[j])
                f[j] = (t + f[j + length]) % Q
                f[j + length] = (z * ((int(f[j + length]) - t) % Q)) % Q
        length *= 2
    return f


def fips203_intt_full(f_hat_in: np.ndarray) -> np.ndarray:
    """Full FIPS 203 INTT including the (n/2)^{-1} scaling.

    FIPS 203 uses 128^{-1} mod q = 3303 (7-layer partial NTT/INTT).
    """
    f = fips203_intt(f_hat_in)
    n_half_inv = pow(N // 2, Q - 2, Q)  # 128^{-1} mod 3329 = 3303
    for i in range(N):
        f[i] = (int(f[i]) * n_half_inv) % Q
    return f


def test_equivalence(n_tests: int = 200):
    """Verify compute_full_intt matches FIPS 203 reference on random inputs."""
    rng = np.random.default_rng(12345)
    n_pass = 0
    n_fail = 0

    for trial in range(n_tests):
        # Random NTT-domain input
        f_hat = rng.integers(0, Q, size=N).astype(np.int64)

        # Our implementation (returns all intermediate layers)
        layers = compute_full_intt(f_hat, N, 7)
        our_output = layers[-1]  # final layer = INTT output (without n^{-1})

        # FIPS 203 reference (without n^{-1})
        ref_output = fips203_intt(f_hat)

        if np.array_equal(our_output, ref_output):
            n_pass += 1
        else:
            n_fail += 1
            if n_fail <= 3:
                diffs = np.where(our_output != ref_output)[0]
                print(f"MISMATCH trial {trial}: {len(diffs)} coefficients differ")
                for idx in diffs[:5]:
                    print(f"  coeff[{idx}]: ours={our_output[idx]}, ref={ref_output[idx]}")

    return n_pass, n_fail


def test_intermediate_consistency():
    """Verify each butterfly layer is self-consistent with the factor graph."""
    rng = np.random.default_rng(99999)
    f_hat = rng.integers(0, Q, size=N).astype(np.int64)
    layers = compute_full_intt(f_hat, N, 7)
    factors = build_full_intt_factor_graph(N, 7)

    n_checked = 0
    n_ok = 0
    for f in factors:
        u_in = int(layers[f.u_in // N][f.u_in % N])
        v_in = int(layers[f.v_in // N][f.v_in % N])
        u_out = int(layers[f.u_out // N][f.u_out % N])
        v_out = int(layers[f.v_out // N][f.v_out % N])

        expected_u_out = (u_in + v_in) % Q
        expected_v_out = (f.zeta * ((v_in - u_in) % Q)) % Q

        n_checked += 1
        if u_out == expected_u_out and v_out == expected_v_out:
            n_ok += 1
        else:
            print(f"CONSTRAINT VIOLATION: factor layer={f.u_in // N}")
            print(f"  u_in={u_in}, v_in={v_in}, zeta={f.zeta}")
            print(f"  expected u_out={expected_u_out}, got {u_out}")
            print(f"  expected v_out={expected_v_out}, got {v_out}")

    return n_checked, n_ok


def main():
    print("=" * 60)
    print("FIPS 203 INTT Verification")
    print("=" * 60)

    # Test 1: INTT output equivalence
    print("\n--- Test 1: compute_full_intt vs FIPS 203 reference ---")
    n_pass, n_fail = test_equivalence(200)
    status1 = "PASS" if n_fail == 0 else "FAIL"
    print(f"  {n_pass}/{n_pass + n_fail} tests passed [{status1}]")

    # Test 2: Factor graph constraint consistency
    print("\n--- Test 2: Factor graph constraint consistency ---")
    n_checked, n_ok = test_intermediate_consistency()
    status2 = "PASS" if n_checked == n_ok else "FAIL"
    print(f"  {n_ok}/{n_checked} constraints satisfied [{status2}]")

    # Test 3: Known property -- INTT(NTT(x)) = x (up to scaling)
    print("\n--- Test 3: NTT round-trip (INTT composed with NTT) ---")

    def fips203_ntt(f_in: np.ndarray) -> np.ndarray:
        """FIPS 203 Algorithm 9 (forward NTT)."""
        f = f_in.copy().astype(np.int64)
        k = 1
        length = 128
        while length >= 2:
            for start in range(0, N, 2 * length):
                z = ZETAS[k]
                k += 1
                for j in range(start, start + length):
                    t = (z * int(f[j + length])) % Q
                    f[j + length] = (int(f[j]) - t) % Q
                    f[j] = (int(f[j]) + t) % Q
            length //= 2
        return f

    rng = np.random.default_rng(77777)
    n_rt_pass = 0
    for trial in range(50):
        x = rng.integers(0, Q, size=N).astype(np.int64)
        x_hat = fips203_ntt(x)
        x_back = fips203_intt_full(x_hat)
        if np.array_equal(x, x_back):
            n_rt_pass += 1
    status3 = "PASS" if n_rt_pass == 50 else "FAIL"
    print(f"  {n_rt_pass}/50 round-trips matched [{status3}]")

    # Summary
    print("\n" + "=" * 60)
    all_pass = n_fail == 0 and n_checked == n_ok and n_rt_pass == 50
    if all_pass:
        print("ALL TESTS PASSED")
        print("  - compute_full_intt exactly matches FIPS 203 Algorithm 10")
        print("  - All 896 butterfly constraints verified")
        print("  - NTT/INTT round-trip confirmed")
    else:
        print("SOME TESTS FAILED -- see above for details")
    print("=" * 60)

    assert all_pass, "FIPS 203 verification failed"


if __name__ == "__main__":
    main()
