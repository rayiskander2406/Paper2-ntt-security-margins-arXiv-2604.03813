#!/usr/bin/env python3
"""Aggregate the gap-transition sweep (8k/12k/15k) into the recovery-curve knee for v3,
assembling the full paired curve for the three gap->=3 topologies:

    5,000 (committed) -> 8k/12k/15k (this sweep) -> 20,000 (gap20k sweep) -> 50,000

Standalone: does NOT run aggregate.py, does NOT touch any committed
artifact. Writes only NEW parameter-stamped files:
    gap_transition_agg.json                 -- per-(config,snr) + per-snr aggregates
    recovery_curve_gap_configs.{pdf,png}    -- the knee figure

Canonical recovery metric == aggregate.py's: full_key = (l0_correct == 256). Wilson 95% CI.
Reports n_hit_maxiter per cell -- a capped run (120 iters, not converged) is the OPPOSITE of
the NC1 early-exit artifact (it spent the full budget), so recovery at low SNR is a LOWER bound,
never an early-exit-fabricated null.
"""
import json, os, sys, math, glob
from collections import defaultdict

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
HERE = os.path.join(REPO, "paper/arxiv/v3_correction_evidence")
sys.path.insert(0, os.path.join(REPO, "src"))
from ntt_bp.statistics import wilson_ci  # noqa: E402
sys.path.insert(0, HERE)
import aggregate as agg_committed  # reuse committed_lookup for the 5k/50k committed points

GAPS = ("L1+L2+L3+L7", "L1+L2+L6+L7", "L1+L5+L6+L7")
MAX_ITER_CAP = 120
EXPF_CEILING = 657  # max reachable SNR*N within the paper's 10k-trace budget


def load_jsonl(path):
    out = []
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return out


def cell(runs):
    """Per-(config,snr) stats from raw runs, matching aggregate.py conventions."""
    n = len(runs)
    nfk = sum(1 for r in runs if r["l0_correct"] == 256)
    lo, hi = wilson_ci(nfk, n)
    capped = sum(1 for r in runs if not r["converged"])
    return dict(
        n_seeds=n, n_full_key=nfk, full_key_rate=round(nfk / n, 4),
        wilson_ci_95=[round(lo, 4), round(hi, 4)],
        n_converged=n - capped, n_hit_maxiter=capped,
        mean_mi_bp=round(sum(r["mi_bp"] for r in runs) / n, 4),
        mean_mid_bsr=round(sum(r["mid_layer_bsr"] for r in runs) / n, 4),
        iters_min=min(r["bp_iterations"] for r in runs),
        iters_max=max(r["bp_iterations"] for r in runs),
        seeds=sorted(r["seed"] for r in runs))


def find_50k_runs():
    """Look for gap-config runs at snr=50000 in the LOCAL re-derivation raw data
    (results*.jsonl / rederivation_results.json). Returns {config: [runs]} or {}."""
    raw = []
    for f in glob.glob(os.path.join(HERE, "results*.jsonl")):
        raw += load_jsonl(f)
    rr = os.path.join(HERE, "rederivation_results.json")
    if os.path.exists(rr):
        raw += json.load(open(rr)).get("runs", [])
    out = defaultdict(list)
    # Dedup by (config, seed): results*.jsonl and rederivation_results.json are the SAME
    # re-derivation with identical 50k seed sets, so reading both double-counts every run
    # (was: 24/config = 72 total; true unique = 12/config = 36).
    seen = set()
    for r in raw:
        if r.get("config") in GAPS and int(round(float(r.get("snr_n", -1)))) == 50000 \
                and "l0_correct" in r:
            key = (r["config"], r["seed"])
            if key in seen:
                continue
            seen.add(key)
            out[r["config"]].append(r)
    return out


