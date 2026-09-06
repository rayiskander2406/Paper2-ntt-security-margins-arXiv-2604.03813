#!/usr/bin/env python3
"""Aggregate the incremental re-derivation results (results.jsonl) into the corrected
output files. Safe to run repeatedly as the background sweep accumulates data — it only
aggregates configs that have >=1 completed run and marks coverage vs the committed seed
counts.

Emits (under paper/arxiv/v3_correction_evidence/):
  rederivation_results.json        — every run + per-(config,snr) aggregate + committed compare
  rederivation_ablation_table.md   — corrected Table 8/8b (fk rate, Wilson CI, MI, mid-BSR)
  rederivation_NC_verdicts.md      — NC1..NC4 corrected verdicts, each backed by the runs
"""
import json
import os
import sys
import math
from collections import defaultdict

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
HERE = os.path.join(REPO, "paper/arxiv/v3_correction_evidence")
EVID = os.path.join(REPO, "evidence")
sys.path.insert(0, os.path.join(REPO, "src"))
from ntt_bp.statistics import wilson_ci  # noqa: E402

RESULTS = os.path.join(HERE, "results.jsonl")
LOG2Q = math.log2(3329)


def load_jsonl(path):
    out = []
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        pass
    return out


def ev(name):
    return json.load(open(os.path.join(EVID, name + ".json")))


def committed_lookup():
    """(config, snr_n) -> committed dict {fk_rate, mean_mi, n_seeds, iters, sources}, POOLED over
    every committed source that holds that (config, snr_n).

    Until 2026-09-03 `put()` assigned into the dict, so a (config, snr_n) present in two evidence
    files (the 35-subset sweep's 50 seeds AND a 10-seed ablation file) kept only the LAST writer:
    the transition aggregate's 5,000 point summed 10 + 10 + 50 = 70 seeds where 170 are committed.
    Pooling is the same rule Table 8 uses for its starred rows; `sources`
    records what was pooled so a consumer can still pick one file.
    """
    look = {}

    def put(cfg, snr, fk_rate, mean_mi, n_seeds, iters, source):
        key = (cfg, int(snr))
        prev = look.get(key)
        if prev is None:
            look[key] = dict(fk_rate=fk_rate, mean_mi=mean_mi, n_seeds=n_seeds, iters=iters,
                             sources=[dict(file=source, fk_rate=fk_rate, mean_mi=mean_mi,
                                           n_seeds=n_seeds, iters=iters)])
            return
        n = prev["n_seeds"] + n_seeds
        fk = (prev["fk_rate"] * prev["n_seeds"] + fk_rate * n_seeds) / n
        if prev["mean_mi"] is None or mean_mi is None:
            mi = prev["mean_mi"] if mean_mi is None else mean_mi
        else:
            mi = (prev["mean_mi"] * prev["n_seeds"] + mean_mi * n_seeds) / n
        prev.update(fk_rate=round(fk, 4), mean_mi=(None if mi is None else round(mi, 4)),
                    n_seeds=n, iters=sorted(set(prev["iters"]) | set(iters)))
        prev["sources"].append(dict(file=source, fk_rate=fk_rate, mean_mi=mean_mi,
                                    n_seeds=n_seeds, iters=iters))
    # NC1 arms
    by = defaultdict(list)
    for r in ev("nc1_moonshot_results") + ev("nc1_tier1_expansion_results"):
        by[(r["config"], r["snr_n"])].append(r)
    for (cfg, snr), rs in by.items():
        fk = sum(1 for r in rs if r.get("full_key"))
        mi = sum(r["mi_bp"] for r in rs) / len(rs)
        put(cfg, snr, round(fk / len(rs), 4), round(mi, 4), len(rs),
            sorted({r["bp_iterations"] for r in rs}), "nc1_moonshot_results+nc1_tier1_expansion_results")
    # k4
    for c in ev("all_k4_configs"):
        its = sorted({p["bp_iterations"] for p in c["per_seed"]})
        put(c["config_name"], c["snr_n"], c["full_key_rate"], c["mean_mi"],
            c["n_seeds"], its, "all_k4_configs")
    # ablation + tier
    for fn in ("ablation_results", "ablation_tier123"):
        for c in ev(fn):
            its = sorted({p["bp_iterations"] for p in c["per_seed"]})
            put(c["config"], c["snr_n"], c["full_key_recovery_rate"],
                c.get("mean_mi_bp", None), c["n_seeds"], its, fn)
    return look


