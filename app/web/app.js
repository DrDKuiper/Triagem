// Versão web do app HealthFlow: as mesmas 4 telas do app Android (Triagem, Unidades,
// Previsões, Info), consumindo o backend FastAPI que serve esta página ou, na versão
// estática, o mesmo backend rodando no navegador (offline.js).
"use strict";

/** Sintomas que, mesmo sem conexão com o servidor, indicam procurar emergência. */
const SINTOMAS_ALARME_OFFLINE = new Set(["dor_peito", "falta_ar", "desmaio", "confusao", "convulsao", "fraqueza_lado", "sangramento"]);
const TIPOS = ["UPA", "PS", "UBS"];
const SEMANAS_HISTORICO = 26;

const ICONE = {
  atualizar: '<svg viewBox="0 0 24 24"><path d="M17.65 6.35A7.96 7.96 0 0012 4a8 8 0 108 8h-2a6 6 0 11-1.76-4.24L13 11h7V4l-2.35 2.35z"/></svg>',
  local: '<svg viewBox="0 0 24 24"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5a2.5 2.5 0 010-5 2.5 2.5 0 010 5z"/></svg>',
  ligar: '<svg viewBox="0 0 24 24"><path d="M6.62 10.79a15.05 15.05 0 006.59 6.59l2.2-2.2a1 1 0 011.01-.24c1.12.37 2.33.57 3.58.57a1 1 0 011 1V20a1 1 0 01-1 1A17 17 0 013 4a1 1 0 011-1h3.5a1 1 0 011 1c0 1.25.2 2.46.57 3.58a1 1 0 01-.25 1.01l-2.2 2.2z"/></svg>',
};

// ---------------------------------------------------------------- estado

const estado = {
  aba: "triagem",
  // Primeira tela: identificação pelo Cartão Cidadão ("cartao") e depois o formulário ("form").
  etapa: "cartao",
  cartaoDigitado: "",
  consultandoCartao: false,
  erroCartao: null,
  cidadao: null, // resposta de /api/cidadao/{cartao}: cidadão + ambiente do bairro + alertas
  residente: true, // false = visitante de outra cidade, sem Cartão Cidadão
  exemplos: [],
  config: null,
  erroConexao: null,
  localizacao: null,
  resultado: null,
  triando: false,
  erroTriagem: null,
  unidades: null,
  filtroTipos: new Set(),
  carregandoUnidades: false,
  previsoes: null,
  carregandoPrevisoes: false,
  erroPrevisoes: null,
  dadosUteis: null,
  form: {
    idade: "", gestante: false, relato: "", sintomas: [], comorbidades: [],
    dias: "1", dor: 0, temperatura: "", saturacao: "", consentimento: false,
    necessidades: [], ambulancia: false,
  },
};

// ---------------------------------------------------------------- utilitários

const $ = (sel) => document.querySelector(sel);

function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

const fmt = (n, casas = 0) => Number(n).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
const ouTraco = (v) => (v ?? "–");
const dataCurta = (iso) => { const p = String(iso).split("-"); return p.length === 3 ? `${p[2]}/${p[1]}` : iso; };
const soDigitos = (s) => String(s).replace(/\D/g, "");

/** Cores da classificação de risco (Protocolo de Manchester). */
function corPrioridade(p) {
  return { vermelho: "#D32F2F", laranja: "#F57C00", amarelo: "#FBC02D", verde: "#388E3C" }[p] || "#1976D2";
}
function corNivel(n) {
  return { epidemia: "#D32F2F", alerta: "#F57C00", esperado: "#FBC02D" }[n] || "#388E3C";
}
function corLotacao(l) {
  return { alta: "#D32F2F", moderada: "#F57C00", baixa: "#388E3C" }[l] || "gray";
}
function textoSobre(hex) {
  const n = parseInt(hex.slice(1), 16);
  const lum = (((n >> 16) & 255) * 0.299 + ((n >> 8) & 255) * 0.587 + (n & 255) * 0.114) / 255;
  return lum > 0.6 ? "#000" : "#fff";
}

async function api(caminho, opcoes = {}) {
  // Versão estática (GitHub Pages / APK): o backend roda no próprio navegador (web/offline.js).
  if (window.backendLocal) {
    const { status, texto } = await window.backendLocal(opcoes.method || "GET", caminho, opcoes.body);
    if (status < 200 || status >= 300) throw new Error(`Erro ${status} do servidor: ${texto.slice(0, 200)}`);
    return JSON.parse(texto);
  }
  const ctrl = new AbortController();
  // A primeira chamada de previsões treina os modelos e pode levar alguns segundos.
  const tempo = setTimeout(() => ctrl.abort(), 60_000);
  try {
    const r = await fetch(caminho, {
      ...opcoes,
      signal: ctrl.signal,
      headers: { Accept: "application/json", ...(opcoes.body ? { "Content-Type": "application/json; charset=utf-8" } : {}) },
    });
    const texto = await r.text();
    if (!r.ok) throw new Error(`Erro ${r.status} do servidor: ${texto.slice(0, 200)}`);
    return JSON.parse(texto);
  } catch (e) {
    throw e.name === "AbortError" ? new Error("tempo esgotado") : e;
  } finally {
    clearTimeout(tempo);
  }
}

/** Localização do aparelho; sem ela, o endereço do Cartão Cidadão; senão, o centro do município. */
const pontoAtual = () => estado.localizacao || estado.cidadao?.cidadao.endereco || estado.config?.centro_mapa || null;

