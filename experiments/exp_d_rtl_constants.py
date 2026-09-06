#!/usr/bin/env python3
"""Experiment D: RTL Leakage Extraction -- documented constants.

These values were measured via Verilator cycle-accurate RTL simulation
of the Adams Bridge accelerator (https://github.com/chipsalliance/adams-bridge)
with 1,000 fixed and 1,000 random input pairs (595 cycles each, masking
boundary at cycle 345).

Reference: arXiv:2604.03813, Section 4.8.4.

-----------------------------------------------------------------------------
2026-07-20 -- v3 CORRECTION NOTICE
-----------------------------------------------------------------------------
RTL_MEASUREMENTS below are the PUBLISHED (arXiv v2) values.  They are retained
verbatim as provenance and as the baseline the v2 chain reproduces.  They are
now known to be measured from a MALFORMED stimulus.  Two independent defects:

  1. STIMULUS.  In the Exp D testbench the mod-q reduction was dead code, and
     the share layout was assumed blocked where the RTL is interleaved -- so
     128 of 256 coefficients were identically zero in both the fixed and the
     random set, and the other 128 carried unreduced 46-bit values far outside
     the datapath's designed input domain.  On this stimulus the RTL matches
     the designers' golden model 0/256.
  2. SAMPLE SIZE.  10,000 traces per set were captured, but the committed
     analysis ran at n_per_set=1,000 (a destructive default in run_tvla.py
     --analyze silently overwrote the larger result).

Neither correction alone finds the other.  Correcting sample size on the
malformed stimulus still measures a datapath running outside its input domain;
correcting the stimulus at N=1,000 still under-samples a 10,000-trace capture.

CONSEQUENCE FOR THE HEADLINE: the published masked-round "Butterfly 3.36 PASS"
does not survive.  It fails at N=10,000 on the original traces (6.53) AND at
N=1,000 once the stimulus is corrected (5.98).  There is no operating point at
which it passes on valid ML-DSA input.

Full-precision values for all four measurement sets, and the executed
propagation through the margin chain, live in:
    experiments/rtl/patch-validation/final_results.json   (source of truth)
    experiments/exp_margin_propagation.py                 (the propagation)
"""

TVLA_THRESHOLD = 4.5  # |t| > 4.5 indicates statistically significant leakage

# PUBLISHED (arXiv v2 §4.8.4). Malformed stimulus, analysed at N=1,000.
# Retained unchanged: this is what the v2 chain reproduces.
RTL_MEASUREMENTS = {
    "butterfly": {"masked_t": 3.36, "unmasked_t": 6.34, "snr": 0.0027},
    "mem_write": {"masked_t": 14.26, "unmasked_t": 13.17, "snr": 0.0155},
    "mem_read":  {"masked_t": 7.09, "unmasked_t": 5.62, "snr": 0.0033},
    "address":   {"masked_t": 1.43, "unmasked_t": 2.63, "snr": 0.0004},
    "control":   {"masked_t": 0.00, "unmasked_t": 0.00, "snr": 0.0000},
}

# CORRECTED stimulus, identical seed schedule, analysed at N=1,000
# (like-for-like replacement for the published operating point).
RTL_MEASUREMENTS_CORRECTED_N1000 = {
    "butterfly": {"masked_t": 5.98, "unmasked_t": 3.79, "snr": 0.00095875},
    "mem_write": {"masked_t": 9.97, "unmasked_t": 12.02, "snr": 0.01609241},
    "mem_read":  {"masked_t": 4.61, "unmasked_t": 5.32, "snr": 0.00141052},
    "address":   {"masked_t": 1.43, "unmasked_t": 2.63, "snr": 0.00041457},
    "control":   {"masked_t": 0.00, "unmasked_t": 0.00, "snr": 0.0000},
}

# CORRECTED stimulus at N=10,000 -- the honest sample size.
RTL_MEASUREMENTS_CORRECTED_N10000 = {
    "butterfly": {"masked_t": 13.18, "unmasked_t": 7.75, "snr": 0.00051789},
    "mem_write": {"masked_t": 29.54, "unmasked_t": 33.94, "snr": 0.01529136},
    "mem_read":  {"masked_t": 7.83, "unmasked_t": 12.24, "snr": 0.00099826},
    "address":   {"masked_t": 2.09, "unmasked_t": 3.28, "snr": 0.00003704},
    "control":   {"masked_t": 0.00, "unmasked_t": 0.00, "snr": 0.0000},
}

# PUBLISHED stimulus re-analysed at N=10,000 -- isolates the sample-size defect
# from the stimulus defect.
RTL_MEASUREMENTS_PUBLISHED_N10000 = {
    "butterfly": {"masked_t": 6.53, "unmasked_t": 15.52, "snr": 0.00233075},
    "mem_write": {"masked_t": 43.76, "unmasked_t": 37.39, "snr": 0.01526250},
    "mem_read":  {"masked_t": 18.26, "unmasked_t": 15.68, "snr": 0.00303532},
    "address":   {"masked_t": 2.09, "unmasked_t": 3.28, "snr": 0.00003704},
    "control":   {"masked_t": 0.00, "unmasked_t": 0.00, "snr": 0.0000},
}

ALL_SETS = {
    "published  N=1,000  (arXiv v2)": RTL_MEASUREMENTS,
    "corrected  N=1,000": RTL_MEASUREMENTS_CORRECTED_N1000,
    "published  N=10,000": RTL_MEASUREMENTS_PUBLISHED_N10000,
    "corrected  N=10,000": RTL_MEASUREMENTS_CORRECTED_N10000,
}


def _verdict(t):
    return "LEAK" if t > TVLA_THRESHOLD else "pass"


def _table(measurements):
    print(f"{'Group':<12} {'Masked |t|':>10} {'Masked':>7} "
          f"{'Unmasked |t|':>12} {'Unmasked':>9} {'SNR':>10}")
    print("-" * 66)
    for group, vals in measurements.items():
        print(f"{group:<12} {vals['masked_t']:>10.2f} {_verdict(vals['masked_t']):>7} "
              f"{vals['unmasked_t']:>12.2f} {_verdict(vals['unmasked_t']):>9} "
              f"{vals['snr']:>10.5f}")


def main():
    print("Experiment D: RTL-Measured Leakage Constants")
    print("=" * 66)
    print("PUBLISHED (arXiv v2 Section 4.8.4) -- malformed stimulus, N=1,000")
    print("=" * 66)
    _table(RTL_MEASUREMENTS)

    print()
    print("=" * 66)
    print("v3 CORRECTION -- all four measurement sets")
    print("=" * 66)
    for label, meas in ALL_SETS.items():
        print(f"\n--- {label} ---")
        _table(meas)

    print()
    print("=" * 66)
    print("HEADLINE: masked-round Butterfly first-order TVLA")
    print("=" * 66)
    for label, meas in ALL_SETS.items():
        t = meas["butterfly"]["masked_t"]
        print(f"  {label:<32} |t| = {t:>6.2f}  -> {_verdict(t)}")
    print()
    print("  The published 3.36 PASS is the ONLY cell in this column that passes,")
    print("  and it is the one produced by both defects acting together.")
    print()
    print("Note: Address and Control are data-independent and are therefore")
    print("identical between the published and corrected arms by construction.")
    print("The SNR values are used as inputs to Experiments E and F.")
    print("Propagation through the margin chain: experiments/exp_margin_propagation.py")


if __name__ == "__main__":
    main()
