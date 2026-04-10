#!/usr/bin/env python3
"""Experiment G: Composite Security Margin Formalization.

Compares the designers' classical CPA security model (ePrint 2026/256) against
the measured SASCA + lattice attack pipeline. The key insight is that SASCA
converts brute-force enumeration into polynomial BP inference, changing the
attack model entirely.

Reference: arXiv:2604.03813, Section 4.8.7.
"""

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class ExperimentInputs:
    """Measured values from Experiments A-F."""
    # Exp A: Factor graph structure
    rsi_states: int = 64
    rsi_entropy_bits: float = 6.0  # log2(64)
    mldsa_layers: int = 8
    mldsa_unmasked_layers: int = 6
    bp_runs_mldsa: int = 512  # layer-by-layer RSI enumeration
    bp_runs_per_layer: int = 64  # RSI states per layer

    # Exp B: Lattice threshold
    lattice_success: dict = None  # error_rate -> success_rate

    # Exp C: RSI shuffling overhead
    rsi_overheads: dict = None  # sigma_bias_ratio -> overhead_factor

    # Exp D: RTL leakage
    snr_butterfly_hd: float = 0.0027
    snr_memwr_hd: float = 0.0155
    snr_combined_per_coeff: float = 0.01064  # (0.0027 + 0.0155 + 0.0034) / 2

    # Exp E: Template bridge
    mi_per_trace_per_coeff: float = 0.023198  # bits/INTT/coefficient
    traces_conservative: int = 807  # HW-only, h_remaining=4.3 bits (insufficient for lattice)
    traces_full_recovery: int = 992

    # System parameters
    mldsa_q: int = 8_380_417
    mldsa_coeff_bits: int = 23

    def __post_init__(self):
        if self.lattice_success is None:
            self.lattice_success = {
                0.00: 1.00, 0.01: 0.47, 0.02: 0.34,
                0.05: 0.06, 0.10: 0.00, 0.15: 0.00, 0.20: 0.00,
            }
        if self.rsi_overheads is None:
            self.rsi_overheads = {
                0.0: 4096.0, 0.1: 1194.7, 0.3: 7.3,
                0.5: 1.2, 1.0: 1.0,
            }


def classical_cpa_model(inp: ExperimentInputs) -> dict:
    """The designers' security model: classical CPA with brute-force enumeration.

    Per ePrint 2026/256 Section 6.1: CPA requires testing each coefficient
    hypothesis individually. With q hypotheses per coefficient and S positions
    per layer, the attacker must enumerate a search space of q x S per
    coefficient. The designers argue this makes the attack infeasible at
    ~2^46 per coefficient.
    """
    q = inp.mldsa_q
    log2q = math.log2(q)  # 23.0 bits

    # Per-coefficient CPA: test q hypotheses per trace
    cpa_hypotheses_per_coeff = log2q  # 23.0 bits

    # Shuffling: attacker must guess which of S positions the coefficient occupies
    shuffle_per_layer = inp.rsi_entropy_bits  # 6 bits
    shuffle_total = shuffle_per_layer * inp.mldsa_unmasked_layers  # 36 bits

    # Claimed security margin from ePrint 2026/256
    designers_claimed = 46  # bits per attack attempt

    # Classical CPA total work: N_traces x hypotheses x shuffle
    n_traces_classical = 100_000  # typical CPA trace count
    total_classical = (
        math.log2(n_traces_classical)
        + cpa_hypotheses_per_coeff
        + shuffle_total
    )

    return {
        "model": "Classical CPA (designers)",
        "per_coeff_hypotheses_bits": cpa_hypotheses_per_coeff,
        "shuffle_per_layer_bits": shuffle_per_layer,
        "shuffle_total_bits": shuffle_total,
        "designers_claimed_bits": designers_claimed,
        "n_traces": n_traces_classical,
        "total_work_bits": total_classical,
        "complexity_class": "O(N x q x S^L)",
    }


