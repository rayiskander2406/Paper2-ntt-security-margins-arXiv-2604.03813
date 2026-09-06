#!/usr/bin/env python3
"""Emit rederivation_NC_verdicts.md — the corrected NC1..NC4 verdicts, each backed by the
actual re-run cells in rederivation_results.json. Data-driven: this script extracts the
committed-vs-corrected quantities per condition; the prose verdict is written from those
numbers. Re-run after aggregate.py as data accumulates.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
AGG = os.path.join(HERE, "rederivation_results.json")


def cell(aggs, config, snr):
    for a in aggs:
        if a["config"] == config and a["snr_n"] == snr:
            return a
    return None


def row(a):
    if a is None:
        return "_(not yet run)_"
    c = a.get("committed")
    comm = f"{c['fk_rate']}/{c['mean_mi']}" if c else "—"
    return (f"corrected FK **{a['n_full_key']}/{a['n_seeds']}={a['full_key_rate']}** "
            f"(Wilson {a['wilson_ci_95']}), mid-BSR {a['mean_mid_bsr']}, MI {a['mean_mi_bp']}, "
            f"iters {a['iters_min']}-{a['iters_max']}, conv {a['n_converged']}/{a['n_seeds']} "
            f"| committed FK/MI {comm}")


def main():
    if not os.path.exists(AGG):
        print("no rederivation_results.json yet; run aggregate.py first")
        return
    data = json.load(open(AGG))
    aggs = data["aggregates"]
    L = []
    w = L.append
    w("# Corrected NC verdicts (v3 re-derivation)\n")
    w(f"_Backed by {data['n_runs']} completed runs. Every number traces to a cell in "
      f"rederivation_results.json. mi_bp = max(0, 11.70 − mean L0 entropy)._\n")

    # NC1
    w("## NC1 — claimed: masking L1 => structural barrier, MI=0 for ANY inference, any trace count")
    w("**Verdict: REFUTED — cost multiplier, not a barrier.**\n")
    w("The factor graph never disconnects L0 (masking = non-observation). Corrected no-L1 recovery:\n")
    for cfg in ["NC1-A_L2-L7", "NC1-B_L2+L4+L6+L7", "NC1-E_L2+L3+L5+L6+L7", "NC1-F_L3+L5+L7",
                "NC1-C_K8_L2-L8", "NC1-D_K8_L2+L4+L6+L8",
                "NC1-A_L2-L7_500K", "NC1-B_L2+L4+L6+L7_500K"]:
        for snr in (50000, 500000):
            a = cell(aggs, cfg, snr)
            if a:
                w(f"- **{cfg}** @{snr}: {row(a)}")
    w("")

    # NC1 via k4 no-L1 (cost-multiplier: 5k vs 50k)
    w("### NC1 cost-multiplier (15 no-L1 four-layer configs, SNR×N 5000 → 50000)")
    w("| config | @5000 (corrected FK / mid-BSR) | @50000 (corrected FK / mid-BSR) |")
    w("|---|---|---|")
    no_l1 = sorted({a["config"] for a in aggs if not a["observes_L1"] and a["config"].startswith("L")})
    for cfg in no_l1:
        a5 = cell(aggs, cfg, 5000)
        a50 = cell(aggs, cfg, 50000)
        f5 = f"{a5['full_key_rate']} / {a5['mean_mid_bsr']}" if a5 else "—"
        f50 = f"{a50['full_key_rate']} / {a50['mean_mid_bsr']}" if a50 else "—"
        w(f"| {cfg} | {f5} | {f50} |")
    w("")

    # NC3
    w("## NC3 — claimed: gap ≥ 3 consecutive unobserved layers kills BP recovery (0% for gap configs)")
    w("The 3 gap configs OBSERVE L1 (so not the iteration-1 artifact), but committed runs still "
      "early-exited via the L0-only check (L1+L5+L6+L7 @6 iters, L1+L2+L6+L7 @7-8) or hit the "
      "30-iter cap unconverged (L1+L2+L3+L7). Corrected + higher-iter re-run:\n")
    w("| gap config | @5000 (corrected FK / mid-BSR / MI) | @50000 (corrected FK / mid-BSR / MI) |")
    w("|---|---|---|")
    for cfg in ["L1+L2+L3+L7", "L1+L2+L6+L7", "L1+L5+L6+L7"]:
        a5 = cell(aggs, cfg, 5000)
        a50 = cell(aggs, cfg, 50000)
        f5 = f"{a5['full_key_rate']} / {a5['mean_mid_bsr']} / {a5['mean_mi_bp']}" if a5 else "—"
        f50 = f"{a50['full_key_rate']} / {a50['mean_mid_bsr']} / {a50['mean_mi_bp']}" if a50 else "—"
        w(f"| {cfg} | {f5} | {f50} |")

    # NC2 / NC4 notes
    w("## NC2 — output-layer (L7) observation")
    w("v2 already classified NC2 as cost-modulating, not isolated (line 854/G19: no dedicated "
      "L7-ablation). No new isolation run here; state as unresolved/cost-modulating.\n")
    w("## NC4 — minimum observed-layer count (k ≥ 4)")
    w("Emerged from the self-falsification fix ({1,4,7} k=3 satisfied R1-R3 but failed). "
      "The ablation cells (L1 only, L4 only, L1+L7, L1+L4+L7 …) speak to this — see the "
      "ablation table; recovery tracks total MI, not a hard k threshold.\n")

    open(os.path.join(HERE, "rederivation_NC_verdicts.md"), "w").write("\n".join(L) + "\n")
    print("wrote rederivation_NC_verdicts.md")


if __name__ == "__main__":
    main()
