// Web Worker da versão estática: carrega o Python (Pyodide) com numpy, pandas e
// scikit-learn e roda o backend do app (app/offline.py). A página (offline.js) envia
// primeiro o backend.zip (app/ + FastAPI) e o endereço do Pyodide, depois as requisições.
"use strict";

const progresso = (texto) => postMessage({ tipo: "progresso", texto });

let receberBackend;
const backendRecebido = new Promise((r) => { receberBackend = r; });

const pronto = (async () => {
  const { zip, pyodide } = await backendRecebido;
  const inicio = performance.now();
  progresso("Carregando o Python…");
  importScripts(pyodide + "pyodide.js");
  const py = await loadPyodide({ indexURL: pyodide });
  progresso("Carregando numpy, pandas e scikit-learn…");
  await py.loadPackage(["numpy", "pandas", "scikit-learn", "pydantic", "ssl"]); // igual a scripts/construir_site.py
  progresso("Carregando o app…");
  py.unpackArchive(zip, "zip", { extractDir: "/backend" });
  py.runPython("import sys; sys.path.insert(0, '/backend')");
  progresso("Preparando o modelo de triagem…");
  const offline = py.pyimport("app.offline");
  // Carrega (ou, sem o arquivo pré-treinado, treina) o modelo de ML antes da primeira consulta.
  const saude = py.pyimport("app.main").saude();
  const modelo = saude.get("origem_modelo_triagem");
  saude.destroy();
  return { requisicao: offline.requisicao, modelo, segundos: (performance.now() - inicio) / 1000 };
})();

pronto.then(
  ({ modelo, segundos }) => postMessage({ tipo: "pronto", modelo, segundos }),
  (e) => postMessage({ tipo: "falha", erro: String(e) }),
);

onmessage = async (e) => {
  const m = e.data;
  if (m.tipo === "backend") { receberBackend(m); return; }
  try {
    const { requisicao } = await pronto;
    const resposta = requisicao(m.metodo, m.caminho, m.corpo);
    const [status, texto] = resposta.toJs();
    resposta.destroy();
    postMessage({ tipo: "resposta", id: m.id, status, texto });
  } catch (err) {
    postMessage({ tipo: "resposta", id: m.id, erro: String(err.message || err).split("\n").slice(-2).join(" ") });
  }
};
