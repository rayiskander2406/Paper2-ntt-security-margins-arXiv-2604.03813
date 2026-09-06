#!/usr/bin/env python3
"""Emit the Exp E / Exp G chain values as LITERALS.

This computes each value from its primary input and writes it down, so the literals cite
committed output instead of prose, a formula, or a hand-typed string. Same contract as
`build_nc1_superseded_counts.py`: every emitted literal is guarded by an assertion, so if
an input moves the script DIES rather than quietly emitting a different number.

Two inputs, both primary:
  * `src/ntt_bp/constants.py:RTL_SNR` -- the published arXiv v2 SNR set. Exp E's live
    entry point.
  * `evidence/composite_margin.json` -- Exp G's committed OUTPUT, not its source. Its
    `807` and `4.279214` are what the script computed; the `807` at exp_g:54 is a
    hardcoded dataclass default, i.e. a transcription.

Design rule for the emitted file: exactly ONE numeric token on every value line.

CAUTION: the two scripts disagree about MI per trace. Exp E computes 0.023194 from
RTL_SNR; exp_g hardcodes 0.023198 (the paper's rounded-intermediate worked example).
Both yield 992 traces, which is why the divergence has stayed invisible. The residual
below is Exp G's, computed from Exp G's 0.023198; recomputing it from Exp E's value
gives 4.2825, not 4.279. That is a real open item, not a rounding artifact.

Regenerate:  python3 build_exp_e_g_literals.py
"""
import json
import math
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]  # v3_correction_evidence -> arxiv -> paper -> <repo root>
sys.path.insert(0, str(ROOT / "src"))

from ntt_bp.constants import RTL_SNR  # noqa: E402

OUT = HERE / "exp_e_g_literals.txt"
COMPOSITE = ROOT / "evidence" / "composite_margin.json"

MLDSA_COEFF_BITS = 23  # exp_e_template_bridge.py:13
GROUPS = ("butterfly", "mem_write", "mem_read")

# The published arXiv v2 set. constants.py deliberately keeps RTL_SNR at these values so
# the v2 chain still reproduces byte-for-byte; the corrected sets live beside it under
# different names. If RTL_SNR is ever repointed at a corrected set, this assertion trips
# rather than letting the artifact silently re-emit a different chain.
PUBLISHED_SNR = {"butterfly": 0.0027, "mem_write": 0.0155, "mem_read": 0.0033}
assert {k: RTL_SNR[k] for k in PUBLISHED_SNR} == PUBLISHED_SNR, (
    f"RTL_SNR moved off the published arXiv v2 set: "
    f"{ {k: RTL_SNR[k] for k in PUBLISHED_SNR} }"
)


def mi_per_transition(snr: float) -> float:
    """Gaussian channel capacity at SNR/2 -- exp_e_template_bridge.py:22, verbatim."""
    return 0.5 * math.log2(1 + snr / 2)


mi = {g: mi_per_transition(RTL_SNR[g]) for g in GROUPS}
per_round = sum(mi.values())
per_trace = per_round * 3  # three unmasked hardware rounds per INTT
traces_full = math.ceil(MLDSA_COEFF_BITS / per_trace)

assert f"{mi['butterfly']:.6f}" == "0.000973", f"Exp E butterfly MI is {mi['butterfly']:.6f}"
assert f"{mi['mem_write']:.6f}" == "0.005569", f"Exp E mem_write MI is {mi['mem_write']:.6f}"
assert f"{mi['mem_read']:.6f}" == "0.001189", f"Exp E mem_read MI is {mi['mem_read']:.6f}"
assert f"{per_round:.6f}" == "0.007731", f"Exp E MI per round is {per_round:.6f}"
assert f"{per_trace:.6f}" == "0.023194", f"Exp E MI per trace is {per_trace:.6f}"
assert traces_full == 992, f"Exp E full-MI trace count is {traces_full}, not 992"

