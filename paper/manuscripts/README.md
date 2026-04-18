# Internal manuscript versions — Paper 2

| Version | Date | Status | Sent to | Mapped to arXiv | Key changes |
|---|---|---|---|---|---|
| v2.19 | 2026-04-17 08:47 | INTERMEDIATE | — | — | Working draft (pre-Khaled-polish base for rebasing) |
| v2.20 | 2026-04-17 08:56 | KHALED_BASE | — | — | Rebased onto Khaled's PAPER_v2.20_FINAL-KK.docx polish |
| v2.21 | 2026-04-17 09:10 | INTERMEDIATE | — | — | Wrong-base near-miss (see project memory `wrong-base-version-filename-trust.md`) |
| v2.22 | 2026-04-17 09:36 | INTERMEDIATE | — | — | Missing orphan-fixes — discarded |
| **v2.23** | **2026-04-17 10:33** | **SENT_TO_KHALED** | **planned arXiv v2** | Title PQC acronym, Code & Data Availability section, ref [34] = arXiv:2604.15249, 3 in-text citations for orphaned Figure 1 + Table 3 + Table 5 |
| v2.24 | 2026-04-17 14:12 | INTERNAL_ITER | — | — | Post-send internal iteration |
| v2.25 | 2026-04-17 14:27 | INTERNAL_ITER | — | — | Post-send internal iteration |
| v2.26 | 2026-04-18 00:49 | CURRENT | — | — | Latest internal cut |

## Why so many versions in one day

v2.19→v2.23 is the prep cycle for the arXiv v2 replacement (sent to Khaled at v2.23). v2.24-v2.26 are post-send refinements while waiting for Khaled's upload — these are NOT what Khaled has, so they should not be uploaded as arXiv v2. Either send Khaled an updated docx (and update `correspondence/khaled/`) or wait for him to upload v2.23 and apply v2.24+ changes in arXiv v3.

## Bump workflow

```bash
cd paper/manuscripts
cp -r v2.26 v2.27
# edit v2.27/source.md
# (build pipeline TODO — currently produced manually)
```

See Paper 3's `paper/manuscripts/README.md` for the canonical workflow.
