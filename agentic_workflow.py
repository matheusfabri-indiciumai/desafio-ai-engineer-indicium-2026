"""Fluxo agêntico que gera o boletim epidemiológico de SRAG com LangGraph e o Claude.

O grafo tem dois nós em ciclo: `assistente`, que chama o modelo com as ferramentas, e
`tools`, que executa as ferramentas locais pedidas, entre elas `atualizar_summary`, que
grava no estado o resumo com os valores do boletim. As ferramentas da web (`busca_web` e
`coleta_web`) são ligadas só ao modelo e rodam nos servidores da Anthropic. O ciclo
termina quando o modelo responde sem pedir novas ferramentas. O nó `criar_boletim`, que
copia o template e o preenche com o resumo, é definido para rodar depois do ciclo, mas
ainda não está ligado ao grafo.

O estado do agente (`EstadoAgente`) guarda as mensagens, o resumo e os caminhos dos
arquivos, que são injetados nas ferramentas locais em vez de passados pelo modelo.

Ao executar, o script grava o diagrama do grafo em `graph_agentic_workflow.png`, roda o
agente com o pedido do boletim epidemiológico e registra as mensagens no arquivo de log.
Requer a variável de ambiente `ANTHROPIC_API_KEY`, por exemplo em um arquivo `.env`.
"""

from pathlib import Path
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AnyMessage
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from src.agent import ResumoBoletim, system_prompt_agente
from src.tools import (
    atualizar_summary,
    busca_web,
    coleta_web,
    crescimento_mensal_ultimos_12_m,
    dataframe_info,
    estatisticas_num_casos,
    num_casos_mensal_ultimos_12_m,
    taxa_de_vacinacao,
    taxa_periodo,
)
from src.utils import build_logger, copy_template, fill_template

# definir logging

logger = build_logger(Path(__file__).name)

# tools

tools = [
    dataframe_info,
    estatisticas_num_casos,
    num_casos_mensal_ultimos_12_m,
    crescimento_mensal_ultimos_12_m,
    taxa_de_vacinacao,
    taxa_periodo,
    atualizar_summary,
]

load_dotenv()

MODEL_ANTHROPIC = "claude-haiku-5-5"
FILEPATH_DATASET = "./data/srag_data_2026_clean.parquet"
PLOT_12_M = "../plots/num_casos_12_meses.png"
PLOT_30_D = "../plots/num_casos_30_dias.png"
FILEPATH_TEMPLATE = "./src/template_boletim.md"


# definição estado do agente
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


# definição do modelo
llm = ChatAnthropic(model=MODEL_ANTHROPIC)
llm_with_tools = llm.bind_tools([*tools, coleta_web, busca_web])


# definição do grafo
builder = StateGraph(EstadoAgente)


# definição do nós
def assistente(state: EstadoAgente):
    """Chama o modelo com o prompt de sistema, as mensagens do estado e as ferramentas.

    Args:
        state: Estado do agente, do qual são lidas as mensagens.

    Returns:
        Atualização do estado com a resposta do modelo, acrescentada a `messages`.
    """
    sys_msg = system_prompt_agente()

    return {"messages": [llm_with_tools.invoke([sys_msg] + state["messages"])]}


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


# add nós
builder.add_node("assistente", assistente)
builder.add_node("tools", ToolNode(tools))
builder.add_node("criar_boletim", criar_boletim)

# add arestas (START -> (assistente <-> tools), (assistente -> criar_boletim) -> end)
builder.add_edge(START, "assistente")
builder.add_conditional_edges(
    "assistente", tools_condition, path_map={"tools": "tools", "__end__": "criar_boletim"}
)
builder.add_edge("tools", "assistente")


# buildar app
srag_reporter = builder.compile()


# plotar grafo para visualização
srag_reporter.get_graph().draw_mermaid_png(output_file_path="./docs/graph_agentic_workflow.png")


# execução do app
if __name__ == "__main__":
    query = {
        "messages": [("user", "Faça o boletim epidemiológico de SRAG.")],
        "filepath_dataset": FILEPATH_DATASET,
        "plot_num_casos_12_m": PLOT_12_M,
        "plot_num_casos_30_d": PLOT_30_D,
        "filepath_template": FILEPATH_TEMPLATE,
    }

    response = srag_reporter.invoke(query)
    for message in response["messages"]:
        logger.info(f"[{message.type}] {message.text}")
