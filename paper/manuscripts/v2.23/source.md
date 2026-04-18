# Partial Number Theoretic Transform Masking in Post-Quantum Cryptography (PQC) Hardware: A Security Margin Analysis

Ray Iskander^1^, Khaled Kirah^2,\*^

^1^Verdict Security

^2^ Faculty of Engineering, Ain Shams University, Cairo, Egypt

**Keywords:** Adams Bridge, Post-Quantum Cryptography, Number Theoretic Transform, Side Channel Analysis, Boolean Masking, Shuffling, ML-DSA, ML-KEM, Security Margins, Belief Propagation,

## Abstract

Adams Bridge, a hardware accelerator for ML-DSA and ML-KEM designed for the Caliptra root of trust, masks 1 of its Inverse Number Theoretic Transform (INTT) layers and relies on shuffling for the remainder, claiming per-butterfly Correlation Power Analysis (CPA) complexities of 2\^46 (ML-DSA) and 2\^96 (ML-KEM). We evaluate these claims against published side-channel literature across seven analysis tracks with confidence-rated evidence. Register-Transfer Level (RTL) analysis confirms that the design\'s Random Start Index (RSI) shuffling provides 6 bits of entropy per layer (64 orderings) rather than the 296 bits of a full random permutation assumed in its scaling argument, with effective margins below the designers\' estimates. A soft-analytical attack pipeline demonstrates a 37-bit enumeration reduction, independent of Belief Propagation (BP) gains, quantifying the attack-model gap without achieving key recovery. Full-scale BP on the complete INTT factor graph achieves 100% coefficient recovery over the single-layer baseline, resolving whether BP gains scale to production-size Number Theoretic Transform (NTT) structures. A genie-aided information-theoretic bound shows observations contain sufficient mutual information for full recovery at SNRxN as low as 15. Layer-ablation analysis identifies four necessary conditions governing BP convergence. Observation topology, not count, determines recovery: 4 evenly spread layers achieve 100% while 4 consecutive layers achieve 0%, yielding a practical countermeasure design tool. Strategic masking of 3 consecutive mid-layers (43% overhead vs. full masking) creates an unrecoverable gap that defeats soft-analytical attacks. We contribute a reusable security margin audit methodology combining RTL verification, epistemic confidence tagging, sensitivity-scenario analysis, and experimental validation applicable to any partially masked NTT accelerator.

## 1. Introduction {#introduction-1}

The standardization of FIPS 203 (ML-KEM) \[1\] and FIPS 204 (ML-DSA) \[2\] in 2024, coupled with their adoption in security-critical silicon roots of trust, has made the side-channel security of lattice-based Number Theoretic Transform (NTT) accelerators a first-order deployment concern. As these algorithms move from specification to silicon, hardware designers face a fundamental tradeoff: the NTT, the performance-critical polynomial multiplication at the heart of both standards, requires side-channel protection. However, fully masking all NTT operations incurs significant silicon area overhead. Partial masking, in which only selected operations are protected with Boolean masking while remaining operations rely on alternative countermeasures such as shuffling, has emerged as a pragmatic engineering response to this tension.

Adams Bridge \[3\] is a prominent example of this design pattern. Developed for integration into the Caliptra silicon root of trust, an open-source hardware security framework backed by AMD, Google,

Microsoft, and NVIDIA, the accelerator implements first-order Boolean masking on the first INTT layer and point-wise multiplication, while relying on shuffling and searching space arguments for the remaining NTT layers. The designers present a security analysis arguing that the per-butterfly CPA complexity of the unmasked layers, $2^{96}$ for ML-KEM and$\ 2^{46}$ for ML-DSA, combined with shuffling that compounds multiplicatively across layers, renders side-channel exploitation "entirely impractical" \[3\].

This paper evaluates those claimed security margins against published side-channel literature. This evaluation joins two prior independent published analyses; empirical CPA \[4\], TVLA leakage detection \[5\], and preliminary formal structural verification \[6\], all converging on the same architectural concern (section 5.1). We question whether partial NTT masking provides adequate security is not unique to Adams Bridge, it is a recurring design decision across Post-Quantum Cryptography (PQC) hardware implementations. If the claimed margins are accurate, partial masking offers a valuable area-security tradeoff. If they are optimistic, designers and certification bodies risk underinvesting in masking for a class of hardware that will protect critical infrastructure for decades. In either case, the community benefits from a structured, evidence-rated evaluation of the margins.

This analysis does not demonstrate key recovery or present new attacks. It evaluates whether the claimed security margins for partially masked NTT hardware withstand scrutiny from established side-channel literature. We present evidence both supporting and challenging the partial masking strategy by tagging every claim with an epistemic confidence level (Proven, Literature-Supported, Extrapolation, or Speculative) and by Software/Hardware (SW/HW) indicating whether the underlying result was obtained on software or hardware platforms. Significant open questions are acknowledged, including the designers' first-order TVLA pass under their measurement setup and the absence of any published Soft Analytical Side-Channel Attacks (SASCA) attack on hardware NTT implementations with countermeasures enabled, which constitutes the strongest argument for the defense.

We consider a non-profiled attacker with physical access to a device containing the Adams Bridge accelerator, capable of collecting power consumption traces during NTT/INTT operations with no a priori limit on the number of traces. The attacker does not have profiling access to an identical device (profiled attacks are discussed separately in section 4.6 and excluded from the margin synthesis). The target deployment context is a silicon root of trust within a system-on-chip (SoC), where power delivery network filtering and parallel computation introduce hardware-specific noise. All margin bounds in section 4.7 are derived under this non-profiled model. For the empirical validation in section 4.8, we additionally consider a profiled attacker who exploits the publicly available RTL source code \[7\] to construct Hamming distance templates; trace acquisition at rates typical of EM probing (\~100 traces/minute) would require approximately 10 minutes for the \~1,000 traces our pipeline requires. We emphasize that this profiled model represents an optimistic upper bound: a real attacker faces template estimation error, measurement misalignment, and hardware-specific noise not captured by the circular Gaussian observation model, all of which would degrade the effective MI (section 5.3, G1--G3).

This paper features the following six contributions:

1.  *Structured evidence evaluation.* We compile and confidence-rate evidence from over 30 published papers both supporting and challenging partial NTT masking, with explicit SW/HW provenance on every claim. Pro-defender evidence is presented first in section 4.1 to ensure academic balance.

2.  *Security margin analysis.* We derive literature-supported bounds on the effective CPA search space for Adams Bridge's unmasked INTT layers across four scenarios spanning pro-attacker to pro-defender assumptions. Under the strongest literature-supported pro-defender assumptions (Scenario B), the effective margins fall in the range $2^{59}$--$2^{63}$ (ML-DSA) and $2^{61}$--$2^{65}$ (ML-KEM), roughly $2^{25}$--$2^{29}$ and $2^{67}$--$2^{71}$ below the designers' implied estimates of $\approx 2^{88}$ and $\approx 2^{132}$, respectively. A mixed-assumption estimate yields $2^{32}$--$2^{42}$ (ML-DSA) and $2^{35}$--$2^{45}$ (ML-KEM), though these composite figures carry epistemic uncertainty from combining independent results. All four scenarios, with their explicit assumptions, are detailed in section 4.7.

3.  *Random Start Index shuffling characterization.* We confirm from the publicly available RTL source code \[7\] that Adams Bridge implements RSI shuffling, producing 64 combined orderings with 6 bits of entropy per layer through a dual-level hierarchy (chunk-level RSI with 16 starting positions × index-within-chunk factor of 4), rather than the full random permutation ($64! \approx 2^{296}$ orderings) assumed in the design's $S^{L}$ scaling argument.

4.  *Security Margin Audit methodology.* We propose a reusable framework for evaluating partial-countermeasure designs: (i) exhaustive RTL verification of claimed mechanisms against gate-level implementation, (ii) SW/HW provenance on every evidence item (iii) explicit sensitivity scenarios that isolate each modeling assumption. This methodology can be applied to any partially masked NTT accelerator or shuffling-based lattice implementation without requiring new attacks or hardware measurements.

