"""Análise ambiental do bairro do cidadão e relação com o perfil de saúde dele.

Combina o clima e os casos recentes do histórico semanal (prontuário) com os
fatores de cada bairro. Indicadores e faixas seguem referências usadas no Brasil:
LIRAa do Ministério da Saúde (<1% satisfatório, 1–3,9% alerta, ≥4% risco) e
índice de qualidade do ar da CETESB para MP2,5 (µg/m³, média de 24 h).
"""

from __future__ import annotations

import pandas as pd

from app.cidadao.bairros import Bairro

_ORDEM = {"baixo": 0, "moderado": 1, "alto": 2}


def _nivel_liraa(v: float) -> str:
    return "alto" if v >= 4 else "moderado" if v >= 1 else "baixo"


def _qualidade_ar(pm25: float) -> tuple[str, str]:
    if pm25 <= 15:
        return "Boa", "baixo"
    if pm25 <= 50:
        return "Moderada", "moderado"
    if pm25 <= 75:
        return "Ruim", "alto"
    return "Muito ruim", "alto"


def analisar_bairro(bairro: Bairro, historico: pd.DataFrame) -> dict:
    """Indicadores ambientais do bairro nas últimas semanas."""
    ultimas = historico.tail(4)
    temperatura = float(ultimas["temperatura"].iloc[-1])
    umidade = float(ultimas["umidade"].iloc[-1])
    chuva_4sem = float(ultimas["chuva_mm"].sum())

    # Dengue: intensidade atual do município relativa ao normal, distribuída pelos bairros.
    dengue_4sem = float(ultimas["dengue"].sum())
    fator = min(max(dengue_4sem / max(historico["dengue"].median() * 4, 1), 0.3), 3.0)
    liraa = round(bairro.liraa_base * fator ** 0.5, 1)
    casos_dengue = int(round(dengue_4sem * bairro.peso_populacao * bairro.liraa_base / 2.4))

    # Qualidade do ar: piora na seca (umidade baixa), sobretudo perto de canaviais (queimadas).
    seca = max(0.0, 70 - umidade)
    pm25 = round(8 + seca * 0.9 + (6 + seca * 0.6 if bairro.perto_canavial else 0), 0)
    qualidade, nivel_ar = _qualidade_ar(pm25)

    alagamento = "alto" if bairro.perto_rio and chuva_4sem >= 220 else "moderado" if bairro.perto_rio and chuva_4sem >= 120 else "baixo"
    escorpioes = int(round(bairro.escorpioes_base * (1 + max(0.0, temperatura - 22) / 4)))

    indicadores = [
        {
            "tipo": "dengue", "nivel": _nivel_liraa(liraa), "titulo": "Aedes aegypti / dengue",
            "valor": f"LIRAa {liraa:.1f}% • {casos_dengue} casos no bairro em 4 semanas".replace(".", ",", 1),
            "recomendacao": "Elimine água parada (vasos, calhas, pneus) e use repelente.",
        },
        {
            "tipo": "ar", "nivel": nivel_ar, "titulo": "Qualidade do ar",
            "valor": f"{qualidade} (MP2,5 ≈ {pm25:.0f} µg/m³, umidade {umidade:.0f}%)",
            "recomendacao": "Na seca, beba água, evite exercícios ao ar livre à tarde e mantenha a casa ventilada.",
        },
        {
            "tipo": "alagamento", "nivel": alagamento, "titulo": "Alagamento / leptospirose",
            "valor": f"{int(chuva_4sem + 0.5)} mm de chuva em 4 semanas" + (" • bairro próximo ao Rio Lençóis" if bairro.perto_rio else ""),
            "recomendacao": "Evite contato com água de enchente; febre e dor na panturrilha após enchente exigem avaliação.",
        },
        {
            "tipo": "escorpiao", "nivel": "moderado" if escorpioes >= 4 else "baixo", "titulo": "Escorpiões",
            "valor": f"{escorpioes} notificações no último mês",
            "recomendacao": "Sacuda roupas e calçados; picada em criança ou idoso é urgência.",
        },
    ]
    return {
        "bairro": bairro.nome,
        "clima": {"temperatura": temperatura, "umidade": umidade, "chuva_4sem_mm": round(chuva_4sem, 1)},
        "liraa": liraa,
        "casos_dengue_4sem": casos_dengue,
        "pm25": pm25,
        "indicadores": indicadores,
    }


