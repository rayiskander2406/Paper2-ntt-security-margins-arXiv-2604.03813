#!/usr/bin/env python3
"""
Decode and compare NTT memory dumps produced by sim_dump.cpp.

Layout (from RTL, see analyze_fill.py header):
  384-bit word = 4 coefficients; coefficient k at bits [96k+95 : 96k]
  share0 = bits [96k+47 : 96k]  (46 bits used)
  share1 = bits [96k+95 : 96k+48] (46 bits used)

With masking enabled a correct design RE-RANDOMISES the output shares on every run,
so raw share bits legitimately differ run-to-run. The invariant that must hold is on
the RECOMBINED value. We do not assume the masking type: we test both arithmetic
(s0+s1 mod q) and Boolean (s0^s1) recombination and report which one is invariant.
"""
import sys

Q = 8380417
MASK46 = (1 << 46) - 1


def load(path):
    """Return {addr: 384-bit int}."""
    mem = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            addr_s, rest = line.split(":", 1)
            words = [int(x, 16) for x in rest.split()]  # MSW first: m_storage[11..0]
            val = 0
            for w in words:            # words[0] is m_storage[11]
                val = (val << 32) | w
            mem[int(addr_s)] = val
    return mem


def coeffs(mem, lo=128, hi=192):
    """Return list of (share0, share1) for the region."""
    out = []
    for a in range(lo, hi):
        w = mem[a]
        for k in range(4):
            out.append(((w >> (96 * k)) & MASK46, (w >> (96 * k + 48)) & MASK46))
    return out


def recombine(pairs, how):
    if how == "arith":
        return [(a + b) % Q for a, b in pairs]
    if how == "bool":
        return [(a ^ b) % Q for a, b in pairs]
    if how == "share0":
        return [a % Q for a, b in pairs]
    raise ValueError(how)


def compare(pa, pb, label_a, label_b, region=(128, 192)):
    ma, mb = load(pa), load(pb)
    ca, cb = coeffs(ma, *region), coeffs(mb, *region)

    raw_same = ca == cb
    results = {}
    for how in ("arith", "bool", "share0"):
        va, vb = recombine(ca, how), recombine(cb, how)
        ndiff = sum(1 for x, y in zip(va, vb) if x != y)
        results[how] = ndiff

    print(f"\n=== {label_a}  vs  {label_b} ===")
    print(f"  raw share bits identical : {raw_same}")
    for how, nd in results.items():
        verdict = "IDENTICAL" if nd == 0 else f"DIFFER in {nd}/{len(ca)} coeffs"
        print(f"  recombined [{how:6s}]      : {verdict}")
    return raw_same, results


def summarize(path, label, region=(128, 192)):
    mem = load(path)
    c = coeffs(mem, *region)
    for how in ("arith", "bool"):
        v = recombine(c, how)
        nz = sum(1 for x in v if x == 0)
        inrange = sum(1 for x in v if x < Q)
        print(f"  [{label}] {how}: zeros={nz}/{len(v)} in_range={inrange}/{len(v)} first8={v[:8]}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "cmp":
        compare(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif cmd == "sum":
        summarize(sys.argv[2], sys.argv[3])