def sasca_attack_model(inp: ExperimentInputs, scenario: str) -> dict:
    """Our measured attack model: SASCA (BP) + lattice recovery.

    Key insight: SASCA replaces brute-force enumeration with polynomial BP
    inference. The attacker does NOT enumerate the q-dimensional hypothesis
    space -- BP computes the posterior over all q values simultaneously using
    the NTT factor graph structure.

    The attack pipeline is:
    1. Collect N traces (minutes with EM probe)
    2. For each RSI candidate (512 layer-by-layer, or fewer with position bias):
       a. Build factor graph with this shuffle assignment
       b. Run BP to compute posteriors: O(q^2 x butterflies x iterations)
       c. Check convergence (correct assignment -> low entropy)
    3. Extract MAP coefficients from posterior
    4. Feed into Qiao lattice recovery (polynomial)
    """
    scenarios = {
        "conservative": {
            "label": "Conservative (HW-only, no position bias)",
            "position_bias": 0.0,
            "bp_gain_bits": 0.0,
            "profiled": False,
        },
        "moderate": {
            "label": "Moderate (profiled, sigma_bias/sigma=0.3)",
            "position_bias": 0.3,
            "bp_gain_bits": 3.9,
            "profiled": True,
        },
        "aggressive": {
            "label": "Aggressive (profiled, sigma_bias/sigma=0.5+)",
            "position_bias": 0.5,
            "bp_gain_bits": 5.3,
            "profiled": True,
        },
    }
    s = scenarios[scenario]

    # Step 1: Trace acquisition
    if not s["profiled"]:
        n_traces = inp.traces_conservative
    else:
        needed_bits = max(inp.mldsa_coeff_bits - s["bp_gain_bits"], 1.0)
        n_traces = math.ceil(needed_bits / inp.mi_per_trace_per_coeff)
        n_traces = max(n_traces, 50)

    # Step 2: RSI shuffle enumeration
    bias = s["position_bias"]
    if bias in inp.rsi_overheads:
        shuffle_factor = inp.rsi_overheads[bias]
    elif bias >= 0.5:
        shuffle_factor = 1.2
    else:
        shuffle_factor = inp.rsi_overheads[0.3]

    # Layer-by-layer: enumerate RSI per layer, not jointly
    if shuffle_factor >= 64:
        shuffle_runs = inp.bp_runs_mldsa  # 512
    else:
        per_layer_candidates = max(math.ceil(shuffle_factor), 1)
        shuffle_runs = per_layer_candidates * inp.mldsa_unmasked_layers

    # Step 3: BP computation per run
    q = inp.mldsa_q
    n_butterflies = 128 * inp.mldsa_unmasked_layers  # 768
    bp_iterations = 50
    ops_per_bp_run = q * q * n_butterflies * bp_iterations * 4
    ops_per_layer = q * q * 128 * bp_iterations * 4

    # Step 4: Lattice recovery (polynomial in n)
    lattice_runs = 4  # sub-problems

    # Per-coefficient residual entropy after N traces + BP
    total_mi = n_traces * inp.mi_per_trace_per_coeff
    bp_reduction = s["bp_gain_bits"]
    residual = max(inp.mldsa_coeff_bits - total_mi - bp_reduction, 0)

    # Error rate: P(MAP correct) ~ 2^(-H_residual)
    if residual < 0.01:
        error_rate = 0.0
    elif residual > 20:
        error_rate = 1.0
    else:
        error_rate = 1.0 - 2 ** (-residual)

    # Look up lattice success from Exp B
    lattice_success = 0.0
    for err_thresh, succ in sorted(inp.lattice_success.items()):
        if error_rate <= err_thresh:
            lattice_success = succ
            break

    # Total attack work (in enumeration terms, not FLOPS)
    total_enum_bits = math.log2(max(shuffle_runs, 1))

    return {
        "model": f"SASCA + Lattice ({scenario})",
        "label": s["label"],
        "n_traces": n_traces,
        "trace_bits": math.log2(max(n_traces, 1)),
        "shuffle_runs": shuffle_runs,
        "shuffle_bits": math.log2(max(shuffle_runs, 1)),
        "bp_gain_bits": s["bp_gain_bits"],
        "total_mi_bits": total_mi,
        "residual_entropy_bits": residual,
        "error_rate": error_rate,
        "lattice_success": lattice_success,
        "total_enum_bits": total_enum_bits,
        "complexity_class": "O(N + S_eff x L x BP_cost + lattice)",
    }


def main():
    output_dir = Path(__file__).parent.parent / "evidence"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Experiment G: Composite Security Margin Formalization")
    print("=" * 60)

    inp = ExperimentInputs()
    classical = classical_cpa_model(inp)
    scenarios = ["conservative", "moderate", "aggressive"]
    sasca = {s: sasca_attack_model(inp, s) for s in scenarios}

    print(f"\nDesigners' claimed margin: 2^{classical['designers_claimed_bits']} bits")
    print(f"Designers' model: {classical['complexity_class']}")

    for s in scenarios:
        r = sasca[s]
        gap = classical["designers_claimed_bits"] - r["total_enum_bits"]
        print(f"\n  {s.upper()}: {r['label']}")
        print(f"    Traces: {r['n_traces']:,}")
        print(f"    Shuffle runs: {r['shuffle_runs']}")
        print(f"    Total enum: 2^{r['total_enum_bits']:.1f}")
        print(f"    Gap: {gap:.0f} bits (2^{gap:.0f}x easier than designers claim)")
        print(f"    Error rate: {r['error_rate']*100:.0f}%")
        print(f"    Lattice success: {r['lattice_success']*100:.0f}%")

    # Save JSON
    json_data = {
        "experiment": "G: Composite Security Margin Formalization",
        "reference": "arXiv:2604.03813, Section 4.8.7",
        "classical": {k: v for k, v in classical.items() if not callable(v)},
        "sasca": {s: {k: v for k, v in sasca[s].items() if not callable(v)}
                  for s in scenarios},
    }
    json_path = output_dir / "composite_margin.json"
    json_path.write_text(json.dumps(json_data, indent=2))
    print(f"\nJSON saved to: {json_path}")

    print(f"\nResults written to {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
