"""ML-KEM (FIPS 203) constants for NTT belief propagation.

Zeta values follow FIPS 203 Section 4.3 and Algorithm 10, using the
primitive 512th root of unity zeta = 17 mod q = 3329.
"""

MLKEM_Q = 3329
MLKEM_N = 256
N_LAYERS = 7
MLKEM_ZETA = 17  # primitive 512th root of unity mod q, per FIPS 203


def _bitrev(x: int, bits: int) -> int:
    """Reverse the lowest `bits` bits of integer `x`."""
    result = 0
    for _ in range(bits):
        result = (result << 1) | (x & 1)
        x >>= 1
    return result


FIPS203_ZETAS = [pow(MLKEM_ZETA, _bitrev(i, 7), MLKEM_Q) for i in range(128)]
FIPS203_ZETAS_INV = [pow(z, MLKEM_Q - 2, MLKEM_Q) for z in FIPS203_ZETAS]

# RTL-measured SNR values from Verilator simulation of Adams Bridge
# (1,000 fixed + 1,000 random input pairs, 595 cycles each)
RTL_SNR = {
    "butterfly": 0.0027,
    "mem_write": 0.0155,
    "mem_read": 0.0033,
    "address": 0.0004,
    "control": 0.0000,
}
