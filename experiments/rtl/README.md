# Experiment D — RTL leakage extraction (Verilator TVLA)

Generator for the RTL-derived SNR values used by Exp E/G and quoted in §4.8.4 of arXiv:2604.03813.

## What is here

| file | role |
|---|---|
| `sim_main.cpp` | Verilator C++ testbench. Runs one INTT, samples 5 register groups per cycle, writes a 32-byte-header `HAKL` binary (595 records × 28 bytes: 1×u16 cycle, 6×u8 state, 10×u16 HW/HD). |
| `run_tvla.py` | Batch runner + analysis. Welch's t-test per cycle per group, SNR, second-order (centered product), convergence sweep, figures, `tvla_results.json` + `RESULTS.md`. |
| `build.sh` | Verilator build. |

## What is NOT here, and why

- **Adams Bridge RTL** — third-party (`chipsalliance/adams-bridge`, Apache-2.0). Not vendored. Clone it
  separately.
- **Raw traces** — 20,000 runs × 16,692 B ≈ **334 MB**. Not committed. Regenerable via `--run`.
- **`obj_dir/`** — Verilator build output.

## ⚠️ Known gap — read before relying on any number this produces

**The analysis default silently truncates, and it has already caused one published error.**
`run_tvla.py` `main()` defaults `n_per_set = 1000`, and `analyze()` slices
`sorted(glob("run_*.bin"))[:n_per_set]` — so with 10,000 traces per set on disk it analyses the first
1,000 unless told otherwise. Worse, `analyze()` writes `tvla_results.json` **and** `RESULTS.md`
unconditionally into the output directory.

On 2026-03-03 an N=10,000 analysis was run (`RESULTS.md` dated 11:20:31) reporting the masked butterfly
round at **|t| = 6.53 → LEAK**. A later default-parameter re-run (19:55:16) **overwrote both files** with
the N=1,000 result, **|t| = 3.36 → PASS**, and that is what was published. Independent recomputation from
the raw traces confirms the N=10,000 values exactly (5/5 groups, 8/8 convergence points).

> **Always pass `-n` explicitly, and back up `tvla_results.json` / `RESULTS.md` before `--analyze`.**

A TVLA *pass* is only meaningful at a stated trace count. The masked-round verdict flips between
N=2,000 (3.37, PASS) and N=5,000 (5.35, LEAK).

## Reproducing

```bash
git clone https://github.com/chipsalliance/adams-bridge     # third-party RTL
# supply the patched wrapper (see below), then:
./build.sh
python3 run_tvla.py --run --analyze -n 10000 -j 8           # ALWAYS pass -n explicitly
```

Requires Verilator 5.044 (the version used; other versions are untested), numpy, matplotlib.
Simulation is deterministic: seeds derive from `np.random.RandomState(42)` — fixed set gets
`seeds[0:n]` (mode 0), random set `seeds[n:2n]` (mode 1). Re-running with the same RTL and seeds
reproduces bit-identical traces.

**Paths.** `build.sh` expects the Adams Bridge clone at `external/adams-bridge` under the repository root
and writes to `obj_dir/`. The `patch-validation/` scripts reference `$HOME/qanary/external/adams-bridge` (the
same clone), `$HOME/qanary/evidence/experiments/rtl_leakage` (the archived trace sets, whose digests are in
`evidence/rtl_leakage_acquisition.json`) and `/tmp/rtl-validate`, `/tmp/rtl-indep` (scratch); edit those
constants for your layout.

**Adams Bridge revision.** The corrected-stimulus re-run in `patch-validation/` was made against
`chipsalliance/adams-bridge` commit `c2f863176bcc773c01a9c2f631536cbcd77a68a0` (2026-03-27), whose
`src/ntt_top/rtl/ntt_ctrl.sv` carries the line anchors the manuscript cites (54, 265, 649, 667). The clone
held commit `4f3249c407905e727a3f707011d0b0706bcdc79b` (2025-12-11) from 2026-01-17 to 2026-04-18, the
window of the March 2026 acquisition; `src/ntt_top/` is identical at the two commits.

## Provenance

Copied byte-identical from the working repository where Exp D was originally run. The committed
`evidence/tvla_results.json` is sha256 `1a14ae31f71f5a3b992d30829247c266f6ac4a29c55529e29c0a53d12fc88a58`
and is the **N=1,000** analysis.

## `ntt_wrapper_patched.sv` (added 2026-07-28)

`build.sh` references `$SCRIPT_DIR/ntt_wrapper_patched.sv`. Until 2026-07-28 that file was **not in this
repository** — it lived only in a private working tree — so a fresh clone could not run `build.sh`. It is
now committed here.

Provenance: derived from Adams Bridge `ntt_wrapper.sv` (github.com/chipsalliance/adams-bridge), Apache-2.0,
upstream notice retained. The modification adds registered `mem_rd_data_valid` / `pwm_a_rd_data_valid` /
`pwm_b_rd_data_valid` (1-cycle-delayed read enables) driving otherwise-unconnected `ntt_top` pins, and keeps
the module name `ntt_wrapper` for drop-in replacement. It is a **modified** file, not upstream source, and
has not been validated for functional correctness — it exists to drive the Exp D leakage harness, not to be
a reference implementation.
