# Changes — arXiv v1 → v2

This is the set of changes applied on top of `PAPER_v2.20_FINAL-KK.docx` (the state corresponding to arXiv v1) to produce the v2.23 manuscript uploaded as arXiv v2. Content changes only — no methodology, results, or reference-set changes.

## 1. Title hyphenation and acronym

"Post Quantum Cryptography" → "Post-Quantum Cryptography (PQC)"

Rationale: matches NIST/IACR standard spelling; improves Google Scholar and Semantic Scholar indexing; aligns with the title of the companion paper (arXiv:2604.15249). Normalization also applied to the keywords line and the body occurrence in Section 1.

## 2. New "Code and Data Availability" section

Inserted immediately before References. Contents:

- GitHub repository URL for this paper's artifacts.
- Zenodo archival DOI for this paper: `10.5281/zenodo.19508454`.
- Cross-reference to the companion paper's Zenodo DOI: `10.5281/zenodo.19625392`.

## 3. Reference [34] updated

The companion paper "Structural Dependency Analysis for Masked NTT Hardware" (Iskander & Kirah) went live on arXiv 2026-04-17 as `arXiv:2604.15249`, so reference [34] moved from a "Manuscript under preparation" placeholder to the arXiv citation. Applied to both the dynamic citation source and the rendered bibliography.

## 4. Three orphaned floats given in-text citations

Figure 1, Table 3, and Table 5 had no in-text reference in v2.20. v2.23 adds one short sentence each:

- **§4.7 opener:** ends "…*in several key assumptions, summarized in Table 3*".
- **Figure 1 lead-in:** "*Figure 1 renders this decomposition as a waterfall, making explicit which CPA assumption each SASCA mechanism invalidates,*".
- **§4.8 experiment list:** "*The validation comprises nine experiments (summarized in Table 5), each targeting a specific link…*".

No other floats needed attention.

## Non-changes (explicit)

- **Methodology:** identical to v1.
- **Numerical results:** identical (all margins, SNR×N thresholds, MI amp factors, ablation outcomes, brute-force counts).
- **Reference set membership:** identical (34 references, same papers).
- **Figures and tables (other than attachment to text):** identical content.
- **Abstract scientific claims:** identical; only minor wording for FIPS 203/204 explicitness.
