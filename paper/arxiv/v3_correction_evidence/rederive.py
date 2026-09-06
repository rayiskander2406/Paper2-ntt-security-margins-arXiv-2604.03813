#!/usr/bin/env python3
"""v3 re-derivation harness — deterministic re-run of the NC1 / layer-ablation / NC3
configurations under the CORRECTED all-variable BP convergence criterion.

Context: src/ntt_bp/belief_propagation.py previously computed its convergence delta
over only the first 50 (Layer-0) variables, so any observation set >=2 butterfly-hops
from L0 early-exited at 1 iteration recording MI=0 / 0% recovery (the fabricated "NC1
input-layer barrier"). That check is now fixed to converge over ALL variables. This
harness re-runs every contaminated configuration to true convergence and records
corrected recovery.

Determinism: single-threaded numba (all six thread env vars pinned to 1 BELOW, before
numpy/numba import). Parallelism is ACROSS runs (multiprocessing.Pool), never within.
Every run is therefore run-to-run bit-deterministic.

The 7-layer arms reproduce ntt_bp.simulate_attack exactly (same RNG order: secret via
rng.integers, then observations via generate_observations). The K=8 arms reproduce the
toy-q 8-layer harness: q=3329, its
own zeta table (zeta256=3061, increasing stride 1,2,..,128), routed through the SAME
(now corrected) run_bp. Only the convergence criterion changed vs the committed runs.

Subcommands:
  probe   — quick timing/behaviour calibration (Control A, few iters, threads=1)
  gate    — verification gate: Control A (256/256), Control B (clean unharmed), determinism
  run     — run a single (config,layers,snr_n,seed,k_total) job, print JSON
  sweep   — run a job manifest JSON with a Pool, append results incrementally to JSONL
"""
import os
# --- DETERMINISM: pin single-threaded numba BEFORE numpy/numba import ---
for _v in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
           "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"

import sys
import json
import time
import math
import argparse
import multiprocessing
from pathlib import Path

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))
import ntt_bp.belief_propagation as bp  # noqa: E402  (corrected package)
from ntt_bp.factor_graph import ButterflyFactor  # noqa: E402

Q = bp.MLKEM_Q          # 3329
N = bp.MLKEM_N          # 256
LOG2Q = math.log2(Q)    # 11.700873...
EVID = os.path.join(REPO, "evidence")

# ---------------------------------------------------------------------------
# Toy-Q K=8 machinery
# (q=3329, 8-layer radix-2 DFT, zeta256=3061, increasing stride). Reproduced here so
# NC1-C/D run on the corrected src/ntt_bp.run_bp.
# ---------------------------------------------------------------------------
TOYQ_ZETA256 = 3061
TOYQ_K = 8


def _bitrev(x: int, bits: int) -> int:
    r = 0
    for _ in range(bits):
        r = (r << 1) | (x & 1)
        x >>= 1
    return r


def build_toyq_k8_factor_graph():
    q, n = Q, N
    zetas = [pow(TOYQ_ZETA256, _bitrev(i, 8), q) for i in range(n)]
    zinv = [pow(z, q - 2, q) for z in zetas]
    factors = []
    k = n - 1
    bf = 1
    for layer in range(TOYQ_K):
        for start in range(0, n, 2 * bf):
            z, zi = zetas[k], zinv[k]
            k -= 1
            for j in range(start, start + bf):
                factors.append(ButterflyFactor(
                    u_in=layer * n + j, v_in=layer * n + j + bf,
                    u_out=(layer + 1) * n + j, v_out=(layer + 1) * n + j + bf,
                    zeta=z, zeta_inv=zi))
        bf *= 2
    return factors


def compute_toyq_k8_intt(secret_ntt):
    q, n = Q, N
    zetas = [pow(TOYQ_ZETA256, _bitrev(i, 8), q) for i in range(n)]
    a = secret_ntt.copy().astype(np.int64)
    inter = [a.copy()]
    k = n - 1
    bf = 1
    for _layer in range(TOYQ_K):
        na = a.copy()
        for start in range(0, n, 2 * bf):
            z = zetas[k]
            k -= 1
            for j in range(start, start + bf):
                u, v = a[j], a[j + bf]
                na[j] = (u + v) % q
                na[j + bf] = (z * ((v - u) % q)) % q
        a = na
        inter.append(a.copy())
        bf *= 2
    return inter


