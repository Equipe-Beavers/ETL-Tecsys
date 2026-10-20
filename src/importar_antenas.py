"""Orquestra a importação de emissões RF exportadas do Spectrum-E da Anatel."""
from __future__ import annotations

from pathlib import Path
import os

from dotenv import load_dotenv

from src.anatel_extractor import iterar_csv, preparar_arquivo
from src.anatel_loader import conectar_banco, salvar_lote, verificar_tabela
from src.anatel_transformer import transformar_lote

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def importar_antenas() -> None:
    load_dotenv(PROJECT_ROOT / ".env", encoding="utf-8", override=False)
    caminho_csv, temporario = preparar_arquivo()
    conexao = None
    processados = 0
    descartados = 0
    rf_incompletos = 0
    rotulo = os.getenv("ANATEL_DATASET_LABEL", "LICENCIADAS").strip().upper()

    try:
        print(f"[EXTRAÇÃO] Exportação Spectrum-E: {caminho_csv}")
        print(f"[FONTE] ANATEL_DATASET_LABEL={rotulo or 'LICENCIADAS'}")
        conexao = conectar_banco(PROJECT_ROOT)
        verificar_tabela(conexao)

        for numero_lote, chunk in enumerate(iterar_csv(caminho_csv), start=1):
            registros, invalidos, incompletos = transformar_lote(chunk)
            descartados += invalidos
            rf_incompletos += incompletos
            carregados = salvar_lote(conexao, registros)
            processados += carregados
            if carregados:
                print(f"Lote {numero_lote}: {carregados} registros inseridos/atualizados.")

        print(
            "Importação concluída. "
            f"Registros processados: {processados}; "
            f"descartados por coordenadas inválidas: {descartados}; "
            f"registros sem frequência TX ou potência: {rf_incompletos}."
        )
        if rf_incompletos:
            print("Aviso: esses registros foram mantidos, mas não têm todos os parâmetros básicos para estimar RF.")
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
