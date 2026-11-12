"""Definições do agente que gera o boletim epidemiológico de SRAG.

Reúne o prompt de sistema do agente, com o contexto, o objetivo, a descrição do dataset
processado, as regras e os passos a seguir; os esquemas do resumo (`ResumoAgente` e
`ResumoBoletim`) com os valores que preenchem o template do boletim; o estado
compartilhado entre os nós (`EstadoAgente`); e os nós do grafo: `assistente`, criado por
`criar_no_assistente` a partir do modelo com as ferramentas, e `criar_boletim`. A
construção do grafo, com o modelo, as ferramentas e as arestas, fica em
`scripts/agentic_workflow.py`.
"""

import datetime
import logging
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage, SystemMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from src.utils import copy_template, fill_template

logger = logging.getLogger(__name__)

# prompts


def system_prompt_agente():
    """Monta o prompt de sistema do agente que cria o boletim epidemiológico de SRAG.

    O prompt é dividido em blocos XML: `<contexto>` (o que é SRAG), `<objetivo>` (o que o
    agente deve produzir), `<schema_dataset>` (colunas, tipos e valores do dataset),
    `<regras>` (premissas, formato dos valores, limitações dos dados e uso da web) e
    `<passos>` (checklist que o agente deve seguir, com a extração das informações do
    dataset e da web e a gravação do resumo, montado por `_prompt_passos_agente`). A data
    de emissão do boletim é a data de hoje, inserida no `<contexto>`. Os caminhos dos
    arquivos não aparecem no prompt: são injetados do estado do agente nas ferramentas.

    Returns:
        Mensagem de sistema com o prompt do agente.
    """
    prompt = f"""Você é um analista de dados de saúde pública. Responda sempre em PT-BR.

<contexto>
A data de hoje (data de emissão do boletim) é {datetime.date.today():%d/%m/%Y}.
SRAG é a Síndrome Respiratória Aguda Grave: um quadro de síndrome gripal (febre, tosse, \
dor de garganta, entre outros sintomas) acompanhado de dispneia ou desconforto \
respiratório, saturação de O2 abaixo de 95% ou cianose, que leva à hospitalização ou ao \
óbito. Os casos são notificados ao Ministério da Saúde e publicados no Open DATASUS \
(SIVEP-Gripe). A vigilância da SRAG permite acompanhar a circulação de vírus respiratórios \
(como influenza e COVID-19) e a pressão sobre o sistema de saúde.
</contexto>

<objetivo>
Extrair do dataset processado e da web as informações que preenchem o boletim \
epidemiológico de SRAG, para apoiar a leitura da situação epidemiológica. Cada informação \
extraída corresponde a um campo do resumo do boletim (descritos no schema `ResumoAgente`):
- números de casos (total, média, desvio padrão, máximo e mínimo) dos últimos 30 dias e dos \
últimos 12 meses;
- número mensal de casos dos últimos 12 meses e taxa de aumento de casos mês a mês;
- taxa de mortalidade e taxa de ocupação de UTI (proporção dos casos internados em UTI) \
nos últimos 30 dias e 12 meses;
- taxa de vacinação (proporção de vacinados contra COVID-19 entre os casos);
- notícias recentes sobre SRAG obtidas na web, para contextualizar os números;
- interpretações, conclusão e recomendações baseadas nesses dados.
</objetivo>

<schema_dataset>
O dataset é um arquivo parquet com um registro por caso notificado e as colunas:
- NU_NOTIFIC (str): número de registro sequencial da notificação, identifica o caso.
- DT_SIN_PRI (datetime64[ns]): data dos primeiros sintomas do caso. É a data usada para \
contar casos.
- EVOLUCAO (str): evolução do caso. Valores: "cura" ou "obito" (inclui óbito por outras \
causas).
- VACINA_COV (str): se o paciente recebeu vacina contra COVID-19. Valores: "vacinado" ou \
"nao_vacinado".
- UTI (str): se o paciente foi internado em UTI. Valores: "uti" ou "nao_uti".

Registros com EVOLUCAO, VACINA_COV ou UTI ignorados ou nulos foram removidos do dataset.
</schema_dataset>

<regras>
- A taxa de vacinação é a proporção de vacinados entre os casos de SRAG, não a cobertura \
vacinal da população.
- Os valores finais seguem o padrão brasileiro: datas em DD/MM/AAAA, números com ponto \
nos milhares e vírgula nos decimais, e taxas com duas casas decimais e o símbolo %. As \
ferramentas devolvem datas como AAAA-MM-DD e números com ponto decimal, então converta.
- Os caminhos dos arquivos são fornecidos automaticamente às ferramentas. Não os peça nem \
os informe ao chamar uma ferramenta.
- Use a busca e a coleta na web apenas para contextualizar os números, nunca para \
substituí-los: as métricas vêm sempre do dataset. A web é restrita a domínios permitidos \
(portais de notícias e do Ministério da Saúde); não tente acessar outros sites.
- Cite a fonte (título e URL) de toda informação vinda da web. Se a busca não retornar \
nada relevante, diga isso. As ferramentas da web têm um limite de usos por execução, \
então faça buscas objetivas.
- Use apenas os dados e as ferramentas disponíveis. Se uma informação não estiver \
disponível, diga isso em vez de estimá-la.
</regras>

{_prompt_passos_agente()}"""

    return SystemMessage(content=prompt)


