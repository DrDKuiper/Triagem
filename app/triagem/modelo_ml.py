"""Modelos de ML da triagem.

Dois classificadores:
  * gravidade: estima a prioridade (azul..vermelho) a partir de sintomas,
    sinais vitais e perfil do paciente;
  * agravo: sugere o agravo mais provável (síndrome gripal, dengue, ...),
    usado para alimentar a vigilância e orientar o paciente.

Sem histórico real disponível, os modelos são inicializados com uma base
sintética gerada a partir de perfis clínicos típicos. Em produção, chame
`ModeloTriagem.treinar(registros)` com triagens já classificadas por
profissionais (exportadas do prontuário) para substituir essa base.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from app.schemas import Prioridade, TriagemEntrada
from app.triagem.sintomas import COMORBIDADES, SINTOMAS

AGRAVOS = {
    "sindrome_gripal": "Síndrome gripal (gripe/COVID-19/resfriado)",
    "dengue": "Suspeita de arbovirose (dengue/chikungunya/zika)",
    "gastroenterite": "Gastroenterite",
    "infeccao_urinaria": "Possível infecção urinária",
    "cardiovascular": "Quadro cardiovascular",
    "neurologico": "Quadro neurológico",
    "trauma": "Trauma / lesão",
    "cronico_rotina": "Acompanhamento de condição crônica / rotina",
    "outros": "Outros",
}

# Sintomas característicos de cada agravo: (sintoma, probabilidade de presença)
_PERFIS: dict[str, list[tuple[str, float]]] = {
    "sindrome_gripal": [("febre", .8), ("tosse", .85), ("coriza", .7), ("dor_garganta", .6), ("dor_corpo", .6), ("dor_cabeca", .5), ("falta_ar", .08)],
    "dengue": [("febre", .95), ("dor_corpo", .85), ("dor_cabeca", .8), ("dor_atras_olhos", .6), ("manchas_pele", .45), ("vomito", .3), ("dor_abdominal", .2), ("sangramento", .05)],
    "gastroenterite": [("diarreia", .9), ("vomito", .7), ("dor_abdominal", .7), ("febre", .35)],
    "infeccao_urinaria": [("dor_urinar", .9), ("dor_abdominal", .4), ("febre", .25)],
    "cardiovascular": [("dor_peito", .8), ("falta_ar", .5), ("pressao_alta", .4), ("desmaio", .1)],
    "neurologico": [("dor_cabeca", .6), ("fraqueza_lado", .4), ("confusao", .3), ("convulsao", .2), ("desmaio", .15)],
    "trauma": [("trauma", .9), ("sangramento", .2), ("queimadura", .1), ("lesao_pele", .3)],
    "cronico_rotina": [("renovar_receita", .8), ("pressao_alta", .3), ("glicemia_alterada", .25)],
    "outros": [("dor_ouvido", .3), ("lesao_pele", .4), ("dor_garganta", .2), ("dor_cabeca", .2)],
}
_FREQ_AGRAVO = [.30, .12, .12, .07, .06, .04, .09, .12, .08]

_COLUNAS_SINTOMAS = list(SINTOMAS)
_COLUNAS = (
    ["idade", "gestante", "n_comorbidades", "dias", "dor", "temp", "spo2", "fc", "pas", "glic"]
    + [f"s_{s}" for s in _COLUNAS_SINTOMAS]
)


def vetorizar(entrada: TriagemEntrada, sintomas: set[str]) -> dict[str, float]:
    sv = entrada.sinais_vitais
    temp = sv.temperatura if sv.temperatura is not None else (38.0 if "febre" in sintomas else 36.5)
    linha = {
        "idade": entrada.idade,
        "gestante": int(entrada.gestante),
        "n_comorbidades": len(set(entrada.comorbidades) & set(COMORBIDADES)),
        "dias": entrada.dias_sintomas,
        "dor": entrada.intensidade_dor,
        "temp": temp,
        "spo2": sv.saturacao if sv.saturacao is not None else 97,
        "fc": sv.frequencia_cardiaca if sv.frequencia_cardiaca is not None else 85,
        "pas": sv.pressao_sistolica if sv.pressao_sistolica is not None else 120,
        "glic": sv.glicemia if sv.glicemia is not None else 100,
    }
    for s in _COLUNAS_SINTOMAS:
        linha[f"s_{s}"] = int(s in sintomas)
    return linha


def _rotulo_gravidade(l: dict, rng: np.random.Generator) -> int:
    """Rótulo de referência usado para a base sintética (aproxima um triador humano)."""
    risco = 0.0
    risco += 3.0 * (l["s_convulsao"] or l["s_fraqueza_lado"] or l["s_desmaio"] or l["s_confusao"])
    risco += 2.2 * l["s_dor_peito"] + 1.8 * l["s_falta_ar"] + 1.5 * l["s_sangramento"]
    risco += 1.0 * (l["s_trauma"] or l["s_queimadura"])
    risco += 0.25 * max(0, l["dor"] - 3)
    risco += 0.9 * max(0, l["temp"] - 38.0)
    risco += 0.35 * max(0, 95 - l["spo2"])
    risco += 0.04 * max(0, l["fc"] - 100)
    risco += 0.5 * (l["idade"] >= 65 or l["idade"] < 2) + 0.3 * l["n_comorbidades"] + 0.4 * l["gestante"]
    risco += 0.6 * (l["s_febre"] and l["s_manchas_pele"])
    risco += 0.1 * min(l["dias"], 10) * l["s_febre"]
    risco -= 0.8 * l["s_renovar_receita"]
    risco += rng.normal(0, 0.35)
    if risco >= 4.2:
        return Prioridade.VERMELHO
    if risco >= 2.4:
        return Prioridade.LARANJA
    if risco >= 1.3:
        return Prioridade.AMARELO
    if risco >= 0.3:
        return Prioridade.VERDE
    return Prioridade.AZUL


def gerar_base_sintetica(n: int = 6000, semente: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(semente)
    agravos = list(AGRAVOS)
    linhas = []
    for _ in range(n):
        agravo = rng.choice(agravos, p=_FREQ_AGRAVO)
        sintomas = {s for s, p in _PERFIS[agravo] if rng.random() < p}
        if rng.random() < 0.1:  # ruído: sintoma inespecífico
            sintomas.add(rng.choice(_COLUNAS_SINTOMAS))
        idade = int(np.clip(rng.gamma(2.2, 17), 0, 100))
        if agravo == "cronico_rotina":
            idade = int(np.clip(rng.normal(58, 14), 18, 95))
        febre = "febre" in sintomas
        temp = rng.normal(38.6 if agravo == "dengue" else 38.2, 0.5) if febre else rng.normal(36.6, 0.3)
        spo2 = rng.normal(97, 1.2)
        if "falta_ar" in sintomas:
            spo2 -= abs(rng.normal(4, 3))
        entrada_sintetica = {
            "idade": idade,
            "gestante": int(rng.random() < 0.04 and 15 <= idade <= 45),
            "n_comorbidades": int(rng.poisson(0.2 + idade / 80)),
            "dias": int(rng.integers(0, 10)),
            "dor": int(np.clip(rng.normal(6 if agravo in {"trauma", "cardiovascular", "dengue"} else 3, 2), 0, 10)),
            "temp": float(np.clip(temp, 35, 42)),
            "spo2": float(np.clip(spo2, 75, 100)),
            "fc": float(np.clip(rng.normal(85 + (temp - 37) * 10, 12), 40, 190)),
            "pas": float(np.clip(rng.normal(125 + 15 * ("pressao_alta" in sintomas) * 3, 15), 70, 230)),
            "glic": float(np.clip(rng.normal(105 + 120 * ("glicemia_alterada" in sintomas), 25), 40, 600)),
        }
        for s in _COLUNAS_SINTOMAS:
            entrada_sintetica[f"s_{s}"] = int(s in sintomas)
        entrada_sintetica["gravidade"] = int(_rotulo_gravidade(entrada_sintetica, rng))
        entrada_sintetica["agravo"] = agravo
        linhas.append(entrada_sintetica)
    return pd.DataFrame(linhas)


@dataclass
class PredicaoML:
    probabilidades: dict[str, float]
    prioridade: Prioridade
    agravo: str
    agravo_prob: float


class ModeloTriagem:
    def __init__(self, semente: int = 42):
        self.semente = semente
        self.clf_gravidade = RandomForestClassifier(n_estimators=200, min_samples_leaf=3, class_weight="balanced", random_state=semente, n_jobs=-1)
        self.clf_agravo = RandomForestClassifier(n_estimators=200, min_samples_leaf=2, random_state=semente, n_jobs=-1)
        self.acuracia: dict[str, float] = {}

    def treinar(self, base: pd.DataFrame) -> "ModeloTriagem":
        """Treina com um DataFrame contendo as colunas de `_COLUNAS` + `gravidade` e `agravo`."""
        corte = int(len(base) * 0.8)
        treino, teste = base.iloc[:corte], base.iloc[corte:]
        self.clf_gravidade.fit(treino[_COLUNAS], treino["gravidade"])
        self.clf_agravo.fit(treino[_COLUNAS], treino["agravo"])
        if len(teste):
            self.acuracia = {
                "gravidade": float(self.clf_gravidade.score(teste[_COLUNAS], teste["gravidade"])),
                "agravo": float(self.clf_agravo.score(teste[_COLUNAS], teste["agravo"])),
            }
        # refit com tudo após medir
        self.clf_gravidade.fit(base[_COLUNAS], base["gravidade"])
        self.clf_agravo.fit(base[_COLUNAS], base["agravo"])
        return self

    def prever(self, entrada: TriagemEntrada, sintomas: set[str]) -> PredicaoML:
        x = pd.DataFrame([vetorizar(entrada, sintomas)])[_COLUNAS]
        probs_g = self.clf_gravidade.predict_proba(x)[0]
        probabilidades = {Prioridade(int(c)).cor: round(float(p), 3) for c, p in zip(self.clf_gravidade.classes_, probs_g)}
        # Escolhe o nível mais grave cuja probabilidade acumulada (do mais grave para baixo)
        # atinge 35%: viés conservador, prefere superestimar a subestimar o risco.
        acumulado, prioridade = 0.0, Prioridade.AZUL
        for c, p in sorted(zip(self.clf_gravidade.classes_, probs_g), key=lambda t: -t[0]):
            acumulado += p
            if acumulado >= 0.35:
                prioridade = Prioridade(int(c))
                break
        probs_a = self.clf_agravo.predict_proba(x)[0]
        i = int(np.argmax(probs_a))
        return PredicaoML(probabilidades, prioridade, str(self.clf_agravo.classes_[i]), float(probs_a[i]))


_modelo: ModeloTriagem | None = None


def obter_modelo(semente: int = 42) -> ModeloTriagem:
    global _modelo
    if _modelo is None:
        _modelo = ModeloTriagem(semente).treinar(gerar_base_sintetica(semente=semente))
    return _modelo
