from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

from src.anatel_extractor import iterar_csv, preparar_arquivo
from src.anatel_loader import conectar_banco, salvar_lote, verificar_tabela
from src.anatel_transformer import transformar_lote

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def importar_antenas() -> None:
    load_dotenv(PROJECT_ROOT / ".env", encoding="utf-8")
    caminho_csv, temporario = preparar_arquivo()
    conexao = None
    processados = 0
    descartados = 0

    try:
        print(f"[EXTRAÇÃO] CSV da Anatel: {caminho_csv}")
        conexao = conectar_banco(PROJECT_ROOT)
        verificar_tabela(conexao)

        for numero_lote, chunk in enumerate(iterar_csv(caminho_csv), start=1):
            registros, invalidos = transformar_lote(chunk)
            descartados += invalidos
            carregados = salvar_lote(conexao, registros)
            processados += carregados
            if carregados:
                print(f"Lote {numero_lote}: {carregados} registros carregados/atualizados.")

        print(
            "Importação concluída. "
            f"Registros processados: {processados}; "
            f"descartados por coordenadas inválidas: {descartados}."
        )
    except Exception:
        if conexao is not None:
            conexao.rollback()
        raise
    finally:
        if conexao is not None:
            conexao.close()
        if temporario is not None:
            temporario.cleanup()


if __name__ == "__main__":
    importar_antenas()
