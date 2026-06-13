import uuid


class Message:
    """
    Representa uma mensagem trocada entre nós durante uma busca.
    """

    def __init__(self, search_id: str, resource_id: str, ttl: int, origin_id: str, algo: str):
        self.search_id = search_id        # ID único da busca (para evitar loops)
        self.resource_id = resource_id    # Recurso que está sendo buscado
        self.ttl = ttl                    # Time to Live
        self.origin_id = origin_id        # Nó que iniciou a busca
        self.algo = algo                  # Algoritmo em uso
        self.path: list[str] = [origin_id]  # Rastro do caminho percorrido

    def hop(self, next_node_id: str) -> "Message":
        """Cria uma cópia da mensagem com TTL decrementado e caminho atualizado."""
        m = Message(self.search_id, self.resource_id, self.ttl - 1, self.origin_id, self.algo)
        m.path = self.path + [next_node_id]
        return m

    def __repr__(self):
        return (f"Message(search={self.search_id[:8]}… resource={self.resource_id} "
                f"ttl={self.ttl} path={' → '.join(self.path)})")