"""
main.py — Ponto de entrada do simulador P2P.

Uso:
    # Modo interativo (menu):
    python main.py default.yaml

    # Busca direta:
    python main.py default.yaml --node n1 --resource r10 --ttl 6 --algo flooding

    # Análise Mestra (gera gráficos comparativos de todas as redes):
    # (Não exige arquivo de configuração como argumento)
    python main.py --analyze --rounds 30

    # Comparar todos os algoritmos (uma rodada):
    python main.py default.yaml --node n1 --resource r10 --ttl 6 --compare

    # Benchmark estatístico (N rodadas):
    python main.py default.yaml --node n1 --resource r10 --ttl 6 --benchmark --rounds 30
"""

import argparse
import sys
from network import Network
from search import ALGORITHMS


def run_interactive(net: Network):
    print("\n── Simulador P2P ──  (digite 'sair' para encerrar)\n")
    algos = list(ALGORITHMS.keys())

    while True:
        print("Nós disponíveis:", sorted(net.nodes.keys()))
        node_id = input("Nó de origem (node_id): ").strip()
        if node_id.lower() == "sair":
            break
        if node_id not in net.nodes:
            print(f"  Nó '{node_id}' não existe. Tente novamente.\n")
            continue

        resource_id = input("Recurso buscado (resource_id): ").strip()
        if resource_id.lower() == "sair":
            break

        try:
            ttl = int(input("TTL: ").strip())
        except ValueError:
            print("  TTL deve ser um número inteiro.\n")
            continue

        print(f"Algoritmos disponíveis: {algos}")
        algo = input("Algoritmo (algo): ").strip().lower()
        if algo not in ALGORITHMS:
            print(f"  Algoritmo '{algo}' desconhecido. Opções: {algos}\n")
            continue

        draw = input("Gerar gráfico da busca? (s/n): ").strip().lower() == "s"

        stats = ALGORITHMS[algo](net, node_id, resource_id, ttl)

        if draw:
            from visualizer import draw_search, draw_search_animation_gif
            draw_search(net, stats, output_path=f"out/busca_{algo}_{resource_id}.png")
            draw_search_animation_gif(net, stats, output_path=f"out/animacao_{algo}_{resource_id}.gif")
        print()


def run_compare(net: Network, node_id: str, resource_id: str, ttl: int):
    """Roda todos os algoritmos uma vez e exibe resumo comparativo."""
    results = []
    for name, func in ALGORITHMS.items():
        stats = func(net, node_id, resource_id, ttl)
        results.append((name, stats))

    sep = "═" * 70
    print(f"\n{sep}")
    print(f"  COMPARATIVO — recurso={resource_id}  origem={node_id}  TTL={ttl}")
    print(f"  {'Algoritmo':<25} {'Encontrado':<18} {'Mensagens':>10} {'Nós visitados':>15}")
    print("─" * 70)
    for name, s in results:
        found_str = f"✔ em {s.found_at}" if s.found else "✘ não encontrado"
        print(f"  {name:<25} {found_str:<18} {s.message_count:>10} {len(s.nodes_visited):>15}")
    print(sep)


