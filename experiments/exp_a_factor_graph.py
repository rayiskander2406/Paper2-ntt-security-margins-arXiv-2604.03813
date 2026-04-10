#!/usr/bin/env python3
"""
Experiment A: Factor-Graph Complexity Baseline
Section 4.8.1 — "Partial NTT Masking in PQC Hardware: A Security Margin Analysis"

Constructs the Adams Bridge NTT/INTT factor graph from architecture parameters,
computes graph-theoretic complexity metrics, and compares to Hermelink et al.
(TCHES 2023) to demonstrate BP structural feasibility.

Parameters from: arXiv:2604.03813, FIPS 203/204, Adams Bridge RTL.
RSI = 64 states per layer (6-bit entropy) per arXiv:2604.03813 Section 4.6.

Reference: arXiv:2604.03813, Section 4.8.1.
"""

import json
import math
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import networkx as nx


# --- Constants ----------------------------------------------------------------

MLDSA_N = 256
MLDSA_Q = 8_380_417
MLDSA_BITS = 23
MLDSA_LAYERS = 8

MLKEM_N = 256
MLKEM_Q = 3_329
MLKEM_BITS = 12
MLKEM_LAYERS = 7

BUTTERFLIES_PER_LAYER = 128  # n/2 = 256/2

# RSI: 16 chunks x 4 start indices = 64 patterns (arXiv:2604.03813 Section 4.6)
RSI_STATES = 64
RSI_ENTROPY_BITS = 6  # log2(64)

# Hermelink et al. TCHES 2023 reference values
HERMELINK_SUBGRAPH_VARS = 32  # ~16-node sub-graph, Figure 7c
HERMELINK_SUBGRAPH_FACTORS = 16
HERMELINK_SUBGRAPH_EDGES = 64
HERMELINK_BP_RUNS_PER_LAYER = 2**16  # worst-case RP enumeration


@dataclass
class FactorGraphMetrics:
    """Metrics computed for a single factor graph configuration."""
    algorithm: str
    shuffle_mode: str  # "none", "rsi", "rp_hypothetical"
    shuffle_states_per_layer: int
    n_layers: int
    n_variable_nodes: int
    n_factor_nodes: int
    n_butterfly_factors: int
    n_shuffle_factors: int
    n_edges: int
    graph_diameter: int
    treewidth_upper_bound: int
    treewidth_method: str
    bp_runs_per_layer: int
    bp_runs_total_layerwise: int
    bp_runs_joint: float  # can be very large
    construction_time_s: float


