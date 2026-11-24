"""Escolhe provedor, modelo e esforço por rota, lendo `config/modelos.yaml` (RF35).

Rota = tipo de tarefa ("dia_a_dia", "visao"...). Assim dá para usar um modelo rápido e
barato no dia a dia e um mais forte só onde precisa, mudando só o YAML.
"""

from dataclasses import dataclass

from app.config import carregar_yaml, settings
from app.ia.base import ErroIA, ProvedorIA, Uso


@dataclass
class Rota:
    nome: str
    provedor: str
    modelo: str
    esforco: str | None
    max_tokens: int


_provedores: dict[str, ProvedorIA] = {}


def rota(nome: str) -> Rota:
    config = carregar_yaml("modelos.yaml")["rotas"][nome]
    return Rota(
        nome=nome,
        provedor=config["provedor"],
        modelo=config["modelo"],
        esforco=config.get("esforco"),
        max_tokens=int(config.get("max_tokens", 4000)),
    )


def ia_configurada(nome_provedor: str = "claude") -> bool:
    return nome_provedor in _provedores or (nome_provedor == "claude" and bool(settings.anthropic_api_key))


def provedor(nome: str) -> ProvedorIA:
    """Cria o adaptador na primeira vez e reaproveita depois."""
    if nome not in _provedores:
        if nome == "claude":
            if not settings.anthropic_api_key:
                raise ErroIA("ANTHROPIC_API_KEY está vazia no .env.")
            from app.ia.claude import ProvedorClaude

            _provedores[nome] = ProvedorClaude(settings.anthropic_api_key)
        else:
            raise ErroIA(f"Provedor de IA desconhecido: {nome!r}")
    return _provedores[nome]


def registrar_provedor(nome: str, instancia: ProvedorIA) -> None:
    """Troca o provedor (usado nos testes, com uma IA de mentira)."""
    _provedores[nome] = instancia


def custo_usd(modelo: str, uso: Uso) -> float:
    """Quanto custou uma chamada, pelos preços de `modelos.yaml`."""
    preco = carregar_yaml("modelos.yaml").get("precos", {}).get(modelo)
    if preco is None:
        # O nome devolvido pela API pode ter sufixo de versão; tenta pelo começo.
        precos = carregar_yaml("modelos.yaml").get("precos", {})
        preco = next((p for nome, p in precos.items() if modelo.startswith(nome)), None)
    if preco is None:
        return 0.0
    por_token = preco["entrada"] / 1_000_000
    return (
        uso.entrada * por_token
        + uso.cache_leitura * por_token * preco["cache_leitura"]
        + uso.cache_escrita * por_token * preco["cache_escrita"]
        + uso.saida * preco["saida"] / 1_000_000
    )
