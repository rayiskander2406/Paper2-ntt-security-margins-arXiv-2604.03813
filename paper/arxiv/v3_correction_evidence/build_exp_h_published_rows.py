#!/usr/bin/env python3
"""Emit Exp H's published rows exactly as source.md 4.8.8 prints them, from the PRIMARY artifact.

evidence/exp_h_monte_carlo.json stores, per SNR*N point, 10 trials with per-trial bsr / error_rate /
avg_entropy / mi_bp, the count of trials with error > 50% and a Wilson CI over those 10 trials. The
manuscript's table prints, per point: the L0 MAP error over the 80 per-coefficient decisions
(10 trials x 8 coefficients) as k/80 and a percentage, a Wilson 95% CI over those 80 decisions
(the convention the v1/v2 table used: its 98.8% [93.3%--99.8%] cell was exactly Wilson(79/80)),
the trial-mean L0 entropy and the trial-mean MI_BP.

Fails closed on any early-exit signature (a point where every trial reports the pre-fix entropy
11.693) and on any disagreement with Exp F at the two operating points.

Run:  python3 paper/arxiv/v3_correction_evidence/build_exp_h_published_rows.py
"""
import json, math, pathlib

REPO = pathlib.Path(__file__).resolve().parents[3]
EXPH = REPO / "evidence/exp_h_monte_carlo.json"
EXPF = REPO / "evidence/exp_f_2layer_bp.json"
N_COEFFS, N_TRIALS = 8, 10
OPERATING_POINTS = (300, 10_000)


def wilson(k, n, z=1.959963985):          # same function as build_table8_spread_pooled.py
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return centre - half, centre + half


def pct(x):
    v = round(100 * x, 1)
    return "100%" if v >= 100.0 else f"{v:.1f}%"


h = json.loads(EXPH.read_text())
f = json.loads(EXPF.read_text())
assert h["parameters"]["n_coeffs"] == N_COEFFS and h["parameters"]["n_trials"] == N_TRIALS
log2q = f["parameters"]["log2_q"]
frows = {p["snr_n"]: p for p in f["results"]}

out = ["Exp H -- Monte Carlo BP validation on the 2-layer ML-KEM subgraph, as published in source.md 4.8.8",
       f"source: {EXPH.relative_to(REPO)}  (regenerated under the all-variable convergence criterion)",
       "error = wrong L0 MAP decisions over 80 per-coefficient decisions per point (10 trials x 8 coefficients), from per-trial bsr",
       "ci = Wilson 95% interval over those 80 decisions (z = 1.959963985); trials>50% and its CI are stored in the artifact as-is",
       "entropy and mi are means over the 10 trials (artifact stores mean_mi_bp; the entropy mean is derived from per_trial avg_entropy)",
       ""]
for p in h["results"]:
    sn = p["snr_n"]
    trials = p["per_trial"]
    assert len(trials) == N_TRIALS, sn
    ents = [t["avg_entropy"] for t in trials]
    assert not all(abs(e - 11.693) < 5e-4 for e in ents), f"early-exit signature at snr_n={sn}"
    wrong = sum(round(N_COEFFS * (1 - t["bsr"])) for t in trials)
    n = N_COEFFS * N_TRIALS
    err = wrong / n
    assert abs(err - p["mean_error_rate"]) < 1e-3, (sn, err, p["mean_error_rate"])
    lo, hi = wilson(wrong, n)
    ent = sum(ents) / len(ents)
    mi = p["mean_mi_bp"]
    assert abs((log2q - ent) - mi) < 2e-3, (sn, ent, mi)
    if sn in OPERATING_POINTS:
        assert abs(mi - frows[sn]["mean_mi_bp"]) < 0.05, (sn, mi, frows[sn]["mean_mi_bp"])
    tlo, thi = p["wilson_ci_above_50pct"]
    out.append(
        f"snr_n {sn:<6} error {pct(err):<6} wrong {wrong}/{n}  ci [{pct(lo)}, {pct(hi)}]  "
        f"entropy {round(ent, 1):<5} raw {round(ent, 3):<7} mi {mi:.2f} raw {mi:<7}  "
        f"trials_above_50pct {p['n_error_above_50pct']}/{p['n_trials']}  ci_trials [{pct(tlo)}, {pct(thi)}]"
        + ("   [operating point]" if sn in OPERATING_POINTS else "")
    )

dest = REPO / "paper/arxiv/v3_correction_evidence/exp_h_published_rows.txt"
dest.write_text("\n".join(out) + "\n")
print("\n".join(out))
print(f"wrote {dest.relative_to(REPO)}")
