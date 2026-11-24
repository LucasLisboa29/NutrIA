"""Adaptador do simulador web.

Converte o formulário enviado pela tela do simulador em `MensagemEntrada`, chama o
núcleo e devolve a resposta em JSON. Também tem as rotas de apoio do simulador:
histórico, lista de usuários de teste, resetar usuário e servir as mídias.
"""

import re
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.banco.modelos import Mensagem
from app.banco.sessao import get_db
from app.canais.base import MensagemEntrada, MensagemSaida, Midia, TipoMidia
from app.nucleo import historico, orquestrador
from app.tempo import como_utc

TAMANHO_MAXIMO = 16 * 1024 * 1024  # 16 MB, o mesmo limite de áudio do WhatsApp

router = APIRouter(prefix="/simulador", tags=["simulador"])


class AdaptadorSimulador:
    canal = "simulador"

    def para_entrada(
        self, telefone: str, texto: str, arquivo: UploadFile | None
    ) -> MensagemEntrada:
        midia = None
        if arquivo is not None and arquivo.filename:
            midia = _ler_midia(arquivo)
        texto = texto.strip()
        if not texto and midia is None:
            raise HTTPException(400, "Mensagem vazia: mande um texto, uma foto ou um áudio.")
        return MensagemEntrada(canal=self.canal, remetente=telefone, texto=texto, midia=midia)

    def responder(self, saida: MensagemSaida) -> dict:
        return {"texto": saida.texto, "horario": como_utc(saida.horario).isoformat()}


adaptador = AdaptadorSimulador()


@router.post("/mensagem")
def receber_mensagem(
    telefone: str = Form(...),
    texto: str = Form(""),
    arquivo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
) -> dict:
    """O usuário de teste mandou uma mensagem (texto, foto ou áudio)."""
    inicio = time.perf_counter()
    entrada = adaptador.para_entrada(_validar_telefone(telefone), texto, arquivo)
    saida = orquestrador.processar(db, entrada)
    return {
        "resposta": adaptador.responder(saida),
        "tempo_ms": round((time.perf_counter() - inicio) * 1000, 1),
    }


@router.get("/usuarios")
def listar_usuarios(db: Session = Depends(get_db)) -> list[dict]:
    return [
        {"telefone": usuario.telefone, "total_mensagens": total}
        for usuario, total in historico.listar_usuarios(db)
    ]


@router.get("/historico/{telefone}")
def ver_historico(telefone: str, db: Session = Depends(get_db)) -> list[dict]:
    usuario = historico.buscar_usuario(db, _validar_telefone(telefone))
    if usuario is None:
        return []
    return [_serializar(m) for m in historico.listar_mensagens(db, usuario)]


@router.delete("/usuarios/{telefone}")
def resetar_usuario(telefone: str, db: Session = Depends(get_db)) -> dict:
    """Apaga o usuário e tudo dele, para recomeçar a conversa do zero (RF32)."""
    usuario = historico.buscar_usuario(db, _validar_telefone(telefone))
    if usuario is None:
        return {"apagado": False}
    historico.apagar_usuario(db, usuario)
    return {"apagado": True}


@router.get("/midia/{mensagem_id}")
def ver_midia(mensagem_id: int, db: Session = Depends(get_db)) -> FileResponse:
    mensagem = db.get(Mensagem, mensagem_id)
    caminho = historico.caminho_absoluto(mensagem) if mensagem else None
    if caminho is None or not caminho.exists():
        raise HTTPException(404, "Mídia não encontrada.")
    return FileResponse(caminho, media_type=mensagem.mime_midia)


def _validar_telefone(telefone: str) -> str:
    """Fica só com os dígitos. Telefones têm de 8 a 15 dígitos (padrão internacional)."""
    digitos = re.sub(r"\D", "", telefone)
    if not 8 <= len(digitos) <= 15:
        raise HTTPException(422, "Telefone inválido: use de 8 a 15 dígitos.")
    return digitos


def _ler_midia(arquivo: UploadFile) -> Midia:
    mime = (arquivo.content_type or "").lower()
    if mime.startswith("image/"):
        tipo = TipoMidia.IMAGEM
    elif mime.startswith("audio/") or mime.startswith("video/webm"):
        # O Chrome às vezes marca a gravação do microfone como "video/webm".
        tipo = TipoMidia.AUDIO
    else:
        raise HTTPException(415, "Só aceito foto ou áudio.")

    conteudo = arquivo.file.read(TAMANHO_MAXIMO + 1)
    if len(conteudo) > TAMANHO_MAXIMO:
        raise HTTPException(413, "Arquivo grande demais (máximo de 16 MB).")
    return Midia(tipo=tipo, conteudo=conteudo, mime=mime, nome_arquivo=arquivo.filename or "")


def _serializar(mensagem: Mensagem) -> dict:
    return {
        "id": mensagem.id,
        "direcao": mensagem.direcao,
        "texto": mensagem.texto,
        "tipo_midia": mensagem.tipo_midia,
        "url_midia": f"/simulador/midia/{mensagem.id}" if mensagem.caminho_midia else None,
        "horario": como_utc(mensagem.criado_em).isoformat(),
    }
