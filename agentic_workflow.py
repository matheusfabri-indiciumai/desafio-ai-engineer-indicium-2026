"""Fluxo agêntico que gera o relatório de SRAG com LangGraph e o Claude.

O grafo tem dois nós em ciclo: `assistente`, que chama o modelo com as ferramentas, e
`tools`, que executa as ferramentas locais pedidas. As ferramentas da web (`busca_web` e
`coleta_web`) são ligadas só ao modelo e rodam nos servidores da Anthropic. O ciclo
termina quando o modelo responde sem pedir novas ferramentas. O estado do agente
(`EstadoAgente`) guarda as mensagens e os caminhos dos arquivos, que são injetados nas
ferramentas locais em vez de passados pelo modelo.

Ao executar, o script grava o diagrama do grafo em `graph_agentic_workflow.png`, roda o
agente com o pedido do relatório e registra as mensagens no arquivo de log. Requer a
variável de ambiente `ANTHROPIC_API_KEY`, por exemplo em um arquivo `.env`.
"""

from pathlib import Path
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AnyMessage
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from src.agent import system_prompt_agente
from src.tools import (
    busca_web,
    coleta_web,
    crescimento_mensal_ultimos_12_m,
    dataframe_info,
    num_casos_mensal_ultimos_12_m,
    taxa_de_vacinacao,
    taxa_periodo,
)
from src.utils import build_logger

# definir logging

logger = build_logger(Path(__file__).name)

# tools

tools = [
    dataframe_info,
    num_casos_mensal_ultimos_12_m,
    crescimento_mensal_ultimos_12_m,
    taxa_de_vacinacao,
    taxa_periodo,
]

load_dotenv()

MODEL_ANTHROPIC = "claude-haiku-5-5"
LOCAL_FILEPATH = "./data/srag_data_2026_clean.parquet"
PLOT_12_M = "./plots/num_casos_12_meses.png"
PLOT_30_D = "./plots/num_casos_30_dias.png"


# definição estado do agente
class EstadoAgente(TypedDict):
    filepath_dataset: str
    plot_num_casos_12_m: str
    plot_num_casos_30_d: str
    messages: Annotated[list[AnyMessage], add_messages]


# definição do modelo
llm = ChatAnthropic(model=MODEL_ANTHROPIC)
llm_with_tools = llm.bind_tools([*tools, coleta_web, busca_web])

# definição do grafo
builder = StateGraph(EstadoAgente)


# definição do nós
def assistente(state: EstadoAgente):
    sys_msg = system_prompt_agente()

    return {"messages": [llm_with_tools.invoke([sys_msg] + state["messages"])]}


# add nós
builder.add_node("assistente", assistente)
builder.add_node("tools", ToolNode(tools))

# add arestas (START -> (assistente <-> tools) -> end)
builder.add_edge(START, "assistente")
builder.add_conditional_edges(
    "assistente",
    tools_condition,
)
builder.add_edge("tools", "assistente")

# buildar app
srag_reporter = builder.compile()

# plotar grafo para visualização
srag_reporter.get_graph().draw_mermaid_png(output_file_path="graph_agentic_workflow.png")

# execução do app
if __name__ == "__main__":
    query = {
        "messages": [("user", "Faça o relatório de SRAG.")],
        "filepath_dataset": LOCAL_FILEPATH,
        "plot_num_casos_12_m": PLOT_12_M,
        "plot_num_casos_30_d": PLOT_30_D,
    }

    response = srag_reporter.invoke(query)
    for message in response["messages"]:
        logger.info(f"[{message.type}] {message.text}")
