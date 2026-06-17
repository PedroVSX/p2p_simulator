"""
benchmark.py — Executa N rodadas de cada algoritmo e calcula
min, max, média e taxa de sucesso de mensagens trocadas.
Útil para comparar os algoritmos de forma estatística robusta,
especialmente o random_walk que varia a cada execução.
"""

import copy
import random
import statistics
from network import Network
from search import ALGORITHMS


def _get_all_resources(network: Network) -> set:
    all_res = set()
    for node in network.nodes.values():
        all_res.update(node.resources)
    return all_res


def _pick_random_search(network: Network):
    """Retorna (origin_id, resource_id) aleatórios onde a origem não tem o recurso."""
    all_res = list(_get_all_resources(network))
    if not all_res:
        return None, None

    # Tenta 100 vezes encontrar uma combinação válida
    for _ in range(100):
        res = random.choice(all_res)
        potential_origins = [node_id for node_id, node in network.nodes.items()
                            if res not in node.resources]
        if potential_origins:
            return random.choice(potential_origins), res
    return None, None


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
                  ttl: int, rounds: int = 20, silent: bool = True,
                  sequential: bool = False) -> dict:
    """
    Executa `rounds` rodadas para cada algoritmo e retorna um dicionário
    com as estatísticas agregadas.

    Parâmetros:
        network     — rede P2P já validada
        origin_id   — nó de origem da busca (ou None para aleatório)
        resource_id — recurso buscado (ou None para aleatório)
        ttl         — TTL da busca
        rounds      — número de execuções por algoritmo (padrão: 20)
        silent      — se True, suprime a saída detalhada de cada busca
        sequential  — se True, NÃO reseta o cache entre as rodadas do mesmo algoritmo.
                       Útil para ver o efeito dos algoritmos informados acumulando cache.

    Retorno:
        {
          "flooding": { ... },
          ...
        }
    """
    results = {}

    # Se origem ou recurso não informados, usaremos buscas variadas a cada rodada
    random_mode = (origin_id is None or resource_id is None)

    # Pré-gera as buscas para que todos os algoritmos testem os mesmos cenários
    search_scenarios = []
    if random_mode:
        for _ in range(rounds):
            o, r = _pick_random_search(network)
            search_scenarios.append((o, r))
    else:
        search_scenarios = [(origin_id, resource_id)] * rounds

    for algo_name, algo_func in ALGORITHMS.items():
        msgs_list  = []
        nodes_list = []
        found_count = 0

        # Para cada algoritmo, começamos com uma rede zerada.
        # Se for sequencial, usaremos ESSA MESMA instância em todas as rodadas do algoritmo.
        net_instance = _fresh_network(network)

        for i in range(rounds):
            o_round, r_round = search_scenarios[i]
            if not o_round or not r_round:
                continue

            if sequential:
                current_net = net_instance
            else:
                current_net = _fresh_network(network)

            # Suprime print_summary durante o benchmark
            if silent:
                stats = _run_silent(algo_func, net_instance if sequential else current_net,
                                    o_round, r_round, ttl)
            else:
                stats = algo_func(net_instance if sequential else current_net,
                                  o_round, r_round, ttl)

            msgs_list.append(stats.message_count)
            nodes_list.append(len(stats.nodes_visited))
            if stats.found:
                found_count += 1

        if not msgs_list:
            continue

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
            "raw_msgs":     msgs_list,
            "raw_nodes":    nodes_list,
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

    res_str = resource_id if resource_id else "Vários (Aleatório)"
    ori_str = origin_id if origin_id else "Vários (Aleatório)"

    print(f"\n{sep}")
    print(f"  BENCHMARK — TTL={ttl}  rodadas={rounds}")
    print(f"  (recurso={res_str}  origem={ori_str})")
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
                   ttl: int, config_name: str = "", output_path: str = "benchmark.png"):
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

    res_str = resource_id if resource_id else "Vários (Aleatório)"
    ori_str = origin_id if origin_id else "Vários (Aleatório)"
    conf_str = f" perfil={config_name}" if config_name else ""

    fig.suptitle(
        f"Benchmark — {conf_str}  TTL={ttl}  ({rounds} rodadas)\n"
        f"recurso={res_str}  origem={ori_str}",
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
    ax2.set_xticks(range(len(algos)))
    ax2.set_xticklabels(algos, rotation=15, ha="right", fontsize=9)
    ax2.grid(axis="y", linestyle="--", alpha=0.4)

    for bar, rate in zip(bars_rate, rates):
        ax2.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 1,
                 f"{rate:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Gráfico do benchmark salvo em: {output_path}")


