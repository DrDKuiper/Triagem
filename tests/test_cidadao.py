from fastapi.testclient import TestClient

from app.cidadao.ambiente import contexto_triagem
from app.main import app

c = TestClient(app)


def test_exemplos_ficticios():
    r = c.get("/api/cidadao/exemplos").json()
    assert r["ficticio"] is True
    assert r["cartoes"][0]["cartao"] == "10000001"


def test_consulta_traz_cadastro_ambiente_e_alertas():
    r = c.get("/api/cidadao/10000001").json()
    assert r["cidadao"]["nome"] == "Maria Aparecida dos Santos"
    assert r["cidadao"]["endereco"]["bairro"] == "Jardim Ubirama"
    assert {i["tipo"] for i in r["ambiente"]["indicadores"]} == {"dengue", "ar", "alagamento", "escorpiao"}
    assert isinstance(r["alertas"], list)


def test_cartao_aceita_formatacao_e_inexistente_da_404():
    assert c.get("/api/cidadao/10.000.002").status_code == 200
    assert c.get("/api/cidadao/99999999").status_code == 404


def test_triagem_com_cartao_completa_perfil():
    # Sem informar doenças nem localização: o cartão traz diabetes/hipertensão e o endereço.
    r = c.post("/api/triagem", json={"idade": 68, "relato": "febre", "cartao_cidadao": "10000001"}).json()
    assert r["unidades_sugeridas"]
    assert any("grupo de risco" in m for m in r["motivos"])


def test_contexto_ambiental_sugere_dengue_em_bairro_de_risco():
    analise = {"bairro": "Teste", "indicadores": [
        {"tipo": "dengue", "nivel": "alto", "valor": "LIRAa 5%"},
        {"tipo": "ar", "nivel": "baixo", "valor": ""},
        {"tipo": "alagamento", "nivel": "baixo", "valor": ""},
        {"tipo": "escorpiao", "nivel": "baixo", "valor": ""},
    ]}
    obs, dengue = contexto_triagem({"febre", "dor_corpo"}, analise)
    assert dengue and obs
    assert contexto_triagem({"tosse"}, analise) == ([], False)