function corNivelRisco(n) {
  return { alto: "#D32F2F", moderado: "#F57C00" }[n] || "#388E3C";
}

// ---------------------------------------------------------------- ações

async function carregarTudo() {
  try {
    estado.config = await api("/api/config");
    estado.erroConexao = null;
  } catch (e) {
    estado.erroConexao = window.backendLocal
      ? `Não foi possível carregar o app (${e.message}). Verifique a conexão com a internet.`
      : `Não foi possível conectar ao servidor (${e.message}). Verifique se o backend está rodando.`;
  }
  renderAvisoConexao();
  api("/api/cidadao/exemplos").then((d) => { estado.exemplos = d.cartoes; renderTriagem(); }).catch(() => {});
  renderTriagem();
  atualizarUnidades();
  api("/api/dados-uteis").then((d) => { estado.dadosUteis = d; renderInfo(); }).catch(() => {});
  carregarPrevisoes();
}

async function atualizarUnidades(silencioso = false) {
  if (!silencioso) { estado.carregandoUnidades = true; renderUnidades(); }
  try {
    const p = pontoAtual();
    const qs = new URLSearchParams();
    if (p) { qs.set("lat", p.lat); qs.set("lon", p.lon); }
    estado.filtroTipos.forEach((t) => qs.append("tipo", t));
    estado.unidades = await api("/api/unidades" + (qs.toString() ? "?" + qs : ""));
  } catch {
    // mantém a última leitura; o aviso de conexão já aparece no topo
  } finally {
    estado.carregandoUnidades = false;
    renderUnidades();
  }
}

async function carregarPrevisoes() {
  estado.carregandoPrevisoes = true;
  estado.erroPrevisoes = null;
  renderPrevisoes();
  try {
    estado.previsoes = await api("/api/previsoes?semanas=8");
  } catch (e) {
    estado.erroPrevisoes = `Falha ao carregar previsões: ${e.message}`;
  } finally {
    estado.carregandoPrevisoes = false;
    renderPrevisoes();
  }
}

async function consultarCartao(cartao) {
  const numero = soDigitos(cartao);
  if (!numero) return;
  estado.cartaoDigitado = numero;
  estado.consultandoCartao = true;
  estado.erroCartao = null;
  renderTriagem();
  try {
    estado.cidadao = await api("/api/cidadao/" + numero);
    if (mapa && !estado.localizacao) {
      const e = estado.cidadao.cidadao.endereco;
      mapa.setView([e.lat, e.lon]);
    }
    atualizarUnidades(true);
    renderInfo();
  } catch (e) {
    estado.cidadao = null;
    estado.erroCartao = e.message.includes("404") ? "Cartão Cidadão não encontrado. Confira o número." : `Falha na consulta: ${e.message}`;
  } finally {
    estado.consultandoCartao = false;
    renderTriagem();
  }
}

/** Preenche o formulário com o cadastro e vai para a triagem. */
function iniciarTriagem(residente = true) {
  const c = estado.cidadao?.cidadao;
  estado.residente = c ? true : residente;
  if (c) {
    Object.assign(estado.form, {
      idade: String(c.idade), gestante: c.gestante, comorbidades: [...c.comorbidades],
      necessidades: [...c.necessidades], ambulancia: c.necessita_ambulancia,
    });
  }
  estado.etapa = "form";
  renderTriagem();
  $(".conteudo").scrollTop = 0;
}

function trocarCartao() {
  estado.cidadao = null;
  estado.cartaoDigitado = "";
  estado.erroCartao = null;
  estado.etapa = "cartao";
  estado.residente = true;
  estado.form = { ...estado.form, idade: "", gestante: false, comorbidades: [], necessidades: [], ambulancia: false };
  atualizarUnidades(true);
  renderTriagem();
  renderInfo();
}

function entradaDoFormulario() {
  const f = estado.form;
  const temp = parseFloat(f.temperatura);
  const sat = parseInt(f.saturacao, 10);
  const p = pontoAtual();
  return {
    idade: parseInt(f.idade, 10) || 0,
    gestante: f.gestante,
    relato: f.relato,
    sintomas: f.sintomas,
    dias_sintomas: parseInt(f.dias, 10) || 1,
    intensidade_dor: f.dor,
    comorbidades: f.comorbidades,
    sinais_vitais: {
      temperatura: temp >= 30 && temp <= 45 ? temp : null,
      saturacao: sat >= 50 && sat <= 100 ? sat : null,
    },
    lat: p?.lat ?? null,
    lon: p?.lon ?? null,
    consentimento_lgpd: f.consentimento,
    cartao_cidadao: estado.cidadao?.cidadao.cartao ?? null,
    residente: estado.residente,
    necessidades: f.necessidades,
    necessita_ambulancia: f.ambulancia,
  };
}

async function triar() {
  const entrada = entradaDoFormulario();
  estado.triando = true;
  estado.erroTriagem = null;
  renderTriagem();
  try {
    estado.resultado = await api("/api/triagem", { method: "POST", body: JSON.stringify(entrada) });
  } catch (e) {
    estado.resultado = null;
    estado.erroTriagem = entrada.sintomas.some((s) => SINTOMAS_ALARME_OFFLINE.has(s))
      ? "Sem conexão com o servidor. Você marcou um sinal de alarme: LIGUE 192 (SAMU) ou procure o pronto-socorro imediatamente."
      : `Sem conexão com o servidor (${e.message}). Se os sintomas forem graves, ligue 192.`;
  } finally {
    estado.triando = false;
    renderTriagem();
    $(".conteudo").scrollTop = 0;
  }
}

