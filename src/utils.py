"""Funções utilitárias do processamento dos dados e da geração do boletim de SRAG.

Reúne as funções usadas pelo script de processamento para calcular o número diário de
casos dentro de uma janela de tempo, salvar o gráfico dessa série em arquivo e
configurar o logging em arquivo, e as funções usadas pelo agente para copiar o template
do boletim epidemiológico e preenchê-lo com os valores do resumo.
"""

import datetime
import logging
import shutil

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


def build_logger(program_name):
    """Configura o logging em arquivo e devolve o logger do módulo.

    Chama `logging.basicConfig` com nível `INFO`, formato `data - nível - mensagem` e
    escrita no arquivo `<program_name>.log`, criado no diretório de execução e
    sobrescrito a cada execução (`filemode="w"`). Como `basicConfig` só tem efeito na
    primeira chamada, chamadas seguintes não alteram a configuração.

    Args:
        program_name: Nome do programa que usa o log, usado para nomear o arquivo. Por
            exemplo, `Path(__file__).name` gera `<script>.py.log`.

    Returns:
        Logger com o nome deste módulo (`utils`), não o do programa chamador.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        filename=f"{program_name}.log",
        filemode="w",
    )

    return logging.getLogger(__name__)


def copy_template(template_path, dest_folder="."):
    """Copia o template do boletim para um novo arquivo com data e hora no nome.

    O arquivo de destino se chama `boletim_epidemiologico_srag__AAAA_MM_DD__HH_MM_SS.md`,
    com a data e a hora do momento da chamada (resolução de segundos), e fica em
    `dest_folder`. A pasta de destino precisa existir. Duas cópias feitas no mesmo
    segundo têm o mesmo nome, e a segunda sobrescreve a primeira.

    Args:
        template_path: Caminho do arquivo markdown do template.
        dest_folder: Pasta onde a cópia é gravada. Os caminhos de imagem do template, como
            os gráficos, são relativos à pasta de execução, então as imagens só aparecem
            se a cópia ficar nela.

    Returns:
        Caminho do arquivo copiado, ainda com os `{campos}` do template sem preencher.

    Raises:
        FileNotFoundError: Se o template ou a pasta de destino não existirem.
    """
    # dest filepath
    timestamp = datetime.datetime.now().strftime("%Y_%m_%d__%H_%M_%S")
    dest_filepath = dest_folder + f"/boletim_epidemiologico_srag__{timestamp}.md"

    # copiar arquivo
    shutil.copy(template_path, dest_filepath)

    return dest_filepath


def fill_template(dest_filepath, summary):
    """Preenche os campos `{...}` do boletim com os valores do resumo.

    Lê o arquivo, substitui cada campo pelo valor de mesmo nome em `summary` (com
    `str.format`) e sobrescreve o arquivo com o resultado. O texto é formatado antes de o
    arquivo ser aberto para escrita, então, se faltar algum valor, o arquivo não é
    alterado. Os valores inseridos não são reinterpretados, então chaves dentro deles são
    mantidas. Como o resultado sobrescreve o arquivo, a função deve ser chamada uma única
    vez, sobre uma cópia nova do template (ver `copy_template`): chamar de novo sobre um
    boletim já preenchido pode falhar se algum valor tiver chaves.

    Args:
        dest_filepath: Caminho do boletim copiado do template, que é sobrescrito.
        summary: Resumo, como um modelo Pydantic (`ResumoBoletim`), com um campo para
            cada `{campo}` do template. Campos a mais no resumo são ignorados.

    Raises:
        KeyError: Se o template tiver um campo que não existe no resumo.
        FileNotFoundError: Se `dest_filepath` não existir.
    """
    # abrir arquivo do boletim
    with open(dest_filepath, encoding="utf-8") as file:
        content = file.read()

    # preencher
    info_fill = summary.model_dump()
    content = content.format(**info_fill)

    # escrever informações no arquivo
    with open(dest_filepath, "w", encoding="utf-8") as file:
        file.write(content)