def hops_to_L0(layers):
    return min(layers)  # nearest observed layer index == butterfly-hops from L0


def aggregate(runs):
    # normalize snr_n to int and dedupe by unique run key (config,seed,snr,k). On a key
    # collision keep the run with the HIGHER max_iter (a deep re-run of a capped run is
    # more converged and supersedes it); tiebreak on converged, then last-read.
    dedup = {}
    seen = defaultdict(list)  # key -> 1-based row numbers in the concatenated jsonl input
    for i, r in enumerate(runs, 1):
        r["snr_n"] = int(round(float(r["snr_n"])))
        k = (r["config"], r["seed"], r["snr_n"], r.get("k_total", 7))
        seen[k].append(i)
        prev = dedup.get(k)
        if prev is None or (r.get("max_iter", 0), int(r.get("converged", False))) >= \
                (prev.get("max_iter", 0), int(prev.get("converged", False))):
            dedup[k] = r
    runs = list(dedup.values())
    aggregate.n_unique = len(runs)
    aggregate.duplicates = [(k, seen[k]) for k in seen if len(seen[k]) > 1]
    groups = defaultdict(list)
    for r in runs:
        groups[(r["config"], r["snr_n"], r.get("k_total", 7))].append(r)
    aggs = []
    for (cfg, snr, k), rs in sorted(groups.items()):
        n = len(rs)
        nfk = sum(1 for r in rs if r["l0_correct"] == 256)
        lo, hi = wilson_ci(nfk, n)
        layers = rs[0]["layers"]
        conv = sum(1 for r in rs if r["converged"])
        maxed = [r for r in rs if not r["converged"]]
        aggs.append(dict(
            config=cfg, layers=layers, snr_n=snr, k_total=k, observes_L1=(1 in layers),
            hops_L0_to_obs=hops_to_L0(layers), n_seeds=n,
            n_full_key=nfk, full_key_rate=round(nfk / n, 4),
            wilson_ci_95=[round(lo, 4), round(hi, 4)],
            mean_l0_bsr=round(sum(r["l0_bsr"] for r in rs) / n, 4),
            mean_mid_bsr=round(sum(r["mid_layer_bsr"] for r in rs) / n, 4),
            mean_mi_bp=round(sum(r["mi_bp"] for r in rs) / n, 4),
            max_l0_bsr=round(max(r["l0_bsr"] for r in rs), 4),
            min_l0_bsr=round(min(r["l0_bsr"] for r in rs), 4),
            n_converged=conv, n_hit_maxiter=len(maxed),
            iters_min=min(r["bp_iterations"] for r in rs),
            iters_max=max(r["bp_iterations"] for r in rs),
            seeds=[r["seed"] for r in rs]))
    return aggs