def build_intt_factor_graph(
    n: int,
    n_layers: int,
    butterflies_per_layer: int,
    shuffle_states: int,
    include_shuffle_nodes: bool = True,
) -> nx.Graph:
    """
    Build the NTT/INTT factor graph as a bipartite graph.

    Variable nodes: "V_L_i" = coefficient i at layer boundary L
        L ranges from 0 (input) to n_layers (output)
        i ranges from 0 to n-1

    Factor nodes: "BF_L_j" = butterfly j at layer L
        L ranges from 0 to n_layers-1
        j ranges from 0 to butterflies_per_layer-1

    Shuffle factor nodes (if included): "SH_L" = shuffle node at layer L
        Connects to all variable nodes at layer L's input boundary.

    Each butterfly BF_L_j connects to:
        - V_L_{2j} and V_L_{2j+1} (inputs from layer L)
        - V_{L+1}_{2j} and V_{L+1}_{2j+1} (outputs to layer L+1)

    Note: The actual NTT butterfly connectivity pattern depends on the
    bit-reversal / decimation structure. For Gentleman-Sande INTT, layer L
    has stride 2^L. We use the standard GS connectivity.
    """
    G = nx.Graph()

    # Add variable nodes (coefficient values at each layer boundary)
    for layer in range(n_layers + 1):
        for coeff in range(n):
            node_id = f"V_{layer}_{coeff}"
            G.add_node(node_id, bipartite=0, node_type="variable", layer=layer)

    # Add butterfly factor nodes with GS connectivity
    for layer in range(n_layers):
        stride = 2 ** layer  # GS butterfly stride
        group_size = 2 * stride

        bf_idx = 0
        for group_start in range(0, n, group_size):
            for offset in range(stride):
                idx_a = group_start + offset
                idx_b = group_start + offset + stride

                bf_node = f"BF_{layer}_{bf_idx}"
                G.add_node(bf_node, bipartite=1, node_type="butterfly", layer=layer)

                # Input edges (from layer L)
                G.add_edge(bf_node, f"V_{layer}_{idx_a}")
                G.add_edge(bf_node, f"V_{layer}_{idx_b}")
                # Output edges (to layer L+1)
                G.add_edge(bf_node, f"V_{layer+1}_{idx_a}")
                G.add_edge(bf_node, f"V_{layer+1}_{idx_b}")

                bf_idx += 1

        assert bf_idx == butterflies_per_layer, (
            f"Layer {layer}: expected {butterflies_per_layer} butterflies, got {bf_idx}"
        )

    # Add shuffle factor nodes (connect to all coefficients at layer input)
    if include_shuffle_nodes and shuffle_states > 1:
        for layer in range(n_layers):
            sh_node = f"SH_{layer}"
            G.add_node(sh_node, bipartite=1, node_type="shuffle",
                       layer=layer, states=shuffle_states)
            for coeff in range(n):
                G.add_edge(sh_node, f"V_{layer}_{coeff}")

    return G


def compute_treewidth_upper_bound(G: nx.Graph) -> tuple[int, str]:
    """
    Compute upper bound on treewidth using greedy min-fill heuristic.

    Exact treewidth is NP-hard for large graphs. We use NetworkX's
    treewidth_min_fill_in which provides an upper bound via greedy
    elimination ordering.

    Returns: (treewidth_upper_bound, method_description)
    """
    n_nodes = G.number_of_nodes()

    if n_nodes > 5000:
        tw, _ = nx.algorithms.approximation.treewidth_min_degree(G)
        method = f"NetworkX treewidth_min_degree (greedy upper bound, {n_nodes} nodes)"
    else:
        tw, _ = nx.algorithms.approximation.treewidth_min_fill_in(G)
        method = f"NetworkX treewidth_min_fill_in (greedy upper bound, {n_nodes} nodes)"

    return tw, method


def analyze_factor_graph(
    algorithm: str,
    n: int,
    n_layers: int,
    shuffle_mode: str,
    shuffle_states: int,
) -> FactorGraphMetrics:
    """Build factor graph and compute all metrics for one configuration."""
    t0 = time.time()

    include_shuffle = shuffle_states > 1
    G = build_intt_factor_graph(
        n=n,
        n_layers=n_layers,
        butterflies_per_layer=BUTTERFLIES_PER_LAYER,
        shuffle_states=shuffle_states,
        include_shuffle_nodes=include_shuffle,
    )

    # Count nodes by type
    var_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "variable"]
    bf_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "butterfly"]
    sh_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "shuffle"]

    n_var = len(var_nodes)
    n_bf = len(bf_nodes)
    n_sh = len(sh_nodes)
    n_edges = G.number_of_edges()

    # Graph diameter (longest shortest path)
    if nx.is_connected(G):
        diameter = nx.diameter(G)
    else:
        diameter = max(
            nx.diameter(G.subgraph(c))
            for c in nx.connected_components(G)
            if len(c) > 1
        )

    # Treewidth upper bound
    tw, tw_method = compute_treewidth_upper_bound(G)

    # BP runs
    bp_per_layer = shuffle_states
    bp_total_layerwise = shuffle_states * n_layers
    bp_joint = float(shuffle_states ** n_layers)

    elapsed = time.time() - t0

    return FactorGraphMetrics(
        algorithm=algorithm,
        shuffle_mode=shuffle_mode,
        shuffle_states_per_layer=shuffle_states,
        n_layers=n_layers,
        n_variable_nodes=n_var,
        n_factor_nodes=n_bf + n_sh,
        n_butterfly_factors=n_bf,
        n_shuffle_factors=n_sh,
        n_edges=n_edges,
        graph_diameter=diameter,
        treewidth_upper_bound=tw,
        treewidth_method=tw_method,
        bp_runs_per_layer=bp_per_layer,
        bp_runs_total_layerwise=bp_total_layerwise,
        bp_runs_joint=bp_joint,
        construction_time_s=round(elapsed, 3),
    )


