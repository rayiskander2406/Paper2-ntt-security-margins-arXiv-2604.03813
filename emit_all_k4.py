#!/usr/bin/env python3
"""Regenerate the per-seed SCIENCE of evidence/all_k4_configs.json from the committed BP primitive.

Experiment: the exhaustive 4-layer ablation — all C(7,4)=35 four-layer observation
subsets of {L1..L7} at SNR*N=5000, max_bp_iter=30 (Section 4.4, "35 four-layer subsets").

What this script regenerates vs. carries:
  * REGENERATED (from ntt_bp.simulate_attack): every per_seed simulation output
    (bsr, mi_bp, entropy, bp_iterations) + the per-config aggregates derived from them.
  * CARRIED (from the committed experiment SPEC): the config list, per-config seed
    count n_seeds, and the topology design labels (max_gap, nc1..nc4, predicted).
    These are the experiment design, not simulation outputs.

Seed formula (VERIFIED against all 635 committed seeds, see the assertion below):
    for sorted layers [w<x<y<z]:
        seed = idx*100000 + SNR_N + (w + 10*x + 100*y + 1000*z)

Reproducibility claim: given the committed spec + committed primitive on the pinned
numeric stack (numba 0.64.0 / numpy 2.4.0 / macOS Accelerate), the per-seed SCIENCE
regenerates deterministically. `time_s` is machine-dependent and is NOT part of the
claim (so the regenerated file is science-identical, not byte-identical, to the blob).

Usage:
    python3 emit_all_k4.py --out /tmp/regen_all_k4.json [--workers N]
    python3 emit_all_k4.py --dry            # spec + seed-formula validation only, no simulation
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
           "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ.setdefault(_v, "1")          # pin per-worker threads (Accelerate = VECLIB); set before numpy import
import sys, json, time, math, argparse, itertools, multiprocessing
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "src"))
from ntt_bp import simulate_attack, MLKEM_Q, warmup_numba

LOG2Q = math.log2(MLKEM_Q)
SNR_N, MAX_BP_ITER = 5000, 30
SPEC_PATH = REPO / "evidence" / "all_k4_configs.json"


def layers_of(name):
    return sorted(int(x[1:]) for x in name.split("+"))


def seed_for(layers, idx):
    L = sorted(layers)
    return idx * 100_000 + SNR_N + sum(L[i] * 10 ** i for i in range(len(L)))


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
        "bp_iterations": r["bp_iterations"],
        "time_s": round(time.time() - t0, 1),
    }


def _init():
    warmup_numba()


def build_and_verify_worklist(spec):
    """Return work items; assert config order and that the seed formula reproduces every committed seed."""
    expected = [list(c) for c in itertools.combinations(range(1, 8), 4)]
    got = [layers_of(c["config_name"]) for c in spec]
    assert got == expected, f"config order != C(7,4) lex order: {got[:3]} vs {expected[:3]}"
    work = []
    for c in spec:
        L = layers_of(c["config_name"])
        for idx, s in enumerate(c["per_seed"]):
            derived = seed_for(L, idx)
            assert derived == s["seed"], (
                f"SEED FORMULA MISMATCH {c['config_name']} idx{idx}: derived {derived} != committed {s['seed']}")
            work.append((s["seed"], L))
    return work


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--dry", action="store_true", help="validate spec + seed formula only; no simulation")
    args = ap.parse_args()

    spec = json.load(open(SPEC_PATH))
    work = build_and_verify_worklist(spec)
    print(f"[emit_all_k4] spec OK: {len(spec)} configs, {len(work)} records; "
          f"seed formula verified against ALL committed seeds", flush=True)
    if args.dry:
        print("[emit_all_k4] DRY OK (no simulation run)")
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
            if done % 25 == 0:
                print(f"  {done}/{len(work)} ({time.time() - t0:.0f}s)", flush=True)

    out = []
    for c in spec:
        L = layers_of(c["config_name"])
        per = [results[seed_for(L, idx)] for idx in range(len(c["per_seed"]))]
        bsrs = [p["bsr"] for p in per]
        mis = [p["mi_bp"] for p in per]
        n_fk = sum(1 for b in bsrs if b == 1.0)
        entry = {k: c[k] for k in ("config_name", "n_layers", "max_gap",
                                   "nc1", "nc2", "nc3", "nc4", "predicted",
                                   "snr_n", "n_seeds") if k in c}
        entry.update({
            "mean_bsr": round(float(np.mean(bsrs)), 4),
            "full_key_rate": round(n_fk / len(bsrs), 4),
            "n_full_key": n_fk,
            "mean_mi": round(float(np.mean(mis)), 2),
            "per_seed": per,
        })
        out.append(entry)

    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"[emit_all_k4] wrote {args.out}: {len(work)} records, {time.time() - t0:.0f}s wall")


if __name__ == "__main__":
    main()
