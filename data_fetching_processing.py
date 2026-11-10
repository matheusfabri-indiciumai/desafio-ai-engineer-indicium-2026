"""Baixa o dataset de SRAG do Open DATASUS, limpa os dados e gera os gráficos de casos.

Lê da URL passada como argumento só as colunas necessárias, rotula `EVOLUCAO`,
`VACINA_COV` e `UTI`, descarta os registros com valores ignorados ou nulos e salva o
dataset limpo em parquet. Também grava em `plots/` os gráficos do número diário de casos
dos últimos 30 dias e dos últimos 12 meses (365 dias). O andamento é registrado em um
arquivo de log.

Uso: `uv run data_fetching_processing.py <url> [-f <filepath>]`.
"""

import argparse
from pathlib import Path

import pandas as pd

from src.utils import build_logger, filtrar_dataset_casos, plot_num_casos

# definir logging
logger = build_logger(Path(__file__).name)

# parsear variáveis

ROOT = Path(__file__).resolve().parent

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

# descartar dados nulos
df_cleaned = df.dropna(subset=["EVOLUCAO", "VACINA_COV", "UTI"])

pct_dados_descartados = (len(df) - len(df_cleaned)) * 100 / len(df)

logger.info(f"porcentagem de dados descartados: {pct_dados_descartados:.3f}")

# salvar dataset na forma final
try:
    Path(FILEPATH).parent.mkdir(parents=True, exist_ok=True)
    df_cleaned.to_parquet(FILEPATH, index=False)
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