function definirLocalizacao(lat, lon) {
  estado.localizacao = { lat, lon };
  if (mapa) mapa.setView([lat, lon]);
  atualizarUnidades(true);
  renderInfo();
}

function obterLocalizacao() {
  if (!navigator.geolocation) return;
  navigator.geolocation.getCurrentPosition(
    (pos) => definirLocalizacao(pos.coords.latitude, pos.coords.longitude),
    () => {}, // sem permissão: usa o centro do município
    { enableHighAccuracy: true, timeout: 10_000, maximumAge: 60_000 },
  );
}

function irPara(aba) {
  estado.aba = aba;
  document.querySelectorAll(".navegacao button").forEach((b) => b.classList.toggle("ativo", b.dataset.aba === aba));
  document.querySelectorAll(".aba").forEach((s) => { s.hidden = s.id !== "aba-" + aba; });
  $(".conteudo").scrollTop = 0;
  // O Leaflet precisa recalcular o tamanho quando o mapa volta a ficar visível.
  if (aba === "unidades" && mapa) setTimeout(() => mapa.invalidateSize(), 0);
}

// ---------------------------------------------------------------- componentes

const telLink = (numero) => "tel:" + soDigitos(numero);
const rotaLink = (u) => `https://www.openstreetmap.org/?mlat=${u.lat}&mlon=${u.lon}#map=17/${u.lat}/${u.lon}`;

function cartaoUnidade(u) {
  const fechada = u.funcionando === false;
  const local = [
    u.distancia_km != null ? `${fmt(u.distancia_km, 1)} km` : null,
    u.deslocamento_min != null ? `~${u.deslocamento_min} min de carro` : null,
    u.bairro || null,
  ].filter(Boolean);
  return `
    <div class="cartao ${fechada ? "fechada" : ""}">
      <div><span class="tipo-unidade">${esc(u.tipo)}</span><span class="negrito">${esc(u.nome)}</span></div>
      ${fechada
        ? `<div class="erro-texto">Fechada agora • ${esc(u.horario)}</div>`
        : `<div style="font-size:16px">${ouTraco(u.em_atendimento)} em atendimento • ${ouTraco(u.aguardando)} aguardando</div>
           <div class="linha" style="flex:none;gap:12px">
             ${u.espera_estimada_min != null ? `<span style="flex:none">Espera ~${u.espera_estimada_min} min</span>` : ""}
             <span class="negrito" style="flex:none;color:${corLotacao(u.lotacao)}">Lotação ${esc(u.lotacao)}</span>
           </div>`}
      ${local.length ? `<div class="pequeno">${esc(local.join(" • "))}</div>` : ""}
      <div class="pequeno suave">${esc(u.endereco)}${u.dados_confirmados ? "" : " (dados de demonstração)"}</div>
      <div class="acoes">
        <a class="acao" href="${rotaLink(u)}" target="_blank" rel="noopener">${ICONE.local} Como chegar</a>
        ${u.telefone ? `<a class="acao" href="${telLink(u.telefone)}">${ICONE.ligar} ${esc(u.telefone)}</a>` : ""}
      </div>
    </div>`;
}

function renderAvisoConexao() {
  const el = $("#aviso-conexao");
  el.hidden = !estado.erroConexao;
  if (estado.erroConexao) {
    el.innerHTML = `${esc(estado.erroConexao)}<br><button class="botao contorno" style="min-height:36px;margin-top:8px" id="tentar-novamente">Tentar novamente</button>`;
    $("#tentar-novamente").onclick = carregarTudo;
  }
}

// ---------------------------------------------------------------- Triagem

function formularioValido() {
  const f = estado.form;
  const idade = parseInt(f.idade, 10);
  return !estado.triando && f.idade !== "" && idade <= 120 && (f.relato.trim() !== "" || f.sintomas.length > 0);
}

function chips(itens, selecionados, grupo) {
  return (itens || []).map((i) =>
    `<button type="button" class="chip ${selecionados.includes(i.codigo) ? "ativo" : ""}" data-grupo="${grupo}" data-codigo="${esc(i.codigo)}">${esc(i.rotulo)}</button>`
  ).join("");
}

