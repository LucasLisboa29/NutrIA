// Simulador do NutrIA: imita a tela do WhatsApp e conversa com a API local.

const $ = (id) => document.getElementById(id);
const conversa = $("conversa");
const campoTexto = $("texto");
const seletor = $("telefone");
const inputArquivo = $("arquivo");

const TELEFONE_PADRAO = "5534999990001";
let anexo = null;      // File ou Blob esperando para ser enviado
let gravador = null;   // MediaRecorder enquanto grava áudio

// ---------- Usuários de teste ----------

function telefoneAtual() {
  return seletor.value;
}

async function carregarUsuarios(selecionar) {
  const usuarios = await (await fetch("/simulador/usuarios")).json();
  const telefones = usuarios.map((u) => u.telefone);
  const salvo = lerPreferencia() || TELEFONE_PADRAO;
  const alvo = selecionar || salvo;
  if (!telefones.includes(alvo)) telefones.push(alvo);

  seletor.innerHTML = "";
  for (const tel of telefones) {
    const total = usuarios.find((u) => u.telefone === tel)?.total_mensagens ?? 0;
    const opcao = new Option(`${formatarTelefone(tel)} (${total} msgs)`, tel);
    seletor.add(opcao);
  }
  seletor.value = alvo;
  salvarPreferencia(alvo);
}

function formatarTelefone(tel) {
  // 5534999990001 -> +55 34 99999-0001
  const m = tel.match(/^(\d{2})(\d{2})(\d{4,5})(\d{4})$/);
  return m ? `+${m[1]} ${m[2]} ${m[3]}-${m[4]}` : tel;
}

function lerPreferencia() {
  try { return localStorage.getItem("nutria.telefone"); } catch { return null; }
}
function salvarPreferencia(tel) {
  try { localStorage.setItem("nutria.telefone", tel); } catch { /* sem armazenamento: tudo bem */ }
}

$("btn-novo").addEventListener("click", async () => {
  const sugestao = String(5534999990000 + Math.floor(Math.random() * 9000) + 100);
  const digitado = prompt("Telefone do novo usuário de teste (só números):", sugestao);
  if (!digitado) return;
  const tel = digitado.replace(/\D/g, "");
  if (tel.length < 8 || tel.length > 15) return alert("Use de 8 a 15 dígitos.");
  await carregarUsuarios(tel);
  await carregarHistorico();
  carregarBanco();
});

seletor.addEventListener("change", async () => {
  salvarPreferencia(telefoneAtual());
  await carregarHistorico();
  carregarBanco();
});

$("btn-resetar").addEventListener("click", async () => {
  const tel = telefoneAtual();
  if (!confirm(`Apagar toda a conversa de ${formatarTelefone(tel)}?`)) return;
  await fetch(`/simulador/usuarios/${tel}`, { method: "DELETE" });
  await carregarUsuarios(tel);
  await carregarHistorico();
  carregarBanco();
});

// ---------- Conversa ----------

async function carregarHistorico() {
  const mensagens = await (await fetch(`/simulador/historico/${telefoneAtual()}`)).json();
  conversa.innerHTML = "";
  ultimoDia = null;
  for (const m of mensagens) desenharMensagem(m);
  rolarParaBaixo();
}

let ultimoDia = null;

function desenharMensagem({ direcao, texto, tipo_midia, url_midia, horario }, extraClasse = "") {
  const data = new Date(horario);
  const dia = data.toLocaleDateString("pt-BR");
  if (dia !== ultimoDia) {
    ultimoDia = dia;
    const sep = document.createElement("div");
    sep.className = "separador";
    sep.textContent = rotuloDia(data);
    conversa.append(sep);
  }

  const balao = document.createElement("div");
  balao.className = `balao ${direcao} ${extraClasse}`.trim();

  if (tipo_midia === "imagem" && url_midia) {
    const img = document.createElement("img");
    img.src = url_midia;
    img.alt = "Foto enviada";
    img.addEventListener("load", rolarParaBaixo);
    balao.append(img);
  } else if (tipo_midia === "audio" && url_midia) {
    const audio = document.createElement("audio");
    audio.controls = true;
    audio.src = url_midia;
    balao.append(audio);
  }

  if (texto) {
    const corpo = document.createElement("span");
    corpo.innerHTML = formatarWhatsApp(texto);
    balao.append(corpo);
  }

  const hora = document.createElement("span");
  hora.className = "hora";
  hora.textContent = data.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  balao.append(hora);

  conversa.append(balao);
  return balao;
}

