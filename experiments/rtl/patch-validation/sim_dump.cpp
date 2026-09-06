// sim_dump.cpp — validation harness for Experiment D's patched Adams Bridge INTT.
//
// Derived from ~/qanary/scripts/experiment_d/sim_main.cpp, with ONE capability added:
// it dumps the raw NTT memory contents (before and after the transform) so the
// functional correctness of the INTT can actually be checked. The original records
// only per-cycle HD/HW, which is why correctness was never verified.
//
// All decoding is done in Python to keep this file's logic minimal and auditable.
//
// Plusargs:
//   +maskseed=N    seed for mask/randomness stream (rnd_i, random)   [default 42]
//   +dataseed=N    seed for the input polynomial                     [default 0xDEADBEEF]
//   +masking=0|1   masking_en                                        [default 1]
//   +shuffle=0|1   shuffle_en                                        [default 1]
//   +nttmode=0|1   0 = ct (forward NTT), 1 = gs (INTT)               [default 1]
//   +fill=0|1      0 = reproduce Exp D's exact fill (raw 32-bit),
//                  1 = canonical masked fill (share0=coeff mod q, share1=0) [default 0]
//   +perturb=K     if K>=0, add 1 to the 32-bit word m_storage[0] of memory
//                  address 128+K after filling (apparatus power control)  [default -1]
//   +predump=FILE  dump memory BEFORE the transform
//   +dump=FILE     dump memory AFTER the transform

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

vluint64_t main_time = 0;
double sc_time_stamp() { return main_time; }

static void clock_posedge(Vntt_wrapper* top) { top->clk = 1; top->eval(); main_time++; }
static void clock_negedge(Vntt_wrapper* top) { top->clk = 0; top->eval(); main_time++; }
static void clock_cycle(Vntt_wrapper* top)   { clock_posedge(top); clock_negedge(top); }

template<int N>
static void set_wide_random(VlWide<N>& w, std::mt19937& rng) {
    for (int i = 0; i < N; i++) w.m_storage[i] = rng();
}

