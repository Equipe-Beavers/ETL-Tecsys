import os
from pathlib import Path
import sqlite3
import pandas
import glob
import psycopg2
from io import StringIO
from tqdm import tqdm
from psycopg2.extras import execute_values
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(encoding="utf-8");

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", 5432)
}

month_map  = {
    1: "janeiro", 2: "fevereiro", 3: "marco", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"
}

def get_processed_folder() -> str:
    now = datetime.now()

    fortnight = "01" if now.day <= 15 else "02"
    folder_name = f"{month_map[now.month]}_{now.year}.{fortnight}"
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fortnight_folder = os.path.join(root_dir, "data", "processed", folder_name)

    os.makedirs(fortnight_folder, exist_ok=True)

    return fortnight_folder  

def save_to_csv(df: pandas.DataFrame, base_name: str, layer_name: str) -> str:
    destiny_path = get_processed_folder()
    csv_path = os.path.join(destiny_path, f"{base_name}_{layer_name}.csv")
    df.to_csv(csv_path, index=True, encoding="utf-8", header=True)
    print(f"Arquivo CSV salvo com sucesso em: {csv_path}")
    return csv_path

def clean_num(series, is_int=False):
    if series is None or series.empty:
        return pandas.Series(dtype='object')
    s = series.astype(str).str.strip().str.replace(',', '.')
    s = s.replace(['nan', 'NaN', 'None', '', 'null', '<NA>'], None)
    if is_int:
        return pandas.to_numeric(s, errors='coerce').astype('Int64')
    return pandas.to_numeric(s, errors='coerce')


