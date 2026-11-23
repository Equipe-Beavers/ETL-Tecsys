def temp_tables_query():
    return """
            CREATE TEMP TABLE IF NOT EXISTS temp_posicoes_carga (
                seq BIGINT GENERATED ALWAYS AS IDENTITY,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                tipo_posicao VARCHAR(30),
                municipio VARCHAR(100),
                id_distribuidora INT,
                are_loc VARCHAR(50),
                lote_carga VARCHAR(20)
            ) ON COMMIT DELETE ROWS;

            CREATE TEMP TABLE IF NOT EXISTS temp_postes (
                cod_id VARCHAR(50), 
                altura NUMERIC, 
                material VARCHAR(50), 
                esforco NUMERIC, 
                latitude DOUBLE PRECISION, 
                longitude DOUBLE PRECISION, 
                id_distribuidora INT,
                registro_atual BOOLEAN, 
                lote_carga VARCHAR(20)
            ) ON COMMIT DELETE ROWS;

            CREATE TEMP TABLE IF NOT EXISTS temp_sub (
                cod_id VARCHAR(50), 
                nome VARCHAR(100), 
                latitude DOUBLE PRECISION, 
                longitude DOUBLE PRECISION, 
                id_distribuidora INT,
                registro_atual BOOLEAN, 
                lote_carga VARCHAR(20)
            ) ON COMMIT DELETE ROWS;

            CREATE TEMP TABLE IF NOT EXISTS temp_disp (
                cod_id VARCHAR(50), 
                id_tipo_dispositivo INT, 
                subestacao VARCHAR(50), 
                codigo_conjunto_aneel INT, 
                latitude DOUBLE PRECISION, 
                longitude DOUBLE PRECISION, 
                id_distribuidora INT,
                registro_atual BOOLEAN, 
                lote_carga VARCHAR(20)
            ) ON COMMIT DELETE ROWS;
        """