def _prompt_passos_agente():
    """Monta o bloco do prompt com os passos que o agente deve seguir no boletim epidemiológico.

    Os passos são um checklist dentro do bloco XML `<passos>`, incluído no prompt de
    sistema por `system_prompt_agente`. Cada passo chama uma ferramenta e indica quais
    valores extrair, já no formato dos campos de `ResumoAgente`. O último passo redige os
    textos interpretativos, e o último grava o resumo no estado do agente com a ferramenta
    `atualizar_summary`.

    Returns:
        Texto do bloco `<passos>` com o checklist.
    """
    return """<passos>
Siga o checklist abaixo, na ordem. Em cada passo, anote os valores extraídos já no formato \
final:
- [ ] 1. Chame `dataframe_info`. Extraia a data final do período (`data_maxima`), a data \
de extração e a porcentagem de dados descartados. A data inicial é a mais recente entre \
`data_minima` e 364 dias antes de `data_maxima`.
- [ ] 2. Chame `estatisticas_num_casos`. Extraia, para 30 dias (`30_d`) e 12 meses \
(`12_m`), o total, a média, o desvio padrão e os dias de máximo e de mínimo (quantidade e \
data).
- [ ] 3. Chame `num_casos_mensal_ultimos_12_m` e `crescimento_mensal_ultimos_12_m`. \
Monte a tabela de crescimento mensal com uma linha por mês (mês no formato MM/AAAA, \
número de casos e crescimento em %, sem crescimento no primeiro mês).
- [ ] 4. Chame `taxa_de_vacinacao`. Extraia o número de casos e a proporção de vacinados \
e de não vacinados.
- [ ] 5. Chame `taxa_periodo` quatro vezes: com `col_target` "EVOLUCAO" e com "UTI", cada \
uma com `dias_filtro` 30 e 365. Extraia a taxa de mortalidade (porcentagem de "obito") e \
a taxa de ocupação de UTI (porcentagem de "uti") em cada janela.
- [ ] 6. Busque notícias recentes sobre SRAG com `web_search` e leia as mais relevantes \
com `web_fetch`, usando apenas as URLs da busca. Extraia título, fonte, URL e um resumo \
de cada uma.
- [ ] 7. Com os valores extraídos, redija o resumo, as interpretações (evolução dos casos, \
crescimento mensal, taxas, impacto das notícias), a conclusão e as recomendações para a \
Indicium HealthCare Inc., sempre apoiadas nos números.
- [ ] 8. Chame `atualizar_summary` uma única vez, com todos os campos do resumo \
preenchidos com os valores extraídos e os textos redigidos. Não preencha os caminhos dos \
gráficos: eles são adicionados automaticamente.

Ao receber a confirmação de `atualizar_summary`, encerre o turno sem repetir o conteúdo do \
resumo.
</passos>"""


# schemas


