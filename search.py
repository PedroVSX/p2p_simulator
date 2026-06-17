"""
Implementação dos 4 algoritmos de busca P2P:
  - flooding
  - informed_flooding
  - random_walk
  - informed_random_walk
"""

import uuid
import random
from collections import deque

from message import Message
from stats import SearchStats


# ──────────────────────────────────────────────
# FLOODING
# ──────────────────────────────────────────────

def flooding(network, origin_id: str, resource_id: str, ttl: int) -> SearchStats:
    """
    Busca por inundação: propaga a requisição para TODOS os vizinhos,
    até encontrar o recurso ou o TTL chegar a zero.
    Usa o search_id para ignorar mensagens duplicadas.
    """
    search_id = str(uuid.uuid4())
    stats = SearchStats(search_id, resource_id, origin_id, "flooding", ttl)

    # Conjunto de (node_id, search_id) já processados — evita loops
    seen: set[str] = set()

    # Fila: (mensagem, nó_atual)
    queue = deque()
    origin_node = network.nodes[origin_id]

    # O nó de origem já verifica seus próprios recursos
    seen.add(origin_id)
    if origin_node.has_resource(resource_id):
        stats.record_found(origin_id, [origin_id])
        stats.log.append(f"  [---] Recurso encontrado na própria origem: {origin_id}")
        stats.print_summary()
        return stats

    # Envia para todos os vizinhos da origem
    initial_msg = Message(search_id, resource_id, ttl, origin_id, "flooding")
    for neighbor_id in origin_node.neighbors:
        msg = initial_msg.hop(neighbor_id)
        stats.record_message(origin_id, neighbor_id, msg.ttl)
        queue.append((msg, neighbor_id))

    while queue:
        msg, current_id = queue.popleft()

        if current_id in seen:
            continue
        seen.add(current_id)

        current_node = network.nodes[current_id]

        if current_node.has_resource(resource_id):
            stats.record_found(current_id, msg.path)
            # Mensagem de retorno até a origem
            _send_reply(msg.path, stats, "RESP")
            break

        if msg.ttl <= 0:
            continue

        # Propaga para todos os vizinhos ainda não visitados
        for neighbor_id in current_node.neighbors:
            if neighbor_id not in seen:
                next_msg = msg.hop(neighbor_id)
                stats.record_message(current_id, neighbor_id, next_msg.ttl)
                queue.append((next_msg, neighbor_id))

    stats.print_summary()
    return stats


# ──────────────────────────────────────────────
# INFORMED FLOODING
# ──────────────────────────────────────────────

def informed_flooding(network, origin_id: str, resource_id: str, ttl: int) -> SearchStats:
    """
    Inundação com cache: antes de propagar, cada nó verifica seu cache.
    Se souber onde o recurso está, responde diretamente sem continuar.
    Ao receber uma resposta, todos os nós no caminho atualizam seu cache.
    """
    search_id = str(uuid.uuid4())
    stats = SearchStats(search_id, resource_id, origin_id, "informed_flooding", ttl)

    seen: set[str] = set()
    queue = deque()
    origin_node = network.nodes[origin_id]

    seen.add(origin_id)

    # Verifica cache da origem primeiro
    if origin_node.knows_location(resource_id):
        found_at = origin_node.cache[resource_id]
        stats.record_found(found_at, [origin_id, f"(cache→{found_at})"])
        stats.log.append(f"  [---] Cache hit na origem {origin_id}: recurso está em {found_at}")
        stats.print_summary()
        return stats

    if origin_node.has_resource(resource_id):
        stats.record_found(origin_id, [origin_id])
        stats.print_summary()
        return stats

    initial_msg = Message(search_id, resource_id, ttl, origin_id, "informed_flooding")
    for neighbor_id in origin_node.neighbors:
        msg = initial_msg.hop(neighbor_id)
        stats.record_message(origin_id, neighbor_id, msg.ttl)
        queue.append((msg, neighbor_id))

    while queue:
        msg, current_id = queue.popleft()

        if current_id in seen:
            continue
        seen.add(current_id)

        current_node = network.nodes[current_id]

        # Cache hit: sabe onde está sem precisar continuar
        if current_node.knows_location(resource_id):
            found_at = current_node.cache[resource_id]
            stats.record_found(found_at, msg.path + [f"(cache→{found_at})"])
            stats.log.append(f"  [---] Cache hit em {current_id}: recurso está em {found_at}")
            _update_cache_along_path(network, msg.path, resource_id, found_at)
            _send_reply(msg.path, stats, "RESP")
            break

        if current_node.has_resource(resource_id):
            stats.record_found(current_id, msg.path)
            _update_cache_along_path(network, msg.path, resource_id, current_id)
            _send_reply(msg.path, stats, "RESP")
            break

        if msg.ttl <= 0:
            continue

        for neighbor_id in current_node.neighbors:
            if neighbor_id not in seen:
                next_msg = msg.hop(neighbor_id)
                stats.record_message(current_id, neighbor_id, next_msg.ttl)
                queue.append((next_msg, neighbor_id))

    stats.print_summary()
    return stats


