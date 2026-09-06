#!/bin/bash
# Build script for Experiment D: RTL-level leakage extraction
# Compiles Adams Bridge NTT with Verilator and links testbench
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ADAMSBRIDGE_ROOT="$REPO_ROOT/external/adams-bridge"
OBJ_DIR="$SCRIPT_DIR/obj_dir"

echo "=== Experiment D: Verilator Build ==="
echo "Adams Bridge: $ADAMSBRIDGE_ROOT"
echo "Output dir:   $OBJ_DIR"

# Step 1: Verilator compilation (RTL → C++)
echo ""
echo "--- Step 1: Verilator compilation ---"
verilator --cc \
  --top-module ntt_wrapper \
  --public-flat-rw \
  -Wno-fatal \
  -Wno-WIDTH \
  -Wno-UNOPTFLAT \
  -Wno-CASEINCOMPLETE \
  -Wno-TIMESCALEMOD \
  +incdir+"$ADAMSBRIDGE_ROOT"/src/abr_top/rtl \
  +incdir+"$ADAMSBRIDGE_ROOT"/src/abr_libs/rtl \
  +incdir+"$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl \
  +incdir+"$ADAMSBRIDGE_ROOT"/src/barrett_reduction/rtl \
  "$ADAMSBRIDGE_ROOT"/src/abr_top/rtl/abr_config_defines.svh \
  "$ADAMSBRIDGE_ROOT"/src/abr_top/rtl/abr_params_pkg.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_defines_pkg.sv \
  "$ADAMSBRIDGE_ROOT"/src/abr_libs/rtl/abr_masked_AND.sv \
  "$ADAMSBRIDGE_ROOT"/src/abr_libs/rtl/abr_delay_masked_shares.sv \
  "$ADAMSBRIDGE_ROOT"/src/abr_libs/rtl/abr_masked_add_sub_mod_Boolean.sv \
  "$ADAMSBRIDGE_ROOT"/src/abr_libs/rtl/abr_masked_MUX.sv \
  "$ADAMSBRIDGE_ROOT"/src/abr_libs/rtl/abr_masked_N_bit_Boolean_sub.sv \
  "$ADAMSBRIDGE_ROOT"/src/abr_libs/rtl/abr_masked_full_adder.sv \
  "$ADAMSBRIDGE_ROOT"/src/abr_libs/rtl/abr_masked_A2B_conv.sv \
  "$ADAMSBRIDGE_ROOT"/src/abr_libs/rtl/abr_masked_N_bit_Boolean_adder.sv \
  "$ADAMSBRIDGE_ROOT"/src/abr_libs/rtl/abr_masked_N_bit_Arith_adder.sv \
  "$ADAMSBRIDGE_ROOT"/src/abr_libs/rtl/abr_masked_B2A_conv.sv \
  "$ADAMSBRIDGE_ROOT"/src/abr_libs/rtl/abr_masked_N_bit_mult.sv \
  "$ADAMSBRIDGE_ROOT"/src/abr_libs/rtl/abr_masked_N_bit_mult_two_share.sv \
  "$ADAMSBRIDGE_ROOT"/src/abr_libs/rtl/abr_adder.sv \
  "$ADAMSBRIDGE_ROOT"/src/abr_libs/rtl/abr_add_sub_mod.sv \
  "$ADAMSBRIDGE_ROOT"/src/abr_libs/rtl/abr_ntt_add_sub_mod.sv \
  "$ADAMSBRIDGE_ROOT"/src/abr_libs/rtl/abr_masked_OR.sv \
  "$ADAMSBRIDGE_ROOT"/src/barrett_reduction/rtl/barrett_reduction.sv \
  "$ADAMSBRIDGE_ROOT"/src/barrett_reduction/rtl/masked_barrett_if_cond.sv \
  "$ADAMSBRIDGE_ROOT"/src/barrett_reduction/rtl/masked_barrett_reduction.sv \
  "$ADAMSBRIDGE_ROOT"/src/barrett_reduction/rtl/masked_barrett_if_cond_v2.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_butterfly2x2.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_butterfly.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_mult_dsp.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_mult_reduction.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_special_adder.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_masked_special_adder.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_masked_mult_redux46.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_div2.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_buffer.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_shuffle_buffer.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_twiddle_lookup.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_ctrl.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_top.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_masked_BFU_add_sub.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_mlkem_masked_BFU_add_sub.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_masked_BFU_mult.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_mlkem_masked_BFU_mult.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_masked_gs_butterfly.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_mlkem_masked_gs_butterfly.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_masked_pwm.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_masked_butterfly1x2.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_mlkem_masked_butterfly1x2.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_hybrid_butterfly_2x2.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_karatsuba_pairwm.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/rtl/ntt_masked_pairwm.sv \
  "$ADAMSBRIDGE_ROOT"/src/ntt_top/tb/ntt_ram_tdp_file.sv \
  "$SCRIPT_DIR/ntt_wrapper_patched.sv" \
  --exe "$SCRIPT_DIR/sim_main.cpp" \
  --Mdir "$OBJ_DIR"

echo "Verilator compilation done."

# Step 2: Build C++ model
echo ""
echo "--- Step 2: C++ compilation ---"
make -C "$OBJ_DIR" -f Vntt_wrapper.mk -j$(sysctl -n hw.ncpu 2>/dev/null || nproc) Vntt_wrapper

echo ""
echo "=== Build complete ==="
echo "Binary: $OBJ_DIR/Vntt_wrapper"
