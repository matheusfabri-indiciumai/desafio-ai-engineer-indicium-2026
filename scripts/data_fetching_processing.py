"""Baixa o dataset de SRAG do Open DATASUS, limpa os dados e gera os gráficos de casos.

Lê da URL passada como argumento só as colunas necessárias, rotula `EVOLUCAO`,
`VACINA_COV` e `UTI`, descarta os registros com valores ignorados ou nulos e salva o
dataset limpo em parquet, com os metadados `data_criacao`, `data_extracao` e
`pct_dados_descartados`. Também grava em `plots/` os gráficos do número diário de casos
dos últimos 30 dias e dos últimos 12 meses (365 dias). O andamento é registrado em um
arquivo de log.

Uso, a partir da raiz do repositório:
`uv run python -m scripts.data_fetching_processing <url> [-f <filepath>]`.
"""

import argparse
import datetime
import re
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.utils import build_logger, filtrar_dataset_casos, plot_num_casos

# definir logging
logger = build_logger(Path(__file__).name)

# parsear variáveis

ROOT = Path(__file__).resolve().parents[1]

parser = argparse.ArgumentParser(
    prog="data_fetching_processing",
    description="Passe a url de download e os filepaths para salvar o datasets raw e o limpo",
)

parser.add_argument("url", help="URL de download do dataset SRAG do Open DATASUS")
parser.add_argument(
    "-f",
    "--filepath",
    default=str(ROOT / "data" / "srag_data_2026_clean.parquet"),
    help="Filepath para salvar o dataset limpo",
)

args = parser.parse_args()

URL_DOWNLOAD = args.url
FILEPATH = args.filepath

logger.info("variáveis parseadas com sucesso")

# carregar em um dataframe o arquivo parquet
try:
    df = pd.read_parquet(
        path=URL_DOWNLOAD, columns=["NU_NOTIFIC", "DT_SIN_PRI", "EVOLUCAO", "VACINA_COV", "UTI"]
    )
except Exception:
    logger.exception("falha ao baixar ou ler o dataset")
    raise

# rotular dados
evolucao = {"1": "cura", "2": "obito", "3": "obito"}
vacinacao = {"1": "vacinado", "2": "nao_vacinado", "9": pd.NA}
uti = {"1": "uti", "2": "nao_uti", "9": pd.NA}

df["EVOLUCAO"] = df["EVOLUCAO"].map(evolucao)
df["VACINA_COV"] = df["VACINA_COV"].map(vacinacao)
df["UTI"] = df["UTI"].map(uti)

logger.info(f"dataset lido de {URL_DOWNLOAD} e rotulado: {len(df)} registros")

# descartar dados nulos
df_cleaned = df.dropna(subset=["EVOLUCAO", "VACINA_COV", "UTI"])

pct_dados_descartados = (len(df) - len(df_cleaned)) * 100 / len(df)

logger.info(f"porcentagem de dados descartados: {pct_dados_descartados:.3f}")

# criar metadado personalizado (o metadado do parquet só aceita texto)

table = pa.Table.from_pandas(df_cleaned, preserve_index=False)

custom_metadata = {
    "data_criacao": datetime.date.today().isoformat(),
    "pct_dados_descartados": f"{pct_dados_descartados:.2f}",
}

logger.info(f"tabela criada: {table.num_rows} registros e {table.num_columns} colunas")

# data de extração do Open DATASUS, presente no nome do arquivo (INFLUD26-19-10-2026.parquet)
match_extracao = re.search(r"-(\d{2})-(\d{2})-(\d{4})\.parquet", URL_DOWNLOAD)
if match_extracao:
    dia, mes, ano = match_extracao.groups()
    custom_metadata["data_extracao"] = f"{ano}-{mes}-{dia}"
else:
    logger.warning("data de extração não encontrada no nome do arquivo")

existing_metadata = table.schema.metadata or {}
combined_metadata = {**existing_metadata, **custom_metadata}

table = table.replace_schema_metadata(combined_metadata)

# salvar dataset na forma final
try:
    Path(FILEPATH).parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, FILEPATH)
except Exception:
    logger.exception("falha ao salvar o dataset")
    raise
logger.info(f"dados salvos em {FILEPATH}")

# criar os gráficos e salvar em png

PLOTS_DIR = ROOT / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

df_reduced_30_d = filtrar_dataset_casos(df_cleaned, "DT_SIN_PRI", 30, "NU_NOTIFIC")
df_reduced_12_m = filtrar_dataset_casos(df_cleaned, "DT_SIN_PRI", 365, "NU_NOTIFIC")

plot_num_casos(
    serie=df_reduced_30_d,
    title="Número de casos últimos 30 dias",
    eixo_x="Data",
    eixo_y="Número de casos",
    filepath=PLOTS_DIR / "num_casos_30_dias.png",
)

plot_num_casos(
    serie=df_reduced_12_m,
    title="Número de casos últimos 12 meses",
    eixo_x="Data",
    eixo_y="Número de casos",
    filepath=PLOTS_DIR / "num_casos_12_meses.png",
)

logger.info(f"gráficos salvos em {PLOTS_DIR}")
