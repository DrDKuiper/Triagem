"""Catálogo de sintomas e extração por palavras-chave (pt-BR)."""

from __future__ import annotations

import re
import unicodedata

# código -> (rótulo exibido, palavras-chave sem acento)
SINTOMAS: dict[str, tuple[str, list[str]]] = {
    "febre": ("Febre", ["febre", "febril", "temperatura alta", "quente"]),
    "tosse": ("Tosse", ["tosse", "tossindo", "catarro", "pigarro"]),
    "coriza": ("Coriza / nariz entupido", ["coriza", "nariz escorrendo", "nariz entupido", "espirro", "resfriado"]),
    "dor_garganta": ("Dor de garganta", ["garganta", "engolir doi", "amigdala"]),
    "dor_corpo": ("Dor no corpo", ["dor no corpo", "corpo doendo", "mialgia", "moleza"]),
    "dor_cabeca": ("Dor de cabeça", ["dor de cabeca", "cefaleia", "enxaqueca"]),
    "dor_atras_olhos": ("Dor atrás dos olhos", ["atras dos olhos", "dor retro", "retroorbital"]),
    "manchas_pele": ("Manchas vermelhas na pele", ["manchas", "manchinha", "exantema", "pintas vermelhas", "brotoeja"]),
    "diarreia": ("Diarreia", ["diarreia", "evacuando muito", "intestino solto", "fezes liquidas"]),
    "vomito": ("Vômitos", ["vomito", "vomitando", "enjoo", "nausea", "ansia"]),
    "dor_abdominal": ("Dor abdominal", ["dor de barriga", "dor abdominal", "colica", "dor na barriga", "estomago"]),
    "falta_ar": ("Falta de ar", ["falta de ar", "dificuldade para respirar", "sem ar", "cansaco para respirar", "dispneia", "chiado"]),
    "dor_peito": ("Dor no peito", ["dor no peito", "aperto no peito", "dor toracica", "peito doendo"]),
    "desmaio": ("Desmaio / perda de consciência", ["desmaio", "desmaiou", "desacordado", "inconsciente", "apagou"]),
    "confusao": ("Confusão mental", ["confuso", "confusao", "desorientado", "nao fala coisa com coisa"]),
    "convulsao": ("Convulsão", ["convulsao", "convulsionando", "ataque epiletico", "crise convulsiva", "tremedeira forte"]),
    "fraqueza_lado": ("Fraqueza/dormência de um lado do corpo", ["boca torta", "dormencia de um lado", "fraqueza de um lado", "nao mexe o braco", "fala enrolada"]),
    "sangramento": ("Sangramento", ["sangramento", "sangrando", "sangue", "hemorragia", "gengiva sangra"]),
    "trauma": ("Trauma / acidente / queda", ["queda", "caiu", "acidente", "batida", "fratura", "pancada", "corte profundo"]),
    "queimadura": ("Queimadura", ["queimadura", "queimou", "queimei"]),
    "dor_urinar": ("Dor ao urinar", ["dor ao urinar", "ardencia para urinar", "ardor ao urinar", "xixi doi"]),
    "dor_ouvido": ("Dor de ouvido", ["dor de ouvido", "ouvido doendo", "otite"]),
    "lesao_pele": ("Lesão/ferida na pele", ["ferida", "machucado", "picada", "alergia na pele", "coceira"]),
    "pressao_alta": ("Pressão alta", ["pressao alta", "hipertensao", "pressao subiu"]),
    "glicemia_alterada": ("Glicemia alterada", ["glicemia", "acucar alto", "hipoglicemia", "diabetes descompensada"]),
    "renovar_receita": ("Renovação de receita / atestado", ["receita", "renovar", "atestado", "exame de rotina", "consulta de rotina"]),
}

SINAIS_ALARME = {"dor_peito", "falta_ar", "desmaio", "confusao", "convulsao", "fraqueza_lado", "sangramento"}

COMORBIDADES: dict[str, str] = {
    "diabetes": "Diabetes",
    "hipertensao": "Hipertensão",
    "cardiopatia": "Doença cardíaca",
    "pneumopatia": "Asma/DPOC/doença pulmonar",
    "imunossupressao": "Imunossupressão (câncer, HIV, transplante)",
    "renal_cronico": "Doença renal crônica",
}

_NEGACAO = re.compile(r"\b(sem|nao|nega|nenhum|nenhuma)\b")


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip()


def extrair_sintomas(texto: str) -> set[str]:
    """Identifica sintomas do catálogo em um relato livre.

    Uma ocorrência é descartada se, na mesma oração, vier logo após uma negação
    ("sem febre", "não tenho falta de ar").
    """
    encontrados: set[str] = set()
    for oracao in re.split(r"[.,;!?\n]| e ", normalizar(texto)):
        for codigo, (_, palavras) in SINTOMAS.items():
            for palavra in palavras:
                pos = oracao.find(palavra)
                if pos < 0:
                    continue
                antes = oracao[max(0, pos - 15):pos]
                if not _NEGACAO.search(antes):
                    encontrados.add(codigo)
                break
    return encontrados
