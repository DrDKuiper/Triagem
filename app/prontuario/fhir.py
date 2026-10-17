"""Integração com prontuário via HL7 FHIR R4 (padrão adotado pela RNDS).

Mapeamento usado:
  * Unidade de saúde        -> `Location` (id = CNES, ou o id interno da unidade)
  * Pacientes em atendimento -> `Encounter?status=in-progress&location=...`
  * Pacientes aguardando     -> `Encounter?status=arrived,triaged&location=...`
  * Pré-triagem do app       -> `Observation` (category=survey) enviada ao servidor
  * Histórico de agravos     -> `Condition` filtrada por CID-10 e data de registro

Configure com PRONTUARIO_BACKEND=fhir, FHIR_BASE_URL e (opcional) FHIR_TOKEN.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx
import pandas as pd

from app.prontuario.base import Ocupacao, ProntuarioAdapter
from app.unidades.catalogo import POR_ID

log = logging.getLogger(__name__)

SISTEMA_CNS = "http://rnds.saude.gov.br/fhir/r4/NamingSystem/cns"
SISTEMA_CID10 = "http://www.saude.gov.br/fhir/r4/CodeSystem/BRCID10"

# Prefixos CID-10 por agravo monitorado
CID_AGRAVO: dict[str, tuple[str, ...]] = {
    "covid19": ("U07", "B342"),
    "sindrome_gripal": ("J00", "J01", "J02", "J03", "J04", "J05", "J06", "J09", "J10", "J11"),
    "dengue": ("A90", "A91", "A920", "A928"),
    "gastroenterite": ("A0",),
    "vsr_bronquiolite": ("J21", "J121"),
}


def agravo_por_cid(codigo: str) -> str | None:
    c = codigo.replace(".", "").upper()
    for agravo, prefixos in CID_AGRAVO.items():
        if c.startswith(prefixos):
            return agravo
    return None


class FHIRProntuario(ProntuarioAdapter):
    nome = "fhir"

    def __init__(self, base_url: str, token: str = "", timeout: float = 10.0, client: httpx.Client | None = None):
        if not base_url:
            raise ValueError("FHIR_BASE_URL não configurada")
        headers = {"Accept": "application/fhir+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.http = client or httpx.Client(base_url=base_url.rstrip("/"), headers=headers, timeout=timeout)

    @staticmethod
    def _location_id(unidade_id: str) -> str:
        u = POR_ID.get(unidade_id)
        return (u.cnes if u and u.cnes else unidade_id)

    def _contar(self, recurso: str, **params) -> int:
        r = self.http.get(f"/{recurso}", params={**params, "_summary": "count"})
        r.raise_for_status()
        return int(r.json().get("total", 0))

    def ocupacao(self, unidade_ids: list[str]) -> dict[str, Ocupacao]:
        agora = datetime.now()
        resultado = {}
        for uid in unidade_ids:
            loc = f"Location/{self._location_id(uid)}"
            try:
                resultado[uid] = Ocupacao(
                    unidade_id=uid,
                    em_atendimento=self._contar("Encounter", location=loc, status="in-progress"),
                    aguardando=self._contar("Encounter", location=loc, status="arrived,triaged"),
                    atualizado_em=agora,
                )
            except httpx.HTTPError as e:
                log.warning("Falha ao consultar ocupação de %s: %s", uid, e)
        return resultado

    def registrar_triagem(self, triagem: dict) -> str | None:
        obs = {
            "resourceType": "Observation",
            "status": "preliminary",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "survey"}]}],
            "code": {"text": "Pré-triagem digital (classificação de risco)"},
            "effectiveDateTime": datetime.now().astimezone().isoformat(),
            "valueCodeableConcept": {"text": triagem["prioridade"]},
            "note": [{"text": "; ".join(triagem.get("motivos", []))}],
            "component": [
                {"code": {"text": "sintoma"}, "valueString": s} for s in triagem.get("sintomas", [])
            ],
        }
        if triagem.get("cns"):
            obs["subject"] = {"identifier": {"system": SISTEMA_CNS, "value": triagem["cns"]}}
        if triagem.get("unidade_id"):
            obs["performer"] = [{"reference": f"Location/{self._location_id(triagem['unidade_id'])}"}]
        try:
            r = self.http.post("/Observation", json=obs, headers={"Content-Type": "application/fhir+json"})
            r.raise_for_status()
            return r.json().get("id")
        except httpx.HTTPError as e:
            log.warning("Falha ao registrar triagem no prontuário: %s", e)
            return None

    def historico_semanal(self, semanas: int) -> pd.DataFrame:
        inicio = (datetime.now() - timedelta(weeks=semanas)).date().isoformat()
        registros: list[tuple[str, str]] = []
        url: str | None = "/Condition"
        params: dict | None = {"recorded-date": f"ge{inicio}", "_elements": "code,recordedDate", "_count": 1000}
        while url:
            r = self.http.get(url, params=params)
            r.raise_for_status()
            bundle = r.json()
            for entry in bundle.get("entry", []):
                res = entry.get("resource", {})
                data = res.get("recordedDate")
                for coding in res.get("code", {}).get("coding", []):
                    agravo = agravo_por_cid(coding.get("code", ""))
                    if agravo and data:
                        registros.append((data[:10], agravo))
                        break
            url = next((l["url"] for l in bundle.get("link", []) if l.get("relation") == "next"), None)
            params = None  # o link "next" já traz os parâmetros
        df = pd.DataFrame(registros, columns=["data", "agravo"])
        df["semana"] = pd.to_datetime(df["data"]).dt.to_period("W-SUN").dt.start_time
        tabela = df.pivot_table(index="semana", columns="agravo", aggfunc="size", fill_value=0)
        todas = pd.date_range(end=pd.Timestamp.today().normalize(), periods=semanas, freq="W-MON")
        tabela = tabela.reindex(todas, fill_value=0)
        for agravo in CID_AGRAVO:
            if agravo not in tabela:
                tabela[agravo] = 0
        return tabela.rename_axis("semana").reset_index()
