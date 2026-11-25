"""Adaptador do simulador web.

Converte o formulário enviado pela tela do simulador em `MensagemEntrada`, chama o
núcleo e devolve a resposta em JSON. Também tem as rotas de apoio do simulador:
histórico, lista de usuários de teste, resetar usuário e servir as mídias.
"""

import json
import re
import time
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.banco.modelos import Mensagem, RevisaoAlimento
from app.banco.sessao import get_db
from app.canais.base import MensagemEntrada, MensagemSaida, Midia, TipoMidia
from app.nucleo import historico, memoria, orquestrador, perfil, registros, revisao
from app.tempo import como_utc, para_local, relogio_simulado

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
    agora_simulado: str = Form(""),
    db: Session = Depends(get_db),
) -> dict:
    """O usuário de teste mandou uma mensagem (texto, foto ou áudio).

    `agora_simulado` (opcional, "AAAA-MM-DDTHH:MM", horário de Brasília) faz o sistema
    fingir que é outro dia/hora durante esta mensagem (RF33).
    """
    inicio = time.perf_counter()
    with relogio_simulado(_ler_agora_simulado(agora_simulado)):
        entrada = adaptador.para_entrada(_validar_telefone(telefone), texto, arquivo)
        resultado = orquestrador.processar(db, entrada)
    return {
        "resposta": adaptador.responder(resultado.saida),
        "tempo_ms": round((time.perf_counter() - inicio) * 1000, 1),
        "depuracao": resultado.depuracao,  # painel de depuração (RF30)
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


@router.get("/banco/{telefone}")
def ver_banco(telefone: str, db: Session = Depends(get_db)) -> dict:
    """Refeições gravadas do usuário, agrupadas por dia (mais recente primeiro), com totais (RF31)."""
    usuario = historico.buscar_usuario(db, _validar_telefone(telefone))
    if usuario is None:
        return {"dias": [], "perfil": {}, "meta": None, "aceite": None, "pesos": [],
                "medidas": {}, "alimentos_proprios": [], "frequentes": []}

    meta = perfil.meta(usuario.perfil)
    aceite = next((c for c in reversed(usuario.consentimentos)), None)
    cabecalho = {
        "perfil": perfil.como_dict(usuario.perfil),
        "meta": meta.como_dict(),
        "aceite": (
            {"em": para_local(aceite.aceito_em).strftime("%d/%m/%Y %H:%M"), "versao": aceite.versao_termo}
            if aceite else None
        ),
        "pesos": [
            {"peso_kg": p.peso_kg, "em": para_local(p.registrado_em).strftime("%d/%m/%Y")}
            for p in usuario.pesos
        ],
        "medidas": memoria.medidas(usuario),
        "alimentos_proprios": [
            {"nome": a.nome, "porcao_g": a.porcao_g, "kcal_porcao": round(a.kcal * a.porcao_g / 100)}
            for a in usuario.alimentos_proprios
        ],
        "frequentes": memoria.itens_frequentes(db, usuario),
    }

    dias: dict[str, dict] = {}
    itens_por_dia: dict[str, list] = {}
    for refeicao in sorted(usuario.refeicoes, key=lambda r: r.data_hora, reverse=True):
        local = para_local(refeicao.data_hora)
        data = local.strftime("%d/%m/%Y")
        dias.setdefault(data, {"data": data, "refeicoes": []})
        itens_por_dia.setdefault(data, []).extend(refeicao.itens)
        dias[data]["refeicoes"].append(
            {
                "id": refeicao.id,
                "tipo": registros.TIPOS.get(refeicao.tipo, refeicao.tipo),
                "hora": local.strftime("%H:%M"),
                "totais": registros.totais(refeicao.itens),
                "itens": [_serializar_item(i) for i in refeicao.itens],
            }
        )
    for data, dia in dias.items():
        dia["totais"] = registros.totais(itens_por_dia[data])
    return {"dias": list(dias.values()), **cabecalho}


def _serializar_item(item) -> dict:
    campos = ("id", "descricao", "alimento_nome", "gramas", "kcal", "proteina", "carboidrato",
              "gordura", "estimado", "confianca", "origem", "explicacao")
    return {campo: getattr(item, campo) for campo in campos}


@router.get("/revisao")
def ver_revisao(db: Session = Depends(get_db)) -> list[dict]:
    """Fila de revisão: o que a base não tinha e a IA estimou (tarefas de cadastro)."""
    return [
        {
            "id": item.id,
            "termo": item.exemplo,
            "vezes": item.vezes,
            "ultima_estimativa": json.loads(item.ultima_estimativa) if item.ultima_estimativa else None,
            "ultimo_em": para_local(item.ultimo_em).strftime("%d/%m %H:%M"),
        }
        for item in revisao.pendentes(db)
    ]


@router.post("/revisao/{item_id}")
def marcar_revisao(item_id: int, status: str = Form(...), db: Session = Depends(get_db)) -> dict:
    """Marca um item como cadastrado (entrou na Base NutrIA) ou ignorado."""
    if status not in ("cadastrado", "ignorado", "pendente"):
        raise HTTPException(422, "status deve ser cadastrado, ignorado ou pendente.")
    item = db.get(RevisaoAlimento, item_id)
    if item is None:
        raise HTTPException(404, "Item não encontrado.")
    item.status = status
    db.commit()
    return {"id": item_id, "status": status}


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


def _ler_agora_simulado(texto: str) -> datetime | None:
    if not texto.strip():
        return None
    try:
        return datetime.fromisoformat(texto.strip())
    except ValueError as erro:
        raise HTTPException(422, "agora_simulado deve estar no formato AAAA-MM-DDTHH:MM.") from erro


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
