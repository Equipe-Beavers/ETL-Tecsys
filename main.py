from src.extractor import clean_raw_paste, download_and_extract_zip
from src.transformer import transform_bdgd_layer
from src.loader import save_to_csv, get_processed_folder, load_all_csvs_directly
from datetime import datetime

BDGD_URL = [
    ["https://www.arcgis.com/sharing/rest/content/items/f7ef6c74ffe74311bb20ef0b83e4070e/data", "Sulgipe_46_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/7d14b859a5934148bde30b2430546b84/data", "Santa_Maria_381_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/676f1716658f47a3b5c8fb8c44c702c0/data", "Roraima_Energia_370_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/19380ec7194a49409c429a149e2c50be/data", "RGE_396_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/e3a518b754ff42fcaf0232003c0b1e9d/data", "Nova_Palma_400_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/a36b00f67b394ff8977cbacb6d278901/data", "Neoenergia_Pernambuco_43_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/0fe22aa2b53c4dacba9b106a10d1c452/data", "Neoenergia_Elektro_385_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/c48b4751afdf41c29923986308e15f44/data", "Neoenergia_Cosern_40_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/8ec3cae3b0ce4d3c8f6536eedf49c9f3/data", "Neoenergia_Coelba_47_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/b6bfc6df4fb44fb393a0c026cf688ced/data", "Neoenergia_Brasilia_5160_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/42482341e0d643eeab286de22fc0dff8/data", "Mux_Energia_401_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/430f90486174407aabe3b07f50ca6150/data", "Light_382_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/3587012de8864d98ae8c4cb77902d4e3/data", "Joao_Cesa_88_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/bf846d18b9e84fa6991bd76af0fc9f44/data", "Hidropan_399_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/cd6c8ecb86c2427493cf4a0d129c2eb4/data", "Forcel_83_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/2b040141e900476586c9bbda852cc264/data", "Equatorial_PI_38_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/0c8dad27817e42aba122b55511e09359/data", "Equatorial_PA_371_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/0abd1d2ff8ec4ab8abedbc96979f0946/data", "Equatorial_MA_37_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/32ecb2c820a742bfbfa077af69c82245/data", "Equatorial_GO_6072_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/cb77602aaeb34bcfa36b822a964dd1a8/data", "Equatorial_AL_44_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/e9a7bd0056174a8da1a5662135056766/data", "Energisa_TO_32_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/98af349591824f7fa42662bbda161b90/data", "Energisa_Sul-Sudeste_5216_2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/6763d91cf46d4562966bd1ad0680f849/data", "Energisa SE 6587 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/23404e39bdc14e92a4d0f087ad84e28b/data", "Energisa RO 369 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/fedab1bd01f849dfa5167c5ce4e92729/data", "Energisa PB 6600 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/02a120db1b5149709f8d371c21635adc/data", "Energisa MT 405 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/9a1ce360865f4358b31e9fb2d016aac9/data", "Energisa MS 404 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/e4127432837e47b48c30c97a2b2dbdb5/data", "Energisa Minas Rio 6585 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/f422f058b473405d9eb39b005c2ba1b3/data", "Energisa AC 26 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/837ab21a1e684f448df2f73d709b6fd9/data", "Enel SP 390 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/32a52a0b29df4b82b9e63362bc927267/data", "Enel RJ 383 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/c57f0c3389a94f21af1e0df99eca2b4f/data", "Enel CE 39 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/22d8a085b8264dae8a77983de348fba6/data", "Eletrocar 398 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/04a736e95f114c32a56206957a492cba/data", "Eflul 86 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/73847c48c58847a7ad6fa725d1d20d51/data", "EDP SP 391 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/1929128a61ba4e10af33178c2d106013/data", "EDP ES 380 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/44ccd59a1cba4e019a258b3e58fea420/data", "Dmed 51 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/35dafef5fcb94c3485ceec799199373d/data", "Demei 95 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/7ebf8b3ffa9145f0b3dbe626dac18f92/data", "Dcelt 87 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/740a0f26c53f4cacac6ce9588b411e17/data", "Creral 2783 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/0d8ca0795ce9453fbe779fd69d0334ed/data", "Creluz-D 598 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/27d4c45e0074491d94bf6a911b286f84/data", "CPFL Santa Cruz 69 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/75863ef447904bbdacc1435e7f47d43a/data", "CPFL Piratininga 2937 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/9a74b75af3634b06b0967b8acd882386/data", "CPFL Paulista 63 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/fb3fa39c507d45e09abb2608cad0c884/data", "Coprel 2351 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/5b9890585186452c8e78dfac89bf9519/data", "Copel-Dis 2866 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/1594a3ae1b4d442daa81d621c47f02fc/data", "Coorsel 7016 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/02b5591ba172448396d2eada7085cc7f/data", "Cooperzem 5374 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/3bc6806896e843b6924697ff60e36a64/data", "Coopersul 5346 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/325005059a3a4606ac5657a3893827e0/data", "Coopernorte 5345 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/5ae4d37c6cd9401db42aeeff9ef2ae33/data", "Coopermila 5373 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/257d8db7726244699e96b1c369ee33b4/data", "Cooperluz 3627 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/acfd8bc19135418b857a9df31546a767/data", "Coopercocal 5371 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/5d0f7ea5db5d48aeb365998fabaa9db7/data", "Coopera 5370 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/082e3f3526254aafbca5ac8ade674e02/data", "Cocel 82 2025-12-31 V11"],
    ["https://www.arcgis.com/sharing/rest/content/items/26f6d3e8e9f74d89921e74eed6213545/data", "Chesp 103 2025-12-31 V11"],
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
        print("[FINALIZADO] - PROCESSO CONCLUÍDO!")
    except Exception as e:
        print(f"[AVISO] - FALHA NA EXECUÇÃO: {e}")
    
    

if __name__ == "__main__":
    run_pipeline()