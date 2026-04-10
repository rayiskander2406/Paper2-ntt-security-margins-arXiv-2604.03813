"""NTT Belief Propagation library for arXiv:2604.03813.

Implements exact loopy sum-product belief propagation on the ML-KEM
INTT factor graph (FIPS 203) with Numba-accelerated O(q^2) message
passing for Gentleman-Sande butterfly factors.
"""

from ntt_bp.constants import MLKEM_Q, MLKEM_N, N_LAYERS, FIPS203_ZETAS
from ntt_bp.factor_graph import ButterflyFactor, build_full_intt_factor_graph, compute_full_intt
from ntt_bp.belief_propagation import simulate_attack, run_bp, generate_observations, warmup_numba
from ntt_bp.statistics import wilson_ci, compute_exact_mi_numerical
