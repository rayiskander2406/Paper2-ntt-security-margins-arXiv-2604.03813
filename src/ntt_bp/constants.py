"""ML-KEM (FIPS 203) constants for NTT belief propagation.

Zeta values follow FIPS 203 Section 4.3 and Algorithm 10, using the
primitive 256th root of unity zeta = 17 mod q = 3329.
"""

MLKEM_Q = 3329
MLKEM_N = 256
N_LAYERS = 7
MLKEM_ZETA = 17  # primitive 256th root of unity mod q, per FIPS 203 (17 has order 256; 512 does not divide 3328)


def _bitrev(x: int, bits: int) -> int:
    """Reverse the lowest `bits` bits of integer `x`."""
    result = 0
    for _ in range(bits):
        result = (result << 1) | (x & 1)
        x >>= 1
    return result


FIPS203_ZETAS = [pow(MLKEM_ZETA, _bitrev(i, 7), MLKEM_Q) for i in range(128)]
FIPS203_ZETAS_INV = [pow(z, MLKEM_Q - 2, MLKEM_Q) for z in FIPS203_ZETAS]

# ---------------------------------------------------------------------------
# RTL-measured SNR values from Verilator simulation of Adams Bridge.
# These are UNMASKED-region SNRs; they are what the margin chain consumes.
#
# 2026-07-20 (v3 correction): the traces behind RTL_SNR were generated from a
# MALFORMED stimulus -- the mod-q reduction was dead code, the share layout was
# blocked where the RTL is interleaved (so 128 of 256 coefficients were
# identically zero), and in the random set the mask PRNG was seeded from the
# data PRNG.  A corrected re-run exists.  Full-precision values for all four
# measurement sets live in
#     experiments/rtl/patch-validation/final_results.json
# and are propagated through the chain by experiments/exp_margin_propagation.py.
#
# RTL_SNR is LEFT AT THE PUBLISHED VALUES so the v2 chain still reproduces
# byte-for-byte (Exp E -> 992 traces; evidence/composite_margin.json unchanged).
# Do not repoint it silently -- v3 must show the published and corrected
# numbers side by side, not overwrite history.
# ---------------------------------------------------------------------------

# PUBLISHED (arXiv v2, §4.8.4): N=1,000 fixed + 1,000 random, 595 cycles each.
# Rounded to 4 dp; the full-precision artifact reads 0.00267541 / 0.01551466 /
# 0.00332475 / 0.00041457.  NB the rounding is load-bearing at the margin: the
# rounded set yields 992 traces, the full-precision set yields 991.
RTL_SNR = {
    "butterfly": 0.0027,
    "mem_write": 0.0155,
    "mem_read": 0.0033,
    "address": 0.0004,
    "control": 0.0000,
}

# CORRECTED stimulus, same seed schedule, N=1,000 (like-for-like replacement).
RTL_SNR_CORRECTED_N1000 = {
    "butterfly": 0.00095875,
    "mem_write": 0.01609241,
    "mem_read": 0.00141052,
    "address": 0.00041457,  # identical to published by construction (data-independent)
    "control": 0.0,
}

# CORRECTED stimulus, N=10,000 -- the honest sample size, since 10,000 traces
# per set are already on disk.  (The published N=1,000 analysis of a 10,000-trace
# capture is the separate sample-size defect.)
RTL_SNR_CORRECTED_N10000 = {
    "butterfly": 0.00051789,
    "mem_write": 0.01529136,
    "mem_read": 0.00099826,
    "address": 0.00003704,  # identical to published by construction
    "control": 0.0,
}

# PUBLISHED-stimulus traces re-analysed at N=10,000 (isolates the sample-size
# defect from the stimulus defect -- neither correction alone finds the other).
RTL_SNR_PUBLISHED_N10000 = {
    "butterfly": 0.00233075,
    "mem_write": 0.01526250,
    "mem_read": 0.00303532,
    "address": 0.00003704,
    "control": 0.0,
}
