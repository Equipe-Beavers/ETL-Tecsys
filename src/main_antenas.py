"""Ponto de entrada isolado para executar a carga de antenas em processo próprio.

Execução, na raiz de ETL-Tecsys: python -m src.main_antenas
"""

from src.importar_antenas import importar_antenas


if __name__ == "__main__":
    importar_antenas()
