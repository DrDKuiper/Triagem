"""Extração de sintomas de relato livre usando a API do Claude (opcional).

Ativada com TRIAGEM_USAR_LLM=1 e credenciais da Anthropic (ANTHROPIC_API_KEY).
O LLM apenas *estrutura* o relato em códigos do catálogo; a classificação de
risco continua sendo feita pelas regras clínicas + modelo de ML. Qualquer falha
(sem credencial, erro de rede, recusa) cai de volta para a extração local por
palavras-chave.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

from app.triagem.sintomas import SINTOMAS

log = logging.getLogger(__name__)

CodigoSintoma = Literal[tuple(SINTOMAS)]  # type: ignore[valid-type]


class ExtracaoSintomas(BaseModel):
    sintomas: list[CodigoSintoma] = Field(description="Códigos dos sintomas presentes no relato")  # type: ignore[valid-type]
    dias_sintomas: int | None = Field(None, description="Há quantos dias os sintomas começaram, se informado")
    intensidade_dor: int | None = Field(None, description="Intensidade da dor 0-10, se for possível inferir")


_SISTEMA = (
    "Você auxilia a triagem de uma unidade de saúde. Leia o relato do paciente e devolva apenas os "
    "códigos de sintomas do catálogo que o paciente afirma ter (ignore sintomas negados). "
    "Não faça diagnóstico nem classificação de risco.\n\nCatálogo (código: descrição):\n"
    + "\n".join(f"- {c}: {rotulo}" for c, (rotulo, _) in SINTOMAS.items())
)


def extrair_com_llm(relato: str, modelo: str) -> ExtracaoSintomas | None:
    try:
        import anthropic
    except ImportError:
        log.warning("Pacote 'anthropic' não instalado; usando extração local.")
        return None
    try:
        client = anthropic.Anthropic()
        resposta = client.messages.parse(
            model=modelo,
            max_tokens=1024,
            output_config={"effort": "low"},
            system=_SISTEMA,
            messages=[{"role": "user", "content": relato}],
            output_format=ExtracaoSintomas,
        )
    except anthropic.APIConnectionError as e:
        log.warning("Sem conexão com a API do Claude: %s", e)
        return None
    except anthropic.APIStatusError as e:
        log.warning("Erro da API do Claude (%s): %s", e.status_code, e.message)
        return None
    except anthropic.AnthropicError as e:  # ex.: credencial ausente
        log.warning("Cliente Claude indisponível: %s", e)
        return None
    if resposta.stop_reason == "refusal":
        log.warning("Extração recusada pelo modelo; usando extração local.")
        return None
    return resposta.parsed_output
