"""Orquestra a triagem: extração de sintomas -> regras -> ML -> destino."""

from __future__ import annotations

import uuid

from app import cidadao
from app.cidadao.ambiente import contexto_triagem
from app.config import config
from app.prontuario import ProntuarioAdapter
from app.schemas import Prioridade, TriagemEntrada, TriagemResultado
from app.triagem import regras
from app.triagem.acessibilidade import NECESSIDADES, acompanhante, precisa_ambulancia, prioridade_legal, transporte
from app.triagem.extrator_llm import extrair_com_llm
from app.triagem.modelo_ml import AGRAVOS, obter_modelo
from app.triagem.sintomas import SINAIS_ALARME, SINTOMAS, extrair_sintomas
from app.unidades import servico as unidades

ORIENTACOES = {
    Prioridade.VERMELHO: (
        "Emergência", "SAMU", 0,
        "Ligue 192 (SAMU) agora. Não espere e não vá por conta própria se não for seguro.",
    ),
    Prioridade.LARANJA: (
        "Muito urgente", "UPA", 10,
        "Procure a UPA imediatamente. Se piorar no caminho, ligue 192.",
    ),
    Prioridade.AMARELO: (
        "Urgente", "UPA", 60,
        "Procure a UPA nas próximas horas.",
    ),
    Prioridade.VERDE: (
        "Pouco urgente", "UBS", 120,
        "Seu caso pode ser atendido no posto de saúde (UBS) do seu bairro, evitando a fila da UPA. "
        "Procure a UBS hoje ou amanhã; se ela estiver fechada e os sintomas piorarem, procure a UPA.",
    ),
    Prioridade.AZUL: (
        "Não urgente", "AUTOCUIDADO", 240,
        "Não há sinais de urgência. Agende consulta na sua UBS, use teleconsulta se disponível "
        "ou ligue 136 (Disque Saúde) para orientações.",
    ),
}


def _completar_com_cartao(entrada: TriagemEntrada) -> tuple[TriagemEntrada, dict | None]:
    """Completa a entrada com o cadastro do Cartão Cidadão (doenças, gestação, endereço)."""
    if not entrada.cartao_cidadao:
        return entrada, None
    consulta = cidadao.consultar(entrada.cartao_cidadao)
    if consulta is None:
        return entrada, None
    c = consulta["cidadao"]
    atualizacao = {
        "comorbidades": sorted(set(entrada.comorbidades) | set(c["comorbidades"])),
        "necessidades": sorted(set(entrada.necessidades) | set(c["necessidades"])),
        "necessita_ambulancia": entrada.necessita_ambulancia or c["necessita_ambulancia"],
        "gestante": entrada.gestante or c["gestante"],
        "sexo": entrada.sexo or c["sexo"],
        "cns": entrada.cns or c["cns"],
        "residente": True,
    }
    # Sem localização do aparelho, as unidades são ordenadas a partir da casa do cidadão.
    if entrada.lat is None or entrada.lon is None:
        atualizacao.update(lat=c["endereco"]["lat"], lon=c["endereco"]["lon"])
    return entrada.model_copy(update=atualizacao), consulta


def _sugerir_unidades(
    prontuario: ProntuarioAdapter, entrada: TriagemEntrada, prioridade: Prioridade, destino: str, ubs_bairro: str | None
) -> tuple[list[dict], str]:
    """O hospital nunca é indicado: urgências vão para a UPA; casos leves, para a UBS do bairro.

    Devolve as unidades e um complemento para a orientação.
    """
    upa = unidades.listar(prontuario, entrada.lat, entrada.lon, {"UPA"}, prioridade)
    if destino in {"SAMU", "UPA"}:
        return upa[:1], ""
    ubs = unidades.listar(prontuario, entrada.lat, entrada.lon, {"UBS"}, prioridade)
    if ubs_bairro:
        escolhida = next((u for u in ubs if u["id"] == ubs_bairro), None)
    else:
        # Sem cadastro, a UBS mais próxima de onde a pessoa está (ou do centro).
        ubs.sort(key=lambda u: u.get("distancia_km") or 0)
        escolhida = ubs[0] if ubs else None
    if escolhida is None:
        return upa[:1], ""
    if escolhida.get("funcionando") is False:
        if destino == "AUTOCUIDADO":
            return [escolhida], f" A {escolhida['nome']} está fechada agora; procure-a no próximo horário ({escolhida['horario']})."
        return [escolhida, *upa[:1]], (
            f" A {escolhida['nome']} está fechada agora (horário: {escolhida['horario']}); "
            "se não puder esperar a abertura ou piorar, procure a UPA."
        )
    return [escolhida], ""


