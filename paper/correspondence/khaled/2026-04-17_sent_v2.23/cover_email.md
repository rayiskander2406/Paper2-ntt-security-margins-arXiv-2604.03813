# Email to Khaled — Paper 2 arXiv v2 Replacement

**To:** Khaled Kirah
**From:** Ray Iskander
**Date:** 2026-04-17
**Attachment:** `2604.03813- PAPER_v2.23_FINAL-Dynamic.docx`

---

**Subject:** Paper 2 arXiv v2 replacement — ready for your sanity check and upload

Dear Khaled,

I've prepared the v2 replacement for our arXiv submission 2604.03813 ("Partial NTT Masking in PQC Hardware: A Security Margin Analysis"), built on top of your `PAPER_v2.20_FINAL-KK.docx` so all of your polish (correspondence marker, sixth contribution, section-heading periods, G18 formatting cleanup, renumbered bibliography) is preserved. The docx is attached: `2604.03813- PAPER_v2.23_FINAL-Dynamic.docx`.

**Four changes on top of your v2.20 submission:**

1. **Title hyphenation and acronym.** "Post Quantum Cryptography" → "Post-Quantum Cryptography (PQC)". This matches the standard NIST/IACR spelling, improves Scholar and Semantic Scholar indexing, and aligns with the title of our companion paper already on arXiv. The same normalization is applied to the keywords line and to the one body occurrence in Section 1.

2. **New "Code and Data Availability" section** inserted just before References. It points to the GitHub repository and to the newly-minted Zenodo archival DOI for this paper (10.5281/zenodo.19508454), and briefly cross-references the companion paper's Zenodo DOI.

3. **Reference [34] updated.** Our companion paper, "Structural Dependency Analysis for Masked NTT Hardware," was posted to arXiv on April 17 (arXiv:2604.15249), so reference [34] has been updated from "Manuscript under preparation" to the arXiv citation. The update was applied to both the dynamic citation source and the rendered bibliography.

4. **Three orphaned floats given in-text citations.** Figure 1, Table 3, and Table 5 had no in-text reference in v2.20 — I added a short mention for each at the natural point in the surrounding prose. Specifically: (a) §4.7 opener now ends "...*in several key assumptions, summarized in Table 3*"; (b) a one-sentence lead-in, "*Figure 1 renders this decomposition as a waterfall, making explicit which CPA assumption each SASCA mechanism invalidates,*" now introduces the figure; (c) §4.8 experiment list now reads "*The validation comprises nine experiments (summarized in Table 5), each targeting a specific link...*". No other floats needed attention.

**One thing I noticed while preparing this** — the in-text citations in Section 1 still show stale cached numbers ([4], [5], [6]) for Karabulut, Saarinen, and our companion paper. In the current bibliography those three actually sit at [22], [24], and [34] respectively, so [6] as-displayed now points to Ishai/Sahai/Wagner, which is a different paper. This is purely a cache-refresh issue — the underlying citation-source tags are correct — and clicking **Update Citations and Bibliography** in step 2 below rewrites every in-text citation to match the current bibliography. Worth a quick scan of Section 1 after the refresh just to confirm the numbers look right.

**Three asks:**

1. **Sanity-check.** Please skim the title, keywords, the single body occurrence of the phrase in Section 1, the new Code and Data Availability section (immediately before References), and reference [34].

2. **Refresh citations in Word** (important for this version). Open the docx, go to the **References** tab, and click **Update Citations and Bibliography**. This will re-render every in-text citation against the renumbered bibliography — fixing the stale [4]/[5]/[6] display in Section 1 as well as the [34] refresh. Scan Section 1 after the refresh to confirm the numbers make sense.

3. **Upload as arXiv v2.** When you're satisfied, please submit the docx as a replacement on arXiv 2604.03813.

Happy to make any adjustments before you upload — just let me know.

Best,
Ray