def load_all_csvs_directly(data_folder_path: str, lote_atual: str):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        cur.execute("SET synchronous_commit = OFF;")
        
        layers_config = {
            'PONNOT': {'tipo_pos': 'POSTE'},
            'SUB':     {'tipo_pos': 'SUBESTACAO'},
            'UNSEAT': {'tipo_pos': 'DISPOSITIVO'}
        }

        for prefix, cfg in layers_config.items():
            csv_files = []
            for f in glob.glob(os.path.join(data_folder_path, f"*{prefix}*.csv")):
                if os.path.getsize(f) <= 75 * 1024 * 1024:
                    csv_files.append(f)
            
            if not csv_files:
                print(f"[AVISO] Nenhum arquivo encontrado ou com mais de 100MB para a camada {prefix}")
                continue

            print(f"\n--- Processando {len(csv_files)} arquivos da camada {prefix} ---")

            chunk_size = 30000
            for file_path in tqdm(csv_files, desc=f"Lendo CSVs {prefix} (Chunks)"):
                for chunk in pandas.read_csv(file_path, sep=None, dtype=str, encoding_errors='ignore', engine='python', chunksize=chunk_size):
                    if chunk is None or chunk.empty:
                        continue

                    chunk.columns = chunk.columns.str.strip().str.upper()

                    col_y = 'Y' if 'Y' in chunk.columns else ('LATITUDE' if 'LATITUDE' in chunk.columns else None)
                    col_x = 'X' if 'X' in chunk.columns else ('LONGITUDE' if 'LONGITUDE' in chunk.columns else None)

                    if not col_y or not col_x:
                        continue

                    chunk['latitude'] = clean_num(chunk[col_y])
                    chunk['longitude'] = clean_num(chunk[col_x])
                    chunk = chunk.dropna(subset=['latitude', 'longitude'])

                    if chunk.empty:
                        continue

                    df_pos = pandas.DataFrame({
                        'latitude': chunk['latitude'],
                        'longitude': chunk['longitude'],
                        'tipo_posicao': cfg['tipo_pos'],
                        'municipio': chunk['MUN'].str.strip() if 'MUN' in chunk.columns else None,
                        'id_distribuidora': clean_num(chunk['DIST'], is_int=True) if 'DIST' in chunk.columns else None,
                        'are_loc': chunk['ARE_LOC'].str.strip() if 'ARE_LOC' in chunk.columns else None,
                        'registro_atual': True,
                        'lote_carga': lote_atual
                    }).drop_duplicates(subset=['latitude', 'longitude', 'tipo_posicao'])

                    cod_id_col = chunk['COD_ID'].str.strip() if 'COD_ID' in chunk.columns else None

                    if prefix == 'PONNOT':
                        df_neg = pandas.DataFrame({
                            'cod_id': cod_id_col,
                            'altura': clean_num(chunk['ALT']) if 'ALT' in chunk.columns else None,
                            'material': chunk['MAT'].str.strip() if 'MAT' in chunk.columns else None,
                            'esforco': clean_num(chunk['EST']) if 'EST' in chunk.columns else None,
                            'latitude': chunk['latitude'],
                            'longitude': chunk['longitude'],
                            'registro_atual': True,
                            'lote_carga': lote_atual
                        })
                    elif prefix == 'SUB':
                        df_neg = pandas.DataFrame({
                            'cod_id': cod_id_col,
                            'nome': chunk['NOME'].str.strip() if 'NOME' in chunk.columns else None,
                            'latitude': chunk['latitude'],
                            'longitude': chunk['longitude'],
                            'registro_atual': True,
                            'lote_carga': lote_atual
                        })
                    elif prefix == 'UNSEAT':
                        tip_unid = clean_num(chunk['TIP_UNID'], is_int=True).fillna(0) if 'TIP_UNID' in chunk.columns else 0
                        df_neg = pandas.DataFrame({
                            'cod_id': cod_id_col,
                            'id_tipo_dispositivo': tip_unid,
                            'subestacao': chunk['SUB'].str.strip() if 'SUB' in chunk.columns else None,
                            'codigo_conjunto_aneel': clean_num(chunk['CONJ'], is_int=True) if 'CONJ' in chunk.columns else None,
                            'latitude': chunk['latitude'],
                            'longitude': chunk['longitude'],
                            'registro_atual': True,
                            'lote_carga': lote_atual
                        })

                    buf_pos = StringIO()
                    df_pos[['tipo_posicao', 'latitude', 'longitude', 'municipio', 'id_distribuidora', 'are_loc', 'registro_atual', 'lote_carga']].to_csv(buf_pos, index=False, header=False, sep='\t')
                    buf_pos.seek(0)
                    
                    cur.copy_expert("""
                        COPY posicoes_geograficas (tipo_posicao, latitude, longitude, municipio, id_distribuidora, are_loc, registro_atual, lote_carga)
                        FROM STDIN WITH (FORMAT csv, DELIMITER '\t', NULL '');
                    """, buf_pos)

                    if prefix == 'PONNOT':
                        cur.execute("DROP TABLE IF EXISTS temp_postes;")
                        cur.execute("CREATE TEMP TABLE temp_postes (cod_id VARCHAR(50), altura NUMERIC, material VARCHAR(50), esforco NUMERIC, latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, registro_atual BOOLEAN, lote_carga VARCHAR(20)) ON COMMIT DROP;")
                        buf_neg = StringIO()
                        df_neg.to_csv(buf_neg, index=False, header=False, sep='\t')
                        buf_neg.seek(0)
                        cur.copy_expert("COPY temp_postes FROM STDIN WITH (FORMAT csv, DELIMITER '\t', NULL '');", buf_neg)

                        cur.execute("""
                            INSERT INTO postes (cod_id, altura, material, esforco, id_posicao, registro_atual, lote_carga)
                            SELECT t.cod_id, t.altura, t.material, t.esforco, g.id_posicao, t.registro_atual, t.lote_carga
                            FROM temp_postes t
                            JOIN posicoes_geograficas g 
                              ON g.latitude = t.latitude 
                             AND g.longitude = t.longitude 
                             AND g.tipo_posicao = 'POSTE' 
                             AND g.lote_carga = t.lote_carga
                             AND g.registro_atual = TRUE;
                        """)

                    elif prefix == 'SUB':
                        cur.execute("DROP TABLE IF EXISTS temp_sub;")
                        cur.execute("CREATE TEMP TABLE temp_sub (cod_id VARCHAR(50), nome VARCHAR(100), latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, registro_atual BOOLEAN, lote_carga VARCHAR(20)) ON COMMIT DROP;")
                        buf_neg = StringIO()
                        df_neg.to_csv(buf_neg, index=False, header=False, sep='\t')
                        buf_neg.seek(0)
                        cur.copy_expert("COPY temp_sub FROM STDIN WITH (FORMAT csv, DELIMITER '\t', NULL '');", buf_neg)

                        cur.execute("""
                            INSERT INTO subestacoes (cod_id, nome, id_posicao, registro_atual, lote_carga)
                            SELECT t.cod_id, t.nome, g.id_posicao, t.registro_atual, t.lote_carga
                            FROM temp_sub t
                            JOIN posicoes_geograficas g 
                              ON g.latitude = t.latitude 
                             AND g.longitude = t.longitude 
                             AND g.tipo_posicao = 'SUBESTACAO' 
                             AND g.lote_carga = t.lote_carga
                             AND g.registro_atual = TRUE;
                        """)

                    elif prefix == 'UNSEAT':
                        cur.execute("DROP TABLE IF EXISTS temp_disp;")
                        cur.execute("CREATE TEMP TABLE temp_disp (cod_id VARCHAR(50), id_tipo_dispositivo INT, subestacao VARCHAR(50), codigo_conjunto_aneel INT, latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, registro_atual BOOLEAN, lote_carga VARCHAR(20)) ON COMMIT DROP;")
                        buf_neg = StringIO()
                        df_neg.to_csv(buf_neg, index=False, header=False, sep='\t')
                        buf_neg.seek(0)
                        cur.copy_expert("COPY temp_disp FROM STDIN WITH (FORMAT csv, DELIMITER '\t', NULL '');", buf_neg)

                        cur.execute("""
                            INSERT INTO tipos_dispositivos (id_tipo_dispositivo, nome_dispositivo)
                            SELECT DISTINCT id_tipo_dispositivo, 'DISPOSITIVO ' || id_tipo_dispositivo
                            FROM temp_disp
                            WHERE id_tipo_dispositivo IS NOT NULL
                            ON CONFLICT (id_tipo_dispositivo) DO NOTHING;
                        """)

                        cur.execute("""
                            INSERT INTO dispositivos (cod_id, id_tipo_dispositivo, subestacao, codigo_conjunto_aneel, id_posicao, registro_atual, lote_carga)
                            SELECT t.cod_id, t.id_tipo_dispositivo, t.subestacao, t.codigo_conjunto_aneel, g.id_posicao, t.registro_atual, t.lote_carga
                            FROM temp_disp t
                            JOIN posicoes_geograficas g 
                              ON g.latitude = t.latitude 
                             AND g.longitude = t.longitude 
                             AND g.tipo_posicao = 'DISPOSITIVO' 
                             AND g.lote_carga = t.lote_carga
                             AND g.registro_atual = TRUE;
                        """)

            conn.commit()
            print(f"[SUCESSO] Camada {prefix} processada e gravada no banco com sucesso!")

        print("\nGerando geometrias PostGIS (ST_MakePoint)...")
        cur.execute("""
            UPDATE posicoes_geograficas 
            SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4674)
            WHERE geom IS NULL;
        """)

        conn.commit()
        print("\n[SUCESSO] Carga e geometrias geradas com sucesso!")

    except Exception as e:
        conn.rollback()
        print(f"\n[ERRO] Ocorreu uma falha no carregamento: {e}")
        raise e
    finally:
        cur.close()
        conn.close()

