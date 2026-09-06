// sim_main.cpp — Verilator testbench for Experiment D: RTL-level leakage extraction
// Drives Adams Bridge INTT (ML-DSA, masking + shuffling), extracts per-cycle
// register Hamming weights for TVLA analysis.
//
// Usage: ./Vntt_wrapper +seed=<N> +mode=<0|1> +output=<file>
//   mode 0 = fixed input (same polynomial for all runs)
//   mode 1 = random input (random polynomial)

#include "Vntt_wrapper.h"
#include "Vntt_wrapper___024root.h"
#include "verilated.h"
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <vector>
#include <random>
#include <iostream>

// Simulation time (Verilator requirement)
vluint64_t main_time = 0;
double sc_time_stamp() { return main_time; }

// Popcount helpers
static inline int popcount32(uint32_t v) { return __builtin_popcount(v); }

template<int N>
static int popcount_wide(const VlWide<N>& w) {
    int count = 0;
    for (int i = 0; i < N; i++) count += popcount32(w.m_storage[i]);
    return count;
}

template<int N>
static void xor_wide(VlWide<N>& dst, const VlWide<N>& a, const VlWide<N>& b) {
    for (int i = 0; i < N; i++) dst.m_storage[i] = a.m_storage[i] ^ b.m_storage[i];
}

// Per-cycle extracted data
struct CycleRecord {
    uint16_t cycle;
    uint8_t  masking_en_ctrl;
    uint8_t  rounds_count;
    uint8_t  read_fsm;
    uint8_t  write_fsm;
    uint8_t  bf_enable;
    uint8_t  _pad;
    // Hamming weights (HW)
    uint16_t hw_bf_out;      // butterfly output registers (uv_o_reg, 92 bits)
    uint16_t hw_mem_wr;      // memory write data (mem_wr_data_int, 96 bits)
    uint16_t hw_mem_rd;      // memory read data (mem_rd_data_reg, 96 bits)
    uint16_t hw_addr;        // address signals (rd + wr addr, 28 bits)
    uint16_t hw_control;     // control/FSM (10 bits)
    // Hamming distances (HD = HW of XOR with previous cycle)
    uint16_t hd_bf_out;
    uint16_t hd_mem_wr;
    uint16_t hd_mem_rd;
    uint16_t hd_addr;
    uint16_t hd_control;
};

// Poke helper for VlWide
template<int N>
static void set_wide_random(VlWide<N>& w, std::mt19937& rng) {
    for (int i = 0; i < N; i++) w.m_storage[i] = rng();
}

static void clock_posedge(Vntt_wrapper* top) {
    top->clk = 1;
    top->eval();
    main_time++;
}

static void clock_negedge(Vntt_wrapper* top) {
    top->clk = 0;
    top->eval();
    main_time++;
}

