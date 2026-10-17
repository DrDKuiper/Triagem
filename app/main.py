"""API e frontend do app de triagem e monitoramento de filas (UPA/UBS)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import cidadao
from app.config import config
from app.preditivo.dados import AGRAVOS_VIGILANCIA
from app.preditivo.modelo import obter_preditor
from app.prontuario import obter_prontuario
from app.schemas import Prioridade, TriagemEntrada, TriagemResultado
from app.triagem.acessibilidade import NECESSIDADES
from app.triagem.modelo_ml import obter_modelo
from app.triagem.servico import triar
from app.triagem.sintomas import COMORBIDADES, SINTOMAS
from app.unidades import servico as unidades
from app.unidades.catalogo import POR_ID

app = FastAPI(
    title="HealthFlow",
    description="Triagem com IA, situação das filas das unidades de saúde e previsão de agravos.",
    version="1.0.0",
)


def _preditor():
    return obter_preditor(lambda: obter_prontuario().historico_semanal(260), config.semente)


@app.get("/api/saude")
def saude():
    modelo = obter_modelo(config.semente)
    return {
        "status": "ok",
        "municipio": config.municipio,
        "prontuario": obter_prontuario().nome,
        "llm_ativo": config.usar_llm,
        "acuracia_modelo_triagem": modelo.acuracia,
    }


@app.get("/api/config")
def configuracao():
    return {
        "municipio": config.municipio,
        "centro_mapa": {"lat": config.lat_padrao, "lon": config.lon_padrao},
        "sintomas": [{"codigo": c, "rotulo": r} for c, (r, _) in SINTOMAS.items()],
        "comorbidades": [{"codigo": c, "rotulo": r} for c, r in COMORBIDADES.items()],
        "necessidades": [{"codigo": c, "rotulo": r} for c, r in NECESSIDADES.items()],
    }


@app.get("/api/cidadao/exemplos")
def cartoes_de_teste():
    """Cartões da base fictícia, para demonstração."""
    return {"ficticio": True, "cartoes": cidadao.obter_cadastro().exemplos()}


@app.get("/api/cidadao/{cartao}")
def consultar_cidadao(cartao: str):
    """Cadastro do Cartão Cidadão + análise ambiental do bairro + alertas personalizados."""
    consulta = cidadao.consultar(cartao)
    if consulta is None:
        raise HTTPException(404, "Cartão Cidadão não encontrado")
    return consulta


@app.post("/api/triagem", response_model=TriagemResultado)
def nova_triagem(entrada: TriagemEntrada):
    return triar(entrada, obter_prontuario())


@app.get("/api/unidades")
def listar_unidades(
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-180, le=180),
    tipo: list[str] | None = Query(None, description="UPA, UBS e/ou PS"),
    prioridade: str | None = Query(None, description="cor da triagem, ex.: verde"),
):
    p = None
    if prioridade:
        try:
            p = Prioridade[prioridade.upper()]
        except KeyError:
            raise HTTPException(422, f"Prioridade inválida: {prioridade}")
    itens = unidades.listar(obter_prontuario(), lat, lon, set(tipo) if tipo else None, p)
    totais = {
        t: sum(i.get("em_atendimento") or 0 for i in itens if i["tipo"] == t) for t in ("UPA", "UBS", "PS")
    }
    return {"unidades": itens, "em_atendimento_por_tipo": totais}


@app.get("/api/unidades/{unidade_id}")
def detalhe_unidade(unidade_id: str):
    if unidade_id not in POR_ID:
        raise HTTPException(404, "Unidade não encontrada")
    tipo = POR_ID[unidade_id].tipo
    return next(u for u in unidades.listar(obter_prontuario(), tipos={tipo}) if u["id"] == unidade_id)


@app.get("/api/previsoes")
def previsoes(semanas: int = Query(8, ge=1, le=26)):
    return _preditor().resumo(semanas)


@app.get("/api/previsoes/{agravo}")
def previsao_agravo(agravo: str, semanas: int = Query(8, ge=1, le=26)):
    if agravo not in AGRAVOS_VIGILANCIA:
        raise HTTPException(404, "Agravo não monitorado")
    return _preditor().prever(agravo, semanas)


@app.get("/api/dados-uteis")
def dados_uteis():
    return {
        "telefones": [
            {"nome": "SAMU", "numero": "192", "descricao": "Urgências e emergências médicas"},
            {"nome": "Resgate Integrado", "numero": "0800 7100 192", "descricao": "Resgate e SAMU regional"},
            {"nome": "UPA 24h Lençóis Paulista", "numero": "(14) 3269-1300", "descricao": "Rua Sete de Setembro, 600 - Centro"},
            {"nome": "Bombeiros", "numero": "193", "descricao": "Resgate, acidentes, incêndios"},
            {"nome": "Polícia Militar", "numero": "190", "descricao": "Segurança pública"},
            {"nome": "Disque Saúde", "numero": "136", "descricao": "Informações e orientações do SUS"},
            {"nome": "CVV", "numero": "188", "descricao": "Apoio emocional e prevenção do suicídio (24h)"},
            {"nome": "Defesa Civil", "numero": "199", "descricao": "Enchentes, deslizamentos, desastres"},
            {"nome": "Disque Intoxicação (CIATox)", "numero": "0800 722 6001", "descricao": "Envenenamentos e intoxicações"},
        ],
        "quando_procurar": {
            "UBS": "Sintomas leves (resfriado, dor leve), renovação de receitas, vacinas, curativos, acompanhamento de doenças crônicas, pré-natal.",
            "UPA": "Febre alta persistente, dor moderada a intensa, cortes, torções, crises de asma leves, vômitos/diarreia com sinais de desidratação.",
            "SAMU 192": "Dor no peito, falta de ar intensa, desmaio, convulsão, sinais de AVC, sangramento grave, acidentes graves.",
        },
        "documentos": ["Documento com foto", "Cartão do SUS (CNS) ou CPF", "Receitas e exames recentes", "Lista de medicamentos em uso"],
        "dicas": [
            "Na dengue, mantenha hidratação abundante e evite anti-inflamatórios (ibuprofeno, AAS, diclofenaco).",
            "Sinais de alarme na dengue: dor abdominal intensa, vômitos persistentes, sangramentos, tontura ao levantar.",
            "Sintomas gripais leves: repouso, hidratação, máscara para proteger quem convive com você.",
            "Mantenha a caderneta de vacinação em dia (gripe, COVID-19 e calendário infantil).",
        ],
    }


# Versão web do app (as mesmas telas do Android), exibida numa moldura de celular no computador.
WEB_DIR = Path(__file__).parent / "web"
app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB_DIR / "index.html")
