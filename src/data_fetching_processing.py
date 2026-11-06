"""TODO: desc arquivo"""

import argparse
import logging
from pathlib import Path

import pandas as pd

# definir logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="app.log",
    filemode="w",
)

logger = logging.getLogger(__name__)

# parsear variáveis

ROOT = Path(__file__).resolve().parent.parent

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
df = pd.read_parquet(
    path=URL_DOWNLOAD, columns=["NU_NOTIFIC", "DT_SIN_PRI", "EVOLUCAO", "VACINA_COV", "UTI"]
)

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
df_cleaned.to_parquet(FILEPATH, index=False)
logger.info("dados salvos")
