from __future__ import annotations

import os
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

UPSERT_SQL = """
    INSERT INTO antenas_anatel (
        source_key, uid, num_estacao, entidade, servico, uf, municipio, endereco,
        tecnologia, tipo_estacao, tipo_antena, frequencia_tx_mhz, frequencia_rx_mhz,
        azimute_graus, altura_antena_m, potencia_transmissor_w, data_licenciamento,
        latitude, longitude, geom
    ) VALUES %s
    ON CONFLICT (source_key) DO UPDATE SET
        uid = EXCLUDED.uid,
        num_estacao = EXCLUDED.num_estacao,
        entidade = EXCLUDED.entidade,
        servico = EXCLUDED.servico,
        uf = EXCLUDED.uf,
        municipio = EXCLUDED.municipio,
        endereco = EXCLUDED.endereco,
        tecnologia = EXCLUDED.tecnologia,
        tipo_estacao = EXCLUDED.tipo_estacao,
        tipo_antena = EXCLUDED.tipo_antena,
        frequencia_tx_mhz = EXCLUDED.frequencia_tx_mhz,
        frequencia_rx_mhz = EXCLUDED.frequencia_rx_mhz,
        azimute_graus = EXCLUDED.azimute_graus,
        altura_antena_m = EXCLUDED.altura_antena_m,
        potencia_transmissor_w = EXCLUDED.potencia_transmissor_w,
        data_licenciamento = EXCLUDED.data_licenciamento,
        latitude = EXCLUDED.latitude,
        longitude = EXCLUDED.longitude,
        geom = EXCLUDED.geom,
        atualizado_em = NOW()
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

    campos_obrigatorios = ("dbname", "user", "password")
    ausentes = [campo for campo in campos_obrigatorios if not configuracao[campo]]
    if ausentes:
        raise RuntimeError(
            "Variáveis de conexão ausentes no .env: "
            + ", ".join(campo.upper() for campo in ausentes)
        )

    return psycopg2.connect(**configuracao)


def verificar_tabela(conexao) -> None:
    with conexao.cursor() as cursor:
        cursor.execute("SELECT to_regclass('public.antenas_anatel')")
        if cursor.fetchone()[0] is None:
            raise RuntimeError(
                "A tabela antenas_anatel não existe. Execute primeiro "
                "Backend-Tecsys/database/migrations/20261019_integracao_antenas.sql."
            )


def salvar_lote(conexao, registros: list[tuple]) -> int:
    if not registros:
        return 0

    template = "(" + ",".join(["%s"] * 19) + ", ST_SetSRID(ST_MakePoint(%s, %s), 4674))"
    try:
        with conexao.cursor() as cursor:
            execute_values(cursor, UPSERT_SQL, registros, template=template, page_size=1000)
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    return len(registros)
