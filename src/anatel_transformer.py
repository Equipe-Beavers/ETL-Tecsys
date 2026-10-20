"""Normaliza as exportações Spectrum-E da Anatel para registros de emissão RF."""
from __future__ import annotations

import hashlib
import math
import os
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
    if texto.lower() in {"", "nan", "none", "null", "<na>", "-", "n/a"}:
        return None
    return texto


def _numero(valor: object) -> float | None:
    texto = _texto(valor)
    if texto is None:
        return None
    texto = texto.replace("\u00a0", "").replace(" ", "")
    # Aceita decimais com vírgula e separadores de milhar tanto pt-BR quanto en-US.
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        resultado = float(texto)
    except ValueError:
        return None
    return resultado if math.isfinite(resultado) else None


def _data(valor: object):
    texto = _texto(valor)
    if texto is None:
        return None
    # ISO (yyyy-mm-dd) deve ser interpretado sem dayfirst para evitar ambiguidade/aviso.
    iso = bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", texto))
    resultado = pd.to_datetime(texto, errors="coerce", dayfirst=not iso)
    return None if pd.isna(resultado) else resultado.date()


def _serie(chunk: pd.DataFrame, aliases: tuple[str, ...]) -> pd.Series:
    colunas = {_normalizar_coluna(coluna): coluna for coluna in chunk.columns}
    for alias in aliases:
        coluna_real = colunas.get(_normalizar_coluna(alias))
        if coluna_real is not None:
            return chunk[coluna_real]
    return pd.Series([None] * len(chunk), index=chunk.index, dtype="object")


# Ordem única usada pelo transformador e pelo loader para evitar divergência de campos.
COLUNAS_DADOS = (
    "source_key", "uid", "fonte_dados", "status", "entidade", "fistel",
    "num_servico", "ato_rf", "num_estacao", "endereco", "complemento", "uf",
    "municipio", "emissao", "tecnologia", "tipo_tecnologia", "meio_acesso",
    "frequencia_tx_mhz", "frequencia_rx_mhz", "azimute_graus", "tipo_estacao",
    "class_infra_fisica", "compartilhamento_infra_fisica", "tipo_antena",
    "homologacao_antena", "ganho_antena", "frente_costas",
    "angulo_meia_potencia_graus", "elevacao_graus", "polarizacao",
    "altura_antena_m", "homologacao_transmissor", "potencia_transmissor_w",
    "latitude", "longitude", "codigo_tfi", "data_licenciamento",
    "data_primeiro_licenciamento", "rede", "data_validade", "fistel_associado",
    "nome_entidade_associado",
)


