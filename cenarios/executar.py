"""Executor de cenários (Fase 7, RF34): roda conversas de teste com a IA DE VERDADE e
mostra o que passou, o que falhou, quanto custou e quanto demorou.

Diferente do pytest (que usa uma IA falsa e é grátis), aqui cada mensagem vai para a API
e custa dinheiro. Serve para calibrar: mudou o prompt? Roda de novo e vê se algo piorou.

Uso (com o .venv ativo, na raiz do projeto):

    python -m cenarios.executar                      # todos os cenários
    python -m cenarios.executar bife ovo             # só os que têm "bife" ou "ovo" no nome
    python -m cenarios.executar --repetir 3          # cada cenário 3 vezes (a IA varia!)
    python -m cenarios.executar --modelo claude-sonnet-5-5 --esforco medium
    python -m cenarios.executar --listar             # só lista, sem chamar a IA

O formato dos arquivos .yaml está em `cenarios/LEIAME.md`.

Tudo roda num banco temporário: o `nutria.db` de desenvolvimento não é tocado, e nenhum
servidor precisa estar ligado.
"""

import argparse
import json
import os
import re
import sys
import tempfile
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

PASTA_CENARIOS = Path(__file__).parent
PASTA_RELATORIOS = PASTA_CENARIOS / "relatorios"

# Banco e uploads temporários. Precisa vir ANTES de importar o app: as configurações são
# lidas na importação (mesmo truque do tests/conftest.py).
_PASTA_TEMP = Path(tempfile.mkdtemp(prefix="nutria_cenarios_"))
os.environ["DATABASE_URL"] = f"sqlite:///{_PASTA_TEMP / 'cenarios.db'}"
os.environ["PASTA_UPLOADS"] = str(_PASTA_TEMP / "uploads")

import yaml  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.banco.modelos import Refeicao, Usuario  # noqa: E402
from app.banco.sessao import Base, SessaoLocal, engine  # noqa: E402
from app.canais.base import MensagemEntrada, Midia, TipoMidia  # noqa: E402
from app.ia import roteador  # noqa: E402
from app.nucleo import memoria, orquestrador, perfil  # noqa: E402
from app.nutricao.importar_taco import garantir_base  # noqa: E402
from app.tempo import fuso_local, para_local, relogio_simulado  # noqa: E402

# ---------------------------------------------------------------- leitura dos cenários

CHAVES_CENARIO = {"nome", "descricao", "tags", "agora", "usuario", "conversa", "final"}
CHAVES_MENSAGEM = {"usuario", "foto", "agora", "espera"}
CHAVES_ESPERA = {
    "ferramentas", "sem_ferramentas", "max_perguntas", "max_chamadas_ia",
    "resposta_contem", "resposta_contem_algum", "resposta_nao_contem", "max_linhas",
}
CHAVES_FINAL = {"refeicoes", "total_kcal", "sem_estimativa_ia", "perfil", "aceite", "usuario_existe", "medidas"}
CHAVES_REFEICAO = {"tipo", "dia", "kcal", "itens", "contem", "nao_contem", "item"}


def carregar_cenarios(pasta: Path = PASTA_CENARIOS) -> list[dict]:
    """Lê todos os .yaml da pasta. Cada arquivo tem uma lista `cenarios:`."""
    cenarios = []
    for arquivo in sorted(pasta.glob("*.yaml")):
        dados = yaml.safe_load(arquivo.read_text(encoding="utf-8")) or {}
        for cenario in dados.get("cenarios", []):
            cenario["_arquivo"] = arquivo.name
            cenarios.append(cenario)
    return cenarios


