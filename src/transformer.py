import os
import pandas
import geopandas as gpd
import psycopg2
from tqdm import tqdm
from .extractor import get_raw_paste

LAYER_ALIASES = {
    "PONNOT": ("PONNOT",),
    "SUB": ("SUB",),
    "UNSEAT": ("UNSEAT", "UNSEBT", "UNSEMT"),
    "UNTRD": ("UNTRD", "UNTRAT", "UNTRBT", "UNTRMT"),
    "UNREGT": ("UNREGT", "UNREAT", "UNREBT", "UNREMT"),
    "UNCR": ("UNCR", "UNCRAT", "UNCRBT", "UNCRMT"),
}

LAYERS_CONFIG = {
    "PONNOT": ["COD_ID", "DIST", "MUN", "ARE_LOC", "TIP_PN", "MAT", "ESF", "ALT", "SITCONT", "SUB", "CONJ"],
    "UNTRD":  ["COD_ID", "DIST", "MUN", "ARE_LOC", "POT_NOM", "PAC_1", "PAC_2", "SITCONT", "SIT_ATIV", "TIP_UNID", "SUB", "CONJ"],
    "UNSEAT": ["COD_ID", "DIST", "MUN", "ARE_LOC", "TIP_UNID", "P_NOM", "SITCONT", "SIT_ATIV", "SUB", "CONJ"],
    "SUB":    ["COD_ID", "DIST", "MUN", "NOME", "SITCONT"],
    "UNREGT": ["COD_ID", "DIST", "MUN", "ARE_LOC", "POT_NOM", "SITCONT", "SIT_ATIV", "TIP_UNID", "SUB", "CONJ"],
    "UNCR":   ["COD_ID", "DIST", "MUN", "ARE_LOC", "POT_NOM", "SITCONT", "SIT_ATIV", "TIP_UNID", "SUB", "CONJ"],
}

def find_gdb_paste(raw_dir: str) -> tuple [str, str]:
    for root, dirs, _ in os.walk(raw_dir):
        for dir in dirs:
            if dir.endswith(".gdb"):
                full_path = os.path.join(root, dir)
                paste_name = os.path.splitext(dir)[0]
                return full_path, paste_name
    raise FileNotFoundError("Nenhuma pasta de extensão .gdb encontrada em data/raw.")

def transform_bdgd_layer(layer_name: str) -> tuple[pandas.DataFrame, str]:
    raw_dir = get_raw_paste()
    gdb_path, paste_name = find_gdb_paste(raw_dir)

    print(f"---------- Carregando dados da camada {layer_name} ----------\n")
    print(f"Carregando Geodatabase: {gdb_path}")

    try:
        available_layers = gpd.list_layers(gdb_path)["name"].tolist()
    except Exception:
        available_layers = []

    aliases = LAYER_ALIASES.get(layer_name.upper(), (layer_name.upper(),))
    matched_layers = [
        layer for layer in available_layers
        if layer.upper() in aliases
    ]

    if not matched_layers:
        print(f"Aviso: Camada '{layer_name}' não encontrada no GDB (esperadas: {', '.join(aliases)}). Retornando DataFrame vazio.")
        target_columns = LAYERS_CONFIG.get(layer_name.upper(), ["COD_ID", "DIST", "MUN", "SITCONT"])
        columns = ["Y", "X"] + target_columns
        empty_df = pandas.DataFrame(columns=columns)
        return empty_df, paste_name

    frames = []
    target_columns = LAYERS_CONFIG.get(layer_name.upper(), ["COD_ID", "DIST", "MUN", "SITCONT"])
    for matched_layer in matched_layers:
        gdf = gpd.read_file(gdb_path, layer=matched_layer)
        if gdf.empty:
            continue

        gdf = gdf.to_crs(epsg=4326)
        centroids = gdf.geometry.apply(
            lambda geom: geom.centroid if geom is not None and not geom.is_empty else None
        )
        gdf["X"] = centroids.x
        gdf["Y"] = centroids.y
        columns = ["Y", "X"] + [col for col in target_columns if col in gdf.columns]
        frame = pandas.DataFrame(gdf[columns])
        frame["CAMADA_BDGD"] = matched_layer
        frames.append(frame)

    if not frames:
        raise ValueError(f"As camadas encontradas para '{layer_name}' estão vazias.")

    df_transformed = pandas.concat(frames, ignore_index=True).drop_duplicates()

    print(f"Transformação concluída! Total de registros: {len(df_transformed)}")

    return df_transformed, paste_name


# PROCESSO DE TRATAMENTO DOS DADOS DA CAMADA RAW PARA SILVER
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", 5432)
}

import os
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "sslmode": "require" if os.getenv("DB_SSL", "").lower() == "true" else "prefer",
}

def get_current_lote() -> str:
    now = datetime.now()
    fortnight = "01" if now.day <= 15 else "02"
    return f"{now.year}_{now.month:02d}_{fortnight}"

def transform_raw_to_silver():
    from .query.raw_to_silver import return_sql_query

    lote_atual = get_current_lote()
    queries = return_sql_query()

    etapas = [
        "Inativando registros antigos (SCD2)",
        "Inserindo Tipos de Dispositivos (ID 0)",
        "Inserindo Tipos de Dispositivos (Desconhecidos)",
        "Inserindo Posições Geográficas (Postes)",
        "Inserindo Tabela Negocial (Postes)",
        "Inserindo Posições Geográficas (Subestações)",
        "Inserindo Tabela Negocial (Subestações)",
        "Inserindo Posições Geográficas (Dispositivos)",
        "Inserindo Tabela Negocial (Dispositivos)"
    ]

    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SET work_mem = '256MB';")
        cursor.execute("SET synchronous_commit = OFF;")

        with tqdm(total=len(queries), desc=f"Pipeline SILVER (Lote: {lote_atual})", unit="etapa") as pbar:
            for query, etapa in zip(queries, etapas):
                pbar.set_postfix_str(f"Executando: {etapa}")
                cursor.execute(query, {"lote": lote_atual})
                pbar.update(1)

        conn.commit()
        cursor.close()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()