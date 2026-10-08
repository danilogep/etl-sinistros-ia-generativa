"""Orquestrador do pipeline ETL.

    python -m src.pipeline                # enriquece com a API do Gemini
    python -m src.pipeline --sem-ia       # roda offline, sem gastar cota
    python -m src.pipeline --limite 10    # processa só os 10 primeiros registros
"""

import argparse
import asyncio
import logging
import sys
import time

from src.config import LOG_DIR, LOG_FILE
from src.extract import RegistroInvalido, carregar_dados
from src.load import salvar_resultados
from src.transform import processar_dados

log = logging.getLogger("etl")


def configurar_log() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)-14s %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
    )


async def executar(limite: int = 0, usar_ia: bool = True) -> int:
    inicio = time.perf_counter()

    try:
        registros = carregar_dados()
    except RegistroInvalido as erro:
        log.error("%s", erro)
        return 2

    if not registros:
        log.error("nenhum registro para processar")
        return 1

    if limite:
        registros = registros[:limite]
        log.info("limitado a %d registros", len(registros))

    registros = await processar_dados(registros, usar_ia=usar_ia)
    escritos = salvar_resultados(registros)

    sem_alerta = sum(1 for r in registros if not r.get("Mensagem_IA"))
    duracao = time.perf_counter() - inicio
    log.info(
        "concluído: %d registros em %.1fs (%.2f s/registro) | %d sem alerta | saídas: %s",
        len(registros),
        duracao,
        duracao / max(len(registros), 1),
        sem_alerta,
        ", ".join(str(p.name) for p in escritos.values()),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limite", type=int, default=0, help="processa só os N primeiros registros")
    ap.add_argument(
        "--sem-ia",
        action="store_true",
        help="gera alertas simulados, sem chamar a API (offline, custo zero)",
    )
    args = ap.parse_args(argv)

    configurar_log()
    return asyncio.run(executar(limite=args.limite, usar_ia=not args.sem_ia))


if __name__ == "__main__":
    sys.exit(main())
