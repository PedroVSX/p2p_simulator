class SearchStats:
    """
    Coleta e exibe estatísticas de uma busca.
    """

    def __init__(self, search_id: str, resource_id: str, origin_id: str, algo: str, ttl: int):
        self.search_id = search_id
        self.resource_id = resource_id
        self.origin_id = origin_id
        self.algo = algo
        self.ttl = ttl

        self.message_count = 0
        self.nodes_visited: set[str] = set()
        self.found = False
        self.found_at: str | None = None
        self.final_path: list[str] = []
        self.log: list[str] = []        # Rastro textual passo a passo

    def record_message(self, sender: str, receiver: str, ttl: int, msg_type: str = "BUSCA"):
        self.message_count += 1
        self.nodes_visited.add(sender)
        self.nodes_visited.add(receiver)
        entry = f"  [{self.message_count:3d}] {msg_type}: {sender} → {receiver}  (TTL={ttl})"
        self.log.append(entry)

    def record_found(self, node_id: str, path: list[str]):
        self.found = True
        self.found_at = node_id
        self.final_path = path

    def print_summary(self):
        sep = "─" * 60
        print(f"\n{sep}")
        print(f"  RESULTADO DA BUSCA")
        print(sep)
        print(f"  ID da busca  : {self.search_id}")
        print(f"  Recurso      : {self.resource_id}")
        print(f"  Origem       : {self.origin_id}")
        print(f"  Algoritmo    : {self.algo}")
        print(f"  TTL inicial  : {self.ttl}")
        print(sep)
        if self.found:
            print(f"  ✔ Recurso ENCONTRADO no nó: {self.found_at}")
            print(f"  Caminho: {' → '.join(self.final_path)}")
        else:
            print(f"  ✘ Recurso NÃO encontrado (TTL esgotado ou rede esgotada)")
        print(sep)
        print(f"  Mensagens trocadas : {self.message_count}")
        print(f"  Nós envolvidos     : {len(self.nodes_visited)}  {sorted(self.nodes_visited)}")
        print(sep)
        print("\n  RASTRO DA BUSCA:")
        for entry in self.log:
            print(entry)
        print(sep)