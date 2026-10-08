"""Leitura e validação da massa de abordagens."""

import logging

import pandas as pd

from src.config import INPUT_FILE

log = logging.getLogger("etl.extract")

COLUNAS_OBRIGATORIAS = ("Nome", "Veiculo", "Placa")
COLUNAS_DE_CONTEXTO = ("BR", "KM", "Municipio", "Causa_Frequente")


class RegistroInvalido(ValueError):
    """O arquivo existe, mas não tem o formato que o pipeline espera."""


def validar_colunas(df: pd.DataFrame) -> None:
    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
    if faltando:
        raise RegistroInvalido(
            f"colunas obrigatórias ausentes no CSV: {', '.join(faltando)}"
        )


def _registro_utilizavel(registro: dict) -> bool:
    """Um registro sem nome ou sem veículo não gera alerta algum.

    Descartar aqui é mais barato que descobrir no meio de uma chamada paga à API.
    """
    for coluna in COLUNAS_OBRIGATORIAS:
        valor = registro.get(coluna)
        if valor is None or (isinstance(valor, float) and pd.isna(valor)):
            return False
        if not str(valor).strip():
            return False
    return True


def carregar_dados(caminho=None) -> list[dict]:
    """Lê o CSV de abordagens e devolve os registros utilizáveis."""
    caminho = caminho or INPUT_FILE
    log.info("lendo %s", caminho)

    try:
        df = pd.read_csv(caminho)
    except FileNotFoundError:
        log.error(
            "arquivo não encontrado: %s — rode `python -m src.seed_data` antes", caminho
        )
        return []
    except pd.errors.EmptyDataError:
        log.error("arquivo vazio: %s", caminho)
        return []

    validar_colunas(df)

    registros = df.to_dict("records")
    validos = [r for r in registros if _registro_utilizavel(r)]

    descartados = len(registros) - len(validos)
    if descartados:
        log.warning("%d registro(s) malformado(s) descartado(s)", descartados)
    log.info("%d registros carregados", len(validos))

    return validos
