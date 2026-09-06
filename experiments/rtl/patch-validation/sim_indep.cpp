// sim_indep.cpp — INDEPENDENT re-derivation harness for the non-degenerate-masked-input question.
//
// Written from scratch (not copied from /tmp/rtl-validate/sim_dump.cpp) to re-test:
//   "non-degenerate masked input does not reproduce (114/256; remainder off by exactly 2^23 mod q)"
//
// The critical addition over the previous harness: it writes a SIDECAR FILE recording exactly what
// the testbench INTENDED to store for every coefficient (coeff, share0, share1). That makes the
// share bit-placement empirically verifiable instead of assumed -- the previous run's first attempt
// had a 16-bit placement bug precisely because placement was assumed.
//
// Plusargs:
//   +mode=1   share1 = 0            (degenerate; POWER CONTROL, must give a correct INTT)
//   +mode=3   share0+share1 = coeff (non-degenerate; the case under test)
//   +maskseed=N +dataseed=N +shuffle=0|1 +masking=0|1
//   +intended=FILE  sidecar: "idx coeff share0 share1"
//   +predump=FILE   memory before transform
//   +dump=FILE      memory after transform

#include "Vntt_wrapper.h"
#include "Vntt_wrapper___024root.h"
#include "verilated.h"
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <random>
#include <string>

static const uint32_t Q = 8380417;

vluint64_t main_time = 0;
double sc_time_stamp() { return main_time; }

static void tick(Vntt_wrapper* t) { t->clk = 1; t->eval(); main_time++; t->clk = 0; t->eval(); main_time++; }

template<int N> static void rnd_wide(VlWide<N>& w, std::mt19937& r) {
    for (int i = 0; i < N; i++) w.m_storage[i] = r();
}

// commandArgsPlusMatch returns "" (not nullptr) when absent -- guard on v[0].
static const char* arg(const char* k) {
    const char* v = Verilated::commandArgsPlusMatch(k);
    return (v && v[0]) ? v : nullptr;
}

static void dump(Vntt_wrapper___024root* root, const std::string& p, int lo, int hi) {
    std::ofstream o(p);
    char b[16];
    for (int a = lo; a < hi; a++) {
        auto& w = root->ntt_wrapper__DOT__ntt_mem__DOT__mem[a];
        o << a << " :";
        for (int i = 11; i >= 0; i--) { snprintf(b, sizeof(b), " %08x", w.m_storage[i]); o << b; }
        o << "\n";
    }
}

