"""
visualizer.py — Representação gráfica da rede P2P e animação das buscas.
Usa networkx + matplotlib.
"""

import copy
import matplotlib
matplotlib.use("Agg")   # backend sem janela — gera arquivos PNG
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.animation as animation
import networkx as nx

# Paleta de cores
C_DEFAULT   = "#AED6F1"   # nó normal
C_ORIGIN    = "#F39C12"   # nó de origem
C_FOUND     = "#2ECC71"   # nó onde o recurso foi encontrado
C_VISITED   = "#E74C3C"   # nós visitados durante a busca
C_EDGE      = "#BDC3C7"   # aresta normal
C_ACTIVE    = "#E74C3C"   # aresta ativa (mensagem passando)


def _build_graph(network) -> nx.Graph:
    G = nx.Graph()
    for node_id in network.nodes:
        G.add_node(node_id)
    for node_id, node in network.nodes.items():
        for neighbor_id in node.neighbors:
            if not G.has_edge(node_id, neighbor_id):
                G.add_edge(node_id, neighbor_id)
    return G


def draw_network(network, output_path: str = "network.png"):
    """
    Gera uma imagem estática da topologia da rede P2P.
    Cada nó exibe seu ID e seus recursos.
    """
    G = _build_graph(network)
    pos = nx.spring_layout(G, seed=42, k=2.5)

    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_title("Topologia da Rede P2P", fontsize=16, fontweight="bold", pad=20)
    ax.axis("off")

    # Arestas
    nx.draw_networkx_edges(G, pos, ax=ax, edge_color=C_EDGE, width=2, alpha=0.7)

    # Nós
    nx.draw_networkx_nodes(G, pos, ax=ax,
                           node_color=C_DEFAULT, node_size=1800, alpha=0.95)

    # Labels: ID + recursos
    labels = {}
    for node_id, node in network.nodes.items():
        res = ", ".join(sorted(node.resources))
        labels[node_id] = f"{node_id}\n[{res}]"
    nx.draw_networkx_labels(G, pos, labels=labels, ax=ax, font_size=7, font_weight="bold")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Gráfico da rede salvo em: {output_path}")


def draw_search(network, stats, output_path: str = "search.png"):
    """
    Gera uma imagem da rede destacando o resultado de uma busca:
      - Laranja  → nó de origem
      - Vermelho → nós visitados durante a busca
      - Verde    → nó onde o recurso foi encontrado
      - Vermelho (arestas) → caminho percorrido
    """
    G = _build_graph(network)
    pos = nx.spring_layout(G, seed=42, k=2.5)

    # Classifica cada nó
    node_colors = []
    for node_id in G.nodes():
        if stats.found and node_id == stats.found_at:
            node_colors.append(C_FOUND)
        elif node_id == stats.origin_id:
            node_colors.append(C_ORIGIN)
        elif node_id in stats.nodes_visited:
            node_colors.append(C_VISITED)
        else:
            node_colors.append(C_DEFAULT)

    # Arestas do caminho percorrido
    path_clean = [p for p in stats.final_path if not p.startswith("(cache")]
    path_edges = set()
    for i in range(len(path_clean) - 1):
        a, b = path_clean[i], path_clean[i + 1]
        path_edges.add((a, b))
        path_edges.add((b, a))

    edge_colors = []
    edge_widths = []
    for u, v in G.edges():
        if (u, v) in path_edges or (v, u) in path_edges:
            edge_colors.append(C_ACTIVE)
            edge_widths.append(4)
        else:
            edge_colors.append(C_EDGE)
            edge_widths.append(1.5)

    fig, ax = plt.subplots(figsize=(12, 8))
    found_str = f"encontrado em {stats.found_at}" if stats.found else "NÃO encontrado"
    ax.set_title(
        f"Busca: recurso={stats.resource_id}  origem={stats.origin_id}  "
        f"algo={stats.algo}  TTL={stats.ttl}\n"
        f"Resultado: {found_str}  |  Mensagens={stats.message_count}  "
        f"Nós visitados={len(stats.nodes_visited)}",
        fontsize=11, fontweight="bold", pad=15
    )
    ax.axis("off")

    nx.draw_networkx_edges(G, pos, ax=ax,
                           edge_color=edge_colors, width=edge_widths, alpha=0.8)
    nx.draw_networkx_nodes(G, pos, ax=ax,
                           node_color=node_colors, node_size=1800, alpha=0.95)

    labels = {nid: nid for nid in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels=labels, ax=ax, font_size=9, font_weight="bold")

    # Legenda
    legend_items = [
        mpatches.Patch(color=C_ORIGIN,  label="Origem"),
        mpatches.Patch(color=C_VISITED, label="Nós visitados"),
        mpatches.Patch(color=C_FOUND,   label="Recurso encontrado"),
        mpatches.Patch(color=C_DEFAULT, label="Não visitado"),
        mpatches.Patch(color=C_ACTIVE,  label="Caminho percorrido"),
    ]
    ax.legend(handles=legend_items, loc="lower left", fontsize=9,
              framealpha=0.9, edgecolor="#cccccc")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Gráfico da busca salvo em: {output_path}")

