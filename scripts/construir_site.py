"""Gera a versão estática do app (GitHub Pages e APK), sem servidor.

O backend Python vai empacotado em web/backend.zip (com o FastAPI e suas dependências,
que são Python puro) e roda no navegador via Pyodide (app/web/offline-worker.js). Uso:

    python scripts/construir_site.py _site            # GitHub Pages: Pyodide vem do CDN
    python scripts/construir_site.py site --app       # APK: tela cheia e tudo embutido (offline)

Com --app, o Pyodide, as bibliotecas (numpy, pandas, scikit-learn, pydantic) e o Leaflet
são baixados uma vez para .cache/ e copiados para o site, que então funciona sem internet
(só os blocos do mapa vêm da internet).
"""

from __future__ import annotations

import io
import json
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
WEB = RAIZ / "app" / "web"
CACHE = RAIZ / ".cache"

PYODIDE_VERSAO = "0.27.7"  # igual ao de app/web/offline.js
PYODIDE_CDN = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSAO}/full/"
PYODIDE_NUCLEO = ["pyodide.js", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"]
# Pacotes do Pyodide carregados pelo worker (as dependências entram automaticamente).
PYODIDE_PACOTES = ["numpy", "pandas", "scikit-learn", "pydantic"]
# Wheels Python puro que não vêm no Pyodide; vão dentro do backend.zip.
WHEELS = {"fastapi": "0.115.12", "starlette": "0.46.2", "anyio": "4.9.0", "sniffio": "1.3.1", "idna": "3.10"}
LEAFLET = "https://registry.npmjs.org/leaflet/-/leaflet-1.9.4.tgz"
LEAFLET_CDN = "https://unpkg.com/leaflet@1.9.4/dist/"


def baixar(url: str, destino: Path) -> Path:
    """Baixa para o cache (uma vez só)."""
    if not destino.exists():
        destino.parent.mkdir(parents=True, exist_ok=True)
        print(f"baixando {url}")
        with urllib.request.urlopen(url, timeout=120) as r:
            dados = r.read()
        temporario = destino.with_suffix(destino.suffix + ".part")
        temporario.write_bytes(dados)
        temporario.replace(destino)
    return destino


def wheel(nome: str, versao: str) -> Path:
    destino = CACHE / "wheels" / f"{nome}-{versao}.whl"
    if not destino.exists():
        with urllib.request.urlopen(f"https://pypi.org/pypi/{nome}/{versao}/json", timeout=60) as r:
            info = json.load(r)
        url = next(u["url"] for u in info["urls"] if u["filename"].endswith("-py3-none-any.whl"))
        baixar(url, destino)
    return destino


def pacotes_pyodide(lock: dict) -> list[str]:
    """Arquivos dos pacotes pedidos e de todas as suas dependências."""
    # Os nomes nas dependências nem sempre batem com as chaves (pydantic_core x pydantic-core).
    normalizar = lambda nome: nome.lower().replace("_", "-")  # noqa: E731
    pacotes = {normalizar(n): p for n, p in lock["packages"].items()}
    vistos: set[str] = set()
    pendentes = list(PYODIDE_PACOTES)
    while pendentes:
        nome = normalizar(pendentes.pop())
        if nome in vistos:
            continue
        vistos.add(nome)
        pendentes.extend(pacotes[nome]["depends"])
    return sorted(pacotes[n]["file_name"] for n in vistos)


def copiar_pyodide(destino: Path) -> None:
    cache = CACHE / f"pyodide-{PYODIDE_VERSAO}"
    destino.mkdir(parents=True)
    for arquivo in PYODIDE_NUCLEO:
        shutil.copy2(baixar(PYODIDE_CDN + arquivo, cache / arquivo), destino / arquivo)
    lock = json.loads((cache / "pyodide-lock.json").read_text(encoding="utf-8"))
    for arquivo in pacotes_pyodide(lock):
        shutil.copy2(baixar(PYODIDE_CDN + arquivo, cache / arquivo), destino / arquivo)


def copiar_leaflet(destino: Path) -> None:
    pacote = baixar(LEAFLET, CACHE / "leaflet-1.9.4.tgz")
    with tarfile.open(pacote) as tar:
        for membro in tar.getmembers():
            if membro.isfile() and membro.name.startswith("package/dist/") and not membro.name.endswith((".map", "-src.js", "-src.esm.js", ".esm.js")):
                alvo = destino / membro.name.removeprefix("package/dist/")
                alvo.parent.mkdir(parents=True, exist_ok=True)
                alvo.write_bytes(tar.extractfile(membro).read())


def construir(saida: Path, app: bool = False) -> Path:
    if saida.exists():
        shutil.rmtree(saida)
    (saida / "web").mkdir(parents=True)

    for arquivo in ("app.js", "estilo.css", "offline.js", "offline-worker.js"):
        shutil.copy2(WEB / arquivo, saida / "web" / arquivo)

    html = (WEB / "index.html").read_text(encoding="utf-8")
    tag_app = '<script src="web/app.js"></script>'
    if tag_app not in html or LEAFLET_CDN not in html:
        raise SystemExit("index.html: tags do app.js/Leaflet não encontradas")
    html = html.replace(tag_app, '<script src="web/offline.js"></script>\n  ' + tag_app)
    if app:
        html = html.replace('<html lang="pt-BR">', '<html lang="pt-BR" class="modo-app" data-pyodide="pyodide/">', 1)
        html = html.replace(LEAFLET_CDN, "web/leaflet/")
        html = html.replace("Na primeira vez o app baixa cerca de 40 MB e pode levar até um minuto.",
                            "Tudo roda no celular, sem internet.")
        copiar_pyodide(saida / "pyodide")
        copiar_leaflet(saida / "web" / "leaflet")
    (saida / "index.html").write_text(html, encoding="utf-8")

    # O pacote app/ inteiro (main.py monta app/web como estáticos, então ele também vai)
    # e o conteúdo das wheels do FastAPI, que ficam importáveis a partir da mesma pasta.
    with zipfile.ZipFile(saida / "web" / "backend.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted((RAIZ / "app").rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc":
                z.write(f, f.relative_to(RAIZ).as_posix())
        for nome, versao in WHEELS.items():
            with zipfile.ZipFile(io.BytesIO(wheel(nome, versao).read_bytes())) as w:
                for item in w.infolist():
                    if not item.is_dir():
                        z.writestr(item.filename, w.read(item))

    (saida / ".nojekyll").touch()
    return saida


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--app"]
    destino = construir(Path(args[0] if args else "_site").resolve(), app="--app" in sys.argv[1:])
    print(f"Site gerado em {destino}")