function renderTriagem() {
  const el = $("#aba-triagem");
  if (estado.resultado) { renderResultado(el, estado.resultado); return; }
  if (estado.etapa === "cartao") { renderCartao(el); return; }
  const f = estado.form;
  const c = estado.config;
  const cid = estado.cidadao?.cidadao;
  el.innerHTML = `
    <h2>Triagem inteligente</h2>
    ${cid ? `
      <div class="cartao identificado">
        <div class="cabecalho" style="align-items:center">
          <div><div class="negrito">${esc(cid.nome)}</div>
            <div class="pequeno suave">Cartão ${esc(cid.cartao)} • ${esc(cid.endereco.bairro)} • dados do prontuário já preenchidos</div></div>
          <button class="chip" id="f-trocar">Trocar</button>
        </div>
      </div>` : `
      <div class="cartao identificado">
        <div class="cabecalho" style="align-items:center">
          <div><div class="negrito">${estado.residente ? "Sem Cartão Cidadão" : "Visitante (não mora em Lençóis Paulista)"}</div>
            <div class="pequeno suave">${estado.residente ? "Preencha seus dados abaixo." : "O SUS atende todos: leve documento com foto e CNS ou CPF."}</div></div>
          <button class="chip" id="f-trocar">Usar cartão</button>
        </div>
      </div>`}
    <div>Responda para saber se você deve ir à UPA, à UBS (posto) ou se pode se cuidar em casa.${c?.municipio ? " — " + esc(c.municipio) : ""}</div>

    <div class="campo"><label for="f-idade">Idade (anos)</label>
      <input id="f-idade" inputmode="numeric" maxlength="3" value="${esc(f.idade)}"></div>
    <label class="interruptor"><input type="checkbox" role="switch" id="f-gestante" ${f.gestante ? "checked" : ""}> Gestante</label>

    <div class="campo"><label for="f-relato">Descreva o que está sentindo</label>
      <textarea id="f-relato" rows="3" maxlength="2000" placeholder="Ex.: febre desde ontem, dor no corpo e atrás dos olhos">${esc(f.relato)}</textarea></div>

    <div class="negrito">Ou marque os sintomas:</div>
    <div class="chips">${chips(c?.sintomas, f.sintomas, "sintomas")}</div>

    <div class="campo"><label for="f-dias">Há quantos dias?</label>
      <input id="f-dias" inputmode="numeric" maxlength="3" value="${esc(f.dias)}"></div>

    <div class="negrito" id="rotulo-dor">Intensidade da dor: ${f.dor}/10</div>
    <input type="range" id="f-dor" min="0" max="10" step="1" value="${f.dor}" aria-labelledby="rotulo-dor">

    <div class="negrito">Doenças pré-existentes:</div>
    <div class="chips">${chips(c?.comorbidades, f.comorbidades, "comorbidades")}</div>

    <div class="negrito">Acessibilidade e cuidados:</div>
    <div class="chips">${chips(c?.necessidades, f.necessidades, "necessidades")}</div>
    <label class="caixa"><input type="checkbox" id="f-ambulancia" ${f.ambulancia ? "checked" : ""}> Precisa de ambulância para se deslocar (acamado ou sem condições de ir de carro).</label>

    <div class="negrito">Se tiver termômetro ou oxímetro (opcional):</div>
    <div class="linha">
      <div class="campo"><label for="f-temp">Temperatura °C</label><input id="f-temp" inputmode="decimal" maxlength="4" value="${esc(f.temperatura)}"></div>
      <div class="campo"><label for="f-sat">Saturação %</label><input id="f-sat" inputmode="numeric" maxlength="3" value="${esc(f.saturacao)}"></div>
    </div>

    <label class="caixa"><input type="checkbox" id="f-consent" ${f.consentimento ? "checked" : ""}> Autorizo o envio desta triagem ao prontuário da unidade (LGPD).</label>

    ${estado.erroTriagem ? `<div class="cartao erro">${esc(estado.erroTriagem)}</div>` : ""}

    <button class="botao" id="f-avaliar" style="min-height:52px" ${formularioValido() ? "" : "disabled"}>
      ${estado.triando ? '<span class="giro"></span>' : "Avaliar"}</button>
    <div class="pequeno erro-texto">Em caso de emergência, não espere: ligue 192 (SAMU).</div>`;

  const atualizarBotao = () => { $("#f-avaliar").disabled = !formularioValido(); };
  const campoTexto = (id, chave, filtro) => {
    const inp = $(id);
    inp.oninput = () => {
      const v = filtro ? filtro(inp.value) : inp.value;
      if (v !== inp.value) inp.value = v;
      f[chave] = v;
      atualizarBotao();
    };
  };
  campoTexto("#f-idade", "idade", (v) => soDigitos(v).slice(0, 3));
  campoTexto("#f-relato", "relato");
  campoTexto("#f-dias", "dias", (v) => soDigitos(v).slice(0, 3));
  campoTexto("#f-temp", "temperatura", (v) => v.replace(",", ".").replace(/[^\d.]/g, "").slice(0, 4));
  campoTexto("#f-sat", "saturacao", (v) => soDigitos(v).slice(0, 3));
  $("#f-gestante").onchange = (e) => { f.gestante = e.target.checked; };
  $("#f-consent").onchange = (e) => { f.consentimento = e.target.checked; };
  $("#f-ambulancia").onchange = (e) => { f.ambulancia = e.target.checked; };
  $("#f-dor").oninput = (e) => { f.dor = Number(e.target.value); $("#rotulo-dor").textContent = `Intensidade da dor: ${f.dor}/10`; };
  el.querySelectorAll(".chip").forEach((b) => {
    b.onclick = () => {
      const lista = f[b.dataset.grupo];
      const i = lista.indexOf(b.dataset.codigo);
      if (i >= 0) lista.splice(i, 1); else lista.push(b.dataset.codigo);
      b.classList.toggle("ativo", i < 0);
      atualizarBotao();
    };
  });
  $("#f-avaliar").onclick = triar;
  $("#f-trocar").onclick = trocarCartao;
}

