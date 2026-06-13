class Node:
    """
    Representa um nó na rede P2P.
    Cada nó conhece apenas: seu próprio ID, seus vizinhos diretos,
    seus recursos locais e seu cache de localização de recursos.
    """

    def __init__(self, node_id: str):
        self.id = node_id
        self.neighbors: list[str] = []          # IDs dos vizinhos diretos
        self.resources: set[str] = set()        # Recursos mantidos localmente
        self.cache: dict[str, str] = {}         # resource_id → node_id (busca informada)

    def has_resource(self, resource_id: str) -> bool:
        return resource_id in self.resources

    def knows_location(self, resource_id: str) -> bool:
        """Retorna True se o cache já contém a localização do recurso."""
        return resource_id in self.cache

    def update_cache(self, resource_id: str, node_id: str):
        """Atualiza o cache com a localização de um recurso."""
        self.cache[resource_id] = node_id

    def add_neighbor(self, neighbor_id: str):
        if neighbor_id not in self.neighbors:
            self.neighbors.append(neighbor_id)

    def add_resource(self, resource_id: str):
        self.resources.add(resource_id.strip())

    def __repr__(self):
        return (f"Node({self.id} | vizinhos={self.neighbors} "
                f"| recursos={sorted(self.resources)} | cache={self.cache})")