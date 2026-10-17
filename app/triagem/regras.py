"""Regras clínicas determinísticas (discriminadores de risco).

As regras têm precedência sobre o modelo de ML: o resultado final é sempre o
nível mais grave entre as duas fontes, para que um sinal de alarme nunca seja
"suavizado" por uma predição estatística.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas import Prioridade, TriagemEntrada


@dataclass
class AvaliacaoRegras:
    prioridade: Prioridade = Prioridade.AZUL
    motivos: list[str] = field(default_factory=list)

    def elevar(self, nivel: Prioridade, motivo: str) -> None:
        self.motivos.append(motivo)
        if nivel > self.prioridade:
            self.prioridade = nivel


def avaliar(entrada: TriagemEntrada, sintomas: set[str]) -> AvaliacaoRegras:
    r = AvaliacaoRegras()
    sv = entrada.sinais_vitais
    idade = entrada.idade
    vulneravel = idade < 2 or idade >= 65 or entrada.gestante or bool(entrada.comorbidades)

    # --- Emergência (vermelho) ---
    if "convulsao" in sintomas:
        r.elevar(Prioridade.VERMELHO, "Convulsão")
    if "fraqueza_lado" in sintomas:
        r.elevar(Prioridade.VERMELHO, "Sinais de possível AVC (fraqueza/dormência de um lado, fala enrolada)")
    if "desmaio" in sintomas or "confusao" in sintomas:
        r.elevar(Prioridade.VERMELHO, "Alteração do nível de consciência")
    if sv.saturacao is not None and sv.saturacao < 90:
        r.elevar(Prioridade.VERMELHO, f"Saturação muito baixa ({sv.saturacao}%)")
    if sv.pressao_sistolica is not None and sv.pressao_sistolica < 80:
        r.elevar(Prioridade.VERMELHO, f"Pressão muito baixa ({sv.pressao_sistolica} mmHg)")
    if sv.glicemia is not None and sv.glicemia < 54:
        r.elevar(Prioridade.VERMELHO, f"Hipoglicemia grave ({sv.glicemia} mg/dL)")

    # --- Muito urgente (laranja) ---
    if "dor_peito" in sintomas:
        nivel = Prioridade.VERMELHO if idade >= 40 or "falta_ar" in sintomas else Prioridade.LARANJA
        r.elevar(nivel, "Dor no peito")
    if "falta_ar" in sintomas:
        r.elevar(Prioridade.LARANJA, "Falta de ar")
    if "sangramento" in sintomas:
        r.elevar(Prioridade.LARANJA, "Sangramento")
    if sv.saturacao is not None and 90 <= sv.saturacao < 94:
        r.elevar(Prioridade.LARANJA, f"Saturação baixa ({sv.saturacao}%)")
    if sv.temperatura is not None and sv.temperatura >= 39.5 and idade < 1:
        r.elevar(Prioridade.LARANJA, "Febre alta em bebê com menos de 1 ano")
    if sv.frequencia_cardiaca is not None and (sv.frequencia_cardiaca > 130 or sv.frequencia_cardiaca < 45):
        r.elevar(Prioridade.LARANJA, f"Frequência cardíaca alterada ({sv.frequencia_cardiaca} bpm)")
    if sv.pressao_sistolica is not None and sv.pressao_sistolica >= 180:
        r.elevar(Prioridade.LARANJA, f"Pressão muito alta ({sv.pressao_sistolica} mmHg)")
    if sv.glicemia is not None and sv.glicemia >= 400:
        r.elevar(Prioridade.LARANJA, f"Glicemia muito alta ({sv.glicemia} mg/dL)")
    if entrada.intensidade_dor >= 8:
        r.elevar(Prioridade.LARANJA, f"Dor intensa ({entrada.intensidade_dor}/10)")
    if entrada.gestante and ("dor_abdominal" in sintomas or "sangramento" in sintomas):
        r.elevar(Prioridade.LARANJA, "Gestante com dor abdominal ou sangramento")

    # --- Urgente (amarelo) ---
    if "febre" in sintomas and idade < 1:
        r.elevar(Prioridade.AMARELO, "Febre em bebê com menos de 1 ano")
    if "febre" in sintomas and vulneravel:
        r.elevar(Prioridade.AMARELO, "Febre em paciente de grupo de risco")
    if sv.temperatura is not None and sv.temperatura >= 39:
        r.elevar(Prioridade.AMARELO, f"Febre alta ({sv.temperatura:.1f} °C)")
    if "febre" in sintomas and "manchas_pele" in sintomas:
        r.elevar(Prioridade.AMARELO, "Febre com manchas na pele (avaliar dengue/arboviroses)")
    if "vomito" in sintomas and "diarreia" in sintomas and (idade < 5 or idade >= 65):
        r.elevar(Prioridade.AMARELO, "Risco de desidratação (vômitos e diarreia)")
    if "trauma" in sintomas or "queimadura" in sintomas:
        r.elevar(Prioridade.AMARELO, "Trauma ou queimadura")
    if 5 <= entrada.intensidade_dor <= 7:
        r.elevar(Prioridade.AMARELO, f"Dor moderada ({entrada.intensidade_dor}/10)")
    if "febre" in sintomas and entrada.dias_sintomas >= 5:
        r.elevar(Prioridade.AMARELO, "Febre persistente há 5 dias ou mais")

    # --- Pouco urgente (verde) ---
    agudos = sintomas - {"renovar_receita"}
    if agudos and r.prioridade < Prioridade.VERDE:
        r.elevar(Prioridade.VERDE, "Queixa aguda sem sinais de alarme")

    if not r.motivos:
        r.motivos.append("Sem queixa aguda identificada")
    return r
