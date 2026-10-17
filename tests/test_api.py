from fastapi.testclient import TestClient

from app.main import app

c = TestClient(app)
LAT, LON = -22.5986, -48.8003


def test_saude():
    r = c.get("/api/saude").json()
    assert r["status"] == "ok"
    assert r["prontuario"] == "simulado"


def test_triagem_regra_prevalece_sobre_ml():
    r = c.post("/api/triagem", json={"idade": 55, "relato": "dor no peito e falta de ar"}).json()
    assert r["prioridade"] == "vermelho"
    assert r["destino"] == "SAMU"


def test_triagem_leve_vai_para_ubs_ou_autocuidado_com_sugestoes():
    r = c.post("/api/triagem", json={"idade": 25, "relato": "nariz escorrendo", "lat": LAT, "lon": LON}).json()
    assert r["destino"] in {"UBS", "AUTOCUIDADO"}
    assert r["unidades_sugeridas"]


def test_unidades_com_distancia_e_ocupacao():
    r = c.get("/api/unidades", params={"lat": LAT, "lon": LON}).json()
    assert set(r["em_atendimento_por_tipo"]) == {"UPA", "UBS", "PS"}
    u = r["unidades"][0]
    assert "distancia_km" in u and "em_atendimento" in u


def test_versao_web():
    r = c.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert c.get("/web/app.js").status_code == 200


def test_unidade_inexistente():
    assert c.get("/api/unidades/nao-existe").status_code == 404


def test_previsoes():
    r = c.get("/api/previsoes", params={"semanas": 4}).json()
    assert r["horizonte_semanas"] == 4
    nomes = {a["agravo"] for a in r["agravos"]}
    assert {"sindrome_gripal", "dengue", "covid19"} <= nomes
    for a in r["agravos"]:
        assert len(a["previsao"]) == 4
        for p in a["previsao"]:
            assert p["minimo"] <= p["previsto"] <= p["maximo"]