def load_municipios():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    GPKG_FILE = Path(__file__).resolve().parent.parent / "data" / "BR_localidades_2022.gpkg"
    gpkg_conn = None

    try:
        gpkg_conn = sqlite3.connect(GPKG_FILE)
        gpkg_cur = gpkg_conn.cursor()
        gpkg_cur.execute("SELECT table_name FROM gpkg_contents WHERE data_type IN ('features', 'attributes');")
        layer_names = [row[0] for row in gpkg_cur.fetchall()]

        mun_layer = None
        mun_columns = None

        for layer_name in layer_names:
            safe_layer = layer_name.replace('"', '""')
            gpkg_cur.execute(f'PRAGMA table_info("{safe_layer}")')
            columns = [row[1] for row in gpkg_cur.fetchall()]
            upper_columns = {column.upper(): column for column in columns}
            if all(column in upper_columns for column in ["CD_MUN", "NM_MUN", "SIGLA_UF"]):
                mun_layer = layer_name
                mun_columns = upper_columns
                break

        if mun_layer is None:
            raise RuntimeError("Nenhuma camada contendo CD_MUN, NM_MUN e SIGLA_UF foi encontrada.")

        print(f"\nCamada selecionada: {mun_layer}")

        layer_sql = mun_layer.replace('"', '""')
        cd_mun = mun_columns["CD_MUN"].replace('"', '""')
        nm_mun = mun_columns["NM_MUN"].replace('"', '""')
        sigla_uf = mun_columns["SIGLA_UF"].replace('"', '""')

        query = f"""
            SELECT
                "{cd_mun}",
                "{nm_mun}",
                "{sigla_uf}"
            FROM "{layer_sql}"
        """
        gpkg_cur.execute(query)
        rows = gpkg_cur.fetchall()

        registers = []
        for codigo_ibge, nome, uf in rows:
            if codigo_ibge is None or nome is None or uf is None:
                continue

            codigo_str = str(codigo_ibge).strip().split('.')[0]
            nome_str = str(nome).strip()
            uf_str = str(uf).strip()

            if not codigo_str.isdigit() or not nome_str or len(uf_str) != 2:
                continue

            registers.append((int(codigo_str), nome_str, uf_str))

        registers = list({row[0]: row for row in registers}.values())
        print(f"Municípios encontrados: {len(registers)}")

        execute_values(
            cur,
            """
                INSERT INTO municipios (codigo_ibge, nome, uf)
                VALUES %s
                ON CONFLICT (codigo_ibge)
                DO UPDATE SET
                    nome = EXCLUDED.nome,
                    uf = EXCLUDED.uf
            """,
            registers,
            page_size=5000
        )

        conn.commit()
        cur.execute("SELECT COUNT(*) FROM municipios")
        total = cur.fetchone()[0]
        print(f"Total de municípios inseridos: {total}")
    except Exception as e:
        conn.rollback()
        print(f"\n[ERRO] Ocorreu uma falha no carregamento: {e}")
        raise e
    finally:
        if gpkg_conn is not None:
            gpkg_conn.close()
        cur.close()
        conn.close()