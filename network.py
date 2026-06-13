"""
Carrega, valida e representa a rede P2P a partir de um arquivo YAML.
"""

import yaml
from collections import deque
from node import Node


class Network:
    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.min_neighbors: int = 1
        self.max_neighbors: int = float("inf")

    # ──────────────────────────────────────────
    # CARREGAMENTO
    # ──────────────────────────────────────────

    @classmethod
    def from_file(cls, path: str) -> "Network":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls._build(data)

    @classmethod
    def _build(cls, data: dict) -> "Network":
        net = cls()
        net.min_neighbors = data.get("min_neighbors", 1)
        net.max_neighbors = data.get("max_neighbors", float("inf"))
        num_nodes = data.get("num_nodes", 0)

        # Cria os nós
        resources_section = data.get("resources", {})
        for node_id, res_list in resources_section.items():
            node = Node(node_id)
            if isinstance(res_list, list):
                for r in res_list:
                    node.add_resource(str(r))
            elif isinstance(res_list, str):
                for r in res_list.split(","):
                    node.add_resource(r.strip())
            net.nodes[node_id] = node

        # Cria arestas (bidirecionais)
        edges_section = data.get("edges", [])
        for edge in edges_section:
            if isinstance(edge, list):
                a, b = str(edge[0]), str(edge[1])
            elif isinstance(edge, str):
                parts = [p.strip() for p in edge.split(",")]
                a, b = parts[0], parts[1]
            else:
                raise ValueError(f"Formato de aresta inválido: {edge}")

            # Garante que os nós existam mesmo que não tenham recursos declarados
            if a not in net.nodes:
                net.nodes[a] = Node(a)
            if b not in net.nodes:
                net.nodes[b] = Node(b)

            net.nodes[a].add_neighbor(b)
            net.nodes[b].add_neighbor(a)

        return net

    # ──────────────────────────────────────────
    # VALIDAÇÃO
    # ──────────────────────────────────────────

    def validate(self) -> bool:
        errors = []

        # 1. Rede não pode estar particionada
        if not self._is_connected():
            errors.append("✘ A rede está PARTICIONADA (nem todos os nós são alcançáveis).")

        # 2. Min/max de vizinhos
        for node_id, node in self.nodes.items():
            degree = len(node.neighbors)
            if degree < self.min_neighbors:
                errors.append(
                    f"✘ Nó {node_id} tem {degree} vizinho(s), mínimo exigido: {self.min_neighbors}."
                )
            if degree > self.max_neighbors:
                errors.append(
                    f"✘ Nó {node_id} tem {degree} vizinho(s), máximo permitido: {self.max_neighbors}."
                )

        # 3. Nenhum nó sem recursos
        for node_id, node in self.nodes.items():
            if not node.resources:
                errors.append(f"✘ Nó {node_id} não possui nenhum recurso.")

        # 4. Sem auto-arestas
        for node_id, node in self.nodes.items():
            if node_id in node.neighbors:
                errors.append(f"✘ Nó {node_id} possui uma aresta para si mesmo.")

        if errors:
            print("\n⚠  Erros encontrados na configuração da rede:")
            for e in errors:
                print(f"   {e}")
            return False

        print(f"✔  Configuração válida! Rede com {len(self.nodes)} nós.")
        return True

    def _is_connected(self) -> bool:
        """BFS a partir de um nó arbitrário para checar conectividade."""
        if not self.nodes:
            return True
        start = next(iter(self.nodes))
        visited = set()
        queue = deque([start])
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            for neighbor in self.nodes[current].neighbors:
                if neighbor not in visited:
                    queue.append(neighbor)
        return len(visited) == len(self.nodes)

    # ──────────────────────────────────────────
    # REPRESENTAÇÃO TEXTUAL
    # ──────────────────────────────────────────

    def print_topology(self):
        sep = "─" * 60
        print(f"\n{sep}")
        print(f"  TOPOLOGIA DA REDE  ({len(self.nodes)} nós)")
        print(sep)
        for node_id, node in sorted(self.nodes.items()):
            print(f"  {node_id}")
            print(f"    vizinhos : {node.neighbors}")
            print(f"    recursos : {sorted(node.resources)}")
        print(sep)