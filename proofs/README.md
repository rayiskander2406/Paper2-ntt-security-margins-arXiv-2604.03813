# Formal Proofs

`paper_formal_proofs.py` is the machine-verified algebraic backbone of
"Partial NTT Masking in PQC Hardware: A Security Margin Analysis" (arXiv:2604.03813):
theorems T1–T18 in Z3 (Tier A: formal proofs; Tier B: verified constants), plus a CVC5
dual-prover entry (T6_CVC5) for the GS butterfly DOF reduction over F_q that runs when a
CVC5 binary is available. It writes `evidence/paper_proofs.json`.

## Running

```bash
python proofs/paper_formal_proofs.py
```

## CVC5 (optional)

The GS butterfly DOF-reduction proof (T6 / T6_CVC5) uses CVC5's finite field theory
(`QF_FF` logic) for universal proof over F_q. Without CVC5, Z3 proves it for specific q
values only.

```bash
# Download CVC5 binary: https://cvc5.github.io/downloads.html
# Place binary in PATH or set CVC5_BINARY environment variable
export CVC5_BINARY=/path/to/cvc5
```

## Dependencies

- `z3-solver` (required)
- `cvc5` binary (optional)