def validar(cenario: dict) -> list[str]:
    """Erros de formato (chave escrita errado, faltando...). Pego antes de gastar API."""
    erros = []
    nome = cenario.get("nome", "?")

    def checar(dic, permitidas, onde):
        for chave in dic or {}:
            if chave not in permitidas:
                erros.append(f"{nome}: chave desconhecida {chave!r} em {onde}")

    checar({k: v for k, v in cenario.items() if not k.startswith("_")}, CHAVES_CENARIO, "cenário")
    if not cenario.get("nome"):
        erros.append(f"{cenario.get('_arquivo')}: cenário sem nome")
    if not cenario.get("conversa"):
        erros.append(f"{nome}: sem conversa")
    for i, msg in enumerate(cenario.get("conversa") or [], 1):
        checar(msg, CHAVES_MENSAGEM, f"mensagem {i}")
        if "usuario" not in msg and "foto" not in msg:
            erros.append(f"{nome}: mensagem {i} sem texto nem foto")
        checar(msg.get("espera"), CHAVES_ESPERA, f"espera da mensagem {i}")
    final = cenario.get("final") or {}
    checar(final, CHAVES_FINAL, "final")
    for i, ref in enumerate(final.get("refeicoes") or [], 1):
        checar(ref, CHAVES_REFEICAO, f"refeição {i} do final")
    return erros


# ---------------------------------------------------------------- execução


@dataclass
class Mensagem:
    texto: str
    resposta: str
    ferramentas: list[str]
    chamadas_ia: int
    tempo_s: float
    custo_usd: float
    erro: str | None = None


@dataclass
class Resultado:
    nome: str
    falhas: list[str] = field(default_factory=list)
    mensagens: list[Mensagem] = field(default_factory=list)
    final: dict = field(default_factory=dict)

    @property
    def passou(self) -> bool:
        return not self.falhas

    @property
    def custo(self) -> float:
        return sum(m.custo_usd for m in self.mensagens)

    @property
    def tempo_max(self) -> float:
        return max((m.tempo_s for m in self.mensagens), default=0)


def _hora(texto: str | None, base: datetime) -> datetime:
    """'12:40' (hoje), 'ontem 20:00' ou '2026-11-25 12:40', no horário de Brasília."""
    if not texto:
        return base
    texto = str(texto).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}", texto):
        return datetime.strptime(texto, "%Y-%m-%d %H:%M").replace(tzinfo=fuso_local())
    dia = base.date()
    if texto.startswith("ontem "):
        dia, texto = dia - timedelta(days=1), texto[6:]
    hora, minuto = (int(x) for x in texto.split(":"))
    return datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=fuso_local())


