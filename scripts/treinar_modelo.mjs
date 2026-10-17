// Treina o modelo de triagem dentro do Pyodide (Node), com as mesmas versões de Python,
// numpy e scikit-learn do app, e salva o arquivo que vai embutido na versão estática.
// Chamado por scripts/construir_site.py:
//
//   node scripts/treinar_modelo.mjs <pasta do Pyodide> <raiz do repositório> <arquivo de saída>
import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";
import { pathToFileURL } from "node:url";

const [pastaPyodide, raiz, saida] = process.argv.slice(2);
const { loadPyodide } = await import(pathToFileURL(join(pastaPyodide, "pyodide.mjs")).href);

const py = await loadPyodide({ indexURL: pastaPyodide.endsWith("/") ? pastaPyodide : pastaPyodide + "/" });
await py.loadPackage(["numpy", "pandas", "scikit-learn", "pydantic"], { messageCallback: () => {} });

// Copia o pacote app/ para o sistema de arquivos do Pyodide.
function copiar(pasta) {
  for (const nome of readdirSync(pasta)) {
    const caminho = join(pasta, nome);
    if (nome === "__pycache__" || nome === "web") continue;
    const destino = "/repo/" + relative(raiz, caminho).replaceAll("\\", "/");
    if (statSync(caminho).isDirectory()) {
      py.FS.mkdirTree(destino);
      copiar(caminho);
    } else if (nome.endsWith(".py")) {
      py.FS.writeFile(destino, readFileSync(caminho));
    }
  }
}
py.FS.mkdirTree("/repo/app");
copiar(join(raiz, "app"));

const inicio = Date.now();
py.runPython(`
import sys
sys.path.insert(0, "/repo")
from app.config import config
from app.triagem.modelo_ml import ModeloTriagem, gerar_base_sintetica, salvar_pronto
from pathlib import Path
salvar_pronto(ModeloTriagem(config.semente).treinar(gerar_base_sintetica(semente=config.semente)), Path("/modelo.pkl.gz"))
`);
writeFileSync(saida, py.FS.readFile("/modelo.pkl.gz"));
console.log(`modelo de triagem treinado no Pyodide em ${((Date.now() - inicio) / 1000).toFixed(1)} s`);
