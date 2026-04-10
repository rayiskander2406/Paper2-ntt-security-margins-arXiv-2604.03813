"""FIPS 203 INTT factor graph construction for belief propagation.

Builds the 896-factor Gentleman-Sande butterfly graph for the ML-KEM
inverse NTT (Algorithm 10), with variable nodes for all 8 intermediate
layers (2048 total = 256 coefficients x 8 layers).
"""

from dataclasses import dataclass

import numpy as np

from .constants import FIPS203_ZETAS, FIPS203_ZETAS_INV, MLKEM_N, MLKEM_Q, N_LAYERS


@dataclass
class ButterflyFactor:
    """A single Gentleman-Sande butterfly constraint.

    Encodes:  u_out = (u_in + v_in) mod q
              v_out = zeta * (v_in - u_in) mod q
    """

    u_in: int
    v_in: int
    u_out: int
    v_out: int
    zeta: int
    zeta_inv: int


def build_full_intt_factor_graph(
    n: int = MLKEM_N, n_layers: int = N_LAYERS
) -> list[ButterflyFactor]:
    """Construct the full ML-KEM INTT factor graph.

    Follows FIPS 203 Algorithm 10 loop structure exactly.
    Returns 896 butterfly factors (7 layers x 128 butterflies/layer).

    Parameters
    ----------
    n : int
        Number of NTT coefficients (default 256).
    n_layers : int
        Number of INTT layers (default 7).

    Returns
    -------
    list[ButterflyFactor]
        Ordered list of butterfly factor nodes.
    """
    factors = []
    k = 127
    bf_len = 2
    for layer in range(n_layers):
        for start in range(0, n, 2 * bf_len):
            z = FIPS203_ZETAS[k]
            z_inv = FIPS203_ZETAS_INV[k]
            k -= 1
            for j in range(start, start + bf_len):
                factors.append(
                    ButterflyFactor(
                        u_in=layer * n + j,
                        v_in=layer * n + j + bf_len,
                        u_out=(layer + 1) * n + j,
                        v_out=(layer + 1) * n + j + bf_len,
                        zeta=z,
                        zeta_inv=z_inv,
                    )
                )
        bf_len *= 2
    return factors


def compute_full_intt(
    secret_ntt: np.ndarray, n: int = MLKEM_N, n_layers: int = N_LAYERS
) -> list[np.ndarray]:
    """Reference INTT computation returning all intermediate layers.

    Implements FIPS 203 Algorithm 10 (without final n^{-1} scaling),
    capturing every intermediate state for factor-graph verification.

    Parameters
    ----------
    secret_ntt : np.ndarray
        Input NTT-domain coefficients, shape (n,), dtype int64.
    n : int
        Number of coefficients (default 256).
    n_layers : int
        Number of INTT layers (default 7).

    Returns
    -------
    list[np.ndarray]
        List of n_layers+1 arrays.  Index 0 is the input; index
        n_layers is the (unscaled) output.
    """
    q = MLKEM_Q
    intermediates = [secret_ntt.copy()]
    a = secret_ntt.copy().astype(np.int64)
    k = 127
    bf_len = 2
    for _ in range(n_layers):
        for start in range(0, n, 2 * bf_len):
            z = FIPS203_ZETAS[k]
            k -= 1
            for j in range(start, start + bf_len):
                t = int(a[j])
                a[j] = (t + int(a[j + bf_len])) % q
                a[j + bf_len] = (z * ((int(a[j + bf_len]) - t) % q)) % q
        bf_len *= 2
        intermediates.append(a.copy())
    return intermediates
