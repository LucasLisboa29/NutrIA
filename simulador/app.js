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
});

seletor.addEventListener("change", async () => {
  salvarPreferencia(telefoneAtual());
  await carregarHistorico();
});

$("btn-resetar").addEventListener("click", async () => {
  const tel = telefoneAtual();
  if (!confirm(`Apagar toda a conversa de ${formatarTelefone(tel)}?`)) return;
  await fetch(`/simulador/usuarios/${tel}`, { method: "DELETE" });
  await carregarUsuarios(tel);
  await carregarHistorico();
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
function formatarWhatsApp(texto) {
  const seguro = texto
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return seguro
    .replace(/\*([^*\n]+)\*/g, "<strong>$1</strong>")
    .replace(/(^|\s)_([^_\n]+)_/g, "$1<em>$2</em>")
    .replace(/~([^~\n]+)~/g, "<s>$1</s>")
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
    $("json").textContent = JSON.stringify(json, null, 2);
    esconderDigitando();
    if (!resposta.ok) {
      desenharMensagem({ direcao: "saida", texto: `⚠️ Erro ${resposta.status}: ${json.detail}`,
        horario: new Date().toISOString() }, "erro");
    } else {
      $("tempo").textContent = `${json.tempo_ms} ms`;
      desenharMensagem({ direcao: "saida", ...json.resposta });
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

// ---------- Início ----------

(async () => {
  await carregarUsuarios();
  await carregarHistorico();
  campoTexto.focus();
})();