def format_comparison_table(results: list[FactorGraphMetrics]) -> str:
    """Format results as a markdown comparison table."""
    lines = []
    lines.append("| Metric | " + " | ".join(
        f"{r.algorithm} ({r.shuffle_mode})" for r in results
    ) + " | Hermelink [13] |")
    lines.append("|--------|" + "|".join("-" * 20 for _ in results) + "|----------------|")

    def fmt_large(v):
        if v > 1e12:
            exp = len(str(int(v))) - 1
            return f"~2^{exp}"
        return f"{v:,}"

    rows = [
        ("Variable nodes", [str(r.n_variable_nodes) for r in results], f"~{HERMELINK_SUBGRAPH_VARS}"),
        ("Factor nodes", [str(r.n_factor_nodes) for r in results], f"~{HERMELINK_SUBGRAPH_FACTORS}"),
        ("Edges", [f"{r.n_edges:,}" for r in results], f"~{HERMELINK_SUBGRAPH_EDGES}"),
        ("Shuffle states/layer", [str(r.shuffle_states_per_layer) for r in results], "16! (RP)"),
        ("BP runs/layer", [str(r.bp_runs_per_layer) for r in results], f"up to 2^16"),
        ("BP runs (layer-by-layer)", [str(r.bp_runs_total_layerwise) for r in results],
         f"up to 2^16 x L"),
        ("BP runs (joint)", [fmt_large(r.bp_runs_joint) for r in results], "intractable"),
        ("Graph diameter", [str(r.graph_diameter) for r in results], "N/A"),
        ("Treewidth (upper bound)", [str(r.treewidth_upper_bound) for r in results], "N/A"),
    ]

    for label, vals, hermelink in rows:
        lines.append(f"| {label} | " + " | ".join(vals) + f" | {hermelink} |")

    return "\n".join(lines)


