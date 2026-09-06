#!/bin/bash
# Launch the full deterministic sweep in the background (16 single-threaded workers).
# Only run AFTER the verification gate passes.
set -u
cd "$(dirname "$0")"
LOG=sweep.log
echo "sweep launch: $(date '+%F %T')" | tee -a "$LOG"
nohup python3 rederive.py sweep --manifest manifest.json --out results.jsonl --workers 16 \
  >> "$LOG" 2>&1 &
echo "sweep PID=$! (results.jsonl grows incrementally; tail -f $LOG)"