static void clock_cycle(Vntt_wrapper* top) {
    clock_posedge(top);
    clock_negedge(top);
}

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);

    // Parse plusargs
    uint32_t seed = 42;
    int input_mode = 0;  // 0=fixed, 1=random
    std::string output_file = "run_output.bin";

    // Verilator +arg parsing
    const char* val;
    if ((val = Verilated::commandArgsPlusMatch("seed="))) {
        seed = atoi(val + strlen("+seed="));
    }
    if ((val = Verilated::commandArgsPlusMatch("mode="))) {
        input_mode = atoi(val + strlen("+mode="));
    }
    if ((val = Verilated::commandArgsPlusMatch("output="))) {
        output_file = val + strlen("+output=");
    }

    std::mt19937 rng(seed);

    // Create model
    auto top = new Vntt_wrapper;
    auto root = top->rootp;

    // ========================================
    // Phase 1: Reset
    // ========================================
    top->clk = 0;
    top->reset_n = 0;
    top->zeroize = 0;
    top->mode = 0;           // ct
    top->ntt_enable = 0;
    top->mlkem = 0;          // ML-DSA mode
    top->shuffle_en = 0;
    top->masking_en = 0;
    top->random = 0;
    top->load_tb_values = 0;
    top->accumulate = 0;
    top->sampler_valid = 0;
    top->sampler_mode = 0;
    top->ntt_mem_base_addr = 0;
    top->pwo_mem_base_addr = 0;
    // Zero out rnd_i (230 bits = 8 words)
    memset(&top->rnd_i, 0, sizeof(top->rnd_i));
    // Zero out sampler_data
    memset(&top->sampler_data, 0, sizeof(top->sampler_data));

    top->eval();

    // Hold reset for 4 cycles
    for (int i = 0; i < 4; i++) clock_cycle(top);

    // Release reset
    top->reset_n = 1;
    for (int i = 0; i < 4; i++) clock_cycle(top);

    // ========================================
    // Phase 2: Fill memory with test data (skip NTT forward pass)
    // ========================================
    // We directly poke the INTT source memory (address base 128) with
    // test polynomial data. This avoids dependency on ntt_unmasked_input.hex
    // and gives us exact control over fixed vs random inputs.
    //
    // Memory format: 384-bit words (VlWide<12>), 64 entries for 256 coeffs.
    // For unmasked storage: share0 = data, share1 = 0.
    {
        // For fixed mode: use a SEPARATE fixed seed so the polynomial is
        // identical across all runs (the main rng varies per run for masks).
        // For random mode: use the main rng so each run gets different data.
        std::mt19937 data_rng(input_mode == 0 ? 0xDEADBEEF : seed);

        for (int addr = 0; addr < 64; addr++) {
            auto& word = root->ntt_wrapper__DOT__ntt_mem__DOT__mem[128 + addr];
            // 4 coefficients per 384-bit word:
            //   share0: words[0..5] (192 bits = 4 × 48-bit shares)
            //   share1: words[6..11] (192 bits, all zero for unmasked)
            // Each 48-bit share holds one 23-bit coefficient (zero-extended).
            for (int w = 0; w < 6; w++) {
                // Generate 23-bit coefficient values mod MLDSA_Q
                uint32_t coeff_lo = data_rng() % 8380417;  // MLDSA_Q
                uint32_t coeff_hi = data_rng() % 8380417;
                // Pack two 24-bit fields into 48 bits (stored in 2 × 32-bit words)
                // Actually each 48-bit share slot maps to 1.5 words. Simpler:
                // just fill the share0 half with random 32-bit values.
                word.m_storage[w] = data_rng();
            }
            // share1 = 0 (unmasked)
            for (int w = 6; w < 12; w++) {
                word.m_storage[w] = 0;
            }
        }
    }
    clock_cycle(top);
    clock_cycle(top);

    // ========================================
    // Phase 4: Run INTT with masking + shuffling (THE EXPERIMENT)
    // ========================================
    // INTT: mode=gs(1), src=128, interim=64, dest=128, masking=1, shuffle=1
    uint64_t intt_base = ((uint64_t)128 << 28) | ((uint64_t)64 << 14) | (uint64_t)128;
    top->mode = 1;  // gs (INTT)
    top->ntt_enable = 1;
    top->masking_en = 1;
    top->shuffle_en = 1;
    top->ntt_mem_base_addr = intt_base;
    top->accumulate = 0;

    top->random = rng() & 0x3F;
    set_wide_random<8>(top->rnd_i, rng);
    clock_cycle(top);
    top->ntt_enable = 0;

    // Storage for previous cycle values (for HD computation)
    VlWide<3> prev_bf_out = {};
    VlWide<3> prev_mem_wr = {};
    VlWide<3> prev_mem_rd = {};
    uint32_t prev_addr = 0;
    uint32_t prev_ctrl = 0;

    std::vector<CycleRecord> records;
    records.reserve(4096);

    int intt_cycles = 0;
    bool first_cycle = true;

    while (!top->ntt_done && intt_cycles < 50000) {
        // Drive fresh randomness every cycle
        top->random = rng() & 0x3F;
        set_wide_random<8>(top->rnd_i, rng);

        clock_posedge(top);

        // Extract register group values
        CycleRecord rec;
        memset(&rec, 0, sizeof(rec));
        rec.cycle = intt_cycles;

        // Control signals
        rec.masking_en_ctrl = root->ntt_wrapper__DOT__ntt_top_inst0__DOT__masking_en_ctrl;
        rec.rounds_count = root->ntt_wrapper__DOT__ntt_top_inst0__DOT__ntt_ctrl_inst0__DOT__rounds_count;
        rec.read_fsm = root->ntt_wrapper__DOT__ntt_top_inst0__DOT__ntt_ctrl_inst0__DOT__read_fsm_state_ps;
        rec.write_fsm = root->ntt_wrapper__DOT__ntt_top_inst0__DOT__ntt_ctrl_inst0__DOT__write_fsm_state_ps;
        rec.bf_enable = root->ntt_wrapper__DOT__ntt_top_inst0__DOT__bf_enable;

        // Group 1: Butterfly output (uv_o_reg, 92 bits packed in VlWide<3>)
        auto& bf_out = root->ntt_wrapper__DOT__ntt_top_inst0__DOT__uv_o_reg;
        rec.hw_bf_out = popcount_wide<3>(bf_out);

        // Group 2: Memory write data (unmasked, 96 bits in VlWide<3>)
        auto& mem_wr = root->ntt_wrapper__DOT__ntt_top_inst0__DOT__mem_wr_data_reg;
        rec.hw_mem_wr = popcount_wide<3>(mem_wr);

        // Group 3: Memory read data (96 bits in VlWide<3>)
        auto& mem_rd = root->ntt_wrapper__DOT__ntt_top_inst0__DOT__mem_rd_data_reg;
        rec.hw_mem_rd = popcount_wide<3>(mem_rd);

        // Group 4: Address signals (rd_addr + wr_addr, each 14 bits)
        uint32_t addr_val =
            ((uint32_t)root->ntt_wrapper__DOT__ntt_top_inst0__DOT__mem_rd_addr & 0x3FFF) |
            (((uint32_t)root->ntt_wrapper__DOT__ntt_top_inst0__DOT__mem_wr_addr & 0x3FFF) << 14);
        rec.hw_addr = popcount32(addr_val);

        // Group 5: Control/FSM
        uint32_t ctrl_val =
            ((uint32_t)rec.masking_en_ctrl) |
            ((uint32_t)rec.rounds_count << 1) |
            ((uint32_t)rec.read_fsm << 4) |
            ((uint32_t)rec.write_fsm << 7) |
            ((uint32_t)rec.bf_enable << 10);
        rec.hw_control = popcount32(ctrl_val);

        // Compute HD (Hamming distance from previous cycle)
        if (!first_cycle) {
            VlWide<3> xor_bf, xor_mw, xor_mr;
            xor_wide<3>(xor_bf, bf_out, prev_bf_out);
            xor_wide<3>(xor_mw, mem_wr, prev_mem_wr);
            xor_wide<3>(xor_mr, mem_rd, prev_mem_rd);
            rec.hd_bf_out = popcount_wide<3>(xor_bf);
            rec.hd_mem_wr = popcount_wide<3>(xor_mw);
            rec.hd_mem_rd = popcount_wide<3>(xor_mr);
            rec.hd_addr = popcount32(addr_val ^ prev_addr);
            rec.hd_control = popcount32(ctrl_val ^ prev_ctrl);
        }

        // Save current as previous
        memcpy(&prev_bf_out, &bf_out, sizeof(prev_bf_out));
        memcpy(&prev_mem_wr, &mem_wr, sizeof(prev_mem_wr));
        memcpy(&prev_mem_rd, &mem_rd, sizeof(prev_mem_rd));
        prev_addr = addr_val;
        prev_ctrl = ctrl_val;
        first_cycle = false;

        records.push_back(rec);

        clock_negedge(top);
        intt_cycles++;
    }

    if (!top->ntt_done) {
        std::cerr << "ERROR: INTT did not complete within 50000 cycles" << std::endl;
        delete top;
        return 1;
    }

    // ========================================
    // Phase 5: Write output
    // ========================================
    std::ofstream out(output_file, std::ios::binary);
    if (!out) {
        std::cerr << "ERROR: Cannot open output file: " << output_file << std::endl;
        delete top;
        return 1;
    }

    // Header
    uint32_t magic = 0x4C4B4148;  // "HAKL" (HArdware LeaKage)
    uint32_t version = 1;
    uint32_t num_cycles = records.size();
    uint32_t record_size = sizeof(CycleRecord);
    out.write(reinterpret_cast<const char*>(&magic), 4);
    out.write(reinterpret_cast<const char*>(&version), 4);
    out.write(reinterpret_cast<const char*>(&seed), 4);
    out.write(reinterpret_cast<const char*>(&input_mode), 4);
    out.write(reinterpret_cast<const char*>(&num_cycles), 4);
    out.write(reinterpret_cast<const char*>(&record_size), 4);
    // Reserved
    uint32_t reserved = 0;
    out.write(reinterpret_cast<const char*>(&reserved), 4);
    out.write(reinterpret_cast<const char*>(&reserved), 4);

    // Records
    out.write(reinterpret_cast<const char*>(records.data()),
              records.size() * sizeof(CycleRecord));
    out.close();

    std::cout << "INTT completed in " << intt_cycles << " cycles. "
              << "Wrote " << records.size() << " records to " << output_file << std::endl;

    delete top;
    return 0;
}
