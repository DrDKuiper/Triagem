"""Consulta ao Cartão Cidadão do município (cadastro + resumo do prontuário).

`CadastroFicticio` gera uma base de TESTE com moradores fictícios de bairros de
Lençóis Paulista. Para a integração real, implemente `CadastroCidadao` consultando
o sistema do Cartão Cidadão e o prontuário (ex.: recurso FHIR `Patient` pelo
identificador do cartão + `Condition`/`MedicationStatement`/`Immunization`).
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import date, timedelta

import numpy as np

from app.cidadao.bairros import BAIRROS, RUAS
from app.triagem.acessibilidade import NECESSIDADES
from app.triagem.sintomas import COMORBIDADES
from app.unidades.catalogo import POR_ID


def normalizar_cartao(cartao: str) -> str:
    return re.sub(r"\D", "", cartao or "")


def _idade(nascimento: date, hoje: date) -> int:
    return hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))


class CadastroCidadao(ABC):
    nome: str = "base"

    @abstractmethod
    def buscar(self, cartao: str) -> dict | None:
        """Dados do cidadão pelo número do Cartão Cidadão (só dígitos)."""

    def exemplos(self) -> list[dict]:
        """Cartões de teste para demonstração (vazio na integração real)."""
        return []

    def cartoes(self) -> list[str]:
        """Todos os cartões da base (só na base de teste; vazio na integração real)."""
        return []


# Personagens com perfis pensados para testar a triagem e os alertas ambientais.
_PERSONAGENS = [
    dict(nome="Maria Aparecida dos Santos", sexo="F", idade=68, bairro="Jardim Ubirama",
         comorbidades=["diabetes", "hipertensao"], medicamentos=["Metformina 850 mg", "Losartana 50 mg"],
         perfil="Idosa diabética em bairro com alta infestação do Aedes"),
    dict(nome="João Pedro Oliveira", sexo="M", idade=7, bairro="Núcleo Habitacional Luiz Zillo",
         comorbidades=["pneumopatia"], medicamentos=["Salbutamol spray (se crise)"],
         perfil="Criança asmática perto de canavial (fumaça na seca)"),
    dict(nome="Ana Carolina Ferreira", sexo="F", idade=29, bairro="Vila Cruzeiro", gestante=True,
         semanas_gestacao=24, medicamentos=["Sulfato ferroso", "Ácido fólico"],
         perfil="Gestante de 24 semanas"),
    dict(nome="José Carlos Pereira", sexo="M", idade=74, bairro="Centro",
         comorbidades=["cardiopatia", "hipertensao"], medicamentos=["AAS 100 mg", "Atenolol 25 mg", "Sinvastatina 20 mg"],
         alergias=["Dipirona"], necessidades=["mobilidade_reduzida"], perfil="Idoso cardiopata que anda com bengala"),
    dict(nome="Luciana Rodrigues Alves", sexo="F", idade=41, bairro="Jardim Monte Azul",
         perfil="Adulta saudável em bairro próximo ao Rio Lençóis (alagamento)"),
    dict(nome="Antônio Ribeiro da Silva", sexo="M", idade=58, bairro="Alfredo Guedes",
         comorbidades=["renal_cronico", "hipertensao"], medicamentos=["Anlodipino 5 mg"],
         perfil="Morador do distrito de Alfredo Guedes com doença renal"),
    dict(nome="Gabriel Souza Lima", sexo="M", idade=19, bairro="Jardim das Nações",
         perfil="Jovem sem doenças"),
    dict(nome="Helena Martins Costa", sexo="F", idade=1, bairro="Conjunto Habitacional Maestro Júlio Ferrari",
         perfil="Bebê de 1 ano"),
    dict(nome="Pedro Henrique Camargo", sexo="M", idade=9, bairro="Vila Mamedina",
         necessidades=["tea"], medicamentos=["Risperidona 0,5 mg"], perfil="Criança autista (TEA)"),
    dict(nome="Rosa Maria Bueno", sexo="F", idade=86, bairro="Jardim Caju",
         comorbidades=["hipertensao", "cardiopatia"], medicamentos=["Furosemida 40 mg", "Enalapril 10 mg"],
         necessidades=["acamado"], necessita_ambulancia=True, perfil="Idosa acamada que precisa de ambulância"),
    dict(nome="Carlos Eduardo Prado", sexo="M", idade=45, bairro="Jardim Planalto",
         necessidades=["cadeirante"], perfil="Cadeirante"),
]

_NOMES_F = ["Mariana", "Juliana", "Fernanda", "Patrícia", "Camila", "Aline", "Beatriz", "Larissa", "Sônia", "Vera",
            "Cláudia", "Rosana", "Letícia", "Isabela", "Tereza", "Bruna"]
_NOMES_M = ["Carlos", "Paulo", "Rafael", "Lucas", "Marcos", "Rodrigo", "Eduardo", "Sérgio", "Fábio", "Luiz",
            "Diego", "Mateus", "Roberto", "André", "Vinícius", "Benedito"]
_SOBRENOMES = ["Silva", "Santos", "Oliveira", "Souza", "Pereira", "Lima", "Carvalho", "Ferreira", "Rodrigues",
               "Almeida", "Gomes", "Martins", "Barbosa", "Ribeiro", "Moraes", "Camargo", "Bueno", "Prado"]
_REMEDIOS = {"diabetes": "Metformina 850 mg", "hipertensao": "Losartana 50 mg", "cardiopatia": "AAS 100 mg",
             "pneumopatia": "Budesonida inalatória", "renal_cronico": "Carbonato de cálcio", "imunossupressao": "Acompanhamento oncológico"}
_MOTIVOS_CONSULTA = ["Consulta de rotina", "Renovação de receita", "Vacinação", "Síndrome gripal", "Dor lombar",
                     "Exames de rotina", "Curativo", "Pré-natal", "Gastroenterite", "Dor de garganta"]

_TOTAL = 40
_PRIMEIRO_CARTAO = 10000001


class CadastroFicticio(CadastroCidadao):
    nome = "fictício"

    def __init__(self, semente: int = 42, hoje: date | None = None):
        self.hoje = hoje or date.today()
        rng = np.random.default_rng(semente + 7)
        self._base: dict[str, dict] = {}
        for i in range(_TOTAL):
            p = _PERSONAGENS[i] if i < len(_PERSONAGENS) else self._aleatorio(rng)
            cartao = str(_PRIMEIRO_CARTAO + i)
            self._base[cartao] = self._montar(cartao, p, rng)

    @staticmethod
    def _aleatorio(rng: np.random.Generator) -> dict:
        sexo = str(rng.choice(["F", "M"]))
        primeiro = str(rng.choice(_NOMES_F if sexo == "F" else _NOMES_M))
        sobrenomes = rng.choice(_SOBRENOMES, size=2, replace=False)
        idade = int(rng.choice([rng.integers(0, 12), rng.integers(12, 60), rng.integers(60, 92)], p=[0.2, 0.55, 0.25]))
        chance = 0.05 + idade / 120
        comorb = [c for c in COMORBIDADES if rng.random() < chance * (0.6 if c in {"hipertensao", "diabetes"} else 0.15)]
        gestante = sexo == "F" and 18 <= idade <= 40 and rng.random() < 0.12
        necessidades = [n for n, p in (("mobilidade_reduzida", 0.3 if idade >= 75 else 0.02), ("cadeirante", 0.03),
                                       ("tea", 0.04 if idade < 30 else 0.0)) if rng.random() < p]
        return dict(nome=f"{primeiro} {sobrenomes[0]} {sobrenomes[1]}", sexo=sexo, idade=idade,
                    bairro=str(rng.choice(list(BAIRROS))), comorbidades=comorb, gestante=gestante,
                    necessidades=necessidades,
                    semanas_gestacao=int(rng.integers(8, 38)) if gestante else None,
                    medicamentos=[_REMEDIOS[c] for c in comorb])

    def _montar(self, cartao: str, p: dict, rng: np.random.Generator) -> dict:
        bairro = BAIRROS[p["bairro"]]
        nascimento = self.hoje - timedelta(days=int(p["idade"] * 365.25 + rng.integers(1, 360)))
        ubs = POR_ID[bairro.ubs_referencia]
        comorb = p.get("comorbidades", [])
        consultas = []
        for _ in range(int(rng.integers(1, 4))):
            dias = int(rng.integers(10, 400))
            motivo = "Pré-natal" if p.get("gestante") else str(rng.choice(_MOTIVOS_CONSULTA[:7] if not comorb else _MOTIVOS_CONSULTA[:3]))
            if "acamado" in p.get("necessidades", []):
                motivo = "Visita domiciliar"
            consultas.append({"data": (self.hoje - timedelta(days=dias)).isoformat(), "unidade": ubs.nome, "motivo": motivo})
        consultas.sort(key=lambda c: c["data"], reverse=True)
        idade = _idade(nascimento, self.hoje)
        vacinas = [{"vacina": "Influenza (gripe)", "data": (self.hoje - timedelta(days=int(rng.integers(30, 300)))).isoformat()}]
        if idade >= 5:
            vacinas.append({"vacina": "COVID-19", "data": (self.hoje - timedelta(days=int(rng.integers(60, 500)))).isoformat()})
        if 10 <= idade <= 14:
            vacinas.append({"vacina": "Dengue (Qdenga)", "data": (self.hoje - timedelta(days=int(rng.integers(30, 200)))).isoformat()})
        return {
            "cartao": cartao,
            "cns": "7" + "".join(str(d) for d in rng.integers(0, 10, size=14)),
            "nome": p["nome"],
            "sexo": p["sexo"],
            "nascimento": nascimento.isoformat(),
            "idade": idade,
            "gestante": bool(p.get("gestante", False)),
            "semanas_gestacao": p.get("semanas_gestacao"),
            "comorbidades": comorb,
            "comorbidades_rotulos": [COMORBIDADES[c] for c in comorb],
            "necessidades": p.get("necessidades", []),
            "necessidades_rotulos": [NECESSIDADES[n] for n in p.get("necessidades", [])],
            "necessita_ambulancia": bool(p.get("necessita_ambulancia", False)),
            "alergias": p.get("alergias", []),
            "medicamentos": p.get("medicamentos", []),
            "vacinas": vacinas,
            "ultimas_consultas": consultas,
            "endereco": {
                "logradouro": f"{rng.choice(RUAS)}, {int(rng.integers(20, 1800))}",
                "bairro": bairro.nome,
                "cidade": "Lençóis Paulista - SP",
                "lat": round(bairro.lat + float(rng.normal(0, 0.0025)), 5),
                "lon": round(bairro.lon + float(rng.normal(0, 0.0025)), 5),
            },
            "ubs_referencia": {"id": ubs.id, "nome": ubs.nome},
            "perfil_teste": p.get("perfil", ""),
            "ficticio": True,
        }

    def buscar(self, cartao: str) -> dict | None:
        c = self._base.get(normalizar_cartao(cartao))
        if c is None:
            return None
        # Mantém a idade correta caso o servidor fique no ar após a virada do dia.
        return {**c, "idade": _idade(date.fromisoformat(c["nascimento"]), date.today())}

    def cartoes(self) -> list[str]:
        return list(self._base)

    def exemplos(self) -> list[dict]:
        return [
            {"cartao": c["cartao"], "nome": c["nome"], "idade": c["idade"], "bairro": c["endereco"]["bairro"], "perfil": c["perfil_teste"]}
            for c in list(self._base.values())[: len(_PERSONAGENS)]
        ]