def transformar_lote(chunk: pd.DataFrame) -> tuple[list[tuple], int, int]:
    """Retorna tuplas para o loader, quantos foram descartados e quantos são RF incompletos.

    Registros sem coordenadas válidas são descartados. Os que têm coordenadas mas não
    têm frequência TX ou potência são mantidos para catálogo/visualização, porém contados
    separadamente porque não bastam, sozinhos, para uma estimativa de propagação RF.
    """
    campos = {
        "uid": ("UID", "_id", "estacao_id"),
        "status": ("Status",),
        "entidade": ("Entidade", "Nome Entidade", "prestadora"),
        "fistel": ("Fistel", "FISTEL", "CNPJ/CPF"),
        "num_servico": ("Num. Serviço", "NumServico", "Serviço", "servico"),
        "ato_rf": ("Ato de RF", "Ato RF", "AtoRF"),
        "num_estacao": ("Num. Estação", "NumEstacao", "numero_estacao", "IdtEstacao"),
        "endereco": ("Endereço", "Endereco", "Logradouro"),
        "complemento": ("Complemento",),
        "uf": ("UF", "SiglaUf", "uf"),
        "municipio": ("Município", "Municipio", "cidade"),
        "emissao": ("Emissão", "Emissao"),
        "tecnologia": ("Tecnologia",),
        "tipo_tecnologia": ("TipoTecnologia", "Tipo Tecnologia"),
        "meio_acesso": ("Meio de Acesso", "MeioAcesso"),
        "frequencia_tx_mhz": ("Freq. TX (MHz)", "Freq TX (MHz)", "FreqTxMHz"),
        "frequencia_rx_mhz": ("Freq. RX (MHz)", "Freq RX (MHz)", "FreqRxMHz"),
        "azimute_graus": ("Azimute", "azimute_graus"),
        "tipo_estacao": ("Tipo Estação", "Tipo Estacao", "CodTipoEstacao", "tipo_estacao"),
        "class_infra_fisica": ("ClassInfraFisica", "Class Infra Fisica"),
        "compartilhamento_infra_fisica": ("CompartilhamentoInfraFisica", "Compartilhamento Infra Fisica"),
        "tipo_antena": ("Tipo Antena", "tipo_antena"),
        "homologacao_antena": ("Homologação Ant.", "Homologacao Ant.", "Homologação Antena"),
        "ganho_antena": ("Ganho Ant.", "Ganho Antena", "ganho_antena"),
        "frente_costas": ("Frente Costa", "Frente/Costa", "frente_costas"),
        "angulo_meia_potencia_graus": ("Ângulo 1/2 Pot.", "Angulo 1/2 Pot.", "angulo_meia_potencia_graus"),
        "elevacao_graus": ("Elevação", "Elevacao", "elevacao_graus"),
        "polarizacao": ("Polarização", "Polarizacao"),
        "altura_antena_m": ("Altura Antena (m)", "Altura Antena", "altura_antena_m"),
        "homologacao_transmissor": ("Homologação Transm.", "Homologacao Transm.", "Homologação Transmissor"),
        "potencia_transmissor_w": ("Potência Transm. (W)", "Potencia Transm. (W)", "potencia_transmissor_w"),
        "latitude": ("Latitude", "MedLatitudeDecimal", "latitude_decimal", "MedLatitude"),
        "longitude": ("Longitude", "MedLongitudeDecimal", "longitude_decimal", "MedLongitude"),
        "codigo_tfi": ("Cod. TFI", "Cod TFI", "codigo_tfi"),
        "data_licenciamento": ("DataLicenciamento", "Data Licenciamento", "data_licenciamento"),
        "data_primeiro_licenciamento": ("DataPrimeiroLicenciamento", "Data Primeiro Licenciamento"),
        "rede": ("Rede",),
        "data_validade": ("DataValidade", "Data Validade", "data_validade"),
        "fistel_associado": ("Fistel Associado", "FistelAssociado"),
        "nome_entidade_associado": ("Nome Entidade Associado", "NomeEntidadeAssociado"),
    }
    colunas = {nome: _serie(chunk, aliases) for nome, aliases in campos.items()}
    fonte = (os.getenv("ANATEL_DATASET_LABEL", "LICENCIADAS").strip() or "LICENCIADAS").upper()
    registros: list[tuple] = []
    descartados = 0
    rf_incompletos = 0

    nomes_campos = list(colunas)
    linhas_valores = zip(*(colunas[nome].tolist() for nome in nomes_campos))
    for valores_linha in linhas_valores:
        linha = dict(zip(nomes_campos, valores_linha))
        valores_texto = {nome: _texto(valor) for nome, valor in linha.items()}
        lat = _numero(linha["latitude"])
        lon = _numero(linha["longitude"])
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            descartados += 1
            continue

        valores_num = {
            campo: _numero(linha[campo])
            for campo in (
                "frequencia_tx_mhz", "frequencia_rx_mhz", "azimute_graus",
                "ganho_antena", "frente_costas", "angulo_meia_potencia_graus",
                "elevacao_graus", "altura_antena_m", "potencia_transmissor_w",
            )
        }
        valores_data = {
            campo: _data(linha[campo])
            for campo in ("data_licenciamento", "data_primeiro_licenciamento", "data_validade")
        }

        uid = valores_texto["uid"]
        if valores_num["frequencia_tx_mhz"] is None or valores_num["potencia_transmissor_w"] is None:
            rf_incompletos += 1

        registro = {
            "uid": uid,
            "fonte_dados": fonte,
            **{k: v for k, v in valores_texto.items() if k != "uid" and k not in {"latitude", "longitude"}},
            **valores_num,
            **valores_data,
            "latitude": lat,
            "longitude": lon,
            "uf": (valores_texto["uf"] or "")[:2].upper() or None,
        }
        # O prefixo permite importar Licenciadas e Cadastradas sem colisão de UID entre bases.
        if uid:
            source_key = f"{fonte}:{uid}"
        else:
            fingerprint_parts = [fonte]
            fingerprint_parts.extend(str(registro.get(campo) or "") for campo in COLUNAS_DADOS if campo not in {"source_key", "fonte_dados"})
            source_key = hashlib.sha256("|".join(fingerprint_parts).encode("utf-8")).hexdigest()
        registro["source_key"] = source_key
        tupla = tuple(registro.get(campo) for campo in COLUNAS_DADOS)
        # As duas últimas posições extras alimentam ST_MakePoint(longitude, latitude).
        registros.append(tupla + (lon, lat))

    return registros, descartados, rf_incompletos
