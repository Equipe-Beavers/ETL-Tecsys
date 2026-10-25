# Pipeline ETL - BDGD ANEEL

Pipeline automatizado em **Python** para Extração, Transformação e Carga (ETL) de dados geográficos e elétricos da Base de Dados Geográfica do Setor Elétrico (**BDGD** da ANEEL) para um banco de dados PostgreSQL com suporte PostGIS.

---

## Etapas do Pipeline

### 1. Extract (Extração)
* **Fonte dos dados:** [Dados Abertos ANEEL](https://dadosabertos-aneel.opendata.arcgis.com/search).
* **Funcionamento:** Os links de download são percorridos em um loop no arquivo principal. Cada arquivo baixado é descompactado automaticamente na pasta `/raw`, preparando-os para a etapa seguinte.

### 2. Transform (Transformação)
* **Funcionamento:** Lê os arquivos descompactados, processa os dados em lotes (*chunks*), limpa formatações numéricas e extrai as informações essenciais.
* **Saída:** Os dados tratados são salvos em arquivos `.csv` organizados na pasta `/processed`.
* **Otimização:** Após a extração de cada arquivo, o diretório temporário descompactado é limpo para evitar a lotação do armazenamento local.

### 3. Load (Carga)
* **Funcionamento:** Realiza a leitura dos arquivos `.csv` e insere os registros diretamente no banco de dados relacional de forma otimizada (utilizando lotes e transações isoladas por camada).

As cargas são divididas em 3 camadas principais:
* **`PONNOT`**: Postes (latitude, longitude, distribuidora, área local, materiais, altura, esforço, etc.).
* **`SUB`**: Subestações (informações estruturais e geográficas).
* **`UNSEAT`**: Dispositivos da rede elétrica (tipos, subestações associadas, conjuntos ANEEL).

---

## Tecnologias Utilizadas

* **Python** (Pandas, TQDM, Dotenv)
* **PostgreSQL / PostGIS** (Manipulação de dados espaciais e geometrias `ST_MakePoint`)
* **SQLite / GeoPackage** (Processamento de malhas territoriais e municípios)