def main():
    # ---- collect raw runs per (config, snr) ----
    per = defaultdict(list)  # (config, snr) -> [runs]
    for r in load_jsonl(os.path.join(HERE, "gap_transition_results.jsonl")):
        per[(r["config"], int(round(float(r["snr_n"]))))].append(r)   # 8k/12k/15k
    for r in load_jsonl(os.path.join(HERE, "gap20k_results.jsonl")):
        per[(r["config"], int(round(float(r["snr_n"]))))].append(r)   # 20k
    for cfg, rs in find_50k_runs().items():
        per[(cfg, 50000)] += rs                                       # 50k if locally present

    look = agg_committed.committed_lookup()  # committed 5k (and maybe 50k) FK rates

    # ---- assemble curve points, aggregating across the 3 gap configs per SNR ----
    SNRS = [5000, 8000, 12000, 15000, 20000, 50000]
    curve = []
    per_config = {c: {} for c in GAPS}
    for snr in SNRS:
        raw_runs, provenance = [], None
        for cfg in GAPS:
            rs = per.get((cfg, snr))
            if rs:
                per_config[cfg][snr] = cell(rs)
                raw_runs += rs
        if raw_runs:  # we have raw runs at this SNR
            provenance = ("this sweep" if snr in (8000, 12000, 15000)
                          else "gap20k sweep" if snr == 20000 else "local re-derivation")
            c = cell(raw_runs)
        else:  # fall back to committed FK rates (5k, possibly 50k)
            fk_rates = [look[(cfg, snr)]["fk_rate"] for cfg in GAPS if (cfg, snr) in look]
            ns = [look[(cfg, snr)]["n_seeds"] for cfg in GAPS if (cfg, snr) in look]
            if not fk_rates:
                continue  # no data at all -> skip point (honest omission)
            n = sum(ns)
            nfk = int(round(sum(r * s for r, s in zip(fk_rates, ns))))
            lo, hi = wilson_ci(nfk, n)
            c = dict(n_seeds=n, n_full_key=nfk, full_key_rate=round(nfk / n, 4),
                     wilson_ci_95=[round(lo, 4), round(hi, 4)],
                     n_converged=None, n_hit_maxiter=None,
                     mean_mi_bp=None, mean_mid_bsr=None, iters_min=None, iters_max=None,
                     seeds=None)
            provenance = "committed"
        c.update(snr_n=snr, provenance=provenance, reachable=(snr <= EXPF_CEILING))
        curve.append(c)

    out = dict(
        note=("Full-key recovery for the three gap->=3 topologies vs SNR*N. "
              "full_key=(l0_correct==256); Wilson 95% CI; corrected all-variable BP "
              f"(tol=1e-4, max_iter={MAX_ITER_CAP}). n_hit_maxiter = runs that spent the full "
              "iteration budget without converging (a conservative floor, NOT an early-exit null). "
              f"Exp F reachable ceiling = {EXPF_CEILING} (10k-trace budget); every recovery point "
              "sits far above it."),
        configs=GAPS, expf_ceiling=EXPF_CEILING,
        curve=curve, per_config=per_config)
    json.dump(out, open(os.path.join(HERE, "gap_transition_agg.json"), "w"), indent=1)

    # ---- console table ----
    print(f"[transition] curve points: {len(curve)}")
    print(f"{'SNRxN':>7} {'FK':>7} {'rate':>7} {'Wilson95':>15} {'capped':>7} {'iters':>9}  prov")
    for c in curve:
        ci = c["wilson_ci_95"]
        cap = "-" if c["n_hit_maxiter"] is None else f"{c['n_hit_maxiter']}/{c['n_seeds']}"
        it = "-" if c["iters_min"] is None else f"{c['iters_min']}-{c['iters_max']}"
        print(f"{c['snr_n']:>7} {c['n_full_key']:>3}/{c['n_seeds']:<3} "
              f"{100*c['full_key_rate']:>6.1f}% [{ci[0]:.2f},{ci[1]:.2f}]  {cap:>7} {it:>9}  "
              f"{c['provenance']}{'  (reachable)' if c['reachable'] else ''}")

    make_figure(curve)


def make_figure(curve):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    xs = [c["snr_n"] for c in curve]
    ys = [100 * c["full_key_rate"] for c in curve]
    lo = [100 * c["wilson_ci_95"][0] for c in curve]
    hi = [100 * c["wilson_ci_95"][1] for c in curve]
    yerr = [[y - l for y, l in zip(ys, lo)], [h - y for y, h in zip(ys, hi)]]

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    # unreachable shading: everything to the RIGHT of the Exp F ceiling
    ax.axvspan(EXPF_CEILING, max(xs) * 1.6, color="#d9534f", alpha=0.06, zorder=0)
    ax.axvline(EXPF_CEILING, color="#d9534f", ls="--", lw=1.3,
               label=f"Exp F reachable ceiling (SNR×N={EXPF_CEILING}, 10k traces)")
    ax.errorbar(xs, ys, yerr=yerr, fmt="o-", color="#0b5394", lw=1.8, ms=6,
                capsize=3, zorder=3, label="full-key recovery (3 gap≥3 configs)")
    for c, x, y in zip(curve, xs, ys):
        tag = f"{c['n_full_key']}/{c['n_seeds']}"
        ax.annotate(tag, (x, y), textcoords="offset points", xytext=(0, 9),
                    ha="center", fontsize=8, color="#333")
    ax.set_xscale("log")
    ax.set_xlabel("SNR × N  (log scale)")
    ax.set_ylabel("full-key recovery rate  (256/256 L0 coeffs)")
    ax.set_ylim(-6, 108)
    ax.set_title("Gap≥3 recovery is a smooth trace-cost ramp, not a barrier — but sits\n"
                 "entirely above the reachable operating range (corrected v3)", fontsize=10)
    ax.text(0.015, 0.5, "REACHABLE\n(≤ ceiling)", transform=ax.transAxes, fontsize=7.5,
            color="#3c763d", va="center", ha="left")
    ax.grid(True, which="both", ls=":", alpha=0.4)
    ax.legend(loc="lower right", fontsize=8, framealpha=0.9)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(HERE, f"recovery_curve_gap_configs.{ext}"), dpi=160)
    print("[transition] wrote recovery_curve_gap_configs.pdf / .png")


if __name__ == "__main__":
    main()