def main():
    print("=" * 70)
    print("EXPERIMENT A: Factor-Graph Complexity Baseline")
    print("=" * 70)
    print()

    configurations = [
        # (algorithm, n, layers, shuffle_mode, shuffle_states)
        ("ML-DSA", MLDSA_N, MLDSA_LAYERS, "none", 1),
        ("ML-DSA", MLDSA_N, MLDSA_LAYERS, "RSI-64", RSI_STATES),
        ("ML-KEM", MLKEM_N, MLKEM_LAYERS, "none", 1),
        ("ML-KEM", MLKEM_N, MLKEM_LAYERS, "RSI-64", RSI_STATES),
    ]

    results = []
    for algo, n, layers, shuffle_mode, shuffle_states in configurations:
        print(f"Building {algo} factor graph (shuffle={shuffle_mode}, S={shuffle_states})...")
        metrics = analyze_factor_graph(algo, n, layers, shuffle_mode, shuffle_states)
        results.append(metrics)
        print(f"  Nodes: {metrics.n_variable_nodes} var + {metrics.n_factor_nodes} factor")
        print(f"  Edges: {metrics.n_edges:,}")
        print(f"  Diameter: {metrics.graph_diameter}")
        print(f"  Treewidth <= {metrics.treewidth_upper_bound}")
        print(f"  BP runs (layer-by-layer): {metrics.bp_runs_total_layerwise}")
        print(f"  Time: {metrics.construction_time_s}s")
        print()

    # Comparison table
    print("=" * 70)
    print("COMPARISON TABLE")
    print("=" * 70)
    table = format_comparison_table(results)
    print(table)
    print()

    # Key findings
    print("=" * 70)
    print("KEY FINDINGS")
    print("=" * 70)

    mldsa_none = next(r for r in results if r.algorithm == "ML-DSA" and r.shuffle_mode == "none")
    mldsa_rsi = next(r for r in results if r.algorithm == "ML-DSA" and r.shuffle_mode == "RSI-64")
    mlkem_none = next(r for r in results if r.algorithm == "ML-KEM" and r.shuffle_mode == "none")
    mlkem_rsi = next(r for r in results if r.algorithm == "ML-KEM" and r.shuffle_mode == "RSI-64")

    print(f"\n1. Treewidth: ML-DSA(none)={mldsa_none.treewidth_upper_bound}, "
          f"ML-DSA(RSI)={mldsa_rsi.treewidth_upper_bound}, "
          f"ML-KEM(none)={mlkem_none.treewidth_upper_bound}, "
          f"ML-KEM(RSI)={mlkem_rsi.treewidth_upper_bound}")
    tw_threshold = 30
    all_above = all(r.treewidth_upper_bound > tw_threshold for r in results)
    print(f"   All > {tw_threshold}? {'YES -- exact inference intractable, BP justified' if all_above else 'NO -- check configurations'}")

    print(f"\n2. RSI structural impact (diameter change):")
    print(f"   ML-DSA: {mldsa_none.graph_diameter} (none) -> {mldsa_rsi.graph_diameter} (RSI)")
    print(f"   ML-KEM: {mlkem_none.graph_diameter} (none) -> {mlkem_rsi.graph_diameter} (RSI)")

    print(f"\n3. RSI vs Hermelink comparison:")
    hermelink_runs = HERMELINK_BP_RUNS_PER_LAYER
    rsi_factor = hermelink_runs / RSI_STATES
    print(f"   RSI: {RSI_STATES} BP runs/layer vs Hermelink: {hermelink_runs} BP runs/layer")
    print(f"   Factor: {rsi_factor:.0f}x simpler (approx 2^{int(math.log2(rsi_factor))} reduction)")
    print(f"   ML-DSA total layer-by-layer: {mldsa_rsi.bp_runs_total_layerwise} BP runs")
    print(f"   ML-KEM total layer-by-layer: {mlkem_rsi.bp_runs_total_layerwise} BP runs")

    # Save results
    output_dir = Path(__file__).parent.parent / "evidence"
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "factor_graph_metrics.json"
    json_data = {
        "experiment": "A: Factor-Graph Complexity Baseline",
        "reference": "arXiv:2604.03813, Section 4.8.1",
        "parameters": {
            "mldsa": {"n": MLDSA_N, "q": MLDSA_Q, "bits": MLDSA_BITS, "layers": MLDSA_LAYERS},
            "mlkem": {"n": MLKEM_N, "q": MLKEM_Q, "bits": MLKEM_BITS, "layers": MLKEM_LAYERS},
            "butterflies_per_layer": BUTTERFLIES_PER_LAYER,
            "rsi_states": RSI_STATES,
            "rsi_entropy_bits": RSI_ENTROPY_BITS,
        },
        "hermelink_reference": {
            "subgraph_vars": HERMELINK_SUBGRAPH_VARS,
            "subgraph_factors": HERMELINK_SUBGRAPH_FACTORS,
            "subgraph_edges": HERMELINK_SUBGRAPH_EDGES,
            "bp_runs_per_layer": HERMELINK_BP_RUNS_PER_LAYER,
        },
        "results": [asdict(r) for r in results],
    }
    with open(json_path, "w") as f:
        json.dump(json_data, f, indent=2)
    print(f"\nJSON saved to: {json_path}")

    print(f"\nExperiment A complete.")
    return results


if __name__ == "__main__":
    results = main()
