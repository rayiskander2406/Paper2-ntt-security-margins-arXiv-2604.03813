"""Independent reproduction: is the NC1 'input-layer barrier' a convergence artifact?

Control  = committed NC1-A pipeline (convergence_tol=1e-4 default). Must match the
           committed artifact: bp_iterations=1, l0_bsr~0, L0 entropy ~11.70.
Forced   = identical instance (same seed/config/snr), early-exit disabled
           (convergence_tol=-1.0). Watch L0 entropy trajectory + final L0 recovery.

Decision signals (thread-count-robust):
  * L0 entropy_history: if it falls 11.70 -> low, L0 is REACHABLE -> 'degree-zero
    disconnection / MI=0 for any inference' is FALSE.
  * l0_bsr vs random baseline 1/3329~=0.0003 (per-coeff) / bsr over 256 coeffs:
    >> baseline => genuine recovery => NC1 inverts. ~0.5 with high MI => confident-wrong.
No repo files are edited; this only imports the package.
"""
import os, sys, json, time
os.environ.setdefault("NUMBA_NUM_THREADS", "6")
import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "src"))
import ntt_bp.belief_propagation as bp

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nc1_repro_result.json")


def run_config(seed, observe_layers, snr_n, tol, max_iter, label):
    rng = np.random.default_rng(seed)
    q = bp.MLKEM_Q
    n = bp.MLKEM_N
    n_layers = bp.N_LAYERS
    snr = 1.0
    n_traces = int(snr_n / snr)
    secret_ntt = rng.integers(0, q, size=n).astype(np.int64)
    intermediates = bp.compute_full_intt(secret_ntt, n, n_layers)
    true_values = {}
    for li in range(n_layers + 1):
        for i in range(n):
            true_values[li * n + i] = int(intermediates[li][i])
    factors = bp.build_full_intt_factor_graph(n, n_layers)
    observed_vars = {}
    for li in observe_layers:
        for i in range(n):
            observed_vars[li * n + i] = true_values[li * n + i]
    observations = bp.generate_observations(observed_vars, snr, n_traces, rng, q)
    n_vars = (n_layers + 1) * n
    print(f"[{label}] starting: seed={seed} observe={observe_layers} snr_n={snr_n} "
          f"tol={tol} max_iter={max_iter}", flush=True)
    t0 = time.time()
    beliefs, n_iter, ent_hist = bp.run_bp(
        n_vars, factors, observations,
        max_iterations=max_iter, damping=0.5, q=q,
        verbose=True, convergence_tol=tol, n_coeffs=n,
    )
    dt = time.time() - t0
    l0_correct = sum(1 for i in range(n) if int(np.argmax(beliefs[i])) == true_values[i])
    mid = n_layers // 2 + 1
    mid_correct = sum(
        1 for i in range(n)
        if int(np.argmax(beliefs[mid * n + i])) == true_values[mid * n + i]
    )
    res = dict(
        label=label, seed=seed, observe_layers=observe_layers, snr_n=snr_n,
        convergence_tol=tol, max_iter=max_iter, bp_iterations=int(n_iter),
        time_s=round(dt, 1), l0_correct=int(l0_correct), l0_bsr=round(l0_correct / n, 4),
        mid_layer_bsr=round(mid_correct / n, 4),
        entropy_history=[round(float(e), 3) for e in ent_hist],
    )
    print(f"[{label}] RESULT " + json.dumps(res), flush=True)
    return res


results = []
# Control: reproduce committed NC1-A_L2-L7 seed 3003270 (expect 1 iter, bsr~0, ent 11.70)
results.append(run_config(3003270, [2, 3, 4, 5, 6, 7], 50000, 1e-4, 50, "control_default_tol"))
with open(OUT, "w") as f:
    json.dump(results, f, indent=2)
# Forced: identical instance, early-exit disabled
results.append(run_config(3003270, [2, 3, 4, 5, 6, 7], 50000, -1.0, 30, "forced_no_earlyexit"))
with open(OUT, "w") as f:
    json.dump(results, f, indent=2)
print("DONE", flush=True)
