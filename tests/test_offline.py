import json

from fastapi.testclient import TestClient

from app.main import app
from app.offline import requisicao

c = TestClient(app)


def _offline(metodo, caminho, corpo=None):
    status, texto = requisicao(metodo, caminho, json.dumps(corpo) if corpo is not None else None)
    return status, json.loads(texto)


def test_mesmas_respostas_que_a_api():
    for caminho in ["/api/config", "/api/cidadao/exemplos", "/api/cidadao/10000001", "/api/dados-uteis",
                    "/api/unidades?lat=-22.5986&lon=-48.8003&tipo=UBS", "/api/previsoes?semanas=4"]:
        status, dados = _offline("GET", caminho)
        assert status == 200, caminho
        if "unidades" not in caminho:  # a ocupação das unidades muda com o tempo
            assert dados == c.get(caminho).json(), caminho


def test_triagem_offline():
    entrada = {"idade": 55, "relato": "dor no peito e falta de ar"}
    status, r = _offline("POST", "/api/triagem", entrada)
    assert status == 200
    assert r["prioridade"] == "vermelho" and r["destino"] == "SAMU"


def test_erros_offline():
    assert _offline("GET", "/api/cidadao/99999999")[0] == 404
    assert _offline("GET", "/api/inexistente")[0] == 404
    assert _offline("GET", "/api/previsoes?semanas=99")[0] == 422
    assert _offline("POST", "/api/triagem", {"idade": "abc"})[0] == 422
