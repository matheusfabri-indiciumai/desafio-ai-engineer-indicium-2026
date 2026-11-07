"""Funções utilitárias para a série temporal de casos de SRAG.

Reúne as funções usadas pelo script de processamento para calcular o número diário de
casos dentro de uma janela de tempo e para salvar o gráfico dessa série em arquivo.
"""

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def filtrar_dataset_casos(df, dt_col_filtro, dias_filtro, col_target):
    """Conta o número diário de casos dentro de uma janela de tempo.

    A janela termina na data máxima de `dt_col_filtro`, que é tratada como "hoje", e
    contém somente as datas estritamente posteriores a `max_date - dias_filtro`, ou
    seja, exatamente `dias_filtro` dias de calendário.

    Args:
        df: DataFrame com os casos.
        dt_col_filtro: Nome da coluna de data usada para filtrar e agrupar.
        dias_filtro: Tamanho da janela, em dias, contado a partir da data máxima.
        col_target: Nome da coluna cujos valores não nulos são contados.

    Returns:
        Série indexada por data com o número de casos de cada dia da janela. Dias sem
        casos não aparecem na série.
    """
    # encontrar data máxima
    max_date = df[dt_col_filtro].max()
    initial = max_date - pd.Timedelta(days=dias_filtro)

    # filtrar o dataset
    df_reduced = df[df[dt_col_filtro] > initial]

    return df_reduced.groupby(dt_col_filtro)[col_target].count()


def plot_num_casos(serie, title, eixo_x, eixo_y, filepath, figsize=(10, 5), marker="o", alpha=0.8):
    """Desenha a série de número de casos como um gráfico de linha e o salva em arquivo.

    A figura é salva em `filepath`, mas não é exibida nem fechada.

    Args:
        serie: Série indexada por data com o número de casos de cada dia.
        title: Título do gráfico.
        eixo_x: Rótulo do eixo x.
        eixo_y: Rótulo do eixo y.
        filepath: Caminho do arquivo de imagem a ser gravado. O formato é definido
            pela extensão (por exemplo, `.png`).
        figsize: Largura e altura da figura, em polegadas.
        marker: Marcador de cada ponto da linha, no formato do matplotlib.
        alpha: Opacidade da linha, entre 0 e 1.

    Raises:
        FileNotFoundError: Se a pasta de `filepath` não existir.
    """
    plt.figure(figsize=figsize)
    sns.lineplot(data=serie, marker=marker, alpha=alpha)
    plt.title(title)
    plt.xlabel(eixo_x)
    plt.ylabel(eixo_y)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(filepath)