function renderCartao(el) {
  const r = estado.cidadao;
  if (r) { renderCidadao(el, r); return; }
  el.innerHTML = `
    <h2>Cartão Cidadão</h2>
    <div>Informe o número do seu Cartão Cidadão de ${esc(estado.config?.municipio || "Lençóis Paulista")}.
      Seus dados do prontuário e as condições do seu bairro serão usados na triagem.</div>
    <form id="form-cartao" style="display:flex;flex-direction:column;gap:12px">
      <div class="campo"><label for="c-numero">Número do Cartão Cidadão</label>
        <input id="c-numero" inputmode="numeric" autocomplete="off" maxlength="20" value="${esc(estado.cartaoDigitado)}" placeholder="Ex.: 10000001"></div>
      ${estado.erroCartao ? `<div class="cartao erro">${esc(estado.erroCartao)}</div>` : ""}
      <button class="botao" type="submit" ${estado.consultandoCartao ? "disabled" : ""}>
        ${estado.consultandoCartao ? '<span class="giro"></span>' : "Consultar"}</button>
    </form>
    <button class="botao contorno" id="c-sem-cartao">Moro aqui, mas estou sem o cartão</button>
    <button class="botao contorno" id="c-visitante">Não moro em Lençóis Paulista</button>
    ${estado.exemplos.length ? `
      <hr>
      <div class="negrito">Cartões fictícios para teste</div>
      <div class="pequeno suave">Base de demonstração com moradores fictícios de bairros de Lençóis Paulista.</div>
      ${estado.exemplos.map((e) => `
        <button class="cartao exemplo" data-cartao="${esc(e.cartao)}">
          <span><b>${esc(e.cartao)}</b> — ${esc(e.nome)}, ${e.idade} ${e.idade === 1 ? "ano" : "anos"}</span>
          <span class="pequeno suave">${esc(e.bairro)} • ${esc(e.perfil)}</span>
        </button>`).join("")}` : ""}
    <div class="pequeno erro-texto">Em caso de emergência, não espere: ligue 192 (SAMU).</div>`;
  const inp = $("#c-numero");
  inp.oninput = () => { inp.value = soDigitos(inp.value); estado.cartaoDigitado = inp.value; };
  $("#form-cartao").onsubmit = (e) => { e.preventDefault(); consultarCartao(inp.value); };
  $("#c-sem-cartao").onclick = () => iniciarTriagem(true);
  $("#c-visitante").onclick = () => iniciarTriagem(false);
  el.querySelectorAll(".exemplo").forEach((b) => { b.onclick = () => consultarCartao(b.dataset.cartao); });
}

function blocoAcompanhante(ac, prioridades) {
  if (!ac && !prioridades?.length) return "";
  const cor = ac?.nivel === "obrigatorio" ? "#D32F2F" : ac?.nivel === "recomendado" ? "#F57C00" : "#388E3C";
  return `
    <div class="cartao" style="border-left:4px solid ${cor}">
      ${ac ? `<div class="negrito">${esc(ac.titulo)}</div><div class="pequeno">${esc(ac.texto)}</div>` : ""}
      ${(prioridades || []).map((p) => `<div class="pequeno">• ${esc(p)}</div>`).join("")}
    </div>`;
}

function renderCidadao(el, r) {
  const c = r.cidadao;
  const a = r.ambiente;
  const lista = (itens) => (itens.length ? esc(itens.join(", ")) : "nenhum registro");
  const formatarData = (iso) => iso.split("-").reverse().join("/");
  el.innerHTML = `
    <h2>Olá, ${esc(c.nome.split(" ")[0])}</h2>
    <div class="cartao" style="gap:6px">
      <div class="negrito" style="font-size:17px">${esc(c.nome)}</div>
      <div class="pequeno suave">Cartão Cidadão ${esc(c.cartao)} • CNS ${esc(c.cns)}</div>
      <div>${c.idade} ${c.idade === 1 ? "ano" : "anos"} • ${c.sexo === "F" ? "feminino" : "masculino"} • nasc. ${formatarData(c.nascimento)}</div>
      <div>${esc(c.endereco.logradouro)} — ${esc(c.endereco.bairro)}</div>
      <div class="pequeno">Unidade de referência: <b>${esc(c.ubs_referencia.nome)}</b></div>
      ${c.gestante ? `<div class="negrito">Gestante${c.semanas_gestacao ? ` • ${c.semanas_gestacao} semanas` : ""}</div>` : ""}
      <hr>
      ${c.necessidades.length || c.necessita_ambulancia ? `
        <div class="pequeno"><b>Acessibilidade:</b> ${esc([...c.necessidades_rotulos, ...(c.necessita_ambulancia ? ["precisa de ambulância"] : [])].join(", "))}</div>` : ""}
      <div class="pequeno"><b>Doenças:</b> ${lista(c.comorbidades_rotulos)}</div>
      <div class="pequeno"><b>Medicamentos:</b> ${lista(c.medicamentos)}</div>
      <div class="pequeno"><b>Alergias:</b> ${lista(c.alergias)}</div>
      <div class="pequeno"><b>Vacinas:</b> ${lista(c.vacinas.map((v) => `${v.vacina} (${formatarData(v.data)})`))}</div>
      <div class="pequeno"><b>Última consulta:</b> ${c.ultimas_consultas[0]
        ? `${formatarData(c.ultimas_consultas[0].data)} — ${esc(c.ultimas_consultas[0].motivo)}` : "nenhuma"}</div>
      ${c.ficticio ? `<div class="mini suave">Dados fictícios para teste.</div>` : ""}
    </div>

    ${blocoAcompanhante(r.acompanhante, r.prioridade_legal)}

    ${r.alertas.length ? `
      <h3>Alertas para você</h3>
      ${r.alertas.map((x) => `
        <div class="cartao alerta-pessoal" style="border-left:4px solid ${corNivelRisco(x.nivel)}">${esc(x.texto)}</div>`).join("")}` : ""}

    ${a ? `
      <h3>Seu bairro: ${esc(a.bairro)}</h3>
      <div class="pequeno suave">Agora: ${fmt(a.clima.temperatura, 1)} °C • umidade ${fmt(a.clima.umidade)}% • ${fmt(a.clima.chuva_4sem_mm)} mm de chuva em 4 semanas</div>
      ${a.indicadores.map((i) => `
        <div class="indicador">
          <i style="background:${corNivelRisco(i.nivel)}" title="${esc(i.nivel)}"></i>
          <div><div class="negrito">${esc(i.titulo)} <span class="selo" style="background:${corNivelRisco(i.nivel)};color:${textoSobre(corNivelRisco(i.nivel))}">${esc(i.nivel)}</span></div>
            <div class="pequeno">${esc(i.valor)}</div>
            ${i.nivel !== "baixo" ? `<div class="pequeno suave">${esc(i.recomendacao)}</div>` : ""}</div>
        </div>`).join("")}` : ""}

    <button class="botao" id="c-iniciar" style="min-height:52px">Iniciar triagem</button>
    <button class="botao contorno" id="c-trocar">Não sou eu / trocar cartão</button>`;
  $("#c-iniciar").onclick = iniciarTriagem;
  $("#c-trocar").onclick = trocarCartao;
}

