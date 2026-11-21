import os
import pandas
import geopandas as gpd
import psycopg2
from tqdm import tqdm
from dotenv import load_dotenv
from datetime import datetime
from .extractor import get_raw_paste

LAYERS_CONFIG = {
    "PONNOT": [
        "COD_ID",
        "DIST",
        "MUN",
        "ARE_LOC",
        "TIP_PN",
        "MAT",
        "ESF",
        "ALT",
        "SITCONT",
        "SUB",
        "CONJ",
    ],
    "UNSEAT": [
        "COD_ID",
        "DIST",
        "MUN",
        "ARE_LOC",
        "TIP_UNID",
        "P_NOM",
        "SITCONT",
        "SUB",
        "CONJ",
    ],
    "SUB": ["COD_ID", "DIST", "MUN", "NOME", "SITCONT"],
}

TARGET_LAYERS = ["PONNOT", "UNSEAT", "SUB"]


def get_distributor_uf(mun_code: int):
    uf_codes = {
        11: "RO",
        12: "AC",
        13: "AM",
        14: "RR",
        15: "PA",
        16: "AP",
        17: "TO",
        21: "MA",
        22: "PI",
        23: "CE",
        24: "RN",
        25: "PB",
        26: "PE",
        27: "AL",
        28: "SE",
        29: "BA",
        31: "MG",
        32: "ES",
        33: "RJ",
        35: "SP",
        41: "PR",
        42: "SC",
        43: "RS",
        50: "MS",
        51: "MT",
        52: "GO",
        53: "DF",
    }
    uf = int(str(mun_code)[:2])
    return uf_codes[uf]


def find_gdb_folder(raw_dir: str) -> tuple[str, str]:
    for root, dirs, _ in os.walk(raw_dir):
        for dir in dirs:
            if dir.endswith(".gdb"):
                full_path = os.path.join(root, dir)
                paste_name = os.path.splitext(dir)[0]
                return full_path, paste_name
    raise FileNotFoundError(f"Nenhuma pasta de extensão .gdb encontrada em {raw_dir}")


def catalog_dataframe(filepath: str):
    interest_columns = ["id", "created", "modified", "title"]
    try:
        df = pandas.read_csv(filepath, usecols=interest_columns)
    except Exception as e:
        raise ValueError(f"Uma coluna especificada não existe no CSV: {e}")
    return df


def format_catalog_data(df: pandas.DataFrame):
    for column in ["created", "modified"]:
        if column in df.columns:
            df[column] = pandas.to_datetime(df[column], errors="coerce")
            df[column] = df[column].dt.tz_localize(None)
    sorted_df = df.sort_values(by="modified", ascending=False)
    return sorted_df


def get_data_by_date(df: pandas.DataFrame):
    df["modified"] = pandas.to_datetime(df["modified"], errors="coerce")
    wanted_date = df["modified"].dt.date.iloc[0]
    filtered_df = df[df["modified"].dt.date == wanted_date]
    return filtered_df 


def transform_bdgd_layer(layer_name: str) -> tuple[pandas.DataFrame, str]:
    raw_dir = get_raw_paste()
    gdb_path, paste_name = find_gdb_folder(raw_dir)

    print(f"---------- Carregando dados da camada {layer_name} ----------\n")
    print(f"Carregando Geodatabase: {gdb_path}")

    try:
        available_layers = gpd.list_layers(gdb_path)["name"].tolist()
    except Exception:
        available_layers = []

    matched_layer = next(
        (l for l in available_layers if l.upper() == layer_name.upper()), None
    )

    if not matched_layer:
        raise ValueError(f"Layer '{layer_name}' não existe no GDB.")

    gdf = gpd.read_file(gdb_path, layer=matched_layer)

    if gdf.empty:
        raise ValueError(f"Layer '{layer_name}' está vazia.")

    gdf = gdf.to_crs(epsg=4326)
    centroids = gdf.geometry.apply(
        lambda geom: geom.centroid if geom and not geom.is_empty else None
    )
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


def transform_bdgd_into_json(extract_dir: str, bdgd_version: any, distributor_id: any, distributor_name: str):
    gdb_path, folder_name = find_gdb_folder(extract_dir)
    columns_filter = {
        "PONNOT": "postes",
        "SUB": "subestações",
        "UNSEAT": "dispositivos",
    }

    response_json = {
        "versao_bdgd": bdgd_version,
        "nome": distributor_name,
        "id_distribuidora": int(distributor_id),
        "uf": None
    }

    try:
        available_layers = gpd.list_layers(gdb_path)["name"].tolist()
    except Exception as e:
        available_layers = []
    for layer in TARGET_LAYERS:
        response_json[columns_filter[layer]] = {}
        matched_layers = next(
            (l for l in available_layers if l.upper() == layer.upper()), None
        )
        if not matched_layers:
            raise ValueError(f"Camada '{layer}' não existe no .gdb")
        gdf = gpd.read_file(gdb_path, layer=matched_layers)
        if gdf.empty:
            pass
        gdf = gdf.to_crs(epsg=4326)
        centroids = gdf.geometry.apply(
            lambda geom: geom.centroid if geom and not geom.is_empty else None
        )
        gdf["X"] = centroids.x
        gdf["Y"] = centroids.y
        target_columns = LAYERS_CONFIG.get(layer, ["COD_ID", "DIST", "MUN", "SITCONT"])
        if "SUB" in gdf.columns and "SUB" not in target_columns:
            target_columns.append("SUB")
        elif "CONJ" in gdf.columns and "CONJ" not in target_columns:
            target_columns.append("CONJ")
        cols_to_keep = ["Y", "X"] + [
            col for col in target_columns if col in gdf.columns
        ]
        df_transformed = pandas.DataFrame(gdf[cols_to_keep]).drop_duplicates()
        response_json[columns_filter[layer]] = df_transformed.to_dict(orient="records")
        if not response_json["uf"] and response_json[columns_filter[layer]]:
            first_line = response_json[columns_filter[layer]][0]
            if first_line["MUN"]:
                mun_cod = first_line["MUN"]
                response_json["uf"] = get_distributor_uf(mun_cod)
    return response_json


load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
}

def get_current_lote() -> str:
    now = datetime.now()
    fortnight = "01" if now.day <= 15 else "02"
    return f"{now.year}_{now.month:02d}_{fortnight}"