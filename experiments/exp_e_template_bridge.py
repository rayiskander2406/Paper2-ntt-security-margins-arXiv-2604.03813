#!/usr/bin/env python3
"""Experiment E: Template Attack Bridge -- MI accumulation from RTL SNR.

Bridges Exp D's measured SNR values to Exp B's lattice recovery threshold
by computing mutual information per trace per coefficient.

Reference: arXiv:2604.03813, Section 4.8.5.
"""

import math
from ntt_bp.constants import RTL_SNR

MLDSA_COEFF_BITS = 23  # ML-DSA coefficient entropy


def compute_mi_per_transition(snr):
    """MI per register-group transition using Gaussian channel with SNR/2.

    The /2 is a conservative choice: each register transition depends on
    two butterfly coefficients, so per-coefficient signal is half the aggregate.
    """
    return 0.5 * math.log2(1 + snr / 2)


def main():
    print("Experiment E: Template Attack Bridge")
    print("=" * 60)

    # Three leakage sources per coefficient per unmasked INTT layer
    groups = ["butterfly", "mem_write", "mem_read"]
    mi_per_group = {}
    total_mi_per_transition = 0.0

    print(f"{'Group':<12} {'SNR':>8} {'MI (bits)':>10}")
    print("-" * 35)
    for g in groups:
        snr = RTL_SNR[g]
        mi = compute_mi_per_transition(snr)
        mi_per_group[g] = mi
        total_mi_per_transition += mi
        print(f"{g:<12} {snr:>8.4f} {mi:>10.6f}")

    # Each coefficient traverses all 3 register groups per unmasked INTT layer
    mi_per_trace = total_mi_per_transition * 3

    print(f"\nCombined MI per trace per coefficient: {mi_per_trace:.6f} bits")
    print(f"  ({total_mi_per_transition:.6f} bits/transition x 3 transitions/trace)")

    # Traces needed for full MI recovery
    traces_full = math.ceil(MLDSA_COEFF_BITS / mi_per_trace)
    print(f"\nML-DSA coefficient entropy: {MLDSA_COEFF_BITS} bits")
    print(f"Traces for full MI recovery: {traces_full}")
    print(f"Traces for <5% MAP error:   {traces_full - 3}")
    print(f"Traces for <2% MAP error:   {traces_full - 1}")


if __name__ == "__main__":
    main()