function renderResultado(el, r) {
  const cor = corPrioridade(r.prioridade);
  const tx = textoSobre(cor);
  el.innerHTML = `
    <div class="faixa-prioridade" style="background:${cor};color:${tx}">
      <div class="rotulo">${esc(r.prioridade.toUpperCase())}</div>
      <div class="titulo">${esc(r.titulo)}</div>
      ${r.tempo_alvo_min > 0 ? `<div>Procure atendimento em até ${r.tempo_alvo_min} min</div>` : ""}
    </div>
    <div style="font-size:17px">${esc(r.orientacao)}</div>
    ${r.destino === "SAMU" || r.transporte?.tipo === "samu" ? `<a class="botao samu" href="tel:192">LIGAR 192 — SAMU</a>` : ""}
    ${r.transporte ? `
      <div class="cartao" style="border-left:4px solid ${r.transporte.tipo === "samu" ? "#D32F2F" : "#1976D2"}">
        <div class="negrito">Como ir</div><div class="pequeno">${esc(r.transporte.texto)}</div>
      </div>` : ""}
    ${blocoAcompanhante(r.acompanhante, r.prioridade_legal)}
    ${r.sintomas_identificados?.length ? `<div>Sintomas considerados: ${esc(r.sintomas_identificados.join(", "))}</div>` : ""}
    ${r.agravo_provavel ? `<div class="negrito">Possível quadro: ${esc(r.agravo_provavel)}</div>` : ""}
    <div class="negrito">Por quê:</div>
    <ul>${(r.motivos || []).map((m) => `<li>${esc(m)}</li>`).join("")}</ul>
    ${r.contexto_ambiental?.length ? `
      <div class="cartao alerta">
        <div class="negrito">Condições do seu bairro</div>
        ${r.contexto_ambiental.map((m) => `<div>• ${esc(m)}</div>`).join("")}
      </div>` : ""}
    ${r.unidades_sugeridas?.length ? `
      <hr>
      <h3>${r.destino === "UBS" || r.destino === "AUTOCUIDADO" ? "Onde ir: posto de saúde (UBS)" : "Onde ir: UPA"}</h3>
      ${r.unidades_sugeridas.map(cartaoUnidade).join("")}
      <button class="botao contorno" id="ver-mapa">Ver todas no mapa</button>` : ""}
    <div class="pequeno suave">Análise: regras clínicas + IA (${esc(r.fonte_extracao)})${r.registrado_prontuario ? " • enviada ao prontuário" : ""}</div>
    <div class="pequeno suave">${esc(r.aviso)}</div>
    <button class="botao" id="nova-triagem">Nova triagem</button>`;
  $("#nova-triagem").onclick = () => {
    estado.resultado = null;
    estado.erroTriagem = null;
    // Mantém o cidadão identificado; sem cartão, volta à tela inicial.
    estado.etapa = estado.cidadao ? "form" : "cartao";
    renderTriagem();
    $(".conteudo").scrollTop = 0;
  };
  const verMapa = $("#ver-mapa");
  if (verMapa) verMapa.onclick = () => irPara("unidades");
}

// ---------------------------------------------------------------- Unidades

let mapa = null;
let camadaMarcadores = null;

function montarUnidades(el) {
  el.innerHTML = `
    <div class="cabecalho">
      <div><h2>Atendimentos agora</h2><div class="pequeno suave" id="u-municipio"></div></div>
      <button class="icone-botao" id="u-atualizar" title="Atualizar" aria-label="Atualizar">${ICONE.atualizar}</button>
    </div>
    <div class="progresso" id="u-progresso" hidden></div>
    <div class="resumo-tipos" id="u-resumo"></div>
    <div class="chips" id="u-filtros">${TIPOS.map((t) => `<button type="button" class="chip" data-tipo="${t}">${t}</button>`).join("")}</div>
    <div class="mapa" id="u-mapa"></div>
    <div class="pequeno suave">Ordenadas pelo menor tempo total (deslocamento + espera). Atualiza a cada 30 s.</div>
    <div id="u-lista" style="display:flex;flex-direction:column;gap:8px"></div>`;
  $("#u-atualizar").onclick = () => atualizarUnidades();
  el.querySelectorAll("#u-filtros .chip").forEach((b) => {
    b.onclick = () => {
      const t = b.dataset.tipo;
      if (estado.filtroTipos.has(t)) estado.filtroTipos.delete(t); else estado.filtroTipos.add(t);
      atualizarUnidades();
    };
  });
}

