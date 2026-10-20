"""Persistência de emissões Spectrum-E da Anatel em PostgreSQL/PostGIS."""
from __future__ import annotations

import os
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

from src.anatel_transformer import COLUNAS_DADOS

COLUNAS_INSERT = (*COLUNAS_DADOS, "geom")
_COLUNAS_BASE = ", ".join(COLUNAS_INSERT[:-1])
_TEMPLATE = "(" + ",".join(["%s"] * len(COLUNAS_DADOS)) + ", ST_SetSRID(ST_MakePoint(%s, %s), 4674))"
_UPDATES = [f"{nome} = EXCLUDED.{nome}" for nome in COLUNAS_DADOS if nome != "source_key"]
_UPDATES.extend(["geom = EXCLUDED.geom", "atualizado_em = NOW()"])
UPSERT_SQL = f"""
    INSERT INTO public.emissoes_anatel ({_COLUNAS_BASE}, geom)
    VALUES %s
    ON CONFLICT (source_key) DO UPDATE SET
        {', '.join(_UPDATES)}
"""


def conectar_banco(raiz_projeto: Path):
    configuracao: dict[str, object] = {
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "sslmode": os.getenv("DB_SSLMODE", "prefer"),
    }
    root_cert = os.getenv("DB_SSLROOTCERT")
    if root_cert:
        caminho_certificado = Path(root_cert)
        if not caminho_certificado.is_absolute():
            caminho_certificado = raiz_projeto / caminho_certificado
        if not caminho_certificado.is_file():
            raise FileNotFoundError(f"Certificado SSL não encontrado: {caminho_certificado}")
        configuracao["sslrootcert"] = str(caminho_certificado.resolve())

    campos_obrigatorios = ("dbname", "user", "password", "host")
    ausentes = [campo for campo in campos_obrigatorios if not configuracao[campo]]
    if ausentes:
        raise RuntimeError(
            "Variáveis de conexão ausentes no .env: "
            + ", ".join(campo.upper() for campo in ausentes)
        )
    return psycopg2.connect(**configuracao)


def verificar_tabela(conexao) -> None:
    with conexao.cursor() as cursor:
        cursor.execute("SELECT to_regclass('public.emissoes_anatel')")
        if cursor.fetchone()[0] is None:
            raise RuntimeError(
                "A tabela public.emissoes_anatel não existe. Execute primeiro "
                "Backend-Tecsys/database/migrations/20261019_integracao_antenas.sql."
            )


def salvar_lote(conexao, registros: list[tuple]) -> int:
    if not registros:
        return 0
    try:
        with conexao.cursor() as cursor:
            execute_values(cursor, UPSERT_SQL, registros, template=_TEMPLATE, page_size=1000)
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    return len(registros)