def draw_search_animation_multipanel(network, stats, output_path: str = "search_animation.png"):
    """
    Gera um PNG multi-painel mostrando o progresso passo a passo da busca,
    reconstruindo o estado da rede a cada mensagem trocada.
    """
    G = _build_graph(network)
    pos = nx.spring_layout(G, seed=42, k=2.5)

    # Extrai os passos do log (apenas mensagens de BUSCA, não RESP)
    steps = []
    active_nodes: set[str] = {stats.origin_id}
    active_edges: set[tuple] = set()

    for entry in stats.log:
        if "BUSCA:" in entry:
            # Formato: "  [NNN] BUSCA: nX → nY  (TTL=Z)"
            parts = entry.split("BUSCA:")[1].strip().split("→")
            if len(parts) == 2:
                sender = parts[0].strip()
                receiver = parts[1].split("(")[0].strip()
                active_nodes.add(receiver)
                active_edges.add((sender, receiver))
                steps.append((frozenset(active_nodes), frozenset(active_edges),
                               f"Passo {len(steps)+1}: {sender} → {receiver}"))

    if not steps:
        # Recurso na própria origem — só um painel
        steps = [(frozenset([stats.origin_id]), frozenset(),
                  f"Recurso na origem: {stats.origin_id}")]

    steps = steps[:]
    n = len(steps)
    cols = min(n, 4)
    rows = (n + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=(5 * cols, 4.5 * rows))
    fig.suptitle(
        f"Animação da Busca — recurso={stats.resource_id}  "
        f"origem={stats.origin_id}  algo={stats.algo}",
        fontsize=13, fontweight="bold"
    )

    # Achata axes para iterar facilmente
    if rows == 1 and cols == 1:
        axes_flat = [axes]
    elif rows == 1:
        axes_flat = list(axes)
    else:
        axes_flat = [ax for row in axes for ax in row]

    for i, (vis_nodes, vis_edges, title) in enumerate(steps):
        ax = axes_flat[i]
        ax.set_title(title, fontsize=8, pad=6)
        ax.axis("off")

        node_colors = []
        for nid in G.nodes():
            if stats.found and nid == stats.found_at and nid in vis_nodes:
                node_colors.append(C_FOUND)
            elif nid == stats.origin_id:
                node_colors.append(C_ORIGIN)
            elif nid in vis_nodes:
                node_colors.append(C_VISITED)
            else:
                node_colors.append(C_DEFAULT)

        edge_colors = []
        edge_widths = []
        for u, v in G.edges():
            if (u, v) in vis_edges or (v, u) in vis_edges:
                edge_colors.append(C_ACTIVE)
                edge_widths.append(3)
            else:
                edge_colors.append(C_EDGE)
                edge_widths.append(1)

        nx.draw_networkx_edges(G, pos, ax=ax, edge_color=edge_colors,
                               width=edge_widths, alpha=0.7)
        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors,
                               node_size=600, alpha=0.95)
        nx.draw_networkx_labels(G, pos, ax=ax, font_size=7, font_weight="bold")

    # Esconde painéis extras (se steps < rows*cols)
    for j in range(len(steps), len(axes_flat)):
        axes_flat[j].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_path, dpi=130, bbox_inches="tight")
    plt.close()
    print(f"  Animação (multi-painel) salva em: {output_path}")


