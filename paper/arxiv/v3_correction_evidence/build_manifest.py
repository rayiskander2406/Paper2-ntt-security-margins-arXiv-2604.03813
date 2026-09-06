#!/usr/bin/env python3
"""Build the re-derivation job manifest from the committed evidence JSONs.

Reads (never hand-types) every config/seed/snr_n/k_total from evidence/*.json and emits
an ordered manifest.json of jobs for rederive.py sweep. Ordering = scientific priority:
the DECISIVE configs (all NC1 arms + the 15 no-L1 ablation configs at both SNRs) come
first, so the core corrected findings land even if the long tail is still running.

Each job: {config, layers, snr_n, seed, k_total, max_iter, group}.
"""
import json
import os
import itertools

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
EVID = os.path.join(REPO, "evidence")
OUT = os.path.join(REPO, "paper/arxiv/v3_correction_evidence/manifest.json")

# Per-group max_iter (bounds per-job wall time at ~55 s/iter on this M5). Runs that hit
# the cap are flagged converged=False; decisive non-converged deep configs get a targeted
# re-run at a higher cap. @50k/500k get more headroom because the
# clean CONVERGED recovery number is the deliverable there; @5k plateaus at low recovery
# quickly (low signal), so 60 is ample.
MAXITER = {"nc1": 120, "nc1_500k": 120, "k4_noL1_5k": 40, "k4_noL1_50k": 120,
           "nc3_gap_5k": 55, "nc3_gap_50k": 120, "k4_L1_ctrl": 60,
           "ablation": 55, "ablation_tier": 55}


def load(name):
    return json.load(open(os.path.join(EVID, name + ".json")))


def key(j):
    return (j["config"], j["seed"], j["snr_n"], j["k_total"])


def main():
    jobs = []
    seen = set()

    def add(config, layers, snr_n, seed, k_total, group, sidx):
        j = dict(config=config, layers=list(layers), snr_n=int(snr_n), seed=int(seed),
                 k_total=int(k_total), max_iter=int(MAXITER.get(group, 120)),
                 group=group, sidx=int(sidx))
        if key(j) not in seen:
            seen.add(key(j))
            jobs.append(j)

    # ---- GROUP 1 (decisive): all 8 NC1 arms, every committed seed ----
    # 500K arms deprioritized within the group (10x traces).
    moon = load("nc1_moonshot_results")
    tier = load("nc1_tier1_expansion_results")
    from collections import defaultdict
    ci = defaultdict(int)
    for r in moon + tier:
        grp = "nc1_500k" if "500K" in r["config"] else "nc1"
        add(r["config"], r["layers"], r["snr_n"], r["seed"], r.get("k_total", 7), grp, ci[r["config"]])
        ci[r["config"]] += 1

    # ---- GROUP 2 (decisive): 15 no-L1 four-layer ablation configs ----
    # committed @5000 (contaminated) + paired @50000 (cost-multiplier demonstration)
    k4 = load("all_k4_configs")
    no_l1 = [c for c in k4 if 1 not in c["layers"]]
    l1 = [c for c in k4 if 1 in c["layers"]]
    assert len(no_l1) == 15 and len(l1) == 20, (len(no_l1), len(l1))
    for c in no_l1:
        seeds = [p["seed"] for p in c["per_seed"]]
        for i, s in enumerate(seeds):
            add(c["config_name"], c["layers"], 5000, s, 7, "k4_noL1_5k", i)
        for i, s in enumerate(seeds):          # same secret, 10x signal (paired)
            add(c["config_name"], c["layers"], 50000, s, 7, "k4_noL1_50k", i)

    # ---- GROUP 3: NC3 gap-violating configs (observe L1+L7, max gap>=3) ----
    # L1+L2+L3+L7 (gap L3->L7=3), L1+L2+L6+L7 (gap L2->L6=3), L1+L5+L6+L7 (gap L1->L5=3)
    nc3_gap = ["L1+L2+L3+L7", "L1+L2+L6+L7", "L1+L5+L6+L7"]
    for c in k4:
        if c["config_name"] in nc3_gap:
            seeds = [p["seed"] for p in c["per_seed"]][:12]   # >=12 for Wilson CI
            for i, s in enumerate(seeds):
                add(c["config_name"], c["layers"], 5000, s, 7, "nc3_gap_5k", i)
            for i, s in enumerate(seeds):
                add(c["config_name"], c["layers"], 50000, s, 7, "nc3_gap_50k", i)

    # ---- GROUP 4: 20 L1-observing k4 controls (validate harness == committed) ----
    for c in l1:
        seeds = [p["seed"] for p in c["per_seed"]][:8]     # validation subset
        for i, s in enumerate(seeds):
            add(c["config_name"], c["layers"], 5000, s, 7, "k4_L1_ctrl", i)

    # ---- GROUP 5: flagship + tier ablation (spread-vs-consecutive) ----
    for fn, grp in (("ablation_results", "ablation"), ("ablation_tier123", "ablation_tier")):
        for c in load(fn):
            seeds = [p["seed"] for p in c["per_seed"]][:8]
            for i, s in enumerate(seeds):
                add(c["config"], c["layers"], c["snr_n"], s, 7, grp, i)

    # Tiered breadth-first ordering so the DECISIVE scientific cells (NC1 across arms,
    # the no-L1 cost-multiplier at both SNRs, the NC3 gap configs at both SNRs) get
    # broad seed coverage FIRST — before spending hours on extra NC1 seeds, the L1
    # harness controls, and the flagship tail. Within a tier, sort by seed index so
    # seed-0 of every config lands before any seed-1 (a mid-run stop still leaves >=1
    # seed per decisive config).
    order = {"nc1": 0, "k4_noL1_5k": 1, "k4_noL1_50k": 2, "nc3_gap_5k": 3,
             "nc3_gap_50k": 4, "k4_L1_ctrl": 5, "ablation": 6, "ablation_tier": 7,
             "nc1_500k": 8}
    DECISIVE = {"nc1", "k4_noL1_5k", "k4_noL1_50k", "nc3_gap_5k", "nc3_gap_50k"}
    # tier 0: decisive groups, first 5 seeds/config (breadth). tier 1: L1 controls +
    # flagship, first 5 seeds. tier 2: everything else (extra decisive seeds, 500K, ...).
    def tier(j):
        if j["group"] in DECISIVE:
            return 0 if j["sidx"] < 5 else 2
        if j["group"] in ("k4_L1_ctrl", "ablation", "ablation_tier"):
            return 1 if j["sidx"] < 5 else 2
        return 2
    jobs.sort(key=lambda j: (tier(j), j["sidx"], order.get(j["group"], 9),
                             j["config"], j["snr_n"]))

    json.dump(jobs, open(OUT, "w"), indent=1)
    from collections import Counter
    c = Counter(j["group"] for j in jobs)
    print(f"wrote {OUT}: {len(jobs)} jobs")
    for g in sorted(c, key=lambda x: order.get(x, 9)):
        print(f"  {g:16s} {c[g]}")


if __name__ == "__main__":
    main()
