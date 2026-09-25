import os
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
            csv_files = glob.glob(os.path.join(data_folder_path, f"*{prefix}*.csv"))
            
            if not csv_files:
                print(f"[AVISO] Nenhum arquivo encontrado para a camada {prefix}")
                continue

            print(f"\n--- Processando {len(csv_files)} arquivos da camada {prefix} ---")
            
            list_posicoes = []
            list_negociais = []

            for file_path in tqdm(csv_files, desc=f"Lendo CSVs {prefix}"):
                df = None
                for enc in ['cp1252', 'latin1', 'iso-8859-1', 'utf-8-sig']:
                    try:
                        df = pandas.read_csv(file_path, sep=';', dtype=str, encoding=enc, engine='python')
                        if len(df.columns) <= 1:
                            df = pandas.read_csv(file_path, sep=',', dtype=str, encoding=enc, engine='python')
                        break
                    except (UnicodeDecodeError, Exception):
                        continue

                if df is None or df.empty:
                    continue

                df.columns = df.columns.str.strip().str.upper()

                col_y = 'Y' if 'Y' in df.columns else ('LATITUDE' if 'LATITUDE' in df.columns else None)
                col_x = 'X' if 'X' in df.columns else ('LONGITUDE' if 'LONGITUDE' in df.columns else None)

                if not col_y or not col_x:
                    print(f"\n[PULANDO] Arquivo {os.path.basename(file_path)} não possui colunas X/Y válidas.")
                    continue

                df['latitude'] = clean_num(df[col_y])
                df['longitude'] = clean_num(df[col_x])
                df = df.dropna(subset=['latitude', 'longitude'])

                if df.empty:
                    continue

                df_pos = pandas.DataFrame({
                    'latitude': df['latitude'],
                    'longitude': df['longitude'],
                    'tipo_posicao': cfg['tipo_pos'],
                    'municipio': df['MUN'].str.strip() if 'MUN' in df.columns else None,
                    'registro_atual': True,
                    'lote_carga': lote_atual
                })
                list_posicoes.append(df_pos)

                cod_id_col = df['COD_ID'].str.strip() if 'COD_ID' in df.columns else None

                if prefix == 'PONNOT':
                    df_neg = pandas.DataFrame({
                        'cod_id': cod_id_col,
                        'altura': clean_num(df['ALT']) if 'ALT' in df.columns else None,
                        'material': df['MAT'].str.strip() if 'MAT' in df.columns else None,
                        'esforco': clean_num(df['EST']) if 'EST' in df.columns else None,
                        'latitude': df['latitude'],
                        'longitude': df['longitude'],
                        'registro_atual': True,
                        'lote_carga': lote_atual
                    })
                    list_negociais.append(df_neg)

                elif prefix == 'SUB':
                    df_neg = pandas.DataFrame({
                        'cod_id': cod_id_col,
                        'nome': df['NOME'].str.strip() if 'NOME' in df.columns else None,
                        'latitude': df['latitude'],
                        'longitude': df['longitude'],
                        'registro_atual': True,
                        'lote_carga': lote_atual
                    })
                    list_negociais.append(df_neg)

                elif prefix == 'UNSEAT':
                    tip_unid = clean_num(df['TIP_UNID'], is_int=True).fillna(0) if 'TIP_UNID' in df.columns else 0
                    df_neg = pandas.DataFrame({
                        'cod_id': cod_id_col,
                        'id_tipo_dispositivo': tip_unid,
                        'subestacao': df['SUB'].str.strip() if 'SUB' in df.columns else None,
                        'codigo_conjunto_aneel': clean_num(df['CONJ'], is_int=True) if 'CONJ' in df.columns else None,
                        'latitude': df['latitude'],
                        'longitude': df['longitude'],
                        'registro_atual': True,
                        'lote_carga': lote_atual
                    })
                    list_negociais.append(df_neg)

            if not list_posicoes:
                print(f"[AVISO] Nenhum dado válido extraído para a camada {prefix}")
                continue

            df_full_pos = pandas.concat(list_posicoes, ignore_index=True).drop_duplicates(subset=['latitude', 'longitude', 'tipo_posicao'])
            df_full_neg = pandas.concat(list_negociais, ignore_index=True)

            print(f"Inserindo {len(df_full_pos)} posições no banco...")
            buf_pos = StringIO()
            df_full_pos[['tipo_posicao', 'latitude', 'longitude', 'municipio', 'registro_atual', 'lote_carga']].to_csv(buf_pos, index=False, header=False, sep='\t')
            buf_pos.seek(0)
            
            cur.copy_expert("""
                COPY posicoes_geograficas (tipo_posicao, latitude, longitude, municipio, registro_atual, lote_carga)
                FROM STDIN WITH (FORMAT csv, DELIMITER '\t', NULL '');
            """, buf_pos)

            print(f"Inserindo {len(df_full_neg)} registros na tabela negocial...")
            
            if prefix == 'PONNOT':
                cur.execute("CREATE TEMP TABLE temp_postes (cod_id VARCHAR(50), altura NUMERIC, material VARCHAR(50), esforco NUMERIC, latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, registro_atual BOOLEAN, lote_carga VARCHAR(20)) ON COMMIT DROP;")
                buf_neg = StringIO()
                df_full_neg.to_csv(buf_neg, index=False, header=False, sep='\t')
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
                cur.execute("CREATE TEMP TABLE temp_sub (cod_id VARCHAR(50), nome VARCHAR(100), latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, registro_atual BOOLEAN, lote_carga VARCHAR(20)) ON COMMIT DROP;")
                buf_neg = StringIO()
                df_full_neg.to_csv(buf_neg, index=False, header=False, sep='\t')
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
                cur.execute("CREATE TEMP TABLE temp_disp (cod_id VARCHAR(50), id_tipo_dispositivo INT, subestacao VARCHAR(50), codigo_conjunto_aneel INT, latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, registro_atual BOOLEAN, lote_carga VARCHAR(20)) ON COMMIT DROP;")
                buf_neg = StringIO()
                df_full_neg.to_csv(buf_neg, index=False, header=False, sep='\t')
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

        print("\nGerando geometrias PostGIS (ST_MakePoint)...")
        cur.execute("""
            UPDATE posicoes_geograficas 
            SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4674)
            WHERE geom IS NULL;
        """)

        conn.commit()
        print("\n[SUCESSO] Carga executada com sucesso!")

    except Exception as e:
        conn.rollback()
        print(f"\n[ERRO] Ocorreu uma falha no carregamento: {e}")
        raise e
    finally:
        cur.close()
        conn.close()