function rotuloDia(data) {
  const hoje = new Date();
  const ontem = new Date(Date.now() - 86400000);
  if (data.toDateString() === hoje.toDateString()) return "Hoje";
  if (data.toDateString() === ontem.toDateString()) return "Ontem";
  return data.toLocaleDateString("pt-BR");
}

// Mesmas marcações do WhatsApp: *negrito*, _itálico_, ~riscado~.
// Regra do WhatsApp: o texto "encosta" nos símbolos (sem espaço por dentro) e, por fora,
// há começo/fim de linha, espaço ou pontuação. Assim "(~150 g), feijão (~140 g)" NÃO vira
// riscado: o "~" ali significa "aproximadamente".
function marcacao(simbolo, tag) {
  const s = `\\${simbolo}`;
  return [
    new RegExp(`(^|[\\s(])${s}([^\\s${s}](?:[^${s}\\n]*[^\\s${s}])?)${s}(?=$|[\\s.,!?;:)])`, "gm"),
    `$1<${tag}>$2</${tag}>`,
  ];
}

function formatarWhatsApp(texto) {
  const seguro = texto
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return seguro
    .replace(...marcacao("*", "strong"))
    .replace(...marcacao("_", "em"))
    .replace(...marcacao("~", "s"))
    .replace(/\n/g, "<br>");
}

function rolarParaBaixo() {
  conversa.scrollTop = conversa.scrollHeight;
}

// ---------- "digitando..." ----------

function mostrarDigitando() {
  $("status").textContent = "digitando...";
  const balao = document.createElement("div");
  balao.className = "balao saida digitando";
  balao.id = "digitando";
  balao.innerHTML = "<span></span><span></span><span></span>";
  conversa.append(balao);
  rolarParaBaixo();
}

function esconderDigitando() {
  $("status").textContent = "online";
  $("digitando")?.remove();
}

// ---------- Enviar ----------

$("form").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  await enviar(campoTexto.value, anexo);
});

async function enviar(texto, arquivo) {
  texto = texto.trim();
  if (!texto && !arquivo) return;

  const tipo = arquivo ? (arquivo.type.startsWith("image/") ? "imagem" : "audio") : null;
  desenharMensagem({
    direcao: "entrada",
    texto,
    tipo_midia: tipo,
    url_midia: arquivo ? URL.createObjectURL(arquivo) : null,
    horario: new Date().toISOString(),
  });
  campoTexto.value = "";
  limparAnexo();
  rolarParaBaixo();

  const dados = new FormData();
  dados.append("telefone", telefoneAtual());
  dados.append("texto", texto);
  if (arquivo) dados.append("arquivo", arquivo, arquivo.name || nomeDoAudio(arquivo.type));

  travarEnvio(true);
  mostrarDigitando();
  try {
    const resposta = await fetch("/simulador/mensagem", { method: "POST", body: dados });
    const json = await resposta.json();
    esconderDigitando();
    if (!resposta.ok) {
      desenharMensagem({ direcao: "saida", texto: `⚠️ Erro ${resposta.status}: ${json.detail}`,
        horario: new Date().toISOString() }, "erro");
    } else {
      desenharMensagem({ direcao: "saida", ...json.resposta });
      mostrarDepuracao(json);
      carregarBanco();
    }
  } catch (erro) {
    esconderDigitando();
    desenharMensagem({ direcao: "saida", texto: `⚠️ Servidor fora do ar? (${erro.message})`,
      horario: new Date().toISOString() }, "erro");
  } finally {
    travarEnvio(false);
    rolarParaBaixo();
    campoTexto.focus();
    carregarUsuarios(telefoneAtual()); // atualiza a contagem de mensagens
  }
}