// Write `val` (<= 46 bits) into the 384-bit word at bit offset `bit`, honouring
// non-32-aligned offsets (share1 sits at 96k+48, and 48 mod 32 == 16).
static void put_bits(VlWide<12>& w, int bit, uint64_t val) {
    for (int i = 0; i < 46; i++) {
        if ((val >> i) & 1ULL) {
            int b = bit + i;
            w.m_storage[b / 32] |= (1u << (b % 32));
        }
    }
}

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);

    uint32_t maskseed = 42, dataseed = 0xDEADBEEF;
    int mode = 3, shuffle = 1, masking = 1;
    std::string dumpf, predumpf, intendedf;
    const char* v;
    if ((v = arg("maskseed="))) maskseed = (uint32_t)strtoul(v + 10, nullptr, 0);
    if ((v = arg("dataseed="))) dataseed = (uint32_t)strtoul(v + 10, nullptr, 0);
    if ((v = arg("mode=")))     mode     = atoi(v + 6);
    if ((v = arg("shuffle=")))  shuffle  = atoi(v + 9);
    if ((v = arg("masking=")))  masking  = atoi(v + 9);
    if ((v = arg("dump=")))     dumpf     = v + 6;
    if ((v = arg("predump=")))  predumpf  = v + 9;
    if ((v = arg("intended="))) intendedf = v + 10;

    std::mt19937 rng(maskseed);
    auto top = new Vntt_wrapper;
    auto root = top->rootp;

    top->clk = 0; top->reset_n = 0; top->zeroize = 0; top->mode = 0;
    top->ntt_enable = 0; top->mlkem = 0; top->shuffle_en = 0; top->masking_en = 0;
    top->random = 0; top->load_tb_values = 0; top->accumulate = 0;
    top->sampler_valid = 0; top->sampler_mode = 0;
    top->ntt_mem_base_addr = 0; top->pwo_mem_base_addr = 0;
    memset(&top->rnd_i, 0, sizeof(top->rnd_i));
    memset(&top->sampler_data, 0, sizeof(top->sampler_data));
    top->eval();
    for (int i = 0; i < 4; i++) tick(top);
    top->reset_n = 1;
    for (int i = 0; i < 4; i++) tick(top);

    // ---- fill + sidecar ----
    {
        std::mt19937 drng(dataseed);
        std::ofstream si;
        if (!intendedf.empty()) si.open(intendedf);
        int idx = 0;
        for (int a = 0; a < 64; a++) {
            auto& w = root->ntt_wrapper__DOT__ntt_mem__DOT__mem[128 + a];
            for (int i = 0; i < 12; i++) w.m_storage[i] = 0;
            for (int k = 0; k < 4; k++) {
                uint32_t coeff, s0, s1;
                if (mode == 4) {
                    // NON-DEGENERATE but NO REDUCTION NEEDED: both shares < q/2, so
                    // s0 + s1 = coeff exactly, with no conditional subtract required.
                    // Discriminates "input recombination mis-reduces" from
                    // "the masked datapath itself accumulates reduction error".
                    s0 = drng() % (Q / 2);
                    s1 = 1u + (drng() % (Q / 2 - 1));
                    coeff = s0 + s1;                      // < q by construction
                } else if (mode == 5) {
                    // ALWAYS-WRAPPING: both shares in [2^22, q) so s0+s1 >= 2^23 always.
                    // Tests the hypothesis that input recombination reduces mod 2^23
                    // instead of mod q (predicted read value = s0+s1-2^23, which is
                    // exactly 8191 = 2^23-q below the correct (s0+s1)-q).
                    s0 = 4194304u + (drng() % (Q - 4194304u));
                    s1 = 4194304u + (drng() % (Q - 4194304u));
                    coeff = (uint32_t)(((uint64_t)s0 + s1) % Q);
                } else {
                    coeff = drng() % Q;
                    s1 = (mode == 3) ? (1u + (drng() % (Q - 1))) : 0u;
                    s0 = (uint32_t)(((uint64_t)coeff + Q - s1) % Q);
                }
                put_bits(w, 96 * k,      s0);   // share0 -> bits [96k+45 : 96k]
                put_bits(w, 96 * k + 48, s1);   // share1 -> bits [96k+93 : 96k+48]
                if (si) si << idx << " " << coeff << " " << s0 << " " << s1 << "\n";
                idx++;
            }
        }
    }
    tick(top); tick(top);
    if (!predumpf.empty()) dump(root, predumpf, 0, 256);

    // ---- gs / INTT, src=128 interim=64 dest=128 ----
    top->mode = 1;
    top->ntt_enable = 1;
    top->masking_en = masking;
    top->shuffle_en = shuffle;
    top->ntt_mem_base_addr = ((uint64_t)128 << 28) | ((uint64_t)64 << 14) | (uint64_t)128;
    top->accumulate = 0;
    top->random = rng() & 0x3F;
    rnd_wide<8>(top->rnd_i, rng);
    tick(top);
    top->ntt_enable = 0;

    int c = 0;
    while (!top->ntt_done && c < 50000) {
        top->random = rng() & 0x3F;
        rnd_wide<8>(top->rnd_i, rng);
        tick(top);
        c++;
    }
    bool done = top->ntt_done;
    for (int i = 0; i < 32; i++) tick(top);
    if (!dumpf.empty()) dump(root, dumpf, 0, 256);

    std::cout << "done=" << done << " cycles=" << c << " mode=" << mode
              << " masking=" << masking << " shuffle=" << shuffle
              << " dataseed=0x" << std::hex << dataseed << std::dec << std::endl;
    delete top;
    return done ? 0 : 1;
}
