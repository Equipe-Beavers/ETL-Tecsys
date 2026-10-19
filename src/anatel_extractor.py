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
    """Obtém o CSV configurado e, quando necessário, o extrai de um ZIP.

    O caminho padrão fica em data/anatel, fora de data/raw, porque o ETL
    principal limpa data/raw ao finalizar cada distribuidora.
    """
    url = os.getenv("ANATEL_CSV_URL", "").strip()
    caminho_configurado = os.getenv(
        "ANATEL_CSV_PATH", "data/anatel/estacoes_anatel.csv"
    ).strip()
    temporario: tempfile.TemporaryDirectory[str] | None = None

    if url:
        temporario = tempfile.TemporaryDirectory(prefix="tecsys-anatel-download-")
        caminho = Path(temporario.name) / "anatel_download"
        resposta = requests.get(url, stream=True, timeout=(15, 180))
        resposta.raise_for_status()
        with caminho.open("wb") as destino:
            for pedaco in resposta.iter_content(chunk_size=1024 * 1024):
                if pedaco:
                    destino.write(pedaco)
    else:
        caminho = Path(caminho_configurado)
        if not caminho.is_absolute():
            caminho = PROJECT_ROOT / caminho
        raiz_raw = (PROJECT_ROOT / "data" / "raw").resolve()
        caminho_resolvido = caminho.resolve()
        try:
            caminho_resolvido.relative_to(raiz_raw)
        except ValueError:
            pass
        else:
            raise ValueError(
                "Para executar os dois ETLs em paralelo, mantenha o CSV da Anatel fora de "
                "data/raw, pois o ETL principal limpa essa pasta. Use data/anatel/estacoes_anatel.csv."
            )
        caminho = caminho_resolvido
        if not caminho.is_file():
            raise FileNotFoundError(
                f"CSV da Anatel não encontrado em: {caminho}. Exporte o CSV no painel "
                "Mosaico ou configure ANATEL_CSV_PATH/ANATEL_CSV_URL no .env do ETL."
            )

    if zipfile.is_zipfile(caminho):
        if temporario is None:
            temporario = tempfile.TemporaryDirectory(prefix="tecsys-anatel-extraido-")
        with zipfile.ZipFile(caminho) as arquivo_zip:
            candidatos = [
                nome for nome in arquivo_zip.namelist()
                if nome.lower().endswith(".csv") and not nome.endswith("/")
            ]
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
    """Lê o CSV em lotes sem carregar todo o arquivo na memória."""
    ultimo_erro: Exception | None = None
    encoding_escolhido: str | None = None

    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            pd.read_csv(
                caminho,
                sep=None,
                engine="python",
                dtype=str,
                encoding=encoding,
                nrows=2,
            )
            encoding_escolhido = encoding
            break
        except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as erro:
            ultimo_erro = erro

    if encoding_escolhido is None:
        raise ValueError("Não foi possível detectar a codificação/separador do CSV da Anatel.") from ultimo_erro

    yield from pd.read_csv(
        caminho,
        sep=None,
        engine="python",
        dtype=str,
        encoding=encoding_escolhido,
        chunksize=tamanho_lote,
    )
