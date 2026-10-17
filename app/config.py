"""Configuração da aplicação, lida de variáveis de ambiente."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool(nome: str, padrao: bool = False) -> bool:
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "sim", "yes", "on"}


@dataclass(frozen=True)
class Config:
    # "mock" usa dados simulados; "fhir" conecta ao prontuário via HL7 FHIR R4.
    prontuario_backend: str = field(default_factory=lambda: os.getenv("PRONTUARIO_BACKEND", "mock"))
    fhir_base_url: str = field(default_factory=lambda: os.getenv("FHIR_BASE_URL", ""))
    fhir_token: str = field(default_factory=lambda: os.getenv("FHIR_TOKEN", ""))
    fhir_timeout: float = field(default_factory=lambda: float(os.getenv("FHIR_TIMEOUT", "10")))

    # Extração de sintomas por texto livre usando a API do Claude (opcional).
    usar_llm: bool = field(default_factory=lambda: _bool("TRIAGEM_USAR_LLM", False))
    modelo_llm: str = field(default_factory=lambda: os.getenv("TRIAGEM_MODELO_LLM", "claude-opus-5-5"))

    # Município atendido e centro padrão do mapa (quando o usuário não compartilha a localização).
    municipio: str = field(default_factory=lambda: os.getenv("MUNICIPIO", "Lençóis Paulista - SP"))
    populacao: int = field(default_factory=lambda: int(os.getenv("POPULACAO", "70000")))
    lat_padrao: float = field(default_factory=lambda: float(os.getenv("MAPA_LAT", "-22.5986")))
    lon_padrao: float = field(default_factory=lambda: float(os.getenv("MAPA_LON", "-48.8003")))

    # Semente usada nos dados simulados e no treino dos modelos (reprodutibilidade).
    semente: int = field(default_factory=lambda: int(os.getenv("SEMENTE", "42")))


config = Config()