class ResumoAgente(BaseModel):
    """Valores que o agente preenche para os campos `{...}` do template do boletim.

    Há um campo para cada chave de `src/template_boletim.md`, na ordem em que aparecem,
    exceto os caminhos dos gráficos (`plot_num_casos_30_d` e `plot_num_casos_12_m`), que
    o agente não preenche: eles vêm do estado e são acrescentados em `ResumoBoletim`.
    Todos são texto, já no formato em que serão inseridos no boletim: datas em
    DD/MM/AAAA, números no padrão brasileiro (separador de milhar com ponto e vírgula
    decimal) e tabelas e listas em markdown.
    """

    # cabeçalho e metadados
    data_inicio: str = Field(
        description=(
            "Data inicial do período analisado, no formato DD/MM/AAAA: a mais recente entre "
            "o início da janela de 12 meses e a data mais antiga de início dos sintomas do "
            "dataset."
        )
    )
    data_fim: str = Field(
        description=(
            "Data final do período analisado, no formato DD/MM/AAAA: a data mais recente de "
            "início dos sintomas do dataset."
        )
    )
    data_relatorio: str = Field(description="Data de emissão do boletim, no formato DD/MM/AAAA.")
    data_extracao: str = Field(
        description=(
            "Data de extração dos dados do Open DATASUS, no formato DD/MM/AAAA. Consta no "
            "nome do arquivo baixado (por exemplo, INFLUD26-19-10-2026 indica 19/10/2026)."
        )
    )
    pct_dados_descartados: str = Field(
        description=(
            "Porcentagem de registros removidos por terem evolução, vacinação ou internação "
            "em UTI nulos ou ignorados, com duas casas decimais e o símbolo %. Ex.: 13,55%."
        )
    )

    # resumo
    resumo: str = Field(
        description=(
            "Resumo do boletim em um parágrafo curto: situação do número de casos, principais "
            "taxas e o contexto trazido pelas notícias."
        )
    )

    # resultados: número de casos
    interpretacao_evolucao_casos: str = Field(
        description=(
            "Interpretação da evolução diária dos casos nos gráficos de 30 dias e de 12 meses: "
            "tendência, picos e vales, lembrando que os últimos dias do dataset estão "
            "incompletos por atraso de notificação."
        )
    )
    total_casos_30_d: str = Field(
        description="Total de casos nos últimos 30 dias, inteiro com separador de milhar. Ex.: 5.054."
    )
    total_casos_12_m: str = Field(
        description="Total de casos nos últimos 12 meses, inteiro com separador de milhar."
    )
    media_casos_30_d: str = Field(
        description="Média diária de casos nos últimos 30 dias, com duas casas decimais. Ex.: 168,47."
    )
    media_casos_12_m: str = Field(
        description="Média diária de casos nos últimos 12 meses, com duas casas decimais."
    )
    desvio_casos_30_d: str = Field(
        description="Desvio padrão do número diário de casos nos últimos 30 dias, com duas casas decimais."
    )
    desvio_casos_12_m: str = Field(
        description="Desvio padrão do número diário de casos nos últimos 12 meses, com duas casas decimais."
    )
    max_casos_30_d: str = Field(
        description=(
            "Dia com mais casos nos últimos 30 dias, no formato `quantidade (DD/MM/AAAA)`. "
            "Ex.: 388 (20/09/2026)."
        )
    )
    max_casos_12_m: str = Field(
        description="Dia com mais casos nos últimos 12 meses, no formato `quantidade (DD/MM/AAAA)`."
    )
    min_casos_30_d: str = Field(
        description="Dia com menos casos nos últimos 30 dias, no formato `quantidade (DD/MM/AAAA)`."
    )
    min_casos_12_m: str = Field(
        description="Dia com menos casos nos últimos 12 meses, no formato `quantidade (DD/MM/AAAA)`."
    )
    tabela_crescimento_mensal: str = Field(
        description=(
            "Tabela em markdown com uma linha por mês e as colunas `Mês`, `Casos` e "
            "`Crescimento (%)`, com a variação em relação ao mês anterior. O primeiro mês não "
            "tem mês anterior e fica sem crescimento."
        )
    )
    interpretacao_crescimento_mensal: str = Field(
        description=(
            "Interpretação do crescimento mês a mês: períodos de alta e de queda. O último mês "
            "é parcial, então sua queda não deve ser apresentada como redução real de casos."
        )
    )

    # resultados: demais métricas
    taxa_mortalidade_30_d: str = Field(
        description=(
            "Taxa de mortalidade nos últimos 30 dias (óbitos entre os casos com desfecho), "
            "com duas casas decimais e o símbolo %. Ex.: 6,87%."
        )
    )
    taxa_mortalidade_12_m: str = Field(
        description="Taxa de mortalidade nos últimos 12 meses, com duas casas decimais e o símbolo %."
    )
    taxa_uti_30_d: str = Field(
        description=(
            "Taxa de ocupação de UTI nos últimos 30 dias (casos internados em UTI entre o total "
            "de casos), com duas casas decimais e o símbolo %. Ex.: 26,14%."
        )
    )
    taxa_uti_12_m: str = Field(
        description="Taxa de ocupação de UTI nos últimos 12 meses, com duas casas decimais e o símbolo %."
    )
    casos_vacinados: str = Field(
        description="Número de casos vacinados contra COVID-19, inteiro com separador de milhar."
    )
    casos_nao_vacinados: str = Field(
        description="Número de casos não vacinados contra COVID-19, inteiro com separador de milhar."
    )
    taxa_vacinados: str = Field(
        description=(
            "Proporção de vacinados entre os casos de SRAG, com duas casas decimais e o "
            "símbolo %. Ex.: 38,85%. Não é a cobertura vacinal da população."
        )
    )
    taxa_nao_vacinados: str = Field(
        description="Proporção de não vacinados entre os casos de SRAG, com duas casas decimais e o símbolo %."
    )
    interpretacao_metricas: str = Field(
        description=(
            "Interpretação conjunta das taxas de mortalidade, de ocupação de UTI e de "
            "vacinação, comparando as janelas de 30 dias e de 12 meses."
        )
    )

    # notícias
    lista_noticias: str = Field(
        description=(
            "Lista em markdown das notícias recentes sobre SRAG, cada item com título, fonte, "
            "URL e uma frase de resumo. Usar só notícias dos domínios permitidos; se nada "
            "relevante for encontrado, dizer isso."
        )
    )
    impacto_noticias: str = Field(
        description=(
            "Análise do impacto das notícias e de sua relação com os dados apresentados. As "
            "métricas vêm sempre do dataset, e as notícias só as contextualizam."
        )
    )

    # conclusão e referências
    conclusao: str = Field(
        description="Conclusão do boletim, retomando os principais achados sobre casos, taxas e contexto."
    )
    recomendacoes: str = Field(
        description=(
            "Lista numerada em markdown de recomendações para a Indicium HealthCare Inc., cada "
            "uma ligada a um achado dos dados."
        )
    )
    fontes_informacoes: str = Field(
        description=(
            "Lista em markdown das fontes (título e URL) das informações que não vêm do "
            "dataset, como as notícias."
        )
    )


