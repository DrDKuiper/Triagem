"""Gera a versão estática do app (GitHub Pages e APK), sem servidor.

O backend Python vai empacotado em web/backend.zip (com o FastAPI e suas dependências,
que são Python puro) e roda no navegador via Pyodide (app/web/offline-worker.js). Uso:

    python scripts/construir_site.py _site            # GitHub Pages: Pyodide vem do CDN
    python scripts/construir_site.py site --app       # APK: tela cheia e tudo embutido (offline)

Com --app, o Pyodide, as bibliotecas (numpy, pandas, scikit-learn, pydantic) e o Leaflet
são baixados uma vez para .cache/ e copiados para o site, que então funciona sem internet
(só os blocos do mapa vêm da internet).

Se as dependências do backend estiverem instaladas (requirements.txt), as respostas que só
dependem dos dados fictícios vão pré-calculadas em web/instantaneo.json: a página abre na
hora, enquanto o Python carrega em segundo plano para a triagem e as unidades.

Com o Node instalado, o modelo de triagem é treinado uma vez dentro do Pyodide
(scripts/treinar_modelo.mjs, mesmas versões do app) e vai pronto no backend.zip; sem ele,
o app treina o modelo ao abrir.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
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
PYODIDE_NODE = "pyodide.mjs"  # só para treinar o modelo no Node; não vai para o site
# Pacotes do Pyodide carregados pelo worker (as dependências entram automaticamente).
PYODIDE_PACOTES = ["numpy", "pandas", "scikit-learn", "pydantic", "ssl"]  # ssl: exigido pelo anyio (FastAPI)
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


def arquivos_pyodide() -> tuple[Path, list[str]]:
    """Baixa (uma vez) o Pyodide e os pacotes usados; devolve a pasta do cache e os arquivos do site."""
    cache = CACHE / f"pyodide-{PYODIDE_VERSAO}"
    for arquivo in [*PYODIDE_NUCLEO, PYODIDE_NODE]:
        baixar(PYODIDE_CDN + arquivo, cache / arquivo)
    lock = json.loads((cache / "pyodide-lock.json").read_text(encoding="utf-8"))
    pacotes = pacotes_pyodide(lock)
    for arquivo in pacotes:
        baixar(PYODIDE_CDN + arquivo, cache / arquivo)
    return cache, [*PYODIDE_NUCLEO, *pacotes]


def copiar_pyodide(destino: Path) -> None:
    cache, arquivos = arquivos_pyodide()
    destino.mkdir(parents=True)
    for arquivo in arquivos:
        shutil.copy2(cache / arquivo, destino / arquivo)


def modelo_pronto() -> Path | None:
    """Modelo de triagem treinado no Pyodide (cache pela versão do código que o gera)."""
    fontes = sorted([*(RAIZ / "app" / "triagem").glob("*.py"), RAIZ / "app" / "schemas.py", RAIZ / "app" / "config.py"])
    chave = hashlib.sha256(PYODIDE_VERSAO.encode() + b"".join(f.read_bytes() for f in fontes)).hexdigest()[:16]
    arquivo = CACHE / "modelo" / f"triagem-{chave}.pkl.gz"
    if arquivo.exists():
        return arquivo
    if not shutil.which("node"):
        print("aviso: sem Node, o modelo de triagem não vai pronto (o app treina ao abrir)")
        return None
    try:
        pasta, _ = arquivos_pyodide()
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = arquivo.with_suffix(".part")
        subprocess.run(["node", str(RAIZ / "scripts" / "treinar_modelo.mjs"), str(pasta), str(RAIZ), str(temporario)], check=True)
        temporario.replace(arquivo)
        return arquivo
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"aviso: falha ao treinar o modelo no Pyodide ({e}); o app treina ao abrir")
        return None


def copiar_leaflet(destino: Path) -> None:
    pacote = baixar(LEAFLET, CACHE / "leaflet-1.9.4.tgz")
    with tarfile.open(pacote) as tar:
        for membro in tar.getmembers():
            if membro.isfile() and membro.name.startswith("package/dist/") and not membro.name.endswith((".map", "-src.js", "-src.esm.js", ".esm.js")):
                alvo = destino / membro.name.removeprefix("package/dist/")
                alvo.parent.mkdir(parents=True, exist_ok=True)
                alvo.write_bytes(tar.extractfile(membro).read())


def caminhos_instantaneo() -> list[str]:
    """Rotas GET respondidas antes do Python carregar. Unidades ficam de fora: o status
    aberta/fechada e a ocupação dependem da hora em que o app é usado."""
    from app.cidadao import obter_cadastro

    cartoes = [f"/api/cidadao/{c}" for c in obter_cadastro().cartoes()]
    return ["/api/config", "/api/cidadao/exemplos", "/api/dados-uteis", "/api/previsoes?semanas=8", *cartoes]


def gerar_instantaneo(destino: Path) -> None:
    sys.path.insert(0, str(RAIZ))
    try:
        from app.offline import requisicao
    except ImportError as e:
        print(f"aviso: sem web/instantaneo.json ({e}); instale o requirements.txt para a abertura rápida")
        return
    respostas = {}
    for caminho in caminhos_instantaneo():
        status, texto = requisicao("GET", caminho)
        if status != 200:
            raise SystemExit(f"{caminho}: HTTP {status} {texto[:200]}")
        respostas[caminho] = json.loads(texto)
    destino.write_text(json.dumps(respostas, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


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
        modelo = modelo_pronto()
        if modelo:  # já comprimido: guarda sem comprimir de novo
            z.write(modelo, "app/triagem/modelo_triagem.pkl.gz", compress_type=zipfile.ZIP_STORED)

    gerar_instantaneo(saida / "web" / "instantaneo.json")
    (saida / ".nojekyll").touch()
    return saida


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--app"]
    destino = construir(Path(args[0] if args else "_site").resolve(), app="--app" in sys.argv[1:])
    print(f"Site gerado em {destino}")
