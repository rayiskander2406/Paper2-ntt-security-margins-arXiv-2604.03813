# arXiv v2 Metadata — as submitted

**arXiv ID:** 2604.03813
**Version:** v2
**URL:** https://arxiv.org/abs/2604.03813v2
**Uploaded:** 2026-04-20 (by Khaled Kirah)
**Moderation complete / publicly live:** 2026-04-21
**Categories:** cs.CR
**Source manuscript:** `../../manuscripts/v2.23/` (git tag `paper-v2.23`, SHA `b69b06dd`)

## Title

Partial Number Theoretic Transform Masking in Post-Quantum Cryptography (PQC) Hardware: A Security Margin Analysis

## Authors

Ray Iskander (Verdict Security) — lead
Khaled Kirah (Faculty of Engineering, Ain Shams University, Cairo, Egypt) — corresponding (`khaled.kirah@eng.asu.edu.eg`)

## Abstract (as submitted)

Adams Bridge, a hardware accelerator for ML-DSA and ML-KEM designed for the Caliptra root of trust, masks 1 of its Inverse Number Theoretic Transform (INTT) layers and relies on shuffling for the remainder, claiming per-butterfly Correlation Power Analysis (CPA) complexities of 2^46 (ML-DSA) and 2^96 (ML-KEM). We evaluate these claims against published side-channel literature across seven analysis tracks with confidence-rated evidence. Register-Transfer Level (RTL) analysis confirms that the design's Random Start Index (RSI) shuffling provides 6 bits of entropy per layer (64 orderings) rather than the 296 bits of a full random permutation assumed in its scaling argument, with effective margins below the designers' estimates. A soft-analytical attack pipeline demonstrates a 37-bit enumeration reduction, independent of Belief Propagation (BP) gains, quantifying the attack-model gap without achieving key recovery. Full-scale BP on the complete INTT factor graph achieves 100% coefficient recovery over the single-layer baseline, resolving whether BP gains scale to production-size Number Theoretic Transform (NTT) structures. A genie-aided information-theoretic bound shows observations contain sufficient mutual information for full recovery at SNR×N as low as 15. Layer-ablation analysis identifies four necessary conditions governing BP convergence. Observation topology, not count, determines recovery: 4 evenly spread layers achieve 100% while 4 consecutive layers achieve 0%, yielding a practical countermeasure design tool. Strategic masking of 3 consecutive mid-layers (43% overhead vs. full masking) creates an unrecoverable gap that defeats soft-analytical attacks. We contribute a reusable security margin audit methodology combining RTL verification, epistemic confidence tagging, sensitivity-scenario analysis, and experimental validation applicable to any partially masked NTT accelerator.

## Comments field (as submitted)

> v2: added Zenodo artifact DOI (10.5281/zenodo.19508454); minor abstract revision to reference FIPS 203/204 explicitly; resolved artifact-repository URL placeholder in the Code and Data Availability section. No changes to the methodology, results, or references.

## Keywords

Adams Bridge, Post-Quantum Cryptography, Number Theoretic Transform, Side Channel Analysis, Boolean Masking, Shuffling, ML-DSA, ML-KEM, Security Margins, Belief Propagation

## Zenodo companion

- **Paper 2 concept DOI (this paper):** [10.5281/zenodo.19508454](https://doi.org/10.5281/zenodo.19508454)
- **Paper 1 concept DOI (cited in §Code and Data Availability):** [10.5281/zenodo.19625392](https://doi.org/10.5281/zenodo.19625392)