function travarEnvio(travar) {
  for (const id of ["btn-enviar", "btn-anexo", "btn-microfone"]) $(id).disabled = travar;
}

// ---------- Anexos: foto ou arquivo de áudio ----------

$("btn-anexo").addEventListener("click", () => inputArquivo.click());
inputArquivo.addEventListener("change", () => {
  if (inputArquivo.files[0]) definirAnexo(inputArquivo.files[0]);
});
$("btn-tirar-anexo").addEventListener("click", limparAnexo);

function definirAnexo(arquivo) {
  anexo = arquivo;
  const icone = arquivo.type.startsWith("image/") ? "📷" : "🎤";
  $("previa-nome").textContent = `${icone} ${arquivo.name || "áudio gravado"}`;
  $("previa").hidden = false;
  campoTexto.placeholder = "Legenda (opcional)";
  campoTexto.focus();
}

function limparAnexo() {
  anexo = null;
  inputArquivo.value = "";
  $("previa").hidden = true;
  campoTexto.placeholder = "Mensagem";
}

// ---------- Gravar áudio pelo microfone ----------

$("btn-microfone").addEventListener("click", async () => {
  if (gravador) {
    gravador.stop();
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    return alert("Este navegador não permite gravar áudio aqui.");
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    return alert("Sem permissão para usar o microfone.");
  }

  // O WhatsApp usa ogg/opus. O Chrome só grava webm/opus, que também serve.
  const formato = ["audio/ogg;codecs=opus", "audio/webm;codecs=opus", "audio/webm"]
    .find((f) => MediaRecorder.isTypeSupported(f));
  gravador = new MediaRecorder(stream, formato ? { mimeType: formato } : undefined);
  const pedacos = [];
  gravador.addEventListener("dataavailable", (e) => pedacos.push(e.data));
  gravador.addEventListener("stop", async () => {
    stream.getTracks().forEach((t) => t.stop());
    $("btn-microfone").classList.remove("gravando");
    const blob = new Blob(pedacos, { type: gravador.mimeType });
    gravador = null;
    await enviar(campoTexto.value, blob); // áudio vai direto, como no WhatsApp
  });
  gravador.start();
  $("btn-microfone").classList.add("gravando");
});

function nomeDoAudio(mime) {
  return mime.includes("ogg") ? "gravacao.ogg" : "gravacao.webm";
}

// ---------- Painel: abas ----------

for (const aba of document.querySelectorAll(".aba")) {
  aba.addEventListener("click", () => {
    for (const outra of document.querySelectorAll(".aba")) {
      const ativa = outra === aba;
      outra.classList.toggle("ativa", ativa);
      outra.setAttribute("aria-selected", String(ativa));
      $(`aba-${outra.dataset.aba}`).hidden = !ativa;
    }
    if (aba.dataset.aba === "banco") carregarBanco();
  });
}

// ---------- Painel: depuração (RF30) ----------

