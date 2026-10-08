"""Gera a massa de abordagens ficticias a partir de locais reais do Datatran.

    python -m src.seed_data --quantidade 50

Os condutores, placas e veiculos sao inventados; o que vem da base aberta sao os
trechos (UF, BR, km, municipio) e a causa de sinistro mais frequente neles. E
esse cruzamento que torna o alerta especifico em vez de generico.
"""

import argparse
import logging
import random
from datetime import datetime

import pandas as pd

from src.config import ARQUIVOS_SINISTROS, INPUT_FILE

log = logging.getLogger("etl.seed")

ARQUIVO_SAIDA = INPUT_FILE
ARQUIVOS_ACIDENTES = ARQUIVOS_SINISTROS

# Dados fictícios para gerar aleatoriedade
NOMES = [
    "Carlos Silva",
    "Ana Souza",
    "Bruno Lima",
    "Mariana Costa",
    "Pedro Santos",
    "Julia Oliveira",
    "Ricardo Almeida",
    "Fernanda Pereira",
    "Lucas Gomes",
    "Patricia Rocha",
]
VEICULOS = [
    "Honda Civic",
    "Toyota Corolla",
    "Fiat Strada",
    "VW Gol",
    "Chevrolet Onix",
    "Jeep Compass",
    "Hyundai Creta",
    "Ford Ranger",
    "Nissan Kicks",
    "Renault Kwid",
]
PLACAS_LETRAS = ["ABC", "DEF", "GHI", "JKL", "MNO", "PQR", "STU", "VWX"]


def gerar_placa():
    letras = random.choice(PLACAS_LETRAS)
    numeros = random.randint(1000, 9999)
    return f"{letras}-{numeros}"


def gerar_dataset_ficticio(quantidade: int = 50, semente: int | None = None):
    if semente is not None:
        random.seed(semente)
    log.info("lendo a base aberta de sinistros")
    dfs = []

    for arquivo in ARQUIVOS_ACIDENTES:
        try:
            # Datatran usa separador ';' e encoding latin1 ou utf-8
            df = pd.read_csv(arquivo, sep=";", encoding="latin1", low_memory=False)
            dfs.append(df)
        except Exception as e:
            log.warning("erro ao ler %s: %s", arquivo.name, e)

    if not dfs:
        log.error("nenhuma base de sinistros encontrada em data/")
        return

    df_total = pd.concat(dfs)

    # Amostra dos trechos: o que interessa e o contexto (onde foi, qual a causa
    # frequente ali), nao a vitima do registro original.
    quantidade = min(quantidade, len(df_total))
    amostra = df_total.sample(quantidade, random_state=semente)[
        ["uf", "br", "km", "municipio", "causa_acidente", "tipo_acidente"]
    ]

    novos_dados = []

    log.info("gerando %d condutores ficticios sobre trechos reais", quantidade)

    count = 1
    for _, row in amostra.iterrows():
        motorista = {
            "UserID": count,
            "Nome": random.choice(NOMES),
            "Veiculo": random.choice(VEICULOS),
            "Placa": gerar_placa(),
            "Data": datetime.now().strftime("%Y-%m-%d"),
            "Horario": f"{random.randint(6, 22):02d}:{random.randint(0, 59):02d}",
            "UF": row["uf"],
            "BR": row["br"],
            "KM": row["km"],
            "Municipio": row["municipio"],
            "Causa_Frequente": row["causa_acidente"],
        }
        novos_dados.append(motorista)
        count += 1

    # Grava a massa de abordagens
    df_final = pd.DataFrame(novos_dados)

    try:
        ARQUIVO_SAIDA.parent.mkdir(parents=True, exist_ok=True)
        df_final.to_csv(ARQUIVO_SAIDA, index=False)
        log.info("%s gerado com %d registros", ARQUIVO_SAIDA, len(df_final))
        return df_final

    except PermissionError:
        log.error(
            "sem permissao para escrever em %s — o arquivo esta aberto em outro programa?",
            ARQUIVO_SAIDA,
        )
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quantidade", type=int, default=50)
    ap.add_argument("--semente", type=int, default=None, help="torna a amostra reproduzivel")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    return 0 if gerar_dataset_ficticio(args.quantidade, args.semente) is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
