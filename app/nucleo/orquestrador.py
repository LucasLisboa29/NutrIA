"""Orquestrador: recebe a mensagem do usuário e produz a resposta do bot.

O laço de ferramentas (o "agente"):

    mensagem do usuário + histórico + contexto
        -> IA responde
        -> pediu ferramenta?  sim -> o código executa -> devolve o resultado -> IA de novo
                              não -> o texto da IA é a resposta final

Tudo o que acontece fica registrado na telemetria (tempo, tokens, custo) e volta junto
da resposta, para o painel de depuração do simulador.
"""

from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banco.modelos import Mensagem as MensagemBanco
from app.banco.modelos import Usuario
from app.canais.base import MensagemEntrada, MensagemSaida, TipoMidia
from app.config import PASTA_CONFIG, carregar_yaml
from app.ia import roteador
from app.ia.base import (
    ErroIA,
    Mensagem,
    MensagemUsuario,
    ResultadoFerramenta,
    ResultadosFerramentas,
    TurnoAssistente,
)
from app.nucleo import ferramentas, historico, perfil, registros
from app.telemetria import Telemetria
from app.tempo import agora, como_utc

MAX_PASSOS = 6  # trava de segurança: no máximo 6 idas e voltas com a IA por mensagem
HISTORICO_MENSAGENS = 12  # quantas mensagens anteriores a IA recebe (RF04)
HISTORICO_HORAS = 12  # e só as das últimas 12 horas

RESPOSTA_ERRO = "Tive um probleminha técnico agora 😕 Pode mandar de novo daqui a pouco?"


@dataclass
class Resultado:
    saida: MensagemSaida
    depuracao: dict = field(default_factory=dict)


def processar(db: Session, entrada: MensagemEntrada) -> Resultado:
    telemetria = Telemetria()
    usuario = historico.obter_ou_criar_usuario(db, entrada.remetente)
    mensagens_anteriores = _historico(db, usuario)  # antes de gravar a atual
    primeiro_contato = not usuario.mensagens
    historico.gravar_entrada(db, usuario, entrada)
    db.commit()

    aceitou = perfil.tem_aceite(usuario)
    depuracao: dict = {"ferramentas": [], "modo": "normal" if aceitou else "primeiro_contato"}
    if not aceitou and primeiro_contato:
        # Boas-vindas + termo: texto fixo, sem IA (mesmo texto para todos, rápido e grátis).
        texto = carregar_yaml("onboarding.yaml")["boas_vindas"].strip()
    elif entrada.midia is not None and not entrada.texto:
        texto = (
            "Por enquanto eu só entendo mensagens de texto 🙏 "
            "Fotos e áudios chegam em breve! Me conta por escrito o que você comeu?"
        )
    elif not roteador.ia_configurada():
        texto = (
            "⚙️ A IA ainda não está configurada (ANTHROPIC_API_KEY vazia no .env).\n"
            f"Você disse: *{entrada.texto}*"
        )
    else:
        texto = _conversar(db, usuario, entrada, mensagens_anteriores, telemetria, depuracao, aceitou)

    saida = MensagemSaida(destinatario=entrada.remetente, texto=texto)
    historico.gravar_saida(db, usuario, saida, canal=entrada.canal)
    db.commit()

    depuracao.update(telemetria.resumo())
    return Resultado(saida=saida, depuracao=depuracao)


