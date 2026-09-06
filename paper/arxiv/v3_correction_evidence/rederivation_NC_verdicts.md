# Corrected NC verdicts (v3 re-derivation)

_Backed by 645 completed runs. Every number traces to a cell in rederivation_results.json. mi_bp = max(0, 11.70 − mean L0 entropy)._

## NC1 — claimed: masking L1 => structural barrier, MI=0 for ANY inference, any trace count
**Verdict: REFUTED — cost multiplier, not a barrier.**

The factor graph never disconnects L0 (masking = non-observation). Corrected no-L1 recovery:

- **NC1-A_L2-L7** @50000: corrected FK **50/50=1.0** (Wilson [0.9286, 1.0]), mid-BSR 1.0, MI 11.7, iters 28-32, conv 50/50 | committed FK/MI 0.0/0.0007
- **NC1-B_L2+L4+L6+L7** @50000: corrected FK **50/50=1.0** (Wilson [0.9286, 1.0]), mid-BSR 1.0, MI 11.6999, iters 29-33, conv 50/50 | committed FK/MI 0.0/0.0007
- **NC1-E_L2+L3+L5+L6+L7** @50000: corrected FK **10/10=1.0** (Wilson [0.7225, 1.0]), mid-BSR 1.0, MI 11.7001, iters 28-34, conv 10/10 | committed FK/MI 0.0/0.0009
- **NC1-F_L3+L5+L7** @50000: corrected FK **6/10=0.6** (Wilson [0.3127, 0.8318]), mid-BSR 0.9781, MI 10.832, iters 32-36, conv 10/10 | committed FK/MI 0.0/0.0009
- **NC1-C_K8_L2-L8** @50000: corrected FK **10/10=1.0** (Wilson [0.7225, 1.0]), mid-BSR 1.0, MI 11.6998, iters 28-30, conv 10/10 | committed FK/MI 0.0/0.0009
- **NC1-D_K8_L2+L4+L6+L8** @50000: corrected FK **10/10=1.0** (Wilson [0.7225, 1.0]), mid-BSR 1.0, MI 11.6999, iters 29-35, conv 10/10 | committed FK/MI 0.0/0.0009
- **NC1-A_L2-L7_500K** @500000: corrected FK **10/10=1.0** (Wilson [0.7225, 1.0]), mid-BSR 1.0, MI 11.7005, iters 25-28, conv 10/10 | committed FK/MI 0.0/0.0009
- **NC1-B_L2+L4+L6+L7_500K** @500000: corrected FK **10/10=1.0** (Wilson [0.7225, 1.0]), mid-BSR 1.0, MI 11.7005, iters 26-29, conv 10/10 | committed FK/MI 0.0/0.0009

### NC1 cost-multiplier (15 no-L1 four-layer configs, SNR×N 5000 → 50000)
| config | @5000 (corrected FK / mid-BSR) | @50000 (corrected FK / mid-BSR) |
|---|---|---|
| L2+L3+L4+L5 | 0.0 / 0.8289 | 0.0 / 0.9484 |
| L2+L3+L4+L6 | 0.0 / 0.8719 | 0.4 / 0.9906 |
| L2+L3+L4+L7 | 0.2 / 0.9609 | 1.0 / 1.0 |
| L2+L3+L5+L6 | 0.0 / 0.8781 | 1.0 / 1.0 |
| L2+L3+L5+L7 | 0.2 / 0.975 | 1.0 / 1.0 |
| L2+L3+L6+L7 | 0.0 / 0.9563 | 1.0 / 1.0 |
| L2+L4+L5+L6 | 0.0 / 0.8781 | 1.0 / 1.0 |
| L2+L4+L5+L7 | 0.2 / 0.9688 | 1.0 / 1.0 |
| L2+L4+L6 | 0.0 / 0.8589 | — |
| L2+L4+L6+L7 | 0.4 / 0.9813 | 1.0 / 1.0 |
| L2+L5+L6+L7 | 0.4 / 0.9813 | 1.0 / 1.0 |
| L3+L4+L5+L6 | 0.0 / 0.6344 | 0.0 / 0.9031 |
| L3+L4+L5+L7 | 0.0 / 0.7687 | 0.8 / 0.9938 |
| L3+L4+L6+L7 | 0.0 / 0.7625 | 1.0 / 1.0 |
| L3+L5+L6+L7 | 0.0 / 0.7875 | 1.0 / 1.0 |
| L4 only | 0.0 / 0.0303 | — |
| L4+L5+L6+L7 | 0.0 / 0.3 | 0.0 / 0.7813 |
| L5-L7 | 0.0 / 0.0351 | — |
| L7 only | 0.0 / 0.0005 | — |

## NC3 — claimed: gap ≥ 3 consecutive unobserved layers kills BP recovery (0% for gap configs)
The 3 gap configs OBSERVE L1 (so not the iteration-1 artifact), but committed runs still early-exited via the L0-only check (L1+L5+L6+L7 @6 iters, L1+L2+L6+L7 @7-8) or hit the 30-iter cap unconverged (L1+L2+L3+L7). Corrected + higher-iter re-run:

| gap config | @5000 (corrected FK / mid-BSR / MI) | @50000 (corrected FK / mid-BSR / MI) |
|---|---|---|
| L1+L2+L3+L7 | 0.0 / 0.8828 / 6.9168 | 1.0 / 1.0 / 11.7005 |
| L1+L2+L6+L7 | 0.0 / 0.7982 / 5.8398 | 1.0 / 1.0 / 11.7005 |
| L1+L5+L6+L7 | 0.0 / 0.6862 / 5.6248 | 1.0 / 1.0 / 11.7005 |
## NC2 — output-layer (L7) observation
v2 already classified NC2 as cost-modulating, not isolated (line 854/G19: no dedicated L7-ablation). No new isolation run here; state as unresolved/cost-modulating.

## NC4 — minimum observed-layer count (k ≥ 4)
Emerged from the self-falsification fix ({1,4,7} k=3 satisfied R1-R3 but failed). The ablation cells (L1 only, L4 only, L1+L7, L1+L4+L7 …) speak to this — see the ablation table; recovery tracks total MI, not a hard k threshold.