# ---------------------------------------------------------------------------
# Unified single run — corrected convergence criterion (tol over ALL variables)
# ---------------------------------------------------------------------------
def run_one(config, layers, snr_n, seed, k_total=7, max_iter=150,
            tol=1e-4, damping=0.5, keep_history=True):
    rng = np.random.default_rng(seed)
    q, n = Q, N
    if int(k_total) == 8:
        n_layers = TOYQ_K
        secret = rng.integers(0, q, size=n).astype(np.int64)
        inter = compute_toyq_k8_intt(secret)
        factors = build_toyq_k8_factor_graph()
    else:
        n_layers = bp.N_LAYERS
        secret = rng.integers(0, q, size=n).astype(np.int64)
        inter = bp.compute_full_intt(secret, n, n_layers)
        factors = bp.build_full_intt_factor_graph(n, n_layers)

    tv = {li * n + i: int(inter[li][i])
          for li in range(n_layers + 1) for i in range(n)}
    obs_vars = {li * n + i: tv[li * n + i] for li in layers for i in range(n)}
    observations = bp.generate_observations(obs_vars, 1.0, int(snr_n), rng, q)

    n_vars = (n_layers + 1) * n
    t0 = time.time()
    beliefs, n_iter, ent = bp.run_bp(
        n_vars, factors, observations, max_iterations=int(max_iter),
        damping=damping, q=q, verbose=False, convergence_tol=tol, n_coeffs=n)
    dt = time.time() - t0

    l0_correct = sum(1 for i in range(n) if int(np.argmax(beliefs[i])) == tv[i])
    l0_ents = []
    for i in range(n):
        b = beliefs[i]
        p = np.maximum(b, 1e-30)
        l0_ents.append(-float(np.sum(b * np.log2(p))))
    l0_avg_ent = float(np.mean(l0_ents))
    mid = n_layers // 2 + 1
    mid_correct = sum(1 for i in range(n)
                      if int(np.argmax(beliefs[mid * n + i])) == tv[mid * n + i])
    # mi_bp defined exactly as the committed pipeline: max(0, log2(q) - mean L0 entropy)
    mi_bp = max(0.0, LOG2Q - l0_avg_ent)

    res = dict(
        config=config, layers=list(layers), snr_n=snr_n, seed=seed,
        k_total=int(k_total), max_iter=int(max_iter), convergence_tol=tol,
        bp_iterations=int(n_iter), converged=bool(n_iter < int(max_iter)),
        l0_correct=int(l0_correct), l0_bsr=round(l0_correct / n, 4),
        mid_layer_bsr=round(mid_correct / n, 4),
        final_l0_entropy=round(l0_avg_ent, 4), mi_bp=round(mi_bp, 4),
        full_key=bool(l0_correct == n), time_s=round(dt, 1))
    if keep_history:
        res["entropy_history"] = [round(float(e), 3) for e in ent]
    return res


# ---------------------------------------------------------------------------
# Pool worker + incremental sweep
# ---------------------------------------------------------------------------
def _init_worker():
    for _v in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
               "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[_v] = "1"
    bp.warmup_numba()


_RUN_ONE_KEYS = ("config", "layers", "snr_n", "seed", "k_total", "max_iter",
                 "tol", "damping", "keep_history")


def _run_job(job):
    res = run_one(**{k: v for k, v in job.items() if k in _RUN_ONE_KEYS})
    res["group"] = job.get("group")   # carry the group tag through for aggregation
    return res


def job_key(j):
    return f"{j['config']}|{j['seed']}|{j['snr_n']}|{j.get('k_total', 7)}"