def triar(entrada: TriagemEntrada, prontuario: ProntuarioAdapter) -> TriagemResultado:
    entrada, consulta = _completar_com_cartao(entrada)
    sintomas = {s for s in entrada.sintomas if s in SINTOMAS}
    fonte = "formulario"
    if entrada.relato.strip():
        extraidos: set[str] = set()
        if config.usar_llm:
            llm = extrair_com_llm(entrada.relato, config.modelo_llm)
            if llm is not None:
                extraidos = set(llm.sintomas)
                fonte = "llm"
                if llm.dias_sintomas is not None and entrada.dias_sintomas <= 1:
                    entrada = entrada.model_copy(update={"dias_sintomas": min(max(llm.dias_sintomas, 0), 365)})
                if llm.intensidade_dor is not None and entrada.intensidade_dor == 0:
                    entrada = entrada.model_copy(update={"intensidade_dor": min(max(llm.intensidade_dor, 0), 10)})
        if fonte != "llm":
            extraidos = extrair_sintomas(entrada.relato)
            fonte = "palavras-chave" if extraidos else fonte
        sintomas |= extraidos
    if entrada.sinais_vitais.temperatura is not None and entrada.sinais_vitais.temperatura >= 37.8:
        sintomas.add("febre")

    avaliacao = regras.avaliar(entrada, sintomas)
    ml = obter_modelo(config.semente).prever(entrada, sintomas)

    prioridade = max(avaliacao.prioridade, ml.prioridade)
    motivos = list(avaliacao.motivos)
    if ml.prioridade > avaliacao.prioridade:
        motivos.append(f"Modelo de IA indicou risco {ml.prioridade.cor} pela combinação de sintomas e perfil")

    titulo, destino, tempo_alvo, orientacao = ORIENTACOES[prioridade]
    ubs_bairro = consulta["cidadao"]["ubs_referencia"]["id"] if consulta else None
    sugeridas, complemento = _sugerir_unidades(prontuario, entrada, prioridade, destino, ubs_bairro)
    orientacao += complemento
    if not entrada.residente:
        orientacao += (" Você não precisa de Cartão Cidadão: o SUS atende todos. "
                       "Leve documento com foto e cartão do SUS (CNS) ou CPF.")

    necessidades = {n for n in entrada.necessidades if n in NECESSIDADES}
    ambulancia = precisa_ambulancia(necessidades, entrada.necessita_ambulancia)

    agravo_provavel = AGRAVOS[ml.agravo] if ml.agravo_prob >= 0.4 and sintomas else None
    contexto: list[str] = []
    if consulta and consulta["ambiente"]:
        contexto, suspeita_dengue = contexto_triagem(sintomas, consulta["ambiente"])
        if suspeita_dengue and agravo_provavel is None:
            agravo_provavel = AGRAVOS["dengue"]

    resultado = TriagemResultado(
        id=str(uuid.uuid4()),
        prioridade=prioridade.cor,
        nivel=int(prioridade),
        titulo=titulo,
        orientacao=orientacao,
        destino=destino,
        tempo_alvo_min=tempo_alvo,
        sintomas_identificados=sorted(SINTOMAS[s][0] for s in sintomas),
        sinais_alarme=sorted(SINTOMAS[s][0] for s in sintomas & SINAIS_ALARME),
        motivos=motivos,
        probabilidades_ml=ml.probabilidades,
        agravo_provavel=agravo_provavel,
        fonte_extracao=fonte,
        unidades_sugeridas=sugeridas,
        contexto_ambiental=contexto,
        acompanhante=acompanhante(entrada.idade, necessidades, entrada.gestante),
        transporte=transporte(prioridade, destino, necessidades, ambulancia),
        prioridade_legal=prioridade_legal(entrada.idade, necessidades, entrada.gestante),
    )

    if entrada.consentimento_lgpd:
        id_pront = prontuario.registrar_triagem({
            "triagem_id": resultado.id,
            "prioridade": resultado.prioridade,
            "motivos": motivos,
            "sintomas": sorted(sintomas),
            "agravo": ml.agravo,
            "cns": entrada.cns,
            "cartao_cidadao": consulta["cidadao"]["cartao"] if consulta else None,
            "unidade_id": sugeridas[0]["id"] if sugeridas else None,
        })
        resultado.registrado_prontuario = id_pront is not None
    return resultado
