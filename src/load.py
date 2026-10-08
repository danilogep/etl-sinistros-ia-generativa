"""Carga do resultado e geração dos gráficos analíticos."""

import logging

import matplotlib

# Backend sem janela: o pipeline roda em container e no CI, onde não há display.
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src.config import IMG_DIR, OUTPUT_FILE  # noqa: E402

log = logging.getLogger("etl.load")

COR_PRIMARIA = "#1f4fd8"
COR_ALERTA = "#c2410c"


def _encurtar(texto: str, limite: int = 34) -> str:
    texto = str(texto)
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def grafico_causas(df: pd.DataFrame, caminho) -> None:
    """As causas de risco que mais aparecem nos trechos abordados."""
    contagem = df["Causa_Frequente"].value_counts().head(8).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh([_encurtar(i) for i in contagem.index], contagem.to_numpy(), color=COR_ALERTA)
    ax.set_title("Causa de risco do trecho abordado", fontsize=13, pad=12)
    ax.set_xlabel("abordagens")
    ax.bar_label(ax.containers[0], padding=3, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(caminho, dpi=130)
    plt.close(fig)


def grafico_rodovias(df: pd.DataFrame, caminho) -> None:
    """Concentração das abordagens por rodovia federal."""
    contagem = df["BR"].astype(str).value_counts().head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh([f"BR-{i}" for i in contagem.index], contagem.to_numpy(), color=COR_PRIMARIA)
    ax.set_title("Abordagens por rodovia", fontsize=13, pad=12)
    ax.set_xlabel("abordagens")
    ax.bar_label(ax.containers[0], padding=3, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(caminho, dpi=130)
    plt.close(fig)


def salvar_resultados(dados: list[dict], destino=None, img_dir=None) -> dict:
    """Grava o CSV enriquecido e os gráficos. Devolve os caminhos escritos."""
    if not dados:
        log.warning("nada para salvar")
        return {}

    destino = destino or OUTPUT_FILE
    img_dir = img_dir or IMG_DIR
    destino.parent.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(dados)
    df.to_csv(destino, index=False, encoding="utf-8-sig")
    log.info("CSV salvo em %s", destino)

    escritos = {"csv": destino}
    for nome, funcao, coluna in (
        ("causas_de_risco.png", grafico_causas, "Causa_Frequente"),
        ("abordagens_por_rodovia.png", grafico_rodovias, "BR"),
    ):
        if coluna not in df.columns:
            log.warning("coluna %s ausente — gráfico %s não gerado", coluna, nome)
            continue
        caminho = img_dir / nome
        funcao(df, caminho)
        log.info("gráfico salvo em %s", caminho)
        escritos[nome] = caminho

    return escritos
