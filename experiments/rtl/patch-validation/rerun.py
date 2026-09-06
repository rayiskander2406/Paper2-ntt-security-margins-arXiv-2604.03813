#!/usr/bin/env python3
"""
Exp D corrected re-run: A/B the ORIGINAL stimulus against the CORRECTED stimulus.

Methodology is copied from ~/qanary/scripts/experiment_d/run_tvla.py so the numbers
are comparable to the published ones:
    SNR   = Var(E[HD|class]) / E[Var(HD|class)]   per cycle, averaged per region
    TVLA  = Welch's t per cycle, |t| > 4.5 = leak
    masked_end from the first masking_en_ctrl transition in the first fixed run
Seed schedule is identical: np.random.RandomState(42).randint(0, 2**31, 2*n).

WRITES ONLY under /tmp/rtl-validate/tvla/. run_tvla.py --analyze is NEVER invoked:
it rewrites tvla_results.json + RESULTS.md unconditionally at n_per_set=1000, which
is the destructive default that corrupted Exp D in the first place.

Arm A: +fill=0 +decouple=0  -> byte-identical to the original March binary (verified)
Arm B: +fill=1 +decouple=1  -> corrected share layout + independent data/mask PRNG
"""
import numpy as np, struct, subprocess, sys, os, json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

BIN = "/tmp/rtl-validate/build/tvla_patched/Vntt_wrapper"
ROOT = Path("/tmp/rtl-validate/tvla")
RECORD_FMT = "<HBBBBBBHHHHHHHHHH"
RECORD_SIZE = struct.calcsize(RECORD_FMT)
HEADER_SIZE = 32
IDX_MASK, IDX_ROUNDS = 1, 2
GROUP_NAMES = ["Butterfly", "Mem Write", "Mem Read", "Address", "Control"]
HD_INDICES = [12, 13, 14, 15, 16]     # hd_bf, hd_mw, hd_mr, hd_ad, hd_ct
N = int(sys.argv[1]) if len(sys.argv) > 1 else 1000


def load(path):
    with open(path, "rb") as f:
        hdr = struct.unpack("<8I", f.read(HEADER_SIZE))
        n = hdr[4]
        assert hdr[5] == RECORD_SIZE
        return np.array([struct.unpack(RECORD_FMT, f.read(RECORD_SIZE)) for _ in range(n)],
                        dtype=np.float64)


def one(task):
    seed, mode, out, fill, dec = task
    r = subprocess.run([BIN, f"+seed={seed}", f"+mode={mode}", f"+output={out}",
                        f"+fill={fill}", f"+decouple={dec}"],
                       capture_output=True, cwd=str(ROOT))
    return r.returncode


def run_arm(tag, fill, dec, seeds):
    d = ROOT / tag
    (d / "fixed").mkdir(parents=True, exist_ok=True)
    (d / "random").mkdir(parents=True, exist_ok=True)
    tasks = [(int(seeds[i]), 0, str(d / "fixed" / f"run_{i:04d}.bin"), fill, dec) for i in range(N)]
    tasks += [(int(seeds[N + i]), 1, str(d / "random" / f"run_{i:04d}.bin"), fill, dec) for i in range(N)]
    with ProcessPoolExecutor(max_workers=14) as ex:
        rc = list(ex.map(one, tasks, chunksize=16))
    bad = sum(1 for x in rc if x != 0)
    print(f"  [{tag}] {len(tasks)} runs, {bad} failures")
    return bad


def analyze(tag):
    d = ROOT / tag
    fx = [load(p) for p in sorted((d / "fixed").glob("run_*.bin"))[:N]]
    rd = [load(p) for p in sorted((d / "random").glob("run_*.bin"))[:N]]
    F, R = np.stack(fx), np.stack(rd)
    n_cycles = F.shape[1]
    tr = np.where(np.diff(F[0][:, IDX_MASK]) != 0)[0] + 1
    masked_end = int(tr[0]) if len(tr) else n_cycles

    out = {"n_per_set": N, "n_cycles": n_cycles, "masked_end": masked_end, "groups": {}}
    for g, idx in zip(GROUP_NAMES, HD_INDICES):
        f, r = F[:, :, idx], R[:, :, idx]
        # SNR = Var(class means) / mean(class variances)
        cm = np.stack([f.mean(axis=0), r.mean(axis=0)])
        var_signal = cm.var(axis=0)
        mean_noise = (f.var(axis=0, ddof=1) + r.var(axis=0, ddof=1)) / 2
        snr = np.where(mean_noise > 0, var_signal / mean_noise, 0)
        # Welch t
        denom = np.sqrt(f.var(axis=0, ddof=1) / N + r.var(axis=0, ddof=1) / N)
        denom[denom == 0] = 1e-10
        t = (f.mean(axis=0) - r.mean(axis=0)) / denom
        out["groups"][g] = {
            "snr_masked": float(snr[:masked_end].mean()),
            "snr_unmasked": float(snr[masked_end:].mean()),
            "max_abs_t_masked": float(np.abs(t[:masked_end]).max()),
            "max_abs_t_unmasked": float(np.abs(t[masked_end:]).max()),
        }
    return out


if __name__ == "__main__":
    seeds = np.random.RandomState(42).randint(0, 2**31, size=2 * N)
    print(f"n_per_set={N}  ({4*N} simulations total)")
    for tag, fill, dec in (("armA_original", 0, 0), ("armB_corrected", 1, 1)):
        run_arm(tag, fill, dec, seeds)
    res = {t: analyze(t) for t in ("armA_original", "armB_corrected")}
    (ROOT / "rerun_results.json").write_text(json.dumps(res, indent=2))

    A, B = res["armA_original"], res["armB_corrected"]
    print(f"\nmasked_end: A={A['masked_end']}  B={B['masked_end']}   "
          f"cycles: A={A['n_cycles']} B={B['n_cycles']}")
    print(f"\n{'group':11s} | {'SNR masked':>21s} | {'SNR unmasked':>21s}")
    print(f"{'':11s} | {'orig':>8s} {'corr':>8s} {'x':>4s} | {'orig':>8s} {'corr':>8s} {'x':>4s}")
    print("-" * 62)
    for g in GROUP_NAMES:
        a, b = A["groups"][g], B["groups"][g]
        rm = b["snr_masked"] / a["snr_masked"] if a["snr_masked"] else float("nan")
        ru = b["snr_unmasked"] / a["snr_unmasked"] if a["snr_unmasked"] else float("nan")
        print(f"{g:11s} | {a['snr_masked']:8.4f} {b['snr_masked']:8.4f} {rm:4.1f} | "
              f"{a['snr_unmasked']:8.4f} {b['snr_unmasked']:8.4f} {ru:4.1f}")
    print(f"\n{'group':11s} | {'max|t| masked':>19s} | {'max|t| unmasked':>19s}   (4.5 = leak threshold)")
    for g in GROUP_NAMES:
        a, b = A["groups"][g], B["groups"][g]
        fa = "LEAK" if a["max_abs_t_masked"] > 4.5 else "pass"
        fb = "LEAK" if b["max_abs_t_masked"] > 4.5 else "pass"
        print(f"{g:11s} | {a['max_abs_t_masked']:8.2f}({fa}) {b['max_abs_t_masked']:8.2f}({fb}) | "
              f"{a['max_abs_t_unmasked']:8.2f} {b['max_abs_t_unmasked']:8.2f}")
