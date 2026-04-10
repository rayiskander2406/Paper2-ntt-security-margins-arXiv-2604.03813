#!/usr/bin/env python3
"""Experiment D: RTL Leakage Extraction -- documented constants.

These values were measured via Verilator cycle-accurate RTL simulation
of the Adams Bridge accelerator (https://github.com/chipsalliance/adams-bridge)
with 1,000 fixed and 1,000 random input pairs (595 cycles each, masking
boundary at cycle 345).

To reproduce these measurements, clone Adams Bridge, synthesize with Yosys,
simulate with Verilator using --trace-underscore, and run first-order TVLA.

Reference: arXiv:2604.03813, Section 4.8.4.
"""

# TVLA t-statistics and SNR by register group
RTL_MEASUREMENTS = {
    "butterfly": {"masked_t": 3.36, "unmasked_t": 6.34, "snr": 0.0027},
    "mem_write": {"masked_t": 14.26, "unmasked_t": 13.17, "snr": 0.0155},
    "mem_read":  {"masked_t": 7.09, "unmasked_t": 5.62, "snr": 0.0033},
    "address":   {"masked_t": 1.43, "unmasked_t": 2.63, "snr": 0.0004},
    "control":   {"masked_t": 0.00, "unmasked_t": 0.00, "snr": 0.0000},
}

TVLA_THRESHOLD = 4.5  # |t| > 4.5 indicates statistically significant leakage


def main():
    print("Experiment D: RTL-Measured Leakage Constants")
    print("=" * 60)
    print(f"{'Group':<12} {'Masked |t|':>10} {'Unmasked |t|':>12} {'SNR':>8} {'Leaks?':>8}")
    print("-" * 60)
    for group, vals in RTL_MEASUREMENTS.items():
        leaks = "LEAK" if vals["unmasked_t"] > TVLA_THRESHOLD else "PASS"
        print(f"{group:<12} {vals['masked_t']:>10.2f} {vals['unmasked_t']:>12.2f} "
              f"{vals['snr']:>8.4f} {leaks:>8}")
    print()
    print("Note: These values require Adams Bridge RTL + Verilator to reproduce.")
    print("The SNR values are used as inputs to Experiments E and F.")


if __name__ == "__main__":
    main()
