import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import construir_site  # noqa: E402

from app.offline import requisicao  # noqa: E402


def test_instantaneo_igual_ao_backend(tmp_path):
    destino = tmp_path / "instantaneo.json"
    construir_site.gerar_instantaneo(destino)
    respostas = json.loads(destino.read_text(encoding="utf-8"))
    assert {"/api/config", "/api/cidadao/exemplos", "/api/cidadao/10000001"} <= set(respostas)
    assert not any(c.startswith("/api/unidades") for c in respostas)  # dependem da hora
    for caminho in ["/api/config", "/api/cidadao/exemplos", "/api/cidadao/10000005"]:
        assert respostas[caminho] == json.loads(requisicao("GET", caminho)[1])
