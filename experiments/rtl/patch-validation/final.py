#!/usr/bin/env python3
"""
Definitive Exp D A/B at full N.

Arm A = the COMMITTED traces (~/qanary/evidence/experiments/rtl_leakage) -- the published data,
        read-only. My analyzer reproduces its published N=1000 numbers exactly (3.36/14.26/7.09/
        1.43/0.00), so the analysis path is validated.
Arm B = corrected stimulus (+fill=1 +decouple=1), generated with the IDENTICAL seed schedule
        (n_per_set=10000 -> fixed seeds[0:10000], random seeds[10000:20000]).

Never invokes run_tvla.py --analyze. Writes only under /tmp/rtl-validate/tvla/.
"""
import numpy as np, subprocess, json, sys, time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

BIN = "/tmp/rtl-validate/build/tvla_patched/Vntt_wrapper"
ROOT = Path("/tmp/rtl-validate/tvla")
COMMITTED = Path.home() / "qanary/evidence/experiments/rtl_leakage"
N = 10000
DT = np.dtype([('cycle','<u2'),('mask','u1'),('rounds','u1'),('rfsm','u1'),('wfsm','u1'),
               ('bfen','u1'),('pad','u1'),('hw_bf','<u2'),('hw_mw','<u2'),('hw_mr','<u2'),
               ('hw_ad','<u2'),('hw_ct','<u2'),('hd_bf','<u2'),('hd_mw','<u2'),('hd_mr','<u2'),
               ('hd_ad','<u2'),('hd_ct','<u2')])
HD = ['hd_bf','hd_mw','hd_mr','hd_ad','hd_ct']
G  = ["Butterfly","Mem Write","Mem Read","Address","Control"]


def load(p):
    return np.frombuffer(open(p,'rb').read(), dtype=DT, offset=32)


def gen(task):
    seed, mode, out = task
    return subprocess.run([BIN, f"+seed={seed}", f"+mode={mode}", f"+output={out}",
                           "+fill=1", "+decouple=1"], capture_output=True, cwd=str(ROOT)).returncode


def build_armB():
    d = ROOT / "armB_full"
    (d/"fixed").mkdir(parents=True, exist_ok=True); (d/"random").mkdir(parents=True, exist_ok=True)
    seeds = np.random.RandomState(42).randint(0, 2**31, size=2*N)   # same schedule as committed
    tasks  = [(int(seeds[i]),      0, str(d/"fixed"/f"run_{i:04d}.bin"))  for i in range(N)]
    tasks += [(int(seeds[N+i]),    1, str(d/"random"/f"run_{i:04d}.bin")) for i in range(N)]
    t0=time.time()
    with ProcessPoolExecutor(max_workers=14) as ex:
        rc = list(ex.map(gen, tasks, chunksize=32))
    print(f"  armB: {len(tasks)} runs, {sum(1 for x in rc if x)} failures, {time.time()-t0:.0f}s")
    return d


def stack(d, n):
    fx = np.stack([np.stack([r[f] for f in HD], -1) for r in
                   (load(p) for p in sorted((d/"fixed").glob("run_*.bin"))[:n])])
    rd = np.stack([np.stack([r[f] for f in HD], -1) for r in
                   (load(p) for p in sorted((d/"random").glob("run_*.bin"))[:n])])
    me = int((np.where(np.diff(load(sorted((d/"fixed").glob("run_*.bin"))[0])['mask'].astype(float))!=0)[0]+1)[0])
    return fx, rd, me


def stats(fx, rd, me, n):
    out={}
    for gi,g in enumerate(G):
        A=fx[:,:,gi].astype(np.float64); B=rd[:,:,gi].astype(np.float64)
        cm=np.stack([A.mean(0),B.mean(0)]); vs=cm.var(0)
        mn=(A.var(0,ddof=1)+B.var(0,ddof=1))/2
        snr=np.where(mn>0, vs/np.where(mn>0,mn,1), 0.0)
        den=np.sqrt(A.var(0,ddof=1)/n+B.var(0,ddof=1)/n); den[den==0]=1e-10
        t=(A.mean(0)-B.mean(0))/den
        out[g]={"snr_masked":float(snr[:me].mean()),"snr_unmasked":float(snr[me:].mean()),
                "max_t_masked":float(np.abs(t[:me]).max()),"max_t_unmasked":float(np.abs(t[me:]).max())}
    return out


if __name__=="__main__":
    print(f"generating Arm B (corrected) at N={N} ...")
    dB = build_armB()
    res={}
    for tag,d in (("A_published", COMMITTED), ("B_corrected", dB)):
        print(f"loading {tag} ...")
        fx,rd,me = stack(d, N)
        res[tag] = {"masked_end":me, "n1000":stats(fx[:1000],rd[:1000],me,1000),
                    "n10000":stats(fx,rd,me,N)}
        del fx,rd
    (ROOT/"final_results.json").write_text(json.dumps(res,indent=2))

    for NN in ("n1000","n10000"):
        lbl = "N=1,000 (the published operating point)" if NN=="n1000" else "N=10,000 (full data on disk)"
        print(f"\n{'='*74}\n{lbl}\n{'='*74}")
        print(f"{'group':11s} | {'masked max|t|  (4.5 = leak)':^30s} | {'masked SNR':^19s}")
        print(f"{'':11s} | {'published':>12s} {'corrected':>15s} | {'pub':>8s} {'corr':>8s}")
        print("-"*74)
        for g in G:
            a=res["A_published"][NN][g]; b=res["B_corrected"][NN][g]
            fa="LEAK" if a["max_t_masked"]>4.5 else "PASS"; fb="LEAK" if b["max_t_masked"]>4.5 else "PASS"
            flip=" <-- FLIPS" if fa!=fb else ""
            print(f"{g:11s} | {a['max_t_masked']:7.2f} [{fa}] {b['max_t_masked']:8.2f} [{fb}] | "
                  f"{a['snr_masked']:8.5f} {b['snr_masked']:8.5f}{flip}")
