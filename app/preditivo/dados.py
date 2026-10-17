"""Série histórica sintética de casos semanais por agravo + clima.

Reproduz padrões conhecidos do hemisfério sul: síndrome gripal e VSR com pico
no outono/inverno, dengue no verão com defasagem em relação à chuva, e
gastroenterite com leve aumento no calor. Serve para demonstração e testes
enquanto não há histórico do prontuário/SINAN conectado.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

AGRAVOS_VIGILANCIA = {
    "sindrome_gripal": "Síndrome gripal",
    "covid19": "COVID-19",
    "dengue": "Dengue",
    "gastroenterite": "Gastroenterite",
    "vsr_bronquiolite": "VSR / bronquiolite",
}


def _pico(semana_ano: np.ndarray, centro: float, largura: float) -> np.ndarray:
    d = np.minimum(np.abs(semana_ano - centro), 52 - np.abs(semana_ano - centro))
    return np.exp(-(d ** 2) / (2 * largura ** 2))


def gerar_historico(
    semanas: int = 260, fim: pd.Timestamp | None = None, semente: int = 42, populacao: int = 70_000
) -> pd.DataFrame:
    """Casos semanais atendidos na rede municipal; volumes calibrados por 100 mil habitantes."""
    rng = np.random.default_rng(semente)
    fim = (fim or pd.Timestamp.today()).normalize()
    fim = fim - pd.Timedelta(days=fim.weekday())  # segunda-feira
    datas = pd.date_range(end=fim, periods=semanas, freq="W-MON")
    sa = datas.isocalendar().week.to_numpy().astype(float)
    t = np.arange(semanas)
    anos = t / 52

    escala = populacao / 100_000
    # Clima do interior paulista: verão quente e chuvoso, inverno seco.
    temperatura = 22.5 + 4.0 * np.cos(2 * np.pi * (sa - 4) / 52) + rng.normal(0, 1.0, semanas)
    umidade = 68 + 12 * np.cos(2 * np.pi * (sa - 8) / 52) + rng.normal(0, 3, semanas)
    chuva = np.clip(35 + 50 * np.cos(2 * np.pi * (sa - 3) / 52) + rng.gamma(2, 8, semanas) - 16, 0, None)

    # intensidade anual variável (anos epidêmicos)
    intensidade_dengue = np.repeat(rng.lognormal(0, 0.6, semanas // 52 + 2), 52)[:semanas]
    intensidade_gripe = np.repeat(rng.lognormal(0, 0.25, semanas // 52 + 2), 52)[:semanas]

    chuva_lag = pd.Series(chuva).shift(4).bfill().to_numpy()
    base = {
        "sindrome_gripal": (60 + 150 * _pico(sa, 24, 5) * intensidade_gripe) * (1 + 0.03 * anos),
        "covid19": 15 + 30 * _pico(sa, 22, 6) + 20 * _pico(sa, 48, 4),
        # A região de Bauru tem histórico de grandes epidemias de dengue: pico alto e variável.
        "dengue": 4 + 180 * _pico(sa, 13, 4.5) * intensidade_dengue * (chuva_lag / 60),
        "gastroenterite": 35 + 12 * _pico(sa, 6, 8) + 0.8 * (temperatura - 22.5),
        "vsr_bronquiolite": 4 + 30 * _pico(sa, 19, 4),
    }
    base = {k: v * escala for k, v in base.items()}
    dados = {"semana": datas}
    for agravo, media in base.items():
        media = np.clip(media, 1, None)
        # Binomial negativa: sobre-dispersão típica de contagens epidemiológicas
        k = 25
        dados[agravo] = rng.negative_binomial(k, k / (k + media))
    dados.update(temperatura=temperatura.round(1), umidade=umidade.round(1), chuva_mm=chuva.round(1))
    return pd.DataFrame(dados)