function renderUnidades() {
  const el = $("#aba-unidades");
  if (!el.firstChild) montarUnidades(el);
  const resp = estado.unidades;
  $("#u-municipio").textContent = estado.config?.municipio || "";
  $("#u-progresso").hidden = !estado.carregandoUnidades;
  $("#u-resumo").innerHTML = TIPOS.map((t) => `
    <div class="cartao"><span class="negrito">${t}</span>
      <span class="numero">${ouTraco(resp?.em_atendimento_por_tipo?.[t])}</span>
      <span class="mini">em atendimento</span></div>`).join("");
  el.querySelectorAll("#u-filtros .chip").forEach((b) => b.classList.toggle("ativo", estado.filtroTipos.has(b.dataset.tipo)));
  $("#u-lista").innerHTML = (resp?.unidades || []).map(cartaoUnidade).join("");
  renderMapa(resp?.unidades || []);
}

function renderMapa(unidades) {
  const centro = pontoAtual();
  if (!centro || typeof L === "undefined") return;
  if (!mapa) {
    mapa = L.map("u-mapa").setView([centro.lat, centro.lon], 13.5);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(mapa);
    camadaMarcadores = L.layerGroup().addTo(mapa);
  }
  camadaMarcadores.clearLayers();
  unidades.forEach((u) => {
    const espera = u.espera_estimada_min != null ? ` • espera ~${u.espera_estimada_min} min` : "";
    L.marker([u.lat, u.lon]).addTo(camadaMarcadores)
      .bindPopup(`<b>${esc(u.nome)}</b><br>${ouTraco(u.em_atendimento)} em atendimento • ${ouTraco(u.aguardando)} aguardando${espera}`);
  });
  if (estado.localizacao) {
    L.circleMarker([estado.localizacao.lat, estado.localizacao.lon], { radius: 8, color: "#fff", weight: 3, fillColor: "#1976D2", fillOpacity: 1 })
      .addTo(camadaMarcadores).bindPopup("Você está aqui");
  }
}

// ---------------------------------------------------------------- Previsões

function grafico(a) {
  const obs = a.observado.slice(-SEMANAS_HISTORICO);
  const prev = a.previsao;
  const n = obs.length + prev.length;
  if (!obs.length || n < 2) return "";
  const L_ = 300, A = 140;
  const maximo = Math.max(1, ...obs.map((o) => Math.max(o.casos, o.canal.limite_superior)),
    ...prev.map((p) => Math.max(p.maximo, p.canal.limite_superior)));
  const x = (i) => (i * L_ / (n - 1)).toFixed(1);
  const y = (v) => (A - v / maximo * A * 0.95).toFixed(1);
  const canais = [...obs.map((o) => o.canal), ...prev.map((p) => p.canal)];
  const faixa = canais.map((c, i) => `${i ? "L" : "M"}${x(i)},${y(c.limite_superior)}`).join("") +
    canais.map((c, i) => [i, c]).reverse().map(([i, c]) => `L${x(i)},${y(c.mediana)}`).join("") + "Z";
  const base = obs.length - 1;
  const ultimo = obs[base].casos;
  const intervalo = `M${x(base)},${y(ultimo)}` + prev.map((p, i) => `L${x(base + i + 1)},${y(p.maximo)}`).join("") +
    prev.map((p, i) => [i, p]).reverse().map(([i, p]) => `L${x(base + i + 1)},${y(p.minimo)}`).join("") + "Z";
  const linhaObs = obs.map((o, i) => `${i ? "L" : "M"}${x(i)},${y(o.casos)}`).join("");
  const linhaPrev = `M${x(base)},${y(ultimo)}` + prev.map((p, i) => `L${x(base + i + 1)},${y(p.previsto)}`).join("");
  return `
    <svg class="grafico" viewBox="0 0 ${L_} ${A}" preserveAspectRatio="none" role="img" aria-label="Casos observados e previstos de ${esc(a.nome)}">
      <path d="${faixa}" fill="#9E9E9E" fill-opacity=".25"/>
      <path d="${intervalo}" fill="var(--secundaria)" fill-opacity=".2"/>
      <path d="${linhaObs}" fill="none" stroke="var(--primaria)" stroke-width="2" vector-effect="non-scaling-stroke"/>
      <path d="${linhaPrev}" fill="none" stroke="var(--secundaria)" stroke-width="2" stroke-dasharray="6 4" vector-effect="non-scaling-stroke"/>
      <line x1="${x(base)}" y1="0" x2="${x(base)}" y2="${A}" stroke="gray" stroke-width="1" vector-effect="non-scaling-stroke"/>
    </svg>`;
}

function cartaoAgravo(a) {
  const cor = corNivel(a.nivel_atual);
  const atual = a.observado.at(-1)?.casos ?? 0;
  const sinal = a.tendencia_pct >= 0 ? "+" : "";
  return `
    <div class="cartao" style="gap:6px">
      <div class="cabecalho" style="align-items:center">
        <div class="negrito">${esc(a.nome)}</div>
        <span class="selo" style="background:${cor};color:${textoSobre(cor)}">${esc(a.nivel_atual.toUpperCase())}</span>
      </div>
      <div>${atual} casos na última semana • tendência ${sinal}${fmt(a.tendencia_pct)}% em 4 semanas</div>
      ${grafico(a)}
      <div class="semanas">${a.previsao.slice(0, 4).map((p) => `
        <div style="background:${corNivel(p.nivel)}2e">
          <div class="mini">${dataCurta(p.semana)}</div>
          <div class="negrito">${p.previsto}</div>
          <div class="mini">${p.minimo}–${p.maximo}</div>
        </div>`).join("")}</div>
      ${a.erro_backtest_pct != null ? `<div class="mini">Erro médio do modelo nas últimas 26 semanas: ${fmt(a.erro_backtest_pct)}%</div>` : ""}
    </div>`;
}

