# Tratamento de Dados - ETL (Python)
# ETL-Python

## Executar somente algumas distribuidoras

O pipeline processa todas as bases listadas em `main.py` por padrão. Para
testar o backend sem baixar todas elas, defina `BDGD_DISTRIBUIDORAS` com
trechos dos nomes das distribuidoras separados por vírgula:

```bash
BDGD_DISTRIBUIDORAS="Energisa Minas Rio,Enel SP,EDP SP,Neoenergia Elektro,CPFL Santa Cruz,CPFL Piratininga,CPFL Paulista" python main.py
```

Para um teste ainda menor, use apenas uma base:

```bash
BDGD_DISTRIBUIDORAS="Enel SP" python main.py
```

O filtro não altera a lista completa de URLs e, se a variável não for
informada, o comportamento original é mantido.