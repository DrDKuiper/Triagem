"""Teste de fumaça no navegador: consulta um Cartão Cidadão e faz uma triagem completa.

Serve tanto para o app com o servidor FastAPI quanto para a versão estática (Pages):

    python scripts/testar_site.py http://localhost:8000 [--screenshot tela.png]
"""

from __future__ import annotations

import argparse
import os

from playwright.sync_api import expect, sync_playwright

# Na versão estática o primeiro acesso baixa o Python e as bibliotecas (dezenas de MB).
TEMPO_MS = 240_000


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--screenshot")
    args = ap.parse_args()

    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        pagina = navegador.new_page(viewport={"width": 412, "height": 900})
        erros: list[str] = []
        pagina.on("pageerror", lambda e: erros.append(str(e)))
        pagina.on("console", lambda m: print("console:", m.text) if m.type in ("error", "warning") else None)

        pagina.goto(args.url)
        pagina.locator(".cartao.exemplo").first.wait_for(timeout=TEMPO_MS)
        expect(pagina.locator("#aviso-conexao")).to_be_hidden()

        pagina.locator(".cartao.exemplo").first.click()
        pagina.locator("#c-iniciar").click(timeout=60_000)
        pagina.fill("#f-relato", "febre alta desde ontem, dor no corpo e atrás dos olhos")
        pagina.click("#f-avaliar")
        faixa = pagina.locator(".faixa-prioridade")
        faixa.wait_for(timeout=60_000)
        print("Triagem:", faixa.inner_text().replace("\n", " | "))

        pagina.click('.navegacao button[data-aba="previsoes"]')
        pagina.locator("#aba-previsoes .grafico").first.wait_for(timeout=120_000)
        pagina.click('.navegacao button[data-aba="unidades"]')
        expect(pagina.locator("#u-lista .cartao").first).to_be_visible(timeout=30_000)

        pagina.click('.navegacao button[data-aba="triagem"]')
        if args.screenshot:
            pagina.screenshot(path=args.screenshot)
        navegador.close()
        if erros:
            raise SystemExit("Erros de JavaScript: " + "; ".join(erros))
    print("OK")


if __name__ == "__main__":
    main()
