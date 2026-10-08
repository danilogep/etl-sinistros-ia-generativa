"""Carga: o CSV enriquecido e os gráficos saem onde deveriam."""

import pandas as pd

from src.load import salvar_resultados

REGISTROS = [
    {
        "Nome": "Ana Souza",
        "Veiculo": "VW Gol",
        "BR": "116",
        "Causa_Frequente": "Velocidade incompatível",
        "Mensagem_IA": "Reduza a velocidade.",
    },
    {
        "Nome": "Bruno Lima",
        "Veiculo": "Fiat Strada",
        "BR": "116",
        "Causa_Frequente": "Velocidade incompatível",
        "Mensagem_IA": "Atenção ao trecho.",
    },
    {
        "Nome": "Carla Dias",
        "Veiculo": "VW Gol",
        "BR": "381",
        "Causa_Frequente": "Animais na pista",
        "Mensagem_IA": "Risco de animais.",
    },
]


def test_gera_csv_e_os_dois_graficos(tmp_path):
    destino = tmp_path / "saida" / "enriquecido.csv"
    img = tmp_path / "img"

    escritos = salvar_resultados(REGISTROS, destino=destino, img_dir=img)

    assert destino.exists()
    assert (img / "causas_de_risco.png").exists()
    assert (img / "abordagens_por_rodovia.png").exists()
    assert set(escritos) == {"csv", "causas_de_risco.png", "abordagens_por_rodovia.png"}


def test_csv_preserva_acentuacao(tmp_path):
    destino = tmp_path / "enriquecido.csv"

    salvar_resultados(REGISTROS, destino=destino, img_dir=tmp_path / "img")
    df = pd.read_csv(destino)

    assert df.loc[0, "Causa_Frequente"] == "Velocidade incompatível"
    assert len(df) == 3


def test_lista_vazia_nao_escreve_nada(tmp_path):
    destino = tmp_path / "enriquecido.csv"

    assert salvar_resultados([], destino=destino, img_dir=tmp_path / "img") == {}
    assert not destino.exists()


def test_coluna_ausente_pula_o_grafico_sem_quebrar_a_carga(tmp_path):
    """Faltar uma coluna de contexto não pode custar o CSV inteiro."""
    sem_br = [{k: v for k, v in r.items() if k != "BR"} for r in REGISTROS]
    destino = tmp_path / "enriquecido.csv"
    img = tmp_path / "img"

    escritos = salvar_resultados(sem_br, destino=destino, img_dir=img)

    assert destino.exists()
    assert "abordagens_por_rodovia.png" not in escritos
    assert (img / "causas_de_risco.png").exists()
