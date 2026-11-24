"""Uma IA de mentira para os testes.

Cada item do roteiro é a próxima resposta. Pode ser:
- um texto: a IA responde só com texto (fim do laço);
- uma tupla (nome_da_ferramenta, argumentos): a IA pede essa ferramenta;
- uma lista de tuplas: a IA pede várias ferramentas de uma vez;
- uma função que recebe as mensagens e devolve um dos formatos acima;
- uma exceção: a IA "falha" (ex.: ErroIA, para simular a internet caindo).
"""

from app.ia.base import ChamadaFerramenta, RespostaIA, Uso


class IAFalsa:
    def __init__(self):
        self.roteiro: list = []
        self.pedidos: list[dict] = []  # tudo o que o orquestrador mandou, para conferir

    def responder(self, *, sistema, mensagens, ferramentas, modelo, esforco, max_tokens):
        self.pedidos.append(
            {"sistema": sistema, "mensagens": list(mensagens), "ferramentas": ferramentas, "modelo": modelo}
        )
        if not self.roteiro:
            raise AssertionError("A IA falsa foi chamada mais vezes do que o roteiro previa.")
        passo = self.roteiro.pop(0)
        if callable(passo) and not isinstance(passo, type):
            passo = passo(mensagens)
        if isinstance(passo, Exception):
            raise passo

        uso = Uso(entrada=1000, saida=100, cache_leitura=3000, cache_escrita=0)
        if isinstance(passo, str):
            return RespostaIA(passo, [], uso, modelo, "end_turn")
        pedidos = passo if isinstance(passo, list) else [passo]
        chamadas = [
            ChamadaFerramenta(id=f"chamada_{len(self.pedidos)}_{i}", nome=nome, argumentos=args)
            for i, (nome, args) in enumerate(pedidos)
        ]
        return RespostaIA("", chamadas, uso, modelo, "tool_use")
