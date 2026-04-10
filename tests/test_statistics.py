"""Tests for statistical utilities."""
import math
from ntt_bp.statistics import wilson_ci, compute_exact_mi_numerical
from ntt_bp.constants import MLKEM_Q

def test_wilson_ci_perfect():
    lo, hi = wilson_ci(10, 10)
    assert lo > 0.7, f"Lower bound {lo} too low for 10/10"
    assert hi == 1.0 or hi > 0.99

def test_wilson_ci_zero():
    lo, hi = wilson_ci(0, 10)
    assert lo == 0.0
    assert hi < 0.3

def test_wilson_ci_empty():
    lo, hi = wilson_ci(0, 0)
    assert lo == 0.0 and hi == 1.0

def test_exact_mi_high_snr():
    """At high SNR, MI should approach log2(q)."""
    result = compute_exact_mi_numerical(10000, n_mc=10000, seed=42)
    log2q = math.log2(MLKEM_Q)
    assert result["MI_exact"] > 6.0, f"MI too low: {result['MI_exact']}"
    assert result["MI_exact"] <= log2q + 0.01

def test_exact_mi_low_snr():
    """At low SNR, MI should be small."""
    result = compute_exact_mi_numerical(100, n_mc=10000, seed=42)
    assert result["MI_exact"] < 5.0
    assert result["MI_exact"] > 0.0
