#!/usr/bin/env python3
"""Regenerate the per-seed SCIENCE of evidence/ablation_tier123.json from the committed BP primitive.

This is the disjoint-seed EXTENSION that lifts Table 5's spread-4 config L1+L3+L5+L7
from 10/10 to 30/30 (and All(L1-L7) likewise), plus three companion configs. Same
experiment family as all_k4 (SNR*N=5000, max_bp_iter=30), same primitive, same
reproducibility posture.

Regenerated: per_seed {bsr, mi_bp, entropy, map_error, bp_iterations} + per-config
aggregates. Carried from the committed spec: config identity, seed list, n_seeds.
The tier123 seeds use a per-config base (group*1_000_000 + SNR_N) that is a recorded
design choice, not a layer formula — so the emitter carries the base from the spec and
verifies the intra-config 100000 stride. `time_s` is machine-dependent, excluded from
the reproducibility claim (science-identical, not byte-identical).

Usage:
    python3 emit_ablation_tier123.py --out /tmp/regen_tier123.json [--workers N]
    python3 emit_ablation_tier123.py --dry
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
           "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
import sys, json, time, math, argparse, multiprocessing
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "src"))
from ntt_bp import simulate_attack, MLKEM_Q, warmup_numba, wilson_ci

LOG2Q = math.log2(MLKEM_Q)
SNR_N, MAX_BP_ITER = 5000, 30
SPEC_PATH = REPO / "evidence" / "ablation_tier123.json"


def layers_of(name):
    name = name.replace("(ext)", "").strip()
    if name.lower().startswith("all"):          # "All (L1-L7)" => all seven layers observed
        return [1, 2, 3, 4, 5, 6, 7]
    return sorted(int(x[1:]) for x in name.split("+"))


def _run(args):
    seed, layers = args
    t0 = time.time()
    r = simulate_attack(snr_n=SNR_N, seed=seed, max_bp_iter=MAX_BP_ITER,
                        observe_layers=layers, verbose=False)
    return {
        "seed": seed,
        "bsr": r["l0_bsr"],
        "mi_bp": round(max(0.0, LOG2Q - r["l0_avg_entropy"]), 2),
        "entropy": round(r["l0_avg_entropy"], 2),
        "map_error": r["l0_map_error"],
        "bp_iterations": r["bp_iterations"],
        "time_s": round(time.time() - t0, 1),
    }


def _init():
    warmup_numba()


def build_and_verify_worklist(spec):
    work = []
    for c in spec:
        L = layers_of(c["config"])
        seeds = [s["seed"] for s in c["per_seed"]]
        for k in range(1, len(seeds)):
            assert seeds[k] - seeds[k - 1] == 100_000, (
                f"{c['config']} intra-config stride != 100000 at idx {k}: {seeds[k] - seeds[k - 1]}")
        for s in c["per_seed"]:
            work.append((s["seed"], L))
    return work


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    spec = json.load(open(SPEC_PATH))
    work = build_and_verify_worklist(spec)
    print(f"[emit_tier123] spec OK: {len(spec)} configs, {len(work)} records; "
          f"intra-config 100000 stride verified", flush=True)
    if args.dry:
        print("[emit_tier123] DRY OK (no simulation run)")
        return
    if not args.out:
        ap.error("--out is required unless --dry")

    ctx = multiprocessing.get_context("fork")
    t0 = time.time()
    results = {}
    with ctx.Pool(args.workers, initializer=_init) as pool:
        done = 0
        for res in pool.imap_unordered(_run, work):
            results[res["seed"]] = res
            done += 1
            if done % 20 == 0:
                print(f"  {done}/{len(work)} ({time.time() - t0:.0f}s)", flush=True)

    # Replicate exp_i_ablation.py's config_result aggregate block exactly (same field order).
    out = []
    for c in spec:
        per = [results[s["seed"]] for s in c["per_seed"]]
        bsrs = [p["bsr"] for p in per]
        mis = [p["mi_bp"] for p in per]
        ents = [p["entropy"] for p in per]
        n_fk = sum(1 for b in bsrs if b == 1.0)
        lo, hi = wilson_ci(n_fk, len(per))
        entry = {k: c[k] for k in ("config", "layers", "n_layers",
                                   "consecutive_from_l1", "snr_n", "n_seeds") if k in c}
        entry.update({
            "mean_bsr": round(float(np.mean(bsrs)), 4),
            "std_bsr": round(float(np.std(bsrs)), 4),
            "mean_mi_bp": round(float(np.mean(mis)), 2),
            "std_mi_bp": round(float(np.std(mis)), 2),
            "mean_entropy": round(float(np.mean(ents)), 2),
            "full_key_recovery_rate": round(n_fk / len(per), 4),
            "n_full_key": n_fk,
            "wilson_ci_95": [round(lo, 4), round(hi, 4)],
            "per_seed": per,
        })
        out.append(entry)

    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"[emit_tier123] wrote {args.out}: {len(work)} records, {time.time() - t0:.0f}s wall")


if __name__ == "__main__":
    main()
