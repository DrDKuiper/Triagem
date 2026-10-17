from app.schemas import Prioridade, SinaisVitais, TriagemEntrada
from app.triagem import regras
from app.triagem.sintomas import extrair_sintomas


def test_extrai_sintomas_e_respeita_negacao():
    s = extrair_sintomas("Estou com febre e tosse, sem falta de ar. Não tenho diarreia.")
    assert {"febre", "tosse"} <= s
    assert "falta_ar" not in s
    assert "diarreia" not in s


def test_avc_e_emergencia():
    e = TriagemEntrada(idade=60)
    assert regras.avaliar(e, {"fraqueza_lado"}).prioridade == Prioridade.VERMELHO


def test_saturacao_baixa_e_emergencia():
    e = TriagemEntrada(idade=30, sinais_vitais=SinaisVitais(saturacao=87))
    assert regras.avaliar(e, set()).prioridade == Prioridade.VERMELHO


def test_resfriado_adulto_e_pouco_urgente():
    e = TriagemEntrada(idade=30)
    assert regras.avaliar(e, {"coriza", "dor_garganta"}).prioridade == Prioridade.VERDE


def test_febre_idoso_eleva_para_amarelo():
    e = TriagemEntrada(idade=72)
    assert regras.avaliar(e, {"febre"}).prioridade == Prioridade.AMARELO
