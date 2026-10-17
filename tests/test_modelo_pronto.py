import gzip
import pickle

import sklearn

from app.triagem import modelo_ml


def test_carrega_modelo_pronto_so_com_mesma_versao(tmp_path):
    modelo = modelo_ml.obter_modelo(42)
    arquivo = tmp_path / "modelo.pkl.gz"
    modelo_ml.salvar_pronto(modelo, arquivo)

    carregado = modelo_ml.carregar_pronto(42, arquivo)
    assert carregado is not None and carregado.origem == "pré-treinado"
    assert carregado.acuracia == modelo.acuracia

    assert modelo_ml.carregar_pronto(7, arquivo) is None  # outra semente
    with gzip.open(arquivo, "wb") as f:
        pickle.dump({"semente": 42, "sklearn": "0.0", "modelo": modelo}, f)
    assert modelo_ml.carregar_pronto(42, arquivo) is None  # outra versão do scikit-learn
    assert sklearn.__version__ != "0.0"


def test_sem_arquivo_treina(tmp_path):
    assert modelo_ml.carregar_pronto(42, tmp_path / "nao-existe.pkl.gz") is None
