"""Ferramentas do agente para consultar os dados de SRAG e a web.

As ferramentas locais leem o dataset processado e devolvem um resumo com as métricas
pedidas: informações gerais do dataset e metadados do arquivo, estatísticas do número
diário de casos, série mensal de casos dos últimos 12 meses e seu crescimento mês a mês,
situação de vacinação e contagem de casos por categoria em um período (base das taxas de
mortalidade e de internação em UTI). O caminho do dataset é injetado do estado do
agente.

O módulo também define as ferramentas de busca (`busca_web`) e de coleta (`coleta_web`)
na web do Claude, restritas a domínios permitidos. Elas rodam nos servidores da
Anthropic, por isso são ligadas só ao modelo e não ao `ToolNode`.

O módulo está em desenvolvimento: as demais ferramentas planejadas estão indicadas nos
comentários ao final.
"""

from typing import Annotated, Any, Literal

import pandas as pd
import pyarrow.parquet as pq
from anthropic.types import WebFetchTool20250910Param, WebSearchTool20260209Param
from langchain.tools import tool
from langgraph.prebuilt import InjectedState

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
    que ocorreram), o total, a média e o desvio padrão da série. O dicionário é
    modificado no lugar e nada é retornado. Os valores são tipos nativos do Python, serializáveis em
    JSON e prontos para o LLM: contagens como `int`, média e desvio padrão como `float`
    com 2 casas decimais e datas como texto `AAAA-MM-DD`.

    Args:
        serie: Série indexada por data com o número de casos de cada dia.
        info: Dicionário que recebe as estatísticas. As chaves adicionadas são
            `max_num_casos_<sufixo>` e `min_num_casos_<sufixo>`, cada uma com
            `{"quantidade": ..., "data": ...}`, além de `total_num_casos_<sufixo>`,
            `mean_num_casos_<sufixo>` e `std_num_casos_<sufixo>`.
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
    info["total_num_casos_" + sufixo] = int(serie.sum())
    info["mean_num_casos_" + sufixo] = round(float(serie.mean()), 2)
    info["std_num_casos_" + sufixo] = round(float(serie.std()), 2)


def _num_mensal_casos(df):
    """Calcula o número mensal de casos dos últimos 12 meses.

    A janela de 365 dias termina na data mais recente de primeiros sintomas
    (`DT_SIN_PRI`). Os casos são somados por mês, então o primeiro e o último mês podem
    ser parciais.

    Args:
        df: DataFrame com as colunas `DT_SIN_PRI` e `NU_NOTIFIC`.

    Returns:
        Série com o número de casos de cada mês, indexada pelo último dia do mês como
        texto `AAAA-MM-DD`.
    """
    num_casos_12_m = filtrar_dataset_casos(df, "DT_SIN_PRI", 365, "NU_NOTIFIC")
    num_casos_12_m = num_casos_12_m.resample("ME").sum()
    num_casos_12_m.index = num_casos_12_m.index.astype("str")

    return num_casos_12_m


def _filtrar_dataframe_coluna(
    df: pd.DataFrame, dt_col_filtro: str, dias_filtro: int, col_target: str
) -> pd.DataFrame:
    """Conta os casos por categoria de uma coluna dentro de uma janela de tempo.

    A janela termina na data máxima de `dt_col_filtro` e contém somente as datas
    estritamente posteriores a `max_date - dias_filtro`, ou seja, exatamente
    `dias_filtro` dias de calendário.

    Args:
        df: DataFrame com os casos e a coluna `NU_NOTIFIC`.
        dt_col_filtro: Nome da coluna de data usada para filtrar.
        dias_filtro: Tamanho da janela, em dias, contado a partir da data máxima.
        col_target: Nome da coluna categórica cujas categorias são contadas.

    Returns:
        DataFrame indexado pelas categorias de `col_target`, com a coluna `NU_NOTIFIC`
        com o número de casos de cada categoria.
    """
    # encontrar data máxima
    max_date = df[dt_col_filtro].max()
    initial = max_date - pd.Timedelta(days=dias_filtro)

    # filtrar o dataset
    df_reduced = df[df[dt_col_filtro] > initial]

    return df_reduced.groupby(col_target).count()[["NU_NOTIFIC"]]


def _add_info_metadata(info, filepath):
    """Acrescenta ao dicionário `info` os metadados gravados no arquivo parquet.

    Lê o metadado do schema do arquivo, gravado pelo `data_fetching_processing.py`, e
    copia para `info` as chaves `data_criacao`, `data_extracao` e `pct_dados_descartados`
    que existirem. Arquivos sem esses metadados não geram erro: as chaves ausentes
    simplesmente não são adicionadas. O dicionário é modificado no lugar e nada é
    retornado.

    Args:
        info: Dicionário que recebe os metadados, como texto.
        filepath: Caminho do arquivo parquet de onde os metadados são lidos.
    """
    # ler o schema e decodificar o metadado (chaves e valores vêm em bytes)
    metadata = pq.read_schema(filepath).metadata or {}
    metadata_decoded = {k.decode("utf-8"): v.decode("utf-8") for k, v in metadata.items()}

    for chave in ("data_criacao", "data_extracao", "pct_dados_descartados"):
        if chave in metadata_decoded:
            info[chave] = metadata_decoded[chave]


