#!/usr/bin/env python3
"""
Independent re-derivation of the non-degenerate-masked-input finding.

Order matters. Before any claim about the DESIGN, we must rule out that the
anomaly is an artifact of OUR OWN construction (cf. convergence-criterion-artifact):

  STEP 1  placement check : does memory decode back to exactly what the TB intended?
  STEP 2  power control   : does mode=1 (share1=0) give 256/256 vs the golden model?
                            If not, the apparatus is broken and nothing else means anything.
  STEP 3  case under test : mode=3, recover the design's effective input via fwd_NTT
                            and characterise every mismatch.
"""

# NOTE ON PROVENANCE: the NTT/INTT reference routines below (zeta_generator, gs_bf,
# ct_bf, div2, inv_NTT, inv_NTT2x2, inv_NTT2x2_div2) are reimplementations of the
# Adams Bridge golden model at src/ntt_top/tb/ntt_ref.py, which is Apache-2.0
# (Copyright chipsalliance/adams-bridge). Reproduced here for verification only.
# The underlying transform is specified in FIPS 204 (ML-DSA).

import sys, copy

Q = 8380417
N = 256
ROOT = 1753


def bitrev8(x):
    return int(format(x, '08b')[::-1], 2)


def zetas():
    tmp = {0: 1}
    for i in range(1, N):
        tmp[i] = (tmp[i - 1] * ROOT) % Q
    z = {i: tmp[bitrev8(i)] for i in range(N)}
    zi = {i: (-z[i]) % Q for i in range(N)}
    return z, zi


Z, ZI = zetas()


def gs_bf(u, v, zz):
    t = (u - v) % Q
    return (u + v) % Q, (t * zz) % Q


def ct_bf(u, v, zz):
    t = (v * zz) % Q
    return (u + t) % Q, (u - t) % Q


def inv_NTT(poly):
    r = copy.deepcopy(poly)
    k, m = N, 1
    while m < N:
        s = 0
        while s < N:
            k -= 1
            zz = ZI[k]
            for j in range(s, s + m):
                r[j], r[j + m] = gs_bf(r[j], r[j + m], zz)
            s += 2 * m
        m <<= 1
    f = 8347681
    return [f * x % Q for x in r]


def fwd_NTT(poly):
    r = copy.deepcopy(poly)
    k, m = 0, 128
    while m > 0:
        s = 0
        while s < N:
            k += 1
            zz = Z[k]
            for j in range(s, s + m):
                r[j], r[j + m] = ct_bf(r[j], r[j + m], zz)
            s += 2 * m
        m >>= 1
    return r


def load(path):
    mem = {}
    for line in open(path):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        a, rest = line.split(':', 1)
        val = 0
        for w in [int(x, 16) for x in rest.split()]:   # MSW first
            val = (val << 32) | w
        mem[int(a)] = val
    return mem


def read_intended(path):
    out = []
    for line in open(path):
        i, c, s0, s1 = line.split()
        out.append((int(c), int(s0), int(s1)))
    return out


def decode_shares(mem, lo=128, hi=192):
    out = []
    for a in range(lo, hi):
        w = mem[a]
        for k in range(4):
            out.append(((w >> (96 * k)) & ((1 << 46) - 1),
                        (w >> (96 * k + 48)) & ((1 << 46) - 1)))
    return out


def decode_out(mem, lo=128, hi=192):
    out = []
    for a in range(lo, hi):
        w = mem[a]
        for k in range(4):
            out.append((w >> (24 * k)) & 0xFFFFFF)
    return out


def run(mode, ds):
    tag = f"m{mode}_{ds}"
    intended = read_intended(f'/tmp/rtl-indep/out/int_{tag}.txt')
    pre = decode_shares(load(f'/tmp/rtl-indep/out/pre_{tag}.txt'))
    hw = decode_out(load(f'/tmp/rtl-indep/out/post_{tag}.txt'))

    # STEP 1 -- placement
    place_ok = sum(1 for (c, s0, s1), (d0, d1) in zip(intended, pre) if s0 == d0 and s1 == d1)
    cons_ok = sum(1 for c, s0, s1 in intended if (s0 + s1) % Q == c)

    # STEP 2/3 -- what did the design compute?
    coeffs = [c for c, _, _ in intended]
    direct = sum(1 for a, b in zip(hw, inv_NTT(coeffs)) if a == b)
    recovered = fwd_NTT(hw)                    # the design's effective input
    rec_ok = sum(1 for c, r in zip(coeffs, recovered) if c == r)

    print(f"\n===== mode={mode}  dataseed={ds} =====")
    print(f"  STEP 1 placement  : memory decodes to intended shares {place_ok}/256"
          f"   {'OK' if place_ok == 256 else '<-- CONSTRUCTION BUG'}")
    print(f"         construction: (s0+s1) mod q == coeff          {cons_ok}/256")
    print(f"  STEP 2/3 INTT out vs golden model(coeff)             {direct}/256")
    print(f"         recovered input == intended coeff            {rec_ok}/256")

    if rec_ok != 256:
        deltas = [(c - r) % Q for c, r in zip(coeffs, recovered) if c != r]
        uniq = sorted(set(deltas))
        print(f"  offsets: {len(deltas)} mismatches, {len(uniq)} distinct delta(s)")
        for d in uniq[:6]:
            print(f"     delta={d}  (= 2^23 mod q = {(1 << 23) % Q}? {d == (1 << 23) % Q})"
                  f"  count={deltas.count(d)}")
        # correlate with share-sum magnitude
        print("  correlation of mismatch with unreduced share sum:")
        for name, pred in (("sum >= q", lambda s0, s1: s0 + s1 >= Q),
                           ("sum >= 2^23", lambda s0, s1: s0 + s1 >= (1 << 23)),
                           ("s0+s1 wraps 2^23 after mod q", lambda s0, s1: ((s0 + s1) % Q) >= (1 << 23) - Q)):
            tp = fp = fn = tn = 0
            for (c, s0, s1), r in zip(intended, recovered):
                bad = (c != r)
                p = pred(s0, s1)
                if p and bad: tp += 1
                elif p and not bad: fp += 1
                elif not p and bad: fn += 1
                else: tn += 1
            acc = (tp + tn) / 256
            print(f"     {name:32s} predicts mismatch: acc={acc:.3f}  "
                  f"(pred&bad={tp} pred&ok={fp} nopred&bad={fn} nopred&ok={tn})")
    return place_ok, cons_ok, direct, rec_ok


if __name__ == '__main__':
    seeds = ['0xDEADBEEF', '0x1234', '0xABCDEF']
    print("#" * 70)
    print("# STEP 2 FIRST: POWER CONTROL (mode=1, share1=0) -- must be 256/256")
    print("#" * 70)
    ctrl = [run(1, s) for s in seeds]
    print("\n" + "#" * 70)
    print("# CASE UNDER TEST (mode=3, non-degenerate sharing)")
    print("#" * 70)
    test = [run(3, s) for s in seeds]

    print("\n" + "=" * 70)
    print("SUMMARY")
    ok = all(d == 256 for _, _, d, _ in ctrl)
    print(f"  power control (mode=1) all 256/256 : {ok}"
          f"   {'-> apparatus has power' if ok else '-> APPARATUS BROKEN, ignore test results'}")
    print(f"  mode=3 direct INTT match           : {[d for _, _, d, _ in test]}")
    print(f"  mode=3 recovered-input match       : {[r for _, _, _, r in test]}")
    print(f"  mode=3 placement verified          : {[p for p, _, _, _ in test]}")
