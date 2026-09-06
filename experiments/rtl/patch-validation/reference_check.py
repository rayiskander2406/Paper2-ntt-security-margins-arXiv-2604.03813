#!/usr/bin/env python3
"""
Tier 2: compare the RTL INTT output against the DESIGNERS' OWN golden model
(adams-bridge/src/ntt_top/tb/ntt_ref.py), on the exact canonical input we loaded.

Input  format (masked read path) : coefficient k of word w at bits [96k+47:96k] (share0), share1=0
Output format (unmasked writeback): coefficient k of word w at bits [24k+23:24k]

Coefficient ordering between memory words and polynomial index is a design convention,
so we test the identity mapping and a small set of standard permutations, and report
exactly which (model, ordering) reproduces the hardware -- or that none does.
"""

# NOTE ON PROVENANCE: the NTT/INTT reference routines below (zeta_generator, gs_bf,
# ct_bf, div2, inv_NTT, inv_NTT2x2, inv_NTT2x2_div2) are reimplementations of the
# Adams Bridge golden model at src/ntt_top/tb/ntt_ref.py, which is Apache-2.0
# (Copyright chipsalliance/adams-bridge). Reproduced here for verification only.
# The underlying transform is specified in FIPS 204 (ML-DSA).

import sys, copy
sys.path.insert(0, '/tmp/rtl-validate')
from check import load

Q = 8380417
N = 256
ROOT = 1753


def bit_reversal(x):
    return int(format(x, '08b')[::-1], 2)


def zeta_generator():
    tmp = {0: 1}
    for i in range(1, N):
        tmp[i] = (tmp[i - 1] * ROOT) % Q
    zetas, zetas_inv = {}, {}
    for i in range(N):
        zetas[i] = tmp[bit_reversal(i)]
        zetas_inv[i] = (-zetas[i]) % Q
    return zetas, zetas_inv


ZETAS, ZETAS_INV = zeta_generator()


def gs_bf(u, v, z):
    t = (u - v) % Q
    u = (u + v) % Q
    v = (t * z) % Q
    return u, v


def div2(x):
    return (x >> 1) + ((Q + 1) // 2) if x & 1 else x >> 1


def gs_bf_div2(u, v, z):
    t = div2((u - v) % Q)
    u = div2((u + v) % Q)
    v = (t * z) % Q
    return u, v


def inv_NTT(poly):
    r = copy.deepcopy(poly)
    k, m = N, 1
    while m < N:
        start = 0
        while start < N:
            k -= 1
            zeta = ZETAS_INV[k]
            for j in range(start, start + m):
                r[j], r[j + m] = gs_bf(r[j], r[j + m], zeta)
            start += 2 * m
        m <<= 1
    f = 8347681
    return [f * x % Q for x in r]


def _inv2x2(poly, bf, final_scale):
    r = copy.deepcopy(poly)
    LOGN = 8
    for l in range(0, LOGN - (LOGN & 1), 2):
        m = 1 << l
        for i in range(0, N, 1 << (l + 2)):
            k10 = ((N - (i >> 1)) >> l) - 1
            k11 = k10 - 1
            k2 = ((N - (i >> 1)) >> (l + 1)) - 1
            z10, z11, z2 = ZETAS_INV[k10], ZETAS_INV[k11], ZETAS_INV[k2]
            for j in range(i, i + m):
                u00, v00 = r[j], r[j + m]
                u01, v01 = r[j + 2 * m], r[j + 3 * m]
                u10, u11 = bf(u00, v00, z10)
                v10, v11 = bf(u01, v01, z11)
                u20, u21 = bf(u10, v10, z2)
                v20, v21 = bf(u11, v11, z2)
                r[j], r[j + m], r[j + 2 * m], r[j + 3 * m] = u20, v20, u21, v21
    if final_scale:
        f = 8347681
        r = [f * x % Q for x in r]
    return r


def inv_NTT2x2(poly):
    return _inv2x2(poly, gs_bf, True)


def inv_NTT2x2_div2(poly):
    return _inv2x2(poly, gs_bf_div2, False)


def decode_input(path, lo=128, hi=192):
    """Masked format: share0 of coeff k at bits [96k+47:96k]."""
    mem = load(path)
    out = []
    for a in range(lo, hi):
        w = mem[a]
        for k in range(4):
            out.append(((w >> (96 * k)) & ((1 << 46) - 1)) % Q)
    return out


def decode_output(path, lo=128, hi=192):
    """Unmasked writeback: coeff k at bits [24k+23:24k]."""
    mem = load(path)
    out = []
    for a in range(lo, hi):
        w = mem[a]
        for k in range(4):
            out.append((w >> (24 * k)) & 0xFFFFFF)
    return out


ORDERINGS = {
    "identity":       lambda i: i,
    "bitrev8":        lambda i: bit_reversal(i),
    # 4 coeffs/word, word-major vs coefficient-major interleave
    "word_interleave": lambda i: (i % 64) * 4 + (i // 64),
    "coeff_stride64":  lambda i: (i % 4) * 64 + (i // 4),
}


def permute(vals, f):
    out = [0] * len(vals)
    for i, v in enumerate(vals):
        out[f(i)] = v
    return out


def main():
    src = decode_input('/tmp/rtl-validate/out/pre_canon.txt')
    hw = decode_output('/tmp/rtl-validate/out/d_canon.txt')

    print(f"input  coeffs: n={len(src)} all<q={all(x < Q for x in src)} first6={src[:6]}")
    print(f"hw out coeffs: n={len(hw)} all<q={all(x < Q for x in hw)} first6={hw[:6]}")
    print(f"hw out values >= q: {sum(1 for x in hw if x >= Q)}")

    models = {
        "inv_NTT (1x1, f-scale)":   inv_NTT,
        "inv_NTT2x2 (f-scale)":     inv_NTT2x2,
        "inv_NTT2x2_div2":          inv_NTT2x2_div2,
    }

    best = None
    for mname, model in models.items():
        for iname, iperm in ORDERINGS.items():
            ref = model(permute(src, iperm))
            for oname, operm in ORDERINGS.items():
                cand = permute(ref, operm)
                nmatch = sum(1 for a, b in zip(cand, hw) if a == b)
                if best is None or nmatch > best[0]:
                    best = (nmatch, mname, iname, oname)
                if nmatch == N:
                    print(f"\n*** EXACT MATCH: {mname} | in-order={iname} | out-order={oname} ***")
                    return 0
    print(f"\nNo exact match. Best: {best[0]}/{N} coeffs "
          f"[{best[1]} | in={best[2]} | out={best[3]}]")
    return 1


if __name__ == "__main__":
    sys.exit(main())
