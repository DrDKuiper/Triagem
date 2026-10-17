"""Gera a versão estática do app (GitHub Pages e APK), sem servidor.

O backend Python vai empacotado em web/backend.zip e roda no navegador via Pyodide
(app/web/offline-worker.js). Uso:

    python scripts/construir_site.py _site            # GitHub Pages
    python scripts/construir_site.py site --app       # APK: tela cheia, sem moldura de celular
"""

from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
WEB = RAIZ / "app" / "web"


def construir(saida: Path, app: bool = False) -> Path:
    if saida.exists():
        shutil.rmtree(saida)
    (saida / "web").mkdir(parents=True)

    for arquivo in ("app.js", "estilo.css", "offline.js", "offline-worker.js"):
        shutil.copy2(WEB / arquivo, saida / "web" / arquivo)

    html = (WEB / "index.html").read_text(encoding="utf-8")
    tag_app = '<script src="web/app.js"></script>'
    if tag_app not in html:
        raise SystemExit("index.html: tag do app.js não encontrada")
    html = html.replace(tag_app, '<script src="web/offline.js"></script>\n  ' + tag_app)
    if app:
        html = html.replace('<html lang="pt-BR">', '<html lang="pt-BR" class="modo-app">', 1)
    (saida / "index.html").write_text(html, encoding="utf-8")

    # O pacote app/ inteiro (main.py monta app/web como estáticos, então ele também vai).
    with zipfile.ZipFile(saida / "web" / "backend.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted((RAIZ / "app").rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc":
                z.write(f, f.relative_to(RAIZ).as_posix())

    (saida / ".nojekyll").touch()
    return saida


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--app"]
    destino = construir(Path(args[0] if args else "_site").resolve(), app="--app" in sys.argv[1:])
    print(f"Site gerado em {destino}")
