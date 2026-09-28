from src.extractor import clean_raw_paste, download_and_extract_zip
from src.transformer import transform_bdgd_layer
from src.loader import save_to_csv, get_processed_folder, load_all_csvs_directly, carregar_ativos_rede
from datetime import datetime

BDGD_URL = [
    ["https://www.arcgis.com/sharing/rest/content/items/f7ef6c74ffe74311bb20ef0b83e4070e/data", "Sulgipe_46_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/7d14b859a5934148bde30b2430546b84/data", "Santa_Maria_381_2025-12-31 V11"]
]

TARGET_LAYERS = ["PONNOT", "UNTRD", "UNSEAT", "SUB", "UNREGT"]
LAYERS_CONFIG = [
    {
        "extension": "PONNOT",
        "table": "postes",
        "columns": ["Y", "X", "COD_ID", "DIST", "MUN", "ARE_LOC", "TIP_PN", "MAT", "EST", "ALT", "SITCONT", "CONJ"]
    },
    {
        "extension": "SUB",
        "table": "subestacoes",
        "columns": ["Y", "X", "COD_ID", "DIST", "NOME"]
    },
    {
        "extension": "UNSEAT",
        "table": "dispositivos",
        "columns": ["Y", "X", "COD_ID", "DIST", "MUN", "TIP_UNID", "SUB", "CONJ"]
    }
]

def run_pipeline():
    print(F"TOTAL DE BASES DE DADOS: {len(BDGD_URL)}")
    print("=" * 15 + "INICIANDO PIPELINE - ETL (BDGD)" + "=" * 15)
    for index, (url, nome_distribuidora) in enumerate(BDGD_URL, 1):
        print("#" * 60)
        print(f"[INICIADO] - PROCESSANDO BASE [{index}/{len(BDGD_URL)}] - {nome_distribuidora}")
        try:
            print("\nETAPA [1/3] - EXTRAÇÃO")
            download_and_extract_zip(url)
            print("\nETAPA [2/3]")
            for layer in TARGET_LAYERS:
                print(f"Camada de extração: {layer}")
                try:
                    df_posts, base_name = transform_bdgd_layer(layer)
                    print("\nETAPA [3/3]")
                    csv_path = save_to_csv(df_posts, base_name, layer)
                    print(f"Arquivo gerado: {csv_path}")
                except Exception as e:
                    print(f"[AVISO] - Falha na camada '{layer} em {nome_distribuidora} | [ERRO] - {e}.")
            print(f"[CONCLUIDO] - ETL {nome_distribuidora} finalizado!")
        except Exception as e:
            print(f"\n[ERRO] - Falha ao processar dados de {nome_distribuidora}: {e}")
        finally:
            print("\nLimpando pastas temporárias (.zip) de 'data/raw/'")
            clean_raw_paste()
    print("\n" + "=" * 20 + "ETL GERAL FINALIZADO" + "=" * 20)
    print("\n")
    print("=" * 15 + "INICIANDO INSERÇÃO DOS DADOS NO BANCO" + "=" * 15)
    folder_path = get_processed_folder()
    now = datetime.now()
    insert_data = f"{now.year}_{now.month:02d}_{now.day:02d}"
    print("[INICIADO] - CARGA DIRETA INICIADA (CSV -> BANCO DE DADOS)")
    try:
        load_all_csvs_directly(folder_path, insert_data)
        carregar_ativos_rede(folder_path, insert_data)
        print("[FINALIZADO] - PROCESSO CONCLUÍDO!")
    except Exception as e:
        print(f"[AVISO] - FALHA NA EXECUÇÃO: {e}")
    
    

if __name__ == "__main__":
    run_pipeline()