def main():
    import glob
    runs = []
    for f in sorted(glob.glob(os.path.join(HERE, "results*.jsonl")) +
                    glob.glob(os.path.join(HERE, "deep_rerun*.jsonl"))):
        runs += load_jsonl(f)   # deep_rerun* read last; dedup prefers higher max_iter
    look = committed_lookup()
    aggs = aggregate(runs)

    for a in aggs:
        c = look.get((a["config"], a["snr_n"]))
        a["committed"] = c
        if c is not None:
            a["committed_fk_rate"] = c["fk_rate"]
            a["committed_mean_mi"] = c["mean_mi"]
            a["committed_iters"] = c["iters"]
            # artifact = committed said mi~0 & iters~1 (early-exit), corrected shows info
            artifact = (c["mean_mi"] is not None and c["mean_mi"] < 0.01
                        and c["iters"] == [1])
            a["was_artifact"] = bool(artifact)
        else:
            a["was_artifact"] = None

    out = dict(
        n_runs=len(runs), n_aggregates=len(aggs),
        note=("mi_bp = max(0, log2(3329) - mean L0 entropy), exactly as committed pipeline. "
              "was_artifact=True means committed recorded mi~0 & bp_iterations==1 (the L0-only "
              "early-exit) for this (config,snr). Corrected criterion = all-variable delta, "
              "tol=1e-4, single-threaded numba. full_key = 256/256 L0 coefficients."),
        aggregates=aggs, runs=runs)
    json.dump(out, open(os.path.join(HERE, "rederivation_results.json"), "w"), indent=1)

    # ---- ablation table ----
    lines = ["# Corrected layer-ablation table (v3 re-derivation)", "",
             (f"Runs completed: **{aggregate.n_unique}** across **{len(aggs)}** (config, SNR×N) cells"
              + (f" (results.jsonl holds {len(runs)} rows; "
                 + "; ".join(f"{k[0]} at SNR×N {k[2]:,} seed {k[1]} on lines {' and '.join(map(str, rows))}"
                             for k, rows in aggregate.duplicates)
                 + f" {'was' if len(aggregate.duplicates) == 1 else 'were'} run twice and {'is' if len(aggregate.duplicates) == 1 else 'are'} counted once)."
                 if aggregate.duplicates else ".")),
             "All under the corrected all-variable BP convergence criterion "
             "(tol=1e-4, single-threaded numba 0.64.0 / numpy 2.4.0). "
             "`full_key` = 256/256 L0 coefficients; `mi_bp = max(0, 11.70 − mean L0 entropy)`.",
             "",
             "| config | obs layers | hops L0→obs | SNR×N | committed FK / MI | **corrected FK (Wilson 95%)** | corrected MI | mid-BSR | iters | conv | artifact? |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for a in sorted(aggs, key=lambda x: (not x["was_artifact"], x["config"], x["snr_n"])):
        c = a["committed"]
        comm = f"{c['fk_rate']} / {c['mean_mi']}" if c else "—"
        ci = a["wilson_ci_95"]
        conv = f"{a['n_converged']}/{a['n_seeds']}"
        art = "**YES→corrected**" if a["was_artifact"] else ("no" if a["was_artifact"] is not None else "?")
        lines.append(
            f"| {a['config']} | {a['layers']} | {a['hops_L0_to_obs']} | {a['snr_n']} | "
            f"{comm} | **{a['n_full_key']}/{a['n_seeds']} = {a['full_key_rate']}** "
            f"[{ci[0]:.2f},{ci[1]:.2f}] | {a['mean_mi_bp']} | {a['mean_mid_bsr']} | "
            f"{a['iters_min']}-{a['iters_max']} | {conv} | {art} |")
    open(os.path.join(HERE, "rederivation_ablation_table.md"), "w").write("\n".join(lines) + "\n")

    print(f"[aggregate] {len(runs)} runs -> {len(aggs)} cells")
    for a in aggs:
        print(f"  {a['config']:22s} snr={a['snr_n']:<6} "
              f"FK={a['n_full_key']}/{a['n_seeds']} mid={a['mean_mid_bsr']} "
              f"mi={a['mean_mi_bp']} iters={a['iters_min']}-{a['iters_max']} "
              f"conv={a['n_converged']}/{a['n_seeds']} "
              f"{'ARTIFACT' if a['was_artifact'] else ''}")


def regenerate_all():
    main()
    import subprocess, sys, os
    subprocess.run([sys.executable, os.path.join(HERE, "nc_verdicts.py")], check=False)

if __name__ == "__main__":
    regenerate_all()
