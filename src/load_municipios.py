import geopandas as gpd
import psycopg2
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv(encoding="utf-8");

ARQUIVO_GPKG = Path(__file__).resolve().parent.parent / "data" / "raw" / "BR_localidades_2022.gpkg"

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", 5432)
}

conn = psycopg2.connect(
    **DB_CONFIG 
)

try:
    layers = gpd.list_layers(ARQUIVO_GPKG)

    print("Camadas encontradas:")
    print(layers[["name", "geometry_type"]].to_string(index=False))

    camada_municipios = None

    for nome_camada in layers["name"]:
        gdf = gpd.read_file(ARQUIVO_GPKG, layer=nome_camada)

        colunas = {col.upper(): col for col in gdf.columns}

        if all(
            coluna in colunas
            for coluna in ["CD_MUN", "NM_MUN", "SIGLA_UF"]
        ):
            camada_municipios = nome_camada
            break

    if camada_municipios is None:
        raise RuntimeError(
            "Nenhuma camada contendo CD_MUN, NM_MUN e SIGLA_UF foi encontrada."
        )

    print(f"\nCamada selecionada: {camada_municipios}")

    gdf = gpd.read_file(
        ARQUIVO_GPKG,
        layer=camada_municipios
    )

    colunas = {col.upper(): col for col in gdf.columns}

    dados = gdf[
        [
            colunas["CD_MUN"],
            colunas["NM_MUN"],
            colunas["SIGLA_UF"]
        ]
    ].copy()

    dados.columns = ["codigo_ibge", "nome", "uf"]

    dados["codigo_ibge"] = dados["codigo_ibge"].astype(str).str.strip()
    dados["nome"] = dados["nome"].astype(str).str.strip()
    dados["uf"] = dados["uf"].astype(str).str.strip()

    dados = dados[
        dados["codigo_ibge"].str.contains(r"\d", na=False)
    ]

    dados["codigo_ibge"] = dados["codigo_ibge"].str.split(".").str[0]

    dados = dados[
        (dados["nome"] != "")
        & (dados["uf"].str.len() == 2)
    ]

    dados["codigo_ibge"] = dados["codigo_ibge"].astype(int)

    dados = dados.drop_duplicates(subset=["codigo_ibge"])

    print(f"Municípios encontrados: {len(dados)}")

    cursor = conn.cursor()

    registros = [
        (
            int(row.codigo_ibge),
            row.nome,
            row.uf
        )
        for row in dados.itertuples(index=False)
    ]

    cursor.executemany(
        """
        INSERT INTO municipios (
            codigo_ibge,
            nome,
            uf
        )
        VALUES (%s, %s, %s)
        ON CONFLICT (codigo_ibge)
        DO UPDATE SET
            nome = EXCLUDED.nome,
            uf = EXCLUDED.uf
        """,
        registros
    )

    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM municipios")
    total = cursor.fetchone()[0]

    print(f"Importação concluída.")
    print(f"Total de municípios na tabela: {total}")

finally:
    conn.close()