const fmtMs = (ms) => (ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${Math.round(ms)} ms`);
const fmtJson = (obj) => JSON.stringify(obj, null, 2);

function mostrarDepuracao(json) {
  const d = json.depuracao || {};
  $("dep-vazio").hidden = true;
  $("dep-conteudo").hidden = false;

  $("m-tempo").textContent = fmtMs(json.tempo_ms);
  $("m-tempo-ia").textContent = d.tempo_ia_ms ? fmtMs(d.tempo_ia_ms) : "-";
  $("m-custo").textContent = d.custo_usd ? `US$ ${d.custo_usd.toFixed(5)}` : "-";
  $("m-chamadas").textContent = d.chamadas_ia ?? "-";
  $("m-modelo").textContent = d.modelo ? `Modelo: ${d.modelo} · esforço: ${d.esforco ?? "padrão"}` : "IA não usada nesta mensagem";
  const t = d.tokens || {};
  $("m-tokens").textContent = d.chamadas_ia
    ? `Tokens: ${t.entrada} entrada · ${t.cache_leitura} do cache · ${t.cache_escrita} gravados no cache · ${t.saida} saída`
    : "";

  const alerta = d.erro || d.aviso;
  $("m-alerta").hidden = !alerta;
  $("m-alerta").textContent = alerta || "";

  const lista = $("m-ferramentas");
  lista.innerHTML = "";
  if (!d.ferramentas?.length) {
    lista.innerHTML = '<p class="dica">Nenhuma nesta mensagem.</p>';
  }
  for (const f of d.ferramentas || []) {
    const bloco = document.createElement("details");
    bloco.className = `ferramenta ${f.erro ? "erro" : ""}`;
    const titulo = document.createElement("summary");
    titulo.textContent = `${f.erro ? "⚠️" : "🔧"} ${f.nome}`;
    const args = document.createElement("pre");
    args.className = "json";
    args.textContent = `Argumentos (o que a IA pediu):\n${fmtJson(f.argumentos)}\n\nResultado (o que o código devolveu):\n${fmtJson(f.resultado)}`;
    bloco.append(titulo, args);
    lista.append(bloco);
  }

  $("m-contexto").textContent = d.contexto || "(sem contexto)";
  $("m-etapas").textContent = (d.etapas || [])
    .map((e) => `${e.etapa.padEnd(32)} ${fmtMs(e.ms).padStart(9)}${e.uso ? `  ${e.uso.entrada + e.uso.cache_leitura + e.uso.cache_escrita}→${e.uso.saida} tokens` : ""}`)
    .join("\n") || "(nenhuma)";
  $("json").textContent = fmtJson(json);
}

// ---------- Painel: banco (RF31) ----------

async function carregarBanco() {
  const { dias } = await (await fetch(`/simulador/banco/${telefoneAtual()}`)).json();
  const alvo = $("banco");
  alvo.innerHTML = "";
  if (!dias.length) {
    alvo.innerHTML = '<p class="dica">Nenhuma refeição gravada para este usuário.</p>';
    return;
  }
  for (const dia of dias) {
    const blocoDia = document.createElement("div");
    blocoDia.className = "dia";
    blocoDia.innerHTML = `<div class="dia-topo"><strong>${dia.data}</strong><span>${Math.round(dia.totais.kcal)} kcal</span></div>
      <div class="macros">P ${dia.totais.proteina} g · C ${dia.totais.carboidrato} g · G ${dia.totais.gordura} g · fibra ${dia.totais.fibra} g</div>`;
    for (const ref of dia.refeicoes) {
      const blocoRef = document.createElement("div");
      blocoRef.className = "refeicao";
      blocoRef.innerHTML = `<div class="refeicao-topo"><span>${ref.tipo} · ${ref.hora}</span><span>${Math.round(ref.totais.kcal)} kcal</span></div>`;
      for (const item of ref.itens) {
        const linha = document.createElement("div");
        linha.className = "item";
        linha.title = item.explicacao; // passe o mouse para ver a conta
        const selos = [
          item.estimado ? '<span class="selo">estimado</span>' : "",
          item.confianca === "baixa" ? '<span class="selo baixa">confiança baixa</span>' : "",
          item.origem === "ia" ? '<span class="selo ia">valor da IA</span>' : "",
        ].join("");
        const nome = document.createElement("span");
        nome.textContent = `${item.alimento_nome}`;
        nome.insertAdjacentHTML("beforeend", selos);
        const valores = document.createElement("span");
        valores.className = "valores";
        valores.textContent = `${item.estimado ? "~" : ""}${Math.round(item.gramas)} g · ${Math.round(item.kcal)} kcal`;
        linha.append(nome, valores);
        blocoRef.append(linha);
      }
      blocoDia.append(blocoRef);
    }
    alvo.append(blocoDia);
  }
}

// ---------- Início ----------

(async () => {
  await carregarUsuarios();
  await carregarHistorico();
  carregarBanco();
  campoTexto.focus();
})();
