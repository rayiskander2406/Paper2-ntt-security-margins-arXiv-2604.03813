#!/usr/bin/env python3
"""Pool the three L1+L3+L5+L7 runs at SNR*N=5,000 into the Table 8 spread row.

Three runs exist at this exact configuration and budget. v1--v2 reported 30/30,
pooling only the first two and omitting the largest (48/50). They are poolable: same
config, same snr_n, same bp_iterations on every seed, and pairwise-disjoint seed sets.
This script re-derives the published row.

Run:  python3 paper/arxiv/v3_correction_evidence/build_table8_spread_pooled.py
"""
import json, math, pathlib

REPO = pathlib.Path(__file__).resolve().parents[3]
SRCS = ["evidence/ablation_results.json", "evidence/ablation_tier123.json",
        "evidence/all_k4_configs.json"]
CONFIG, SNR_N = "L1+L3+L5+L7", 5000


def row(path):
    for r in json.loads((REPO / path).read_text()):
        name = (r.get("config") or r.get("config_name")).replace(" (ext)", "")
        if name == CONFIG and r.get("snr_n") == SNR_N:
            return r
    raise SystemExit(f"{CONFIG} @ {SNR_N} not found in {path}")


def wilson(k, n, z=1.959963985):
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return round(100 * (centre - half), 1), round(100 * (centre + half), 1)


runs, seeds = [], []
for path in SRCS:
    r = row(path)
    per = r["per_seed"]
    runs.append({"source": path, "n_seeds": r["n_seeds"], "n_full_key": r["n_full_key"],
                 "seeds": [p["seed"] for p in per],
                 "bp_iterations": sorted({p["bp_iterations"] for p in per})})
    seeds.append({p["seed"] for p in per})

per_all = [p for path in SRCS for p in row(path)["per_seed"]]
n = len(per_all)
k = sum(1 for p in per_all if p["bsr"] == 1.0)
budgets = sorted({p["bp_iterations"] for p in per_all})

# poolability is asserted, not assumed -- the script fails closed if it breaks
assert len(set().union(*seeds)) == n, "seed sets overlap -- runs are NOT poolable"
assert budgets == [30], f"mixed BP budgets {budgets} -- runs are NOT poolable"

lo, hi = wilson(k, n)
out = {
    "config": CONFIG, "snr_n": SNR_N,
    "n_seeds": n, "n_full_key": k,
    "full_key_rate_pct": round(100 * k / n, 1),
    "wilson_ci_95_pct": [lo, hi],
    "mean_mi_bp": round(sum(p["mi_bp"] for p in per_all) / n, 2),
    "mean_mi_bp_full": sum(p["mi_bp"] for p in per_all) / n,
    "bp_iterations": budgets,
    "seeds_pairwise_disjoint": True,
    "failing_seeds": [p["seed"] for p in per_all if p["bsr"] != 1.0],
    "runs": runs,
    "note": ("Table 8 spread row. Pools all three runs of this config at this budget; "
             "the 48/50 run was omitted from the v1-v2 30/30 figure."),
}
dest = REPO / "paper/arxiv/v3_correction_evidence/table8_spread_pooled.json"
dest.write_text(json.dumps(out, indent=1) + "\n")
print(f"{k}/{n} = {out['full_key_rate_pct']}%  Wilson [{lo}%, {hi}%]  MI {out['mean_mi_bp']}")
print(f"wrote {dest.relative_to(REPO)}")

# literal-form companion (see nc1_superseded_counts.txt).
txt = REPO / "paper/arxiv/v3_correction_evidence/table8_spread_pooled.txt"
txt.write_text(
    "Table 8 spread row -- L1+L3+L5+L7 at SNR*N=5,000\n"
    "pooled over three disjoint-seed runs (10 + 20 + 50), all at 30 BP iterations\n"
    f"full_key      {k}/{n}\n"
    f"rate_pct      {out['full_key_rate_pct']}%\n"
    f"wilson_lo_pct {lo}%\n"
    f"wilson_hi_pct {hi}%\n"
    f"mean_mi_bp    {out['mean_mi_bp']}\n"
)
print(f"wrote {txt.relative_to(REPO)}")