def main():
    parser = argparse.ArgumentParser(description="Simulador de busca em redes P2P")
    parser.add_argument("config", nargs='?', help="Arquivo YAML de configuração da rede (opcional se usar --analyze)")
    parser.add_argument("--node",     help="Nó de origem da busca")
    parser.add_argument("--resource", help="Recurso a buscar")
    parser.add_argument("--ttl",      type=int, help="TTL da busca")
    parser.add_argument("--algo",     choices=list(ALGORITHMS.keys()), help="Algoritmo de busca")

    parser.add_argument("--compare",      action="store_true",
                        help="Compara todos os algoritmos (1 rodada cada)")
    parser.add_argument("--benchmark",    action="store_true",
                        help="Benchmark estatístico: N rodadas por algoritmo")
    parser.add_argument("--rounds",       type=int, default=20,
                        help="Número de rodadas para o benchmark (padrão: 20)")
    parser.add_argument("--sequential",   action="store_true",
                        help="No benchmark, mantém o cache entre rodadas (testa efeito acumulado)")
    parser.add_argument("--analyze",      action="store_true",
                        help="Executa a análise mestra (gráficos comparativos de todas as redes)")
    parser.add_argument("--draw-network", action="store_true",
                        help="Gera gráfico PNG da topologia da rede")
    parser.add_argument("--draw-search",  action="store_true",
                        help="Gera gráfico PNG do resultado da busca + animação multi-painel")
    parser.add_argument("--seed",         type=int, help="Semente para o gerador de números aleatórios")

    args = parser.parse_args()

    # ── Análise Mestra ───────────────────────────────────
    # Se pedir análise, não precisamos carregar a config agora
    if args.analyze:
        from benchmark import run_full_analysis
        run_full_analysis(rounds=args.rounds, seed=args.seed or 42)
        return

    # ── Carrega e valida ──────────────────────────────────
    if not args.config:
        print("Erro: Informe o arquivo de configuração (.yaml) ou use --analyze.")
        parser.print_help()
        sys.exit(1)

    # ── Configura Semente ────────────────────────────────
    if args.seed is not None:
        import random
        import numpy as np
        random.seed(args.seed)
        np.random.seed(args.seed)

    try:
        net = Network.from_file(args.config)
    except FileNotFoundError:
        print(f"Erro: arquivo '{args.config}' não encontrado.")
        sys.exit(1)
    except Exception as e:
        print(f"Erro ao carregar a configuração: {e}")
        sys.exit(1)

    if not net.validate():
        print("\nCorriga os erros acima antes de prosseguir.")
        sys.exit(1)

    net.print_topology()

    # ── Gráfico da rede ───────────────────────────────────
    if args.draw_network:
        from visualizer import draw_network
        draw_network(net, output_path="out/network.png")

    # ── Benchmark ────────────────────────────────────────
    if args.benchmark:
        if not args.ttl:
            print("Para --benchmark, informe pelo menos o --ttl.")
            sys.exit(1)
        from benchmark import run_benchmark, print_benchmark, plot_benchmark, plot_histogram
        import os
        config_name = os.path.splitext(os.path.basename(args.config))[0]
        
        mode_str = "SEQUENCIAL" if args.sequential else "INDEPENDENTE"
        print(f"\n  Rodando benchmark {mode_str} ({args.rounds} rodadas por algoritmo)...")
        results = run_benchmark(net, args.node, args.resource, args.ttl,
                                rounds=args.rounds, silent=True,
                                sequential=args.sequential)
        print_benchmark(results, args.node, args.resource, args.ttl)
        
        output_plot = f"out/benchmark/benchmark_{config_name}_ttl{args.ttl}.png"
        plot_benchmark(results, args.node, args.resource, args.ttl, config_name=config_name,
                       output_path=output_plot)
        
        output_hist = f"out/benchmark/histogram_{config_name}_ttl{args.ttl}.png"
        plot_histogram(results, args.node, args.resource, args.ttl, config_name=config_name,
                       output_path=output_hist)
        return

    # ── Comparar (1 rodada) ───────────────────────────────
    if args.compare:
        if not all([args.node, args.resource, args.ttl]):
            print("Para --compare, informe também --node, --resource e --ttl.")
            sys.exit(1)
        run_compare(net, args.node, args.resource, args.ttl)
        return

    # ── Busca direta via flags ────────────────────────────
    if args.node or args.resource or args.ttl or args.algo:
        missing = [f for f, v in [("--node", args.node), ("--resource", args.resource),
                                   ("--ttl", args.ttl), ("--algo", args.algo)] if not v]
        if missing:
            print(f"Faltam os parâmetros: {missing}")
            sys.exit(1)
        stats = ALGORITHMS[args.algo](net, args.node, args.resource, args.ttl)

        if args.draw_search:
            from visualizer import draw_search, draw_search_animation_gif
            draw_search(net, stats,
                        output_path=f"out/busca_{args.algo}_{args.resource}.png")
            draw_search_animation_gif(net, stats,
                                  output_path=f"out/animacao_{args.algo}_{args.resource}.gif")
        return

    # ── Modo interativo ───────────────────────────────────
    run_interactive(net)


if __name__ == "__main__":
    main()