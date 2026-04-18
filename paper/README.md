# Paper 2 — Partial NTT Masking: A Security Margin Analysis

**Title:** Partial Number Theoretic Transform Masking in Post-Quantum Cryptography (PQC) Hardware: A Security Margin Analysis

**arXiv:** [2604.03813](https://arxiv.org/abs/2604.03813) (v1 live; v2 replacement pending — see `arxiv/v2/`)

**Zenodo:** concept DOI [10.5281/zenodo.19508454](https://doi.org/10.5281/zenodo.19508454)

**Authors:** Ray Iskander, Khaled Kirah

**Status:** on-arxiv (v1 live; v2 prepared as v2.23, awaiting Khaled's sanity-check + upload — see `correspondence/khaled/2026-04-17_sent_v2.23/`)

## Version map (manuscript ↔ arXiv)

| Manuscript | Date | Status | Mapped to arXiv | Notes |
|---|---|---|---|---|
| v1.x (TBD) | TBD | published | arXiv v1 | Original arXiv submission. Manuscript bytes need recovery; see `arxiv/v1/README.md` |
| v2.19 | 2026-04-17 08:47 | INTERMEDIATE | — | Working draft (pre-Khaled-polish base) |
| v2.20 | 2026-04-17 08:56 | KHALED_BASE | — | Per cover note: "your `PAPER_v2.20_FINAL-KK.docx`" — rebased onto Khaled's polish |
| v2.21 | 2026-04-17 09:10 | INTERMEDIATE | — | Wrong-base near-miss (per memory `wrong-base-version-filename-trust.md`) |
| v2.22 | 2026-04-17 09:36 | INTERMEDIATE | — | Missing orphan-fixes — discarded |
| **v2.23** | **2026-04-17 10:33** | **SENT_TO_KHALED** | **planned arXiv v2** | Title PQC acronym + Code & Data Availability + ref [34] update + 3 orphan-fix in-text citations. **Sent to Khaled 2026-04-17 for sanity-check + upload** |
| v2.24 | 2026-04-17 14:12 | INTERNAL_ITER | — | Post-send internal iteration |
| v2.25 | 2026-04-17 14:27 | INTERNAL_ITER | — | Post-send internal iteration |
| v2.26 | 2026-04-18 00:49 | CURRENT | — | Latest internal cut |

## arXiv

- **v1** — published. Bytes recovery TODO (see `arxiv/v1/README.md`).
- **v2** — pending upload. Send-ready cut is `manuscripts/v2.23/camera_ready_fully_dynamic.docx`. Once Khaled uploads, freeze that exact docx into `arxiv/v2/manuscript.docx` with metadata.

## Layout

```
paper/
├── README.md                            this file
├── arxiv/
│   ├── README.md                        which arXiv version is current
│   ├── v1/                              FROZEN exact bytes of v1 upload (TODO: recover)
│   └── v2/                              pending upload — populate once Khaled uploads
├── manuscripts/                         all internal cuts
│   ├── README.md
│   ├── v2.19/, v2.20/, v2.21/, v2.22/   intermediate
│   ├── v2.23/                           ← SENT_TO_KHALED
│   ├── v2.24/, v2.25/, v2.26/           post-send internal iteration
│   └── ...
├── correspondence/
│   ├── README.md
│   └── khaled/
│       ├── README.md
│       └── 2026-04-17_sent_v2.23/       cover_email + frozen attachment + STATUS=PENDING
├── build/                               build pipeline (TODO: extract from elsewhere)
└── tex/                                 LaTeX backup (TBD)
```

## Co-existence with the existing repo structure

This repo also contains the **research artifact** at the root (`evidence/`, `experiments/`, `proofs/`, `src/`, `tests/`, `reproduce.py`) for Zenodo deposit `10.5281/zenodo.19508454`. The new `paper/` subtree sits alongside without disturbing any of that.

## TODO

- **arxiv/v1/**: recover exact bytes of the v1 upload from arXiv source download or local backup
- **build/**: pull a build_camera_ready.py + build_bibliography.py + cite_harden invocation matching Paper 3's pattern; or document the manual workflow that produced v2.23
- **tex/**: LaTeX backup if maintained
- After Khaled uploads v2: snapshot v2.23 docx into `arxiv/v2/manuscript.docx` + write `arxiv/v2/{README,arxiv_metadata,CHANGES,build_sha}.md/.txt`

## Standing rules

See `~/qanary/papers/registry.yaml` and `~/.claude/projects/-Users-rayiskander-qanary/memory/no-desktop-storage-version-control.md`.