def _sem_acento(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return texto.lower()


def contar_perguntas(texto: str) -> int:
    """Quantas frases terminam em '?'. Aproximado, mas serve para "fez 3 perguntas"."""
    return len(re.findall(r"[^.!?\n]*[a-zA-ZÀ-ú0-9)][^.!?\n]*\?", texto or ""))


def _faixa(valor: float, faixa) -> bool:
    if isinstance(faixa, (int, float)):
        return abs(valor - faixa) < 0.01
    minimo, maximo = faixa
    return minimo <= valor <= maximo


def executar(cenario: dict, numero: int) -> Resultado:
    resultado = Resultado(nome=cenario["nome"])
    telefone = f"55340000{numero:05d}"
    hoje = datetime.now(fuso_local())
    momento = _hora(cenario.get("agora", "12:40"), hoje.replace(second=0, microsecond=0))

    with SessaoLocal() as db:
        _preparar_usuario(db, telefone, cenario.get("usuario") or {})

    for i, msg in enumerate(cenario["conversa"], 1):
        momento = _hora(msg.get("agora"), momento) if msg.get("agora") else momento
        entrada = MensagemEntrada(canal="simulador", remetente=telefone, texto=msg.get("usuario", ""))
        if msg.get("foto"):
            caminho = (PASTA_CENARIOS / msg["foto"]).resolve()
            if not caminho.exists():
                resultado.falhas.append(f"msg {i}: foto não encontrada ({msg['foto']})")
                return resultado
            mime = "image/png" if caminho.suffix.lower() == ".png" else "image/jpeg"
            entrada.midia = Midia(tipo=TipoMidia.IMAGEM, conteudo=caminho.read_bytes(), mime=mime, nome_arquivo=caminho.name)

        inicio = time.perf_counter()
        with relogio_simulado(momento), SessaoLocal() as db:
            entrada.horario = momento
            saida = orquestrador.processar(db, entrada)
        dep = saida.depuracao
        registro = Mensagem(
            texto=entrada.texto or f"[foto {msg.get('foto')}]",
            resposta=saida.saida.texto,
            ferramentas=[f["nome"] for f in dep.get("ferramentas", [])],
            chamadas_ia=dep.get("chamadas_ia", 0),
            tempo_s=round(time.perf_counter() - inicio, 2),
            custo_usd=dep.get("custo_usd", 0.0),
            erro=dep.get("erro") or dep.get("aviso"),
        )
        resultado.mensagens.append(registro)
        if registro.erro:
            resultado.falhas.append(f"msg {i}: erro no processamento: {registro.erro}")
        _conferir_mensagem(i, msg.get("espera") or {}, registro, resultado.falhas)
        momento += timedelta(minutes=2)  # a próxima mensagem chega um pouco depois

    with relogio_simulado(momento), SessaoLocal() as db:
        resultado.final = _estado_final(db, telefone)
        _conferir_final(cenario.get("final") or {}, resultado.final, momento.date(), resultado.falhas)
    return resultado


def _preparar_usuario(db, telefone: str, config: dict) -> None:
    from app.nucleo import historico

    usuario = historico.obter_ou_criar_usuario(db, telefone)
    if config.get("aceite", True):
        perfil.registrar_aceite(db, usuario, "simulador")
        # Sem nenhuma mensagem, o orquestrador acha que é o primeiro contato e manda as
        # boas-vindas fixas. Uma mensagem antiga (de 2 dias atrás) evita isso sem entrar
        # no histórico que a IA lê (que é só das últimas 12 h).
        from app.banco.modelos import Mensagem as MensagemBanco

        antiga = datetime.now(fuso_local()) - timedelta(days=2)
        db.add(MensagemBanco(usuario_id=usuario.id, direcao="entrada", canal="simulador", texto="oi", criado_em=antiga))
    if config.get("perfil"):
        perfil.atualizar(db, usuario, config["perfil"])
    for medida in config.get("medidas") or []:
        memoria.ensinar_medida(db, usuario, medida["unidade"], medida["gramas"])
    db.commit()


def _conferir_mensagem(i: int, espera: dict, m: Mensagem, falhas: list[str]) -> None:
    for nome in espera.get("ferramentas") or []:
        if nome not in m.ferramentas:
            falhas.append(f"msg {i}: esperava a ferramenta {nome} (chamou {m.ferramentas or 'nenhuma'})")
    for nome in espera.get("sem_ferramentas") or []:
        if nome == "*" and m.ferramentas:
            falhas.append(f"msg {i}: não devia chamar ferramenta (chamou {m.ferramentas})")
        elif nome in m.ferramentas:
            falhas.append(f"msg {i}: não devia chamar {nome}")
    if "max_perguntas" in espera and (n := contar_perguntas(m.resposta)) > espera["max_perguntas"]:
        falhas.append(f"msg {i}: {n} perguntas (máximo {espera['max_perguntas']})")
    if "max_chamadas_ia" in espera and m.chamadas_ia > espera["max_chamadas_ia"]:
        falhas.append(f"msg {i}: {m.chamadas_ia} chamadas à IA (máximo {espera['max_chamadas_ia']})")
    if "max_linhas" in espera and (n := len([x for x in m.resposta.splitlines() if x.strip()])) > espera["max_linhas"]:
        falhas.append(f"msg {i}: resposta com {n} linhas (máximo {espera['max_linhas']})")
    resposta = _sem_acento(m.resposta)
    for trecho in espera.get("resposta_contem") or []:
        if _sem_acento(trecho) not in resposta:
            falhas.append(f"msg {i}: resposta sem {trecho!r}")
    if (algum := espera.get("resposta_contem_algum")) and not any(_sem_acento(t) in resposta for t in algum):
        falhas.append(f"msg {i}: resposta sem nenhum de {algum}")
    for trecho in espera.get("resposta_nao_contem") or []:
        if _sem_acento(trecho) in resposta:
            falhas.append(f"msg {i}: resposta não devia ter {trecho!r}")


def _estado_final(db, telefone: str) -> dict:
    """Foto do banco no fim da conversa (vai para o relatório e é conferida)."""
    usuario = db.scalar(select(Usuario).where(Usuario.telefone == telefone))
    if usuario is None:
        return {"usuario_existe": False, "refeicoes": []}
    refeicoes = db.scalars(select(Refeicao).where(Refeicao.usuario_id == usuario.id).order_by(Refeicao.data_hora))
    return {
        "usuario_existe": True,
        "aceite": perfil.tem_aceite(usuario),
        "perfil": perfil.como_dict(usuario.perfil),
        "medidas": memoria.medidas(usuario),
        "refeicoes": [
            {
                "tipo": r.tipo,
                "data": para_local(r.data_hora).strftime("%Y-%m-%d %H:%M"),
                "kcal": round(sum(i.kcal for i in r.itens)),
                "itens": [
                    {
                        "alimento": i.alimento_nome, "descricao": i.descricao, "gramas": round(i.gramas),
                        "kcal": round(i.kcal), "origem": i.origem, "confianca": i.confianca,
                    }
                    for i in r.itens
                ],
            }
            for r in refeicoes
        ],
    }


def _item_bate(item: dict, termo: str) -> bool:
    alvo = _sem_acento(f"{item['alimento']} {item['descricao']}")
    return all(palavra in alvo for palavra in _sem_acento(termo).split())


def _conferir_final(esperado: dict, final: dict, dia_final: date, falhas: list[str]) -> None:
    if "usuario_existe" in esperado and final["usuario_existe"] != esperado["usuario_existe"]:
        falhas.append(f"final: usuario_existe={final['usuario_existe']} (esperado {esperado['usuario_existe']})")
    if not final["usuario_existe"]:
        return
    if "aceite" in esperado and final["aceite"] != esperado["aceite"]:
        falhas.append(f"final: aceite={final['aceite']} (esperado {esperado['aceite']})")
    for campo, valor in (esperado.get("perfil") or {}).items():
        obtido = final["perfil"].get(campo)
        if obtido is None or (isinstance(valor, list) and not _faixa(obtido, valor)) or (not isinstance(valor, list) and obtido != valor):
            falhas.append(f"final: perfil.{campo}={obtido!r} (esperado {valor!r})")
    for unidade, valor in (esperado.get("medidas") or {}).items():
        obtido = final["medidas"].get(unidade)
        if obtido is None or not _faixa(obtido, valor):
            falhas.append(f"final: medida {unidade!r}={obtido} (esperado {valor})")

    refeicoes = final["refeicoes"]
    if "refeicoes" in esperado:
        lista = esperado["refeicoes"]
        if len(refeicoes) != len(lista):
            falhas.append(f"final: {len(refeicoes)} refeições gravadas (esperado {len(lista)})")
        for n, (ref, esp) in enumerate(zip(refeicoes, lista), 1):
            _conferir_refeicao(n, ref, esp, dia_final, falhas)
    todos = [i for r in refeicoes for i in r["itens"]]
    if "total_kcal" in esperado:
        total = sum(r["kcal"] for r in refeicoes)
        if not _faixa(total, esperado["total_kcal"]):
            falhas.append(f"final: total {total} kcal (esperado entre {esperado['total_kcal']})")
    if esperado.get("sem_estimativa_ia") and (ia := [i["alimento"] for i in todos if i["origem"] == "ia"]):
        falhas.append(f"final: itens com número da IA: {ia}")


def _conferir_refeicao(n: int, ref: dict, esp: dict, dia_final: date, falhas: list[str]) -> None:
    onde = f"refeição {n} ({ref['tipo']})"
    if "tipo" in esp:
        tipos = esp["tipo"] if isinstance(esp["tipo"], list) else [esp["tipo"]]
        if ref["tipo"] not in tipos:
            falhas.append(f"{onde}: tipo {ref['tipo']} (esperado {esp['tipo']})")
    if "dia" in esp:
        dia = datetime.strptime(ref["data"], "%Y-%m-%d %H:%M").date()
        esperado = {"hoje": dia_final, "ontem": dia_final - timedelta(days=1)}[esp["dia"]]
        if dia != esperado:
            falhas.append(f"{onde}: dia {dia:%d/%m} (esperado {esp['dia']})")
    if "kcal" in esp and not _faixa(ref["kcal"], esp["kcal"]):
        falhas.append(f"{onde}: {ref['kcal']} kcal (esperado entre {esp['kcal']})")
    if "itens" in esp and not _faixa(len(ref["itens"]), esp["itens"]):
        falhas.append(f"{onde}: {len(ref['itens'])} itens (esperado {esp['itens']})")
    for termo in esp.get("contem") or []:
        if not any(_item_bate(i, termo) for i in ref["itens"]):
            falhas.append(f"{onde}: sem item {termo!r} (tem {[i['alimento'] for i in ref['itens']]})")
    for termo in esp.get("nao_contem") or []:
        if any(_item_bate(i, termo) for i in ref["itens"]):
            falhas.append(f"{onde}: não devia ter {termo!r}")
    for termo, regras in (esp.get("item") or {}).items():
        achados = [i for i in ref["itens"] if _item_bate(i, termo)]
        if not achados:
            falhas.append(f"{onde}: sem item {termo!r}")
            continue
        item = achados[0]
        for campo in ("gramas", "kcal"):
            if campo in regras and not _faixa(item[campo], regras[campo]):
                falhas.append(f"{onde}: {termo} com {item[campo]} {campo} (esperado entre {regras[campo]})")


# ---------------------------------------------------------------- relatório


def _usar_modelo(modelo: str | None, esforco: str | None) -> None:
    """Troca o modelo/esforço de todas as rotas só nesta execução (para comparar modelos)."""
    if not modelo and not esforco:
        return
    original = roteador.rota

    def rota(nome):
        r = original(nome)
        r.modelo = modelo or r.modelo
        r.esforco = esforco or r.esforco
        return r

    roteador.rota = rota


def relatorio_markdown(resultados: list[Resultado], titulo: str) -> str:
    passou = sum(r.passou for r in resultados)
    mensagens = [m for r in resultados for m in r.mensagens]
    linhas = [
        f"# {titulo}",
        "",
        f"**{passou}/{len(resultados)} cenários passaram** · {len(mensagens)} mensagens · "
        f"custo US$ {sum(m.custo_usd for m in mensagens):.4f} · "
        f"tempo médio {sum(m.tempo_s for m in mensagens) / max(len(mensagens), 1):.1f} s · "
        f"pior {max((m.tempo_s for m in mensagens), default=0):.1f} s",
        "",
        "| Cenário | Resultado | Msgs | Chamadas IA | Pior tempo | Custo |",
        "|---|---|---|---|---|---|",
    ]
    for r in resultados:
        linhas.append(
            f"| {r.nome} | {'✅' if r.passou else '❌'} | {len(r.mensagens)} | "
            f"{sum(m.chamadas_ia for m in r.mensagens)} | {r.tempo_max:.1f} s | US$ {r.custo:.4f} |"
        )
    for r in resultados:
        linhas += ["", f"## {'✅' if r.passou else '❌'} {r.nome}", ""]
        for falha in r.falhas:
            linhas.append(f"- ❗ {falha}")
        for m in r.mensagens:
            ferramentas = ", ".join(m.ferramentas) or "nenhuma"
            linhas += [
                "",
                f"👤 {m.texto}",
                "",
                "🤖 " + m.resposta.replace("\n", "\n> ").strip(),
                "",
                f"<sub>{ferramentas} · {m.chamadas_ia} chamadas · {m.tempo_s} s · US$ {m.custo_usd:.4f}</sub>",
            ]
        resumo = [f"{x['tipo']} {x['data'][5:]}: {x['kcal']} kcal = " + ", ".join(
            f"{i['alimento']} {i['gramas']} g ({i['origem']})" for i in x["itens"]) for x in r.final.get("refeicoes", [])]
        linhas += ["", "**Banco no fim:** " + ("; ".join(resumo) if resumo else "nenhuma refeição")]
    return "\n".join(linhas) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Roda os cenários de teste com a IA real.")
    parser.add_argument("filtros", nargs="*", help="só cenários com algum destes trechos no nome ou nas tags")
    parser.add_argument("--repetir", type=int, default=1, help="rodar cada cenário N vezes")
    parser.add_argument("--modelo", help="força um modelo em todas as rotas (ex.: claude-sonnet-5-5)")
    parser.add_argument("--esforco", help="força um esforço (low, medium, high)")
    parser.add_argument("--listar", action="store_true", help="só lista e valida, sem chamar a IA")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # o terminal do Windows não é UTF-8 por padrão

    cenarios = carregar_cenarios()
    erros = [e for c in cenarios for e in validar(c)]
    if erros:
        print("Erros de formato nos cenários:\n  " + "\n  ".join(erros))
        return 2
    if args.filtros:
        cenarios = [c for c in cenarios if any(f in c["nome"] or f in (c.get("tags") or []) for f in args.filtros)]
    if args.listar or not cenarios:
        for c in cenarios:
            print(f"- {c['nome']} ({c['_arquivo']}, {len(c['conversa'])} msgs): {c.get('descricao', '')}")
        return 0
    if not roteador.ia_configurada():
        print("ANTHROPIC_API_KEY vazia no .env: não dá para rodar com a IA real.")
        return 2

    _usar_modelo(args.modelo, args.esforco)
    Base.metadata.create_all(bind=engine)
    with SessaoLocal() as db:
        garantir_base(db)

    resultados: list[Resultado] = []
    numero = 0
    for cenario in cenarios:
        for rodada in range(args.repetir):
            numero += 1
            nome = cenario["nome"] + (f" #{rodada + 1}" if args.repetir > 1 else "")
            print(f"▶ {nome} ...", end=" ", flush=True)
            resultado = executar(cenario, numero)
            resultado.nome = nome
            resultados.append(resultado)
            print("✅" if resultado.passou else "❌", f"US$ {resultado.custo:.4f}, pior {resultado.tempo_max:.1f} s")
            for falha in resultado.falhas:
                print(f"    ❗ {falha}")

    rota = roteador.rota("dia_a_dia")
    titulo = f"Cenários {datetime.now():%d/%m/%Y %H:%M} · {rota.modelo} ({rota.esforco})"
    PASTA_RELATORIOS.mkdir(exist_ok=True)
    base = PASTA_RELATORIOS / f"{datetime.now():%Y-%m-%d_%H%M%S}"
    base.with_suffix(".md").write_text(relatorio_markdown(resultados, titulo), encoding="utf-8")
    base.with_suffix(".json").write_text(
        json.dumps([r.__dict__ | {"mensagens": [m.__dict__ for m in r.mensagens]} for r in resultados],
                   ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    passou = sum(r.passou for r in resultados)
    print(f"\n{passou}/{len(resultados)} passaram · US$ {sum(r.custo for r in resultados):.4f} · relatório: {base.with_suffix('.md')}")
    return 0 if passou == len(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
