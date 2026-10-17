"""Análise preditiva de agravos (gripe, COVID-19, dengue, ...).

Para cada agravo é treinado um modelo de gradient boosting sobre a série
semanal de casos, com variáveis de defasagem (lags), sazonalidade e clima.
Três regressões quantílicas (10%, 50%, 90%) dão a previsão central e a faixa
de incerteza. A previsão para várias semanas é recursiva.

O nível de alerta segue o diagrama de controle (canal endêmico) usado pela
vigilância epidemiológica: quartis históricos da mesma semana epidemiológica
dos anos anteriores.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

from app.preditivo.dados import AGRAVOS_VIGILANCIA

QUANTIS = (0.1, 0.5, 0.9)
LAGS = (1, 2, 3, 4)
CLIMA = ("temperatura", "umidade", "chuva_mm")
NIVEIS = ("baixo", "esperado", "alerta", "epidemia")


def _semana_ano(datas: pd.Series) -> np.ndarray:
    return pd.to_datetime(datas).dt.isocalendar().week.to_numpy().astype(int)


def _climatologia(hist: pd.DataFrame) -> pd.DataFrame:
    sa = _semana_ano(hist["semana"])
    cols = [c for c in CLIMA if c in hist]
    if not cols:
        return pd.DataFrame(index=range(1, 54))
    return hist[cols].groupby(sa).mean().reindex(range(1, 54)).interpolate(limit_direction="both")


def _features(y: np.ndarray, t: int, semana_ano: int, clima: dict[str, float]) -> list[float]:
    lags = [np.log1p(y[t - l]) for l in LAGS]
    lag52 = np.log1p(y[t - 52]) if t >= 52 else lags[0]
    ang = 2 * np.pi * semana_ano / 52
    return [*lags, lag52, float(np.mean(lags)), lags[0] - lags[1], np.sin(ang), np.cos(ang),
            clima.get("temperatura", 0.0), clima.get("umidade", 0.0), clima.get("chuva_mm", 0.0)]


@dataclass
class ModeloAgravo:
    agravo: str
    modelos: dict[float, GradientBoostingRegressor] = field(default_factory=dict)
    erro_backtest: float | None = None  # WAPE (%) nas últimas semanas


def _matriz(y: np.ndarray, sa: np.ndarray, clima_df: pd.DataFrame, inicio: int, fim: int):
    X, alvo = [], []
    for t in range(inicio, fim):
        clima = clima_df.iloc[t - 3].to_dict() if len(clima_df.columns) else {}  # clima com defasagem de 3 semanas
        X.append(_features(y, t, sa[t], clima))
        alvo.append(np.log1p(y[t]))
    return np.array(X), np.array(alvo)


def _novo_gbr(q: float, semente: int) -> GradientBoostingRegressor:
    return GradientBoostingRegressor(loss="quantile", alpha=q, n_estimators=250, max_depth=3,
                                     learning_rate=0.05, subsample=0.8, random_state=semente)


class PreditorEpidemiologico:
    def __init__(self, semente: int = 42, semanas_backtest: int = 26):
        self.semente = semente
        self.semanas_backtest = semanas_backtest
        self.modelos: dict[str, ModeloAgravo] = {}
        self.hist: pd.DataFrame | None = None
        self.treinado_em: float | None = None

    def treinar(self, hist: pd.DataFrame) -> "PreditorEpidemiologico":
        hist = hist.sort_values("semana").reset_index(drop=True)
        self.hist = hist
        self.clim = _climatologia(hist)
        sa = _semana_ano(hist["semana"])
        clima_df = hist[[c for c in CLIMA if c in hist]] if any(c in hist for c in CLIMA) else pd.DataFrame(index=hist.index)
        inicio = max(LAGS) + 3
        for agravo in AGRAVOS_VIGILANCIA:
            if agravo not in hist:
                continue
            y = hist[agravo].to_numpy(dtype=float)
            m = ModeloAgravo(agravo)
            corte = len(y) - self.semanas_backtest
            if corte - inicio > 52:
                Xtr, ytr = _matriz(y, sa, clima_df, inicio, corte)
                Xte, yte = _matriz(y, sa, clima_df, corte, len(y))
                med = _novo_gbr(0.5, self.semente).fit(Xtr, ytr)
                prev = np.expm1(med.predict(Xte))
                real = np.expm1(yte)
                m.erro_backtest = float(np.abs(prev - real).sum() / max(real.sum(), 1) * 100)
            X, alvo = _matriz(y, sa, clima_df, inicio, len(y))
            m.modelos = {q: _novo_gbr(q, self.semente).fit(X, alvo) for q in QUANTIS}
            self.modelos[agravo] = m
        self.treinado_em = time.time()
        return self

    def canal_endemico(self, agravo: str) -> pd.DataFrame:
        """Canal endêmico por semana epidemiológica, com anos anteriores ao último.

        Agrupa cada semana com as duas vizinhas de cada lado para estabilizar os
        quartis. O limite superior (média + 1,96 desvio-padrão, método de Cullen)
        separa "alerta" de "epidemia".
        """
        assert self.hist is not None
        h = self.hist.iloc[:-52] if len(self.hist) > 104 else self.hist
        sa = _semana_ano(h["semana"])
        valores = h[agravo].to_numpy(dtype=float)
        linhas = {}
        for semana in range(1, 54):
            dist = np.minimum(np.abs(sa - semana), 52 - np.abs(sa - semana))
            v = valores[dist <= 2]
            linhas[semana] = {
                "q1": np.quantile(v, 0.25),
                "mediana": np.median(v),
                "q3": np.quantile(v, 0.75),
                "limite_superior": v.mean() + 1.96 * v.std(),
            }
        return pd.DataFrame.from_dict(linhas, orient="index")

    @staticmethod
    def classificar(valor: float, canal: pd.Series) -> str:
        if valor <= canal["mediana"]:
            return "baixo"
        if valor <= canal["q3"]:
            return "esperado"
        if valor <= canal["limite_superior"]:
            return "alerta"
        return "epidemia"

    def prever(self, agravo: str, horizonte: int = 8) -> dict:
        assert self.hist is not None
        m = self.modelos[agravo]
        hist = self.hist
        y = list(hist[agravo].to_numpy(dtype=float))
        clima_hist = [hist.iloc[i][[c for c in CLIMA if c in hist]].to_dict() for i in range(len(hist))]
        ultima = pd.Timestamp(hist["semana"].iloc[-1])
        canal = self.canal_endemico(agravo)
        previsoes = []
        for passo in range(1, horizonte + 1):
            data = ultima + pd.Timedelta(weeks=passo)
            sa = int(data.isocalendar().week)
            t = len(y)
            # clima defasado: observado se existir, senão climatologia da semana
            idx = t - 3
            clima = clima_hist[idx] if idx < len(clima_hist) else self.clim.loc[min(int((data - pd.Timedelta(weeks=3)).isocalendar().week), 53)].to_dict()
            x = np.array([_features(np.array(y), t, sa, clima)])
            q = {qq: float(np.expm1(mod.predict(x)[0])) for qq, mod in m.modelos.items()}
            lo, mid, hi = sorted(max(0.0, q[k]) for k in QUANTIS)
            y.append(mid)
            previsoes.append({
                "semana": data.date().isoformat(),
                "semana_epidemiologica": sa,
                "previsto": round(mid),
                "minimo": round(lo),
                "maximo": round(hi),
                "nivel": self.classificar(mid, canal.loc[sa]),
                "canal": {k: round(float(v)) for k, v in canal.loc[sa].items()},
            })
        observado = [
            {"semana": pd.Timestamp(r.semana).date().isoformat(), "casos": int(getattr(r, agravo)),
             "canal": {k: round(float(v)) for k, v in canal.loc[int(pd.Timestamp(r.semana).isocalendar().week)].items()}}
            for r in hist.tail(52).itertuples()
        ]
        atual = observado[-1]["casos"]
        pico = max(previsoes, key=lambda p: p["previsto"])
        return {
            "agravo": agravo,
            "nome": AGRAVOS_VIGILANCIA[agravo],
            "observado": observado,
            "previsao": previsoes,
            "tendencia_pct": round((previsoes[min(3, horizonte - 1)]["previsto"] - atual) / max(atual, 1) * 100, 1),
            "nivel_atual": self.classificar(atual, canal.loc[int(ultima.isocalendar().week)]),
            "pico_previsto": {"semana": pico["semana"], "casos": pico["previsto"]},
            "erro_backtest_pct": None if m.erro_backtest is None else round(m.erro_backtest, 1),
        }

    def resumo(self, horizonte: int = 8) -> dict:
        agravos = [self.prever(a, horizonte) for a in self.modelos]
        prioridade = {n: i for i, n in enumerate(NIVEIS)}
        alertas = [
            {"agravo": a["agravo"], "nome": a["nome"], "nivel": max((p["nivel"] for p in a["previsao"]), key=prioridade.get),
             "tendencia_pct": a["tendencia_pct"], "pico_previsto": a["pico_previsto"]}
            for a in agravos
        ]
        alertas = [x for x in alertas if x["nivel"] in ("alerta", "epidemia")]
        return {"horizonte_semanas": horizonte, "agravos": agravos, "alertas": alertas}


_cache: dict[str, PreditorEpidemiologico] = {}
_VALIDADE_S = 6 * 3600


def obter_preditor(historico: Callable[[], pd.DataFrame], semente: int = 42) -> PreditorEpidemiologico:
    """Retreina a cada 6 horas com o histórico mais recente do prontuário."""
    p = _cache.get("p")
    if p is None or p.treinado_em is None or time.time() - p.treinado_em > _VALIDADE_S:
        p = PreditorEpidemiologico(semente).treinar(historico())
        _cache["p"] = p
    return p
