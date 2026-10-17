from __future__ import annotations

from functools import lru_cache

from app.config import config
from app.prontuario.base import Ocupacao, ProntuarioAdapter


@lru_cache(maxsize=1)
def obter_prontuario() -> ProntuarioAdapter:
    if config.prontuario_backend == "fhir":
        from app.prontuario.fhir import FHIRProntuario

        return FHIRProntuario(config.fhir_base_url, config.fhir_token, config.fhir_timeout)
    from app.prontuario.mock import MockProntuario

    return MockProntuario(config.semente, config.populacao)


__all__ = ["Ocupacao", "ProntuarioAdapter", "obter_prontuario"]
