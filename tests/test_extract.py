"""Leitura do CSV de abordagens: o que entra, o que é descartado, o que explode."""

import pandas as pd
import pytest

from src.extract import RegistroInvalido, carregar_dados, validar_colunas

CABECALHO = "UserID,Nome,Veiculo,Placa,Data,Horario,UF,BR,KM,Municipio,Causa_Frequente\n"
LINHA_OK = "1,Ana Souza,VW Gol,ABC-1234,2025-11-27,14:10,BA,367,\"26,1\",PORTO SEGURO,Velocidade incompatível\n"


def escrever(tmp_path, conteudo, nome="abordagens.csv"):
    caminho = tmp_path / nome
    caminho.write_text(conteudo, encoding="utf-8")
    return caminho


def test_le_registro_valido(tmp_path):
    registros = carregar_dados(escrever(tmp_path, CABECALHO + LINHA_OK))

    assert len(registros) == 1
    assert registros[0]["Nome"] == "Ana Souza"
    # O km vem com vírgula decimal do Datatran e precisa sobreviver à leitura.
    assert registros[0]["KM"] == "26,1"


def test_arquivo_inexistente_devolve_lista_vazia(tmp_path):
    assert carregar_dados(tmp_path / "nao-existe.csv") == []


def test_arquivo_vazio_devolve_lista_vazia(tmp_path):
    assert carregar_dados(escrever(tmp_path, "")) == []


def test_coluna_obrigatoria_ausente_levanta_erro(tmp_path):
    sem_placa = CABECALHO.replace("Placa,", "") + "1,Ana,VW Gol,2025-11-27,14:10,BA,367,26,PORTO SEGURO,x\n"

    with pytest.raises(RegistroInvalido) as erro:
        carregar_dados(escrever(tmp_path, sem_placa))

    assert "Placa" in str(erro.value)


@pytest.mark.parametrize(
    ("linha_ruim", "motivo"),
    [
        ("2,,VW Gol,DEF-2222,2025-11-27,10:00,SP,116,10,SANTOS,x\n", "nome vazio"),
        ("3,João,,GHI-3333,2025-11-27,10:00,SP,116,10,SANTOS,x\n", "veículo vazio"),
        ("4,Maria,Fiat Strada,,2025-11-27,10:00,SP,116,10,SANTOS,x\n", "placa vazia"),
        ("5,   ,Fiat Strada,JKL-4444,2025-11-27,10:00,SP,116,10,SANTOS,x\n", "nome só com espaços"),
    ],
)
def test_registro_malformado_e_descartado_sem_derrubar_o_lote(tmp_path, linha_ruim, motivo):
    """Um registro ruim não pode custar uma chamada paga nem interromper o resto."""
    caminho = escrever(tmp_path, CABECALHO + LINHA_OK + linha_ruim)

    registros = carregar_dados(caminho)

    assert len(registros) == 1, f"o registro com {motivo} deveria ter sido descartado"
    assert registros[0]["Nome"] == "Ana Souza"


def test_validar_colunas_aceita_colunas_extras():
    df = pd.DataFrame(columns=["Nome", "Veiculo", "Placa", "ColunaNova"])

    validar_colunas(df)  # não deve levantar
