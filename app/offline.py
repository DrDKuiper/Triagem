"""Atende as rotas da API sem servidor HTTP, para a versão estática (GitHub Pages e APK).

Nessas versões o backend roda dentro do navegador (Pyodide, num Web Worker), onde não
há uvicorn nem threads. O JavaScript chama `requisicao(metodo, caminho, corpo)` e
recebe `(status, json)` como se tivesse feito um fetch para o servidor.
"""

from __future__ import annotations

import json
import re
from urllib.parse import parse_qs, urlsplit

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError

from app import main
from app.schemas import TriagemEntrada


def _numero(query: dict[str, list[str]], nome: str, tipo=float, padrao=None, minimo=None, maximo=None):
    if nome not in query:
        return padrao
    try:
        valor = tipo(query[nome][-1])
    except ValueError:
        raise HTTPException(422, f"Parâmetro inválido: {nome}")
    if (minimo is not None and valor < minimo) or (maximo is not None and valor > maximo):
        raise HTTPException(422, f"Parâmetro fora do intervalo: {nome}")
    return valor


def _texto(query: dict[str, list[str]], nome: str) -> str | None:
    return query[nome][-1] if nome in query else None


def _semanas(q):
    return _numero(q, "semanas", int, 8, 1, 26)


# (método, caminho, função(match, query, corpo))
_ROTAS = [
    ("GET", r"/api/saude", lambda m, q, b: main.saude()),
    ("GET", r"/api/config", lambda m, q, b: main.configuracao()),
    ("GET", r"/api/cidadao/exemplos", lambda m, q, b: main.cartoes_de_teste()),
    ("GET", r"/api/cidadao/(?P<cartao>[^/]+)", lambda m, q, b: main.consultar_cidadao(m["cartao"])),
    ("POST", r"/api/triagem", lambda m, q, b: main.nova_triagem(TriagemEntrada.model_validate(b or {}))),
    (
        "GET",
        r"/api/unidades",
        lambda m, q, b: main.listar_unidades(
            lat=_numero(q, "lat", minimo=-90, maximo=90),
            lon=_numero(q, "lon", minimo=-180, maximo=180),
            tipo=q.get("tipo"),
            prioridade=_texto(q, "prioridade"),
        ),
    ),
    ("GET", r"/api/unidades/(?P<id>[^/]+)", lambda m, q, b: main.detalhe_unidade(m["id"])),
    ("GET", r"/api/previsoes", lambda m, q, b: main.previsoes(_semanas(q))),
    ("GET", r"/api/previsoes/(?P<agravo>[^/]+)", lambda m, q, b: main.previsao_agravo(m["agravo"], _semanas(q))),
    ("GET", r"/api/dados-uteis", lambda m, q, b: main.dados_uteis()),
]
_ROTAS = [(metodo, re.compile(padrao + r"/?"), funcao) for metodo, padrao, funcao in _ROTAS]


def requisicao(metodo: str, caminho: str, corpo: str | None = None) -> tuple[int, str]:
    """Executa a rota correspondente e devolve (status HTTP, corpo JSON)."""
    url = urlsplit(caminho)
    query = parse_qs(url.query)
    try:
        dados = json.loads(corpo) if corpo else None
        for m, padrao, funcao in _ROTAS:
            achou = padrao.fullmatch(url.path)
            if achou and m == metodo.upper():
                return 200, json.dumps(jsonable_encoder(funcao(achou, query, dados)), ensure_ascii=False)
        raise HTTPException(404, "Not Found")
    except HTTPException as e:
        return e.status_code, json.dumps({"detail": e.detail}, ensure_ascii=False)
    except ValidationError as e:
        return 422, json.dumps({"detail": jsonable_encoder(e.errors(include_url=False, include_context=False))}, ensure_ascii=False)
    except json.JSONDecodeError:
        return 400, json.dumps({"detail": "JSON inválido"})