def _conversar(
    db: Session,
    usuario: Usuario,
    entrada: MensagemEntrada,
    anteriores: list[Mensagem],
    telemetria: Telemetria,
    depuracao: dict,
    aceitou: bool,
) -> str:
    rota = roteador.rota("dia_a_dia")
    depuracao.update({"rota": rota.nome, "modelo": rota.modelo, "esforco": rota.esforco})

    # Antes do aceite (LGPD), outro prompt e só a ferramenta de aceite. Os dois conjuntos
    # ficam fixos durante o laço: trocar prompt ou ferramentas no meio invalida o cache.
    if aceitou:
        arquivo_prompt, definicoes = "prompt_sistema.md", ferramentas.DEFINICOES
        contexto = registros.texto_contexto(db, usuario)
    else:
        arquivo_prompt, definicoes = "prompt_onboarding.md", ferramentas.DEFINICOES_ONBOARDING
        contexto = registros.texto_contexto_minimo()
    sistema = (PASTA_CONFIG / arquivo_prompt).read_text(encoding="utf-8")  # RF35

    texto_usuario = entrada.texto
    if entrada.midia is not None:
        tipo = "uma foto" if entrada.midia.tipo is TipoMidia.IMAGEM else "um áudio"
        texto_usuario += f"\n[o usuário mandou {tipo}, que você ainda não consegue ver/ouvir]"
    depuracao["contexto"] = contexto

    conversa: list[Mensagem] = [*anteriores, MensagemUsuario(texto=texto_usuario, contexto=contexto)]
    ctx = ferramentas.Contexto(db=db, usuario=usuario, canal=entrada.canal)

    try:
        ia = roteador.provedor(rota.provedor)
        for passo in range(1, MAX_PASSOS + 1):
            with telemetria.etapa("ia", passo=passo, modelo=rota.modelo) as registro:
                resposta = ia.responder(
                    sistema=sistema,
                    mensagens=conversa,
                    ferramentas=definicoes,
                    modelo=rota.modelo,
                    esforco=rota.esforco,
                    max_tokens=rota.max_tokens,
                )
                registro["uso"] = resposta.uso.__dict__
                registro["custo_usd"] = roteador.custo_usd(rota.modelo, resposta.uso)
                registro["motivo_parada"] = resposta.motivo_parada

            if not resposta.chamadas:
                return resposta.texto or RESPOSTA_ERRO

            conversa.append(TurnoAssistente(resposta=resposta))
            resultados = ResultadosFerramentas()
            for chamada in resposta.chamadas:  # a IA pode pedir várias de uma vez
                resultados.resultados.append(_executar(ctx, chamada, telemetria, depuracao))
            conversa.append(resultados)

        depuracao["aviso"] = f"Parou após {MAX_PASSOS} passos sem resposta final."
        return RESPOSTA_ERRO
    except ErroIA as erro:
        # RN01: o que as ferramentas já gravaram continua gravado.
        db.rollback()
        depuracao["erro"] = str(erro)
        return RESPOSTA_ERRO


def _executar(ctx, chamada, telemetria: Telemetria, depuracao: dict) -> ResultadoFerramenta:
    with telemetria.etapa(f"ferramenta:{chamada.nome}") as registro:
        try:
            resultado = ferramentas.executar(ctx, chamada.nome, chamada.argumentos)
            erro = False
        except (ferramentas.ErroFerramenta, ValueError, KeyError, TypeError) as excecao:
            # Erro de argumento: a IA lê a mensagem e pode tentar de novo.
            ctx.db.rollback()
            resultado = {"erro": str(excecao)}
            erro = True
        registro["erro"] = erro
    depuracao["ferramentas"].append(
        {"nome": chamada.nome, "argumentos": chamada.argumentos, "resultado": resultado, "erro": erro}
    )
    return ResultadoFerramenta(chamada.id, ferramentas.como_texto(resultado), erro)


def _historico(db: Session, usuario: Usuario) -> list[Mensagem]:
    """Últimas mensagens da conversa, para a IA entender referências (RF04).

    Vão só os textos: o raciocínio interno e as chamadas de ferramenta de turnos
    passados não são guardados. Os ids que a IA precisa estão no <contexto>.
    """
    limite = agora() - timedelta(hours=HISTORICO_HORAS)
    recentes = list(
        db.scalars(
            select(MensagemBanco)
            .where(MensagemBanco.usuario_id == usuario.id)
            .order_by(MensagemBanco.id.desc())
            .limit(HISTORICO_MENSAGENS)
        )
    )
    mensagens: list[Mensagem] = []
    for m in reversed(recentes):
        if como_utc(m.criado_em) < limite:
            continue
        if m.direcao == "entrada":
            mensagens.append(MensagemUsuario(texto=m.texto or "[mídia]"))
        elif mensagens:  # a conversa enviada à IA precisa começar pelo usuário
            mensagens.append(TurnoAssistente(texto=m.texto))
    return mensagens
