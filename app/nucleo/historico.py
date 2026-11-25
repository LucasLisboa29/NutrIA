"""Histórico da conversa: usuários, mensagens e arquivos de mídia.

Fica no núcleo (e não no canal) porque qualquer canal grava do mesmo jeito.
As mídias são salvas em `uploads/<id do usuário>/`. A pasta usa o id, e não o
telefone, para o telefone não aparecer em nomes de arquivo (LGPD).
"""

import mimetypes
import shutil
import uuid
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.banco.modelos import (
    AlimentoUsuario,
    Consentimento,
    HistoricoPeso,
    ItemRefeicao,
    MedidaUsuario,
    Mensagem,
    Perfil,
    Refeicao,
    Usuario,
)
from app.canais.base import MensagemEntrada, MensagemSaida, Midia
from app.config import settings


def obter_ou_criar_usuario(db: Session, telefone: str) -> Usuario:
    usuario = db.scalar(select(Usuario).where(Usuario.telefone == telefone))
    if usuario is None:
        usuario = Usuario(telefone=telefone)
        db.add(usuario)
        db.flush()  # gera o id agora, antes do commit
    return usuario


def buscar_usuario(db: Session, telefone: str) -> Usuario | None:
    return db.scalar(select(Usuario).where(Usuario.telefone == telefone))


def gravar_entrada(db: Session, usuario: Usuario, entrada: MensagemEntrada) -> Mensagem:
    mensagem = Mensagem(
        usuario_id=usuario.id,
        direcao="entrada",
        canal=entrada.canal,
        texto=entrada.texto,
        criado_em=entrada.horario,
    )
    if entrada.midia is not None:
        mensagem.tipo_midia = entrada.midia.tipo.value
        mensagem.mime_midia = entrada.midia.mime
        mensagem.caminho_midia = _salvar_midia(usuario.id, entrada.midia)
    db.add(mensagem)
    return mensagem


def gravar_saida(db: Session, usuario: Usuario, saida: MensagemSaida, canal: str) -> Mensagem:
    mensagem = Mensagem(
        usuario_id=usuario.id,
        direcao="saida",
        canal=canal,
        texto=saida.texto,
        criado_em=saida.horario,
    )
    db.add(mensagem)
    return mensagem


def listar_mensagens(db: Session, usuario: Usuario) -> list[Mensagem]:
    return list(
        db.scalars(select(Mensagem).where(Mensagem.usuario_id == usuario.id).order_by(Mensagem.id))
    )


def listar_usuarios(db: Session) -> list[tuple[Usuario, int]]:
    """Todos os usuários com a contagem de mensagens de cada um."""
    consulta = (
        select(Usuario, func.count(Mensagem.id))
        .outerjoin(Mensagem)
        .group_by(Usuario.id)
        .order_by(Usuario.id)
    )
    return [(usuario, total) for usuario, total in db.execute(consulta)]


def caminho_absoluto(mensagem: Mensagem) -> Path | None:
    if not mensagem.caminho_midia:
        return None
    return settings.pasta_uploads / mensagem.caminho_midia


def apagar_usuario(db: Session, usuario: Usuario) -> None:
    """Apaga de verdade todos os dados do usuário (RF26, RF32, LGPD).

    Apaga tabela por tabela, direto no banco, em vez de confiar só no "cascade" do
    SQLAlchemy: o cascade só enxerga o que já foi carregado na memória (uma mensagem
    gravada há pouco podia escapar), e o SQLite não aplica o ON DELETE CASCADE sozinho.
    Para a LGPD, "quase tudo" não serve.
    """
    usuario_id = usuario.id
    pasta = settings.pasta_uploads / str(usuario_id)
    db.flush()  # grava o que estiver pendente antes, para apagar junto
    refeicoes = select(Refeicao.id).where(Refeicao.usuario_id == usuario_id)
    db.execute(delete(ItemRefeicao).where(ItemRefeicao.refeicao_id.in_(refeicoes)))
    for tabela in (Refeicao, Mensagem, HistoricoPeso, Consentimento, Perfil, MedidaUsuario, AlimentoUsuario):
        db.execute(delete(tabela).where(tabela.usuario_id == usuario_id))
    db.execute(delete(Usuario).where(Usuario.id == usuario_id))
    db.commit()
    db.expunge_all()  # esquece os objetos na memória: eles não existem mais no banco
    shutil.rmtree(pasta, ignore_errors=True)


def _salvar_midia(usuario_id: int, midia: Midia) -> str:
    extensao = (
        mimetypes.guess_extension(midia.mime.split(";")[0])
        or Path(midia.nome_arquivo).suffix
        or ".bin"
    )
    relativo = Path(str(usuario_id)) / f"{uuid.uuid4().hex}{extensao}"
    destino = settings.pasta_uploads / relativo
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(midia.conteudo)
    return relativo.as_posix()
