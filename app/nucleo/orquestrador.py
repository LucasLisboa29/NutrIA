"""Orquestrador: recebe a mensagem do usuário e produz a resposta do bot.

Versão provisória da Fase 1: um bot "eco" que só repete o que recebeu. Serve para testar
o caminho completo (canal → núcleo → banco → resposta) antes de ligar a IA.
Na Fase 3, `_gerar_resposta` passa a chamar a IA e as ferramentas de registro.
"""

from sqlalchemy.orm import Session

from app.canais.base import MensagemEntrada, MensagemSaida, TipoMidia
from app.nucleo import historico


def processar(db: Session, entrada: MensagemEntrada) -> MensagemSaida:
    usuario = historico.obter_ou_criar_usuario(db, entrada.remetente)
    historico.gravar_entrada(db, usuario, entrada)

    saida = MensagemSaida(destinatario=entrada.remetente, texto=_gerar_resposta(entrada))

    historico.gravar_saida(db, usuario, saida, canal=entrada.canal)
    db.commit()
    return saida


def _gerar_resposta(entrada: MensagemEntrada) -> str:
    partes = []
    if entrada.midia is not None:
        if entrada.midia.tipo is TipoMidia.IMAGEM:
            partes.append("📷 Recebi sua foto.")
        else:
            partes.append("🎤 Recebi seu áudio.")
    if entrada.texto:
        partes.append(f"Você disse: *{entrada.texto}*")
    return "\n".join(partes)
