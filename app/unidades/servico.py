"""Situação das unidades, estimativa de espera e recomendação por proximidade."""

from __future__ import annotations

import math

from app.prontuario import ProntuarioAdapter
from app.schemas import Prioridade
from app.unidades.catalogo import UNIDADES, Unidade

ATENDIMENTOS_POR_HORA_PROFISSIONAL = 3.0
VELOCIDADE_URBANA_KMH = 25.0
_ORDEM_CORES = ["vermelho", "laranja", "amarelo", "verde", "azul"]


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _fila_a_frente(por_cor: dict[str, int], aguardando: int, prioridade: Prioridade | None) -> int:
    if prioridade is None or not por_cor:
        return aguardando
    # Atendidos antes: todos com prioridade igual ou maior.
    cores = _ORDEM_CORES[: _ORDEM_CORES.index(prioridade.cor) + 1]
    return sum(por_cor.get(c, 0) for c in cores)


def _lotacao(aguardando: int, unidade: Unidade) -> str:
    razao = aguardando / max(1.0, unidade.profissionais_plantao * ATENDIMENTOS_POR_HORA_PROFISSIONAL)
    if razao < 0.8:
        return "baixa"
    if razao < 1.6:
        return "moderada"
    return "alta"


def listar(
    prontuario: ProntuarioAdapter,
    lat: float | None = None,
    lon: float | None = None,
    tipos: set[str] | None = None,
    prioridade: Prioridade | None = None,
) -> list[dict]:
    unidades = [u for u in UNIDADES if not tipos or u.tipo in tipos]
    ocupacao = prontuario.ocupacao([u.id for u in unidades])
    resultado = []
    for u in unidades:
        oc = ocupacao.get(u.id)
        item = u.model_dump()
        if oc is not None:
            vazao = max(1.0, u.profissionais_plantao * ATENDIMENTOS_POR_HORA_PROFISSIONAL)
            if prioridade is not None and prioridade >= Prioridade.LARANJA:
                espera = 0 if prioridade == Prioridade.VERMELHO else 10
            else:
                espera = round(_fila_a_frente(oc.aguardando_por_cor, oc.aguardando, prioridade) / vazao * 60)
            item.update(
                em_atendimento=oc.em_atendimento,
                aguardando=oc.aguardando,
                aguardando_por_cor=oc.aguardando_por_cor,
                espera_estimada_min=espera,
                lotacao=_lotacao(oc.aguardando, u),
                atualizado_em=oc.atualizado_em.isoformat(timespec="seconds"),
                funcionando=oc.em_atendimento > 0 or u.aberta_24h,
            )
        else:
            item.update(em_atendimento=None, aguardando=None, espera_estimada_min=None, lotacao="indisponível",
                        funcionando=None, atualizado_em=None)
        if lat is not None and lon is not None:
            d = distancia_km(lat, lon, u.lat, u.lon)
            item["distancia_km"] = round(d, 2)
            item["deslocamento_min"] = round(d / VELOCIDADE_URBANA_KMH * 60)
        resultado.append(item)

    def custo(i: dict) -> float:
        if i.get("funcionando") is False:
            return math.inf
        return (i.get("deslocamento_min") or 0) + (i.get("espera_estimada_min") or 0)

    resultado.sort(key=custo)
    return resultado