# tool para pegar informações básicas acerca do dataset


@tool
def dataframe_info(filepath: Annotated[str, InjectedState("filepath_dataset")]) -> dict[str, Any]:
    """Resume as informações gerais do dataset e os metadados do arquivo.

    Args:
        filepath: Caminho do arquivo parquet com o dataset processado. É injetado do estado
            (`filepath_dataset`), e o modelo não o informa.

    Returns:
        Dicionário serializável em JSON, com tipos nativos do Python (datas como texto
        `AAAA-MM-DD`), contendo:
            - `shape`: dimensões do dataset (linhas e colunas);
            - `data_maxima` e `data_minima`: datas extremas de `DT_SIN_PRI`;
            - `data_criacao`: data em que o arquivo processado foi gerado;
            - `data_extracao`: data de extração dos dados do Open DATASUS;
            - `pct_dados_descartados`: porcentagem de registros removidos por valores
              nulos ou ignorados, como texto com 2 casas decimais.
        As três últimas chaves só aparecem quando o arquivo tem esses metadados.
    """
    # carregar dataframe
    df = _importar_dataset(filepath=filepath)

    # informações do dataset
    info = {}

    info["shape"] = df.shape
    info["data_maxima"] = df["DT_SIN_PRI"].max().strftime("%Y-%m-%d")
    info["data_minima"] = df["DT_SIN_PRI"].min().strftime("%Y-%m-%d")

    _add_info_metadata(info, filepath)

    return info


# tool para pegar estatísticas básicas acerca do número de casos


@tool
def estatisticas_num_casos(
    filepath: Annotated[str, InjectedState("filepath_dataset")],
) -> dict[str, Any]:
    """Calcula as estatísticas do número diário de casos nos últimos 30 dias e 12 meses.

    As janelas de 30 dias e 12 meses (365 dias) terminam na data mais recente de
    primeiros sintomas (`DT_SIN_PRI`). Os últimos dias do dataset estão incompletos por
    atraso de notificação, então o mínimo costuma cair nesse período.

    Args:
        filepath: Caminho do arquivo parquet com o dataset processado. É injetado do estado
            (`filepath_dataset`), e o modelo não o informa.

    Returns:
        Dicionário serializável em JSON, com tipos nativos do Python (datas como texto
        `AAAA-MM-DD`), com as chaves abaixo para cada janela, identificada pelo sufixo
        `30_d` (últimos 30 dias) ou `12_m` (últimos 12 meses):
            - `max_num_casos_<sufixo>` e `min_num_casos_<sufixo>`: dia com mais e com
              menos casos, como `{"quantidade": ..., "data": ...}`;
            - `total_num_casos_<sufixo>`: total de casos da janela;
            - `mean_num_casos_<sufixo>` e `std_num_casos_<sufixo>`: média e desvio padrão
              do número diário de casos, com 2 casas decimais.
    """
    # carregar dataframe
    df = _importar_dataset(filepath=filepath)

    # informações do dataset
    info = {}

    num_casos_30_d = filtrar_dataset_casos(df, "DT_SIN_PRI", 30, "NU_NOTIFIC")
    num_casos_12_m = filtrar_dataset_casos(df, "DT_SIN_PRI", 365, "NU_NOTIFIC")

    _add_info_num_casos_dataset(serie=num_casos_12_m, info=info, sufixo="12_m")

    _add_info_num_casos_dataset(serie=num_casos_30_d, info=info, sufixo="30_d")

    return info


# tool para num_mensal_casos


@tool
def num_casos_mensal_ultimos_12_m(
    filepath: Annotated[str, InjectedState("filepath_dataset")],
) -> str:
    """Calcula o número mensal de casos dos últimos 12 meses.

    Usa os dados dos últimos 12 meses (365 dias até a data mais recente de primeiros
    sintomas, `DT_SIN_PRI`) e soma os casos por mês. O primeiro e o último mês podem ser
    parciais.

    Args:
        filepath: Caminho do arquivo parquet com o dataset processado. É injetado do estado
            (`filepath_dataset`), e o modelo não o informa.

    Returns:
        Texto JSON que mapeia o último dia de cada mês (`AAAA-MM-DD`) ao número de casos
        do mês.
    """
    # carregar dataframe
    df = _importar_dataset(filepath=filepath)

    # série últimos 12 meses
    num_casos_12_m = _num_mensal_casos(df)

    # num_casos mensal
    return num_casos_12_m.to_json()


# tool para crescimento_mensal_num_casos


