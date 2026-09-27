# Tratamento de Dados - ETL (Python)

Pipeline para baixar as bases BDGD, extrair as camadas geográficas, gerar arquivos CSV e carregar os dados no PostgreSQL.

## Pré-requisitos

- Windows 10 ou superior;
- Python 3.10 ou superior instalado e disponível no PATH;
- PostgreSQL instalado e em execução;
- acesso à internet para baixar as bases BDGD;
- um banco PostgreSQL com as tabelas esperadas pelo projeto.

## Como executar do zero

### 1. Obter o projeto

Abra o PowerShell e clone o repositório:

```powershell
git clone https://github.com/Equipe-Beavers/ETL-Tecsys.git
cd ETL-Tecsys
```

Se o projeto já estiver no computador, abra o PowerShell na pasta do projeto:

```powershell
cd C:\caminho\para\ETL-Tecsys
```

### 2. Criar e ativar o ambiente virtual

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Se o PowerShell bloquear a ativação, rode uma vez:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Depois, ative novamente o ambiente virtual. O terminal exibirá `(.venv)` no início da linha.

### 3. Instalar as dependências

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Configurar o PostgreSQL

Crie o banco de dados no PostgreSQL e execute o SQL abaixo conectado ao banco `Tecsys_Data`. Ele habilita o PostGIS, cria as tabelas usadas pelo ETL e cadastra os tipos de dispositivos.

Primeiro, conectado ao banco padrão `postgres`, crie o banco:

```sql
CREATE DATABASE "Tecsys_Data";
```

Depois, conecte-se ao banco `Tecsys_Data` no pgAdmin ou no `psql` e execute:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE POSICOES_GEOGRAFICAS (
	ID_POSICAO BIGSERIAL PRIMARY KEY,
	TIPO_POSICAO VARCHAR(30) NOT NULL,
	LATITUDE DOUBLE PRECISION NOT NULL,
	LONGITUDE DOUBLE PRECISION NOT NULL,
	GEOM GEOMETRY(Point, 4674),
	MUNICIPIO VARCHAR(100),
	BAIRRO VARCHAR(100),
	DATA_INCLUSAO TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	DATA_FIM TIMESTAMP NULL,
	REGISTRO_ATUAL BOOLEAN DEFAULT TRUE,
	LOTE_CARGA VARCHAR(20)
);

CREATE INDEX IDX_POSICOES_GEOGRAFICAS_GEOM
ON POSICOES_GEOGRAFICAS USING GIST (GEOM);

CREATE TABLE TIPOS_DISPOSITIVOS (
	ID_TIPO_DISPOSITIVO INT PRIMARY KEY,
	NOME_DISPOSITIVO VARCHAR(100) NOT NULL,
	CATEGORIA VARCHAR(50)
);

CREATE TABLE POSTES (
	ID_POSTE BIGSERIAL PRIMARY KEY,
	COD_ID VARCHAR(50) NOT NULL,
	ALTURA NUMERIC(4,1),
	MATERIAL VARCHAR(30),
	ESFORCO NUMERIC(6,1),
	ID_POSICAO BIGINT NOT NULL,
	DATA_INCLUSAO TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	DATA_FIM TIMESTAMP NULL,
	REGISTRO_ATUAL BOOLEAN DEFAULT TRUE,
	LOTE_CARGA VARCHAR(20),
	CONSTRAINT FK_POSTES_POSICAO
		FOREIGN KEY (ID_POSICAO)
		REFERENCES POSICOES_GEOGRAFICAS (ID_POSICAO)
		ON DELETE RESTRICT
);

CREATE TABLE SUBESTACOES (
	ID_SUBESTACAO BIGSERIAL PRIMARY KEY,
	COD_ID VARCHAR(50) NOT NULL,
	NOME VARCHAR(100),
	ID_POSICAO BIGINT NOT NULL,
	DATA_INCLUSAO TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	DATA_FIM TIMESTAMP NULL,
	REGISTRO_ATUAL BOOLEAN DEFAULT TRUE,
	LOTE_CARGA VARCHAR(20),
	CONSTRAINT FK_SUBESTACOES_POSICAO
		FOREIGN KEY (ID_POSICAO)
		REFERENCES POSICOES_GEOGRAFICAS (ID_POSICAO)
		ON DELETE RESTRICT
);

CREATE TABLE DISPOSITIVOS (
	ID_DISPOSITIVO BIGSERIAL PRIMARY KEY,
	COD_ID VARCHAR(50) NOT NULL,
	ID_TIPO_DISPOSITIVO INT NOT NULL,
	SUBESTACAO VARCHAR(50),
	CODIGO_CONJUNTO_ANEEL INT,
	ID_POSICAO BIGINT NOT NULL,
	DATA_INCLUSAO TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	DATA_FIM TIMESTAMP NULL,
	REGISTRO_ATUAL BOOLEAN DEFAULT TRUE,
	LOTE_CARGA VARCHAR(20),
	CONSTRAINT FK_DISPOSITIVOS_TIPO
		FOREIGN KEY (ID_TIPO_DISPOSITIVO)
		REFERENCES TIPOS_DISPOSITIVOS (ID_TIPO_DISPOSITIVO),
	CONSTRAINT FK_DISPOSITIVOS_POSICAO
		FOREIGN KEY (ID_POSICAO)
		REFERENCES POSICOES_GEOGRAFICAS (ID_POSICAO)
		ON DELETE RESTRICT
);

