"""Tests for FIPS 203 factor graph construction and INTT computation."""
import numpy as np
from ntt_bp.constants import MLKEM_Q, MLKEM_N, N_LAYERS, FIPS203_ZETAS
from ntt_bp.factor_graph import build_full_intt_factor_graph, compute_full_intt, ButterflyFactor

def test_factor_count():
    factors = build_full_intt_factor_graph()
    assert len(factors) == 896, f"Expected 896 factors, got {len(factors)}"

def test_variable_count():
    factors = build_full_intt_factor_graph()
    all_vars = set()
    for f in factors:
        all_vars.update([f.u_in, f.v_in, f.u_out, f.v_out])
    assert len(all_vars) == 2048, f"Expected 2048 variables, got {len(all_vars)}"

def test_butterfly_constraints():
    """Verify GS butterfly constraints hold on random input."""
    rng = np.random.default_rng(42)
    secret = rng.integers(0, MLKEM_Q, size=MLKEM_N).astype(np.int64)
    intermediates = compute_full_intt(secret)
    factors = build_full_intt_factor_graph()
    true_vals = {}
    for layer in range(N_LAYERS + 1):
        for i in range(MLKEM_N):
            true_vals[layer * MLKEM_N + i] = int(intermediates[layer][i])
    for f in factors:
        u_in = true_vals[f.u_in]
        v_in = true_vals[f.v_in]
        assert true_vals[f.u_out] == (u_in + v_in) % MLKEM_Q
        assert true_vals[f.v_out] == (f.zeta * ((v_in - u_in) % MLKEM_Q)) % MLKEM_Q

def test_fips203_intt_reference():
    """Verify compute_full_intt matches FIPS 203 Algorithm 10."""
    q = MLKEM_Q
    rng = np.random.default_rng(123)
    f_hat = rng.integers(0, q, size=256).astype(np.int64)

    # Reference implementation of FIPS 203 Algorithm 10
    a = f_hat.copy()
    k = 127
    bf_len = 2
    for _ in range(7):
        for start in range(0, 256, 2 * bf_len):
            z = FIPS203_ZETAS[k]
            k -= 1
            for j in range(start, start + bf_len):
                t = int(a[j])
                a[j] = (t + a[j + bf_len]) % q
                a[j + bf_len] = (z * ((int(a[j + bf_len]) - t) % q)) % q
        bf_len *= 2

    intermediates = compute_full_intt(f_hat)
    np.testing.assert_array_equal(intermediates[-1], a)
