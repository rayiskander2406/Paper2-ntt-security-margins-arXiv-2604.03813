# Manuscript v2.23 — SENT_TO_KHALED 2026-04-17

**Status:** SENT_TO_KHALED — sent on 2026-04-17 for sanity-check + arXiv v2 upload. See `../../correspondence/khaled/2026-04-17_sent_v2.23/`.

**Maps to:** planned arXiv v2

## What's in this cut (vs. v2.20 / Khaled's polish base)

Per the cover email (see `../../correspondence/khaled/2026-04-17_sent_v2.23/cover_email.md`), four changes on top of Khaled's v2.20:

1. **Title hyphenation + acronym** — "Post Quantum Cryptography" → "Post-Quantum Cryptography (PQC)". Applied to title, keywords line, and one body occurrence in §1.
2. **New "Code and Data Availability" section** between Conclusion and References. Points to GitHub repo + Zenodo DOI 10.5281/zenodo.19508454. Cross-references companion Paper 1's Zenodo at 10.5281/zenodo.19625392.
3. **Reference [34] updated** — was "Manuscript under preparation" for the companion Structural Dependency Analysis paper; now cites arXiv:2604.15249 (since Paper 1 was posted to arXiv 2026-04-17).
4. **Three orphaned floats given in-text citations** — Figure 1, Table 3, Table 5 had no in-text reference in v2.20. Added a short mention for each.

## Files

| File | Purpose |
|---|---|
| `source.md` | Markdown source |
| `camera_ready_fully_dynamic.docx` | Pandoc + cite-harden output (this is what Khaled received) |
| `media/image1.png`, `image2.png` | Figures |

## Note on Section 1 stale citation cache

Per cover email: in-text citations in Section 1 still showed stale cached numbers ([4], [5], [6]) for Karabulut, Saarinen, and the companion paper. In the current bibliography those three sit at [22], [24], and [34] respectively. Khaled was instructed to click **References → Update Citations and Bibliography** in Word to re-render — fixing the display before upload.
