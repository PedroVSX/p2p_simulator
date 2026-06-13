"""
benchmark.py — Executa N rodadas de cada algoritmo e calcula
min, max, média e taxa de sucesso de mensagens trocadas.
Útil para comparar os algoritmos de forma estatística robusta,
especialmente o random_walk que varia a cada execução.
"""

import copy
import statistics
from network import Network
from search import ALGORITHMS


def _fresh_network(network: Network) -> Network:
    """
    Retorna uma cópia profunda da rede com caches zerados.
    Necessário para que cada rodada comece do zero.
    """
    net = Network()
    net.min_neighbors = network.min_neighbors
    net.max_neighbors = network.max_neighbors
    for node_id, node in network.nodes.items():
        from node import Node
        n = Node(node_id)
        n.neighbors = list(node.neighbors)
        n.resources = set(node.resources)
        n.cache = {}          # cache zerado — cada rodada é independente
        net.nodes[node_id] = n
    return net


def run_benchmark(network: Network, origin_id: str, resource_id: str,
                  ttl: int, rounds: int = 20, silent: bool = True) -> dict:
    """
    Executa `rounds` rodadas para cada algoritmo e retorna um dicionário
    com as estatísticas agregadas.

    Parâmetros:
        network     — rede P2P já validada
        origin_id   — nó de origem da busca
        resource_id — recurso buscado
        ttl         — TTL da busca
        rounds      — número de execuções por algoritmo (padrão: 20)
        silent      — se True, suprime a saída detalhada de cada busca

    Retorno:
        {
          "flooding": {
              "rounds": 20,
              "found": 20,
              "success_rate": 100.0,
              "min_msgs": 12,
              "max_msgs": 12,
              "avg_msgs": 12.0,
              "median_msgs": 12.0,
              "min_nodes": 8,
              "max_nodes": 8,
              "avg_nodes": 8.0,
          },
          ...
        }
    """
    results = {}

    for algo_name, algo_func in ALGORITHMS.items():
        msgs_list  = []
        nodes_list = []
        found_count = 0

        for _ in range(rounds):
            net_copy = _fresh_network(network)

            # Suprime print_summary durante o benchmark
            if silent:
                stats = _run_silent(algo_func, net_copy, origin_id, resource_id, ttl)
            else:
                stats = algo_func(net_copy, origin_id, resource_id, ttl)

            msgs_list.append(stats.message_count)
            nodes_list.append(len(stats.nodes_visited))
            if stats.found:
                found_count += 1

        results[algo_name] = {
            "rounds":       rounds,
            "found":        found_count,
            "success_rate": round(100 * found_count / rounds, 1),
            "min_msgs":     min(msgs_list),
            "max_msgs":     max(msgs_list),
            "avg_msgs":     round(statistics.mean(msgs_list), 1),
            "median_msgs":  round(statistics.median(msgs_list), 1),
            "min_nodes":    min(nodes_list),
            "max_nodes":    max(nodes_list),
            "avg_nodes":    round(statistics.mean(nodes_list), 1),
        }

    return results


def _run_silent(func, network, origin_id, resource_id, ttl):
    """Executa a busca sem imprimir o sumário no terminal."""
    import io, sys
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        stats = func(network, origin_id, resource_id, ttl)
    finally:
        sys.stdout = old_stdout
    return stats


def print_benchmark(results: dict, origin_id: str, resource_id: str, ttl: int):
    sep = "═" * 90
    thin = "─" * 90
    rounds = next(iter(results.values()))["rounds"]

    print(f"\n{sep}")
    print(f"  BENCHMARK  —  recurso={resource_id}  origem={origin_id}  "
          f"TTL={ttl}  rodadas={rounds}")
    print(thin)

    header = (f"  {'Algoritmo':<25} {'Sucesso':>8} "
              f"{'Min msg':>8} {'Max msg':>8} {'Média':>8} {'Mediana':>8} "
              f"{'Min nós':>8} {'Max nós':>8} {'Média nós':>10}")
    print(header)
    print(thin)

    for algo, r in results.items():
        print(
            f"  {algo:<25} {r['success_rate']:>7.1f}% "
            f"{r['min_msgs']:>8} {r['max_msgs']:>8} {r['avg_msgs']:>8} {r['median_msgs']:>8} "
            f"{r['min_nodes']:>8} {r['max_nodes']:>8} {r['avg_nodes']:>10}"
        )

    print(sep)
    print()


def plot_benchmark(results: dict, origin_id: str, resource_id: str,
                   ttl: int, output_path: str = "benchmark.png"):
    """
    Gera um gráfico de barras comparando min/média/max de mensagens
    entre os algoritmos.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    algos = list(results.keys())
    mins   = [results[a]["min_msgs"]  for a in algos]
    maxs   = [results[a]["max_msgs"]  for a in algos]
    avgs   = [results[a]["avg_msgs"]  for a in algos]
    rates  = [results[a]["success_rate"] for a in algos]
    rounds = results[algos[0]]["rounds"]

    x = np.arange(len(algos))
    width = 0.25

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(
        f"Benchmark — recurso={resource_id}  origem={origin_id}  "
        f"TTL={ttl}  ({rounds} rodadas por algoritmo)",
        fontsize=12, fontweight="bold"
    )

    # --- Gráfico 1: min / média / max de mensagens ---
    bars_min = ax1.bar(x - width, mins, width, label="Mínimo",  color="#2ECC71", alpha=0.85)
    bars_avg = ax1.bar(x,         avgs, width, label="Média",   color="#3498DB", alpha=0.85)
    bars_max = ax1.bar(x + width, maxs, width, label="Máximo",  color="#E74C3C", alpha=0.85)

    ax1.set_title("Mensagens trocadas por algoritmo", fontsize=11)
    ax1.set_ylabel("Número de mensagens")
    ax1.set_xticks(x)
    ax1.set_xticklabels(algos, rotation=15, ha="right", fontsize=9)
    ax1.legend()
    ax1.grid(axis="y", linestyle="--", alpha=0.4)

    # Rótulos nas barras
    for bar in [*bars_min, *bars_avg, *bars_max]:
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width() / 2., h + 0.1,
                 f"{h:.0f}", ha="center", va="bottom", fontsize=7)

    # --- Gráfico 2: taxa de sucesso ---
    colors = ["#2ECC71" if r == 100 else "#F39C12" if r >= 50 else "#E74C3C"
              for r in rates]
    bars_rate = ax2.bar(algos, rates, color=colors, alpha=0.85, edgecolor="white")
    ax2.set_title("Taxa de sucesso (%)", fontsize=11)
    ax2.set_ylabel("% de buscas que encontraram o recurso")
    ax2.set_ylim(0, 115)
    ax2.set_xticklabels(algos, rotation=15, ha="right", fontsize=9)
    ax2.grid(axis="y", linestyle="--", alpha=0.4)

    for bar, rate in zip(bars_rate, rates):
        ax2.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 1,
                 f"{rate:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Gráfico do benchmark salvo em: {output_path}")