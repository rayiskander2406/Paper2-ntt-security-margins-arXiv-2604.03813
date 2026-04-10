# Partial NTT Masking in PQC Hardware: A Security Margin Analysis

[![arXiv](https://img.shields.io/badge/arXiv-2604.03813-b31b1b.svg)](https://arxiv.org/abs/2604.03813)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

Artifact repository for reproducing results from [arXiv:2604.03813](https://arxiv.org/abs/2604.03813).

## Abstract

We present a Security Margin Audit methodology for evaluating partially masked NTT hardware in post-quantum cryptographic accelerators. Applying this methodology to the Adams Bridge ML-DSA/ML-KEM accelerator, we show that masking only 7 of 8 INTT layers leaves security margins 2^25 to 2^29 below claimed levels under pro-defender assumptions. A full-scale belief propagation attack on the complete ML-KEM INTT factor graph achieves 100% coefficient recovery at SNR x N = 3000 (30 traces at SNR = 100), with 30 out of 30 full-key recoveries across multiple seeds. We contribute the Security Margin Audit framework, a SASCA belief propagation pipeline validated on production-scale factor graphs, and 19 formal SMT proofs (Z3 + CVC5) establishing the algebraic backbone of our analysis.

## Quick Start

```bash
git clone https://github.com/rayiskander/ntt-security-margins.git
cd ntt-security-margins
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"

# Verify pre-computed results match paper claims (~1 min)
python reproduce.py --verify

# Run analytical experiments + formal proofs (~15 min)
python reproduce.py --quick

# Run everything including full BP sweep (~24 hours)
python reproduce.py --full
```

## Repository Structure

```
ntt-security-margins/
├── reproduce.py                  # Main reproduction entry point
├── experiments/                  # All paper experiments
│   ├── exp_a_factor_graph.py     # Exp A: Factor graph construction + treewidth
│   ├── exp_b_lattice.py          # Exp B: Lattice sensitivity analysis
│   ├── exp_c_rsi_shuffling.py    # Exp C: RSI shuffling countermeasures
│   ├── exp_d_rtl_constants.py    # Exp D: RTL constant extraction (SNR)
│   ├── exp_e_template_bridge.py  # Exp E: Template-to-BP bridge
│   ├── exp_f_2layer_bp.py        # Exp F: 2-layer BP validation
│   ├── exp_g_composite_margin.py # Exp G: Composite security margin
│   ├── exp_h_monte_carlo.py      # Exp H: Monte Carlo on minimal graph
│   ├── exp_i_full_scale_sweep.py # Exp I: Full-scale BP sweep (120 trials)
│   ├── exp_i_ablation.py         # Exp I: Layer ablation (14 configs)
│   ├── exp_i_nc1_barrier.py      # Exp I: NC1 barrier (no-L1 configs)
│   ├── exp_i_nc4_validation.py   # Exp I: NC4 held-out validation
│   ├── exp_i_convergence.py      # Exp I: BP convergence analysis
│   ├── exp_i_damping.py          # Exp I: Damping sensitivity
│   ├── exp_i_key_enumeration.py  # Exp I: Key enumeration bounds
│   ├── exp_i_genie_bound.py      # Exp I: Genie-aided lower bound
│   └── exp_i_fips203_verify.py   # Exp I: FIPS 203 NTT correctness
├── proofs/                       # Formal SMT proofs
│   ├── paper_formal_proofs.py    # T1-T5 combined proof suite
│   ├── T1_value_independence_distributional.py
│   ├── T2_boolean_reparametrization_round_trip.py
│   ├── T3_arithmetic_reparametrization_round_trip.py
│   ├── T4_no_overflow_assertion.py
│   ├── T5_mlkem_bias_ratio.py
│   ├── T6_small_instance_value_independence.py
│   ├── nc3_fourier_contraction.py  # NC3 gap-contraction proof
│   └── run_all_proofs.py         # Run all 19 proof checks
├── evidence/                     # Pre-computed results (JSON)
│   ├── sweep_results.json        # Full 120-trial BP sweep
│   ├── ablation_results.json     # Layer ablation results
│   ├── ablation_tier123.json     # Extended tier 1-3 ablation
│   ├── convergence_results.json  # BP convergence data
│   ├── nc1_moonshot_results.json # NC1 barrier evidence
│   ├── nc3_proof.json            # NC3 statistical proof
│   ├── nc4_validation.json       # NC4 held-out validation
│   ├── paper_proofs.json         # Formal proof results
│   └── ...                       # Additional evidence files
├── src/ntt_bp/                   # Core library
├── tests/                        # Unit tests
├── pyproject.toml                # Package configuration
└── requirements.txt              # Pinned dependencies
```

## Reproducing Paper Results

| Paper Reference | Experiment | Command | Runtime | Key Claim |
|----------------|------------|---------|---------|-----------|
| Table 7 (Section 4.8.9) | Exp I: Full-scale BP sweep | `python experiments/exp_i_full_scale_sweep.py` | ~5h | 100% recovery at SNR x N = 3000 |
| Table 8 (Section 4.8.9) | Exp I: Layer ablation | `python experiments/exp_i_ablation.py` | ~10h | 4 spread layers > 6 consecutive |
| Section 4.8.1 | Exp A: Factor graph | `python experiments/exp_a_factor_graph.py` | ~30s | Treewidth > 30; 512 RSI runs |
| Section 4.8.2 | Exp B: Lattice sensitivity | `python experiments/exp_b_lattice.py` | ~30m | 47% at 1% error, 0% at 10% |
| Section 4.8.3 | Exp C: RSI shuffling | `python experiments/exp_c_rsi_shuffling.py` | ~10m | RSI 7.3x at sigma_bias/sigma = 0.3 |
| Section 4.8.4 | Exp D: RTL constants | `python experiments/exp_d_rtl_constants.py` | instant | SNR = 0.0027 (butterfly) |
| Section 4.8.5 | Exp E: Template bridge | `python experiments/exp_e_template_bridge.py` | instant | 992 traces for MI exhaustion |
| Section 4.8.6 | Exp F: 2-layer BP | `python experiments/exp_f_2layer_bp.py` | ~1h | 3.9-bit gain at SNR x N = 10^4 |
| Section 4.8.7 | Exp G: Composite margin | `python experiments/exp_g_composite_margin.py` | instant | 37-bit attack-model gap |
| Section 4.8.8 | Exp H: Monte Carlo | `python experiments/exp_h_monte_carlo.py` | ~1h | >50% error on minimal graph |
| Section 4.8.9 | NC1 barrier | `python experiments/exp_i_nc1_barrier.py` | ~3h | MI approx 0 across all no-L1 configs |
| Section 4.8.9 | NC4 validation | `python experiments/exp_i_nc4_validation.py` | ~1h | {1,3,4,7} validates k >= 4 |
| Claim C6 | Formal proofs (19 checks) | `python proofs/paper_formal_proofs.py` | ~60s | All pass (Z3 + CVC5) |
| Section 4.8.9 | NC3 proof | `python proofs/nc3_fourier_contraction.py` | ~1s | Fisher p = 0.0083 |

## Experiments

**Analytical experiments (A, C, D, E, G)** derive security parameters from closed-form analysis of the NTT structure, RTL constants, and information-theoretic bounds. These run in seconds to minutes and require no simulation.

**Simulation experiments (F, H, I)** run belief propagation on NTT factor graphs of varying scale. Experiment F validates on a 2-layer subgraph; Experiment H uses Monte Carlo sampling on a minimal graph to quantify approximation error; Experiment I runs the full 7-layer ML-KEM INTT factor graph (256 coefficients, 896 butterflies) across 120 trials at 8 SNR x N operating points, plus 14 layer-ablation configurations with 10 seeds each.

**Formal proofs** encode algebraic properties as SMT constraints verified by Z3 and CVC5. The proof suite covers value independence (T1), Boolean and arithmetic reparametrization round-trips (T2, T3), overflow absence (T4), ML-KEM bias ratios (T5), and universal finite-field value independence (T6). The NC3 gap-contraction proof uses Fisher's exact test on empirical ablation data.

## Hardware Requirements

- **Minimum:** 8 GB RAM, any modern CPU (for `--quick` and `--verify` modes)
- **Recommended:** 16 GB RAM, multi-core CPU (for full BP experiments)
- **Full suite:** Apple M2 or equivalent, ~24 hours total compute
- **Note:** Numba JIT compilation adds ~2 minutes of startup time on first run

## Dependencies

| Package | Version | Required | Purpose |
|---------|---------|----------|---------|
| numpy | >= 1.24 | Yes | Array operations |
| numba | >= 0.58 | Yes | JIT-accelerated BP message passing |
| scipy | >= 1.10 | Yes | Fisher exact test (NC3 proof) |
| z3-solver | >= 4.12 | Yes | SMT formal proofs |
| networkx | >= 3.0 | Yes | Factor graph treewidth (Exp A) |
| fpylll | >= 0.6 | Optional | Lattice reduction (Exp B) |
| CVC5 | any | Optional | Universal finite field proof (T6) |

## Citation

```bibtex
@misc{iskander2026partial,
  title={Partial {NTT} Masking in {PQC} Hardware: A Security Margin Analysis},
  author={Iskander, Ray and Kirah, Khaled},
  year={2026},
  eprint={2604.03813},
  archivePrefix={arXiv},
  primaryClass={cs.CR}
}
```

## License

Apache License 2.0. See [LICENSE](LICENSE).
