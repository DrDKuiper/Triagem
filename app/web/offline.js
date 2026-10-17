// Versão estática (GitHub Pages e APK): em vez de chamar o servidor FastAPI, o app chama
// o mesmo backend Python rodando no navegador, via Pyodide num Web Worker
// (offline-worker.js). Este arquivo só é incluído na página pelo scripts/construir_site.py.
"use strict";

(() => {
  let worker = null; // Promise<Worker>
  let falhou = false;
  let proximoId = 1;
  const pendentes = new Map();

  const overlay = () => document.getElementById("carregando-app");
  const mostrarCarregando = (texto) => {
    const el = overlay();
    if (!el) return;
    el.hidden = false;
    document.getElementById("carregando-texto").textContent = texto;
  };
  const esconderCarregando = () => { const el = overlay(); if (el) el.hidden = true; };

  function falhar(erro) {
    falhou = true;
    esconderCarregando();
    pendentes.forEach((p) => p.rejeitar(erro));
    pendentes.clear();
  }

  // O código do worker e o backend.zip são baixados pela página e repassados ao worker:
  // assim tudo passa pelo carregador de arquivos do WebView no APK.
  async function iniciar() {
    falhou = false;
    mostrarCarregando("Preparando…");
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
      if (m.tipo === "progresso") mostrarCarregando(m.texto);
      else if (m.tipo === "pronto") esconderCarregando();
      else if (m.tipo === "falha") { falhou = true; esconderCarregando(); }
      else if (m.tipo === "resposta") {
        const p = pendentes.get(m.id);
        pendentes.delete(m.id);
        if (!p) return;
        if (m.erro) p.rejeitar(new Error(m.erro)); else p.resolver({ status: m.status, texto: m.texto });
      }
    };
    w.onerror = (e) => falhar(new Error(e.message || "falha ao carregar o app"));
    w.postMessage({ tipo: "backend", zip }, [zip]);
    return w;
  }

  window.backendLocal = (metodo, caminho, corpo) => {
    // Depois de uma falha (ex.: sem internet no primeiro acesso), "Tentar novamente" recria o worker.
    if (!worker || falhou) {
      worker?.then((w) => w.terminate(), () => {});
      worker = iniciar();
      worker.catch(falhar);
    }
    return new Promise((resolver, rejeitar) => {
      const id = proximoId++;
      pendentes.set(id, { resolver, rejeitar });
      worker.then((w) => w.postMessage({ tipo: "requisicao", id, metodo, caminho, corpo: corpo ?? null }), () => {});
    });
  };

  document.querySelectorAll("[data-servidor]").forEach((el) => { el.hidden = true; });
  document.querySelectorAll("[data-estatico]").forEach((el) => { el.hidden = false; });
})();