# Exp G's conservative leg evaluated at ITS OWN hardcoded 807-trace input, and at the Exp E
# full-MI budget of 992 that Table 6 actually prints. The second is what settles which leg the
# table reports: Table 6 prints "Traces needed 992" beside "MI-theoretic residual 0.0", and a
# 0.0 residual is reproducible ONLY at n >= 992. At 807 the same model gives 4.279. The Moderate
# column confirms the row's meaning independently -- ceil((23.0-3.9)/0.023198) = 824, exactly what
# it prints, i.e. the same MI-exhaustion formula with Exp F's 3.9-bit BP gain subtracted.
MI_PER_TRACE_EXPG = 0.023198  # exp_g_composite_margin.py:53, the value exp_g derives its leg from
residual_at = lambda n: max(MLDSA_COEFF_BITS - n * MI_PER_TRACE_EXPG, 0)
expg_traces_at_expE_budget = math.ceil(MLDSA_COEFF_BITS / MI_PER_TRACE_EXPG)
assert expg_traces_at_expE_budget == 992, f"Exp E budget under exp_g's mi is {expg_traces_at_expE_budget}"
assert residual_at(992) == 0, f"residual at 992 is {residual_at(992)}, not exactly 0"
assert residual_at(991) > 0, "residual already exhausted at 991 -- the 992 threshold moved"
assert f"{residual_at(807):.3f}" == "4.279", f"residual at 807 is {residual_at(807)}"

cons = json.loads(COMPOSITE.read_text())["sasca"]["conservative"]
assert cons["n_traces"] == 807, f"exp_g conservative n_traces is {cons['n_traces']}"
assert f"{cons['residual_entropy_bits']:.3f}" == "4.279", (
    f"exp_g conservative residual is {cons['residual_entropy_bits']}"
)
mod = json.loads(COMPOSITE.read_text())["sasca"]["moderate"]
assert cons["lattice_success"] == 0.0, f"conservative lattice_success is {cons['lattice_success']}"
assert mod["lattice_success"] == 1.0, f"moderate lattice_success is {mod['lattice_success']}"
assert f"{cons['total_mi_bits']:.3f}" == "18.721", (
    f"exp_g conservative total MI is {cons['total_mi_bits']}"
)

lines = [
    "# Exp E / Exp G chain literals -- generated by build_exp_e_g_literals.py",
    "# inputs: src/ntt_bp/constants.py:RTL_SNR (published arXiv v2 set)",
    "#         evidence/composite_margin.json -> sasca.conservative (exp_g committed output)",
    "# Exactly one numeric token per value line.",
    "",
    f"exp_e_mi_butterfly_per_transition = {mi['butterfly']:.6f}",
    f"exp_e_mi_memwrite_per_transition = {mi['mem_write']:.6f}",
    f"exp_e_mi_memread_per_transition = {mi['mem_read']:.6f}",
    f"exp_e_mi_per_round = {per_round:.6f}",
    f"exp_e_mi_per_trace = {per_trace:.6f}",
    f"exp_e_traces_full_mi = {traces_full}",
    "",
    f"exp_g_conservative_residual_entropy_bits = {cons['residual_entropy_bits']:.3f}",
    f"exp_g_conservative_traces = {cons['n_traces']}",
    f"exp_g_conservative_total_mi_bits = {cons['total_mi_bits']:.3f}",
    "",
    "# The SAME model at the Exp E full-MI budget -- the leg Table 6 actually reports.",
    "# A 0.0 MI-theoretic residual is reproducible only at n >= 992; at 807 it is 4.279.",
    f"exp_g_conservative_traces_at_expE_budget = {expg_traces_at_expE_budget}",
    f"exp_g_conservative_residual_at_expE_budget = {residual_at(992):.1f}",
    "",
    "# Lattice-success cells, written WITH the percent sign because that is the literal form",
    "# Table 6 prints. composite_margin.json stores them as fractions (0.0 / 1.0).",
    f"exp_g_conservative_lattice_success_pct = {round(cons['lattice_success'] * 100)}%",
    f"exp_g_moderate_lattice_success_pct = {round(mod['lattice_success'] * 100)}%",
    "",
    "# full precision, for provenance only",
    f"# exp_e_mi_per_trace_full = {per_trace!r}",
    f"# exp_g_residual_full = {cons['residual_entropy_bits']!r}",
    "# NB exp_g computes its residual from a hardcoded mi_per_trace of 0.023198",
    "# (exp_g_composite_margin.py:53), not from the 0.023194 Exp E computes above.",
    "# Recomputed from Exp E's value the residual is 4.2825. Open item, not rounding.",
]
OUT.write_text("\n".join(lines) + "\n")
print("\n".join(lines))
