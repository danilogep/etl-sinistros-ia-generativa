"""Enriquecimento: prompt, retry e tolerância a falha — tudo com a API dublada.

Nenhum teste deste arquivo faz chamada de rede. O cliente do Gemini é
substituído em `_get_model`, que existe justamente para permitir isso: antes, o
modelo era construído no import do módulo e não havia onde interceptar.
"""

from unittest.mock import AsyncMock

import pytest

from src import transform
from src.transform import (
    FalhaPermanenteAPI,
    FalhaTransitoriaAPI,
    gerar_mensagem,
    mensagem_simulada,
    montar_prompt,
    processar_dados,
)

REGISTRO = {
    "Nome": "Ana Souza",
    "Veiculo": "VW Gol",
    "BR": "116",
    "KM": "536",
    "Municipio": "REGISTRO",
    "Causa_Frequente": "Velocidade incompatível",
}


@pytest.fixture(autouse=True)
def sem_modelo_real(monkeypatch):
    """Garante que nenhum teste escape para a API de verdade."""
    monkeypatch.setattr(transform, "_model", None)
    yield
    monkeypatch.setattr(transform, "_model", None)


def modelo_falso(respostas):
    """Dublê do GenerativeModel: cada chamada consome o próximo item da lista.

    Item que for exceção é levantado; o resto vira o `.text` da resposta.
    """
    modelo = AsyncMock()

    async def _responder(_prompt):
        item = respostas.pop(0)
        if isinstance(item, Exception):
            raise item
        resposta = AsyncMock()
        resposta.text = item
        return resposta

    modelo.generate_content_async = _responder
    return modelo


# --- prompt -----------------------------------------------------------------


def test_prompt_carrega_o_contexto_do_trecho():
    prompt = montar_prompt(REGISTRO)

    assert "Ana Souza" in prompt
    assert "VW Gol" in prompt
    assert "BR-116" in prompt
    assert "536" in prompt
    assert "Velocidade incompatível" in prompt


def test_prompt_funciona_com_contexto_faltando():
    prompt = montar_prompt({"Nome": "Ana", "Veiculo": "Gol"})

    assert "rodovia" in prompt  # cai no valor neutro em vez de estourar KeyError


def test_prompt_nao_cita_instituicao():
    prompt = montar_prompt(REGISTRO).lower()

    assert "prf" not in prompt
    assert "polícia" not in prompt


# --- retry ------------------------------------------------------------------


async def test_sucesso_na_primeira_tentativa(monkeypatch):
    modelo = modelo_falso(["Reduza a velocidade neste trecho."])
    monkeypatch.setattr(transform, "_get_model", lambda: modelo)

    assert await gerar_mensagem(dict(REGISTRO)) == "Reduza a velocidade neste trecho."


async def test_falha_transitoria_e_repetida_ate_dar_certo(monkeypatch):
    """429 é o caso comum no free tier: a segunda tentativa costuma passar."""
    respostas = [
        RuntimeError("429 Too Many Requests"),
        RuntimeError("503 Service Unavailable"),
        "Atenção ao limite de velocidade.",
    ]
    modelo = modelo_falso(respostas)
    monkeypatch.setattr(transform, "_get_model", lambda: modelo)
    monkeypatch.setattr(transform.gerar_mensagem.retry, "wait", lambda _: 0)

    assert await gerar_mensagem(dict(REGISTRO)) == "Atenção ao limite de velocidade."
    assert respostas == []  # as três tentativas foram consumidas


async def test_falha_transitoria_persistente_desiste_apos_tres_tentativas(monkeypatch):
    respostas = [RuntimeError("429 Too Many Requests") for _ in range(5)]
    modelo = modelo_falso(respostas)
    monkeypatch.setattr(transform, "_get_model", lambda: modelo)
    monkeypatch.setattr(transform.gerar_mensagem.retry, "wait", lambda _: 0)

    with pytest.raises(FalhaTransitoriaAPI):
        await gerar_mensagem(dict(REGISTRO))

    assert len(respostas) == 2, "deveria ter parado na terceira tentativa"


async def test_falha_permanente_nao_e_repetida(monkeypatch):
    """Repetir um `API key not valid` três vezes só atrasa o lote."""
    respostas = [RuntimeError("API key not valid") for _ in range(5)]
    modelo = modelo_falso(respostas)
    monkeypatch.setattr(transform, "_get_model", lambda: modelo)

    with pytest.raises(FalhaPermanenteAPI):
        await gerar_mensagem(dict(REGISTRO))

    assert len(respostas) == 4, "deveria ter desistido na primeira tentativa"


# --- lote -------------------------------------------------------------------


async def test_um_registro_com_falha_nao_derruba_o_lote(monkeypatch):
    modelo = modelo_falso(["alerta 1", RuntimeError("API key not valid"), "alerta 3"])
    monkeypatch.setattr(transform, "_get_model", lambda: modelo)
    monkeypatch.setattr(transform, "CONCURRENCY", 1)

    registros = [dict(REGISTRO, Nome=f"Condutor {i}") for i in range(3)]
    resultado = await processar_dados(registros)

    assert [r["Mensagem_IA"] for r in resultado] == ["alerta 1", "", "alerta 3"]
    assert resultado[1]["Erro_IA"] == "FalhaPermanenteAPI"


async def test_modo_sem_ia_nao_toca_na_api(monkeypatch):
    def explodir():
        raise AssertionError("--sem-ia não pode construir o cliente da API")

    monkeypatch.setattr(transform, "_get_model", explodir)

    resultado = await processar_dados([dict(REGISTRO)], usar_ia=False)

    assert resultado[0]["Mensagem_IA"].startswith("[SIMULADO]")


def test_mensagem_simulada_e_marcada_e_deterministica():
    """A saída offline precisa ser inconfundível com texto de modelo."""
    primeira = mensagem_simulada(REGISTRO)

    assert primeira.startswith("[SIMULADO]")
    assert primeira == mensagem_simulada(REGISTRO)
    assert "BR-116" in primeira
