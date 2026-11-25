"""Adaptador da IA Claude (Anthropic), usando o SDK oficial `anthropic`.

Traduz os tipos neutros de `base.py` para o formato da API Messages e de volta.
"""

import base64

import anthropic

from app.ia.base import (
    ChamadaFerramenta,
    ErroIA,
    Ferramenta,
    Mensagem,
    MensagemUsuario,
    RespostaIA,
    ResultadosFerramentas,
    TurnoAssistente,
    Uso,
)


class ProvedorClaude:
    def __init__(self, api_key: str):
        # max_retries: o SDK repete sozinho erros temporários (rede, sobrecarga).
        self.cliente = anthropic.Anthropic(api_key=api_key, max_retries=2, timeout=60.0)

    def responder(
        self,
        *,
        sistema: str,
        mensagens: list[Mensagem],
        ferramentas: list[Ferramenta],
        modelo: str,
        esforco: str | None,
        max_tokens: int,
    ) -> RespostaIA:
        parametros = {
            "model": modelo,
            "max_tokens": max_tokens,
            # Cache de prompt, em duas marcas (a API reaproveita tudo até cada marca e
            # cobra ~10% do preço da entrada por esse trecho):
            # 1. no fim do prompt do sistema: ferramentas + prompt (a parte grande e fixa)
            #    ficam em cache sozinhos, aconteça o que acontecer com a conversa;
            # 2. automática, no fim do pedido: cobre a conversa dentro do laço de ferramentas.
            "system": [{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}],
            "messages": _converter_mensagens(mensagens),
            "tools": [
                {"name": f.nome, "description": f.descricao, "input_schema": f.parametros}
                for f in ferramentas
            ],
            "cache_control": {"type": "ephemeral"},
        }
        if esforco:
            parametros["output_config"] = {"effort": esforco}

        try:
            resposta = self.cliente.messages.create(**parametros)
        except anthropic.AuthenticationError as erro:
            raise ErroIA("Chave da Anthropic inválida (confira ANTHROPIC_API_KEY no .env).") from erro
        except anthropic.APIStatusError as erro:
            raise ErroIA(f"A API da Anthropic respondeu {erro.status_code}: {erro.message}") from erro
        except anthropic.APIConnectionError as erro:
            raise ErroIA("Sem conexão com a API da Anthropic.") from erro

        texto = "".join(b.text for b in resposta.content if b.type == "text").strip()
        chamadas = [
            ChamadaFerramenta(id=b.id, nome=b.name, argumentos=dict(b.input))
            for b in resposta.content
            if b.type == "tool_use"
        ]
        uso = resposta.usage
        return RespostaIA(
            texto=texto,
            chamadas=chamadas,
            uso=Uso(
                entrada=uso.input_tokens,
                saida=uso.output_tokens,
                cache_leitura=uso.cache_read_input_tokens or 0,
                cache_escrita=uso.cache_creation_input_tokens or 0,
            ),
            modelo=resposta.model,
            motivo_parada=resposta.stop_reason or "",
            # Guardamos o conteúdo original (inclusive o raciocínio interno, se houver):
            # a API exige recebê-lo de volta exatamente igual no próximo passo do laço.
            bruto=resposta.content,
        )


def _converter_mensagens(mensagens: list[Mensagem]) -> list[dict]:
    convertidas: list[dict] = []
    for mensagem in mensagens:
        if isinstance(mensagem, MensagemUsuario):
            blocos = []
            # A imagem vai antes do texto: a documentação recomenda essa ordem.
            for imagem in mensagem.imagens:
                blocos.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": imagem.mime,
                        "data": base64.standard_b64encode(imagem.dados).decode("ascii"),
                    },
                })
            if mensagem.contexto:
                blocos.append({"type": "text", "text": mensagem.contexto})
            blocos.append({"type": "text", "text": mensagem.texto or "(mensagem vazia)"})
            _juntar(convertidas, "user", blocos)
        elif isinstance(mensagem, TurnoAssistente):
            if mensagem.resposta is not None and mensagem.resposta.bruto is not None:
                _juntar(convertidas, "assistant", list(mensagem.resposta.bruto))
            elif mensagem.texto:
                _juntar(convertidas, "assistant", [{"type": "text", "text": mensagem.texto}])
        elif isinstance(mensagem, ResultadosFerramentas):
            blocos = [
                {
                    "type": "tool_result",
                    "tool_use_id": r.chamada_id,
                    "content": r.conteudo,
                    "is_error": r.erro,
                }
                for r in mensagem.resultados
            ]
            _juntar(convertidas, "user", blocos)
    return convertidas


def _juntar(convertidas: list[dict], papel: str, blocos: list) -> None:
    """Mensagens seguidas do mesmo papel viram uma só (ex.: usuário mandou 2 seguidas)."""
    if convertidas and convertidas[-1]["role"] == papel:
        convertidas[-1]["content"].extend(blocos)
    else:
        convertidas.append({"role": papel, "content": blocos})
