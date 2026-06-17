import yaml
import random


# Classe auxiliar para forçar apenas as arestas a ficarem no formato [n1, n2]
class FlowList(list):
    pass


def flow_list_representer(dumper, data):
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)


yaml.add_representer(FlowList, flow_list_representer)


def gerar_config_p2p(filename, num_nodes, min_neighbors, max_neighbors):
    config = {
        "num_nodes": num_nodes,
        "min_neighbors": min_neighbors,
        "max_neighbors": max_neighbors,
        "resources": {},
        "edges": []
    }

    # 1. Gerar Recursos
    for i in range(1, num_nodes + 1):
        qtd_recursos = random.randint(1, 3)
        recursos = [f"r{random.randint(1, 30)}" for _ in range(qtd_recursos)]
        config["resources"][f"n{i}"] = ", ".join(set(recursos))

    # 2. Gerar Edges (Garantindo conectividade básica em anel)
    for i in range(1, num_nodes):
        config["edges"].append(FlowList([f"n{i}", f"n{i + 1}"]))
    config["edges"].append(FlowList([f"n{num_nodes}", "n1"]))

    # Conexões extras respeitando o limite
    grau_nos = {f"n{i}": 2 for i in range(1, num_nodes + 1)}
    lista_nos = [f"n{i}" for i in range(1, num_nodes + 1)]

    # Garantir que todos os nós alcancem pelo menos min_neighbors
    for no_atual in lista_nos:
        tentativas = 0
        while grau_nos[no_atual] < min_neighbors and tentativas < 100:
            alvo = random.choice(lista_nos)
            if no_atual != alvo and grau_nos[alvo] < max_neighbors:
                edge = sorted([no_atual, alvo])
                if FlowList(edge) not in config["edges"]:
                    config["edges"].append(FlowList(edge))
                    grau_nos[no_atual] += 1
                    grau_nos[alvo] += 1
            tentativas += 1

    # Salvar arquivo com a formatação correta
    with open(filename, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    print(f"Arquivo '{filename}' gerado com sucesso!")


# Gerar os 3 arquivos corrigidos
gerar_config_p2p("config/leve.yaml", num_nodes=20, min_neighbors=2, max_neighbors=3)
gerar_config_p2p("config/medio.yaml", num_nodes=100, min_neighbors=5, max_neighbors=10)
gerar_config_p2p("config/pesado.yaml", num_nodes=1000, min_neighbors=8, max_neighbors=15)