@tool
def crescimento_mensal_ultimos_12_m(
    filepath: Annotated[str, InjectedState("filepath_dataset")],
) -> str:
    """Calcula o crescimento mês a mês do número de casos dos últimos 12 meses.

    Usa os dados dos últimos 12 meses (365 dias até a data mais recente de primeiros
    sintomas, `DT_SIN_PRI`). Cada valor é a variação percentual do número de casos do
    mês em relação ao mês anterior (10.0 significa +10%). O primeiro mês não tem mês
    anterior e fica de fora.
    O último mês é parcial, pois termina na data mais recente do dataset, então sua
    variação tende a ser fortemente negativa sem representar uma queda real.

    Args:
        filepath: Caminho do arquivo parquet com o dataset processado. É injetado do estado
            (`filepath_dataset`), e o modelo não o informa.

    Returns:
        Texto JSON que mapeia o último dia de cada mês (`AAAA-MM-DD`) ao crescimento
        percentual do número de casos em relação ao mês anterior.
    """
    # carregar dataframe
    df = _importar_dataset(filepath=filepath)

    # série últimos 12 meses
    num_casos_12_m = _num_mensal_casos(df)

    # crescimento mensal
    crescimento_mensal_ultimos_12_m = num_casos_12_m.pct_change().dropna() * 100
    return crescimento_mensal_ultimos_12_m.round(2).to_json()


# tool busca e fetch de noticias SRAG

dominios_permitidos = [
    "cnnbrasil.com.br",
    "agencia.fiocruz.br",
    "agenciabrasil.ebc.com.br",
    "gov.br/saude/pt-br",
    "gov.br/saude/pt-br/composicao/svsa/cnie/sindromes-gripais/srag",
]

coleta_web = WebFetchTool20250910Param(
    name="web_fetch", type="web_fetch_20250910", max_uses=5, allowed_domains=dominios_permitidos
)

busca_web = WebSearchTool20260209Param(
    name="web_search", type="web_search_20260209", max_uses=5, allowed_domains=dominios_permitidos
)

# tool taxa de vacinação


@tool
def taxa_de_vacinacao(
    filepath: Annotated[str, InjectedState("filepath_dataset")],
) -> str:
    """Calcula o número de casos por situação de vacinação contra COVID-19.

    Usa todo o dataset, sem filtro de período. A porcentagem de cada situação é calculada
    sobre o total de casos de SRAG, então é a proporção de vacinados entre os casos, e
    não a cobertura vacinal da população.

    Args:
        filepath: Caminho do arquivo parquet com o dataset processado. É injetado do estado
            (`filepath_dataset`), e o modelo não o informa.

    Returns:
        Texto JSON com, para as categorias `vacinado` e `nao_vacinado`, o número de
        casos (`NU_NOTIFIC`) e a porcentagem sobre o total (`pct_vacinados`, com 2 casas
        decimais).
    """
    # carregar dataframe
    df = _importar_dataset(filepath=filepath)

    # taxa de vacinação
    vacinados = df.groupby("VACINA_COV").count()[["NU_NOTIFIC"]]
    vacinados["pct_vacinados"] = (vacinados["NU_NOTIFIC"] * 100 / len(df)).round(2)

    return vacinados.to_json(orient="index")


# tool taxa de mortalidade/internacao


@tool
def taxa_periodo(
    dias_filtro: int,
    col_target: Literal["EVOLUCAO", "UTI"],
    filepath: Annotated[str, InjectedState("filepath_dataset")],
) -> str:
    """Calcula o número e a porcentagem de casos por categoria nos últimos `dias_filtro` dias.

    A janela termina na data mais recente de primeiros sintomas (`DT_SIN_PRI`) e contém
    exatamente `dias_filtro` dias. Serve para as taxas de mortalidade (`EVOLUCAO`) e de
    internação em UTI (`UTI`).

    Args:
        dias_filtro: Tamanho da janela, em dias.
        col_target: Coluna categórica a contar: `EVOLUCAO` (mortalidade) ou `UTI`
            (internação em UTI).
        filepath: Caminho do arquivo parquet com o dataset processado. É injetado do estado
            (`filepath_dataset`), e o modelo não o informa.

    Returns:
        Texto JSON com, para cada categoria de `col_target`, o número de casos
        (`NU_NOTIFIC`) e a porcentagem sobre o total de casos da janela (`pct`, com 2
        casas decimais).
    """
    # carregar dataframe
    df = _importar_dataset(filepath=filepath)

    # taxa
    df_filtrado = _filtrar_dataframe_coluna(
        df=df, dt_col_filtro="DT_SIN_PRI", dias_filtro=dias_filtro, col_target=col_target
    )

    df_filtrado["pct"] = (df_filtrado["NU_NOTIFIC"] * 100 / df_filtrado["NU_NOTIFIC"].sum()).round(
        2
    )

    return df_filtrado.to_json(orient="index")


# tool leitura de relatorio

# tool salvamento relatorio
