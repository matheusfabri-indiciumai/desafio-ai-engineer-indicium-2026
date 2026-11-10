"""Ferramentas do agente para consultar os dados de SRAG.

Cada ferramenta lê o dataset processado e devolve um resumo com as métricas pedidas.
O módulo está em desenvolvimento: as demais ferramentas planejadas estão indicadas
nos comentários ao final.
"""

from typing import Any

import pandas as pd
from langchain.tools import tool

from src.utils import filtrar_dataset_casos

# funções auxiliares


def _importar_dataset(filepath):
    """Carrega o dataset em formato parquet.

    Args:
        filepath: Caminho do arquivo parquet.

    Returns:
        DataFrame com o conteúdo do arquivo.
    """
    return pd.read_parquet(path=filepath)


def _add_info_num_casos_dataset(serie, info, sufixo):
    """Acrescenta ao dicionário `info` as estatísticas de uma série de número de casos.

    Adiciona, com o `sufixo` no final de cada chave, o máximo e o mínimo (com a data em
    que ocorreram), a média e o desvio padrão da série. O dicionário é modificado no
    lugar e nada é retornado. Os valores são tipos nativos do Python, serializáveis em
    JSON e prontos para o LLM: contagens como `int`, média e desvio padrão como `float`
    com 2 casas decimais e datas como texto `AAAA-MM-DD`.

    Args:
        serie: Série indexada por data com o número de casos de cada dia.
        info: Dicionário que recebe as estatísticas. As chaves adicionadas são
            `max_num_casos_<sufixo>` e `min_num_casos_<sufixo>`, cada uma com
            `{"quantidade": ..., "data": ...}`, além de `mean_num_casos_<sufixo>` e
            `std_num_casos_<sufixo>`.
        sufixo: Identificador da janela de tempo, por exemplo `"30_d"` ou `"12_m"`.
    """
    info["max_num_casos_" + sufixo] = {
        "quantidade": int(serie.max()),
        "data": serie.idxmax().strftime("%Y-%m-%d"),
    }
    info["min_num_casos_" + sufixo] = {
        "quantidade": int(serie.min()),
        "data": serie.idxmin().strftime("%Y-%m-%d"),
    }
    info["mean_num_casos_" + sufixo] = round(float(serie.mean()), 2)
    info["std_num_casos_" + sufixo] = round(float(serie.std()), 2)


# tool para pegar informações básicas acerca dos dados


@tool
def dataframe_info(filepath: str) -> dict[str, Any]:
    """Resume as informações básicas do dataset e o número de casos por janela de tempo.

    As janelas de 30 dias e 12 meses (365 dias) terminam na data mais recente de
    primeiros sintomas (`DT_SIN_PRI`), tratada como "hoje".

    Args:
        filepath: Caminho do arquivo parquet com o dataset processado.

    Returns:
        Dicionário serializável em JSON, com tipos nativos do Python (datas como texto
        `AAAA-MM-DD`), contendo:
            - `shape`: dimensões do dataset;
            - `data_maxima` e `data_minima`: datas extremas de `DT_SIN_PRI`;
            - `max_num_casos_*`, `min_num_casos_*`, `mean_num_casos_*` e
              `std_num_casos_*`: estatísticas do número diário de casos, com sufixo
              `12_m` (últimos 12 meses) e `30_d` (últimos 30 dias).
    """
    # carregar dataframe
    df = _importar_dataset(filepath=filepath)

    # informações do dataset
    info = {}

    info["shape"] = df.shape
    info["data_maxima"] = df["DT_SIN_PRI"].max().strftime("%Y-%m-%d")
    info["data_minima"] = df["DT_SIN_PRI"].min().strftime("%Y-%m-%d")

    num_casos_30_d = filtrar_dataset_casos(df, "DT_SIN_PRI", 30, "NU_NOTIFIC")
    num_casos_12_m = filtrar_dataset_casos(df, "DT_SIN_PRI", 365, "NU_NOTIFIC")

    _add_info_num_casos_dataset(serie=num_casos_12_m, info=info, sufixo="12_m")

    _add_info_num_casos_dataset(serie=num_casos_30_d, info=info, sufixo="30_d")

    return info


# tool para crescimento_mensal_num_casos

# tool estatistica numero de casos

# tool busca de noticias SRAG

# tool taxa de vacinação

# tool taxa de mortalidade

# tool taxa de internação

# tool leitura de relatorio

# tool salvamento relatorio