def draw_search_animation_gif(network, stats, output_path: str = "search_animation.gif",
                              fps: float = 1.5, dpi: int = 130,
                              hold_last_frames: int = 3):
    """
    Gera um GIF animado mostrando o progresso passo a passo da busca,
    reconstruindo o estado da rede a cada mensagem trocada.

    Parâmetros extras em relação à versão multi-painel:
        fps: quadros por segundo (controla a velocidade da animação).
        hold_last_frames: quantas vezes repetir o último quadro, para a
            animação "pausar" no resultado final antes de reiniciar o loop.
    """
    G = _build_graph(network)
    pos = nx.spring_layout(G, seed=42, k=2.5)

    # Extrai os passos do log (apenas mensagens de BUSCA, não RESP)
    steps = []
    active_nodes: set[str] = {stats.origin_id}
    active_edges: set[tuple] = set()

    for entry in stats.log:
        if "BUSCA:" in entry:
            # Formato: "  [NNN] BUSCA: nX → nY  (TTL=Z)"
            parts = entry.split("BUSCA:")[1].strip().split("→")
            if len(parts) == 2:
                sender = parts[0].strip()
                receiver = parts[1].split("(")[0].strip()
                active_nodes.add(receiver)
                active_edges.add((sender, receiver))
                steps.append((frozenset(active_nodes), frozenset(active_edges),
                              f"Passo {len(steps) + 1}: {sender} → {receiver}"))

    if not steps:
        # Recurso na própria origem — só um quadro
        steps = [(frozenset([stats.origin_id]), frozenset(),
                  f"Recurso na origem: {stats.origin_id}")]

    # Repete o último estado algumas vezes para "pausar" no resultado final
    if hold_last_frames > 1:
        steps = steps + [steps[-1]] * (hold_last_frames - 1)

    fig, ax = plt.subplots(figsize=(7, 6))
    fig.suptitle(
        f"Animação da Busca — recurso={stats.resource_id}  "
        f"origem={stats.origin_id}  algo={stats.algo}",
        fontsize=12, fontweight="bold"
    )

    def render_frame(idx):
        vis_nodes, vis_edges, title = steps[idx]
        ax.clear()
        ax.set_title(title, fontsize=10, pad=8)
        ax.axis("off")

        node_colors = []
        for nid in G.nodes():
            if stats.found and nid == stats.found_at and nid in vis_nodes:
                node_colors.append(C_FOUND)
            elif nid == stats.origin_id:
                node_colors.append(C_ORIGIN)
            elif nid in vis_nodes:
                node_colors.append(C_VISITED)
            else:
                node_colors.append(C_DEFAULT)

        edge_colors = []
        edge_widths = []
        for u, v in G.edges():
            if (u, v) in vis_edges or (v, u) in vis_edges:
                edge_colors.append(C_ACTIVE)
                edge_widths.append(3)
            else:
                edge_colors.append(C_EDGE)
                edge_widths.append(1)

        nx.draw_networkx_edges(G, pos, ax=ax, edge_color=edge_colors,
                               width=edge_widths, alpha=0.7)
        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors,
                               node_size=600, alpha=0.95)
        nx.draw_networkx_labels(G, pos, ax=ax, font_size=8, font_weight="bold")

    anim = animation.FuncAnimation(fig, render_frame, frames=len(steps))
    anim.save(output_path, writer=animation.PillowWriter(fps=fps), dpi=dpi)
    plt.close(fig)

    print(f"  Animação (GIF) salva em: {output_path}")