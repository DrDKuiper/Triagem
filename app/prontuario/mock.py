"""Prontuário simulado para demonstração e testes."""

from __future__ import annotations

import hashlib
import threading
import uuid
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from app.preditivo.dados import gerar_historico
from app.prontuario.base import Ocupacao, ProntuarioAdapter
from app.unidades.catalogo import POR_ID

# Fluxo relativo por hora do dia (0h..23h): picos no fim da manhã e início da noite.
_CURVA_HORARIA = [0.35, 0.3, 0.25, 0.2, 0.2, 0.25, 0.45, 0.7, 0.9, 1.0, 1.0, 0.95,
                  0.85, 0.85, 0.9, 0.9, 0.95, 1.0, 1.05, 1.0, 0.9, 0.75, 0.6, 0.45]


class MockProntuario(ProntuarioAdapter):
    nome = "simulado"

    def __init__(self, semente: int = 42, populacao: int = 70_000):
        self.semente = semente
        self._triagens: list[dict] = []
        self._lock = threading.Lock()
        self._historico = gerar_historico(semente=semente, populacao=populacao)

    def _rng(self, unidade_id: str, agora: datetime) -> np.random.Generator:
        # Muda a cada 2 minutos: valores estáveis entre atualizações próximas.
        chave = f"{self.semente}:{unidade_id}:{agora:%Y%m%d%H}:{agora.minute // 2}"
        return np.random.default_rng(int(hashlib.sha256(chave.encode()).hexdigest()[:12], 16))

    def ocupacao(self, unidade_ids: list[str]) -> dict[str, Ocupacao]:
        agora = datetime.now()
        resultado = {}
        for uid in unidade_ids:
            u = POR_ID.get(uid)
            if u is None:
                continue
            fator = _CURVA_HORARIA[agora.hour]
            if not u.aberta(agora):
                resultado[uid] = Ocupacao(unidade_id=uid, em_atendimento=0, aguardando=0, atualizado_em=agora)
                continue
            rng = self._rng(uid, agora)
            capacidade = u.profissionais_plantao * (4 if u.tipo != "UBS" else 2)
            em_atendimento = int(min(capacidade, rng.poisson(capacidade * 0.8 * fator) + 1))
            aguardando = int(rng.poisson(u.profissionais_plantao * (3.5 if u.tipo == "UPA" else 2) * fator))
            with self._lock:
                limite = agora - timedelta(hours=2)
                aguardando += sum(1 for t in self._triagens if t.get("unidade_id") == uid and t["recebida_em"] > limite)
            cores = rng.multinomial(aguardando, [0.02, 0.12, 0.33, 0.43, 0.10]) if aguardando else [0] * 5
            resultado[uid] = Ocupacao(
                unidade_id=uid,
                em_atendimento=em_atendimento,
                aguardando=aguardando,
                aguardando_por_cor=dict(zip(["vermelho", "laranja", "amarelo", "verde", "azul"], map(int, cores))),
                atualizado_em=agora,
            )
        return resultado

    def registrar_triagem(self, triagem: dict) -> str | None:
        identificador = str(uuid.uuid4())
        with self._lock:
            self._triagens.append({**triagem, "id_prontuario": identificador, "recebida_em": datetime.now()})
            del self._triagens[:-500]
        return identificador

    def historico_semanal(self, semanas: int) -> pd.DataFrame:
        return self._historico.tail(semanas).reset_index(drop=True)

