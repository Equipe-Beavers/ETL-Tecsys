from datetime import datetime
import tempfile
import os
import requests
import zipfile
import shutil

def get_data_folder():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root =  os.path.dirname(current_dir)
    data_folder = os.path.join(project_root, "data")
    os.makedirs(data_folder, exist_ok=True)
    return data_folder

def download_catalog():
    catalog_url = "https://hub.arcgis.com/api/feed/all/csv?target=dadosabertos-aneel.opendata.arcgis.com&usePortal=true"
    data_folder = get_data_folder()
    filename = "catalog_bdgd.csv"
    full_path = os.path.join(data_folder, filename)
    try:
        response = requests.get(catalog_url, stream=True)
        if response.status_code == 200:
            with open(full_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
        else:
            raise ValueError(f"Erro HTTP - {response.status_code}")
    except Exception as e:
        raise ValueError(f"Ocorreu um erro ao baixar o arquivo - {e}")
    return full_path

def get_raw_paste() -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)

    raw_paste = os.path.join(project_root, "data", "raw")
    os.makedirs(raw_paste, exist_ok=True)

    return raw_paste

def download_and_extract_zip(url: str, temp_file_name: str = "temp_data.zip") -> str:
    raw_paste = get_raw_paste()
    zip_dir = os.path.join(raw_paste, temp_file_name)

    response = requests.get(url, stream=True)
    response.raise_for_status()

    with open(zip_dir, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file.write(chunk)

    with zipfile.ZipFile(zip_dir, "r") as zip_ref:
        zip_ref.extractall(raw_paste)

    os.remove(zip_dir)

    return raw_paste

def extract_zip(zip_path: str, extract_to: str):
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
            extracted_files = [os.path.join(extract_to, filename) for filename in zip_ref.namelist()]

            return extracted_files
    except zipfile.BadZipFile:
        raise ValueError("O arquivo enviado não é um ZIP válido ou está corrompido.")
    except Exception as e:
        raise ValueError(f"Erro ao descompactar arquivo zip {str(e)}")

def clean_raw_paste():
    raw_paste = get_raw_paste()
    for item in os.listdir(raw_paste):
        item_dir = os.path.join(raw_paste, item)
        if os.path.isfile(item_dir) or os.path.islink(item_dir):
            os.unlink(item_dir)
        elif os.path.isdir(item_dir):
            shutil.rmtree(item_dir)
