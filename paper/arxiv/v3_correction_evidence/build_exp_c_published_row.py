#!/usr/bin/env python3
"""Emit the Exp C shuffling table exactly as the manuscript prints it.

exp_c_rsi_shuffling.py stores full-precision overheads (7.333..., 1.25). The manuscript prints
each overhead at the fewest decimals that stay within 1% of the archived median (7.3, 1.25), and
derives the RSI/RP ratio from the ARCHIVED median, not from the printed overhead (:389-391:
559 = round(4096/7.333), 3,277 = round(4096/1.25)).

Run:  python3 paper/arxiv/v3_correction_evidence/build_exp_c_published_row.py
"""
import json, pathlib

REPO = pathlib.Path(__file__).resolve().parents[3]
SRC = REPO / "evidence/experiments/rsi_vs_rp/shuffling_overhead.json"
rows = [c for c in json.loads(SRC.read_text())["config_results"]
        if c.get("mode") == "rsi" and c.get("sigma_noise") == 1.0]

out = ["Exp C -- RSI vs RP shuffling overhead, as published in source.md:388-392",
       f"source: {SRC.relative_to(REPO)}",
       "overhead printed at the fewest decimals within 1% of the archived median; ratio derived from the ARCHIVED median",
       ""]
for c in sorted(rows, key=lambda c: c["sigma_bias"]):
    oh = c["overhead_median"]
    r = next(round(oh, d) for d in (0, 1, 2, 3) if abs(round(oh, d) - oh) <= 0.01 * oh)
    out.append(f"sigma_bias {c['sigma_bias']:<4} overhead {r:<8} raw {oh:<20} ratio {round(4096.0/oh):,}")
dest = REPO / "paper/arxiv/v3_correction_evidence/exp_c_published_row.txt"
dest.write_text("\n".join(out) + "\n")
print("\n".join(out[4:]))
print(f"wrote {dest.relative_to(REPO)}")