# ──────────────────────────────────────────────
# RANDOM WALK
# ──────────────────────────────────────────────

def random_walk(network, origin_id: str, resource_id: str, ttl: int) -> SearchStats:
    """
    Passeio aleatório: a cada passo, escolhe UM vizinho aleatório e
    encaminha somente para ele. Muito mais leve em tráfego, mas pode
    demorar mais ou não encontrar o recurso dentro do TTL.
    """
    search_id = str(uuid.uuid4())
    stats = SearchStats(search_id, resource_id, origin_id, "random_walk", ttl)

    origin_node = network.nodes[origin_id]

    if origin_node.has_resource(resource_id):
        stats.record_found(origin_id, [origin_id])
        stats.print_summary()
        return stats

    msg = Message(search_id, resource_id, ttl, origin_id, "random_walk")
    current_id = origin_id

    while msg.ttl > 0:
        current_node = network.nodes[current_id]
        # Escolhe um vizinho aleatório (pode revisitar nós — é intencional no random walk)
        next_id = random.choice(current_node.neighbors)
        msg = msg.hop(next_id)
        stats.record_message(current_id, next_id, msg.ttl)
        current_id = next_id

        next_node = network.nodes[current_id]
        if next_node.has_resource(resource_id):
            stats.record_found(current_id, msg.path)
            _send_reply(msg.path, stats, "RESP")
            break

    stats.print_summary()
    return stats


# ──────────────────────────────────────────────
# INFORMED RANDOM WALK
# ──────────────────────────────────────────────

def informed_random_walk(network, origin_id: str, resource_id: str, ttl: int) -> SearchStats:
    """
    Passeio aleatório com cache e consulta de vizinhança (1-hop):
    Antes de dar um passo aleatório, o nó pergunta aos vizinhos se algum 
    tem o recurso ou o cache. Se sim, ele vai direto para o alvo.
    """
    search_id = str(uuid.uuid4())
    stats = SearchStats(search_id, resource_id, origin_id, "informed_random_walk", ttl)

    origin_node = network.nodes[origin_id]

    # 1. Verifica a própria origem
    if origin_node.has_resource(resource_id):
        stats.record_found(origin_id, [origin_id])
        return stats
    if origin_node.knows_location(resource_id):
        found_at = origin_node.cache[resource_id]
        stats.record_found(found_at, [origin_id, f"(cache→{found_at})"])
        return stats

    msg = Message(search_id, resource_id, ttl, origin_id, "informed_random_walk")
    current_id = origin_id

    while msg.ttl > 0:
        current_node = network.nodes[current_id]
        target_id = None

        # 2. INTELIGÊNCIA: Verifica se algum vizinho tem o recurso ou cache
        for neighbor_id in current_node.neighbors:
            neighbor_node = network.nodes[neighbor_id]
            if neighbor_node.has_resource(resource_id):
                target_id = neighbor_id
                break
            if neighbor_node.knows_location(resource_id):
                target_id = neighbor_id
                break
        
        # 3. Se não encontrou nada nos vizinhos, escolhe um aleatório
        if not target_id:
            target_id = random.choice(current_node.neighbors)
        
        # Realiza o movimento
        msg = msg.hop(target_id)
        stats.record_message(current_id, target_id, msg.ttl)
        current_id = target_id
        current_node = network.nodes[current_id]

        if current_node.has_resource(resource_id):
            stats.record_found(current_id, msg.path)
            _update_cache_along_path(network, msg.path, resource_id, current_id)
            _send_reply(msg.path, stats, "RESP")
            break
        
        if current_node.knows_location(resource_id):
            found_at = current_node.cache[resource_id]
            stats.record_found(found_at, msg.path + [f"(cache→{found_at})"])
            _update_cache_along_path(network, msg.path, resource_id, found_at)
            _send_reply(msg.path, stats, "RESP")
            break

    stats.print_summary()
    return stats


# ──────────────────────────────────────────────
# HELPERS INTERNOS
# ──────────────────────────────────────────────

def _send_reply(path: list[str], stats: SearchStats, msg_type: str):
    """Simula as mensagens de resposta voltando pelo caminho percorrido."""
    clean_path = [p for p in path if not p.startswith("(cache")]
    for i in range(len(clean_path) - 1, 0, -1):
        stats.record_message(clean_path[i], clean_path[i - 1], ttl=0, msg_type=msg_type)


def _update_cache_along_path(network, path: list[str], resource_id: str, found_at: str):
    """Atualiza o cache de todos os nós no caminho percorrido."""
    for node_id in path:
        if node_id in network.nodes:
            network.nodes[node_id].update_cache(resource_id, found_at)


ALGORITHMS = {
    "flooding": flooding,
    "informed_flooding": informed_flooding,
    "random_walk": random_walk,
    "informed_random_walk": informed_random_walk,
}