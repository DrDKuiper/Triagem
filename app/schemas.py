"""Modelos de entrada e saída da API."""

from __future__ import annotations

from enum import IntEnum
from typing import Literal

from pydantic import BaseModel, Field


class Prioridade(IntEnum):
    """Classificação de risco inspirada no Protocolo de Manchester."""

    AZUL = 0       # não urgente
    VERDE = 1      # pouco urgente
    AMARELO = 2    # urgente
    LARANJA = 3    # muito urgente
    VERMELHO = 4   # emergência

    @property
    def cor(self) -> str:
        return self.name.lower()


TipoUnidade = Literal["UPA", "UBS", "PS"]


class SinaisVitais(BaseModel):
    temperatura: float | None = Field(None, ge=30, le=45, description="°C")
    saturacao: int | None = Field(None, ge=50, le=100, description="SpO2 (%)")
    frequencia_cardiaca: int | None = Field(None, ge=20, le=250, description="bpm")
    pressao_sistolica: int | None = Field(None, ge=40, le=300, description="mmHg")
    glicemia: int | None = Field(None, ge=10, le=900, description="mg/dL")


class TriagemEntrada(BaseModel):
    idade: int = Field(..., ge=0, le=120)
    sexo: Literal["F", "M", "O"] | None = None
    gestante: bool = False
    relato: str = Field("", max_length=2000, description="Descrição livre do que está sentindo")
    sintomas: list[str] = Field(default_factory=list, description="Códigos do catálogo de sintomas")
    dias_sintomas: int = Field(1, ge=0, le=365)
    intensidade_dor: int = Field(0, ge=0, le=10)
    comorbidades: list[str] = Field(default_factory=list)
    sinais_vitais: SinaisVitais = Field(default_factory=SinaisVitais)
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    cns: str | None = Field(None, pattern=r"^\d{15}$", description="Cartão Nacional de Saúde (opcional)")
    cartao_cidadao: str | None = Field(
        None, max_length=20, description="Cartão Cidadão do município: completa o perfil e o endereço (opcional)"
    )
    residente: bool = Field(True, description="Mora no município? Visitantes não têm Cartão Cidadão")
    necessidades: list[str] = Field(default_factory=list, description="cadeirante, tea, mobilidade_reduzida...")
    necessita_ambulancia: bool = Field(False, description="Não consegue se deslocar sem ambulância")
    consentimento_lgpd: bool = Field(False, description="Autoriza envio da triagem ao prontuário")


class TriagemResultado(BaseModel):
    id: str
    prioridade: str
    nivel: int
    titulo: str
    orientacao: str
    destino: Literal["SAMU", "UPA", "UBS", "AUTOCUIDADO"]
    tempo_alvo_min: int | None
    sintomas_identificados: list[str]
    sinais_alarme: list[str]
    motivos: list[str]
    probabilidades_ml: dict[str, float]
    agravo_provavel: str | None
    fonte_extracao: Literal["formulario", "palavras-chave", "llm"]
    unidades_sugeridas: list[dict] = Field(default_factory=list)
    contexto_ambiental: list[str] = Field(default_factory=list, description="Observações do bairro do cidadão")
    acompanhante: dict | None = Field(None, description="nivel (obrigatorio/recomendado/direito), titulo, texto")
    transporte: dict | None = Field(None, description="tipo (samu/transporte_sanitario/adaptado) e texto")
    prioridade_legal: list[str] = Field(default_factory=list, description="Direitos de atendimento prioritário")
    registrado_prontuario: bool = False
    aviso: str = (
        "Esta triagem é uma ferramenta de orientação e não substitui avaliação profissional. "
        "Em caso de piora ou dúvida, procure atendimento ou ligue 192 (SAMU)."
    )
