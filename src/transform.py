"""Enriquecimento dos registros com a API do Google Gemini.

O cliente é construído sob demanda (`_get_model`), e não no import: assim o
módulo pode ser importado — e testado — sem chave de API, e o modo `--sem-ia`
roda offline.
"""

import asyncio
import logging

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import CONCURRENCY, GEMINI_MODEL, get_api_key

log = logging.getLogger("etl.transform")

_model = None


class FalhaTransitoriaAPI(RuntimeError):
    """Erro que vale repetir: rate limit, indisponibilidade, timeout."""


class FalhaPermanenteAPI(RuntimeError):
    """Erro que não vale repetir: chave inválida, prompt recusado, cota esgotada."""


# Repetir um 400 ("prompt inválido") três vezes só queima cota e atrasa o lote.
# Só erro transitório entra no retry; o resto sobe na hora.
_PERMANENTES = ("api key", "api_key", "permission", "invalid", "not found", "unauthorized")


def _get_model():
    global _model
    if _model is None:
        import google.generativeai as genai

        genai.configure(api_key=get_api_key())
        _model = genai.GenerativeModel(GEMINI_MODEL)
    return _model


def montar_prompt(registro: dict) -> str:
    """Monta o prompt de alerta para um condutor em um trecho específico."""
    nome = registro["Nome"]
    veiculo = registro["Veiculo"]
    br = registro.get("BR", "rodovia")
    km = registro.get("KM", "?")
    municipio = registro.get("Municipio", "região")
    causa = registro.get("Causa_Frequente", "acidentes diversos")

    return (
        "Você é um agente de segurança viária. "
        f"Gere um alerta curto e impactante (máximo 20 palavras) para {nome}, "
        f"que dirige um {veiculo}. "
        f"CONTEXTO: o condutor está passando pela BR-{br} no KM {km} ({municipio}). "
        f"Neste trecho, o histórico de sinistros aponta como causa frequente: '{causa}'. "
        "O alerta deve falar especificamente desse risco. "
        "Não cite nenhum órgão ou instituição."
    )


def _classificar(erro: Exception) -> Exception:
    texto = str(erro).lower()
    if any(marca in texto for marca in _PERMANENTES):
        return FalhaPermanenteAPI(str(erro))
    return FalhaTransitoriaAPI(str(erro))


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(FalhaTransitoriaAPI),
    reraise=True,
)
async def gerar_mensagem(registro: dict) -> str:
    """Gera o alerta de um registro, com até 3 tentativas em falha transitória."""
    try:
        resposta = await _get_model().generate_content_async(montar_prompt(registro))
        return resposta.text.strip()
    except (FalhaTransitoriaAPI, FalhaPermanenteAPI):
        raise
    except Exception as erro:  # noqa: BLE001 - o SDK levanta tipos variados
        classificado = _classificar(erro)
        log.warning("falha ao gerar para %s: %s", registro.get("Nome"), classificado)
        raise classificado from erro


def mensagem_simulada(registro: dict) -> str:
    """Alerta determinístico, sem chamar a API.

    Usado por `--sem-ia`: permite exercitar extract/load, gerar os gráficos e
    rodar o pipeline no CI sem gastar cota. A saída é explicitamente marcada
    para que ninguém confunda com texto gerado por modelo.
    """
    causa = str(registro.get("Causa_Frequente", "risco não informado")).lower()
    br = registro.get("BR", "?")
    km = registro.get("KM", "?")
    return f"[SIMULADO] Atenção na BR-{br}, km {km}: trecho com histórico de {causa}."


async def processar_dados(registros: list[dict], usar_ia: bool = True) -> list[dict]:
    """Enriquece a lista inteira, com paralelismo limitado por semáforo."""
    if not usar_ia:
        log.info("modo --sem-ia: gerando %d alertas simulados", len(registros))
        for registro in registros:
            registro["Mensagem_IA"] = mensagem_simulada(registro)
        return registros

    log.info("enriquecendo %d registros (%d chamadas simultâneas)", len(registros), CONCURRENCY)
    semaforo = asyncio.Semaphore(CONCURRENCY)

    async def _uma(registro: dict) -> str:
        # Sem o semáforo, 50 registros viram 50 chamadas simultâneas e o free
        # tier responde 429 em quase todas.
        async with semaforo:
            return await gerar_mensagem(registro)

    resultados = await asyncio.gather(
        *(_uma(r) for r in registros), return_exceptions=True
    )

    falhas = 0
    for registro, resultado in zip(registros, resultados, strict=True):
        if isinstance(resultado, Exception):
            # Um registro que falhou não derruba o lote: ele é marcado e o
            # pipeline segue, porque reprocessar 49 chamadas pagas por causa de
            # uma é desperdício.
            registro["Mensagem_IA"] = ""
            registro["Erro_IA"] = type(resultado).__name__
            falhas += 1
        else:
            registro["Mensagem_IA"] = resultado

    if falhas:
        log.warning("%d de %d registros ficaram sem alerta", falhas, len(registros))
    log.info("enriquecimento concluído")
    return registros