class ResumoBoletim(ResumoAgente):
    """Resumo completo do boletim: os campos do agente mais os caminhos dos gráficos.

    Há um campo para cada chave de `src/template_boletim.md`. Os caminhos dos gráficos
    vêm do estado do agente e são acrescentados pela ferramenta que grava o resumo,
    sem passar pelo modelo.
    """

    plot_num_casos_30_d: str = Field(
        description="Caminho da imagem do gráfico do número diário de casos dos últimos 30 dias."
    )
    plot_num_casos_12_m: str = Field(
        description="Caminho da imagem do gráfico do número diário de casos dos últimos 12 meses."
    )


# estado do agente


class EstadoAgente(TypedDict):
    """Estado compartilhado entre os nós do grafo.

    Attributes:
        filepath_dataset: Caminho do dataset processado, injetado nas ferramentas locais.
        plot_num_casos_12_m: Caminho do gráfico do número diário de casos dos últimos 12
            meses, injetado em `atualizar_summary`.
        plot_num_casos_30_d: Caminho do gráfico do número diário de casos dos últimos 30
            dias, injetado em `atualizar_summary`.
        filepath_template: Caminho do template markdown do boletim.
        summary: Resumo com os valores que preenchem o template. Só existe depois de o
            agente chamar `atualizar_summary`.
        messages: Histórico de mensagens, acumulado pelo reducer `add_messages`.
    """

    filepath_dataset: str
    plot_num_casos_12_m: str
    plot_num_casos_30_d: str
    filepath_template: str
    summary: ResumoBoletim
    messages: Annotated[list[AnyMessage], add_messages]


# nós do grafo


def criar_no_assistente(llm_with_tools):
    """Cria o nó `assistente`, que chama o modelo com as ferramentas.

    O modelo e as ferramentas são definidos na construção do grafo, em
    `scripts/agentic_workflow.py`. Eles entram aqui, e não como importação, porque
    `src/tools.py` já importa este módulo e um import das ferramentas aqui seria circular.

    Args:
        llm_with_tools: Modelo de chat com as ferramentas já ligadas (`bind_tools`).

    Returns:
        Função `assistente(state)`, o nó do grafo. Ela chama o modelo com o prompt de
        sistema (ver `system_prompt_agente`) e as mensagens do estado, e devolve a
        atualização do estado com a resposta do modelo, acrescentada a `messages`.
    """

    def assistente(state: EstadoAgente):
        sys_msg = system_prompt_agente()

        return {"messages": [llm_with_tools.invoke([sys_msg] + state["messages"])]}

    return assistente


def criar_boletim(state: EstadoAgente):
    """Copia o template e o preenche com o resumo do estado, gerando o boletim em arquivo.

    A cópia é gravada na pasta de execução, com data e hora no nome (ver `copy_template`).
    Se o agente encerrou sem chamar `atualizar_summary`, o estado não tem `summary`: o nó
    registra o erro no log e não gera o boletim, para não deixar uma cópia do template sem
    preencher. O nó não atualiza o estado.

    Args:
        state: Estado do agente, do qual são lidos `filepath_template` e `summary`.
    """
    # proteção: sem resumo, não há o que preencher
    if not state.get("summary"):
        logger.error("boletim não gerado: o agente encerrou sem chamar atualizar_summary")
        return

    # copiar template boletim
    boletim_filepath = copy_template(state["filepath_template"])

    # escrever template boletim
    fill_template(dest_filepath=boletim_filepath, summary=state["summary"])
    logger.info(f"boletim gerado em {boletim_filepath}")