def alertas_pessoais(cidadao: dict, analise: dict) -> list[dict]:
    """Cruza os indicadores do bairro com idade, gestação e doenças do cidadão."""
    niveis = {i["tipo"]: i["nivel"] for i in analise["indicadores"]}
    comorb = set(cidadao.get("comorbidades", []))
    idade = cidadao.get("idade", 30)
    alertas: list[dict] = []

    if niveis["dengue"] != "baixo":
        risco = []
        if idade >= 60:
            risco.append("idade acima de 60 anos")
        if idade < 2:
            risco.append("criança pequena")
        if cidadao.get("gestante"):
            risco.append("gestação")
        risco += [r for c, r in (("diabetes", "diabetes"), ("hipertensao", "hipertensão"), ("renal_cronico", "doença renal")) if c in comorb]
        texto = f"Seu bairro ({analise['bairro']}) está com risco {niveis['dengue']} para dengue."
        if risco:
            texto += f" Por {', '.join(risco)}, a dengue pode ser mais grave para você: com febre, procure atendimento no mesmo dia."
        alertas.append({"tipo": "dengue", "nivel": "alto" if risco else niveis["dengue"], "texto": texto})

    if niveis["ar"] != "baixo" and (comorb & {"pneumopatia", "cardiopatia"} or idade < 5 or idade >= 65):
        alertas.append({"tipo": "ar", "nivel": niveis["ar"],
                        "texto": "A qualidade do ar está prejudicada e você é mais sensível (doença respiratória/cardíaca ou idade). "
                                 "Tenha a medicação de uso contínuo à mão e procure atendimento se houver falta de ar."})

    if niveis["alagamento"] != "baixo":
        alertas.append({"tipo": "alagamento", "nivel": niveis["alagamento"],
                        "texto": "Chuvas recentes com risco de alagamento perto de sua casa: atenção para leptospirose."})

    if niveis["escorpiao"] != "baixo" and (idade < 10 or idade >= 65):
        alertas.append({"tipo": "escorpiao", "nivel": "moderado",
                        "texto": "Aumento de escorpiões no bairro. Em criança ou idoso, picada exige ir à UPA imediatamente."})

    return sorted(alertas, key=lambda a: -_ORDEM[a["nivel"]])


_DENGUE = {"dor_corpo", "dor_cabeca", "dor_atras_olhos", "manchas_pele"}
_RESPIRATORIO = {"tosse", "falta_ar", "coriza", "dor_garganta"}


def contexto_triagem(sintomas: set[str], analise: dict) -> tuple[list[str], bool]:
    """Observações do ambiente relevantes para os sintomas relatados.

    Devolve as observações e se o quadro é compatível com dengue num bairro de risco.
    O contexto ambiental orienta, mas não altera a classificação de risco clínica.
    """
    niveis = {i["tipo"]: i for i in analise["indicadores"]}
    obs: list[str] = []
    suspeita_dengue = False
    if "febre" in sintomas and sintomas & _DENGUE and niveis["dengue"]["nivel"] != "baixo":
        suspeita_dengue = True
        obs.append(f"Bairro {analise['bairro']} com {niveis['dengue']['valor']}: febre com dor no corpo/cabeça "
                   "sugere dengue. Hidrate-se e evite anti-inflamatórios (ibuprofeno, AAS, diclofenaco).")
    if sintomas & _RESPIRATORIO and niveis["ar"]["nivel"] != "baixo":
        obs.append(f"Qualidade do ar no bairro: {niveis['ar']['valor']}. A fumaça e o tempo seco pioram sintomas respiratórios.")
    if "febre" in sintomas and niveis["alagamento"]["nivel"] != "baixo":
        obs.append("Houve risco de alagamento no bairro: se teve contato com água de enchente, informe na consulta (leptospirose).")
    return obs, suspeita_dengue
