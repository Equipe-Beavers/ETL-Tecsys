import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from src.anatel_transformer import COLUNAS_DADOS, transformar_lote
from src.anatel_extractor import iterar_csv


class TransformadorSpectrumETest(unittest.TestCase):
    def test_preserva_parametros_tecnicos_por_registro_de_emissao(self):
        df = pd.DataFrame([{
            "Status": "LIC-LIC-01",
            "Entidade": "Operadora Exemplo",
            "Fistel": "50400000000",
            "Num. Serviço": "010",
            "Ato de RF": "123456",
            "Num. Estação": "2119",
            "UF": "SP",
            "Município": "São José dos Campos",
            "Emissão": "10M0G7W",
            "Tecnologia": "LTE",
            "TipoTecnologia": "4G",
            "Freq. TX (MHz)": "2655",
            "Freq. RX (MHz)": "2535",
            "Azimute": "35",
            "Tipo Estação": "FB",
            "Tipo Antena": "760",
            "Ganho Ant.": "16,8",
            "Frente Costa": "34",
            "Ângulo 1/2 Pot.": "68,91",
            "Elevação": "0",
            "Polarização": "X",
            "Altura Antena (m)": "42",
            "Potência Transm. (W)": "40",
            "Latitude": "-23.1791",
            "Longitude": "-45.8872",
            "DataLicenciamento": "2025-07-18",
            "UID": "4d5c019f589a1",
            "DataValidade": "2038-04-30",
        }])
        with patch.dict(os.environ, {"ANATEL_DATASET_LABEL": "LICENCIADAS"}):
            registros, descartados, incompletos = transformar_lote(df)

        self.assertEqual((descartados, incompletos), (0, 0))
        registro = dict(zip(COLUNAS_DADOS, registros[0][:len(COLUNAS_DADOS)]))
        self.assertEqual(registro["source_key"], "LICENCIADAS:4d5c019f589a1")
        self.assertEqual(registro["frequencia_tx_mhz"], 2655.0)
        self.assertEqual(registro["frequencia_rx_mhz"], 2535.0)
        self.assertEqual(registro["potencia_transmissor_w"], 40.0)
        self.assertEqual(registro["ganho_antena"], 16.8)
        self.assertEqual(registro["azimute_graus"], 35.0)
        self.assertEqual(registro["angulo_meia_potencia_graus"], 68.91)
        self.assertEqual(registro["uf"], "SP")
        self.assertEqual(registro["latitude"], -23.1791)
        self.assertEqual(registro["longitude"], -45.8872)
        self.assertEqual(registros[0][-2:], (-45.8872, -23.1791))

    def test_descarta_coordenadas_invalidas_e_conta_parametros_rf_ausentes(self):
        df = pd.DataFrame([
            {"UID": "sem-rf", "Latitude": "-23.1", "Longitude": "-45.9"},
            {"UID": "sem-coordenada", "Latitude": "", "Longitude": "-45.9"},
        ])
        registros, descartados, incompletos = transformar_lote(df)
        self.assertEqual(len(registros), 1)
        self.assertEqual(descartados, 1)
        self.assertEqual(incompletos, 1)


    def test_recusa_csv_antigo_sem_cabecalho_de_emissoes_spectrum_e(self):
        with TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "antigo_erb.csv"
            pd.DataFrame({"IdEstacao": [1], "Latitude": [-23.1], "Longitude": [-45.9]}).to_csv(caminho, index=False)
            with self.assertRaisesRegex(ValueError, "não parece ser a exportação"):
                list(iterar_csv(caminho))



if __name__ == "__main__":
    unittest.main()
