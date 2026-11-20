from src.extractor import download_catalog, download_and_extract_zip, clean_raw_paste
from src.transformer import catalog_dataframe, format_catalog_data, get_data_by_date, transform_bdgd_layer, get_distributor_uf
from src.loader import save_to_csv, get_processed_folder, load_distributor, load_all_csvs_directly
from datetime import datetime
import re

TARGET_LAYERS = ["PONNOT", "UNSEAT", "SUB"]

def run_anual_pipeline():
    path = download_catalog()
    df = catalog_dataframe(path)
    formated_df = format_catalog_data(df)
    filtered_df = get_data_by_date(formated_df)

    download_url = f"https://www.arcgis.com/sharing/rest/content/items/"
    print(f"TOTAL DE BASE DE DADOS: {len(filtered_df)}")
    print("=" * 15 + "INICIANDO PIPELINE - ETL (BDGD)" + "=" * 15)
    for distributor in range(len(filtered_df)):
        print("#" * 60)
        print(f"[INICIADO] - PROCESSANDO BASE [{distributor + 1}/{len(filtered_df)}] - {filtered_df.iloc[distributor]["title"]}")
        match = re.search(r"(.+)_(\d+)_", filtered_df.iloc[distributor]["title"])
        if not match:
            raise ValueError("A distribuidora não possui nome nem ID.")
        distributor_name = match.group(1).replace("_", " ")
        distributor_id = int(match.group(2))
        try:
            print("\nETAPA [1/3] - EXTRAÇÃO")
            download_and_extract_zip(download_url + f"{filtered_df.iloc[distributor]["id"]}/data")
            print("\nETAPA [2/3] - TRANSFORMAÇÃO")
            for layer in TARGET_LAYERS:
                print(f"Extraindo dados da camada: {layer}")
                try:
                    df, base_name = transform_bdgd_layer(layer)
                    if layer == "PONNOT":
                        distributor_uf = get_distributor_uf(df.iloc[0, 4])
                        load_distributor(distributor_id, distributor_name, distributor_uf)
                    csv_path = save_to_csv(df, base_name, layer)
                    print(f"Arquivo gerado: {csv_path}")
                except Exception as e:
                    print(F"\n[AVISO] - FALHA NA CAMADA '{layer}' em '{filtered_df.iloc[distributor]['title']}' | [ERRO] - {e}")
        except Exception as e:
            print(f"\n[ERRO] - Falha ao processar dados de {filtered_df.iloc[distributor]['title']}: {e}")
        finally:
            print("\nLIMPANDO PASTAS TEMPORÁRIAS (.zip) DE '/data/raw'")
            clean_raw_paste()
    print("\nETAPA [3/3] - CARGA")
    print("#" * 60)
    print("=" * 20 + "INICIANDO CARGA NO BANCO DE DADOS" + 20 * "=")
    folder_path = get_processed_folder()
    now = datetime.now()
    insert_data = f"{now.year}_{now.month:02d}_{now.day:02d}"
    print("[INICIADO] - CARGA DIRETA (CSV -> BANCO DE DADOS)")
    folder_path = get_processed_folder()
    now = datetime.now()
    insert_data = f"{now.year}_{now.month:02d}_{now.day:02d}"
    try:
        print(f"[INSERINDO] - INSERINDO DADOS DAS DISTRIBUIDORAS")
        load_all_csvs_directly(folder_path, insert_data)
        print("[FINALIZADO] - INSERÇÃO DOS DAOS CONCLUÍDA!")
    except Exception as e:
        print(f"[AVISO] - FALHA NA EXECUÇÃO: {e}")

if __name__ == "__main__":
    run_anual_pipeline()