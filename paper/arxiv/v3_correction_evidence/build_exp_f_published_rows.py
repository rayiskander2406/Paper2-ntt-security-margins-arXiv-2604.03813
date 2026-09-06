#!/usr/bin/env python3
"""Emit Exp F's published rows exactly as source.md prints them, from the PRIMARY artifact.

The manuscript prints Exp F at one decimal (11.7 -> 8.1 bits, 3.6-bit gain) and derives the
withdrawn sensitivity-table trace counts from the ROUNDED gain (:390 convention: round, then
derive -- the earlier 824 = ceil((23.0-3.9)/0.023198) reproduces only from the rounded 3.9).
The measured figures bind straight to
evidence/exp_f_2layer_bp.json; this file exists for the DERIVED ones.

Fails closed: any early-exit signature (bp_iterations == 1) in the artifact, any disagreement
between Exp F and Exp H at a shared operating point, or any divergence between the two MI/trace
constants in use in the repo aborts the emit.

Run:  python3 paper/arxiv/v3_correction_evidence/build_exp_f_published_rows.py
"""
import json, math, pathlib

REPO = pathlib.Path(__file__).resolve().parents[3]
EXPF = REPO / "evidence/exp_f_2layer_bp.json"
EXPH = REPO / "evidence/exp_h_monte_carlo.json"
# Exp E / Table 6 MI-per-trace constants. exp_g_composite_margin.py:53 hardcodes 0.023198 and the
# manuscript's corrected :461 chain gives 0.023194; both are exercised and must agree on the ceil.
MI_PER_TRACE = (0.023198, 0.023194)
TARGET_BITS = 23.0
OPERATING_POINTS = (300, 10_000)     # the two "AB range" points named at source.md:486-489

f = json.loads(EXPF.read_text())
h = json.loads(EXPH.read_text())
log2q = f["parameters"]["log2_q"]
assert abs(log2q - math.log2(f["parameters"]["q"])) < 5e-5

rows = {}
for p in f["results"]:
    iters = [s["bp_iterations"] for s in p["per_seed"]]
    assert p["n_seeds"] == 5 and len(iters) == 5, p["snr_n"]
    assert min(iters) > 1, f"early-exit signature at snr_n={p['snr_n']}: iters={iters}"
    rows[p["snr_n"]] = p

hrows = {p["snr_n"]: p for p in h["results"]}
for sn in OPERATING_POINTS:
    assert sn in rows and sn in hrows, sn
    # Exp H is a 10-trial run of the same graph; its mean MI must sit within 0.05 bit of Exp F's
    assert abs(rows[sn]["mean_mi_bp"] - hrows[sn]["mean_mi_bp"]) < 0.05, (
        sn, rows[sn]["mean_mi_bp"], hrows[sn]["mean_mi_bp"])

out = ["Exp F -- 2-layer BP on the minimal ML-KEM subgraph, as published in source.md (4.8.6, Table 5, sensitivity table)",
       f"source: {EXPF.relative_to(REPO)}  (regenerated under the all-variable convergence criterion; no seed exits at iteration 1)",
       f"cross-check: {EXPH.relative_to(REPO)} agrees with Exp F to <0.05 bit at both operating points",
       f"log2_q printed 11.7  raw {log2q}",
       "entropy and gain printed at 1 decimal; traces = ceil((23.0 - gain_1dp) / mi_per_trace), derived from the ROUNDED gain (paper's convention)",
       ""]
for sn in sorted(rows):
    p = rows[sn]
    ent, gain = p["mean_entropy"], p["mean_mi_bp"]
    ent1, gain1 = round(ent, 1), round(gain, 1)
    if sn in OPERATING_POINTS:
        # the manuscript derives a trace count ONLY at the two operating points (sensitivity table)
        ceils = {mi: math.ceil((TARGET_BITS - gain1) / mi) for mi in MI_PER_TRACE}
        assert len(set(ceils.values())) == 1, f"MI/trace constants disagree on the ceil at snr_n={sn}: {ceils}"
        traces = next(iter(ceils.values()))
        out.append(f"snr_n {sn:<6} entropy {ent1:<5} raw {ent:<7} gain {gain1:<4} raw {gain:<7} traces {traces}   [operating point]")
    else:
        out.append(f"snr_n {sn:<6} entropy {ent1:<5} raw {ent:<7} gain {gain1:<4} raw {gain:<7}   [simulated, not an operating point; no trace count is published]")
    if sn == max(rows):
        out.append(f"note: the largest simulated gain is at snr_n {sn} ({gain1} bits), above the AB range; 10^4 is the upper OPERATING point, not the maximum gain")

dest = REPO / "paper/arxiv/v3_correction_evidence/exp_f_published_rows.txt"
dest.write_text("\n".join(out) + "\n")
print("\n".join(out))
print(f"wrote {dest.relative_to(REPO)}")