// Dump memory words [lo, hi) as hex: one line per address, 12 words MSW-first.
static void dump_mem(Vntt_wrapper___024root* root, const std::string& path, int lo, int hi) {
    std::ofstream o(path);
    if (!o) { std::cerr << "ERROR: cannot open " << path << std::endl; return; }
    o << "# addr : m_storage[11] .. m_storage[0]  (384-bit word, MSW first)\n";
    char buf[16];
    for (int a = lo; a < hi; a++) {
        auto& word = root->ntt_wrapper__DOT__ntt_mem__DOT__mem[a];
        o << a << " :";
        for (int w = 11; w >= 0; w--) {
            snprintf(buf, sizeof(buf), " %08x", word.m_storage[w]);
            o << buf;
        }
        o << "\n";
    }
    o.close();
}

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);

    uint32_t maskseed = 42;
    uint32_t dataseed = 0xDEADBEEF;
    int masking = 1, shuffle = 1, nttmode = 1, fill = 0, perturb = -1, roundtrip = 0;
    std::string dump_file, predump_file;

    // NOTE: Verilated::commandArgsPlusMatch returns "" (NOT nullptr) when a plusarg
    // is absent -- see verilated.cpp:2835 `if (match.empty()) return "";`. The idiom
    // `if ((v = commandArgsPlusMatch("x=")))` is therefore ALWAYS true, and
    // `atoi(v + strlen("+x="))` then reads past the end of a 1-byte buffer.
    // The original sim_main.cpp (lines 95-103) uses exactly that idiom. Guard on v[0].
    auto arg = [](const char* key) -> const char* {
        const char* v = Verilated::commandArgsPlusMatch(key);
        return (v && v[0]) ? v : nullptr;
    };
    const char* v;
    if ((v = arg("maskseed="))) maskseed = (uint32_t)strtoul(v + strlen("+maskseed="), nullptr, 0);
    if ((v = arg("dataseed="))) dataseed = (uint32_t)strtoul(v + strlen("+dataseed="), nullptr, 0);
    if ((v = arg("masking=")))  masking  = atoi(v + strlen("+masking="));
    if ((v = arg("shuffle=")))  shuffle  = atoi(v + strlen("+shuffle="));
    if ((v = arg("nttmode=")))  nttmode  = atoi(v + strlen("+nttmode="));
    if ((v = arg("fill=")))     fill     = atoi(v + strlen("+fill="));
    if ((v = arg("perturb=")))  perturb  = atoi(v + strlen("+perturb="));
    if ((v = arg("roundtrip="))) roundtrip = atoi(v + strlen("+roundtrip="));
    if ((v = arg("dump=")))     dump_file    = v + strlen("+dump=");
    if ((v = arg("predump=")))  predump_file = v + strlen("+predump=");

    std::mt19937 rng(maskseed);

    auto top = new Vntt_wrapper;
    auto root = top->rootp;

    // ---- Phase 1: Reset (identical to sim_main.cpp) ----
    top->clk = 0; top->reset_n = 0; top->zeroize = 0;
    top->mode = 0; top->ntt_enable = 0; top->mlkem = 0;
    top->shuffle_en = 0; top->masking_en = 0; top->random = 0;
    top->load_tb_values = 0; top->accumulate = 0;
    top->sampler_valid = 0; top->sampler_mode = 0;
    top->ntt_mem_base_addr = 0; top->pwo_mem_base_addr = 0;
    memset(&top->rnd_i, 0, sizeof(top->rnd_i));
    memset(&top->sampler_data, 0, sizeof(top->sampler_data));
    top->eval();
    for (int i = 0; i < 4; i++) clock_cycle(top);
    top->reset_n = 1;
    for (int i = 0; i < 4; i++) clock_cycle(top);

    // ---- Phase 2: Fill source memory at base 128 ----
    {
        std::mt19937 data_rng(dataseed);
        for (int addr = 0; addr < 64; addr++) {
            auto& word = root->ntt_wrapper__DOT__ntt_mem__DOT__mem[128 + addr];
            if (fill == 0) {
                // EXACT reproduction of Exp D's sim_main.cpp fill, including the
                // two discarded mod-q draws (they consume PRNG state, so they must
                // be kept to reproduce the byte-identical stimulus).
                for (int w = 0; w < 6; w++) {
                    volatile uint32_t coeff_lo = data_rng() % 8380417; (void)coeff_lo;
                    volatile uint32_t coeff_hi = data_rng() % 8380417; (void)coeff_hi;
                    word.m_storage[w] = data_rng();
                }
                for (int w = 6; w < 12; w++) word.m_storage[w] = 0;
            } else if (fill == 2) {
                // UNMASKED layout (masking_en=0 path): ntt_top.sv:567 registers
                // mem_rd_data[MEM_DATA_WIDTH-1:0] = bits[95:0] = 4 coeffs x 24 bits.
                for (int w = 0; w < 12; w++) word.m_storage[w] = 0;
                uint64_t lo = 0;
                uint32_t c[4];
                for (int k = 0; k < 4; k++) c[k] = data_rng() % 8380417u;
                lo = (uint64_t)c[0] | ((uint64_t)c[1] << 24);
                word.m_storage[0] = (uint32_t)(lo & 0xFFFFFFFFu);
                word.m_storage[1] = (uint32_t)((lo >> 32) & 0xFFFFu) | (c[2] << 16);
                word.m_storage[2] = (c[2] >> 16) | (c[3] << 8);
            } else if (fill == 3) {
                // NON-DEGENERATE arithmetic sharing: share0 + share1 = coeff (mod q),
                // BOTH shares non-zero and in [0,q). Tests that correctness does not
                // depend on the share1=0 special case used by fill=1.
                for (int w = 0; w < 12; w++) word.m_storage[w] = 0;
                for (int k = 0; k < 4; k++) {
                    uint32_t coeff  = data_rng() % 8380417u;
                    uint32_t share1 = 1u + (data_rng() % 8380416u);          // non-zero
                    uint32_t share0 = (uint32_t)(((uint64_t)coeff + 8380417u - share1) % 8380417u);
                    // share0 at bit 96k (32-aligned); share1 at bit 96k+48 (NOT aligned:
                    // 48 mod 32 == 16), so it must be split across two 32-bit words.
                    word.m_storage[(96 * k) / 32] = share0;                  // bits [96k+47:96k]
                    const int b1 = 96 * k + 48;
                    word.m_storage[b1 / 32]     |= (share1 & 0xFFFFu) << 16; // low 16 bits
                    word.m_storage[b1 / 32 + 1] |= (share1 >> 16);           // remaining bits
                }
            } else {
                // Canonical masked ML-DSA layout, per ntt_top.sv:99/286:
                //   logic [3:0][1:0][47:0] share_mem_rd_data = mem_rd_data
                //   coefficient k -> bits [96k+95 : 96k]
                //     share0 = bits [96k+47 : 96k], share1 = bits [96k+95 : 96k+48]
                // We set share0 = coeff (in [0,q)), share1 = 0 -> "unmasked" storage.
                for (int w = 0; w < 12; w++) word.m_storage[w] = 0;
                for (int k = 0; k < 4; k++) {
                    uint32_t coeff = data_rng() % 8380417u;   // valid ML-DSA field element
                    int bit = 96 * k;                          // share0 base bit
                    word.m_storage[bit / 32]     = coeff;      // 96k is always 32-aligned
                    // share1 (bits 96k+48 .. ) left at 0
                }
            }
        }
        // Apparatus power control: perturb one 32-bit word of one address.
        if (perturb >= 0 && perturb < 64) {
            root->ntt_wrapper__DOT__ntt_mem__DOT__mem[128 + perturb].m_storage[0] += 1;
        }
    }
    clock_cycle(top);
    clock_cycle(top);

    if (!predump_file.empty()) dump_mem(root, predump_file, 0, 256);

    // ---- Phase 4: Run the transform ----
    // base addr packing: src << 28 | interim << 14 | dest  (ABR_MEM_ADDR_WIDTH = 14)
    uint64_t base = ((uint64_t)128 << 28) | ((uint64_t)64 << 14) | (uint64_t)128;
    top->mode = nttmode ? 1 : 0;      // 1 = gs (INTT), 0 = ct (forward NTT)
    top->ntt_enable = 1;
    top->masking_en = masking;
    top->shuffle_en = shuffle;
    top->ntt_mem_base_addr = base;
    top->accumulate = 0;

    top->random = rng() & 0x3F;
    set_wide_random<8>(top->rnd_i, rng);
    clock_cycle(top);
    top->ntt_enable = 0;

    int cycles = 0;
    while (!top->ntt_done && cycles < 50000) {
        top->random = rng() & 0x3F;
        set_wide_random<8>(top->rnd_i, rng);
        clock_posedge(top);
        clock_negedge(top);
        cycles++;
    }

    bool done = top->ntt_done;
    for (int i = 0; i < 32; i++) clock_cycle(top);

    // Tier 1(c) ROUND-TRIP: run the inverse transform on the forward result, using the
    // design's OWN NTT as the reference -- zero external-convention risk.
    // Stage 1 above ran ct with dest=128; stage 2 runs gs src=128 -> dest=192.
    int cycles2 = -1;
    if (roundtrip) {
        uint64_t base2 = ((uint64_t)128 << 28) | ((uint64_t)64 << 14) | (uint64_t)192;
        top->mode = 1;                 // gs (INTT)
        top->ntt_enable = 1;
        top->ntt_mem_base_addr = base2;
        top->random = rng() & 0x3F;
        set_wide_random<8>(top->rnd_i, rng);
        clock_cycle(top);
        top->ntt_enable = 0;
        cycles2 = 0;
        while (!top->ntt_done && cycles2 < 50000) {
            top->random = rng() & 0x3F;
            set_wide_random<8>(top->rnd_i, rng);
            clock_posedge(top);
            clock_negedge(top);
            cycles2++;
        }
        done = done && top->ntt_done;
        for (int i = 0; i < 32; i++) clock_cycle(top);
    }

    if (!dump_file.empty()) dump_mem(root, dump_file, 0, 256);

    std::cout << "done=" << (done ? 1 : 0)
              << " cycles=" << cycles
              << " masking=" << masking
              << " shuffle=" << shuffle
              << " nttmode=" << nttmode
              << " fill=" << fill
              << " maskseed=" << maskseed
              << " dataseed=0x" << std::hex << dataseed << std::dec
              << " perturb=" << perturb
              << " roundtrip=" << roundtrip << " cycles2=" << cycles2
              << std::endl;

    delete top;
    return done ? 0 : 1;
}
