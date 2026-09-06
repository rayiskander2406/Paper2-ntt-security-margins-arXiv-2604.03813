# Exp D patched-RTL validation harness

This directory preserves the source that actually produced the results. Build output is *not*
preserved — regenerate it with the steps below.

## What is deliberately NOT here

**The wrapper variants are absent on purpose.** `ntt_wrapper_patched.sv` is a MODIFIED
Apache-2.0 Adams Bridge file (`src/ntt_top/tb/ntt_wrapper.sv`); the copy this harness builds against is
`../ntt_wrapper_patched.sv`.

The five wrapper variants used as controls are **derivatives of that file** and are
absent. They are trivially regenerated — see "Regenerating the variants" below.

`reference_check.py` and `analyze.py` reimplement routines from the Apache-2.0 golden model
`ntt_ref.py`; both carry a provenance header.

## Toolchain

**Verilator 5.044 is required.** 5.048 fails with an internal error
(`V3Delayed.cpp: Unexpected LHS form`) on `ntt_masked_gs_butterfly.sv:182`, where a whole-array and a
per-element assignment to `u_o_reg` share one `always_ff`. 5.044 is also what the original March Exp D
run used (recorded in its `obj_dir/Vntt_wrapper.mk`).

```bash
curl -sL -o v.tgz https://github.com/verilator/verilator/archive/refs/tags/v5.044.tar.gz
tar xzf v.tgz && cd verilator-5.044 && autoconf && ./configure && make -j16
# `make install` fails on verilator_gantt.1 (needs pod2man) — harmless, use the in-tree binary:
export VERILATOR_ROOT=$PWD
```

## Contents

| File | Role |
|---|---|
| `sim_dump.cpp` | Main harness. Adds an output dump after `ntt_done` — the original `sim_main.cpp` records only per-cycle HD/HW, which is why correctness was never checked. Fill modes: `0` = Exp D's exact stimulus, `1` = canonical masked (`share1=0`), `2` = unmasked, `3` = non-degenerate sharing. |
| `sim_indep.cpp` | Independent re-derivation harness (written from scratch). Adds an **intent sidecar** so share bit-placement is verified, not assumed. Modes `1/3/4/5`. |
| `build_variant.sh` | Verilator + C++ build driver, one obj dir per wrapper variant. |
| `run_matrix.sh` | The full experiment matrix. |
| `check.py` | Decode/compare memory dumps; tests arithmetic vs Boolean recombination. |
| `reference_check.py` | Tier 2 comparison against the designers' golden model. |
| `analyze_fill.py` | Static reproduction of Exp D's fill (own MT19937 matching C++ `std::mt19937`) — needs no simulator. |
| `analyze.py` | Independent analysis: placement check → power control → case under test. |

## Regenerating the variants

From `../ntt_wrapper_patched.sv`, each control is a small textual edit:

- **`stock`** — the upstream `src/ntt_top/tb/ntt_wrapper.sv`, unmodified.
- **`delay2`** — add `mem_rd_data_valid_d1`; drive `mem_rd_data_valid <= mem_rd_data_valid_d1` (2-cycle).
- **`tied0` / `tied1`** — replace `mem_rd_data_valid <= ntt_mem_rden;` with `1'b0` / `1'b1`.
- **`datadelay`** (positive control) — register `mem_rd_data` one extra cycle and feed the delayed
  copy to `ntt_top`. This one **must** change the output; if it does not, the harness has no power.

## Key results this reproduces

```bash
./build_variant.sh patched          # also: stock delay2 tied0 tied1 datadelay
./run_matrix.sh
python3 check.py cmp out/d_base.txt out/d_stock.txt patched stock       # IDENTICAL  (patch inert in gs)
python3 check.py cmp out/d_base.txt out/d_datadelay.txt patched mutant  # DIFFER     (apparatus has power)
python3 reference_check.py                                             # EXACT MATCH 256/256
python3 analyze_fill.py                                                # 128/256 zeros, 100% out of range
python3 analyze.py                                                     # mode 1/4 = 256/256; mode 3 = 0 direct
```

Seeds: data `0xDEADBEEF` (Exp D fixed set), masks `42 / 9999 / 777`.

**Two controls are load-bearing and must not be dropped.** The negative control
(re-timing the patch 1→2 cycles) is *powerless here* — it mutates a signal that is inert in gs mode, so
it passes by construction. Power comes from `datadelay` (mutating a live signal) and from ct-mode,
where stock **hangs** at 50,000 cycles while patched completes in 321.

## The corrected Exp D re-run

| File | Role |
|---|---|
| `sim_tvla.cpp` | `sim_main.cpp` with exactly two changes: `+fill=0/1` (original vs corrected share layout) and `+decouple=0/1` (independent data/mask PRNG in the random set). With `+fill=0` it is **byte-identical** to the original March binary. |
| `rerun.py` | A/B driver at arbitrary N; parallel, writes only under its own tree. |
| `final.py` | Definitive run: Arm A = the committed traces read-only, Arm B = corrected stimulus on the identical seed schedule. |
| `final_results.json` | The results below. |

```bash
./build_tvla.sh patched      # build_variant.sh with --exe sim_tvla.cpp
python3 final.py             # ~6.5 min: 20,000 corrected sims + both analyses
```

**Never run `run_tvla.py --analyze`.** It rewrites `tvla_results.json` and `RESULTS.md`
unconditionally at `n_per_set=1000` — the destructive default that corrupted Exp D originally. These
scripts reimplement its statistics (`max|t|` over `[0,masked_end)` vs a 4.5 threshold;
`SNR = Var(E[HD|class])/E[Var(HD|class)]`) and write only to their own tree.

**Three fidelity checks gate the result** — reproduce them before trusting any number:
1. `+fill=0` output is `cmp`-identical to the original binary;
2. the analyzer reproduces the published N=1,000 values 3.36 / 14.26 / 7.09 / 1.43 / 0.00;
3. at N=10,000 it reproduces 6.53 / 15.52 / 43.76 / 18.26.

**Result — masked-round max|t|, 4.5 = leak:**

| Group | N=1k published | N=1k corrected | N=10k published | N=10k corrected |
|---|---|---|---|---|
| Butterfly | **3.36 PASS** | **5.98 LEAK** | 6.53 LEAK | **13.18 LEAK** |
| Mem Write | 14.26 | 9.97 | 43.76 | 29.54 |
| Mem Read | 7.09 | 4.61 | 18.26 | 7.83 |
| Address | 1.43 | 1.43 | 2.09 | 2.09 |
| Control | 0.00 | 0.00 | 0.00 | 0.00 |

`Address` and `Control` are unchanged across arms by construction (data-independent) — if a stimulus
change moves either, the comparison is broken.

**What this does and does not establish.** The *TVLA verdict* moves unidirectionally: Butterfly
PASS → LEAK, all data-carrying groups leak, no group moves LEAK → PASS. The *margins* (trace budget,
2^46→2^9, Table 4/6) are a different quantity derived from the SNRs, which move in **opposite
directions by group** (Butterfly masked +18x, Mem Read -20x) and were **not** propagated here (the propagation is `experiments/exp_margin_propagation.py`).

The seed schedule has a trap worth knowing: `run_batch` uses `seeds[n_per_set + i]` for the random
set, so **the random-set seeds depend on `n_per_set`**. An A/B at N=1,000 does *not* reproduce the
committed random traces (which were generated at n_per_set=10,000); the fixed set does match. Run at
N=10,000 to reproduce both sets bit-exactly.