def plot_histogram(results: dict, origin_id: str, resource_id: str,
                   ttl: int, config_name: str = "", output_path: str = "histogram.png"):
    """
    Gera um histograma da distribuição de mensagens para cada algoritmo.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import math

    algos = list(results.keys())
    num_algos = len(algos)
    
    # Define layout da grade (ex: 2x2 para 4 algoritmos)
    cols = 2
    rows = math.ceil(num_algos / cols)

    fig, axes = plt.subplots(rows, cols, figsize=(12, 4 * rows), squeeze=False)
    
    res_str = resource_id if resource_id else "Vários (Aleatório)"
    conf_str = f" perfil={config_name}" if config_name else ""
    
    fig.suptitle(
        f"Distribuição de Mensagens — {conf_str}  TTL={ttl}\n"
        f"recurso={res_str}  ({results[algos[0]]['rounds']} rodadas)",
        fontsize=14, fontweight="bold"
    )

    colors = ["#3498DB", "#E74C3C", "#2ECC71", "#F39C12", "#9B59B6"]

    for i, algo in enumerate(algos):
        r = i // cols
        c = i % cols
        ax = axes[r][c]
        
        data = results[algo]["raw_msgs"]
        color = colors[i % len(colors)]
        
        ax.hist(data, bins=15, color=color, alpha=0.7, edgecolor='black')
        ax.set_title(f"Algoritmo: {algo}", fontsize=12, color=color, fontweight="bold")
        ax.set_xlabel("Número de mensagens")
        ax.set_ylabel("Frequência (rodadas)")
        ax.grid(axis='y', linestyle='--', alpha=0.3)
        
        # Adiciona linha da média
        avg = results[algo]["avg_msgs"]
        ax.axvline(avg, color='black', linestyle='dashed', linewidth=1.5, label=f"Média: {avg}")
        ax.legend(fontsize=8)

    # Remove eixos vazios se houver
    for i in range(num_algos, rows * cols):
        fig.delaxes(axes[i // cols][i % cols])

    plt.tight_layout(rect=[0, 0.03, 1, 0.93])
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Histograma do benchmark salvo em: {output_path}")


# ──────────────────────────────────────────────────────────────────────────────
# ANÁLISE MESTRA (Análise Comparativa Profunda)
# ──────────────────────────────────────────────────────────────────────────────

def run_full_analysis(rounds: int = 30, seed: int = 42):
    """
    Executa uma análise profunda cobrindo todos os perfis e múltiplos TTLs.
    Gera vários gráficos comparativos em out/analysis/.
    """
    import os
    import numpy as np
    
    output_dir = "out/analysis"
    os.makedirs(output_dir, exist_ok=True)
    
    random.seed(seed)
    # Tenta importar numpy aqui para garantir que está disponível
    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass

    profiles = {
        "leve":   "config/leve.yaml",
        "medio":  "config/medio.yaml",
        "pesado": "config/pesado.yaml"
    }
    ttls = [2, 4, 6, 8]
    
    # data[perfil][ttl][algo] = {stats}
    data_independent = {}
    data_sequential = {}

    print(f"\nIniciando Análise Mestra ({rounds} rodadas por cenário)...")

    for profile_name, path in profiles.items():
        print(f"  Processando perfil: {profile_name.upper()}")
        network = Network.from_file(path)
        data_independent[profile_name] = {}
        data_sequential[profile_name] = {}
        
        for ttl in ttls:
            print(f"    - TTL {ttl} ", end="", flush=True)
            res_indep = run_benchmark(network, None, None, ttl, rounds, silent=True, sequential=False)
            data_independent[profile_name][ttl] = res_indep
            print("(Indep) ", end="", flush=True)
            
            res_seq = run_benchmark(network, None, None, ttl, rounds, silent=True, sequential=True)
            data_sequential[profile_name][ttl] = res_seq
            print("(Seq) ✔")

    print("\nGerando gráficos de análise...")
    _plot_success_rate_vs_ttl(data_independent, ttls, "medio", f"{output_dir}/1_sucesso_vs_ttl.png")
    _plot_scalability(data_independent, 6, ["leve", "medio", "pesado"], [20, 100, 1000], f"{output_dir}/2_escalabilidade.png")
    _plot_cache_impact(data_independent, data_sequential, "medio", 6, f"{output_dir}/3_impacto_cache.png")
    _plot_ttl_vs_messages(data_independent, ttls, f"{output_dir}/4_ttl_impacto_mensagens.png")
    _plot_algorithm_comparison_by_network(data_independent, 6, ["leve", "medio", "pesado"], f"{output_dir}/5_comparativo_redes.png")

    print(f"\nAnálise completa! Gráficos salvos em: {output_dir}/")


# --- Funções Internas de Plotagem da Análise ---

def _get_algo_color(algo_name):
    colors = {
        "flooding": "#3498DB",
        "informed_flooding": "#E74C3C",
        "random_walk": "#2ECC71",
        "informed_random_walk": "#F39C12"
    }
    return colors.get(algo_name, "#95A5A6")

def _plot_success_rate_vs_ttl(data, ttls, profile, output_path):
    import matplotlib.pyplot as plt
    plt.figure(figsize=(10, 6))
    algos = list(data[profile][ttls[0]].keys())
    for algo in algos:
        rates = [data[profile][t][algo]["success_rate"] for t in ttls]
        plt.plot(ttls, rates, marker='o', label=algo, color=_get_algo_color(algo))
    plt.title(f"Taxa de Sucesso vs TTL (Rede {profile.capitalize()})", fontweight="bold")
    plt.xlabel("TTL")
    plt.ylabel("Taxa de Sucesso (%)")
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend()
    plt.savefig(output_path, dpi=150)
    plt.close()

def _plot_scalability(data, ttl, profiles, sizes, output_path):
    import matplotlib.pyplot as plt
    plt.figure(figsize=(10, 6))
    algos = list(data["leve"][ttl].keys())
    for algo in algos:
        msgs = [data[p][ttl][algo]["avg_msgs"] for p in profiles]
        plt.plot(sizes, msgs, marker='s', label=algo, color=_get_algo_color(algo))
    plt.xscale('log')
    plt.title(f"Escalabilidade: Mensagens vs Tamanho da Rede (TTL={ttl})", fontweight="bold")
    plt.xlabel("Número de Nós (escala log)")
    plt.ylabel("Média de Mensagens")
    plt.grid(True, which="both", linestyle='--', alpha=0.6)
    plt.legend()
    plt.savefig(output_path, dpi=150)
    plt.close()

def _plot_cache_impact(data_ind, data_seq, profile, ttl, output_path):
    import matplotlib.pyplot as plt
    import numpy as np
    algos = ["informed_flooding", "informed_random_walk"]
    ind_vals = [data_ind[profile][ttl][a]["avg_msgs"] for a in algos]
    seq_vals = [data_seq[profile][ttl][a]["avg_msgs"] for a in algos]
    x = np.arange(len(algos))
    width = 0.35
    plt.figure(figsize=(10, 6))
    plt.bar(x - width/2, ind_vals, width, label='Independente (Sem Cache)', color='#BDC3C7')
    plt.bar(x + width/2, seq_vals, width, label='Sequencial (Com Cache)', color='#3498DB')
    plt.title(f"Impacto do Cache: Independente vs Sequencial ({profile.capitalize()}, TTL={ttl})", fontweight="bold")
    plt.xticks(x, algos)
    plt.ylabel("Média de Mensagens")
    plt.legend()
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    plt.savefig(output_path, dpi=150)
    plt.close()

def _plot_ttl_vs_messages(data, ttls, output_path):
    import matplotlib.pyplot as plt
    profiles = list(data.keys())
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    for i, p in enumerate(profiles):
        algos = list(data[p][ttls[0]].keys())
        for algo in algos:
            msgs = [data[p][t][algo]["avg_msgs"] for t in ttls]
            axes[i].plot(ttls, msgs, marker='o', label=algo, color=_get_algo_color(algo))
        axes[i].set_title(f"Rede {p.capitalize()}")
        axes[i].set_xlabel("TTL")
        axes[i].set_ylabel("Média de Mensagens")
        axes[i].grid(True, alpha=0.3)
        if i == 2: axes[i].legend()
    plt.suptitle("Impacto do TTL no Nº de Mensagens por Tipo de Rede", fontsize=14, fontweight="bold")
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(output_path, dpi=150)
    plt.close()

def _plot_algorithm_comparison_by_network(data, ttl, profiles, output_path):
    import matplotlib.pyplot as plt
    import numpy as np
    algos = list(data["leve"][ttl].keys())
    x = np.arange(len(algos))
    width = 0.25
    plt.figure(figsize=(12, 6))
    for i, p in enumerate(profiles):
        vals = [data[p][ttl][a]["avg_msgs"] for a in algos]
        plt.bar(x + (i-1)*width, vals, width, label=f"Rede {p.capitalize()}")
    plt.title(f"Mensagens Trocadas por Algoritmo nas Diferentes Redes (TTL={ttl})", fontweight="bold")
    plt.xticks(x, algos)
    plt.ylabel("Média de Mensagens")
    plt.legend()
    plt.grid(axis='y', linestyle='--', alpha=0.4)
    plt.savefig(output_path, dpi=150)
    plt.close()