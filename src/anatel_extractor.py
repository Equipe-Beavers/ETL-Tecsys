"""Obtém e lê uma exportação CSV/ZIP do Spectrum-E da Anatel."""
from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Iterator

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def preparar_arquivo() -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    """Obtém CSV/ZIP local ou de uma URL direta de arquivo.

    ANATEL_CSV_URL deve apontar para o arquivo CSV/ZIP real, não para a página HTML
    do Spectrum-E. Por padrão, espera-se uma exportação manual em data/anatel.
    """
    url = os.getenv("ANATEL_CSV_URL", "").strip()
    caminho_configurado = os.getenv(
        "ANATEL_CSV_PATH", "data/anatel/emissoes_licenciadas.csv"
    ).strip()
    temporario: tempfile.TemporaryDirectory[str] | None = None

    if url:
        temporario = tempfile.TemporaryDirectory(prefix="tecsys-anatel-download-")
        caminho = Path(temporario.name) / "anatel_download"
        with requests.get(url, stream=True, timeout=(15, 180)) as resposta:
            resposta.raise_for_status()
            content_type = resposta.headers.get("content-type", "").lower()
            primeiro_bloco = next(resposta.iter_content(chunk_size=4096), b"")
            if "text/html" in content_type or primeiro_bloco.lstrip(b"\xef\xbb\xbf \r\n\t").lower().startswith((b"<!doctype html", b"<html")):
                raise ValueError(
                    "ANATEL_CSV_URL retornou uma página HTML, não um CSV. "
                    "No Spectrum-E, use Download CSV e configure ANATEL_CSV_PATH; "
                    "não use a URL da própria página como link do arquivo."
                )
            with caminho.open("wb") as destino:
                if primeiro_bloco:
                    destino.write(primeiro_bloco)
                for pedaco in resposta.iter_content(chunk_size=1024 * 1024):
                    if pedaco:
                        destino.write(pedaco)
    else:
        caminho = Path(caminho_configurado)
        if not caminho.is_absolute():
            caminho = PROJECT_ROOT / caminho
        raiz_raw = (PROJECT_ROOT / "data" / "raw").resolve()
        caminho = caminho.resolve()
        try:
            caminho.relative_to(raiz_raw)
        except ValueError:
            pass
        else:
            raise ValueError(
                "Mantenha a exportação Anatel fora de data/raw porque o ETL principal limpa essa pasta. "
                "Use data/anatel/emissoes_licenciadas.csv."
            )
        if not caminho.is_file():
            raise FileNotFoundError(
                f"CSV da Anatel não encontrado: {caminho}. Abra o Spectrum-E, clique em Download CSV "
                "na aba desejada e salve o arquivo neste caminho (ou ajuste ANATEL_CSV_PATH)."
            )

    if zipfile.is_zipfile(caminho):
        if temporario is None:
            temporario = tempfile.TemporaryDirectory(prefix="tecsys-anatel-extraido-")
        with zipfile.ZipFile(caminho) as arquivo_zip:
            candidatos = [nome for nome in arquivo_zip.namelist() if nome.lower().endswith(".csv") and not nome.endswith("/")]
            if not candidatos:
                raise ValueError("O ZIP fornecido pela Anatel não contém nenhum CSV.")
            escolhido = candidatos[0]
            extraido = Path(temporario.name) / Path(escolhido).name
            with arquivo_zip.open(escolhido) as origem, extraido.open("wb") as destino:
                shutil.copyfileobj(origem, destino)
            caminho_csv = extraido
    else:
        caminho_csv = caminho

    return caminho_csv, temporario


def iterar_csv(caminho: Path, tamanho_lote: int = 20_000) -> Iterator[pd.DataFrame]:
    """Lê o arquivo por lotes, tentando codificações e separadores comuns."""
    ultimo_erro: Exception | None = None
    encoding_escolhido: str | None = None
    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            pd.read_csv(caminho, sep=None, engine="python", dtype=str, encoding=encoding, nrows=2)
            encoding_escolhido = encoding
            break
        except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as erro:
            ultimo_erro = erro
    if encoding_escolhido is None:
        raise ValueError("Não foi possível detectar a codificação/separador do CSV da Anatel.") from ultimo_erro
    cabecalho = pd.read_csv(
        caminho, sep=None, engine="python", dtype=str, encoding=encoding_escolhido, nrows=0
    )
    nomes = {"".join(ch for ch in str(col).lower() if ch.isalnum()) for col in cabecalho.columns}
    indicadores_spectrum = {
        "freqtxmhz", "freqrxmhz", "atoderf", "uid", "potenciatransmw", "ganhoant"
    }
    if not nomes.intersection(indicadores_spectrum):
        raise ValueError(
            "O arquivo não parece ser a exportação 'Emissões' do Spectrum-E. "
            "O CSV antigo de ERBs de telefonia móvel não contém os parâmetros RF necessários. "
            "Baixe Download CSV na página oficial do Spectrum-E."
        )

    yield from pd.read_csv(
        caminho, sep=None, engine="python", dtype=str, encoding=encoding_escolhido, chunksize=tamanho_lote
    )
