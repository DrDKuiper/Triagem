"""Bairros de Lençóis Paulista usados no cadastro fictício e nas análises ambientais.

Os bairros são os das unidades de Atenção Básica do município (ver
app/unidades/catalogo.py), mais o Centro. A unidade de referência de cada bairro é
a ESF/UBS do próprio bairro; sem unidade no bairro, a mais próxima.

ATENÇÃO: dados de DEMONSTRAÇÃO. Coordenadas são aproximadas e os fatores
ambientais (infestação do Aedes, proximidade do rio e de canaviais, escorpiões)
são fictícios. Na integração real, use a territorialização das equipes de Saúde da
Família, o georreferenciamento do Cartão Cidadão e os boletins da Vigilância
Ambiental / CETESB.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.unidades.catalogo import UNIDADES
from app.unidades.servico import distancia_km


class Bairro(BaseModel):
    nome: str
    lat: float
    lon: float
    ubs_referencia: str = ""   # id em app/unidades/catalogo.py (preenchido abaixo)
    peso_populacao: float      # fração aproximada dos moradores do município
    liraa_base: float          # índice de infestação predial típico no verão (%)
    perto_rio: bool = False    # margem do Rio Lençóis: risco de alagamento e leptospirose
    perto_canavial: bool = False  # borda com lavoura de cana: fumaça de queimadas na seca
    escorpioes_base: int = 2   # notificações mensais típicas


_BAIRROS = [
    Bairro(nome="Centro", lat=-22.5986, lon=-48.8003, peso_populacao=0.12, liraa_base=1.6, perto_rio=True,
           escorpioes_base=4),
    Bairro(nome="Vila Cruzeiro", lat=-22.5895, lon=-48.8009, peso_populacao=0.09, liraa_base=2.4, escorpioes_base=3),
    Bairro(nome="Jardim Ubirama", lat=-22.6048, lon=-48.8116, peso_populacao=0.10, liraa_base=4.2, escorpioes_base=3),
    Bairro(nome="Núcleo Habitacional Luiz Zillo", lat=-22.5826, lon=-48.8115, peso_populacao=0.10, liraa_base=3.1,
           perto_canavial=True),
    Bairro(nome="Jardim Monte Azul", lat=-22.6127, lon=-48.7924, peso_populacao=0.09, liraa_base=2.8, perto_rio=True),
    Bairro(nome="Alfredo Guedes", lat=-22.6616, lon=-48.7263, peso_populacao=0.04, liraa_base=0.8,
           perto_canavial=True, escorpioes_base=1),
    Bairro(nome="Jardim Planalto", lat=-22.6041, lon=-48.7821, peso_populacao=0.08, liraa_base=2.0),
    Bairro(nome="Vila Mamedina", lat=-22.5961, lon=-48.7881, peso_populacao=0.08, liraa_base=2.2, perto_rio=True,
           escorpioes_base=3),
    Bairro(nome="Conjunto Habitacional Maestro Júlio Ferrari", lat=-22.5839, lon=-48.8140, peso_populacao=0.08,
           liraa_base=3.6, perto_canavial=True),
    Bairro(nome="Jardim Caju", lat=-22.6230, lon=-48.7889, peso_populacao=0.07, liraa_base=2.6, perto_canavial=True,
           escorpioes_base=1),
    Bairro(nome="Jardim das Nações", lat=-22.5880, lon=-48.8060, peso_populacao=0.07, liraa_base=1.2,
           escorpioes_base=1),
    Bairro(nome="Núcleo Habitacional João Zillo", lat=-22.6009, lon=-48.7850, peso_populacao=0.08, liraa_base=3.0),
]

_ATENCAO_BASICA = [u for u in UNIDADES if u.tipo == "UBS"]
for _b in _BAIRROS:
    proprias = [u for u in _ATENCAO_BASICA if u.bairro == _b.nome]
    _b.ubs_referencia = (proprias or sorted(_ATENCAO_BASICA, key=lambda u: distancia_km(_b.lat, _b.lon, u.lat, u.lon)))[0].id

BAIRROS: dict[str, Bairro] = {b.nome: b for b in _BAIRROS}

# Ruas usadas para compor endereços fictícios em cada bairro.
RUAS = [
    "Rua Sete de Setembro", "Rua XV de Novembro", "Rua Tiradentes", "Rua Rui Barbosa", "Rua Anita Garibaldi",
    "Avenida Brasil", "Rua Ignácio Anselmo", "Rua Duque de Caxias", "Rua São Paulo", "Rua Santos Dumont",
    "Rua Campos Salles", "Rua Marechal Deodoro", "Rua Ipiranga", "Rua das Palmeiras", "Rua dos Ipês",
]
