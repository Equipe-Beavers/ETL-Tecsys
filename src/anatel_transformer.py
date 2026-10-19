from __future__ import annotations

import hashlib
import re
import unicodedata

import pandas as pd


def _normalizar_coluna(valor: object) -> str:
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]", "", texto.lower())


def _texto(valor: object) -> str | None:
    if valor is None or pd.isna(valor):
        return None
    texto = str(valor).strip()
    if texto.lower() in {"", "nan", "none", "null", "<na>", "-"}:
        return None
    return texto


def _numero(valor: object) -> float | None:
    texto = _texto(valor)
    if texto is None:
        return None
    texto = texto.replace(" ", "").replace(",", ".")
    try:
        resultado = float(texto)
    except ValueError:
        return None
    return resultado if pd.notna(resultado) else None


def _data(valor: object):
    texto = _texto(valor)
    if texto is None:
        return None
    resultado = pd.to_datetime(texto, errors="coerce", dayfirst=True)
    return None if pd.isna(resultado) else resultado.date()


def _serie(chunk: pd.DataFrame, aliases: tuple[str, ...]) -> pd.Series:
    colunas = {_normalizar_coluna(coluna): coluna for coluna in chunk.columns}
    for alias in aliases:
        coluna_real = colunas.get(_normalizar_coluna(alias))
        if coluna_real is not None:
            return chunk[coluna_real]
    return pd.Series([None] * len(chunk), index=chunk.index, dtype="object")


def transformar_lote(chunk: pd.DataFrame) -> tuple[list[tuple], int]:
    """Transforma um lote em tuplas prontas para o loader; retorna descartados."""
    uid = _serie(chunk, ("UID", "_id", "estacao_id"))
    num_estacao = _serie(chunk, ("Num. Estação", "NumEstacao", "numero_estacao", "IdtEstacao"))
    entidade = _serie(chunk, ("Entidade", "Nome Entidade", "Nome Entidade Associado", "prestadora"))
    servico = _serie(chunk, ("NumServico", "Serviço", "servico", "nome_servico"))
    uf = _serie(chunk, ("SiglaUf", "UF", "uf"))
    municipio = _serie(chunk, ("Municipio", "município", "cidade"))
    endereco = _serie(chunk, ("Endereco", "Endereço", "Logradouro"))
    tecnologia = _serie(chunk, ("Tecnologia", "TipoTecnologia", "tipo_tecnologia"))
    tipo_estacao = _serie(chunk, ("Tipo Estacao", "Tipo Estação", "CodTipoEstacao", "tipo_estacao"))
    tipo_antena = _serie(chunk, ("Tipo Antena", "tipo_antena"))
    freq_tx = _serie(chunk, ("Freq TX (MHz)", "Freq. TX (MHz)", "FreqTxMHz", "frequencia_tx_mhz"))
    freq_rx = _serie(chunk, ("Freq RX (MHz)", "Freq. RX (MHz)", "FreqRxMHz", "frequencia_rx_mhz"))
    azimute = _serie(chunk, ("Azimute", "azimute_graus"))
    altura = _serie(chunk, ("Altura Antena (m)", "Altura Antena", "altura_antena_m"))
    potencia = _serie(chunk, ("Potencia Transm. (W)", "Potência Transm. (W)", "potencia_transmissor_w"))
    data_lic = _serie(chunk, ("DataLicenciamento", "Data Licenciamento", "data_licenciamento"))
    latitude = _serie(chunk, ("Latitude", "MedLatitudeDecimal", "latitude_decimal", "MedLatitude"))
    longitude = _serie(chunk, ("Longitude", "MedLongitudeDecimal", "longitude_decimal", "MedLongitude"))

    registros: list[tuple] = []
    descartados = 0

    for indice in chunk.index:
        lat = _numero(latitude.loc[indice])
        lon = _numero(longitude.loc[indice])
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            descartados += 1
            continue

        uid_texto = _texto(uid.loc[indice])
        estacao_texto = _texto(num_estacao.loc[indice])
        entidade_texto = _texto(entidade.loc[indice])
        municipio_texto = _texto(municipio.loc[indice])
        tecnologia_texto = _texto(tecnologia.loc[indice])
        tx = _numero(freq_tx.loc[indice])
        rx = _numero(freq_rx.loc[indice])
        az = _numero(azimute.loc[indice])
        alt = _numero(altura.loc[indice])
        pot = _numero(potencia.loc[indice])
        data = _data(data_lic.loc[indice])

        chave_base = "|".join(str(v or "") for v in (
            estacao_texto, entidade_texto, municipio_texto, lat, lon,
            tecnologia_texto, tx, rx, az, _texto(tipo_antena.loc[indice]),
        ))
        source_key = uid_texto or hashlib.sha256(chave_base.encode("utf-8")).hexdigest()

        registros.append((
            source_key,
            uid_texto,
            estacao_texto,
            entidade_texto,
            _texto(servico.loc[indice]),
            (_texto(uf.loc[indice]) or "")[:2].upper() or None,
            municipio_texto,
            _texto(endereco.loc[indice]),
            tecnologia_texto,
            _texto(tipo_estacao.loc[indice]),
            _texto(tipo_antena.loc[indice]),
            tx,
            rx,
            az,
            alt,
            pot,
            data,
            lat,
            lon,
            lon,
            lat,
        ))

    return registros, descartados
