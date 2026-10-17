"""Cadastro das unidades de saúde de Lençóis Paulista (SP).

Nomes, endereços, telefones e horários: site da Prefeitura (Secretaria de Saúde >
Unidades de Atendimento e Carta de Serviços: "Consultas Médicas na Atenção Básica" e
"Atendimento de Urgência e Emergência – UPA"), consultado em 17/10/2026.
A Carta de Serviços publica um único horário para toda a Atenção Básica (ESF/UBS).

Coordenadas: APROXIMADAS, obtidas do OpenStreetMap pela rua do endereço (não pelo
número); a do Jardim das Nações é estimada. Confirme com o CNES antes do uso real e
preencha o código `cnes` (usado como id do `Location` com PRONTUARIO_BACKEND=fhir).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

# Dia da semana (0 = segunda) -> (abre, fecha) em horas.
Horarios = dict[int, tuple[float, float]]

HORARIO_ATENCAO_BASICA: Horarios = {0: (7, 22), 1: (7, 22), 2: (7, 22), 3: (7, 22), 4: (7, 20), 5: (7, 13)}
TEXTO_ATENCAO_BASICA = "Seg a qui 7h–22h • Sex 7h–20h • Sáb 7h–13h"
_SERVICOS_ATENCAO_BASICA = ["Acolhimento com classificação de risco", "Consultas médicas e de enfermagem", "Vacinas",
                            "Curativos", "Medicamentos", "Visitas domiciliares", "Pré-natal", "Hiperdia"]


class Unidade(BaseModel):
    id: str
    nome: str
    tipo: str  # UPA | UBS (ESF e UBS da Atenção Básica) | PS
    endereco: str
    bairro: str
    telefone: str = ""
    lat: float
    lon: float
    horario: str
    aberta_24h: bool
    horarios: Horarios = {}
    servicos: list[str]
    profissionais_plantao: int
    cnes: str | None = None
    dados_confirmados: bool = False

    def aberta(self, quando: datetime) -> bool:
        if self.aberta_24h:
            return True
        faixa = self.horarios.get(quando.weekday())
        hora = quando.hour + quando.minute / 60
        return faixa is not None and faixa[0] <= hora < faixa[1]


def _ab(id: str, nome: str, endereco: str, bairro: str, telefone: str, lat: float, lon: float, profissionais: int = 3) -> Unidade:
    return Unidade(id=id, nome=nome, tipo="UBS", endereco=endereco, bairro=bairro, telefone=telefone, lat=lat, lon=lon,
                   horario=TEXTO_ATENCAO_BASICA, aberta_24h=False, horarios=HORARIO_ATENCAO_BASICA,
                   servicos=_SERVICOS_ATENCAO_BASICA, profissionais_plantao=profissionais, dados_confirmados=True)


UNIDADES: list[Unidade] = [
    Unidade(id="upa-lencois", nome="UPA 24h \"Antônio Lorenzetti Filho\"", tipo="UPA",
            endereco="Rua Sete de Setembro, 600", bairro="Centro", telefone="(14) 3269-1300",
            lat=-22.5980, lon=-48.8023, horario="24 horas, todos os dias", aberta_24h=True,
            servicos=["Urgência e emergência clínica e traumática", "Estabilização", "Encaminhamento hospitalar"],
            profissionais_plantao=6, dados_confirmados=True),
    # O hospital aparece no mapa, mas nunca é indicado pela triagem (porta de entrada: UBS/ESF ou UPA).
    Unidade(id="ps-hospital-piedade", nome="Hospital N. Sra. da Piedade (referência da UPA)", tipo="PS",
            endereco="Endereço a confirmar", bairro="Centro", lat=-22.6010, lon=-48.8035, horario="24 horas",
            aberta_24h=True, servicos=["Internação", "Maternidade", "Centro cirúrgico"], profissionais_plantao=5),
    _ab("ubs-ubirama", "UBS \"José Antônio Garrido\"", "Rua Marechal Dutra, 895", "Jardim Ubirama",
        "(14) 3263-6251", -22.6048, -48.8116, 4),
    _ab("ubs-joao-zillo", "UBS \"Dr. Antônio Leão Tocci\"", "Rua Dias Gomes, 37", "Núcleo Habitacional João Zillo",
        "(14) 3264-4040", -22.6009, -48.7850, 4),
    _ab("ubs-luiz-zillo", "ESF \"Dr. João Paccola Primo\"", "Rua dos Lavradores, 34", "Núcleo Habitacional Luiz Zillo",
        "(14) 3263-1985", -22.5826, -48.8115),
    _ab("ubs-monte-azul", "ESF \"Antonio Benedetti\"", "Rua Horácio Moretto, 1255", "Jardim Monte Azul",
        "(14) 3264-4042", -22.6127, -48.7924),
    _ab("ubs-cruzeiro", "ESF \"Dr. José Nege\"", "Rua Bahia, 294", "Vila Cruzeiro",
        "(14) 3264-3505", -22.5895, -48.8009),
    _ab("ubs-alfredo-guedes", "ESF \"Victorio Boso\"", "Rua Bento Ribeiro, 29", "Alfredo Guedes",
        "(14) 99651-3684", -22.6616, -48.7263, 2),
    _ab("esf-planalto", "ESF \"Dr. Rowilson Roselli Abiuzzi\"", "Avenida Jácomo Augusto Paccola, 2330", "Jardim Planalto",
        "(14) 3264-8903", -22.6041, -48.7821),
    _ab("esf-mamedina", "ESF \"Carlos Alberto Baptistella\"", "Rua Ana Neri, 124", "Vila Mamedina",
        "(14) 3263-2562", -22.5961, -48.7881),
    _ab("esf-julio-ferrari", "ESF \"Winter Malatrasi\"", "Rua Manoel Duarte Moreira, 160",
        "Conjunto Habitacional Maestro Júlio Ferrari", "(14) 3264-5040", -22.5839, -48.8140),
    _ab("esf-caju", "ESF do Jardim do Caju", "Rua João Coneglian, 350", "Jardim Caju",
        "(14) 3264-9933", -22.6230, -48.7889),
    _ab("esf-nacoes", "ESF \"Dra. Irene Alcídia da Costa Andrade\"", "Rua das Araras, 560", "Jardim das Nações",
        "(14) 3264-1007", -22.5880, -48.8060),
]

POR_ID = {u.id: u for u in UNIDADES}
