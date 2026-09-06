#!/usr/bin/env python3
"""Rebuild evidence/rtl_leakage_acquisition.json from the archived RTL trace sets (content digests, not name lists).

The per-run binaries of the section 4.8.4 acquisition (Verilator harness experiments/rtl/patch-validation/sim_tvla.cpp, original-stimulus arm)
live in the companion QANARY evidence tree, not in this repository. This builder walks that tree, checks every run file has the declared
geometry (32-byte header + 595 records x 28 bytes = 16,692 bytes), hashes every file, and writes one digest per set over the sorted
"name sha256" lines, so a reader holding the companion tree can verify the exact bytes the manuscript's 10,000 + 10,000 statement rests on.
Usage: python3 paper/arxiv/v3_correction_evidence/build_rtl_leakage_manifest.py [companion_root]   (default ~/qanary/evidence/experiments/rtl_leakage)
"""
import hashlib, json, pathlib, sys
REPO = pathlib.Path(__file__).resolve().parents[3]
ROOT = pathlib.Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else pathlib.Path("~/qanary/evidence/experiments/rtl_leakage").expanduser()
HEADER, RECORD, CYCLES = 32, 28, 595
sets = {}
for name in ("fixed", "random"):
    files = sorted((ROOT / name).glob("run_*.bin")); assert len(files) == 10000, (name, len(files))
    lines, sizes = [], set()
    for f in files:
        b = f.read_bytes(); sizes.add(len(b)); lines.append(f"{f.name} {hashlib.sha256(b).hexdigest()}")
    assert sizes == {HEADER + CYCLES * RECORD}, (name, sizes)
    sets[name] = {"runs": len(files), "bytes_per_run": HEADER + CYCLES * RECORD, "first": files[0].name, "last": files[-1].name,
                  "content_sha256": hashlib.sha256(("\n".join(lines) + "\n").encode()).hexdigest()}
assert sets["fixed"]["content_sha256"] != sets["random"]["content_sha256"]
out = {
    "description": "Acquisition record for the RTL TVLA/SNR trace sets of section 4.8.4 (Verilator harness experiments/rtl/patch-validation/sim_tvla.cpp; original-stimulus arm). The per-run binaries are archived in the companion QANARY evidence tree, not in this repository.",
    "companion_path": "qanary/evidence/experiments/rtl_leakage/{fixed,random}/run_NNNN.bin",
    "digest_method": "per set: sha256 over the sorted lines '<file name> <sha256 of the file bytes>\\n' (rebuild with build_rtl_leakage_manifest.py)",
    "header_bytes": HEADER, "record_bytes": RECORD, "cycles_per_run": CYCLES, "masked_end_cycle": 345,
    "fixed_runs": sets["fixed"]["runs"], "fixed_content_sha256": sets["fixed"]["content_sha256"],
    "random_runs": sets["random"]["runs"], "random_content_sha256": sets["random"]["content_sha256"],
    "total_traces": sets["fixed"]["runs"] + sets["random"]["runs"], "bytes_per_run": HEADER + CYCLES * RECORD,
    "analysis_sets_reported": [1000, 10000],
}
dest = REPO / "evidence/rtl_leakage_acquisition.json"; dest.write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=2)); print("wrote", dest.relative_to(REPO))
