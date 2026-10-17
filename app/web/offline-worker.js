// Web Worker da versão estática: carrega o Python (Pyodide) com numpy, pandas e
// scikit-learn, instala o FastAPI e roda o backend do app (app/offline.py).
// A página (offline.js) envia primeiro o backend.zip e depois as requisições.
"use strict";

const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/";
importScripts(PYODIDE + "pyodide.js");

const progresso = (texto) => postMessage({ tipo: "progresso", texto });

let receberZip;
const zipRecebido = new Promise((r) => { receberZip = r; });

const pronto = (async () => {
  progresso("Baixando o Python…");
  const py = await loadPyodide({ indexURL: PYODIDE });
  progresso("Carregando numpy, pandas e scikit-learn…");
  await py.loadPackage(["numpy", "pandas", "scikit-learn", "pydantic", "micropip"]);
  progresso("Instalando o FastAPI…");
  await py.pyimport("micropip").install(["fastapi==0.115.12"]);
  progresso("Carregando o app…");
  py.unpackArchive(await zipRecebido, "zip", { extractDir: "/backend" });
  py.runPython("import sys; sys.path.insert(0, '/backend')");
  progresso("Treinando o modelo de triagem…");
  const offline = py.pyimport("app.offline");
  py.pyimport("app.main").saude(); // treina o modelo de ML da triagem antes da primeira consulta
  return offline.requisicao;
})();

pronto.then(
  () => postMessage({ tipo: "pronto" }),
  (e) => postMessage({ tipo: "falha", erro: String(e) }),
);

onmessage = async (e) => {
  const m = e.data;
  if (m.tipo === "backend") { receberZip(m.zip); return; }
  try {
    const requisicao = await pronto;
    const resposta = requisicao(m.metodo, m.caminho, m.corpo);
    const [status, texto] = resposta.toJs();
    resposta.destroy();
    postMessage({ tipo: "resposta", id: m.id, status, texto });
  } catch (err) {
    postMessage({ tipo: "resposta", id: m.id, erro: String(err.message || err).split("\n").slice(-2).join(" ") });
  }
};
