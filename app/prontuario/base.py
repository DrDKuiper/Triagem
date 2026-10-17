"""Contrato de integração com o prontuário eletrônico local."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd
from pydantic import BaseModel


class Ocupacao(BaseModel):
    unidade_id: str
    em_atendimento: int        # pacientes sendo atendidos agora
    aguardando: int            # pacientes na fila (já chegaram, ainda não atendidos)
    aguardando_por_cor: dict[str, int] = {}
    atualizado_em: datetime


class ProntuarioAdapter(ABC):
    """Implementações: `MockProntuario` (demonstração) e `FHIRProntuario` (HL7 FHIR R4)."""

    nome: str = "base"

    @abstractmethod
    def ocupacao(self, unidade_ids: list[str]) -> dict[str, Ocupacao]:
        """Situação atual de cada unidade."""

    @abstractmethod
    def registrar_triagem(self, triagem: dict) -> str | None:
        """Envia a pré-triagem ao prontuário; devolve o identificador gerado."""

    @abstractmethod
    def historico_semanal(self, semanas: int) -> pd.DataFrame:
        """Casos semanais por agravo.

        Colunas: `semana` (datetime, início da semana) e uma coluna por agravo,
        mais `temperatura`, `umidade` e `chuva_mm` quando disponíveis.
        """
