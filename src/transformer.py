import os
import pandas
import geopandas as gpd
import psycopg2
from tqdm import tqdm
from dotenv import load_dotenv
from datetime import datetime
from .extractor import get_raw_paste
from .query.raw_to_silver  import return_sql_query

LAYERS_CONFIG = {
    "PONNOT": ["COD_ID", "DIST", "MUN", "ARE_LOC", "TIP_PN", "MAT", "ESF", "ALT", "SITCONT", "SUB", "CONJ"],
    "UNTRD":  ["COD_ID", "DIST", "MUN", "ARE_LOC", "POT_NOM", "PAC_1", "PAC_2", "SITCONT", "SUB", "CONJ"],
    "UNSEAT": ["COD_ID", "DIST", "MUN", "ARE_LOC", "TIP_UNID", "P_NOM", "SITCONT", "SUB", "CONJ"],
    "SUB":    ["COD_ID", "DIST", "MUN", "NOME", "SITCONT"],
    "UNREGT": ["COD_ID", "DIST", "MUN", "ARE_LOC", "POT_NOM", "SITCONT", "SUB", "CONJ"]
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

    matched_layer = next((l for l in available_layers if l.upper() == layer_name.upper()), None)

    if not matched_layer:
        raise ValueError(f"Layer '{layer_name}' não existe no GDB.")

    gdf = gpd.read_file(gdb_path, layer=matched_layer)
    
    if gdf.empty:
        raise ValueError(f"Layer '{layer_name}' está vazia.")

    gdf = gdf.to_crs(epsg=4326)
    centroids = gdf.geometry.apply(lambda geom: geom.centroid if geom and not geom.is_empty else None)
    gdf["X"] = centroids.x
    gdf["Y"] = centroids.y
    target_columns = LAYERS_CONFIG.get(layer_name, ["COD_ID", "DIST", "MUN", "SITCONT"])

    if "SUB" in gdf.columns and "SUB" not in target_columns:
        target_columns.append("SUB")
    elif "CONJ" in gdf.columns and "CONJ" not in target_columns:
        target_columns.append("CONJ")

    cols_to_keep = ["Y", "X"] + [col for col in target_columns if col in gdf.columns]
    df_transformed = pandas.DataFrame(gdf[cols_to_keep])
    df_transformed = df_transformed.drop_duplicates()

    print(f"Transformação concluída! Total de registros: {len(df_transformed)}")

    return df_transformed, paste_name


load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

def get_current_lote() -> str:
    now = datetime.now()
    fortnight = "01" if now.day <= 15 else "02"
    return f"{now.year}_{now.month:02d}_{fortnight}"
