from fastapi import FastAPI, Form, UploadFile, File, HTTPException
from src.extractor import extract_zip
from src.transformer import transform_bdgd_into_json
import zipfile
import tempfile
import re
import os

app = FastAPI()

@app.post("/process-file")
async def process_file(file: UploadFile = File(...), bdgd_version: str = Form(...)):
    file_name = os.path.splitext(os.path.splitext(file.filename)[0])[0]
    match_id = re.search(r"_(\d+)_", file_name)
    distributor_id = match_id.group(1)
    file_extension = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
        while chunk := await file.read(1024 * 1024):
            temp_file.write(chunk)
        temp_file_path = temp_file.name
    try:
        with tempfile.TemporaryDirectory() as extract_dir:
            if zipfile.is_zipfile(temp_file_path):
                extract_zip(temp_file_path, extract_dir)
            else:
                dest_path = os.path.join(extract_dir, file.filename)
                os.rename(temp_file_path, dest_path)
            gdb_json_data = transform_bdgd_into_json(extract_dir, bdgd_version, distributor_id)
            return gdb_json_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no processamento ETL do arquivo: {str(e)}")
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)