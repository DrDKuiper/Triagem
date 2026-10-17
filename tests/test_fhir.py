import httpx

from app.prontuario.fhir import FHIRProntuario, agravo_por_cid


def test_agravo_por_cid():
    assert agravo_por_cid("A90") == "dengue"
    assert agravo_por_cid("U07.1") == "covid19"
    assert agravo_por_cid("J10.1") == "sindrome_gripal"
    assert agravo_por_cid("I21") is None


def test_ocupacao_e_registro_via_fhir():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET" and req.url.path == "/Encounter":
            total = 7 if req.url.params["status"] == "in-progress" else 3
            return httpx.Response(200, json={"resourceType": "Bundle", "total": total})
        if req.method == "POST" and req.url.path == "/Observation":
            return httpx.Response(201, json={"resourceType": "Observation", "id": "obs-1"})
        return httpx.Response(404)

    client = httpx.Client(base_url="http://fhir.local", transport=httpx.MockTransport(handler))
    p = FHIRProntuario("http://fhir.local", client=client)
    oc = p.ocupacao(["upa-lencois"])["upa-lencois"]
    assert (oc.em_atendimento, oc.aguardando) == (7, 3)
    assert p.registrar_triagem({"prioridade": "verde", "sintomas": ["tosse"]}) == "obs-1"
