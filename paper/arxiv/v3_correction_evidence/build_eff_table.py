#!/usr/bin/env python3
"""Emit eff_table_rows.txt: the BP-efficiency table (source.md 4.8.9) and the near-threshold cross-check, recomputed from
the archived L1+L3+L5+L7 / L1-L4 / L1-L6 runs in eff_sweep_results.jsonl (corrected all-variable criterion, cap 120) plus
the corrected L1+L3+L5+L7 runs at 5,000 already in rederivation_results.json. One numeric token per value line.

MI_1-layer and MI_genie come from evidence/sweep_results.json / genie_bound.json exactly as before; only the MI_BP column
and the derived efficiency change. Fails closed: every point must hold exactly the expected number of seeds, all seeds
distinct, and the two 5,000 pools must agree on their cardinality.

Run:  python3 paper/arxiv/v3_correction_evidence/build_eff_table.py
"""
import json, math, pathlib, sys

REPO = pathlib.Path(__file__).resolve().parents[3]
EV = REPO / "evidence"
HERE = pathlib.Path(__file__).resolve().parent
LOG2Q = math.log2(3329)

runs = [json.loads(l) for l in open(HERE / "eff_sweep_results.jsonl") if l.strip()]
manifest = json.load(open(HERE / "manifest_eff_sweep.json"))
want = {(j["config"], j["snr_n"]) for j in manifest}
by = {}
for r in runs:
    by.setdefault((r["config"], int(round(float(r["snr_n"])))), []).append(r)
missing = [k for k in want if len(by.get(k, [])) != 10]
if missing:
    print("INCOMPLETE — points without 10 runs:", sorted(missing), file=sys.stderr); sys.exit(1)
for k, rs in by.items():
    assert len({r["seed"] for r in rs}) == 10, k
    assert all(r["max_iter"] == 120 and r["convergence_tol"] == 1e-4 for r in rs), k

out = ["# BP-efficiency table and near-threshold cross-check, recomputed from the archived corrected-criterion runs",
       "# (eff_sweep_results.jsonl: 10 seeds per point, cap 120, tol 1e-4; 5,000 point: rederivation_results.json corrected runs)",
       "# one numeric token per value line", ""]
def emit(name, val): out.append(f"{name} = {val}")

# MI_1-layer per point from the committed sweep (unchanged column)
sw = json.load(open(EV / "sweep_results.json")); pts = sw if isinstance(sw, list) else (sw.get("results") or sw.get("sweep"))
mi1 = {p["snr_n"]: p["mi_1_layer"] for p in pts}

rr = json.load(open(HERE / "rederivation_results.json"))["runs"]
_p5k = {}
for r in rr:
    if r["config"] in ("L1+L3+L5+L7", "L1+L3+L5+L7 (ext)") and r["snr_n"] == 5000:
        prev = _p5k.get(r["seed"])
        if prev is None or r["max_iter"] > prev["max_iter"]: _p5k[r["seed"]] = r   # one row per seed; a deeper re-run supersedes
p5k = list(_p5k.values())
assert len(p5k) == 24, len(p5k)

for snr in (500, 1000, 1500, 2000, 3000, 5000, 10000):
    rs = p5k if snr == 5000 else by[("L1+L3+L5+L7", snr)]
    mi = sum(r["mi_bp"] for r in rs) / len(rs)
    fk = sum(1 for r in rs if r["full_key"])
    emit(f"eff_{snr}_n_seeds", len(rs)); emit(f"eff_{snr}_full_key", f"{fk}/{len(rs)}")
    emit(f"eff_{snr}_mi_bp", f"{mi:.2f}"); emit(f"eff_{snr}_efficiency_pct", f"{100 * mi / LOG2Q:.1f}%")
    emit(f"eff_{snr}_efficiency_pct_rounded", f"{round(100 * mi / LOG2Q)}%")  # the prose form (:884, :956)
    if snr in mi1 and mi1[snr] is not None: emit(f"eff_{snr}_mi_1layer", f"{mi1[snr]:.2f}")
    emit(f"eff_{snr}_iters", f"{min(r['bp_iterations'] for r in rs)}--{max(r['bp_iterations'] for r in rs)}")
    out.append("")

# near-threshold cross-check at 3,000 (:724) and the TOP-Bc points (2,000 / 3,000)
for cfg, label in (("L1+L3+L5+L7", "spread"), ("L1-L4", "L1L4"), ("L1-L6", "L1L6")):
    rs = by[(cfg, 3000)]; fk = sum(1 for r in rs if r["full_key"])
    emit(f"x3k_{label}_full_key", f"{fk}/10"); emit(f"x3k_{label}_mi_bp", f"{sum(r['mi_bp'] for r in rs)/10:.2f}")
    from math import sqrt
    z = 1.959963984540054; n = 10; p = fk / n
    centre = (p + z*z/(2*n)) / (1 + z*z/n); half = z * sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1 + z*z/n)
    emit(f"x3k_{label}_wilson_lo", f"{100*(centre-half):.1f}%"); emit(f"x3k_{label}_wilson_hi", f"{100*(centre+half):.1f}%")
rs = by[("L1+L3+L5+L7", 2000)]; fk = sum(1 for r in rs if r["full_key"])
emit("x2k_spread_full_key", f"{fk}/10"); emit("x2k_spread_mi_bp", f"{sum(r['mi_bp'] for r in rs)/10:.2f}")
p = fk / 10; centre = (p + z*z/20) / (1 + z*z/10); half = z * sqrt(p*(1-p)/10 + z*z/400) / (1 + z*z/10)
emit("x2k_spread_wilson_lo", f"{100*(centre-half):.1f}%"); emit("x2k_spread_wilson_hi", f"{100*(centre+half):.1f}%")

dest = HERE / "eff_table_rows.txt"
dest.write_text("\n".join(out) + "\n")
print("\n".join(out[4:])); print(f"wrote {dest.relative_to(REPO)}")
