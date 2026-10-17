from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.schemas import Prioridade
from app.triagem.acessibilidade import acompanhante, transporte
from app.unidades.catalogo import POR_ID

c = TestClient(app)


def _tipos(r: dict) -> set[str]:
    return {u["tipo"] for u in r["unidades_sugeridas"]}


def test_hospital_nunca_e_indicado():
    for relato in ["dor no peito e falta de ar", "febre alta e vomitando muito", "nariz escorrendo"]:
        r = c.post("/api/triagem", json={"idade": 50, "relato": relato, "lat": -22.5986, "lon": -48.8003}).json()
        assert "PS" not in _tipos(r)


def test_urgencia_vai_para_upa():
    r = c.post("/api/triagem", json={"idade": 55, "relato": "dor no peito e falta de ar"}).json()
    assert _tipos(r) == {"UPA"}


def test_caso_leve_vai_para_unidade_do_bairro_do_cartao():
    r = c.post("/api/triagem", json={"idade": 68, "relato": "dor de garganta", "cartao_cidadao": "10000001"}).json()
    assert r["unidades_sugeridas"][0]["id"] == "ubs-ubirama"


def test_visitante_sem_cartao_recebe_orientacao():
    r = c.post("/api/triagem", json={"idade": 30, "relato": "dor de garganta", "residente": False}).json()
    assert "não precisa de Cartão Cidadão" in r["orientacao"]


def test_cartao_traz_necessidades_e_ambulancia():
    r = c.post("/api/triagem", json={"idade": 86, "relato": "febre alta e vomitando muito", "intensidade_dor": 7,
                                     "cartao_cidadao": "10000010"}).json()
    assert r["transporte"]["tipo"] == "samu"
    assert r["acompanhante"] is not None


def test_acompanhante_pela_idade():
    assert acompanhante(10, set())["nivel"] == "obrigatorio"
    assert acompanhante(85, set())["nivel"] == "recomendado"
    assert acompanhante(65, set())["nivel"] == "direito"
    assert acompanhante(30, set()) is None
    assert acompanhante(30, {"tea"})["nivel"] == "recomendado"


def test_transporte_conforme_mobilidade():
    assert transporte(Prioridade.VERDE, "UBS", {"cadeirante"}, False)["tipo"] == "adaptado"
    assert transporte(Prioridade.VERDE, "UBS", {"acamado"}, True)["tipo"] == "visita_domiciliar"
    assert transporte(Prioridade.VERDE, "UBS", set(), False) is None


def test_horario_atencao_basica():
    u = POR_ID["ubs-ubirama"]
    assert u.aberta(datetime(2026, 10, 19, 21, 30))       # segunda 21h30
    assert not u.aberta(datetime(2026, 10, 23, 20, 30))   # sexta 20h30
    assert u.aberta(datetime(2026, 10, 24, 12, 0))        # sábado 12h
    assert not u.aberta(datetime(2026, 10, 25, 10, 0))    # domingo
    assert POR_ID["upa-lencois"].aberta(datetime(2026, 10, 25, 3, 0))
