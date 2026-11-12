"""Monta e executa o grafo do agente que gera o boletim epidemiológico de SRAG.

O script só constrói o grafo com LangGraph: define o modelo (Claude) e as ferramentas, e
liga os nós por arestas. O estado do agente (`EstadoAgente`) e os nós (`assistente` e
`criar_boletim`) ficam em `src/agent.py`, e as ferramentas, em `src/tools.py`.

O grafo tem dois nós em ciclo: `assistente`, que chama o modelo com as ferramentas, e
`tools`, que executa as ferramentas locais pedidas, entre elas `atualizar_summary`, que
grava no estado o resumo com os valores do boletim. As ferramentas da web (`busca_web` e
`coleta_web`) são ligadas só ao modelo e rodam nos servidores da Anthropic. O ciclo
termina quando o modelo responde sem pedir novas ferramentas, e então roda o nó
`criar_boletim`, que copia o template e o preenche com o resumo gravado no estado.

Ao executar, o script grava o diagrama do grafo em `docs/graph_agentic_workflow.png`, roda
o agente com o pedido do boletim epidemiológico e registra no arquivo de log as mensagens
de cada nó, à medida que ele termina (`stream`), em vez de só ao fim da execução.
Requer a variável de ambiente `ANTHROPIC_API_KEY`, por exemplo em um arquivo `.env`.

Uso, a partir da raiz do repositório: `uv run python -m scripts.agentic_workflow`.
"""

from pathlib import Path

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langgraph.graph import START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src.agent import EstadoAgente, criar_boletim, criar_no_assistente
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
from src.utils import build_logger

# definir logging

logger = build_logger(Path(__file__).name)

load_dotenv()

# constantes

MODEL_ANTHROPIC = "claude-haiku-5-5"
FILEPATH_DATASET = "./data/srag_data_2026_clean.parquet"
PLOT_12_M = "../plots/num_casos_12_meses.png"
PLOT_30_D = "../plots/num_casos_30_dias.png"
FILEPATH_TEMPLATE = "./src/template_boletim.md"

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

# definição do modelo

llm = ChatAnthropic(model=MODEL_ANTHROPIC)
llm_with_tools = llm.bind_tools([*tools, coleta_web, busca_web])

# definição do grafo

builder = StateGraph(EstadoAgente)

# add nós
builder.add_node("assistente", criar_no_assistente(llm_with_tools))
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

    logger.info(f"iniciando o agente com o modelo {MODEL_ANTHROPIC} e o dataset {FILEPATH_DATASET}")

    try:
        for step in srag_reporter.stream(query, stream_mode="updates"):
            for update in step.values():
                for message in (update or {}).get("messages", []):
                    logger.info(f"[{message.type}] {message.text}")
    except Exception:
        logger.exception("falha na execução do agente")
        raise
