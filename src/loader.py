import os
import json
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
    "port": os.getenv("DB_PORT", 5432),
    "sslmode": "require" if os.getenv("DB_SSL", "").lower() == "true" else "prefer",
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

def load_csv_to_postegres(bdgd_layer: str, table_name: str, columns: str, truncate_before: bool = True):
    target_folder = get_processed_folder()
    csv_files = glob.glob(os.path.join(target_folder, f"*_{bdgd_layer}.csv"))

    if not csv_files:
        raise FileNotFoundError(f"Nenhum arquivo CSV encontrado no camiminho especificado ({target_folder})")

    print(f"Conectando ao banco de dados.")
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    if truncate_before:
        print(f"Esvaziando a tabela {table_name} para inserir os dados da nova quinzena (TRUNCATE)...")
        cursor.execute(f"TRUNCATE TABLE raw.{table_name} RESTART IDENTITY;")
        conn.commit()

    cols_to_insert = ", ".join(columns)
    query = f"INSERT INTO raw.{table_name} ({cols_to_insert}) VALUES %s"

    for file in csv_files:
        print(f"Lendo e inserindo os dados do arquivo: {os.path.basename(file)}")
        df = pandas.read_csv(file, dtype=str)
        df.columns = df.columns.str.upper()
        df = df.where(pandas.notnull(df), None)

        records = []
        for row in df.itertuples(index=False):
            record = tuple(getattr(row, col, None) for col in columns)
            records.append(record)

        execute_values(cursor, query, records, page_size=10000)
        conn.commit()
        print(f"[CONCLUÍDO] - {len(df)} dados inseridos com sucesso!")

    cursor.close()
    conn.close()
    print(f"Carga da tabela raw.{table_name} finalizada!")

def clean_num(series, is_int=False):
    """Trata valores nulos, vírgulas e converte para numérico de forma rápida."""
    if series is None or series.empty:
        return pandas.Series(dtype='object')
    s = series.astype(str).str.strip().str.replace(',', '.')
    s = s.replace(['nan', 'NaN', 'None', '', 'null', '<NA>'], None)
    if is_int:
        return pandas.to_numeric(s, errors='coerce').astype('Int64')
    return pandas.to_numeric(s, errors='coerce')

def distributor_from_filename(file_path: str) -> str:
    filename = os.path.basename(file_path).casefold()
    if "enel_sp" in filename:
        return "Enel SP"
    if "edp_sp" in filename:
        return "EDP SP"
    if "energisa_minas_rio" in filename:
        return "Energisa Minas Rio"
    return "Desconhecida"


def selected_distributors() -> set[str] | None:
    configured = os.getenv("BDGD_DISTRIBUIDORAS")
    if not configured:
        return None
    values = {value.strip() for value in configured.split(",") if value.strip()}
    return values or None


