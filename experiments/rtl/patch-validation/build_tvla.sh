#!/bin/bash
# Build one wrapper variant into its own obj dir. Scratch-only; touches neither repo.
set -e
VARIANT="$1"
AB="$HOME/qanary/external/adams-bridge"
SCRATCH="/tmp/rtl-validate"
# Match the toolchain the March Exp D run used (obj_dir/Vntt_wrapper.mk records 5.044).
# Verilator 5.048 hits an internal error (V3Delayed "Unexpected LHS form") on
# ntt_masked_gs_butterfly.sv:182, so the original version is rebuilt in scratch.
export VERILATOR_ROOT="$SCRATCH/verilator-5.044"
VERILATOR="$VERILATOR_ROOT/bin/verilator"
WRAPPER="$SCRATCH/rtl/wrapper_${VARIANT}.sv"
OBJ="$SCRATCH/build/tvla_${VARIANT}"

[ -f "$WRAPPER" ] || { echo "no such variant: $WRAPPER"; exit 2; }

"$VERILATOR" --cc \
  --top-module ntt_wrapper \
  --public-flat-rw \
  -Wno-fatal -Wno-WIDTH -Wno-UNOPTFLAT -Wno-CASEINCOMPLETE -Wno-TIMESCALEMOD -Wno-PINMISSING \
  +incdir+"$AB"/src/abr_top/rtl \
  +incdir+"$AB"/src/abr_libs/rtl \
  +incdir+"$AB"/src/ntt_top/rtl \
  +incdir+"$AB"/src/barrett_reduction/rtl \
  "$AB"/src/abr_top/rtl/abr_config_defines.svh \
  "$AB"/src/abr_top/rtl/abr_params_pkg.sv \
  "$AB"/src/ntt_top/rtl/ntt_defines_pkg.sv \
  "$AB"/src/abr_libs/rtl/abr_masked_AND.sv \
  "$AB"/src/abr_libs/rtl/abr_delay_masked_shares.sv \
  "$AB"/src/abr_libs/rtl/abr_masked_add_sub_mod_Boolean.sv \
  "$AB"/src/abr_libs/rtl/abr_masked_MUX.sv \
  "$AB"/src/abr_libs/rtl/abr_masked_N_bit_Boolean_sub.sv \
  "$AB"/src/abr_libs/rtl/abr_masked_full_adder.sv \
  "$AB"/src/abr_libs/rtl/abr_masked_A2B_conv.sv \
  "$AB"/src/abr_libs/rtl/abr_masked_N_bit_Boolean_adder.sv \
  "$AB"/src/abr_libs/rtl/abr_masked_N_bit_Arith_adder.sv \
  "$AB"/src/abr_libs/rtl/abr_masked_B2A_conv.sv \
  "$AB"/src/abr_libs/rtl/abr_masked_N_bit_mult.sv \
  "$AB"/src/abr_libs/rtl/abr_masked_N_bit_mult_two_share.sv \
  "$AB"/src/abr_libs/rtl/abr_adder.sv \
  "$AB"/src/abr_libs/rtl/abr_add_sub_mod.sv \
  "$AB"/src/abr_libs/rtl/abr_ntt_add_sub_mod.sv \
  "$AB"/src/abr_libs/rtl/abr_masked_OR.sv \
  "$AB"/src/barrett_reduction/rtl/barrett_reduction.sv \
  "$AB"/src/barrett_reduction/rtl/masked_barrett_if_cond.sv \
  "$AB"/src/barrett_reduction/rtl/masked_barrett_reduction.sv \
  "$AB"/src/barrett_reduction/rtl/masked_barrett_if_cond_v2.sv \
  "$AB"/src/ntt_top/rtl/ntt_butterfly2x2.sv \
  "$AB"/src/ntt_top/rtl/ntt_butterfly.sv \
  "$AB"/src/ntt_top/rtl/ntt_mult_dsp.sv \
  "$AB"/src/ntt_top/rtl/ntt_mult_reduction.sv \
  "$AB"/src/ntt_top/rtl/ntt_special_adder.sv \
  "$AB"/src/ntt_top/rtl/ntt_masked_special_adder.sv \
  "$AB"/src/ntt_top/rtl/ntt_masked_mult_redux46.sv \
  "$AB"/src/ntt_top/rtl/ntt_div2.sv \
  "$AB"/src/ntt_top/rtl/ntt_buffer.sv \
  "$AB"/src/ntt_top/rtl/ntt_shuffle_buffer.sv \
  "$AB"/src/ntt_top/rtl/ntt_twiddle_lookup.sv \
  "$AB"/src/ntt_top/rtl/ntt_ctrl.sv \
  "$AB"/src/ntt_top/rtl/ntt_top.sv \
  "$AB"/src/ntt_top/rtl/ntt_masked_BFU_add_sub.sv \
  "$AB"/src/ntt_top/rtl/ntt_mlkem_masked_BFU_add_sub.sv \
  "$AB"/src/ntt_top/rtl/ntt_masked_BFU_mult.sv \
  "$AB"/src/ntt_top/rtl/ntt_mlkem_masked_BFU_mult.sv \
  "$AB"/src/ntt_top/rtl/ntt_masked_gs_butterfly.sv \
  "$AB"/src/ntt_top/rtl/ntt_mlkem_masked_gs_butterfly.sv \
  "$AB"/src/ntt_top/rtl/ntt_masked_pwm.sv \
  "$AB"/src/ntt_top/rtl/ntt_masked_butterfly1x2.sv \
  "$AB"/src/ntt_top/rtl/ntt_mlkem_masked_butterfly1x2.sv \
  "$AB"/src/ntt_top/rtl/ntt_hybrid_butterfly_2x2.sv \
  "$AB"/src/ntt_top/rtl/ntt_karatsuba_pairwm.sv \
  "$AB"/src/ntt_top/rtl/ntt_masked_pairwm.sv \
  "$AB"/src/ntt_top/tb/ntt_ram_tdp_file.sv \
  "$WRAPPER" \
  --exe "$SCRATCH/sim_tvla.cpp" \
  --Mdir "$OBJ" > "$SCRATCH/build/verilate_${VARIANT}.log" 2>&1

make -C "$OBJ" -f Vntt_wrapper.mk -j8 Vntt_wrapper > "$SCRATCH/build/make_${VARIANT}.log" 2>&1
echo "BUILT: $OBJ/Vntt_wrapper"
