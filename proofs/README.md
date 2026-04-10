# Formal Proofs

Machine-verified algebraic proofs supporting the claims in
"Partial NTT Masking in PQC Hardware: A Security Margin Analysis"
(arXiv:2604.03813).

## Proof Suite

| Proof | Description | Solver | Time |
|-------|-------------|--------|------|
| T1 | Value independence (distributional) | Z3 | <1s |
| T2 | Boolean reparametrization round-trip | Z3 | <1s |
| T3 | Arithmetic reparametrization round-trip | Z3 | <1s |
| T4 | No-overflow assertion | Z3 | <1s |
| T5 | ML-KEM bias ratio | Z3 | <1s |
| T6 | GS butterfly DOF reduction (universal) | CVC5 (FF) | <100ms |
| NC3 | Gap >= 3 kills BP recovery (Fisher exact) | SciPy | <1s |

## Running

```bash
# Run complete proof suite
python proofs/run_all_proofs.py

# Run individual proofs
python proofs/paper_formal_proofs.py --verbose

# Run NC3 proof
python proofs/nc3_fourier_contraction.py
```

## CVC5 Installation (Optional)

T6 uses CVC5's finite field theory (`QF_FF` logic) for universal proof
over F_q. Without CVC5, Z3 proves T6 for specific q values only.

```bash
# Download CVC5 binary
# See: https://cvc5.github.io/downloads.html
# Place binary in PATH or set CVC5_BINARY environment variable
export CVC5_BINARY=/path/to/cvc5
```

## Dependencies

- `z3-solver` (required)
- `scipy` (for NC3 Fisher exact test)
- `cvc5` binary (optional, for T6 universal proof)
