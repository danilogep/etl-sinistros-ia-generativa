"""Configuração do pipeline, lida do ambiente ou do arquivo .env."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Caminhos ──────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
LOG_DIR = ROOT_DIR / "logs"
IMG_DIR = ROOT_DIR / "img"

# Massa de abordagens gerada por seed_data.py a partir dos locais reais do Datatran.
INPUT_FILE = DATA_DIR / "abordagens.csv"
OUTPUT_FILE = DATA_DIR / "abordagens_enriquecidas.csv"
LOG_FILE = LOG_DIR / "pipeline.log"

# Bases abertas de sinistros que alimentam o seed.
ARQUIVOS_SINISTROS = [DATA_DIR / "datatran2024.csv", DATA_DIR / "datatran2025.csv"]

# ── API ───────────────────────────────────────────────────────────────────
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-2.0-flash-001")

# Chamadas simultâneas à API. O free tier do Gemini devolve 429 acima de ~10
# requisições por segundo, e aí o retry passa a dominar o tempo de execução.
CONCURRENCY = int(os.getenv("ETL_CONCURRENCY", "8"))


def get_api_key() -> str:
    """Devolve a chave da API, ou falha com uma mensagem acionável.

    A leitura é tardia de propósito: o módulo precisa ser importável sem chave
    para que os testes rodem no CI e para que `--sem-ia` funcione offline. Antes
    isso era um `raise` em tempo de import, e qualquer `import src.config`
    quebrava sem `.env`.
    """
    chave = os.getenv("GOOGLE_API_KEY", "").strip()
    if not chave or chave.startswith("cole-sua-chave"):
        raise RuntimeError(
            "GOOGLE_API_KEY não configurada. Copie .env.example para .env e "
            "preencha a chave (https://aistudio.google.com/app/apikey), ou rode "
            "o pipeline com --sem-ia para gerar os relatórios sem chamar a API."
        )
    return chave