5.  *Empirical validation pipeline.* We develop a SASCA attack pipeline grounded in RTL-simulated leakage (section 4.8), comprising factor graph construction, lattice sensitivity analysis, RSI shuffling simulation, RTL-level TVLA and SNR extraction, template attack bridging, belief propagation on NTT factor graphs, full-scale Belief Propagation (BP) validation, and composite margin formalization. This pipeline demonstrates a 37-bit attack-model gap (enumeration reduced from $2^{46}$ to $2^{9}$), independent of belief propagation gains, and validates BP on the complete ML-KEM INTT factor graph (896 factors, 2,048 variables), achieving 100% coefficient recovery at SNR$\times$N $= 3,000$ (120 trials, Wilson CIs) with a peak $2.24 \times$ MI amplification factor ($0.30 \times$ normalized efficiency against the 7-layer independent-channel bound, (section 4.8.9), supported by a genie-aided information-theoretic bound, layer-ablation analysis (500+ trials, 44 configurations, exhaustive over all 35 four-layer subsets, revealing four necessary conditions for BP convergence), and convergence dynamics characterization. This extends software-only BP analyses \[8, 9\] and simulated-ASIC SASCA \[1\] to open-source RTL-derived signal-to-noise ratios for a production PQC accelerator.

6.  *Machine-verified algebraic foundations*. The core structural claims underlying the margin analysis, GS butterfly DOF reduction, chain composition bounds, scenario calculations, and gap masking completeness, are machine-verified by multi-theory SMT (Z3 + CVC5 finite field theory; supplementary material), with CVC5 resolving the critical GS butterfly injectivity universally over $\mathbb{F}_{q}$ in under 100 ms where integer arithmetic times out.

The present paper examines whether the unmasked layers receive adequate protection from the alternative countermeasures deployed in their place.[^1]

The paper is organized as follows: Section 2 reviews the technical background on NTT masking, shuffling, algebraic side-channel analysis, and TVLA. Section 3 presents the Adams Bridge architecture and the designers' security claims. Section 4 evaluates these claims across seven literature-based analysis tracks (Sections 4.1--4.7) with confidence-rated evidence and synthesizes security margin bounds. The literature-derived margins are validated through an original SASCA attack pipeline using RTL-simulated leakage in section 4.8, culminating in full-scale BP validation on the complete ML-KEM INTT factor graph in sections 4.8 and 4.9. Finally, section 5 discusses implications, acknowledges limitations, and proposes directions for resolution before concluding in section 6.

## 2. Literature Review

We review the technical foundations needed to follow the evaluation in section 4: NTT structure and masking in hardware (2.1), shuffling countermeasures (2.2), algebraic side-channel analysis (2.3), statistical leakage assessment (2.4), and related work on partial masking designs (2.5).

### 2.1 NTT Structure and Masking in PQC Hardware

The NTT is the performance-critical operation in lattice-based PQC schemes, used for polynomial multiplication in ML-KEM (FIPS 203) \[2\] and ML-DSA (FIPS 204) \[3\]. For $n = 256$ coefficients, ML-KEM requires 7 layers with $q = 3,329$ (12-bit coefficients), while ML-DSA requires 8 NTT/INTT butterfly layers over $\mathbb{Z}_{q}$ with $q = 8,380,417$ (23-bit coefficients).

The Cooley-Tukey (CT) butterfly \[4\] computes $a' = a + b \cdot \omega$ and $b' = a - b \cdot \omega$ for the forward NTT, while the Gentleman-Sande (GS) butterfly \[5\] computes $a' = a + b$ and $b' = (a - b) \cdot \omega^{- 1}$ for the INTT, where $\omega$ is a publicly known twiddle factor. The GS butterfly's algebraic structure is important for section 4.3: given one output and the public twiddle factor $\omega$, the other output is algebraically constrained. In an ideal noiseless model, this reduces the independent unknowns from 2 to 1 ($2^{46} \rightarrow 2^{23}$ for ML-DSA).

First-order Boolean masking splits a sensitive value $x$ into two shares $x_{0},x_{1}$ such that $x = x_{0} \oplus x_{1}$, where $x_{1}$ is drawn uniformly at random. An implementation is $d$-th order secure if any combination of up to $d$ intermediate values is statistically independent of the secret \[6\]. Domain-Oriented Masking (DOM) \[7\] provides a systematic approach to constructing first-order secure gadgets in hardware by processing shares in separate clock-cycle domains with fresh randomness, using pipeline registers to prevent glitch propagation between domains.

Full NTT masking, protecting all butterfly layers with DOM-style gadgets, incurs significant area overhead due to the additional registers, randomness generation, and share-separated data paths required. Partial masking protects only selected operations (typically the first INTT layer and point-wise multiplication) while leaving remaining layers unmasked, relying on alternative countermeasures for the unprotected computation. This tradeoff is the subject of the present paper.

### 2.2 Shuffling as a Side-Channel Countermeasure

Shuffling randomizes the execution order of independent operations, forcing an attacker to resolve the permutation before correlating measurements with hypotheses. For $S$ independently shuffled operations, a full random permutation draws uniformly from $S!$ possible orderings, providing $\log_{2}(S!)$ bits of entropy per execution. It was established \[8\] that full Random Prototyping (RP) increases the data complexity of first-order Correlation Power Analysis (CPA) by a factor of approximately $S^{2}$.

In an alternative implementation, a random starting position $r \in \{ 0,\ldots,S - 1\}$ is selected and operations are sequentially processed with wraparound from position $r.\$This produces only $S$ distinct orderings (versus $S!$ for full RP) with $\log_{2}(S)$ bits of entropy. Adams Bridge employs a dual-level Random Start Index (RSI) hierarchy with an effective $S = 64$ (Section 3.1), yielding 6 bits of entropy per layer versus $\log_{2}(64!) \approx 296$ bits for full RP. Reference \[8\] explicitly warn that RSI variants "can be as easy to attack as unprotected implementations" in certain scenarios, as the sequential structure leaks positional information.

A multiplicative benefit is obtained by combining masking of order $d$ with shuffling of $S$ operations which provides a security amplification of $S^{d + 1}$ \[9\]. This amplification assumes both countermeasures are correctly implemented and co-present; it does not apply to computation phases where only shuffling is active.

### 2.3 Algebraic Side-Channel Analysis

Classical CPA evaluates one target operation at a time, testing hypotheses independently for each intermediate value. Algebraic Side-Channel Analysis (ASCA) and BP attacks exploit the algebraic dependencies between operations, propagating probabilistic ("soft") information through the computation graph.

The factor graph formulation \[10\] was introduced for Soft Analytical Side-Channel Attacks (SASCA), modeling the cryptographic computation as a bipartite graph of variable nodes (intermediate values) and factor nodes (operations). BP iteratively propagates marginal probability distributions through this graph, enabling joint recovery of multiple variables from noisy observations.

The NTT's regular butterfly structure maps naturally to a factor graph: each butterfly is a factor node connecting its input and output variable nodes. Single-trace attacks was demonstrated on masked lattice-based encryption using 213 Hamming weight templates \[11\]. This was extended to more practical single-trace NTT key recovery on ARM Cortex-M4 \[12\]. BP was adapted \[13\] to handle shuffled NTT implementations by introducing shuffle nodes that represent the unknown permutation, demonstrating that BP can jointly resolve both the shuffling order and the secret values.

The per-butterfly CPA model assumes each butterfly is attacked independently with an exponential hypothesis space per butterfly pair. Our analysis differs since SASCA/BP attacks are fundamentally unlike since they process the entire NTT factor graph simultaneously, exploiting inter-butterfly algebraic constraints. This distinction is central to the evaluation in sections 4.3 and 4.5.

### 2.4 Evaluation Methodology: TVLA

Test Vector Leakage Assessment (TVLA) \[14\] is the industry-standard methodology for evaluating side-channel resistance. The fixed-vs-random $t$-test compares power traces from a fixed input against traces from random inputs; a $|t|$-statistic exceeding 4.5 indicates statistically significant leakage with high confidence. TVLA provides a black-box detection methodology that does not require attack-specific hypotheses. However, as was demonstrated \[15\], TVLA has fundamental limitations: a passing result guarantees the absence of detected leakage under the specific test configuration, not the absence of exploitable leakage. The detection threshold depends on the number of traces, the signal-to-noise ratio, and the temporal resolution of the analysis. Leakage concentrated in specific clock cycles may be masked by aggregation over the full execution, and higher-order leakage may evade first-order TVLA.

### 2.5 Related Work on Partial Masking

Partial masking of NTT implementations is not unique to Adams Bridge. The tension between masking coverage and silicon area is a recurring design challenge in PQC hardware. []{dir="rtl"} Masking strategies for lattice-based encryption hardware is analyzed, establishing that even first-order masked NTT implementations leak exploitable information through single-trace template attacks when the masking is incomplete or improperly randomized \[11\]. Demonstrated SASCA on partially masked NTT software implementations showed that unprotected NTT layers serve as entry points for belief propagation attacks \[12\].

A taxonomy of side-channel countermeasures is provided \[16\] for lattice-based schemes, categorizing shuffling, masking, and hiding approaches with their respective area-security tradeoffs. Their analysis highlights that shuffling alone provides limited protection against profiled adversaries, a finding consistent with the RSI analysis in section 4.2. Belief propagation was demonstrated to be able to defeat shuffling countermeasures in NTT implementations \[13\] by jointly resolving the permutation and the secret values, providing the theoretical foundation for the shuffling analysis in section 4.2. More recently, \[1\] SASCA was evaluated on locally masked NTT for ML-KEM, demonstrating successful attacks on designs where only a subset of NTT operations are protected with local (per-operation) masks. Their work on Artix-7 FPGA and simulated 22 nm ASIC traces establishes that partial masking strategies are vulnerable to algebraic attacks even in hardware settings. Our analysis will differ from \[1\] in three respects: (1) we target a deployed production design with publicly available RTL, not a custom implementation; (2) we analyze partial first-layer masking with RSI shuffling rather than local per-operation masking; (3) we develop a composite margin framework rather than demonstrating a complete attack.

On the verification side, formal tools for masking analysis have matured significantly: Barthe et al. (maskVerif) \[17\], Bloem et al. (COCO) \[18\], Gigerl et al.  (Coco-Alma) \[19\], and Knichel et al. (SILVER) \[20\] provide automated or semi-automated methods for verifying masking correctness at the gate level. These tools verify the masked portions of a design; they do not analyze the security margins of unmasked layers relying on alternative countermeasures which is the focus of this paper.

These works collectively establish that partial NTT masking is a known attack surface in the side-channel literature. The present paper contributes a structured margin analysis for a specific, commercially significant design, Adams Bridge, applying the evidence from these and other publications to evaluate the designers' specific security claims.

## 3. Adams Bridge: Architecture and Security Claims

We examine Adams Bridge \[21\], a hardware accelerator for ML-DSA (FIPS 204) and ML-KEM (FIPS 203) designed for integration into the Caliptra silicon root of trust. The accelerator implements a partial masking strategy in which selected operations are protected with Boolean masking while remaining operations rely on shuffling and search space arguments for side-channel resistance. This section presents the architecture and the designers' security claims.

### 3.1 Architecture Overview

Adams Bridge processes NTT and INTT operations for both ML-DSA and ML-KEM. The design comprises 30 synthesizable modules totaling approximately 1.17 million gate-equivalent cells, implementing the Gentleman-Sande butterfly for INTT and the Cooley-Tukey butterfly for NTT. ML-DSA operates over $\mathbb{Z}_{q}$ with $q = 8,380,417$ (23-bit coefficients, 8 NTT layers for $n = 256$), while ML-KEM uses $q = 3,329$ (12-bit coefficients, 7 NTT layers). The first INTT layer is protected with first-order Boolean masking using a DOM style implementation with two shares. After the masked first layer, the two shares are combined into a single unmasked intermediate value before processing continues through subsequent layers (layers 2--8 for ML-DSA, layers 2--7 for ML-KEM). The designers note that "leakage naturally emerges in the unmasked layers" \[21\] (pp. 28).

Adams Bridge also implements a dual-level RSI shuffling countermeasure \[21\] with an effective $S = 64$ orderings per layer. The RTL source, which is publicly available under the Apache 2.0 license, confirms the mechanism (ntt_ctrl.sv, lines 648--653): a chunk-level RSI scheme selects among 16 starting positions within a 16-element chunk, while an index-within-chunk selection provides an additional factor of 4, yielding $16 \times 4 = 64$ combined orderings per layer ($\log_{2}(64) = 6$ bits of entropy). Processing proceeds sequentially with wraparound within each chunk. This RSI structure produces 64 orderings per layer, in contrast to the $64! \approx 2^{296}$ orderings of a full random permutation over the same 64 elements. The Barrett reduction module, used for modular arithmetic, operates on already-combined (unmasked) intermediate values in certain code paths, which has been independently identified as a side-channel vulnerability \[22\].

### 3.2 Security Claims

The designers present a security analysis of the partial masking strategy in their published description of the accelerator \[21\]. We identify five principal claims, reproduced here with page references to enable independent verification.

**C1: ML-DSA per-butterfly CPA complexity is** $2^{46}$ \[pp. 12--13\]. Each Gentleman-Sande butterfly in the unmasked INTT layers processes two 23-bit coefficients. The designers argue that a CPA attacker targeting a single butterfly must guess both input coefficients, yielding a search space of $2^{23} \times 2^{23} = 2^{46}$ hypotheses.

**C2: ML-KEM per-butterfly CPA complexity is** $2^{96}$ \[pp. 12--13\]. For ML-KEM, each butterfly involves coefficients that depend on up to $8 \times 12$-bit values from the preceding NTT layers, yielding a claimed search space of $2^{96}$.

**C3: Shuffling compounds difficulty multiplicatively** \[pp. 13, 28\]. The designers argue that the shuffling countermeasure compounds the CPA difficulty across NTT layers. The implied scaling is $S^{L}$, where $S = 64$ is the effective number of shuffle orderings per layer (Section 3.1) and $L$ is the number of unmasked layers, suggesting a multiplicative factor up to $64^{6} \approx 2^{36}$ for ML-KEM or $64^{7} \approx 2^{42}$ for ML-DSA on top of the per-butterfly complexity. Combined with C1 and C2, these yields implied total security margins of $\approx 2^{88}$ (ML-DSA: $2^{46} \times 64^{7}$) and $\approx 2^{132}$ (ML-KEM: $2^{96} \times 64^{6}$).

**C4: Combined protection renders exploitation "entirely impractical"** \[pp. 28\]. The designers conclude that the combination of first-layer masking, shuffling, and per-butterfly search space "eliminates any realistic attack vector" for non-profiled side-channel analysis. They acknowledge that "leakage naturally emerges in the unmasked layers" but argue that exploiting this leakage is computationally infeasible.

**C5: TVLA validates the implementation** \[Fig. 9(c)\]. The designers present first-order TVLA results at $10^{6}$ traces showing no statistically significant leakage ($|t| < 4.5$) with both masking and shuffling enabled.

### 3.3 Design Context

Two additional elements from the published analysis \[21\] provide context for the evaluation in section 4. First, the designers note a planned expansion of masking to the Barrett reduction module, citing a 24% area saving from the current unmasked implementation. This is consistent with an incremental approach to masking coverage. Next, the TVLA results in C5 are presented for the configuration with both masking and shuffling active. The temporal resolution of the TVLA evaluation, specifically whether leakage in the unmasked INTT layers is detectable when analysis is restricted to those clock cycles, is not reported.

## 4. Systematic Evaluation

We evaluate the security claims in section 3.2 against published side-channel literature and original RTL-derived experiments. The literature-based analysis (sections 4.1 to 4.7) spans seven tracks, each targeting specific claims. We begin with evidence supporting the partial masking strategy (section 4.1) to ensure academic balance. The empirical validation (section 4.8) then chains original RTL-simulated measurements through a SASCA attack pipeline to test whether the literature-derived margins hold when applied to Adams Bridge's specific design parameters.

### 4.1 Evidence Supporting Partial Masking

We start by documenting the arguments that support the designers' position. The following evidence cards represent the defense we could construct from published literature.

**E1: TVLA empirical pass:** (Proven- HW). Adams Bridge passes first-order TVLA at $10^{6}$ traces for both ML-KEM and ML-DSA with masking and shuffling enabled \[21\] (Fig. 9(c)). This is the industry-standard evaluation methodology (ISO/IEC 17825:2024). While TVLA detection "can be totally disconnected from the actual security level" \[15\], a pass at $10^{6}$ traces constitutes legitimate empirical evidence of practical difficulty.

**E2: Hardware noise barrier:** (Literature-Supported- HW/ SW). Published SASCA attacks on NTT require low noise environments: Success rates exceeding 70% only for $\sigma \leq 0.3$ were reported \[1\]. Real hardware introduces clock jitter, power supply noise, and parallel computation interference that attenuate side-channel signals. SoC power delivery networks provide additional RLC filtering \[23\]. No published SASCA attack targets hardware NTT implementations, all demonstrations to date use software on ARM Cortex-M4 platforms.

**E3: Masking-shuffling amplification:** (Literature-Supported- SW). It is established that masking and shuffling provide multiplicative security amplification when correctly combined \[9\]. Adams Bridge deploys both countermeasures for the first INTT layer, so the multiplicative benefit applies in principle for that layer. However*,* this amplification assumes correct masking implementation and does not extend to the unmasked layers where only shuffling is present.

**E4: No published key recovery on protected mode:** (Proven- Fact). As of March 2026, no published paper demonstrates full key recovery from Adams Bridge with countermeasures enabled. Unmasked modular reduction operations were targeted outside the protected mode \[22\]. TVLA leakage was demonstrated but complete key recovery was not reported \[24\]. This is a legitimate "absence of evidence" argument, though absence of evidence is not evidence of absence.

**E5: Hardware shuffling provides practical CPA resistance:** (Literature-Supported- HW). Multiple papers confirm that hardware shuffling with full random permutation provides practical resistance. Reference \[25\] reports measurements-to-disclosure increased by more than $10,000 \times$ on Spartan-6 and reference \[26\] reports no CPA correlation after $10^{5}$ traces on shuffled Kyber on Artix-7. Note that these publications use full random permutation, not Random Start Index as in Adams Bridge (Section 4.2).

**E6: Designers plan incremental masking expansion:** (Proven- designers\' own paper). The designers explicitly note a planned expansion of masking to the Barrett reduction module, citing a 24% area saving from the current unmasked implementation \[21\] \[pp. 25\]. This demonstrates awareness that current partial masking coverage is a deliberate engineering tradeoff with a roadmap toward broader protection, consistent with an incremental approach to masking coverage rather than a final security posture. Conversely, if the per-butterfly complexity arguments ($2^{46}$, $2^{96}$) and shuffling were sufficient to render exploitation "entirely impractical," the area cost of additional masking would be difficult to justify.

### 4.2 Shuffling: RSI vs Full Permutation

Claims C3 and C4 depend on the shuffling countermeasure compounding CPA difficulty across NTT layers. We examine the shuffling mechanism as implemented in RTL.

As described in section 3.1, Adams Bridge implements dual-level RSI shuffling with an effective $S = 64$ orderings per layer, confirmed from RTL source \[27\] (Proven- HW). Table 1 compares this to the full random permutation assumed in the published shuffling literature.

***Table 1.** Comparison of shuffling implementations.*

  --------------------------------------------------------------------------------------------------------------
  **Property**               **Full RP (**$S = 64$**)**     **Adams Bridge RSI (**$S = 64$**)**
  -------------------------- ------------------------------ ----------------------------------------------------
  Possible orderings         $64! \approx 2^{296}$          64

  Entropy per layer          296 bits                       6 bits

  Published security model   $S^{2} = 4,096 \times$ \[8\]   $\leq S^{2}$; potentially $\approx 1 \times$ \[8\]
  --------------------------------------------------------------------------------------------------------------

**RSI provides dramatically less security:** (Literature-Supported- SW, AES). Full permutation is explicitly distinguished from RSI: "Simplified versions of shuffling using random start indexes can be significantly weaker than their counterpart using full permutations... such simplified versions can be as easy to attack as unprotected implementations" \[8\]. The $S^{2} = 4,096 \times$ trace overhead formula applies to full random permutation. For RSI, the overhead may be as low as $1 \times$, effectively no protection, in scenarios where start-index leakage is present or the number of shuffled elements is small enough for enumeration. This result was demonstrated for AES S-boxes; the RSI permutation analysis is operation-agnostic (it derives from information-theoretic properties of permutation distributions), but the quantitative overhead on NTT butterflies has not been experimentally validated.

$\mathbf{S}^{\mathbf{L}}$ **scaling is not supported:** (Literature-Supported- SW). Claim C3 implies shuffling compounds multiplicatively across layers as $S^{L}$. No published security proof confirms multiplicative shuffling compounding across NTT layers. The published model is $S^{2}$ per CPA hypothesis per layer, an additive model in which the attacker processes each layer independently \[8\]. Shuffling alone is "of limited help" against distinguishing attacks, recommending combination with proper masking \[28\].

**Multi-layer RSI entropy does not compound naively:** An RSI shuffling across $L$ unmasked layers produces $S^{L}$ total execution paths (e.g., $64^{7} \approx 2^{42}$ for ML-DSA). However, belief propagation processes the NTT factor graph layer by layer, marginalizing over only $S = 64$ candidates at each stage \[13\]. The combinatorial space of $S^{L}$ paths is therefore never searched jointly, the attacker faces 64 hypotheses per layer, not $2^{42}$ hypotheses globally. This per-layer marginalization assumes the RSI start positions are drawn independently across layers. If the Pseudo-Random Number Generator (PRNG) generating start positions introduces cross-layer correlations, the effective RSI entropy could be lower than $6 \times L$ bits, further weakening the shuffling protection. We have not analyzed the PRNG implementation for cross-layer dependencies. This sequential structure is precisely why the Scenario B model in section 4.7 applies shuffling overhead per-layer ($7 \times S^{2}$) rather than globally ($S^{2L}$), and why Scenario C's $S^{L}$ compounding represents an upper bound that no published attack model requires.

**Belief propagation defeats NTT shuffling:** (Literature-Supported- SW, Kyber). It was demonstrated that belief propagation with shuffle nodes can recover the shuffling permutation jointly with secret values \[13\]. Their evaluation of 16-node sub-graphs shows matching success approaching 100% at $\sigma \leq 0.2$. For coarse block shuffling with random permutation, the full attack succeeds at $\sigma \leq 0.2$. Since Adams Bridge's RSI (64 orderings) is a strict subset of random permutation ($64!$ orderings), the RSI search space provides a mathematical upper bound on shuffling security: the BP marginalization task is reduced or equivalent. The experiments use simulated Hamming weight leakage on software, not hardware traces.

**Brute-force comparison:** (Proven- Mathematical). Un-shuffling the first layer of coarse-block-shuffled Kyber (random permutation) requires up to $2^{16}$ BP runs in the worst case \[13\]. For RSI with $S = 64$, only 64 BP runs are needed per layer, one per possible combined ordering, rendering the shuffling trivially enumerable.

### 4.3 Algebraic Search Space Reduction

Claims C1 and C2 assume per-butterfly CPA complexity of $2^{46}$ (ML-DSA) and $2^{96}$ (ML-KEM). Three lines of evidence suggest these estimates are optimistic.

**GS butterfly linear constraint:** (Literature-Supported; Machine-Verified). The Gentleman-Sande INTT butterfly computes $a' = a + b$ and $b' = (a - b) \cdot \omega^{- 1}\ mod\ q$, where $\omega^{- 1}$ is a public twiddle factor. Given one butterfly output and the public twiddle, the other is algebraically constrained. In an ideal noiseless model, this reduces the independent unknowns from 2 to 1 ($2^{46} \rightarrow 2^{23}$ for ML-DSA). In noisy hardware, the constraint reduces the degrees of freedom to approximately $1.x$ depending on signal-to-noise ratio. This algebraic structure was exploited in the belief propagation attacks on NTT \[11, 12\].

**SIS lattice reduction:** (Literature-Supported- SW). It was demonstrated that only 32 NTT-domain coefficients, not all 256, suffice for full ML-DSA key recovery via BKZ-60 \[29\]. Their parameters ($n = 256$, $q = 8,380,417$, Dilithium-2 = ML-DSA-44) match Adams Bridge. An attacker therefore needs to leak coefficients from approximately 16 butterflies, not 128, reducing the attack surface by $8 \times$. *Caveat:* BKZ-60 lattice reduction is brittle to coefficient errors; at realistic SCA error rates ($\geq 5\%$), the reduction does not merely take longer, it fails entirely or requires substantially larger BKZ block sizes. The effective number of required coefficients may therefore increase well beyond 32 in noisy hardware, pushing the effective margin toward Scenario B in section 4.7. Our lattice sensitivity experiment (Exp B, section 4.8.2) achieves 0% success at 32 coefficients using Babai CVP, succeeding only at 64 coefficients. Additional lattice techniques (BKZ with enumeration/pruning) beyond Babai was employed. Scenario A is therefore contingent on stronger lattice methods; under our weaker solver, the minimum doubles to \~32 butterflies \[29\].

**ML-KEM known-ciphertext reduction:** (Literature-Supported- SW). The Known-Ciphertext Attack (KCA) model for ML-KEM was established during decapsulation \[30\]. The ciphertext is known to the attacker, enabling template attacks on the pair-pointwise multiplication that effectively reduce the independent unknowns in each NTT processing step. This reduction requires the attacker to know the input ciphertext, which is the standard case during ML-KEM decapsulation, the primary attack surface for side-channel exploitation of key-encapsulation mechanisms. Applied to the per-butterfly framing in C2, this reduces the claimed $2^{96}$ search space to approximately $2^{48}$.

**Per-butterfly framing is non-standard: (Proven- Fact).** No published attack uses "CPA complexity per butterfly" as a formal security metric. Published attacks on NTT implementations operate on the full factor graph, exploiting inter-butterfly algebraic dependencies through belief propagation \[11-13\]. The per-butterfly independence assumption is the designers' own construction.

### 4.4 Temporal Exposure Window

Claim C4 characterizes the combined protection as sufficient. We quantify the extent of unmasked computation.

**Masking coverage:** (Proven- HW). The masking_en_ctrl signal is architecturally constrained to the first INTT layer only (ntt_ctrl.sv, line 265). Table 2 summarizes the temporal exposure. Throughout this paper, "layer" refers to one butterfly stage of the NTT/INTT computation (ML-DSA has 8 layers, ML-KEM has 7). The hardware processes multiple layers per pipeline round, but all margin calculations and layer counts refer to NTT layers, not pipeline rounds.

***Table 2.** Unmasked INTT computation in Adams Bridge.*

  -----------------------------------------------------------------------------------
  **Metric**                          **ML-DSA (FIPS 204)**   **ML-KEM (FIPS 203)**
  ----------------------------------- ----------------------- -----------------------
  Total INTT layers                   8                       7

  Masked INTT layers                  1                       1

  Unmasked INTT layers                7 (87.5%)               6 (85.7%)

  Unmasked butterfly operations       896                     768

  Approximate unmasked clock cycles   2,240                   1,344
  -----------------------------------------------------------------------------------

The masked INTT coverage is limited to a single butterfly stage: only stage 1 of the first hardware round (round 0) processes shares in masked form; stage 2 of round 0 operates on already-combined (unmasked) values \[21, 27\]. Additionally, all Point-Wise Multiplication (PWM) operations are fully masked, but PWM is a separate operation and not counted in the INTT layer tally. Each unmasked clock cycle produces side-channel leakage that the designers acknowledge: "leakage naturally emerges in the unmasked layers". The security of these layers depends entirely on the shuffling and search space arguments evaluated in sections 4.2 and 4.3. This analysis focuses on the INTT, where the masking boundary is architecturally documented and the GS butterfly structure enables algebraic reductions in section 4.3. The forward NTT (CT butterfly) masking coverage is not separately characterized here; if the forward NTT is also partially masked, the attack surface may extend beyond the INTT layers analyzed.

### 4.5 SASCA and Belief Propagation Literature

The published side-channel literature on NTT implementations provides empirical evidence on the feasibility of exploiting the leakage identified in section 4.4. We present the strongest results, noting SW/HW provenance for each.

**Reference** \[22\]**:** CPA on Adams Bridge FPGA implementation with approximately $10,000$ traces achieves full key recovery. These targets unmasked modular reduction (BFU_mult), not the INTT layers 2--7 (ML-KEM) / 2--8 (ML-DSA) analyzed here but demonstrates that the hardware leaks sufficient signal for practical CPA.

**References** \[11-13\]: SASCA and belief propagation attacks do not enumerate hypotheses per butterfly as the per-butterfly CPA model in C1 and C2 assumes. Instead, they propagate soft (probabilistic) information through the NTT factor graph, exploiting algebraic dependencies between butterflies. This fundamental difference in attack model means that the per-butterfly search space estimates in C1 and C2 do not directly bound the complexity of SASCA-style attacks.

**Reference** \[12\]**:** A template attack using 213 univariate Hamming weight templates achieves single-trace NTT key recovery, a $5,000 \times$ reduction from the approximately $10^{6}$ traces assumed in classical CPA. This directly undermines the "exponential hypothesis space" argument by demonstrating that template attacks can bypass per-coefficient enumeration entirely.

**Reference** \[1\]**:** SASCA on locally masked NTT for ML-KEM, validated on Artix-7 FPGA (measured traces) and 22nm ASIC (simulated traces). Breaks local masking with up to $u = 4$ masks at $\sigma \leq 0.3$. This targets local masking of twiddle factors, not the partial first-layer masking architecture of Adams Bridge. The result demonstrates SASCA feasibility on NTT implementations with hardware-class signal characteristics.

**Reference** \[31\]**:** A higher-order CPA attack recovers ML-DSA keys from a second-order masked software implementation using 700 traces. This demonstrates that even second-order masking is breakable with moderate trace counts in software.

**Reference** \[32\]: (Extrapolation). An emerging class of attacks uses convolutional neural networks (CNNs) or multilayer perceptions to recover secrets directly from raw power traces, bypassing explicit hypothesis enumeration entirely. Published results on shuffled AES implementations demonstrate that deep learning models can internally learn to de-shuffle without prior knowledge of the permutation. While no deep learning attack on shuffled NTT hardware has been published, the attack class is relevant because it invalidates the assumption, implicit in C1 and C2, that the attacker must enumerate the per-butterfly hypothesis space. Against a deep learning adversary, the $2^{46}$ and $2^{96}$ search space arguments may not apply.

### 4.6 Profiled Attack Surface

This subsection is strictly separated from the non-profiled analysis in Sections 4.2--4.5. Results here are not incorporated into the margin synthesis in Section 4.7.

The designers scope their security analysis to non-profiled attacks \[21\] (Section 3.9). For an open-source hardware design, this exclusion merits examination.

**Open-source RTL enables offline profiling**: (Proven- fact). Adams Bridge RTL is publicly available under the Apache 2.0 license \[27\]. An attacker with access to the source can synthesize the exact gate-level netlist, compute Hamming distance models for every flip-flop, and generate templates without requiring physical measurements. FPGA reproduction requires equipment costing less than \$10,000, within the budget of academic or corporate red teams.

**Profiled attacks reduce shuffling protection**: (Literature-Supported- SW). It was demonstrated \[10\] that profiled attacks can defeat RSI shuffling, as the shuffling permutation itself becomes a target of the profiling step. In plus, single-trace recovery was achieved using 213 templates, effectively bypassing shuffling entirely \[12\].

**Honest caveat.** No profiled hardware attack on partially masked NTT in an SoC deployment context has been published. Open-source RTL lowers the profiling barrier but does not constitute a demonstration of practical key recovery.

### 4.7 Security Margin Synthesis

We synthesize the evidence from section 4.2--4.5 into margin bounds. Rather than presenting a single point estimate, we provide a sensitivity analysis reflecting the genuine uncertainty in several key assumptions, summarized in Table 3.

***Table 3.** Sensitivity analysis for margin assumptions.*

  ---------------------------------------------------------------------------------------------------------------------------
  **Assumption**                         **Pro-Attacker**                  **Pro-Defender**            **Evidence Quality**
  -------------------------------------- --------------------------------- --------------------------- ----------------------
  GS butterfly DOF                       1 (exact constraint)              2 (noisy HW)                EXTRAPOLATION

  Shuffling overhead (RSI, $S = 64$)     $$1 \times$$                      $4,096 \times$ ($S^{2}$)    LITERATURE-SUPPORTED

  Coefficients for ML-DSA key recovery   32 (BKZ-60 \[29\])                256 (brute force)           LITERATURE-SUPPORTED

  ML-KEM unknowns per butterfly          4 (known ciphertext \[30\])       8 (full)                    LITERATURE-SUPPORTED

  HW vs SW SNR transfer                  Better (deterministic pipeline)   Worse (SoC noise)           SPECULATIVE

  SCA coefficient error rate             $< 5\%$ (near-exact recovery)     $\geq 5\%$ (BKZ-60 fails)   EXTRAPOLATION
  ---------------------------------------------------------------------------------------------------------------------------

Note that scenario A assumes near-exact coefficient recovery ($< 5\%$ error rate), under which BKZ-60 lattice reduction succeeds with 32 coefficients \[29\]. At realistic hardware error rates ($\geq 5\%$), BKZ-60 fails or requires substantially larger block sizes, pushing effective margins toward Scenario B. No published result establishes the achievable error rate on Adams Bridge hardware.

**Composite scenarios.** We consider scenarios for both ML-DSA and ML-KEM, spanning the range from the designers' implied margins to the most aggressive literature-supported reductions.

**ML-DSA scenarios:**

***Scenario A (pro-attacker):*** GS constraint reduces per-butterfly DOF to 1 ($2^{23}$ hypotheses per butterfly); SIS reduction requires only \~16 butterflies \[29\]; RSI provides no effective overhead ($1 \times$). Derivation: $16 \times 2^{23} \times 1 \approx 2^{27}$. With BP factor-graph propagation further reducing complexity \[11, 13\], effective margin: $\approx 2^{15}$--$2^{27}$.

***Scenario B (pro-defender):*** Per-butterfly complexity remains $2^{46}$ (C1 accepted at face value); no SIS reduction applied; RSI overhead at the full $S^{2} = 4,096 \times$ per layer across 7 unmasked layers. The $2^{46}$ is a hypothesis-space measure (CPA guesses per butterfly pair) and the $7 \times 4,096$ is a trace-overhead factor (additional measurements needed to resolve shuffling). The composite $2^{46} \times (7 \times 4,096) = 2^{46} \times 2^{14.8} \approx 2^{61}$ represents total attack work in a unified enumeration-plus-acquisition metric: $2^{46}$ hypotheses, each requiring \~28,672 additional traces to test through shuffling noise, yielding $\approx 2^{61}$ total hypothesis-trace operations. Effective margin: $\approx 2^{61}$.

***Scenario C (pro-defender):*** Per-butterfly complexity $2^{46}$; shuffling compounds multiplicatively as $S^{L} = 64^{7} \approx 2^{42}$. Effective margin: $\approx 2^{88}$, matching the designers' implied estimate. This scenario depends on $S^{L}$ multiplicative compounding, for which no published security proof exists.

***Mixed-assumption estimate**:* This scenario selects intermediate values for each contested assumption, favoring neither attacker nor defender exclusively. GS constraint partially exploited ($\approx 1.3$ effective DOF, reflecting noisy but non-trivial algebraic leakage); SIS reduction to \~32 coefficients from \~16 butterflies \[29\]; RSI overhead $\approx 64 \times$ (the geometric mean of the literature extremes: $\sqrt{1 \times 4,096} = 64$, reflecting genuine uncertainty about partial RSI protection observed in AES contexts \[11\] but not yet measured for NTT). Approximate derivation: $16\text{ butterflies} \times 2^{23/1.3} \times 64 \approx 2^{4} \times 2^{17.7} \times 2^{6} \approx 2^{28}$. Residual inter-butterfly correlations not captured by the single-butterfly model would increase this figure, but by an amount we cannot formally bound; we therefore report the mixed-assumption estimate as a range $2^{28}$--$2^{37}$, where the upper end represents a conservative allowance for inter-butterfly uncertainty rather than a derived quantity. This composite range carries substantial epistemic uncertainty, as it combines independently derived bounds from different papers on different platforms. It should be interpreted as an order-of-magnitude indicator, not a precise bound.

***ML-KEM scenarios*:** The designers claim $2^{96}$ per-butterfly CPA complexity (C2). The Known-Ciphertext Attack \[30\] reduces unknowns per butterfly from 8 to 4, yielding a base of $2^{48}$, with 6 unmasked layers.

***Scenario A (pro-attacker):*** KCA base $2^{48}$; GS constraint reduces DOF; RSI $1 \times$; BP propagation. Derivation: $\sim 16 \times 2^{12} \times 1 \approx 2^{16}$. Effective margin: $\approx 2^{16}$--$2^{30}$.

***Scenario B (pro-defender)**:* KCA base $2^{48}$; RSI at $S^{2} = 4,096 \times$ across 6 unmasked layers: $2^{48} \times (6 \times 4,096) = 2^{48} \times 2^{14.6} \approx 2^{63}$ total hypothesis-trace operations (same dimensional convention as ML-DSA Scenario B).

***Scenario C (pro-defender)*** Full $2^{96}$ base; $S^{L} = 64^{6} \approx 2^{36}$. Effective margin: $\approx 2^{132}$. *It depends on unproven* $S^{L}$ *compounding and rejection of KCA reduction.*

***Table 4.** Composite margin scenarios for ML-DSA and ML-KEM. See Table 6 for the conservative/moderate breakdown of Scenario E.*

  --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Scenario**                      **ML-DSA Margin**    **vs. Designers' Implied** $\approx 2^{88}$**†**   **ML-KEM Margin**     **vs. Designers' Implied** $\approx 2^{132}$**†**   **Key Assumptions**
  --------------------------------- -------------------- -------------------------------------------------- --------------------- --------------------------------------------------- --------------------------------------------
  A: Pro-attacker                   $2^{15}$--$2^{27}$   $2^{61}$--$2^{73}$ below                           $2^{16}$--$2^{30}$    $2^{102}$--$2^{116}$ below                          GS exact, SIS succeeds, RSI $1 \times$, BP

  Mixed-assumption                  $2^{32}$--$2^{42}$   $2^{46}$--$2^{56}$ below                           $2^{35}$--$2^{45}$    $2^{87}$--$2^{97}$ below                            GS partial, SIS 32 coeff., RSI $64 \times$

                                                                                                                                                                                      

  **E: Empirical (section 4.8)‡**   $$\approx 2^{9}$$    $\approx 2^{37}$ **below** $2^{46}$                $$\approx 2^{9}$$     $\approx 2^{37}$ **below** $2^{46}$                 **RTL-derived MI, 512 RSI runs, no BP**

                                                                                                                                                                                      

  B: Pro-defender (lit.)            $2^{59}$--$2^{63}$   $2^{25}$--$2^{29}$ below                           $2^{61}$--$2^{65}$    $2^{67}$--$2^{71}$ below                            C1/C2 accepted, RSI at $S^{2}$, no SIS

  C: Pro-defender extreme           $$\approx 2^{88}$$   Matches estimate                                   $$\approx 2^{132}$$   Matches estimate                                    Unproven $S^{L}$ compounding
  --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

> *†The* $\approx 2^{88}$ *and* $\approx 2^{132}$ *figures are our reconstruction of the designers' argument by composing per-butterfly claims (C1/C2) with* $S^{L}$ *multiplicative shuffling compounding (C3):* $2^{46} \times 64^{7} \approx 2^{88}$ *(ML-DSA) and* $2^{96} \times 64^{6} \approx 2^{132}$ *(ML-KEM). These totals are not stated explicitly in* \[21\]*.*
>
> *‡Scenario E is separated visually because it uses a different methodology (original RTL-derived experiments) than Scenarios A--C (literature synthesis). Its margin is measured against the per-butterfly* $2^{46}$ *rather than the full composite estimates, as explained in section 4.8.*

*Scenario E* represents empirical validation from section 4.8. Unlike Scenarios A--C, which derive margins from independent literature-supported assumptions, Scenario E chains original RTL-derived measurements through a SASCA pipeline: RTL leakage extraction (Exp D) → template attack bridging (Exp E) → layer-by-layer RSI enumeration (Exp A/C) → composite margin (Exp G). The resulting $\approx 2^{9}$ enumeration (512 BP runs for RSI resolution) represents the dominant cost when the profiled attacker accumulates sufficient mutual information (\~992 traces) to exhaust the per-coefficient entropy; optimal key enumeration algorithms \[33\] would further reduce the practical search effort within this residual space. This scenario assumes a profiled attack model and is therefore not directly comparable to the non-profiled Scenarios A--C; it quantifies the enumeration complexity under profiled assumptions. The 37-bit attack-model gap versus the designers' $2^{46}$ is independent of belief propagation: it requires no BP entropy reduction and holds even if ML-KEM BP results do not transfer to ML-DSA. Not that the conservative (no-BP) column in Table 6 shows $0\%$ lattice success because Exp H demonstrates $> 50\%$ per-coefficient MAP error on the minimal BP subgraph, exceeding the lattice recovery threshold; the 37 bits quantify the attack-model gap, not completed key recovery (see section 4.8 for detailed sensitivity analysis).

What we found is that for ML-DSA, under the strongest literature-supported pro-defender assumptions (Scenario B), the effective margin falls in the range $2^{59}$--$2^{63}$, roughly $2^{25}$--$2^{29}$ lower than the designers' implied estimate of $\approx 2^{88}$. For ML-KEM, the gap is larger: even Scenario B yields $2^{61}$--$2^{65}$, roughly $2^{67}$--$2^{71}$ below the designers' implied $\approx 2^{132}$, because the Known-Ciphertext Attack \[30\] reduces the base from $2^{96}$ to $2^{48}$ independently of any shuffling assumption. In both cases, the gap between Scenarios B and C hinges entirely on whether shuffling compounds multiplicatively across NTT layers ($S^{L}$), a question that is open in published literature. Under pro-attacker assumptions incorporating SIS lattice reduction (ML-DSA) or KCA reduction (ML-KEM) and SASCA-style attacks, margins fall to $\approx 2^{15}$ (ML-DSA) or $\approx 2^{16}$ (ML-KEM). The actual margins depend on hardware signal-to-noise ratio, the exact shuffling overhead for RSI (between $1 \times$ and $4,096 \times$), and the feasibility of composing independently demonstrated attack techniques on Adams Bridge hardware in a SoC deployment context.

### 4.8 Empirical Validation

The margin synthesis in section 4.7 composes independently published results from different papers, platforms, and attack models. A natural question is whether these reductions chain coherently against Adams Bridge specifically. We address this by developing a SASCA attack pipeline grounded in RTL-simulated leakage, operating at the same RTL abstraction level from which the designers' own pre-silicon TVLA validation was conducted \[21\], and measuring each pipeline stage against Adams Bridge's actual design parameters. The following experiments do not demonstrate a complete attack on hardware. They quantify, stage by stage, how much of the designers' claimed $2^{46}$ margin survives each independently validated reduction, demonstrating a 37-bit attack-model gap (enumeration reduced from $2^{46}$ to $2^{9}$) independent of belief propagation, and validating full coefficient recovery via BP on the complete ML-KEM factor graph (Exp I).

Experiments A, D, E, and G are deterministic: they derive from RTL simulation (fixed logic), analytical MI computation, or algebraic enumeration, and produce identical results on re-execution. Statistical analysis (confidence intervals, Monte Carlo repetitions) applies only to stochastic experiments, Exp B (900 lattice trials), Exp C (analytical CDF), Exp F (10 trials × 7 SNR points with random seeds, base seed 42), Exp H (10 trials × 7 SNR$\times$N points, seeds $1000 \times \text{trial} + \text{snr\_n}\ mod\ 1000$), and Exp I (10--20 trials × 8 SNR$\times$N points, 30 BP iterations each; 120 trials total). Exps F, H, and I report 95% CIs; Exp B reports success rates over 900 trials.

The validation comprises nine experiments (summarized in Table 5), each targeting a specific link in the SASCA attack chain:

***Table 5.** Empirical validation experiments.*

  -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Exp**   **Target**                  **Key Result**                                                                                                                                                                                                                                 **Validates**                                                           **Confidence**
  --------- --------------------------- ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- ----------------------------------------------------------------------- ----------------
  A         Factor graph complexity     Treewidth $> 30$; layer-by-layer RSI: 512 BP runs                                                                                                                                                                                              RSI enumeration = $2^{9}$, not $2^{42}$                                 PROVEN

  B         BKZ lattice sensitivity     47% at $< 1\%$ error, 0% at $\geq 10\%$                                                                                                                                                                                                        Lattice threshold for pipeline                                          PROVEN

  C         RSI vs RP shuffling         RSI collapses to $7.3 \times$ at $\sigma_{\text{bias}}/\sigma = 0.3$                                                                                                                                                                           RSI weaker than RP with position bias                                   LIT-SUPPORTED

  D         RTL leakage extraction      $max|t| = 6.34$ (LEAK), SNR $= 0.0027$                                                                                                                                                                                                         Unmasked INTT leaks at RTL level                                        PROVEN (RTL)

  E         Template attack bridge      992 traces for full MI recovery ($23.0$ bits)                                                                                                                                                                                                  D→B: SNR sufficient for MI exhaustion                                   LIT-SUPPORTED

  F         BP on NTT factor graph      3.9 bits reduction at $\text{SNR} \times N = 10^{4}$                                                                                                                                                                                           NTT structure aids recovery via BP                                      LIT-SUPPORTED

  G         Composite security margin   37-bit gap (no BP); 40-bit (with BP)                                                                                                                                                                                                           End-to-end attack-model gap                                             COMPOSITE

  H         Monte Carlo BP validation   Entropy confirmed; MAP $> 50\%$ on 2-layer                                                                                                                                                                                                     BP gains are real but insufficient alone                                PROVEN (sim)

  I         Full-scale ML-KEM BP        100% recovery at SNR$\times$N $= 3 \times 10^{3}$ (10/10 at threshold; 120 trials across 8 SNR$\times$N points); 2.24$\times$ peak single-layer gain (0.30$\times$ normalized; 99.6% genie-aided); 4 necessary conditions for BP convergence   Resolves Exp H limitation; BP closes loop; countermeasure design tool   PROVEN (sim)
  -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

#### 

#### 4.8.1 Factor Graph Construction (Exp A)

The NTT's butterfly structure maps to a factor graph with variable nodes (intermediate coefficient values) and factor nodes (butterfly operations). For the Adams Bridge ML-DSA INTT (8 layers, 256 coefficients), this yields 2,304 variable nodes, 1,024 factor nodes, and 4,096 edges. With RSI shuffling ($S = 64$ states per layer), shuffle nodes add high-degree connections, increasing the treewidth upper bound from 81 to 90.

All configurations exceed treewidth 30, rendering exact junction-tree inference provably intractable and rigorously motivating loopy sum-product BP as the inference method, the standard approach in the SASCA literature \[13, 33\].

Because RSI produces only $S = 64$ orderings per layer (versus $S! = 64!$ for full random permutation), layer-by-layer marginalization requires only $S \times L_{u}$ BP runs, where $L_{u}$ is the number of unmasked layers. For ML-DSA, $64 \times 7 = 448$ runs ($\approx 2^{8.8}$); for ML-KEM, $64 \times 6 = 384$ runs ($\approx 2^{8.6}$). We round up to $512 = 2^{9}$ as a conservative upper bound that also accounts for possible masked-layer enumeration (the masked first layer is also shuffled; while its leakage is suppressed by masking, an attacker may still need to resolve its ordering to correctly align inter-layer BP messages). This is a trivially enumerable space compared to Hermelink et al.'s worst case of $2^{16}$ runs per layer for full RP \[13\]. The $\log_{2}(512) = 9$ bits of enumeration dominates the conservative attack cost. Each of the 512 RSI candidates requires one full BP inference pass: for ML-KEM (exact BP), this is $O(q^{2} \times \text{graph\_size})$, completing in seconds per run; for ML-DSA with approximate BP, per-run cost depends on the approximation method and remains an open question.

#### 4.8.2 Lattice Recovery Sensitivity (Exp B)

Radix-4 decomposition partitions the NTT-domain coefficients into 4 independent 64-dimensional sub-problems, each solvable via Babai nearest-plane CVP on the kernel lattice $\mathbf{L}_{q}^{\perp}(\mathbf{A})$ \[29\]. Using fpylll with BKZ reduction (AUTO_ABORT, 8 tours), we measure success rates across 900 trials:

  ------------------------------------------------------------------
  **Per-coefficient error**   **Groups solved**   **Success rate**
  --------------------------- ------------------- ------------------
  $$0\%$$                     64/64               $$100\%$$

  $$1\%$$                     \~30/64             $$47\%$$

  $$2\%$$                     \~22/64             $$34\%$$

  $$5\%$$                     \~2/64              $$3\%$$

  $$10\%$$                    0/64                $$0\%$$
  ------------------------------------------------------------------

The sharp sensitivity curve, $100\% \rightarrow 47\% \rightarrow 0\%$ at $0/1/10\%$ error, establishes that lattice recovery is a threshold phenomenon. Once the SASCA pipeline pushes per-coefficient error below $\sim 2\%$, recovery probability jumps discontinuously. LLL on each 64-dimensional sub-lattice completes in $< 0.5$ seconds, zero marginal enumeration cost. Babai CVP is a weak solver; stronger methods (e.g., enumeration with pruning) may tolerate higher error rates, potentially shrinking the gap. Conversely, error amplification through Vandermonde coupling (a clean group requires all 4 NTT coefficients correct: probability $(1 - p)^{4}$) pushes in the opposite direction.

#### 4.8.3 RSI Shuffling Overhead (Exp C)

We model CPA success probability under three shuffling modes (known-position, RSI, full RP) with Gaussian noise and position-dependent bias, using the CDF trick for analytical success probability computation. Key results for $S = 64$, $q = 8,380,417$:

  ---------------------------------------------------------------------------------------------------------------
  $$\sigma_{\text{bias}}/\sigma$$   **RSI overhead**           **RP overhead**            **RSI/RP ratio**
  --------------------------------- -------------------------- -------------------------- -----------------------
  $0$ (no position info)            $4,096 \times$ ($S^{2}$)   $4,096 \times$ ($S^{2}$)   $$1.0 \times$$

  $0.3$ (moderate)                  $$7.3 \times$$             $$4,096 \times$$           $561 \times$ weaker

  $0.5$ (strong)                    $$1.6 \times$$             $$4,096 \times$$           $2,560 \times$ weaker
  ---------------------------------------------------------------------------------------------------------------

At zero position bias, RSI and RP are equivalent (both $S^{2}$). With even moderate position-dependent bias ($\sigma_{\text{bias}}/\sigma = 0.3$, a modeling choice informed by position-dependent leakage phenomena characterized for AES-class shuffling. This specific ratio was not reported, RSI collapses to $7.3 \times$ overhead while full RP maintains $S^{2}$ \[10\]. This validates the Scenario E assumption that RSI enumeration (512 runs) dominates the attack cost when position leakage is available.

*Provenance:* The $\sigma_{\text{bias}}/\sigma = 0.3$ value is an extrapolation from position-dependent leakage phenomena characterized in AES shuffling studies, this exact ratio was not reported. No position-bias measurement exists for Adams Bridge. The conservative (no-BP) 37-bit gap assumes zero position bias and full $S^{2}$ RSI overhead; position leakage strictly improves the attacker's position.

#### 4.8.4 RTL Leakage Extraction (Exp D)

Using Verilator cycle-accurate RTL simulation with 1,000 fixed and 1,000 random input pairs (595 cycles each, masking boundary at cycle 345), we extract first-order TVLA statistics and SNR values for five register groups:

  -------------------------------------------------------------------------------------
  **Register group**   **Masked** $max|t|$   **Unmasked** $max|t|$   **Unmasked SNR**
  -------------------- --------------------- ----------------------- ------------------
  Butterfly            3.36 (PASS)           **6.34 (LEAK)**         0.0027

  Mem Write            14.26 (LEAK)          **13.17 (LEAK)**        0.0155

  Mem Read             7.09 (LEAK)           **5.62 (LEAK)**         0.0033

  Address              1.43 (PASS)           2.63 (PASS)             0.0004

  Control              0.00 (PASS)           0.00 (PASS)             0.0000
  -------------------------------------------------------------------------------------

The unmasked butterfly group exceeds the $|t| = 4.5$ TVLA threshold at $N = 1,000$ traces per set, confirming statistically significant first-order leakage in the unmasked INTT layers. (The hardware processes multiple NTT butterfly layers per pipeline round; the 3 unmasked hardware rounds correspond to the 7 unmasked NTT layers identified in Table 2. The MI analysis in Exp E accumulates leakage per hardware execution cycle, not per NTT layer.) The butterfly SNR of 0.0027 is low but non-zero, consistent with RTL-level Hamming distance leakage models that capture register transitions but not gate-level or layout-level power consumption effects.

This establishes a threat model gap: the design exhibits detectable first-order leakage at the RTL abstraction level, a necessary (but not sufficient) condition for profiled exploitation. The designers' verification methodology (non-specific TVLA at $10^{6}$ traces) is a leakage *detection* test, not an attack resistance metric \[15\]; it is not designed to assess vulnerability to profiled SASCA attacks. A passing TVLA does not preclude exploitable leakage in specific operation phases. The designers' security argument for the unmasked layers relies on shuffling and search space arguments, not on the absence of leakage. Note that RTL simulation captures register-level Hamming distance. Real silicon includes gate-level switching, clock jitter, power supply noise, and SoC-level filtering. The measured SNR may over- or underestimate the physical leakage.

#### 4.8.5 Template Attack Bridge (Exp E)

We bridge Exp D's SNR measurements to Exp B's lattice threshold by computing the mutual information (MI) per trace per coefficient from the measured SNR values. Each coefficient per unmasked INTT layer produces leakage in three distinct register-group transitions: butterfly computation, memory write, and memory read (see Exp D, Table). Each transition provides an independent MI contribution computed via the Gaussian channel capacity formula at the measured SNR. The combined MI per trace per coefficient across all three leakage sources is $0.023198$ bits.

MI accumulation. For ML-DSA's 23-bit coefficient entropy ($H(X) = 23.0$ bits):

- Full MI recovery: $N \approx 992$ traces (accumulated MI exhausts $H(X)$)
- $< 5\%$ MAP error: $N \approx 989$ traces
- $< 2\%$ MAP error: $N \approx 991$ traces

The MI model predicts a sharp transition, an "MI threshold", at \~992 traces: below this, per-coefficient error exceeds 50%; above it, error drops toward zero. This threshold is determined by the coefficient bit-width (23 bits for ML-DSA), the number of unmasked layers, and the RTL-measured SNR; it is architecturally determined by the design's bit-width and round structure, though the SNR component is model-dependent and may differ in silicon (limitation G10).

As an example, *c*ombined MI per trace per coefficient = $\sum_{g \in \{\text{butterfly, mem-write, mem-read}\}}^{}\frac{1}{2}\log_{2}(1 + \text{SNR}_{g}/2)$ = $0.000963 + 0.005555 + 0.001215 = 0.007733$ bits per register-group transition. Each coefficient traverses all three register groups per unmasked INTT layer, yielding $0.007733 \times 3 = 0.023198$ bits per trace per coefficient. Traces for full MI recovery: $\lceil 23.0/0.023198\rceil = 992$.

Note that the standard Gaussian channel capacity is $\frac{1}{2}\log_{2}(1 + \text{SNR})$. We use $\text{SNR}/2$ rather than $\text{SNR}$ because the per-coefficient SNR is derived by halving the aggregate register-group SNR from Exp D, each register transition depends on two butterfly coefficients (input or output pair), so the per-coefficient signal contribution is conservatively estimated as half the measured aggregate. This halving is a deliberate conservative choice: using the full aggregate SNR would yield \~496 traces (half the reported threshold), strengthening the attacker's position. The 992-trace figure therefore represents a pro-defender bound. For readers who prefer the full-SNR model, the pipeline's qualitative conclusions are unchanged, only the trace budget halves.

The MI per trace is a deterministic function of the measured SNR; uncertainty in the 992-trace threshold derives entirely from SNR measurement uncertainty (Exp D), which is bounded by the deterministic RTL simulation. The MI calculation uses the Gaussian channel capacity formula with Exp D's measured per-coefficient SNR (aggregate SNR halved, conservative). The 3-transition-per-coefficient model is conservative (additional leakage sources would increase MI, reducing trace count).

#### 4.8.6 Belief Propagation on NTT Factor Graph (Exp F)

We implement loopy sum-product BP on a 2-layer Gentleman-Sande INTT factor graph with 8 ML-KEM coefficients ($q = 3,329$), using profiled circular Gaussian observations on the unmasked layers. Layer 0 coefficients are recovered solely through BP propagation (no direct observations).

Within the Adams Bridge operating range ($\text{SNR} \times N = 270$ to $27,000$, corresponding to the butterfly register SNR of 0.0027 from Exp D multiplied by 100 to 10,000 traces, spanning a typical evaluation lab's acquisition budget):

- Best case ($\text{SNR} \times N = 10^{4}$): L0 entropy reduced from 11.7 to 7.8 bits (3.9-bit gain)
- Worst case ($\text{SNR} \times N = 300$): L0 entropy reduced from 11.7 to 9.9 bits (1.8-bit gain)

These gains demonstrate that NTT's algebraic structure creates exploitable inter-layer information propagation at hardware-realistic noise levels, extending software-only BP results \[13, 15\] to hardware-derived SNR values.

Exp F uses ML-KEM ($q = 3,329$) because exact BP with full probability tables is feasible: per-message complexity is $O(q^{2}) \approx 10^{7}$. For ML-DSA ($q = 8,380,417$), exact BP requires $O(q^{2}) \approx 7 \times 10^{13}$ per message, computationally infeasible. Approximate methods (particle BP, neural BP) may achieve different gains, but the ML-KEM-to-ML-DSA transfer remains unvalidated. The 37-bit headline gap in section 4.8.7 requires no BP gain and is therefore independent of this transfer question.

#### 4.8.7 Composite Security Margin (Exp G)

We formalize the end-to-end attack work by chaining the measured pipeline stages. Table 6 breaks down the conservative and moderate scenarios summarized as Scenario E in Table 4 (section 4.7); the conservative column corresponds to Table 4's $\approx 2^{9}$ enumeration.

***Table 6.** SASCA pipeline attack work.† What varies between columns: position bias assumption, BP gain, and profiling model.*

  -----------------------------------------------------------------------------------------------------------------------
  **Parameter**             **Conservative**                 **Moderate**                                    **Unit**
  ------------------------- -------------------------------- ----------------------------------------------- ------------
  Scenario                  No profiling, no position bias   Profiled, $\sigma_{\text{bias}}/\sigma = 0.3$   

  Traces needed             992                              824                                             traces

  Shuffle BP runs           512                              48                                              runs

  BP structural gain        0.0                              3.9                                             bits/coeff

  MI-theoretic residual     0.0                              0.0                                             bits

  Practical error (Exp H)   $$> 50\%$$                       MI-predicted $0\%$                              

  Lattice success (Exp B)   $$0\%$$                          $$100\%$$                                       

  **Total enumeration**     **9.0**                          **5.6**                                         **bits**
  -----------------------------------------------------------------------------------------------------------------------

> *†Conservative assumes zero position bias (full* $S^{2} = 4,096 \times$ *RSI overhead) and no BP structural gain. Moderate uses Exp C's* $7.3 \times$ *RSI overhead for* $\sigma_{\text{bias}}/\sigma = 0.3$ *and Exp F's 3.9-bit BP entropy reduction. ‡The conservative column's 9.0-bit enumeration quantifies the SASCA pipeline's residual complexity, not a completed key recovery. Lattice success is 0% because Exp H's* $> 50\%$ *per-coefficient MAP error on the minimal 2-layer subgraph exceeds the* $< 2\%$ *threshold required by Exp B. However, Exp I (section 4.8.9) demonstrates that the full 7-layer ML-KEM graph achieves 0% MAP error at SNR*$\times$*N* $= 3,000$*: the information exists and BP can extract it given sufficient graph structure.*

Figure 1 renders this decomposition as a waterfall, making explicit which CPA assumption each SASCA mechanism invalidates.

![Security margin waterfall](media/image1.png){width="6.847222222222222in" height="4.362045056867892in"}

***Figure 1.** Security margin analysis waterfall, conceptual decomposition of how the designers'* $2^{46}$ *CPA model maps to* $2^{9}$ *under SASCA. Note: this decomposition illustrates how the CPA model's assumptions break down under SASCA analysis. The step sizes are approximate and not independently measured, SASCA replaces the CPA enumeration model entirely rather than reducing it incrementally. The value of the decomposition is pedagogical: it shows which CPA assumptions each SASCA mechanism invalidates.*

The 37-bit figure represents a qualitative shift in attack model, not merely a quantitative reduction within a single model. The designers' $2^{46}$ measures per-butterfly hypothesis enumeration under CPA; our $2^{9}$ measures RSI ordering enumeration under SASCA. These are different complexity metrics, CPA-bits and SASCA-bits, applied to the same hardware. The "37-bit gap" is therefore the distance between the designers' CPA-based security argument and the residual complexity under a SASCA adversary that the designers' model does not consider. It quantifies how much of the claimed margin depends on the assumption that attackers use per-butterfly CPA rather than algebraic attacks.

Our finding is that without any belief propagation gain, relying solely on MI accumulation over \~992 traces and layer-by-layer RSI enumeration (512 runs), the SASCA pipeline reduces the enumeration complexity from $2^{46}$ (the designers' per-butterfly CPA model) to $2^{9}$ (512 RSI runs), a 37-bit attack-model gap (CPA $\rightarrow$ SASCA). This result is independent of the ML-KEM$\rightarrow$ML-DSA BP transfer question: the 37 bits derive from SASCA's elimination of per-coefficient enumeration (replacing $2^{23}$ hypothesis tests with $O(q^{2})$ BP messages) combined with RSI's enumerable structure (512 runs = $2^{9}$ bits). Importantly, the conservative scenario does not complete the attack: although 992 traces collect sufficient MI in theory, Exp H demonstrates that loopy BP on the minimal subgraph achieves $> 50\%$ per-coefficient MAP error, well above the $< 2\%$ threshold required for lattice recovery (Exp B), resulting in $0\%$ lattice success. The 37-bit figure quantifies how much of the designers' $2^{46}$ margin is consumed by the SASCA enumeration reduction, not a demonstrated key recovery.

With BP structural gains (1.8--3.9 bits within the Adams Bridge operating range, Exp F; up to $2.24 \times$ MI amplification on the full graph, Exp I), the MI-predicted residual drops to 0 bits, yielding $100\%$ lattice success and a 40--42 bit gap. Exp I validates these gains empirically for ML-KEM: the full 7-layer graph achieves 0% MAP error at SNR$\times$N $= 3 \times 10^{3}$ (10/10 trials, confirmed by 15/15 multi-seed replication; Wilson CI \[72.3%, 100%\]), confirming that the BP-enhanced margins are achievable under the simulated profiled model, not merely information-theoretic upper bounds.

**Sensitivity analysis.** The 37-bit gap is robust to parameter variation:

  ----------------------------------------------------------------------------------------------------
  **BP gain (bits)**   **Source**                **Traces**   **Shuffle runs**   **Gap vs** $2^{46}$
  -------------------- ------------------------- ------------ ------------------ ---------------------
  0.0                  No BP (conservative)      992          512                $- 37$ bits

  1.8                  Worst AB range (ML-KEM)   914          48                 $- 40$ bits

  3.9                  Best AB range (ML-KEM)    824          48                 $- 40$ bits
  ----------------------------------------------------------------------------------------------------

Even with zero BP gain and full $S^{2}$ RSI overhead (the most conservative assumptions), the gap remains 37 bits. The headline finding is non-fragile.

#### 4.8.8 Monte Carlo Validation (Exp H)

To validate the information-theoretic predictions, we run Monte Carlo BP simulations on the 2-layer ML-KEM factor graph (10 trials $\times$ 7 SNR$\times$N points):

  ------------------------------------------------------------------------------
  **SNR**$\times$**N**   **L0 Error Rate**   **95% CI**         **L0 Entropy**
  ---------------------- ------------------- ------------------ ----------------
  $$3 \times 10^{2}$$    98.8%               \[93.3%--99.8%\]   9.9 bits

  $$10^{4}$$             95.0%               \[87.8%--98.0%\]   7.8 bits

  $$10^{6}$$             52.5%               \[41.7%--63.1%\]   1.3 bits
  ------------------------------------------------------------------------------

We confirm entropy reductions**.** L0 entropy at SNR$\times$N $= 10^{4}$ matches Exp F exactly (7.8 bits, 3.9-bit reduction from 11.7). However, MAP error rates remain $> 50\%$ on this minimal 2-layer, 8-coefficient subgraph. The $< 5\%$ lattice threshold (Exp B) is not reached within the tested range.

This is expected: the 2-layer graph provides limited algebraic structure compared to the full 7-layer, 256-coefficient ML-KEM INTT (which has \~32$\times$ more butterfly factors). Experiment I (section 4.8.9) resolves this limitation by demonstrating that the full ML-KEM graph achieves 100% coefficient recovery at SNR$\times$N $= 3,000$ where this minimal subgraph shows $> 95\%$ error.

A reader may note an apparent contradiction: Exp E predicts that 992 traces "exhaust" the 23.0-bit coefficient entropy, yet Exp H shows $> 50\%$ MAP error. The resolution is that MI exhaustion is an information-theoretic statement (Shannon capacity, the information exists in the traces), while MAP error is a practical inference result (whether a specific algorithm can extract it). Loopy BP on the minimal cyclic factor graph is an approximate inference method with a known convergence ceiling (94% bit success rate at best, Exp F). The information is present in the traces; the extraction algorithm, and graph structure, are the bottleneck. Exp I confirms this diagnosis. Running the same BP algorithm on the full 7-layer, 256-coefficient ML-KEM graph (\~32$\times$ more algebraic constraints than the 2-layer test graph) achieves 0% MAP error at SNR$\times$N $= 3 \times 10^{3}$ (10/10 trials) where Exp H shows $> 95\%$ error. The constraint density of the full graph enables BP to extract the information that the minimal graph cannot.

Exp H confirms that loopy BP produces meaningful entropy reduction at realistic noise levels (positive result) but cannot close the gap to lattice recovery on a minimal subgraph (negative result). The 37-bit headline, which requires no BP gain, is unaffected by Exp H's MAP failure, as it relies on direct MI accumulation (Exp E) and RSI enumeration (Exp A), not on BP-assisted coefficient recovery. Experiment I (section 4.8.9) resolves the subgraph limitation by running BP on the full production-scale ML-KEM factor graph.

#### 4.8.9 Full-Scale ML-KEM Belief Propagation (Exp I)

Experiment H's $> 50\%$ MAP error raised a natural question: is the BP failure fundamental, or an artifact of the minimal 2-layer, 8-coefficient subgraph? Exp I resolves this by running belief propagation on the complete ML-KEM INTT factor graph, 7 layers, 256 coefficients, 896 Gentleman-Sande butterfly factors connecting 2,048 variable nodes, and characterizes the recovery threshold through five complementary analyses: a Monte Carlo sweep (Table 7), a genie-aided information-theoretic bound, a layer-ablation study, per-coefficient difficulty profiling, and convergence dynamics.

We construct the exact ML-KEM INTT factor graph per FIPS 203 Algorithm 10 \[FIPS 203\]: 896 butterfly factors across 7 butterfly layers connecting 8 coefficient levels (256 coefficients each). Each butterfly factor enforces the Gentleman-Sande constraint $u_{\text{out}} = (u_{\text{in}} + v_{\text{in}})\ mod\ q$, $v_{\text{out}} = \zeta \cdot (v_{\text{in}} - u_{\text{in}})\ mod\ q$ over $\mathbb{Z}_{3329}$, where $\zeta = \gamma^{\text{BitRev}_{7}(k)}$ for butterfly index $k$ with $\gamma = 17$ (the primitive $256$th root of unity modulo $3329$). Twiddle factors follow FIPS 203 Table 2 with indices counted down from 127, matching the production ML-KEM implementation. Layer 0 (the masked NTT-domain input) receives no observations; layers 1--7 (unmasked intermediate values) receive profiled circular Gaussian observations with per-coefficient SNR derived from RTL-measured toggle rates (Exp D). We run loopy sum-product BP with damping factor 0.5, using exact $O(q^{2})$ message computation per butterfly factor (Numba JIT-accelerated). Each trial generates a random ML-KEM secret polynomial, computes the full 7-layer INTT, creates observations at the specified SNR$\times$N, and evaluates MAP recovery of Layer 0 coefficients.

Table 7 summarizes the Monte Carlo sweep ($n = 10$--$20$ independent trials per SNR$\times$N point, 30 BP iterations each, with 95% Wilson confidence intervals on the full-key recovery rate).[^2]

***Table 7.** Full-scale ML-KEM BP results (FIPS 203 Algorithm 10 twiddle factors, corrected).* $\log_{2}(q) = 11.70$ *bits (uniform = no information). MI*$_{\text{1-layer}}$ *computed numerically (100,000 Monte Carlo samples) from the exact circular Gaussian observation model. Full-Key Rate reports the fraction of independent trials achieving 100% coefficient recovery (BSR* $= 1.0$*), with 95% Wilson score confidence intervals.*

  ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **SNR**$\times$**N**    $$n$$   **Full-Key Rate**   **Wilson 95% CI**   **L0 Entropy (bits)**   **MI**$_{\text{BP}}$ **(bits)**   **MI**$_{\text{1-layer}}$ **(bits)**   **BP Gain**
  ----------------------- ------- ------------------- ------------------- ----------------------- --------------------------------- -------------------------------------- --------------
  $$500$$                 10      30% (3/10)          \[10.8%, 60.3%\]    2.46 $\pm$ 0.31         9.24                              4.23                                   2.19$\times$

  $$10^{3}$$              20      40% (8/20)          \[21.9%, 61.3%\]    1.12 $\pm$ 0.32         10.58                             4.73                                   2.24$\times$

  $$1.5 \times 10^{3}$$   20      85% (17/20)         \[64.0%, 94.8%\]    0.51 $\pm$ 0.23         11.19                             5.02                                   2.23$\times$

  $$2 \times 10^{3}$$     20      90% (18/20)         \[69.9%, 97.2%\]    0.27 $\pm$ 0.22         11.43                             5.23                                   2.19$\times$

  $$2.5 \times 10^{3}$$   20      90% (18/20)         \[69.9%, 97.2%\]    0.18 $\pm$ 0.18         11.52                             5.39                                   2.14$\times$

  $$3 \times 10^{3}$$     10      100% (10/10)        \[72.3%, 100%\]     0.05 $\pm$ 0.05         11.65                             5.52                                   2.11$\times$

  $$5 \times 10^{3}$$     10      100% (10/10)        \[72.3%, 100%\]     0.06 $\pm$ 0.12         11.64                             5.89                                   1.98$\times$

  $$10^{4}$$              10      100% (10/10)        \[72.3%, 100%\]     0.00 $\pm$ 0.00         11.70                             6.39                                   1.83$\times$
  ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

MI$_{\text{BP}}$ = $\log_{2}(q)$ $,\$posterior entropy. MI$_{\text{1-layer}}$ is the mutual information between a single coefficient and its profiled observation on one layer, computed numerically from the circular Gaussian model (the standard formula $\frac{1}{2}\log_{2}(1 + \text{SNR})$ overestimates by \~0.25 bits due to discrete-uniform shaping loss). BP Gain = MI$_{\text{BP}}$ / MI$_{\text{1-layer}}$. The recovery threshold shifts from 90% at SNR$\times$N $= 2,000$ to 100% at SNR$\times$N $= 3,000$; the transition zone ($500$--$3,000$) exhibits high variance characteristic of loopy BP on cyclic factor graphs (e.g., at SNR$\times$N $= 500$, individual trials range from 0% to 100% BSR). Total: 120 trials across 8 operating points. Figure 2 illustrates the sigmoid recovery characteristic with Wilson 95% confidence intervals, showing the transition from partial recovery (30% at SNR$\times$N $= 500$) through the high-variance transition zone to deterministic recovery (100% at SNR$\times$N $\geq 3,000$), with the peak $2.24 \times$ BP gain annotated at the inflection point.

![Recovery sigmoid](media/image2.png){width="6.107023184601925in" height="4.100333552055993in"}

***Figure 2.** Full-key recovery rate vs. SNR*$\times$*N for the complete ML-KEM INTT factor graph (896 factors, 2,048 variables). Dots: empirical recovery rate; shaded region: Wilson 95% confidence intervals; dashed line: 100% recovery threshold at SNR*$\times$*N* $= 3,000$*. The sigmoid shape reflects the transition from loopy BP convergence failures (low SNR) to posterior concentration (high SNR).*

At SNR$\times$N $= 10^{3}$, a striking phenomenon emerges: Trial 1 achieves 100% BSR with MI$_{\text{BP}}$ $= 9.63$ bits, while Trial 2 achieves *0% BSR* (every MAP estimate wrong) with nearly identical MI$_{\text{BP}}$ $= 9.64$ bits. Both trials converge to posteriors of similar entropy (\~2.1 bits), but the second trial's posteriors concentrate on the *wrong* values. This is a well-known failure mode of loopy belief propagation on factor graphs with short cycles: the algorithm can converge to a fixed point of the Bethe free energy that does not correspond to the true posterior mode. The NTT butterfly interconnection pattern creates cycles of length 4--6, inducing message double-counting that pushes beliefs toward incorrect but self-consistent configurations. This failure mode is seed-dependent (some secret polynomials create harder inference problems than others) and disappears at higher SNR$\times$N where per-layer observations dominate the cycle-induced bias. At SNR$\times$N $\leq 500$, the failure mode is more severe: the BSR $= 37.5\%$ average indicates that some trials converge to posteriors that are concentrated but entirely incorrect (BSR $\approx 0\%$), pulling the average below the 50% mirror floor. The bimodal (100%/50%) characterization applies primarily in the $1,000$--$2,000$ transition zone.

To contextualize BP efficiency, we compute an information-theoretic upper bound on the mutual information extractable from the 7-layer factor graph. The *genie-aided bound* assumes perfect knowledge of all intermediate variables except the target Layer 0 coefficients: given a genie that reveals all $v_{\text{in}}$ values for each butterfly, the constraint $u_{\text{out}} = u_{\text{in}} + v_{\text{in}}$ allows $u_{\text{in}}$ to be determined from the observation of $u_{\text{out}}$ alone. Each of the 7 observed layers provides an independent MI$_{\text{1-layer}}$ contribution, yielding:

$\text{MI}_{\text{genie}} = min\left( \log_{2}(q),\mspace{6mu} 7 \times \text{MI}_{\text{1-layer}}(\text{SNR} \times N) \right)$

The genie bound reaches $\log_{2}(q)$ at SNR$\times$N $\approx 15,\$meaning that with perfect knowledge of intermediate values, even 15 traces would theoretically suffice for full recovery. At SNR$\times$N $= 500$, the genie bound is already saturated at $11.70$ bits ($3 \times 4.23 = 12.69 > 11.70$, so only 3 layers are needed). This establishes that the *information* for full recovery is abundantly present in the observations; the question is whether loopy BP can *extract* it.

The ratio MI$_{\text{BP}}$ / MI$_{\text{genie}}$ quantifies what fraction of the available information BP extracts. Note that MI$_{\text{genie}}$ is saturated at $\log_{2}(q) = 11.70$ bits for all SNR$\times$N $\geq 500$ in our tested range, so these efficiency figures represent MI$_{\text{BP}}$ / $\log_{2}(q)$, the fraction of the theoretical maximum, not a measurement of algorithmic optimality:

  -------------------------------------------------------------------------------------------------------------------------
  **SNR**$\times$**N**    **MI**$_{\text{1-layer}}$   **MI**$_{\text{genie}}$   **MI**$_{\text{BP}}$   **BP Efficiency**
  ----------------------- --------------------------- ------------------------- ---------------------- --------------------
  $$500$$                 4.23                        11.70                     7.65                   65.4%

  $$10^{3}$$              4.73                        11.70                     9.53                   81.5%

  $$1.5 \times 10^{3}$$   5.02                        11.70                     10.32                  88.2%

  $$5 \times 10^{3}$$     5.89                        11.70                     11.56                  98.8%

  $$10^{4}$$              6.39                        11.70                     11.65                  99.6%
  -------------------------------------------------------------------------------------------------------------------------

MI$_{\text{BP}}$ values in this table are from the L1+L3+L5+L7 (4-layer spread) configuration --- the minimum NC-satisfying topology (see Table 8). Table 7's all-layer MI$_{\text{BP}}$ values are higher (e.g., 9.24 vs 7.65 at SNR$\times$N $= 500$), reflecting the additional constraint density from 7 vs 4 observed layers. At SNR$\times$N $= 500$, BP's 4-layer extraction (7.65 bits) falls below the independent 2-layer bound ($2 \times 4.23 = 8.46$ bits), reflecting convergence failures where loopy BP's cycle-induced message double-counting destroys information rather than combining it.

This gap between genie-aided optimum and actual BP performance reflects the fundamental limitation of loopy BP on cyclic factor graphs: the NTT butterfly interconnection pattern creates short cycles (length 4--6) that cause message double-counting, preventing convergence to the true posterior.

To quantify which layer-observation topologies enable BP convergence, we run BP with restricted observation subsets at SNR$\times$N $= 5,000$ (5--30 independent seeds per configuration, 30 BP iterations). Table 8 reports full-key recovery rates with Wilson 95% confidence intervals for 16 representative configurations, organized by the structural factor for each tests. For L1+L3+L5+L7 and All, 30 replication seeds tighten the CIs. To validate the resulting necessary conditions framework exhaustively, we additionally evaluate all $\binom{7}{4} = 35$ possible 4-layer subsets (5--15 seeds each, 375+ trials total), covering every NC violation type at the minimum layer count. The primary ablation uses SNR$\times$N $= 5,000$ (above the recovery threshold) to isolate topology effects from noise-floor interactions; near-threshold cross-checks at SNR$\times$N $= 3,000$ confirm that the NC structure holds under stress.

***Table 8.** Layer ablation at SNR*$\times$*N* $= 5,000$ *(10 seeds each; 30 for starred configs). "Max Gap" is the longest run of consecutive unobserved layers between any pair of observed layers. Full-key = fraction of trials achieving BSR* $= 1.0$*.*

  --------------------------------------------------------------------------------------------------------------------------------------------
  **Configuration**                   **Layers**    $$k$$   **Max Gap**   **Full-Key**   **Wilson 95% CI**   **MI**$_{\text{BP}}$ **(bits)**
  ----------------------------------- ------------- ------- ------------- -------------- ------------------- ---------------------------------
  **Anchor-point controls**                                                                                  

  L1 only                             {1}           1       ---           0/10           \[0%, 27.8%\]       0.80

  L7 only                             {7}           1       ---           0/10           \[0%, 27.8%\]       0.00

  L2+L4+L6 (no L1)                    {2,4,6}       3       ---           0/10           \[0%, 27.8%\]       0.00

  L5--L7                              {5,6,7}       3       ---           0/10           \[0%, 27.8%\]       0.00

  **Gap topology**                                                                                           

  L1+L7                               {1,7}         2       5             0/10           \[0%, 27.8%\]       0.80

  L1+L2+L6+L7                         {1,2,6,7}     4       3             0/10           \[0%, 27.8%\]       ---

  L1+L2+L5+L7                         {1,2,5,7}     4       2             9/10           \[59.6%, 98.2%\]    ---

  **Minimum-observation threshold**                                                                          

  L1+L4+L7                            {1,4,7}       3       2             0/10           \[0%, 27.8%\]       2.95

  L1+L3+L4+L7                         {1,3,4,7}     4       2             9/10           \[59.6%, 98.2%\]    11.20

  **Diversity vs. locality**                                                                                 

  L1+L3+L5+L7 (spread)\*              {1,3,5,7}     4       1             **30/30**      \[88.6%, 100%\]     11.58

  L1--L4 (consecutive)                {1,2,3,4}     4       ---           0/10           \[0%, 27.8%\]       6.88

  L1--L5 (consecutive)                {1,2,3,4,5}   5       ---           0/10           \[0%, 27.8%\]       9.03

  L1--L6 (consecutive)                {1,...,6}     6       ---           2/10           \[5.7%, 51.0%\]     11.08

  All (L1--L7)\*                      {1,...,7}     7       0             **30/30**      \[88.6%, 100%\]     11.67

  **Cross-check**                                                                                            

  L1+L2+L3+L7                         {1,2,3,7}     4       3             0/10           \[0%, 27.8%\]       5.44

  L1+L3+L5+L6 (no L7)                 {1,3,5,6}     4       ---           2/10           \[5.7%, 51.0%\]     ---
  --------------------------------------------------------------------------------------------------------------------------------------------

A near-threshold cross-check at SNR$\times$N $= 3,000$ (10 seeds each) confirms the spread-vs-consecutive contrast under stress: L1+L3+L5+L7 achieves 9/10 full-key (Wilson CI \[59.6%, 98.2%\], MI $= 11.11$), while L1--L4 and L1--L6 both achieve 0/10, the spread configuration at $k = 4$ outperforms the consecutive configuration at $k = 6$.

Five structural insights emerge from these 500+ trials across 44 configurations, supplemented by 280+ targeted trials resolving the barrier structure of the conditions identified in the initial ablation (Table 8b):

**Table 8b.** Extended barrier characterization. K=7 results use q=3,329 (ML-KEM); K=8 results (F-series) use q = 97 (toy prime, exact BP is computationally infeasible at the ML-DSA modulus q=8,380,417).[^3] "FK" = full-key recovery rate. Wilson 95% CIs on all FK rates.

  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  **Experiment**                              **Configuration**          **Layers**    **SNR**$\times$**N**   **Iter**   **FK Rate**   **Wilson 95% CI**   **MI**$_{\text{BP}}$
  ------------------------------------------- -------------------------- ------------- ---------------------- ---------- ------------- ------------------- ----------------------
  **NC1: Input-layer structural barrier**                                                                                                                  

  NC1-A                                       L2--L7 (k=6, no L1)        {2,...,7}     50,000                 30         0/10          \[0%, 27.8%\]       0.00

  NC1-B                                       L2+L4+L6+L7 (k=4, no L1)   {2,4,6,7}     50,000                 30         0/10          \[0%, 27.8%\]       0.00

  **NC4: Layer-count barrier (trace-cost)**                                                                                                                

  G1                                          L1+L4+L7 (k=3)             {1,4,7}       50,000                 30         15/15         \[79.6%, 100%\]     11.70

  G2                                          L1+L4+L7 (k=3)             {1,4,7}       100,000                30         5/5           \[56.6%, 100%\]     11.70

  **NC3: Gap barrier (trace-cost)**                                                                                                                        

  TOP-A                                       L1+L2+L3+L7 (gap=3)        {1,2,3,7}     50,000                 30         12/12         \[75.8%, 100%\]     11.69

  **Computation-cost vs trace-cost**                                                                                                                       

  F1                                          K=8, k=5, gap=3            {1,2,3,7,8}   5,000                  30         10/20         \[29.9%, 70.1%\]    9.94

  F4                                          K=8, k=5, gap=3            {1,2,3,7,8}   5,000                  50         5/5           \[56.6%, 100%\]     11.66

  F2                                          K=8, k=4, gap=3            {1,2,6,8}     5,000                  30         1/20          \[0.9%, 23.6%\]     2.29

  F3                                          K=8, k=4, gap=2            {1,3,6,8}     5,000                  30         14/15         \[70.0%, 99.2%\]    11.50

  **Gap=1 S-curve (partial, in progress)**                                                                                                                 

  TOP-Bc                                      L1+L3+L5+L7 (gap=1)        {1,3,5,7}     2,000                  30         10/15         \[38.8%, 83.2%\]    10.50

  TOP-Bc                                      L1+L3+L5+L7 (gap=1)        {1,3,5,7}     3,000                  30         13/15         \[59.5%, 95.7%\]    11.27
  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

> *Input-layer structural barrier (NC1).* Layer 1 must be observed. It is the only layer directly adjacent to the secret Layer 0. Without L1, the factor graph structurally disconnects the target coefficient nodes from all observed factors: each input coefficient $a_{i}$ connects to exactly one butterfly factor (its layer-1 butterfly), and removing layer-1 observations isolates $a_{i}$ with degree zero in the inference graph. By construction, this disconnection implies that *no* factor-graph-based inference algorithm, not just BP, can extract information about individual coefficients from non-L1 observations.

Empirically, we tested 200 no-L1 trials across 8 configurations spanning $k \in \{ 1,3,4,5,6,7\}$, $K \in \{ 7,8\}$, and SNR$\times$N up to 500,000: all yield MI $\approx 0.000$, with BP converging in 1 iteration to uniform posteriors. The initial 20-trial moonshot (NC1-A with $k = 6$, NC1-B with $k = 4$, both at SNR$\times$N $= 50,000$) was extended to 140 additional trials (Table 8b) covering: (a) 40 more seeds per original config at SNR$\times$N $= 50,000$, (b) SNR$\times$N $= 500,000$ (10$\times$ more traces --- 10 seeds per config), (c) K=8 at SNR$\times$N $= 50,000$ (NC1-C: L2--L8 with $k = 7$; NC1-D: L2+L4+L6+L8 with $k = 4$), and (d) two additional K=7 configurations (NC1-E: L2+L3+L5+L6+L7; NC1-F: L3+L5+L7). All 160 trials (original + extension) yield 0 FK. The combined 95% Clopper-Pearson upper bound on the no-L1 FK rate is 1.8% (note: individual experiment CIs in Table 8b use the Wilson method).

NC1 is qualitatively distinct from all other conditions: it is the only barrier where MI $= 0$ (not merely low MI or low FK rate). All other NC violations produce non-zero MI that increases with SNR$\times$N --- they are cost multipliers. NC1 is a structural disconnection.

- All other barriers are trace-cost or computation-cost multipliers. Extended experiments (Table 8b) demonstrate that every previously identified "hard" barrier can be overcome:

<!-- -->

- NC4 ($k \geq 4$) is a trace-cost multiplier, not a hard barrier. L1+L4+L7 ($k = 3$, gap $= 2$) achieves 0/10 FK at SNR$\times$N $= 5,000$ but 15/15 FK at SNR$\times$N $= 50,000$ (G1) and 5/5 FK at 100,000 (G2). The \~10$\times$ trace increase overcomes the $k < 4$ barrier entirely.

- NC3 (gap $\leq 2$) is a trace-cost multiplier. L1+L2+L3+L7 (gap $= 3$) achieves 0/10 FK at SNR$\times$N $= 5,000$ but 12/12 FK at SNR$\times$N $= 50,000$ (TOP-A). Again, \~10$\times$ more traces suffice.

- Some barriers are computation-cost multipliers. F1 (K=8, $k = 5$, gap $= 3$) achieves 10/20 FK at 30 BP iterations but 5/5 FK at 50 iterations (F4) with identical trace data. This is not a trace-cost barrier, it is a computation-cost barrier overcome by running BP longer. Trace cost and computation cost are categorically different for a real attacker: traces require physical measurement time and equipment access; BP iterations require only CPU cycles.

- NC2 (output-layer observation) status. The initial ablation identified observation of L7 as a convergence-stabilization condition. The extended experiments (Table 8b) do not include dedicated NC2 isolation trials; however, all successful high-SNR configurations (G1, G2, TOP-A) include L7. Whether L7 can be replaced by other high-layer observations at sufficient trace budget remains untested. NC2 is conservatively classified as a cost-modulating condition pending dedicated ablation.

- Note on F2 vs F3. F2 ({1,2,6,8}, gap = 3) achieves only 1/20 FK while F3 ({1,3,6,8}, gap=2) achieves 14/15 FK at identical SNR$\times$N and iterations. The gap metric alone does not determine difficulty, specific layer positions matter. F2's layers cluster at the boundaries (L1--L2 and L6--L8), leaving a large unobserved interior; F3's layers are more evenly distributed. This is consistent with Insight 3 (observation diversity governs efficiency).

Tables 8b--8c supersede the initial ablation's characterization of NC3 and NC4 as necessary conditions for BP recovery. At the trace budgets tested in the initial ablation (SNR$\times$N $\leq 5,000$), these conditions appeared necessary; extended experiments reveal they are trace-cost multipliers that collapse at \~10$\times$ higher budgets. We retain the NC1--NC4 naming convention for cross-referencing but emphasize that only NC1 is structurally necessary.

**Table 8c.** Progressive barrier spectrum. All barriers conditional on L1 being observed. Trace-cost multiplier is relative to the gap=1, $k$=4 baseline (SNR$\times$N $\approx 3,000$ for 100% FK).

  -----------------------------------------------------------------------------------------------------------------------------
  **Barrier**               **Trace-Cost Multiplier**                         **Computation Cost**           **Nature**
  ------------------------- ------------------------------------------------- ------------------------------ ------------------
  Gap=1, $k$=4 (baseline)   1$\times$ (\~3K SNR$\times$N)                     30 iter                        Baseline

  Gap=2, $k$=4              \~2--2.5$\times$ (\~7.5K SNR$\times$N)            30 iter                        Soft trace-cost

  Gap=3, $k$=5              \~1$\times$                                       **50 iter required**           Computation-cost

  Gap=3, $k$=4              \~5--7$\times$ (\~15--20K SNR$\times$N)           30 iter                        Trace-cost

  $k$=3, gap=2              \~10$\times$ (\~50K)                              30 iter                        Trace-cost

  No L7 (NC2)               Not isolated --- conservatively: cost-modulator   ---                            Pending ablation

  **No L1**                 $\infty$ **(not overcome at 500K)**               **1 iter (instant failure)**   **Structural**
  -----------------------------------------------------------------------------------------------------------------------------

- Observation diversity governs efficiency*:* The contrast between spread and consecutive observations, L1+L3+L5+L7 (4 spread layers) achieves 30/30 full-key recovery (MI $= 11.58$), while L1--L4 (4 consecutive) achieves 0/10 (MI $= 6.88$), reflects the GS butterfly's stride-doubling: evenly spaced observations sample the factor graph's geometrically growing long-range dependencies, while consecutive observations redundantly constrain short-range correlations. The consecutive configuration requires 50% more layers, L1--L6 ($k = 6$), to approach the spread configuration's MI ($11.08$ vs $11.58$), and even then achieves only 2/10 full-key. For the attacker, targeting evenly spaced layers is far more efficient than exhaustively profiling adjacent layers.

- MI does not guarantee recovery: L1--L4 extracts 6.88 bits MI (59% of maximum) yet achieves 0% full-key recovery, every MAP estimate is wrong. L1--L5 extracts 9.03 bits (77%) with still 0% full-key. This "confident but wrong" failure mode is characteristic of loopy BP on cyclic factor graphs: the algorithm converges to a concentrated but incorrect posterior when the observation topology lacks sufficient constraint diversity. The minimum for any full-key recovery ($> 0\%$ rate) in the consecutive-only regime is $k = 6$ layers (L1--L6: 2/10); in the spread regime, $k = 4$ suffices (L1+L3+L5+L7: 30/30).

- Practical countermeasure hierarchy*.* The barrier structure yields a prioritized defense strategy for chip designers:

<!-- -->

- Priority 1: Mask L1 (the input butterfly layer). This creates a structural information barrier that no amount of traces can overcome under this attack model. It is the single most effective masking investment.
- Priority 2: Strategic gap masking**.** Masking any 3 consecutive mid-layers (e.g., L3--L5) forces a gap $\geq 3$ in the attacker's observation set. At SNR$\times$N $= 5,000$, this defeats BP recovery (0/10 FK for gap=3 topologies). However, this barrier is overcome at \~10$\times$ more traces (12/12 FK at SNR$\times$N $= 50,000$), so it provides quantified but not absolute protection.
- Priority 3: Full DOM-style masking. Masking all NTT/INTT layers with pipeline registers eliminates the dependence on shuffling and search space arguments entirely, the gold standard for maximum assurance.

The strategic gap masking recommendation from our initial analysis (R1, section 5.4) remains valid as a cost-effective defense: at the trace budgets typical of EM probing (\~1,000--10,000 traces), a gap $\geq 3$ provides effective protection. But the extended experiments show this protection degrades at higher trace counts. L1 masking does not degrade, it is structural.

For automated verification, the strategic gap masking countermeasure (R1, section 5.4) is verified exhaustively: for each of the 15 non-empty subsets of $\{ 1,2,6,7\}$, at least one NC is violated at the SNR$\times$N $= 5,000$ operating point. The 37-bit chain composition ($2^{46} \rightarrow 2^{23} \rightarrow 2^{9}$) is verified as a strict monotone pipeline. Both checks are included in the supplementary verification suite.

Table 9 shows a representative convergence trajectory at three SNR$\times$N operating points, illustrating the characteristic two-phase convergence of loopy BP on the NTT factor graph. These single-trial trajectories are confirmed by multi-seed replication: 15 independent trials (5 per SNR$\times$N point) all achieve 100% full-key recovery, with mean final MI of 11.65 (SNR$\times$N $= 3,000$), 11.70 ($5,000$), and 11.70 ($10^{4}$).

***Table 9.** BP convergence trajectory (representative trial). MI =* $\log_{2}(q)$ $-$ *entropy. Multi-seed confirmation: 15/15 trials (5 per operating point) achieve 100% full-key recovery.*

  -------------------------------------------------------------------------------------------------------------------------------------------------------
  **Iteration**    **SNR**$\times$**N** $= 3,000$               **SNR**$\times$**N** $= 5,000$               **SNR**$\times$**N** $= 10^{4}$  
  --------------- -------------------------------- ----------- -------------------------------- ----------- --------------------------------- -----------
                              H (bits)              MI (bits)              H (bits)              MI (bits)              H (bits)               MI (bits)

  1                            11.58                  0.12                  11.50                  0.20                   11.34                  0.36

  5                             9.60                  2.10                   8.36                  3.34                   7.03                   4.67

  10                            4.79                  6.91                   3.12                  8.58                   2.05                   9.65

  15                            1.65                  10.05                  0.79                  10.91                  0.46                   11.24

  20                            0.39                  11.31                  0.16                  11.54                  0.08                   11.62

  Final                    0.25 (30 iter)             11.45             0.00 (30 iter)             11.70             0.00 (26 iter)              11.70
  -------------------------------------------------------------------------------------------------------------------------------------------------------

All three trajectories show two-phase convergence: a *propagation phase* (iterations 1--10) where MI increases roughly linearly as messages traverse the factor graph, followed by a *concentration phase* (iterations 10+) where entropy drops exponentially as the posterior sharpens around the MAP estimate. Higher SNR$\times$N accelerates convergence: 30 iterations at SNR$\times$N $= 3,000$, 30 at $5,000$, and 26 at $10^{4}$, consistent with stronger per-layer observations enabling earlier posterior concentration. At SNR$\times$N $= 10^{4}$ (the highest tested point), 83% of extractable MI is obtained within 10 iterations (9.65 of 11.70 bits), with the remaining 17% requiring 16 more iterations due to the diminishing-returns dynamics of loopy BP convergence. The BP damping factor (0.5 in all reported experiments) is conservative: reducing damping to 0.1 yields faster convergence (17 vs 30 iterations to 100% full-key at SNR$\times$N $= 3,000$) and improved reliability (5/5 vs 4/5 full-key), suggesting that the thresholds in Table 7 are not optimized.

We report BP gain against two baselines. The *single-layer gain* MI$_{\text{BP}}$ / MI$_{\text{1-layer}}$ measures how much more information BP extracts compared to what a single observed layer provides, the relevant baseline for evaluating the designers' per-layer CPA model (C1/C2). This gain peaks at $2.24 \times$ (SNR$\times$N $= 10^{3}$) and decreases at both lower SNR ($2.19 \times$ at $500$, loopy BP convergence failures at the threshold) and higher SNR ($1.83 \times$ at $10^{4}$, ceiling effect as MI$_{\text{1-layer}}$ approaches $\log_{2}(q)$). The *normalized efficiency* MI$_{\text{BP}}$ / $(7 \times \text{MI}_{\text{1-layer}})$ measures BP's extraction relative to the 7-layer independent-channel upper bound, the maximum MI achievable if all 7 layers contributed independently. This normalized efficiency ranges from $0.26 \times$ at SNR$\times$N $= 10^{4}$ (near the $\log_{2}(q)$ ceiling, where both numerator and denominator saturate) to $0.32 \times$ at SNR$\times$N $= 10^{3}$. At the recovery threshold (SNR$\times$N $= 3,000$), normalized efficiency is $0.30 \times$, BP extracts roughly 30% of the independent-channel bound, yet this suffices for full coefficient recovery because $\log_{2}(q) = 11.70$ bits provides a generous information budget. For security assessment, the *genie-aided efficiency* (MI$_{\text{BP}}$ / MI$_{\text{genie}}$, where MI$_{\text{genie}}$ is capped at $\log_{2}(q)$) is the relevant metric: at the recovery threshold, BP achieves $11.65/11.70 = 99.6\%$ of the genie-aided bound. The $0.30 \times$ normalized figure reflects the sub-linearity of information combination across loopy BP's cyclic factor graph, not a security-relevant information gap.

The single-layer gain arises from two complementary mechanisms: (1) the 7 observed layers provide correlated but partially independent observations of the Layer 0 secret through the butterfly cascade, and (2) BP propagates information bidirectionally through the factor graph constraints, jointly resolving inter-coefficient dependencies that single-layer analysis cannot exploit. The sub-linear normalized efficiency ($0.26$--$0.32 \times$ rather than $1.0 \times$) reflects the fundamental limitation of loopy BP on cyclic factor graphs: message double-counting through short cycles (length 4--6) prevents full utilization of the available inter-layer information.

This result has four implications for the security margin analysis:

- *Exp H reconciliation:* Exp H's $> 50\%$ MAP error was an artifact of limited algebraic structure: the 2-layer, 8-coefficient subgraph has only 4 butterfly factors, providing insufficient constraint density for convergence. The full graph's 896 interconnected factors resolve this limitation completely, 100% coefficient recovery at SNR$\times$N where Exp H showed $> 95\%$ error.

- *BP-enhanced margin:* BP reaches the key-recovery threshold at lower SNR$\times$N than a single-layer model would require. The transition from partial to full recovery spans the range SNR$\times$N $= 500$--$3,000$: at $500$, 30% of trials achieve full-key recovery (Wilson CI \[10.8%, 60.3%\]); at $1.5 \times 10^{3}$, 85% (17/20); at $3 \times 10^{3}$, recovery is deterministic (10/10, confirmed by 15/15 multi-seed replication). The layer-ablation study (Table 8) shows that this gain requires evenly spaced layer observations satisfying the convergence conditions (NC1--NC4), precisely the structure available in Adams Bridge's unmasked INTT layers. Combined with the 37-bit BP-independent enumeration reduction (Exp G), full BP on the ML-KEM INTT reduces the effective search space from $2^{46}$ (designers' CPA model) to the 512 RSI enumeration runs. Rank-based key enumeration does not extend the recovery regime: at SNR$\times$N $= 1,500$ (where 15% of trials fail full-key recovery), enumeration with a $2^{20}$ budget recovers 0 of 6 failing trials, the MAP estimates in the "confident but wrong" failure mode are too distant from the true key (rank $> 128$ in all cases), confirming that BP success is a binary convergence phenomenon rather than a soft-margin one amenable to post-hoc enumeration.

- *Information-theoretic context:* The genie-aided bound establishes that far more information exists in the observations than BP currently extracts. BP efficiency rises from 65% at SNR$\times$N $= 500$ to 88% at SNR$\times$N $= 1,500$, reaching near-optimal extraction at the recovery threshold. The remaining 12--35% gap could potentially be closed by improved decoding algorithms (Generalized BP, Expectation Propagation), further reducing the required SNR$\times$N for full recovery.

- *Actionable countermeasure hierarchy.* The ablation study reveals a prioritized defense strategy. L1 masking creates a structural information barrier: the GS-NTT factor graph structurally disconnects input coefficient nodes when L1 is unobserved, yielding MI $= 0$ regardless of trace count (verified: 0/60 trials across 6 no-L1 configurations at up to SNR$\times$N $= 50,000$). All other barriers (gap topology, layer count) are trace-cost multipliers that can be overcome at \~10$\times$ more traces. Strategic gap masking (e.g., masking L3--L5, creating gap $\geq 3$) provides effective protection at moderate trace budgets (0/10 FK at SNR$\times$N $= 5,000$) at 43% of the cost of full masking, but this protection is overcome at higher trace counts (12/12 FK at SNR$\times$N $= 50,000$). For maximum assurance, L1 masking combined with strategic gap masking provides structural protection plus quantified trace-cost defense-in-depth.

Our analysis has some limitations:

\(i\) All BP experiments use profiled circular Gaussian observations on $\mathbb{Z}_{q}$, an idealized model where the noise distribution is known exactly and each coefficient leaks independently with identical SNR. Real power and EM side-channel leakage follows Hamming weight or Hamming distance models with multiplicative noise, clock jitter, measurement misalignment, and inter-coefficient coupling not captured by this model. Published SASCA literature suggests these factors degrade effective MI by 10--30% in profiled settings and substantially more for non-profiled attackers who must estimate the noise distribution from training traces \[10, 13\]. The BP thresholds reported here (e.g., 100% recovery at SNR$\times$N $= 3,000$) should therefore be interpreted as optimistic lower bounds on the required trace count; the true threshold on silicon hardware is likely higher. Note that all results in section 4.8 are simulation-only. The SASCA pipeline operates on RTL-simulated Hamming distance leakage, not silicon-measured traces. While this is the same abstraction level used by the designers' TVLA validation \[21\], real silicon introduces additional noise sources not captured by register-level models. The gap between simulated and silicon thresholds is an open empirical question (G10). We note, however, that NC1 (the structural barrier) is a topological property of the NTT factor graph, L1 adjacency to the masked layer derives from the Gentleman-Sande butterfly connectivity, not from the noise model. The cost-modulating conditions (NC2--NC4) likewise reflect graph topology: NC2 (L7 anchoring), NC3 (stride-doubling gap mechanism). While the quantitative thresholds (e.g., SNR$\times$N $= 3,000$ for 100% recovery) and cost multipliers (\~10$\times$ for NC3/NC4) are model-dependent, the qualitative topology-recovery relationship is expected to hold under alternative observation models, as it reflects the geometric structure of BP message routing through the butterfly cascade.

\(ii\) The gain factor is specific to ML-KEM's 7-layer INTT structure; ML-DSA's 8-layer INTT with $q = 8,380,417$ requires approximate BP (particle BP, neural BP) and may yield a different gain.

\(iii\) Each trial requires \~17 minutes on a single CPU core (Numba JIT-accelerated, Apple M2); GPU acceleration would reduce this to minutes per trial.

\(iv\) Loopy BP on cyclic factor graphs has no theoretical guarantee of convergence; the smooth convergence observed here is a property of the high-SNR regime.

\(v\) The layer-ablation results (Table 8) show that BP success is highly sensitive to which layers are observed, the attacker must achieve sufficient diversity and constraint density across the factor graph and must profile the correct intermediate layers to satisfy the convergence conditions (NC1--NC4).

The computational feasibility is next discussed. Under the profiled circular Gaussian observation model, the full BP enumeration, 512 RSI candidate runs, each consisting of 30 BP iterations on 896 butterfly factors, is computationally feasible. Each trial requires approximately 17 minutes on a consumer CPU (Apple M2, 6 cores, Numba JIT-compiled $O(q^{2})$ message passing). With GPU acceleration (conservatively 20$\times$ speedup from batch-parallel butterfly processing), the full 512-run enumeration completes in approximately 7 hours at a cloud cost of \~\$10 (A100 spot pricing). Memory requirements are modest: \~170 MB per trial (belief arrays over $\mathbb{Z}_{3329}$ for 2,048 variables, factor-to-variable messages for 896 factors, and precomputed sum tables). The 512 RSI trials are embarrassingly parallel with no inter-trial communication, enabling linear scaling across GPUs. For context, It is reported \[13\] that BP execution in seconds on 16-node software NTT subgraphs; our 2,048-node hardware NTT graph (112$\times$ more butterfly factors) scales to minutes per trial, well within feasible computational budgets, though silicon-measured traces may require significantly more data due to hardware noise factors not captured by the RTL simulation (section 5.3, G2, G10).

All experiments use publicly available inputs: FIPS 203 Algorithm 10 twiddle factors (Table 2), the Adams Bridge RTL \[27\] for SNR calibration. Factor graph construction follows Algorithm 10 exactly, verified against the standard's test vectors (200 random inputs, round-trip NTT/INTT consistency, 896/896 butterfly constraints). Monte Carlo experiments use fixed random seeds documented in the experiment scripts. The complete BP implementation (896-factor graph construction, Numba-accelerated message passing, circular Gaussian observation model) totals approximately 500 lines of Python and will be made available upon publication.

## 5. Discussions

The margin analysis in section 4 identifies a gap between the designers' implied security estimates and the bounds supported by published literature. We now discuss the broader implications of this finding, acknowledge the limitations of our analysis, and suggest directions for resolution.

### 5.1 Converging Independent Analyses

Three published independent analyses plus one preliminary formal study, conducted with different methodologies on different aspects of Adams Bridge, converge on the same architectural concern: the unmasked INTT layers present a side-channel attack surface that the current countermeasures may not adequately protect.

\(i\) Reference \[22\] demonstrated practical key recovery from Adams Bridge's FPGA implementation using approximately 10,000 traces, targeting unmasked modular reduction operations. Their attack confirms that the hardware leaks sufficient signal for correlation-based exploitation.

\(ii\) Reference \[24\] reported first-order TVLA leakage in Adams Bridge, demonstrating detectable information leakage under controlled measurement conditions.

\(iii\) Reference \[34\] using pre-silicon formal verification, identified 14 physically exploitable instances of share convergence across 5 masked modules, where Boolean shares are combined in combinational logic without pipeline registers. This analysis targets the masked layers and confirms that the masking implementation itself has structural vulnerabilities independent of the unmasked layer exposure analyzed in this paper.

In the present work for SASCA pipeline analysis, the empirical validation in section 4.8, using RTL-simulated leakage at the same abstraction level as the designers' own TVLA, demonstrates a 37-bit attack-model gap, reducing the enumeration complexity from the designers' $2^{46}$ CPA model to $2^{9}$ (512 RSI runs), independent of belief propagation. This pipeline-based analysis chains measured quantities (RTL SNR, MI per trace, RSI enumeration cost) into a composite margin that can be compared directly to the designers' claims.

The three published analyses, empirical CPA, empirical TVLA, and SASCA pipeline, were conducted independently using different tools and attack models. Preliminary formal verification \[34\] provides additional supporting evidence from a fourth methodology. Their convergence on a common architectural concern strengthens the case that the partial masking strategy warrants further scrutiny; the two published external analyses \[22, 24\] establish this convergence independently of \[34\].

Notice that the CPA attack paper \[22\] and the Adams Bridge architecture description \[21\] do not cross-reference each other, despite addressing the same design's side-channel properties.

### 5.2 Implications for PQC Hardware Design

The Adams Bridge case study illustrates a broader design tension in post-quantum hardware: the tradeoff between silicon area and side-channel security.

Masking the first INTT layer and relying on shuffling for the remaining layers reduces the area overhead from full masking. The designers note that a masked Barrett reduction implementation would incur non-trivial area overhead compared with their current unmasked design. This is a legitimate engineering decision, but the security margin of the unmasked layers should be evaluated against the same rigor applied to any cryptographic countermeasure, not assumed from search space arguments alone. For calibration: the designers' per-butterfly CPA complexity of $2^{46}$ for ML-DSA is smaller than the exhaustive search space of DES ($2^{56}$), a cipher retired precisely because its key space was insufficient against brute-force attacks. CPA complexity and key exhaustion are fundamentally different, CPA is a signal-processing attack requiring physical measurements, while key exhaustion is pure computation, and this analogy should not be overread. The comparison serves only to calibrate the order of magnitude: $2^{46}$, before any algebraic reduction, sits in a range that the cryptographic community has historically treated with caution for long-lived deployments. Our conclusion is that Partial masking is a cost tradeoff, not a security equivalence.

The margin gap matters. A security margin of $2^{59}$--$2^{63}$ (Scenario B) remains computationally significant, no published attacker can enumerate this space today. The concern is not immediate exploitability but the erosion of the architectural safety margin. In cryptographic engineering, security margins exist to absorb future algorithmic improvements, measurement advances, and deployment-specific signal amplification. A $2^{25}$--$2^{29}$ gap between the claimed and literature-supported margins for ML-DSA means the design's tolerance for such improvements is substantially narrower than intended. For a silicon root of trust with a multi-decade deployment lifecycle, and in the context of FIPS 140-3 or Common Criteria certification where margins must be justified against documented threat models, this gap represents the difference between a robust safety margin and a design whose security depends on the absence of a specific class of attack that the academic community is actively developing.

The partial masking strategy couples the security of unmasked layers to the shuffling countermeasure. If the shuffling is weaker than assumed, as the RSI vs full permutation analysis in section 4.2 suggests, the unmasked layers lose their primary protection. A more robust architecture would ensure that each NTT layer has independent side-channel protection, so that a weakness in one countermeasure does not expose multiple layers simultaneously.

We also conclude that shuffling supplements masking; it does not substitute for it. The published shuffling literature consistently treats shuffling as a complement to masking, not a replacement. The amplification of masking combined with shuffling was analyzed \[9\]. It was concluded that shuffling alone is "of limited help" against distinguishing attacks \[28\]. The Adams Bridge architecture inverts this relationship for layers 2--8 (ML-DSA) / 2--7 (ML-KEM), relying on shuffling as the primary protection.

### 5.3 Honest Gaps in Our Analysis

We identify sixteen limitations of our margin analysis. These are not rhetorical concessions, they represent genuine uncertainty that could shift the margins in either direction.

**G1: No hardware SASCA on Adams Bridge:** No published paper demonstrates a SASCA or belief propagation attack on Adams Bridge hardware with countermeasures enabled. This is the strongest pro-defender argument. Our section 4 analysis applies results from software platforms and simulated hardware models to argue that the potential for exploitation exists, but the demonstration does not. The margin between potential and demonstration is the central open question.

**G2: SW→HW transfer:** Most SASCA/BP results in section 4.5 were obtained on ARM Cortex-M4 software implementations \[11-12, 31\] or simulated hardware traces \[1, 13\]. Real hardware introduces clock jitter, power supply noise, and parallel computation interference that attenuate side-channel signals. The quantitative impact of these factors on NTT-specific attacks is unknown. Our margin analysis tags these transfers as extrapolation throughout, but the reader should weight pro-attacker scenarios (A and the mixed-assumption estimate) accordingly.

**G3: Hermelink uses simulated leakage:** The belief propagation results in section 4.2 \[13\] use a simulated Hamming weight leakage model, not measured hardware traces. While the BP algorithm itself is independent of the leakage source, the noise tolerance thresholds ($\sigma \leq 0.2$ for 16-node sub-graphs) may differ on real hardware where leakage models are imperfect and measurement noise is non-Gaussian.

**G4:** $\mathbf{S}^{\mathbf{L}}$ **vs** $\mathbf{S}^{\mathbf{2}}$ **is genuinely open:** The question of whether shuffling protection compounds multiplicatively across NTT layers ($S^{L}$, as the designers imply in C3) or additively ($S^{2}$ per layer, as the published model suggests) has not been definitively resolved in the literature for NTT-specific implementations. The $S^{L}$ model assumes that shuffling distributions are independent across layers and that an attacker must jointly resolve all layers simultaneously; the $S^{2}$ model assumes the attacker can process each layer independently, with shuffling adding a per-layer trace overhead. The gap between our Scenario B and the designers' implied estimates hinges on this question: $\approx 2^{61}$ vs $\approx 2^{88}$ for ML-DSA, and $\approx 2^{63}$ vs $\approx 2^{132}$ for ML-KEM. We do not claim to have resolved it.

**G5: SoC power delivery filtering:** Adams Bridge is designed for integration into the Caliptra silicon root of trust within a larger SoC. SoC power delivery networks provide RLC filtering \[23\] that attenuates power side-channel signals. The magnitude of this attenuation for NTT-specific leakage patterns has not been characterized in published literature.

**G6: Composite extrapolation.** Our margin scenarios in section 4.7 combine independently derived results from different papers, attack models, platforms, and noise regimes. The GS butterfly constraint comes from theoretical analysis \[11\], the SIS reduction from lattice theory \[29\], the RSI characterization from AES shuffling studies \[33\], and the KCA reduction from ML-KEM-specific analysis \[30\]. Composing these into a single margin estimate introduces coupling assumptions that have not been validated empirically. We do not claim the composite margins are precise predictions; they are order-of-magnitude bounds that isolate each literature-supported reduction and make the underlying assumptions explicit. This sensitivity-analysis approach, varying one assumption at a time while holding others fixed, is standard practice in cryptographic margin evaluation when full end-to-end attacks are unavailable. The value of Table 4 is not any single number but the explicit mapping from assumptions to margins, which allows designers and evaluators to substitute their own estimates for any contested parameter and derive the corresponding bound. The mixed-assumption estimate ($2^{30}$--$2^{40}$) should be interpreted as an order-of-magnitude indicator whose primary purpose is to demonstrate the sensitivity of the margin to each individual assumption.

**G7: We may underestimate hardware-specific defenses.** Real hardware introduces defensive factors not captured by software leakage models: clock jitter reduces temporal alignment precision, power supply filtering attenuates signal amplitudes, and parallel computation from other SoC components adds measurement noise. Additionally, our analysis focuses on power side-channel leakage; electromagnetic (EM) probing may bypass some SoC-level power filtering but requires different measurement setups and probe placement strategies not considered here. TVLA limitations in noisy environments \[35\] mean that both our attack extrapolations and the designers' TVLA-based defense claims carry hardware-specific uncertainty that neither party has resolved empirically.

**G8: ML-KEM**$\rightarrow$**ML-DSA BP transfer is unvalidated (section 4.8).** The belief propagation experiments in section 4.8.6 use ML-KEM ($q = 3,329$) because exact BP is computationally feasible at this modulus. ML-DSA ($q = 8,380,417$) requires approximate BP (particle BP, neural BP) with fundamentally different accuracy and convergence properties. The BP-enhanced margins (40--42 bits) are ML-KEM-validated; their transfer to ML-DSA is an open question. The 37-bit headline is BP-independent and applies to both algorithms.

**G9: Exp H subgraph limitation, resolved by Exp I (section 4.8).** Monte Carlo validation on the 2-layer ML-KEM subgraph (Exp H) showed MAP error $> 50\%$ at all tested SNR$\times$N values, the $< 5\%$ lattice threshold (Exp B) was not reached on this minimal graph. Exp I resolves this limitation**:** full-scale BP on the complete 7-layer, 256-coefficient ML-KEM INTT factor graph (896 butterfly factors, 120 trials across 8 operating points) achieves 0% MAP error at SNR$\times$N $= 3 \times 10^{3}$, with a peak $2.24 \times$ MI amplification factor over single-layer numerical MI predictions. A genie-aided bound shows 65--99% extraction efficiency, and layer-ablation analysis (900+ trials, 50+ configurations; exhaustive over all 35 four-layer subsets) identifies one structural barrier (NC1: L1 required) and three cost-modulating conditions (NC2--NC4) for BP convergence, observation topology, not count, governs recovery, with direct implications for cost-effective countermeasure design. The BP-enhanced margins are therefore empirically validated for ML-KEM. The ML-KEM$\rightarrow$ML-DSA transfer (G8) remains open.

**G10: RTL leakage may not predict silicon leakage (section 4.8).** The SASCA pipeline in section 4.8 operates on RTL-simulated Hamming distance leakage. While this is the same abstraction level used by the designers' TVLA validation \[21\], real silicon introduces gate-level switching, interconnect capacitance, and layout-dependent coupling not captured by register-level models. The RTL-derived SNR (0.0027 for butterflies) may over- or underestimate the physical signal.

**G11: Selection of literature sources.** Our margin synthesis draws on a specific set of published results. Different literature selections, or future publications, could shift the boundaries of individual scenarios. We have attempted to include the strongest results from both the pro-attacker and pro-defender perspectives but cannot claim exhaustive coverage of all relevant work.

**G12: Word-level vs bit-decomposed leakage.** Our leakage model assumes word-level Hamming distance over 23-bit (ML-DSA) or 12-bit (ML-KEM) coefficients. Bit-decomposed attacks \[12\] that target individual coefficient bits could yield different MI characteristics, potentially higher per-bit SNR but requiring bit-level templates. This alternative leakage model could reduce MI thresholds further; we do not analyze it here.

**G13: Profiling error from finite training traces.** The SASCA pipeline (section 4.8) assumes perfect profiling, the attacker knows the exact noise distribution and leakage model. In practice, profiling from finite training traces introduces template estimation error that degrades effective MI. Published SASCA analyses report 10--25% MI reduction from template mismatch in comparable settings \[11, 13\]. To quantify the impact: at 25% MI degradation, the 100% recovery threshold shifts from SNR$\times$N $= 3,000$ to \~4,000 (requiring \~1.48M traces, or \~10.3 days of EM acquisition at 100 traces/minute); at 30%, the threshold rises to \~4,300 (\~11.0 days). The attack remains practical even under pessimistic profiling assumptions, though with a \~33--43% increase in trace requirements. This affects all BP-enhanced margins (Scenario E) but not the BP-independent 37-bit headline, which depends on MI-theoretic bounds rather than BP convergence.

**G14: Higher-order attacks on the masked first layer.** This analysis focuses exclusively on the unmasked INTT layers (layers 2--7 for ML-KEM, 2--8 for ML-DSA). A complementary attack surface exists: higher-order DPA or higher-order SASCA targeting the first-order masked layer itself. If the masked layer's implementation is vulnerable to second-order attacks, as suggested by the structural share-convergence issues identified in \[34\], the entire masking strategy may be compromised independently of the unmasked-layer margins analyzed here. We do not evaluate higher-order attack feasibility in this paper.

**G15: Multi-target advantage.** With 256 coefficients per polynomial, a multi-target attacker who needs to recover any subset of coefficients (rather than all 256) gains up to $\log_{2}(256) = 8$ bits of advantage from the birthday-like reduction in the per-coefficient success probability required. This multi-target setting is not modeled in our analysis and could reduce effective thresholds in scenarios where partial coefficient recovery suffices for key recovery (e.g., via the SIS lattice reduction in Exp B, which requires only 32--64 coefficients).

**G16: Scope of machine verification.** Our verification suite confirms the algebraic and combinatorial backbone of the margin argument: the GS butterfly DOF reduction, the 37-bit chain composition, scenario margin calculations, and the combinatorial completeness of strategic gap masking. These are necessary conditions for the security argument but not sufficient: the probing model, the leakage-to-MI mapping (including the Gaussian channel capacity formula and its SNR instantiation), the Wilson CIs, and the BP convergence dynamics are validated empirically (section 4.8), not formally. The necessary conditions (NC1--NC4) are empirically validated topological properties; while the NC3 gap mechanism has a formal justification via Fourier analysis of the GS stride-doubling structure (Fisher $p = 0.0083$), the full NC framework is validated by exhaustive experimentation (50 configurations, 800+ trials), not by formal proof. The supplementary material distinguishes genuine formal proofs (whose negation would be satisfiable if the claim were wrong) from arithmetic consistency checks (verified constants).

**G17: NC1 structural barrier.** The NC1 structural barrier (MI $\approx 0$ without L1) rests on two legs: (a) a constructive graph-disconnection argument showing that removing L1 isolates every input coefficient at degree zero in the inference graph, and (b) empirical confirmation across 160 no-L1 trials (Clopper-Pearson 95% upper bound on FK rate: 1.8%). The graph-disconnection argument implies NC1 holds for any factor-graph-based inference algorithm but does not rule out attacks that exploit information outside the factor-graph model, for example, multivariate leakage correlations, transition effects between clock cycles, or electromagnetic coupling that creates information paths not represented in the butterfly factor graph. The NC1 claim is structural within the model; its transfer to physical hardware requires the model to faithfully represent the available side-channel information. A formal proposition and proof (rather than the informal constructive argument given here) would strengthen the claim for a verification-minded audience.

**G18: NC barrier characterization uses** $\mathbf{q}\mathbf{=}\mathbf{3}\mathbf{,}\mathbf{329}$ **(ML-KEM).** The barrier characterization experiments (Tables 8--8c) use $q = 3,329$ for K=7 and a toy prime $q = 97$ for K=8 (used in the F-series experiments where exact BP on the full ML-DSA modulus is computationally infeasible). The NC1 structural barrier depends on factor graph topology (determined by $n$ and the butterfly structure), not on the field arithmetic, and is therefore expected to be $q$-independent. The trace-cost multipliers for NC3/NC4 barriers depend on per-observation information content, which scales differently with $q$: larger $q$ means weaker per-observation constraints, likely increasing required trace counts. Our reported multipliers are therefore likely underestimates for the full ML-DSA modulus.

**G19: NC2 (output-layer observation) not isolated in extended experiments.** The extended barrier characterization (Table 8b) includes dedicated isolation experiments for NC1, NC3, and NC4, but not for NC2 (output-layer observation). All successful recovery configurations in Table 8b include L7; whether L7 can be replaced by other high-layer observations at sufficient trace budget remains untested. NC2 is conservatively classified as a cost-modulating condition pending dedicated ablation.

### 5.4 Recommendations

Based on this analysis, we identify three immediate design implications: (1) RSI shuffling (6 bits/layer) should not be relied upon as the sole protection for unmasked NTT layers; full random permutation or masking extension is recommended. (2) Security claims for partially masked NTT should be evaluated against SASCA/BP attack models, not per-butterfly CPA alone. (3) Pre-silicon TVLA should include temporal analysis restricted to unmasked computation phases. We propose four concrete steps to resolve the open questions.

**R1: Prioritized masking strategy.** The extended layer-ablation analysis (Tables 8--8c, section 4.8.9) reveals a clear investment hierarchy for NTT masking.

**R1a: Mask L1 (the input butterfly layer).** This is the single most effective masking investment. L1 is the only layer whose masking creates a structural information barrier: the factor graph disconnects input coefficient nodes when L1 is unobserved, yielding MI $= 0$ regardless of trace count (verified: 0/60 trials across 6 configurations at up to SNR$\times$N $= 50,000$).

**R1b: Strategic gap masking as cost-effective defense-in-depth.** Additionally masking any 3 consecutive mid-layers (e.g., L3--L5) forces a gap $\geq 3$ in the attacker's observation set. At moderate trace budgets (SNR$\times$N $\leq 5,000$), this defeats BP recovery, but at \~5--7$\times$ more traces (SNR$\times$N $\approx 15,000$--$20,000$), recovery becomes possible (10/10 FK at SNR$\times$N $= 20,000$ for gap=3 topologies). This guarantee is combinatorially exact: for any 3 consecutive masked layers $\{ L_{k},L_{k + 1},L_{k + 2}\}$ with $k \in \{ 2,3,4\}$, the largest observed layer below the masked band is $L_{k - 1}$ and the smallest above is $L_{k + 3}$, yielding a minimum gap of $(k + 3) - (k - 1) - 1 = 3$, violating NC3 regardless of which subset the attacker observes. The supplementary verification suite exhaustively confirms that no subset of $\{ 1,2,6,7\}$ satisfies all four NCs. For L3--L5 specifically, the attacker's maximum observation set is $\{$L1, L2, L6, L7$\}$ (gap $= 3$); all subsets inherit this gap or a larger one ($\{$L1, L6, L7$\}$: gap $= 4$; $\{$L1, L2, L7$\}$: gap $= 3$). Empirically, the strongest attacker topology {L1, L2, L6, L7} achieves 0/10 full-key recovery (Table 8), and all weaker topologies inherit this failure by construction. This "strategic gap masking" reduces the INTT masking overhead to 3/7 layers (43%), a 57% cost reduction in INTT masking compared to full 7-layer masking, a practical middle ground between the current 1-layer masking (insufficient) and full masking (expensive). Total chip area savings depend on the relative cost of INTT masking versus other protected operations (e.g., point-wise multiplication, which is already fully masked). For maximum assurance, full DOM-style masking with pipeline registers on all NTT/INTT layers remains the gold standard, eliminating the dependence on shuffling and search space arguments entirely. The designers report a 24% area saving from their current unmasked Barrett implementation, suggesting that the incremental cost of masking additional INTT layers is non-trivial but bounded; strategic gap masking (3 of 7 layers) would incur roughly 43% of the full masking overhead for the INTT portion. The designers' own Barrett masking plan suggests this direction is under consideration \[21\].

**R2: Publish hardware SASCA experiments.** The central open question, whether SASCA/BP attacks transfer from software to hardware NTT implementations, can only be resolved empirically. Our RTL-simulated pipeline (section 4.8) demonstrates a 37-bit gap at the register-transfer level; validating this on FPGA with measured traces would either confirm the gap in silicon or quantify the RTL-to-silicon attenuation factor. We encourage the research community to conduct belief propagation attacks on FPGA implementations of partially masked NTT, using measured (not simulated) traces. A positive result would validate our pro-attacker scenarios and Scenario E; a negative result would strengthen the defense significantly and bound the RTL-to-silicon transfer gap.

**R3: Temporal TVLA analysis.** The designers' TVLA evaluation \[21\] reports aggregated results across all clock cycles. TVLA restricted to the unmasked INTT layers, specifically, the $\approx 2,240$ (ML-DSA) or $\approx 1,344$ (ML-KEM) clock cycles identified in Table 2, would provide targeted leakage characterization for the most vulnerable computation phases. Extended trace counts to $10^{7}$--$10^{8}$, increasingly standard for high-assurance TVLA in recent CHES/TCHES publications, may reveal leakage currently below the detection threshold at $10^{6}$ traces.

**R4: Pre-silicon formal verification.** Formal verification tools that analyze RTL source code for side-channel vulnerabilities can identify structural weaknesses before silicon fabrication \[19\]. For partially masked designs, formal analysis can verify that masking boundaries are correctly implemented and that unmasked regions do not inadvertently leak share information through combinational paths. As demonstrated in this paper, theory-matched SMT verification, routing finite field properties to CVC5's QF_FF logic and combinatorial constraints to Z3, can machine-verify the algebraic foundations of security margin arguments, offering a reusable methodology for evaluating NTT masking claims prior to tape-out.

## 6. Conclusion

We have presented a systematic security margin analysis of the partial NTT masking strategy in Adams Bridge, evaluating the designers' claimed CPA complexity bounds against published side-channel literature across seven analysis tracks with confidence-rated evidence, and validating the literature-derived margins through an original SASCA attack pipeline grounded in RTL-simulated leakage (section 4.8). Our main findings is that under the strongest literature-supported pro-defender assumptions (Scenario B, per section 4.7 Table 4), the effective security margins fall in the range $2^{59}$--$2^{63}$ for ML-DSA and $2^{61}$--$2^{65}$ for ML-KEM, roughly $2^{25}$--$2^{29}$ and $2^{67}$--$2^{71}$ below the designers' implied estimates of $\approx 2^{88}$ and $\approx 2^{132}$, respectively. Under pro-attacker assumptions (Scenario A), margins drop to $2^{15}$--$2^{27}$ (ML-DSA) / $2^{16}$--$2^{30}$ (ML-KEM). Our empirical validation (Scenario E) demonstrates a 37-bit attack-model gap versus the designers' $2^{46}$ per-butterfly CPA model, reducing enumeration from $2^{46}$ to $2^{9}$ (512 RSI runs), independent of belief propagation, by chaining RTL-derived mutual information, layer-by-layer RSI enumeration, and lattice sensitivity analysis. The conservative (no-BP) pipeline does not achieve key recovery: despite collecting sufficient MI in theory, Exp H shows that loopy BP on the minimal subgraph yields $> 50\%$ per-coefficient error, exceeding the lattice recovery threshold. With BP-enhanced margins (MI-predicted, not empirically validated), the pipeline projects $100\%$ lattice success. This analysis identifies a potential threat model gap: the designers' verification scope (non-specific TVLA) does not encompass the profiled SASCA threat model analyzed here, yet the security argument treats the unmasked layers as adequately protected. The arithmetic backbone of this analysis, GS butterfly DOF reduction, chain compositions, scenario calculations, and gap masking completeness, is machine-verified by multi-theory SMT (Z3 + CVC5 finite field theory; supplementary material), with CVC5 resolving the critical GS butterfly injectivity universally over $\mathbb{F}_{q}$ in under 100ms where integer arithmetic times out.

We reached four structural observations. (i) The RSI shuffling implementation provides 6 bits of entropy per layer (64 combined orderings from a dual-level hierarchy), not the $\log_{2}(64!) \approx 296$ bits of a full random permutation over the same elements, a distinction that directly affects whether the $S^{L}$ multiplicative compounding claimed in the design's analysis is achievable. (ii) The Gentleman-Sande butterfly's algebraic structure constrains the independent degrees of freedom per butterfly pair, reducing the per-butterfly hypothesis space below the designers' $2^{46}$ (ML-DSA) and $2^{96}$ (ML-KEM) estimates (given one butterfly output, the other is algebraically determined). (iii) 87.5% (7/8 layers, ML-DSA) and 85.7% (6/7 layers, ML-KEM) of the NTT computation is executed without masking protection, relying entirely on shuffling for side-channel resistance in a regime where published literature consistently treats shuffling as a complement to masking rather than a substitute. (iv) The SASCA pipeline eliminates per-coefficient enumeration entirely, replacing the $2^{23}$ (ML-DSA) or $2^{48}$ (ML-KEM) hypothesis space with $O(q^{2})$ belief propagation messages per butterfly, a fundamentally different complexity model than the per-butterfly CPA framing. (For ML-DSA, $O(q^{2}) \approx 7 \times 10^{13}$ per message makes exact BP infeasible; approximate methods are required, as discussed in section 4.8.6.

A full-scale BP validation was achieved. Experiment I resolves the most significant empirical gap in prior versions of this analysis: belief propagation on the complete 7-layer, 256-coefficient ML-KEM INTT factor graph (896 butterfly factors, 2,048 variable nodes) achieves 100% coefficient recovery at SNR$\times$N $= 3 \times 10^{3}$ (10/10 trials; confirmed by 15/15 multi-seed replication), with a peak $2.24 \times$ MI amplification over the single-layer baseline ($0.30 \times$ normalized efficiency against the 7-layer independent-channel bound; 99.6% genie-aided efficiency at the recovery threshold, BP extracts sub-linearly but captures nearly all theoretically available information). A genie-aided information-theoretic bound shows the observations contain sufficient MI for recovery at SNR$\times$N as low as 15; BP extracts 65--99% of this optimum. Layer-ablation analysis (900+ trials, 50+ configurations) reveals that BP convergence depends on observation topology rather than count: 4 evenly spread layers (L1+L3+L5+L7) achieve 30/30 full-key recovery, while 4 consecutive layers (L1--L4) achieve 0/10 despite extracting 6.88 bits MI. One structural barrier and three cost-modulating conditions govern BP convergence: the input layer (L1) creates a structural information barrier where MI $\approx 0.000$ across 160 no-L1 trials (8 configurations, $k = 1$--$7$, $K \in \{ 7,8\}$, SNR$\times$N up to 500,000; Clopper-Pearson 95% upper bound: 1.8%), while the remaining conditions, output-layer observation (NC2), gap topology (NC3), and layer count (NC4), are overcome by \~10$\times$ more traces or additional computation. This provides defenders with a prioritized countermeasure hierarchy: L1 masking creates structural protection; strategic gap masking (3 consecutive mid-layers, 43% overhead) adds quantified trace-cost defense-in-depth that is effective at moderate trace budgets but not absolute. Under the simulated profiled model, the full enumeration (512 RSI runs) is computationally feasible: \~7 hours on a single GPU at \~\$10 cloud cost. This confirms that the BP-enhanced margins (40--42 bits) are achievable with sufficient graph structure, the Exp H subgraph limitation was an artifact of the minimal test graph, not a fundamental BP limitation.

This study does not demonstrate key recovery on hardware, present new attacks, or claim that Adams Bridge is insecure in deployed settings. The SASCA pipeline (section 4.8) demonstrates a security margin gap, not a complete attack: while Exp I achieves full coefficient recovery on a simulated ML-KEM factor graph, the ML-KEM BP results have not been validated for ML-DSA's larger modulus ($q = 8,380,417$ requires approximate BP), and all leakage measurements are RTL-simulated rather than silicon-measured. Specifically, the Exp I results (100% coefficient recovery, NC1 structural barrier, countermeasure hierarchy) are validated only for ML-KEM ($q = 3,329$, $n = 256$). ML-DSA's 23-bit modulus ($q = 8,380,417$) increases the per-message BP complexity from $O(q^{2}) \approx 10^{7}$ to $\approx 7 \times 10^{13}$, requiring approximate inference methods whose convergence properties may differ. The 37-bit enumeration reduction (Exp G) and RSI shuffling analysis (Exps A, C) apply equally to both algorithms. The central gap in our analysis, and the strongest argument for the defense, remains the absence of any published SASCA attack on hardware NTT implementations with countermeasures enabled.

Two empirical investigations would substantially narrow the remaining margin uncertainty: (1) hardware SASCA experiments on FPGA implementations of partially masked NTT using measured traces, which would either confirm the 37-bit Scenario E attack-model gap in silicon or quantify the RTL-to-silicon attenuation factor; and (2) temporal TVLA analysis restricted to the unmasked INTT layers with extended trace counts ($10^{7}$--$10^{8}$). A third direction, belief propagation on the full ML-DSA factor graph using approximate inference methods (particle BP, neural BP), would resolve the ML-KEM$\rightarrow$ML-DSA transfer question; Exp I has already validated BP on the full ML-KEM graph, demonstrating $2.24 \times$ peak MI amplification over the single-layer baseline ($0.30 \times$ normalized efficiency) and 100% recovery at SNR$\times$N $= 3,000$ under the simulated profiled model. On the design side, the layer-ablation analysis offers a cost-effective alternative: strategic gap masking of 3 consecutive mid-layers (43% masking overhead) creates a gap $\geq 3$ that defeats SASCA, providing a 57% cost reduction versus full masking while maintaining BP-verifiable security guarantees. For maximum assurance, extending DOM-style masking with pipeline registers to all NTT/INTT layers would eliminate the dependence on shuffling and search space arguments entirely, resolving the margin question architecturally.

Partial masking of NTT operations is a legitimate engineering tradeoff between silicon area and side-channel security. This paper's contribution is not to declare that tradeoff is wrong, but to provide the community with a structured, evidence-rated analysis, now validated by original RTL-derived experiments, of the security margins it entails. Designers, evaluators, and certification bodies can then make informed decisions about acceptable risks in PQC hardware deployments.

# Code and Data Availability

The code and data supporting this paper are publicly available at https://github.com/rayiskander2406/ntt-security-margins-arXiv-2604.03813 under the Apache 2.0 license, with an archival snapshot of version v1.0.0 deposited on Zenodo at https://doi.org/10.5281/zenodo.19508454. The repository contains the factor-graph construction, RTL-derived TVLA/SNR extraction, belief-propagation solvers, layer-ablation sweep configurations, and the raw JSON/CSV outputs underlying every figure and table in Section 4.8, together with a reproducibility driver that regenerates the headline results (100% coefficient recovery at SNR×N = 3,000; multi-seed ablation; convergence sweeps) under seed-controlled random state.

The companion structural-dependency verification paper (reference \[34\]) is archived at https://doi.org/10.5281/zenodo.19625392.

# References

  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  \[1\]    D. Carrera Rodriguez, P. Music, and L. De Meyer, \"SASCA on Locally Masked NTT for ML-KEM,\" *In IACR Communications in Cryptology (CiC),* 2025.
  -------- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
  \[2\]    The National Institute of Standards and Technology, U.S. Department of Commerce, \"Module-Lattice-Based Key-Encapsulation Mechanism Standard,\" NIST Federal Information Processing Standards (FIPS) 203, doi: 10.6028/NIST.FIPS.203, 2024.

  \[3\]    The National Institute of Standards and Technology, Standard U.S. Department of Commerce,, \"Module-Lattice-Based Digital Signature Mechanism,\" NIST Federal Information Processing Standards (FIPS) 204, doi: org/10.6028/NIST.FIPS.204, 2024.

  \[4\]    O. S. Sonbul, M. Rashid, , & A. Y. Jaffar, \"Accelerating CRYSTALS-Kyber: High-Speed NTT Design with Optimized Pipelining and Modular Reduction,\" *Electronics,* vol. 14, no. 11, 2026.

  \[5\]    ARDIANTO SATRIAWAN, INFALL SYAFALNI, RELLA MARETA, ISA ANSHORI, WERVYAN SHALANNANDA and ALEAMS BARRA, \"Conceptual Review on Number Theoretic Transform and Comprehensive Review on Its Implementations,\" *IEEE Access,* vol. 11, pp. 70288- 70316, 2023, DOI: 10.1109/ACCESS.2023.3294446.

  \[6\]    Y. Ishai, A. Sahai, and D. Wagner, \"Private Circuits: Securing Hardware against Probing Attacks,\" *In Proc. CRYPTO, LNCS, Springer,* 2003.

  \[7\]    H. Gross, S. Mangard, and T. Korak, \"Domain-Oriented Masking: Compact Masked Hardware Implementations with Arbitrary Protection Order,\" *In Proc. ACM Workshop on Theory of Implementation Security (TIS @ CCS),* 2016.

  \[8\]    Nicolas Veyrat-Charvillon, Marcel Medwed, Stéphanie Kerckhof, François-Xavier Standaert, \"Shuffling against side-channel attacks: a comprehensive study with cautionary note,\" in *ASIACRYPT\'12: Proceedings of the 18th international conference on The Theory and Application of Cryptology and Information Security, Pages 740 - 757*, 2012.

  \[9\]    Matthieu Rivain, Emmanuel Prouff, Julien Doget, \"Higher-Order Masking and Shuffling for Software Implementations of Block Ciphers,\" in *Cryptographic Hardware and Embedded Systems - CHES 2009, 11th International Workshop*, Lausanne, Switzerland, September 6-9, 2009.

  \[10\]   N. Veyrat-Charvillon, B. Gérard, and F.-X. Standaert, \"Soft Analytical Side-Channel Attacks (SASCA),,\" in *Proceedings of ASIACRYPT 2014 (LNCS, Springer) and is available as Cryptology ePrint Archive Report 2014/410.* , 2014.

  \[11\]   R. Primas, P. Pessl, and S. Mangard, \"Single-Trace Side-Channel Attacks on Masked Lattice-Based Encryption,\" *Cryptology ePrint Archive, Paper 2017/594,* 2017.

  \[12\]   P. Pessl and R. Primas, \"More Practical Single-Trace Attacks on the Number Theoretic Transform,\" in *In Proc. LATINCRYPT, LNCS, Springer*, 2019.

  \[13\]   J. Hermelink, J. Streit, B. Strieder, and F. Thieme, \"Adapting Belief Propagation to Counter Shuffling of NTTs,\" in *In IACR Transactions on Cryptographic Hardware and Embedded Systems (TCHES)*, 2023.

  \[14\]   G. Goodwill, Benjamin Jun, J. Jaffe, P. Rohatgi, \"A testing methodology for side ­ channel resistance validation,\" https://api.semanticscholar.org/CorpusID:16852899, 2011.

  \[15\]   T. Schneider, A. Moradi, \" Leakage Assessment Methodology-A Clear Roadmap for Side-Channel Evaluations.,\" in *CHES. In LectureNotes in Computer Science; Springer: Berlin/Heidelberg, Germany, Volume 9293, pp. 495--513.*, 2015.

  \[16\]   P. Ravi, A. Chattopadhyay, S. Bhasin, and A. Mendelson, \"Side-Channel Countermeasures for Lattice-Based Post-Quantum Cryptography,\" *ACM Computing Surveys,* vol. 56, no. 11, pp. 1-39, 2024, doi: 10.1145/3660634.

  \[17\]   Gilles Barthe, Sonia Belaid, Gaetan Cassiers, Pierre-Alain Fouque, Benjamin Gregoire, Francois-Xavier Standaert, \"maskVerif: Automated Verification of Higher-Order Masking in Presence of Physical Defaults,\" in *European Symposium on Research in Computer Security (pp. 300-318)* , Springer, Cham., Luxembourg,, 2019.

  \[18\]   R. Bloem, H. Groß, R. Iusupov, B. Könighofer, S. Mangard, and J. Winter, \"Formal Verification of Masked Hardware Implementations in the Presence of Glitches,\" in *Proc. EUROCRYPT, LNCS, Springer*, 2018.

  \[19\]   B. Gigerl, V. Hadzic, R. Primas, S. Mangard, and R. Bloem, \"Coco: Co-Design and Co-Verification of Masked Software Implementations on CPUs,\" in *Proc. USENIX Security*, 2021.

  \[20\]   David Knichel, Pascal Sasdrich, Amir Moradi, \"SILVER -- Statistical Independence and Leakage Verification,\" in *ASIACRYPT 2020* , Daejeon, South Korea (Virtual), 2020.

  \[21\]   M. Bisheh-Niasar, E. Karabulut, B. Upadhyayula, A. Norris, and L. Pillilli, \"Adams Bridge Accelerator: Bridging the Post-Quantum Transition,\" *Cryptology ePrint Archive, Report 2026/256,* 2026.

  \[22\]   E. Karabulut and R. Azarderakhsh, \"Side-Channel Attack on Adams Bridge,\" in *Cryptology ePrint Archive, Report 2025/009. In Proc. IEEE International Symposium on Hardware Oriented Security and Trust (HOST)*, 2025.

  \[23\]   H. Wang and W. Yueh, \"SoC Power Delivery Network Analysis,\" in *Proc. ACM/IEEE Design Automation Conference (DAC)*, 2013.

  \[24\]   M.-J. O. Saarinen, \"Adams Bridge TVLA Analysis,\" in *Presentation at Hardwear.io USA*, 2025.

  \[25\]   V. Lapôtre, C. Chavet, G. Harcha, and P. Coussy, \"Exploring the Contribution of Hardware Shuffling in Securing Low-Cost Symmetric Encryption Devices against Power-Based Side-Channel Attacks,\" *ACM Transactions on Reconfigurable Technology and Systems (TRETS),* vol. 18, no. 4, 2025.

  \[26\]   D. Xu, K. Wang, and J. Tian., \" A Hardware-Friendly Shuffling Countermeasure Against Side-Channel Attacks for Kyber,\" *IEEE Transactions on Circuits and Systems II: Express Briefs,* vol. 72, no. 3, p. 504--508, 2025.

  \[27\]   \"CHIPS Alliance. Adams Bridge RTL Source. https://github.com/chipsalliance/adams-bridge. Apache 2.0 License,\" \[Online\].

  \[28\]   D. Pay and F.-X. Standaert, \"Keep it Simple: Refreshing the NTT of Kyber's Decapsulation to Prevent Plaintext-Checking Side-Channel Attacks,\" *IACR Transactions on Cryptographic Hardware and Embedded Systems (TCHES),* vol. 2026, no. 1, p. 472--499, 2026.

  \[29\]   Y. Qiao, M. Wang, Y. Yu, and W. Wang, \"Improved Side-Channel Key Recovery for ML-DSA via SIS Lattice Reduction,\" *Cryptology ePrint Archive, Report 2023/1866,* 2023.

  \[30\]   E. A. Bock, G. Banegas, C. Brzuska, Ł. Chmielewski, K. Puniamurthy, and M. Šorf, \"Breaking DPA-Protected Kyber via the Pair-Pointwise Multiplication,\" in *Cryptology ePrint Archive, Report 2023/551. In Proc. INDOCRYPT, LNCS, Springer*, 2023.

  \[31\]   E. Tosun, K. Gaj, and P. Schaumont., \" Higher-Order CPA on Masked Dilithium Software Implementation,\" *IACR Communications in Cryptology (CiC),* 2025.

  \[32\]   Olivier Bronchain, Melissa Azouaoui, Mohamed ElGhamrawy, Joost Renes, Tobias Schneider, \"Exploiting Small-Norm Polynomial Multiplication with Physical Attacks: Application to CRYSTALS-Dilithium,\" *IACR Transactions Cryptographic Hardware and Embedded Systems,* vol. 2, pp. 359-383, 2024 DOI:10.46586/tches.v2024.i2.359-383..

  \[33\]   N. Veyrat-Charvillon, B. Gérard, M. Renauld, and F.-X. Standaert, \"An Optimal Key Enumeration Algorithm and its Application to Side-Channel Attacks,\" *Proc. SAC, LNCS, Springer, 2012. Extended version in Journal of Cryptographic Engineering,* 2013.

  \[34\]   R. Iskander and K. Kirah, \"Structural Dependency Analysis for Masked NTT Hardware: Scalable Pre-Silicon Verification of Post-Quantum Cryptographic Accelerators,\" *arXiv preprint arXiv:2604.15249,* 2026.

  \[35\]   A. Moradi and T. Schneider, \"Side-Channel Analysis in Practice: Leakage Assessment and Exploitation under Noisy Conditions,\" *IACR Transactions on Cryptographic Hardware and Embedded Systems (TCHES),* 2018.

  \[36\]   Shaowei Wang, Jin Li, Changyu Dong, Jin Li, Zhili Zhou, Jinhui Xu, Zikai Alex Wen, \"Side-channel Attacks and New Principles in the Shuffle Model of Differential Privacy,\" *IEEE Transactions on Information Forensics and Security,* vol. 20, pp. 6515-6528, 2025. DOI: 10.1109/tifs.2025.3571661.
  -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

[^1]: Our structural vulnerability disclosure to the Adams Bridge designers preceded their publication of ePrint 2026/256 \[1\]. The disclosure and the present analysis are independent: the disclosure addresses masked-layer implementation flaws, while this paper evaluates unmasked-layer security margins.

[^2]: An earlier version of this analysis used fewer trials (n=5), fewer BP iterations (20), and incorrect twiddle factors. The current results use FIPS 203 Algorithm 10 twiddle factors ($v_{\text{out}} = \zeta \cdot (v_{\text{in}} - u_{\text{in}})$, indices counting down from 127), larger sample sizes ($n = 10$--$20$), and 30 BP iterations. The qualitative findings (sigmoid recovery curve, two-phase convergence) are consistent; the corrected twiddle factors shift the 100% threshold from SNR$\times$N $= 2,000$ to $3,000$, and the layer-ablation structure changes substantially (see Table 8).

[^3]: The NC1 structural barrier depends on factor graph *topology* (determined by n and the butterfly structure), not field arithmetic, and is expected to be q-independent. Trace-cost multipliers may differ at larger q (see G18).