def sweep(manifest_path, out_jsonl, workers):
    jobs = json.load(open(manifest_path))
    done = set()
    if os.path.exists(out_jsonl):
        with open(out_jsonl) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        done.add(job_key(json.loads(line)))
                    except Exception:
                        pass
    pending = [j for j in jobs if job_key(j) not in done]
    print(f"[sweep] {len(jobs)} jobs, {len(done)} done, {len(pending)} pending, "
          f"{workers} workers", flush=True)
    if not pending:
        print("[sweep] nothing to do", flush=True)
        return
    bp.warmup_numba()
    ctx = multiprocessing.get_context("fork")
    t0 = time.time()
    n = 0
    with ctx.Pool(workers, initializer=_init_worker) as pool, open(out_jsonl, "a") as fout:
        for res in pool.imap_unordered(_run_job, pending):
            n += 1
            fout.write(json.dumps(res) + "\n")
            fout.flush()
            os.fsync(fout.fileno())
            el = time.time() - t0
            eta = el / n * (len(pending) - n)
            print(f"  [{n}/{len(pending)}] {res['config']} seed={res['seed']} "
                  f"snr={res['snr_n']} -> bsr={res['l0_bsr']} mid={res['mid_layer_bsr']} "
                  f"mi={res['mi_bp']} iters={res['bp_iterations']} conv={res['converged']} "
                  f"{res['time_s']}s (ETA {eta/60:.0f}m)", flush=True)
    print(f"[sweep] done {n} runs in {(time.time()-t0)/60:.1f}m", flush=True)


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("probe")
    p.add_argument("--iters", type=int, default=4)

    sub.add_parser("gate")

    r = sub.add_parser("run")
    r.add_argument("--config", required=True)
    r.add_argument("--layers", required=True, help="comma list e.g. 2,3,4,5,6,7")
    r.add_argument("--snr_n", type=float, required=True)
    r.add_argument("--seed", type=int, required=True)
    r.add_argument("--k_total", type=int, default=7)
    r.add_argument("--max_iter", type=int, default=150)

    s = sub.add_parser("sweep")
    s.add_argument("--manifest", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--workers", type=int, default=14)

    args = ap.parse_args()

    if args.cmd == "probe":
        bp.warmup_numba()
        t0 = time.time()
        res = run_one("PROBE_NC1-A_L2-L7", [2, 3, 4, 5, 6, 7], 50000, 3003270,
                      k_total=7, max_iter=args.iters, tol=-1.0)
        res["wall_s"] = round(time.time() - t0, 1)
        res["s_per_iter"] = round(res["time_s"] / max(1, res["bp_iterations"]), 1)
        print(json.dumps(res, indent=2))

    elif args.cmd == "run":
        layers = [int(x) for x in args.layers.split(",")]
        bp.warmup_numba()
        print(json.dumps(run_one(args.config, layers, args.snr_n, args.seed,
                                 k_total=args.k_total, max_iter=args.max_iter)))

    elif args.cmd == "gate":
        bp.warmup_numba()
        print("=== Control A: NC1-A_L2-L7 seed 3003270 (must recover 256/256) ===", flush=True)
        a1 = run_one("NC1-A_L2-L7", [2, 3, 4, 5, 6, 7], 50000, 3003270,
                     k_total=7, max_iter=150)
        print(json.dumps({k: v for k, v in a1.items() if k != "entropy_history"}), flush=True)
        print("=== Control A (repeat, determinism) ===", flush=True)
        a2 = run_one("NC1-A_L2-L7", [2, 3, 4, 5, 6, 7], 50000, 3003270,
                     k_total=7, max_iter=150)
        print(json.dumps({k: v for k, v in a2.items() if k != "entropy_history"}), flush=True)
        print("=== Control B: clean L1+L3+L5+L7 seed 44595 (must stay ~1.0) ===", flush=True)
        b1 = run_one("L1+L3+L5+L7", [1, 3, 5, 7], 5000, 44595, k_total=7, max_iter=150)
        print(json.dumps({k: v for k, v in b1.items() if k != "entropy_history"}), flush=True)

        ident = (a1["l0_correct"] == a2["l0_correct"]
                 and a1["bp_iterations"] == a2["bp_iterations"]
                 and a1["final_l0_entropy"] == a2["final_l0_entropy"]
                 and a1.get("entropy_history") == a2.get("entropy_history"))
        verdict = {
            "control_A_l0_bsr": a1["l0_bsr"], "control_A_256of256": a1["l0_correct"] == 256,
            "control_A_iters": a1["bp_iterations"], "control_A_converged": a1["converged"],
            "control_B_l0_bsr": b1["l0_bsr"], "control_B_unharmed": b1["l0_bsr"] >= 0.99,
            "control_B_iters": b1["bp_iterations"],
            "determinism_identical": bool(ident),
            "GATE_PASS": bool(a1["l0_correct"] == 256 and b1["l0_bsr"] >= 0.99 and ident),
        }
        print("=== GATE VERDICT ===", flush=True)
        print(json.dumps(verdict, indent=2), flush=True)

    elif args.cmd == "sweep":
        sweep(args.manifest, args.out, args.workers)


if __name__ == "__main__":
    main()
