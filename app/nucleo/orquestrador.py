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
from app.audio.base import ErroTranscricao
from app.ia.base import (
    ErroIA,
    Imagem,
    Mensagem,
    MensagemUsuario,
    ResultadoFerramenta,
    ResultadosFerramentas,
    TurnoAssistente,
)
from app.ia.imagens import preparar as preparar_imagem
from app.ia.imagens import tokens_estimados
from app.nucleo import ferramentas, historico, perfil, registros
from app.telemetria import Telemetria
from app.tempo import agora, como_utc, para_local

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
    mensagem_entrada = historico.gravar_entrada(db, usuario, entrada)
    db.commit()

    aceitou = perfil.tem_aceite(usuario)
    depuracao: dict = {"ferramentas": [], "modo": "normal" if aceitou else "primeiro_contato"}
    if not aceitou and primeiro_contato:
        # Boas-vindas + termo: texto fixo, sem IA (mesmo texto para todos, rápido e grátis).
        texto = carregar_yaml("onboarding.yaml")["boas_vindas"].strip()
    elif not roteador.ia_configurada():
        texto = (
            "⚙️ A IA ainda não está configurada (ANTHROPIC_API_KEY vazia no .env).\n"
            f"Você disse: *{entrada.texto}*"
        )
    else:
        texto_usuario, resposta_pronta = _texto_da_mensagem(db, entrada, mensagem_entrada, telemetria, depuracao)
        if resposta_pronta:
            texto = resposta_pronta
        else:
            texto = _conversar(
                db, usuario, entrada, texto_usuario, mensagens_anteriores, telemetria,
                depuracao, aceitou, mensagem_entrada.id,
            )

    saida = MensagemSaida(destinatario=entrada.remetente, texto=texto)
    if not depuracao.get("usuario_apagado"):
        # Depois de "apagar meus dados", nada é gravado: nem a despedida (senão o usuário
        # seria recriado no banco).
        historico.gravar_saida(db, usuario, saida, canal=entrada.canal)
        db.commit()

    depuracao.update(telemetria.resumo())
    return Resultado(saida=saida, depuracao=depuracao)


def _texto_da_mensagem(db, entrada, mensagem_entrada, telemetria, depuracao) -> tuple[str, str | None]:
    """O texto que a IA vai ler. Áudio é transcrito aqui (RF03) e segue como texto.

    Devolve (texto, resposta_pronta). Se houver resposta pronta (ex.: áudio sem
    transcrição configurada), ela vai direto ao usuário, sem chamar a IA.
    """
    midia = entrada.midia
    if midia is None or midia.tipo is not TipoMidia.AUDIO:
        return entrada.texto, None

    if not roteador.audio_configurado():
        return "", "🎤 Ainda não consigo ouvir áudios aqui (GROQ_API_KEY vazia no .env). Me conta por escrito?"
    try:
        with telemetria.etapa("transcricao") as registro:
            transcricao = roteador.transcritor().transcrever(midia.conteudo, midia.mime, midia.nome_arquivo)
            registro["modelo"] = transcricao.modelo
            registro["duracao_s"] = round(transcricao.duracao_s, 1)
            registro["custo_usd"] = roteador.custo_transcricao_usd(transcricao.duracao_s)
    except (ErroTranscricao, ErroIA) as erro:
        depuracao["erro"] = str(erro)
        return "", "Não consegui ouvir seu áudio agora 😕 Pode mandar de novo ou escrever?"

    if not transcricao.texto:
        return "", "Não entendi nada nesse áudio 🤔 Pode gravar de novo, mais perto do microfone?"

    depuracao["transcricao"] = transcricao.texto
    texto = transcricao.texto if not entrada.texto else f"{entrada.texto}\n{transcricao.texto}"
    # Grava a transcrição na mensagem: o histórico e o chat passam a mostrar o que foi dito.
    mensagem_entrada.texto = texto
    db.commit()
    return texto, None


def _conversar(
    db: Session,
    usuario: Usuario,
    entrada: MensagemEntrada,
    texto_usuario: str,
    anteriores: list[Mensagem],
    telemetria: Telemetria,
    depuracao: dict,
    aceitou: bool,
    mensagem_id: int,
) -> str:
    foto = entrada.midia if entrada.midia is not None and entrada.midia.tipo is TipoMidia.IMAGEM else None
    imagens: list[Imagem] = []
    if foto is not None and aceitou:
        # Foto do prato: modelo com visão (RF02), com a imagem reduzida antes.
        preparada = preparar_imagem(foto.conteudo)
        imagens.append(Imagem(dados=preparada.dados, mime=preparada.mime))
        depuracao["imagem"] = {
            "original": preparada.tamanho_original,
            "enviada": preparada.tamanho_final,
            "tokens_estimados": tokens_estimados(preparada.largura, preparada.altura),
        }
        if not texto_usuario:
            texto_usuario = "[foto sem legenda]"
    elif foto is not None:
        # Antes do aceite a foto não é analisada (seria um dado de saúde).
        texto_usuario = f"{texto_usuario}\n[o usuário mandou uma foto]".strip()

    rota = roteador.rota("visao" if imagens else "dia_a_dia")
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

    if ferramentas.pedido_de_apagar_pendente(usuario.id):
        # Sem este aviso, a IA não liga o "sim" do usuário ao pedido de apagar e pede
        # confirmação de novo, em laço (visto no teste com a IA real).
        contexto = contexto.replace(
            "</contexto>",
            "ATENÇÃO: há um pedido de APAGAR TODOS OS DADOS aguardando confirmação. Se o "
            "usuário confirmar nesta mensagem, chame apagar_meus_dados com confirmado=true. "
            "Se ele desistir, não chame.\n</contexto>",
        )
    depuracao["contexto"] = contexto

    conversa: list[Mensagem] = [
        *anteriores,
        MensagemUsuario(texto=texto_usuario, contexto=contexto, imagens=imagens),
    ]
    ctx = ferramentas.Contexto(db=db, usuario=usuario, canal=entrada.canal, mensagem_id=mensagem_id)

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
                if ctx.usuario_apagado:
                    # Tudo apagado: encerra sem chamar a IA de novo (o histórico não existe mais).
                    depuracao["usuario_apagado"] = True
                    return carregar_yaml("onboarding.yaml")["despedida"].strip()
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
        except (ferramentas.ErroFerramenta, ValueError, LookupError, TypeError) as excecao:
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
            # Com data e hora: sem isso, a IA não sabe que uma conversa foi "ontem" e acha
            # que as refeições sumiram dos registros de hoje.
            quando = para_local(m.criado_em).strftime("%d/%m %H:%M")
            conteudo = m.texto or ""
            if m.tipo_midia == "imagem":
                # A foto não é reenviada (custaria tokens a cada mensagem); fica o aviso.
                conteudo = f"[foto] {conteudo}".strip()
            mensagens.append(MensagemUsuario(texto=f"[{quando}] {conteudo or '[mídia]'}"))
        elif mensagens:  # a conversa enviada à IA precisa começar pelo usuário
            mensagens.append(TurnoAssistente(texto=m.texto))
    return mensagens
