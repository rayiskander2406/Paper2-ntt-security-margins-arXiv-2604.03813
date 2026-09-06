#!/usr/bin/env python3
"""
Static reproduction of Experiment D's memory fill (sim_main.cpp Phase 2), decoded
under the Adams Bridge ML-DSA masked memory layout established from the RTL.

No simulator needed: this reproduces the exact PRNG stream C++ std::mt19937 emits
and shows what polynomial the INTT actually receives.

Layout evidence:
  abr_params_pkg.sv : MLDSA_Q_WIDTH=24, MLDSA_SHARE_WIDTH=48, COEFF_PER_CLK=4,
                      ABR_MEM_MASKED_DATA_WIDTH=384
  ntt_top.sv:99     : logic [3:0][1:0][MLDSA_SHARE_WIDTH-1:0] share_mem_rd_data
  ntt_top.sv:286    : share_mem_rd_data = mem_rd_data   (ML-DSA gs+masked: direct bitcast)
  ntt_top.sv:595    : share_mem_rd_data_reg[i][j] <= share_mem_rd_data[i][j][45:0]
  => coefficient k occupies bits [96k+95 : 96k]
       share0 = bits [96k+47 : 96k]   (46 bits used)
       share1 = bits [96k+95 : 96k+48] (46 bits used)
"""

Q = 8380417


class MT19937:
    """Matches C++ std::mt19937 seeded with a single 32-bit value (init_genrand)."""

    def __init__(self, seed):
        self.mt = [0] * 624
        self.mt[0] = seed & 0xFFFFFFFF
        for i in range(1, 624):
            self.mt[i] = (1812433253 * (self.mt[i - 1] ^ (self.mt[i - 1] >> 30)) + i) & 0xFFFFFFFF
        self.idx = 624

    def _generate(self):
        for i in range(624):
            y = (self.mt[i] & 0x80000000) + (self.mt[(i + 1) % 624] & 0x7FFFFFFF)
            self.mt[i] = self.mt[(i + 397) % 624] ^ (y >> 1)
            if y % 2:
                self.mt[i] ^= 2567483615
        self.idx = 0

    def __call__(self):
        if self.idx >= 624:
            self._generate()
        y = self.mt[self.idx]
        y ^= y >> 11
        y ^= (y << 7) & 2636928640
        y ^= (y << 15) & 4022730752
        y ^= y >> 18
        self.idx += 1
        return y & 0xFFFFFFFF


def expd_fill(dataseed):
    """Reproduce sim_main.cpp Phase 2 exactly. Returns list of 64 x 384-bit ints."""
    rng = MT19937(dataseed)
    words = []
    for _addr in range(64):
        st = [0] * 12
        for w in range(6):
            rng()          # coeff_lo = data_rng() % Q   -- DISCARDED
            rng()          # coeff_hi = data_rng() % Q   -- DISCARDED
            st[w] = rng()  # word.m_storage[w] = data_rng()
        # st[6..11] = 0
        val = 0
        for w in range(12):
            val |= st[w] << (32 * w)
        words.append(val)
    return words


def decode(word):
    """Decode a 384-bit masked word into 4 (share0, share1) pairs, 46 bits each."""
    out = []
    for k in range(4):
        share0 = (word >> (96 * k)) & ((1 << 46) - 1)
        share1 = (word >> (96 * k + 48)) & ((1 << 46) - 1)
        out.append((share0, share1))
    return out


def main():
    words = expd_fill(0xDEADBEEF)

    coeffs = []
    for w in words:
        coeffs.extend(decode(w))

    print(f"Total coefficient slots: {len(coeffs)}  (expect 256)")

    both_zero = sum(1 for s0, s1 in coeffs if s0 == 0 and s1 == 0)
    share1_zero = sum(1 for _s0, s1 in coeffs if s1 == 0)
    share1_nonzero = sum(1 for _s0, s1 in coeffs if s1 != 0)
    print(f"\n--- What Exp D's testbench actually loads ---")
    print(f"coefficients with BOTH shares zero (i.e. value 0): {both_zero} / 256")
    print(f"coefficients with share1 == 0 (the claimed config): {share1_zero} / 256")
    print(f"coefficients with share1 != 0 (contradicts claim):  {share1_nonzero} / 256")

    # Position analysis: which k-slot within each 4-coefficient word is zero?
    print(f"\n--- Zero pattern by slot position (k mod 4) ---")
    for k in range(4):
        sl = coeffs[k::4]
        z = sum(1 for s0, s1 in sl if s0 == 0 and s1 == 0)
        print(f"  slot k={k}: {z}/{len(sl)} slots identically zero")

    # Range analysis on the non-zero shares
    nz = [s for s0, s1 in coeffs for s in (s0, s1) if s != 0]
    over_q = sum(1 for s in nz if s >= Q)
    print(f"\n--- Range of loaded shares (valid ML-DSA field element is < q = {Q}) ---")
    print(f"non-zero share values: {len(nz)}")
    print(f"  >= q (out of range):  {over_q} ({100.0*over_q/len(nz):.1f}%)")
    print(f"  max value observed:   {max(nz)}  (= {max(nz)/Q:.1f} x q)")

    # Arithmetic masking: value = (share0 + share1) mod q
    vals = [(s0 + s1) % Q for s0, s1 in coeffs]
    zero_vals = sum(1 for v in vals if v == 0)
    print(f"\n--- Represented polynomial, assuming arithmetic masking v = (s0+s1) mod q ---")
    print(f"coefficients equal to 0: {zero_vals} / 256  ({100.0*zero_vals/256:.1f}%)")

    print(f"\n--- First 8 coefficient slots (share0, share1) ---")
    for i, (s0, s1) in enumerate(coeffs[:8]):
        print(f"  coeff[{i:3d}] (word {i//4}, k={i%4}): share0=0x{s0:012x}  share1=0x{s1:012x}")

    print(f"\n--- Cross-check: what sim_main.cpp's comment CLAIMED ---")
    print("  'share0: words[0..5] (192 bits), share1: words[6..11] (192 bits, all zero)'")
    print("  That is a BLOCKED layout. The RTL (ntt_top.sv:99/286) uses an INTERLEAVED")
    print("  layout, {share1_k, share0_k} per coefficient at bits [96k+95:96k].")


if __name__ == "__main__":
    main()
