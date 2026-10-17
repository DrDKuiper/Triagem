// Versão estática (GitHub Pages e APK): em vez de chamar o servidor FastAPI, o app chama
// o mesmo backend Python rodando no navegador, via Pyodide num Web Worker
// (offline-worker.js). Este arquivo só é incluído na página pelo scripts/construir_site.py.
//
// Para abrir na hora, as respostas que só dependem dos dados fictícios vêm prontas em
// web/instantaneo.json enquanto o Python carrega em segundo plano. Quando ele fica pronto,
// o evento "healthflow:backend-pronto" avisa o app para atualizar o que muda com a hora.
"use strict";

(() => {
  // No APK o Pyodide vem embutido (data-pyodide no <html>); no GitHub Pages, do CDN.
  // A versão precisa ser a mesma de scripts/construir_site.py.
  const PYODIDE = new URL(document.documentElement.dataset.pyodide || "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/", location.href).href;

  let worker = null; // Promise<Worker>
  let falhou = false;
  let pronto = false;
  let proximoId = 1;
  const pendentes = new Map();

  const instantaneo = fetch("web/instantaneo.json").then((r) => (r.ok ? r.json() : {})).catch(() => ({}));

  // Sem as respostas prontas, a tela de carregamento cobre o app; com elas, só uma barra no topo.
  let comInstantaneo = false;
  const elemento = (id) => document.getElementById(id);
  function mostrarProgresso(texto) {
    const [el, txt] = comInstantaneo ? ["preparando", "preparando-texto"] : ["carregando-app", "carregando-texto"];
    if (!elemento(el)) return;
    elemento(el).hidden = false;
    elemento(txt).textContent = texto;
  }
  function esconderProgresso() {
    for (const id of ["carregando-app", "preparando"]) if (elemento(id)) elemento(id).hidden = true;
  }

  function falhar(erro) {
    falhou = true;
    esconderProgresso();
    pendentes.forEach((p) => p.rejeitar(erro));
    pendentes.clear();
  }

  // O código do worker e o backend.zip são baixados pela página e repassados ao worker:
  // assim tudo passa pelo carregador de arquivos do WebView no APK.
  async function iniciar() {
    falhou = false;
    comInstantaneo = Object.keys(await instantaneo).length > 0;
    mostrarProgresso("Preparando…");
    const [codigo, zip] = await Promise.all([
      fetch("web/offline-worker.js").then((r) => r.text()),
      fetch("web/backend.zip", { cache: "no-cache" }).then((r) => {
        if (!r.ok) throw new Error(`backend.zip: HTTP ${r.status}`);
        return r.arrayBuffer();
      }),
    ]);
    const w = new Worker(URL.createObjectURL(new Blob([codigo], { type: "text/javascript" })));
    w.onmessage = (e) => {
      const m = e.data;
      if (m.tipo === "progresso") mostrarProgresso(m.texto);
      else if (m.tipo === "pronto") {
        console.info("HealthFlow: backend pronto");
        pronto = true;
        esconderProgresso();
        window.dispatchEvent(new Event("healthflow:backend-pronto"));
      } else if (m.tipo === "falha") {
        console.error("HealthFlow: falha ao carregar o backend: " + m.erro);
        falhou = true;
        esconderProgresso();
      } else if (m.tipo === "resposta") {
        const p = pendentes.get(m.id);
        pendentes.delete(m.id);
        if (!p) return;
        if (m.erro) p.rejeitar(new Error(m.erro)); else p.resolver({ status: m.status, texto: m.texto });
      }
    };
    w.onerror = (e) => falhar(new Error(e.message || "falha ao carregar o app"));
    w.postMessage({ tipo: "backend", zip, pyodide: PYODIDE }, [zip]);
    return w;
  }

  function garantirWorker() {
    // Depois de uma falha (ex.: sem internet no primeiro acesso), "Tentar novamente" recria o worker.
    if (!worker || falhou) {
      worker?.then((w) => w.terminate(), () => {});
      worker = iniciar();
      worker.catch(falhar);
    }
  }

  window.backendLocal = async (metodo, caminho, corpo) => {
    if (!pronto && metodo === "GET") {
      const resposta = (await instantaneo)[caminho];
      if (resposta !== undefined) return { status: 200, texto: JSON.stringify(resposta) };
    }
    garantirWorker();
    const w = await worker;
    return new Promise((resolver, rejeitar) => {
      const id = proximoId++;
      pendentes.set(id, { resolver, rejeitar });
      w.postMessage({ tipo: "requisicao", id, metodo, caminho, corpo: corpo ?? null });
    });
  };

  // Começa a carregar o Python já, sem esperar a primeira triagem.
  garantirWorker();

  document.querySelectorAll("[data-servidor]").forEach((el) => { el.hidden = true; });
  document.querySelectorAll("[data-estatico]").forEach((el) => { el.hidden = false; });
})();
