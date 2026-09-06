#!/bin/bash
# Full validation matrix. All artifacts land in /tmp/rtl-validate/out (scratch only).
cd /tmp/rtl-validate/out || exit 1
BD=/tmp/rtl-validate/build
run() {  # run <variant> <tag> <extra args...>
  local var=$1 tag=$2; shift 2
  "$BD/obj_$var/Vntt_wrapper" "$@" +dump="d_${tag}.txt" 2>&1 | grep -v 'In ram' | sed "s/^/[${tag}] /"
}

EXPD="+maskseed=42 +dataseed=0xDEADBEEF +masking=1 +shuffle=1 +nttmode=1 +fill=0"

echo "########## A. Baseline (Exp D exact config) ##########"
run patched   base        $EXPD

echo "########## B. Patch-timing variants (expect INERT) ##########"
run stock     stock       $EXPD
run delay2    delay2      $EXPD
run tied0     tied0       $EXPD
run tied1     tied1       $EXPD

echo "########## C. Positive controls (expect DIFFERENT) ##########"
run datadelay datadelay   $EXPD
run patched   perturb     $EXPD +perturb=0

echo "########## D. Mask-independence (invariant a) ##########"
run patched   mask42      $EXPD
run patched   mask9999    +maskseed=9999 +dataseed=0xDEADBEEF +masking=1 +shuffle=1 +nttmode=1 +fill=0
run patched   mask777     +maskseed=777  +dataseed=0xDEADBEEF +masking=1 +shuffle=1 +nttmode=1 +fill=0

echo "########## E. Shuffle-independence (invariant b) ##########"
run patched   shufoff     +maskseed=42 +dataseed=0xDEADBEEF +masking=1 +shuffle=0 +nttmode=1 +fill=0

echo "########## F. Canonical fill (share1=0, coeffs < q) ##########"
run patched   canon       +maskseed=42 +dataseed=0xDEADBEEF +masking=1 +shuffle=1 +nttmode=1 +fill=1
run patched   canon_m2    +maskseed=9999 +dataseed=0xDEADBEEF +masking=1 +shuffle=1 +nttmode=1 +fill=1
run patched   canon_nosh  +maskseed=42 +dataseed=0xDEADBEEF +masking=1 +shuffle=0 +nttmode=1 +fill=1
run patched   canon_fwd   +maskseed=42 +dataseed=0xDEADBEEF +masking=1 +shuffle=1 +nttmode=0 +fill=1
run stock     canon_stock +maskseed=42 +dataseed=0xDEADBEEF +masking=1 +shuffle=1 +nttmode=1 +fill=1
run datadelay canon_dd    +maskseed=42 +dataseed=0xDEADBEEF +masking=1 +shuffle=1 +nttmode=1 +fill=1
# canonical input, pre-transform dump, for reference comparison
"$BD/obj_patched/Vntt_wrapper" +maskseed=42 +dataseed=0xDEADBEEF +masking=1 +shuffle=1 +nttmode=1 \
   +fill=1 +predump=pre_canon.txt +dump=d_canon_dup.txt 2>&1 | grep -v 'In ram' | sed 's/^/[canon_pre] /'
echo "########## matrix complete ##########"
