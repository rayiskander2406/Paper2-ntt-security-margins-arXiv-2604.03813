# arXiv v2 — published 2026-04-21

**arXiv URL:** https://arxiv.org/abs/2604.03813v2
**Uploaded:** 2026-04-20 (by Khaled Kirah, after iterating the send-ready docx on his side with 0 paragraph-level content changes)
**Publicly live:** 2026-04-21
**Source manuscript:** `../../manuscripts/v2.23/` (git tag `paper-v2.23`, SHA `b69b06dd`)

## Files (frozen)

| File | SHA-256 (first 16) | Purpose |
|---|---|---|
| `manuscript.docx` | `c4864c69dc614368…` | FROZEN — source copy of `manuscripts/v2.23/camera_ready_fully_dynamic.docx` as submitted to arXiv |
| `manuscript.docx.ots` | — | OpenTimestamps proof of the docx bytes (Bitcoin, pending confirmation) |
| `manuscript.pdf` | `a85247fbbfb562e5…` | arXiv-rendered v2 PDF (downloaded from arxiv.org after moderation cleared) |
| `manuscript.pdf.ots` | — | OpenTimestamps proof of the rendered PDF (Bitcoin, pending confirmation) |
| `source.md` | — | Markdown source for v2.23 — the last full-stack cut of the manuscript |
| `arxiv_metadata.md` | — | Title / abstract / Comments / keywords as submitted to arXiv |
| `CHANGES.md` | — | Content diff against arXiv v1 (four items) |
| `build_sha.txt` | — | Git SHA of the manuscript source at build time |

## Summary of v2 changes vs v1

See `CHANGES.md` for full detail. Four items:

1. Title: "Post Quantum Cryptography" → "Post-Quantum Cryptography (PQC)".
2. New "Code and Data Availability" section (Zenodo 10.5281/zenodo.19508454 + cross-ref to Paper 1 Zenodo 10.5281/zenodo.19625392).
3. Reference [34] updated from placeholder to `arXiv:2604.15249` (Paper 1 companion, posted 2026-04-17).
4. Three orphaned floats (Figure 1, Table 3, Table 5) given in-text citations.

No changes to methodology, numerical results, or reference-set membership.

## Deferred debt — bibliography hygiene

Between v2.23 (what's on arXiv) and v2.26 (current internal latest), 66 body citation numerals swapped due to a bibliography re-sort into **first-appearance order**. v2.23 renders the bibliography in a non-first-appearance order inherited from the Word native reference manager:

- Self-reference to the companion paper (Iskander & Kirah Paper 1, Zenodo 19625392) sits at slot **[34]** (the very last slot) in the arXiv v2 bibliography. In v2.26 it is at slot [6] — closer to where the reader expects it given narrative order.
- Adams Bridge, Karabulut CPA, Saarinen TVLA, CHIPS Alliance RTL — all shifted earlier in v2.26. Corresponding in-text numerals jump non-monotonically in v2.23 (e.g., first-cited-in-body references don't appear in the lowest bibliography slots).

**Why this was deferred:** arXiv PDFs are immutable, so a later bib-swap-class incident (as occurred with Paper 3 v1.3 → v1.4) can't hit a reader of the frozen arXiv v2. The bib-hygiene fix is cosmetic and doesn't affect any numerical claim, methodology, or reference membership. Submitting a v3 solely for bibliography re-ordering would invite "what changed?" scrutiny that's awkward to answer when the answer is "nothing scientific."

**Pickup condition:** if/when a substantive reason arises to replace arXiv v2 (new results, Khaled edit pass, venue prep, reviewer request), fold the v2.26 bib-order fix into that v3. Track v2.26 as the starting point for the next replacement.

## Source-authoring history

Khaled iterated the send-ready docx between receipt (2026-04-17) and upload (2026-04-20); local iteration filenames visible on his side: `v2_for_Khaled_2026-04-17` → `v4_for_Khaled_2026-04-17`. Paragraph-level diff (after typographic normalization): **0 content changes**. The size delta is Word save-cycle metadata.

Post-send, `Paper2` internal iterations v2.24 / v2.25 / v2.26 were cut as docx-only (no `source.md`) refinements — these are NOT what Khaled has and NOT what went to arXiv. v2.26 captures the bib-hygiene fix described above.

## Zenodo

Paper 2's Zenodo concept DOI `10.5281/zenodo.19508454` was minted 2026-04-17 alongside v1.0.0 of the Paper 2 artifact code. The v2 change (item 2 above) added an in-text reference to this DOI. No new Zenodo mint is required or occurring.
