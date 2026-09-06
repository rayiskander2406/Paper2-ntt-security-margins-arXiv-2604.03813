"""Phase A: contamination map from committed evidence.

Partition every ablation / NC1 / NC3 config by whether the early-exit artifact
touched it. Tell = bp_iterations: a config the L0-only early-exit corrupted ran
~1 iteration; a clean config (observes L1, so L0 moves at iter 1) ran many.
Also flag observes_L1 (masking L1 = L1 absent from observed layers).
"""
import json, os
from collections import defaultdict

EV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "evidence")


def load(name):
    with open(os.path.join(EV, name)) as f:
        return json.load(f)


def layers_of(rec):
    for k in ("layers", "observe_layers", "observed_layers"):
        if k in rec and isinstance(rec[k], list):
            return rec[k]
    return None


def iters_of(rec):
    for k in ("bp_iterations", "n_iter", "iterations", "bp_iter"):
        if k in rec:
            return rec[k]
    return None


def fk_of(rec):
    for k in ("full_key", "fk"):
        if k in rec:
            return bool(rec[k])
    if "bsr" in rec:
        return rec["bsr"] >= 0.999
    if "l0_bsr" in rec:
        return rec["l0_bsr"] >= 0.999
    return None


def analyze_list(name):
    try:
        data = load(name)
    except FileNotFoundError:
        print(f"  [{name}] MISSING")
        return
    if not isinstance(data, list):
        print(f"  [{name}] not a list (type {type(data).__name__}); keys="
              f"{list(data.keys())[:8] if isinstance(data, dict) else ''}")
        return
    if not data:
        print(f"  [{name}] empty")
        return
    print(f"\n=== {name} ({len(data)} records; sample keys: {sorted(data[0].keys())}) ===")
    agg = defaultdict(lambda: {"n": 0, "fk": 0, "iters": set(), "layers": None, "snr": set()})
    for rec in data:
        cfg = rec.get("config") or rec.get("config_name") or str(layers_of(rec))
        a = agg[cfg]
        a["n"] += 1
        if fk_of(rec):
            a["fk"] += 1
        it = iters_of(rec)
        if it is not None:
            a["iters"].add(it)
        if a["layers"] is None:
            a["layers"] = layers_of(rec)
        if "snr_n" in rec:
            a["snr"].add(rec["snr_n"])
    print(f"  {'config':32s} {'obsL1':5s} {'iters':12s} {'recov':>10s}  snr_n")
    for cfg, a in sorted(agg.items()):
        L = a["layers"]
        obsL1 = ("YES" if (L and 1 in L) else "no ") if L is not None else "?  "
        its = a["iters"]
        itrange = (f"{min(its)}-{max(its)}" if its else "?")
        contaminated = (L is not None and 1 not in L) and (its and max(its) <= 2)
        flag = "  <-- CONTAMINATED (no-L1 + <=2 iters)" if contaminated else ""
        rate = f"{a['fk']}/{a['n']}"
        snr = ",".join(str(int(s)) for s in sorted(a["snr"])) if a["snr"] else "?"
        print(f"  {str(cfg)[:32]:32s} {obsL1:5s} it={itrange:9s} {rate:>10s}  {snr}{flag}")


print("################ ABLATION / TOPOLOGY (SC-1) ################")
for f in ("ablation_results.json", "ablation_tier123.json", "all_k4_configs.json"):
    analyze_list(f)

print("\n################ NC1 (the barrier) ################")
for f in ("nc1_moonshot_results.json", "nc1_tier1_expansion_results.json"):
    analyze_list(f)

print("\n################ NC3 (gap) — dict summary ################")
try:
    nc3 = load("nc3_proof.json")
    sl = nc3.get("exhaustive_verification", {}).get("seed_level", {})
    print(f"  seed_level: {sl}")
    print(f"  (nc3_no_fk_seeds=0 is the '0% recovery for gap configs' claim — suspect if those")
    print(f"   gap configs leave L0 >=2 hops from the nearest observed layer.)")
except Exception as e:
    print(f"  nc3 load error: {e}")
