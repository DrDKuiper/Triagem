from __future__ import annotations

from functools import lru_cache

from app.cidadao.ambiente import alertas_pessoais, analisar_bairro
from app.cidadao.bairros import BAIRROS
from app.cidadao.cadastro import CadastroCidadao, CadastroFicticio
from app.config import config
from app.prontuario import obter_prontuario
from app.triagem.acessibilidade import acompanhante, prioridade_legal


@lru_cache(maxsize=1)
def obter_cadastro() -> CadastroCidadao:
    # Integração real com o sistema do Cartão Cidadão: implemente CadastroCidadao e selecione aqui.
    return CadastroFicticio(config.semente)


def consultar(cartao: str) -> dict | None:
    """Cidadão + análise ambiental do bairro onde mora + alertas personalizados."""
    cidadao = obter_cadastro().buscar(cartao)
    if cidadao is None:
        return None
    bairro = BAIRROS.get(cidadao["endereco"]["bairro"])
    ambiente = analisar_bairro(bairro, obter_prontuario().historico_semanal(260)) if bairro else None
    necessidades = set(cidadao["necessidades"])
    return {
        "cidadao": cidadao,
        "ambiente": ambiente,
        "alertas": alertas_pessoais(cidadao, ambiente) if ambiente else [],
        "acompanhante": acompanhante(cidadao["idade"], necessidades, cidadao["gestante"]),
        "prioridade_legal": prioridade_legal(cidadao["idade"], necessidades, cidadao["gestante"]),
    }


__all__ = ["CadastroCidadao", "consultar", "obter_cadastro"]
