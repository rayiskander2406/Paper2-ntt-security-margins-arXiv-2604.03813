"""Phase B: re-run contaminated no-L1 configs under a corrected (run-to-convergence)
criterion (convergence_tol=-1.0 disables the L0-only early-exit; same message-passing
math, zero info added). Maps recovery vs L0's hop-distance to the nearest observed layer
and vs SNR. Tells us what survives once the artifact is removed.
"""
import os, sys, json, time
os.environ.setdefault("NUMBA_NUM_THREADS", "6")
import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))
import ntt_bp.belief_propagation as bp

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nc_corrected_result.json")

# (label, observe_layers, snr_n, seed, committed_fk_rate, hops_L0_to_nearest_obs)
CONFIGS = [
    ("NC1-F_L3+L5+L7 @50k",   [3, 5, 7],       50000, 4700150, "0/10", 3),
    ("L2+L3+L4+L5 @5k",       [2, 3, 4, 5],     5000,   10432, "0/5",  2),
    ("L4+L5+L6+L7 @5k",       [4, 5, 6, 7],     5000,   12654, "0/5",  4),
    ("L4+L5+L6+L7 @50k",      [4, 5, 6, 7],    50000,   12654, "0/5",  4),
]
MAX_ITER = 50


def run(label, observe_layers, snr_n, seed, committed, hops):
    rng = np.random.default_rng(seed)
    q, n, n_layers = bp.MLKEM_Q, bp.MLKEM_N, bp.N_LAYERS
    n_traces = int(snr_n / 1.0)
    secret = rng.integers(0, q, size=n).astype(np.int64)
    inter = bp.compute_full_intt(secret, n, n_layers)
    tv = {li * n + i: int(inter[li][i]) for li in range(n_layers + 1) for i in range(n)}
    factors = bp.build_full_intt_factor_graph(n, n_layers)
    obs_vars = {li * n + i: tv[li * n + i] for li in observe_layers for i in range(n)}
    observations = bp.generate_observations(obs_vars, 1.0, n_traces, rng, q)
    print(f"\n[{label}] seed={seed} obs={observe_layers} snr_n={snr_n} "
          f"hops(L0->nearest obs)={hops} committed={committed}", flush=True)
    t0 = time.time()
    beliefs, n_iter, ent = bp.run_bp((n_layers + 1) * n, factors, observations,
                                     max_iterations=MAX_ITER, damping=0.5, q=q,
                                     verbose=True, convergence_tol=-1.0, n_coeffs=n)
    dt = time.time() - t0
    l0 = sum(1 for i in range(n) if int(np.argmax(beliefs[i])) == tv[i])
    mid = n_layers // 2 + 1
    midc = sum(1 for i in range(n) if int(np.argmax(beliefs[mid * n + i])) == tv[mid * n + i])
    # convergence: last-5-iter entropy change
    conv = (len(ent) >= 5 and abs(ent[-1] - ent[-5]) < 0.02)
    res = dict(label=label, seed=seed, observe_layers=observe_layers, snr_n=snr_n,
               hops=hops, committed_fk_rate=committed, corrected_l0_bsr=round(l0 / n, 4),
               corrected_l0_correct=l0, corrected_mid_bsr=round(midc / n, 4),
               full_key_recovered=(l0 == n), converged=bool(conv), iters_run=int(n_iter),
               time_s=round(dt, 1), ent_start=round(float(ent[0]), 2),
               ent_end=round(float(ent[-1]), 3),
               ent_history=[round(float(e), 2) for e in ent])
    print(f"[{label}] RESULT " + json.dumps({k: v for k, v in res.items() if k != 'ent_history'}), flush=True)
    return res


results = []
for cfg in CONFIGS:
    results.append(run(*cfg))
    with open(OUT, "w") as f:
        json.dump(results, f, indent=2)
print("\nALL DONE", flush=True)