function renderPrevisoes() {
  const el = $("#aba-previsoes");
  const r = estado.previsoes;
  const legenda = (cor, texto) => `<div class="legenda"><i style="background:${cor}"></i>${texto}</div>`;
  el.innerHTML = `
    <div class="cabecalho">
      <div><h2>Previsão de doenças</h2>
        <div class="pequeno suave">Modelo de ML (gradient boosting) com sazonalidade, clima e histórico de casos.</div></div>
      <button class="icone-botao" id="p-atualizar" title="Atualizar" aria-label="Atualizar">${ICONE.atualizar}</button>
    </div>
    ${estado.carregandoPrevisoes ? `<div class="progresso"></div><div class="pequeno suave">Treinando modelos…</div>` : ""}
    ${estado.erroPrevisoes ? `<div class="erro-texto">${esc(estado.erroPrevisoes)}</div>` : ""}
    ${r?.alertas?.length ? `
      <div class="cartao alerta">
        <div class="negrito">Alertas para as próximas ${r.horizonte_semanas} semanas</div>
        ${r.alertas.map((a) => `<div>• ${esc(a.nome)}: nível ${esc(a.nivel)} — pico previsto de ${a.pico_previsto.casos} casos/semana em ${dataCurta(a.pico_previsto.semana)}</div>`).join("")}
      </div>` : ""}
    ${(r?.agravos || []).map(cartaoAgravo).join("")}
    <div>
      <div class="negrito">Como ler</div>
      ${legenda("#388E3C", "Abaixo da mediana histórica")}
      ${legenda("#FBC02D", "Esperado (até o 3º quartil)")}
      ${legenda("#F57C00", "Alerta (acima do esperado)")}
      ${legenda("#D32F2F", "Epidemia (acima do limite superior)")}
      <div class="pequeno suave" style="margin-top:4px">Faixa sombreada: canal endêmico (anos anteriores). Linha tracejada: previsão; área clara: intervalo de 80%.</div>
    </div>`;
  $("#p-atualizar").onclick = carregarPrevisoes;
}

// ---------------------------------------------------------------- Info

function renderInfo() {
  const el = $("#aba-info");
  const d = estado.dadosUteis;
  const loc = estado.localizacao;
  el.innerHTML = `
    <h2>Dados úteis</h2>
    ${(d?.telefones || []).map((t) => `
      <div class="cartao telefone">
        <div><div class="negrito">${esc(t.nome)} — ${esc(t.numero)}</div><div class="pequeno suave">${esc(t.descricao)}</div></div>
        <a class="icone-botao" href="${telLink(t.numero)}" aria-label="Ligar ${esc(t.numero)}">${ICONE.ligar}</a>
      </div>`).join("")}
    ${d ? `
      <h3>Onde procurar atendimento</h3>
      ${Object.entries(d.quando_procurar).map(([local, quando]) => `<div><div class="negrito">${esc(local)}</div><div>${esc(quando)}</div></div>`).join("")}
      <h3>Leve com você</h3>
      <ul>${d.documentos.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
      <h3>Dicas de saúde</h3>
      <ul>${d.dicas.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
    <hr>
    <h3>Localização</h3>
    <div class="pequeno">${loc
      ? `Usando sua localização (${fmt(loc.lat, 4)}, ${fmt(loc.lon, 4)}).`
      : estado.cidadao
        ? `Sem localização do aparelho: usando o endereço do Cartão Cidadão (${esc(estado.cidadao.cidadao.endereco.bairro)}).`
        : `Sem localização: usando o centro de ${esc(estado.config?.municipio || "município")}.`}</div>
    <button class="botao contorno" id="i-localizar">Usar minha localização</button>
    ${loc ? `<button class="botao contorno" id="i-centro">Usar o centro do município</button>` : ""}
    <div class="pequeno suave">Este aplicativo orienta e não substitui a avaliação de um profissional de saúde.
      Os dados de unidades são de demonstração até a integração com o prontuário/CNES do município.</div>`;
  $("#i-localizar").onclick = obterLocalizacao;
  const centro = $("#i-centro");
  if (centro) centro.onclick = () => { estado.localizacao = null; atualizarUnidades(true); renderInfo(); };
}

// ---------------------------------------------------------------- início

function relogio() {
  $("#relogio").textContent = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

document.querySelectorAll(".navegacao button").forEach((b) => { b.onclick = () => irPara(b.dataset.aba); });
relogio();
setInterval(relogio, 15_000);
renderTriagem();
renderUnidades();
renderPrevisoes();
renderInfo();
carregarTudo();
obterLocalizacao();
// Atualiza a ocupação das unidades a cada 30 segundos.
setInterval(() => atualizarUnidades(true), 30_000);
// Versão estática: quando o Python termina de carregar, troca as respostas pré-calculadas
// pelas calculadas agora (ocupação e status das unidades dependem da hora).
window.addEventListener("healthflow:backend-pronto", async () => {
  atualizarUnidades(true);
  try {
    estado.previsoes = await api("/api/previsoes?semanas=8");
    renderPrevisoes();
  } catch {
    // mantém as previsões pré-calculadas
  }
});