INSERT INTO TIPOS_DISPOSITIVOS (ID_TIPO_DISPOSITIVO, NOME_DISPOSITIVO, CATEGORIA) VALUES
(0, 'Não Informado', 'Desconhecido'),
(1, 'Comparador / fiscal e concentrador', 'Medidor'),
(2, 'Medidor eletromecânico', 'Medidor'),
(3, 'Medidor eletrônico', 'Medidor'),
(4, '79 (rele de religamento)', 'Relé'),
(5, 'CTPN (chave de transferência da posição de neutro)', 'Relé'),
(6, 'Disparo para terra', 'Relé'),
(7, 'RAI (Rele de alta impedância)', 'Relé'),
(8, 'Sistema de aterramento', 'Sistema de Aterramento'),
(9, 'Banco de capacitor serial e paralelo', 'Unidade Compensadora de Reativo'),
(10, 'Banco de capacitores paralelo', 'Unidade Compensadora de Reativo'),
(11, 'Banco de capacitores serial', 'Unidade Compensadora de Reativo'),
(12, 'Compensador de reativos', 'Unidade Compensadora de Reativo'),
(13, 'Auto booster', 'Unidade Reguladora'),
(14, 'Regulador automático de tensão', 'Unidade Reguladora'),
(15, 'Abertura de jumper', 'Unidade Seccionadora'),
(16, 'Chave a gás', 'Unidade Seccionadora'),
(17, 'Chave a óleo', 'Unidade Seccionadora'),
(18, 'Chave de transferência automática', 'Unidade Seccionadora'),
(19, 'Chave faca', 'Unidade Seccionadora'),
(20, 'Chave faca tripolar abertura com carga', 'Unidade Seccionadora'),
(21, 'Chave faca unipolar abertura com carga', 'Unidade Seccionadora'),
(22, 'Chave fusível', 'Unidade Seccionadora'),
(23, 'Chave fusível abertura com carga com aterramento', 'Unidade Seccionadora'),
(24, 'Chave fusível abertura sem carga', 'Unidade Seccionadora'),
(25, 'Chave fusível abertura sem carga com aterramento', 'Unidade Seccionadora'),
(26, 'Chave fusível lamina', 'Unidade Seccionadora'),
(27, 'Chave fusível três operações', 'Unidade Seccionadora'),
(28, 'Chave motorizada', 'Unidade Seccionadora'),
(29, 'Disjuntor', 'Unidade Seccionadora'),
(30, 'Disjuntor de interligação de barra', 'Unidade Seccionadora'),
(31, 'Lamina desligadora', 'Unidade Seccionadora'),
(32, 'Religador', 'Unidade Seccionadora'),
(33, 'Seccionadora tripolar de subestação', 'Unidade Seccionadora'),
(34, 'Seccionadora unipolar de subestação', 'Unidade Seccionadora'),
(35, 'Seccionalizador', 'Unidade Seccionadora'),
(36, 'Seccionalizador monofásico', 'Unidade Seccionadora'),
(37, 'Transformador de aterramento', 'Unidade Transformadora'),
(38, 'Transformador de distribuição', 'Unidade Transformadora'),
(39, 'Transformador de isolamento', 'Unidade Transformadora'),
(40, 'Transformador de serviço auxiliar', 'Unidade Transformadora'),
(41, 'Transformador de subestação', 'Unidade Transformadora'),
(42, 'Transformador de corrente', 'Unidade Transformadora de Medidas'),
(43, 'Transformador de potencial', 'Unidade Transformadora de Medidas')
ON CONFLICT (ID_TIPO_DISPOSITIVO) DO NOTHING;
```

Na raiz do projeto, crie ou ajuste o arquivo `.env`:

```env
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=sua_senha
DB_HOST=localhost
DB_PORT=5432
DB_SCHEMA=public
```

Substitua `DB_PASSWORD` e os demais valores pelos dados do seu PostgreSQL. O usuário configurado deve ter permissão para criar tabelas temporárias e inserir dados no schema indicado. Como o SQL acima cria as tabelas no schema padrão, use `DB_SCHEMA=public`.

### 5. Rodar o ETL

Com o PostgreSQL em execução e o ambiente virtual ativo:

```powershell
python main.py
```

O processo irá baixar as bases BDGD configuradas em `main.py`, extrair e transformar as camadas `PONNOT`, `SUB` e `UNSEAT`, salvar os CSVs em `data\processed\<mes>_<ano>.<quinzena>`, carregar os dados no PostgreSQL e limpar os arquivos temporários de `data\raw`.
