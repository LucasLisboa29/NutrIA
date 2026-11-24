"""Interface `ProvedorIA`: o que o núcleo espera de qualquer IA.

O núcleo nunca importa o SDK da Anthropic (nem de outra empresa). Ele fala só com os
tipos deste arquivo. Cada empresa ganha um *adaptador* (ex.: `claude.py`) que traduz
esses tipos para a API dela. Trocar de IA = escrever outro adaptador.

Como funciona uma conversa com ferramentas (tool use):
1. Mandamos o histórico + a lista de ferramentas que a IA pode usar.
2. A IA responde com texto e/ou com *chamadas de ferramenta* ("registrar_refeicao com
   estes itens"). Ela não executa nada: só pede.
3. O nosso código executa a ferramenta e devolve o resultado para a IA.
4. Repetimos até a IA responder só com texto. Esse texto vai para o usuário.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Ferramenta:
    """Uma ação que a IA pode pedir para o nosso código executar."""

    nome: str
    descricao: str  # a IA lê isto para decidir quando usar a ferramenta
    parametros: dict  # JSON Schema dos argumentos


@dataclass
class ChamadaFerramenta:
    id: str  # identificador da chamada, para casar com o resultado
    nome: str
    argumentos: dict


@dataclass
class Uso:
    """Tokens gastos numa chamada. Token ~ pedaço de palavra; é como a IA é cobrada."""

    entrada: int = 0  # o que mandamos (sem cache)
    saida: int = 0  # o que a IA escreveu (inclui o raciocínio interno)
    cache_leitura: int = 0  # entrada reaproveitada do cache (bem mais barata)
    cache_escrita: int = 0  # entrada gravada no cache nesta chamada


@dataclass
class RespostaIA:
    texto: str
    chamadas: list[ChamadaFerramenta]
    uso: Uso
    modelo: str
    motivo_parada: str  # ex.: "end_turn" (terminou) ou "tool_use" (quer ferramenta)
    bruto: Any = None  # conteúdo original do provedor, devolvido intacto no próximo passo


# ---------- Mensagens da conversa, no formato neutro ----------


@dataclass
class MensagemUsuario:
    texto: str
    contexto: str = ""  # informações do sistema que vão junto (data, registros de hoje)


@dataclass
class TurnoAssistente:
    """Uma resposta anterior da IA. Pode vir do banco (só texto) ou do laço atual (bruto)."""

    texto: str = ""
    resposta: RespostaIA | None = None


@dataclass
class ResultadoFerramenta:
    chamada_id: str
    conteudo: str  # normalmente um JSON em texto
    erro: bool = False


@dataclass
class ResultadosFerramentas:
    resultados: list[ResultadoFerramenta] = field(default_factory=list)


Mensagem = MensagemUsuario | TurnoAssistente | ResultadosFerramentas


class ErroIA(RuntimeError):
    """Falha ao falar com a IA (rede, chave inválida, limite de uso...)."""


class ProvedorIA(Protocol):
    def responder(
        self,
        *,
        sistema: str,
        mensagens: list[Mensagem],
        ferramentas: list[Ferramenta],
        modelo: str,
        esforco: str | None,
        max_tokens: int,
    ) -> RespostaIA: ...