def load_all_csvs_directly(data_folder_path: str, lote_atual: str):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        cur.execute("SET synchronous_commit = OFF;")
        cur.execute(
            "TRUNCATE TABLE postes, subestacoes, dispositivos, "
            "transformadores, reguladores, "
            "posicoes_geograficas RESTART IDENTITY CASCADE;"
        )
        cur.execute("TRUNCATE TABLE ativos_rede RESTART IDENTITY;")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_posicoes_geograficas_lookup
                ON posicoes_geograficas
                    (latitude, longitude, tipo_posicao, lote_carga, registro_atual);
        """)
        
        layers_config = {
            'PONNOT': {'tipo_pos': 'POSTE'},
            'SUB':     {'tipo_pos': 'SUBESTACAO'},
            'UNTRD':   {'tipo_pos': 'TRANSFORMADOR'},
            'UNSEAT':  {'tipo_pos': 'DISPOSITIVO'},
            'UNCR':    {'tipo_pos': 'DISPOSITIVO'},
            'UNREGT':  {'tipo_pos': 'REGULADOR_TENSAO'}
        }
        device_layers = {'UNSEAT', 'UNCR'}
        ativos_rede = []
        allowed_distributors = selected_distributors()

        for prefix, cfg in layers_config.items():
            csv_files = glob.glob(os.path.join(data_folder_path, f"*{prefix}*.csv"))
            
            if not csv_files:
                print(f"[AVISO] Nenhum arquivo encontrado para a camada {prefix}")
                continue

            print(f"\n--- Processando {len(csv_files)} arquivos da camada {prefix} ---")
            
            list_posicoes = []
            list_negociais = []

            for file_path in tqdm(csv_files, desc=f"Lendo CSVs {prefix}"):
                distributor = distributor_from_filename(file_path)
                if allowed_distributors is not None and distributor not in allowed_distributors:
                    continue

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
                df['distribuidora'] = distributor

                if df.empty:
                    continue

                df_pos = pandas.DataFrame({
                    'latitude': df['latitude'],
                    'longitude': df['longitude'],
                    'tipo_posicao': cfg['tipo_pos'],
                    'municipio': df['MUN'].str.strip() if 'MUN' in df.columns else None,
                    'bairro': df['BAIRRO'].str.strip() if 'BAIRRO' in df.columns else None,
                    'distribuidora': df['distribuidora'],
                    'registro_atual': True,
                    'lote_carga': lote_atual
                })
                list_posicoes.append(df_pos)

                tipo_ativo = cfg['tipo_pos']
                if prefix in device_layers:
                    tipo_ativo = 'DISPOSITIVO'
                for row in df.to_dict('records'):
                    atributos = {
                        str(key).lower(): (
                            None if pandas.isna(value) else value
                        )
                        for key, value in row.items()
                        if key not in {'X', 'Y', 'latitude', 'longitude',
                                       'COD_ID', 'MUN', 'BAIRRO'}
                    }
                    ativos_rede.append((
                        str(row.get('COD_ID', '')).strip() or None,
                        tipo_ativo,
                        prefix,
                        float(row['latitude']),
                        float(row['longitude']),
                        str(row.get('MUN', '')).strip() or None,
                        str(row.get('BAIRRO', '')).strip() or None,
                        df['distribuidora'].iloc[0],
                        json.dumps(atributos, default=str),
                        True,
                        lote_atual,
                    ))

                cod_id_col = df['COD_ID'].str.strip() if 'COD_ID' in df.columns else None

                if prefix == 'PONNOT':
                    df_neg = pandas.DataFrame({
                        'cod_id': cod_id_col,
                        'altura': clean_num(df['ALT']) if 'ALT' in df.columns else None,
                        'material': df['MAT'].str.strip() if 'MAT' in df.columns else None,
                        'esforco': clean_num(df['ESF']) if 'ESF' in df.columns else None,
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

                elif prefix in device_layers:
                    tip_unid = clean_num(df['TIP_UNID'], is_int=True).fillna(0) if 'TIP_UNID' in df.columns else 0
                    tip_unid = tip_unid.where(tip_unid.between(0, 43), 0)
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

                elif prefix == 'UNTRD':
                    df_neg = pandas.DataFrame({
                        'cod_id': cod_id_col,
                        'potencia_nominal': clean_num(df['POT_NOM']) if 'POT_NOM' in df.columns else None,
                        'ponto_alimentacao_1': df['PAC_1'].str.strip() if 'PAC_1' in df.columns else None,
                        'ponto_alimentacao_2': df['PAC_2'].str.strip() if 'PAC_2' in df.columns else None,
                        'subestacao': df['SUB'].str.strip() if 'SUB' in df.columns else None,
                        'codigo_conjunto_aneel': clean_num(df['CONJ'], is_int=True) if 'CONJ' in df.columns else None,
                        'latitude': df['latitude'],
                        'longitude': df['longitude'],
                        'registro_atual': True,
                        'lote_carga': lote_atual
                    })
                    list_negociais.append(df_neg)

                elif prefix == 'UNREGT':
                    df_neg = pandas.DataFrame({
                        'cod_id': cod_id_col,
                        'potencia_nominal': clean_num(df['POT_NOM']) if 'POT_NOM' in df.columns else None,
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

            df_full_pos = pandas.concat(list_posicoes, ignore_index=True).drop_duplicates(
                subset=['latitude', 'longitude', 'tipo_posicao', 'distribuidora']
            )
            df_full_neg = (
                pandas.concat(list_negociais, ignore_index=True)
                if list_negociais else pandas.DataFrame()
            )

            print(f"Inserindo {len(df_full_pos)} posições no banco...")
            buf_pos = StringIO()
            df_full_pos[
                ['tipo_posicao', 'latitude', 'longitude', 'municipio', 'bairro', 'distribuidora',
                 'registro_atual', 'lote_carga']
            ].to_csv(buf_pos, index=False, header=False, sep='\t')
            buf_pos.seek(0)
            
            cur.copy_expert("""
                COPY posicoes_geograficas (tipo_posicao, latitude, longitude, municipio, bairro, distribuidora, registro_atual, lote_carga)
                FROM STDIN WITH (FORMAT csv, DELIMITER '\t', NULL '');
            """, buf_pos)
            cur.execute("ANALYZE posicoes_geograficas;")

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

            elif prefix == 'UNTRD':
                cur.execute("CREATE TEMP TABLE temp_transformadores (cod_id VARCHAR(80), potencia_nominal NUMERIC, ponto_alimentacao_1 VARCHAR(80), ponto_alimentacao_2 VARCHAR(80), subestacao VARCHAR(80), codigo_conjunto_aneel INT, latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, registro_atual BOOLEAN, lote_carga VARCHAR(20)) ON COMMIT DROP;")
                buf_neg = StringIO()
                df_full_neg.to_csv(buf_neg, index=False, header=False, sep='\t')
                buf_neg.seek(0)
                cur.copy_expert("COPY temp_transformadores FROM STDIN WITH (FORMAT csv, DELIMITER '\t', NULL '');", buf_neg)
                cur.execute("""
                    INSERT INTO transformadores (
                        cod_id, potencia_nominal, ponto_alimentacao_1,
                        ponto_alimentacao_2, subestacao, codigo_conjunto_aneel,
                        id_posicao, registro_atual, lote_carga
                    )
                    SELECT t.cod_id, t.potencia_nominal, t.ponto_alimentacao_1,
                           t.ponto_alimentacao_2, t.subestacao,
                           t.codigo_conjunto_aneel, g.id_posicao,
                           t.registro_atual, t.lote_carga
                    FROM temp_transformadores t
                    JOIN posicoes_geograficas g
                      ON g.latitude = t.latitude
                     AND g.longitude = t.longitude
                     AND g.tipo_posicao = 'TRANSFORMADOR'
                     AND g.lote_carga = t.lote_carga
                     AND g.registro_atual = TRUE;
                """)

            elif prefix == 'UNREGT':
                cur.execute("CREATE TEMP TABLE temp_reguladores (cod_id VARCHAR(80), potencia_nominal NUMERIC, subestacao VARCHAR(80), codigo_conjunto_aneel INT, latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, registro_atual BOOLEAN, lote_carga VARCHAR(20)) ON COMMIT DROP;")
                buf_neg = StringIO()
                df_full_neg.to_csv(buf_neg, index=False, header=False, sep='\t')
                buf_neg.seek(0)
                cur.copy_expert("COPY temp_reguladores FROM STDIN WITH (FORMAT csv, DELIMITER '\t', NULL '');", buf_neg)
                cur.execute("""
                    INSERT INTO reguladores (
                        cod_id, potencia_nominal, subestacao,
                        codigo_conjunto_aneel, id_posicao,
                        registro_atual, lote_carga
                    )
                    SELECT t.cod_id, t.potencia_nominal, t.subestacao,
                           t.codigo_conjunto_aneel, g.id_posicao,
                           t.registro_atual, t.lote_carga
                    FROM temp_reguladores t
                    JOIN posicoes_geograficas g
                      ON g.latitude = t.latitude
                     AND g.longitude = t.longitude
                     AND g.tipo_posicao = 'REGULADOR_TENSAO'
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

            elif prefix in device_layers:
                cur.execute("DROP TABLE IF EXISTS temp_disp;")
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

        if ativos_rede:
            execute_values(
                cur,
                """
                INSERT INTO ativos_rede (
                     cod_id, tipo_ativo, camada_origem, latitude, longitude,
                     municipio, bairro, distribuidora, atributos, registro_atual, lote_carga
                ) VALUES %s
                """,
                ativos_rede,
                page_size=5000,
            )
            print(f"Inserindo {len(ativos_rede)} ativos detalhados...")

        print("\nGerando geometrias PostGIS (ST_MakePoint)...")
        cur.execute("""
            UPDATE posicoes_geograficas 
            SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
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