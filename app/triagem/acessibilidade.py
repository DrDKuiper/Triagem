"""Necessidades especiais, acompanhante e transporte até a unidade.

Regras de orientação (não substituem o protocolo da unidade):
- Menores de 18 anos vão com pais ou responsável (ECA).
- Pessoa idosa (60+) tem direito a acompanhante e prioridade (Estatuto da Pessoa Idosa);
  a partir de 80 anos a prioridade é especial e ir acompanhado é recomendado.
- Pessoa com TEA tem atendimento prioritário (Lei 12.764/2012) e deve ir acompanhada.
- Quem precisa de ambulância (acamado ou sem condições de se deslocar) não deve ir por meios próprios.
"""

from __future__ import annotations

from app.schemas import Prioridade

NECESSIDADES: dict[str, str] = {
    "cadeirante": "Cadeirante",
    "mobilidade_reduzida": "Dificuldade motora / anda com apoio",
    "acamado": "Acamado",
    "tea": "Autismo (TEA)",
    "deficiencia_visual": "Deficiência visual",
    "deficiencia_auditiva": "Deficiência auditiva",
    "deficiencia_intelectual": "Deficiência intelectual",
}

_MOTORAS = {"cadeirante", "mobilidade_reduzida", "acamado"}
_PEDE_ACOMPANHANTE = {"tea", "acamado", "deficiencia_intelectual", "deficiencia_visual"}


def precisa_ambulancia(necessidades: set[str], informado: bool) -> bool:
    return informado or "acamado" in necessidades


def acompanhante(idade: int, necessidades: set[str], gestante: bool = False) -> dict | None:
    """Se a pessoa precisa (ou tem direito a) ir acompanhada, e por quê."""
    motivos: list[str] = []
    nivel = None
    if idade < 18:
        nivel = "obrigatorio"
        motivos.append("menores de 18 anos devem ir com pais ou responsável")
    if necessidades & _PEDE_ACOMPANHANTE:
        nivel = nivel or "recomendado"
        rotulos = [NECESSIDADES[n].lower().replace("(tea)", "(TEA)") for n in sorted(necessidades & _PEDE_ACOMPANHANTE)]
        motivos.append(f"pela condição ({', '.join(rotulos)}), vá com alguém de confiança")
    if necessidades & {"cadeirante", "mobilidade_reduzida"}:
        nivel = nivel or "recomendado"
        motivos.append("um acompanhante ajuda no deslocamento e na unidade")
    if idade >= 80:
        nivel = nivel or "recomendado"
        motivos.append("acima de 80 anos é recomendado ir acompanhado (prioridade especial)")
    elif idade >= 60:
        nivel = nivel or "direito"
        motivos.append("pessoa idosa tem direito a acompanhante")
    if gestante and nivel is None:
        nivel = "direito"
        motivos.append("gestante tem direito a acompanhante")
    if nivel is None:
        return None
    titulo = {"obrigatorio": "Acompanhante obrigatório", "recomendado": "Vá acompanhado(a)",
              "direito": "Você pode levar acompanhante"}[nivel]
    return {"nivel": nivel, "titulo": titulo, "texto": "; ".join(motivos).capitalize() + "."}


def prioridade_legal(idade: int, necessidades: set[str], gestante: bool) -> list[str]:
    """Direitos de atendimento prioritário a informar na recepção."""
    itens = []
    if "tea" in necessidades:
        itens.append("Pessoa com TEA: atendimento prioritário. Avise na recepção; peça um local mais calmo para aguardar.")
    if necessidades - {"tea"}:
        itens.append("Pessoa com deficiência ou mobilidade reduzida: atendimento prioritário (Lei 10.048/2000).")
    if idade >= 80:
        itens.append("Pessoa com 80 anos ou mais: prioridade especial.")
    elif idade >= 60:
        itens.append("Pessoa idosa: atendimento prioritário.")
    if gestante:
        itens.append("Gestante: atendimento prioritário.")
    if "deficiencia_auditiva" in necessidades:
        itens.append("Deficiência auditiva: peça intérprete de Libras ou comunicação por escrito.")
    return itens


def transporte(prioridade: Prioridade, destino: str, necessidades: set[str], ambulancia: bool) -> dict | None:
    """Como chegar à unidade, conforme urgência e mobilidade."""
    if destino == "SAMU":
        return {"tipo": "samu", "texto": "Ligue 192: a equipe do SAMU vai até você e faz o transporte."}
    if ambulancia:
        if prioridade >= Prioridade.AMARELO:
            return {"tipo": "samu", "texto": "Você precisa de ambulância para se deslocar: ligue 192 (SAMU) e informe a situação."}
        return {"tipo": "visita_domiciliar",
                "texto": "Não vá por meios próprios: ligue para a ESF/UBS do seu bairro e peça visita domiciliar da equipe. "
                         "Se piorar, ligue 192 (SAMU)."}
    if necessidades & _MOTORAS:
        return {"tipo": "adaptado",
                "texto": "Use transporte adaptado ou carro com acompanhante. As unidades indicadas devem ter acesso para cadeira de rodas; avise ao chegar."}
    return None
