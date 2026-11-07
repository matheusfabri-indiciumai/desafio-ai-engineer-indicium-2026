"""TODO: docstring"""

from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages

load_dotenv()

MODEL_ANTHROPIC = "claude-haiku-5-5"


# definição estado do agente
class EstadoAgente(TypedDict):
    plot_num_casos_30_d: str
    plot_num_casos_12_m: str
    messages: Annotated[list[AnyMessage], add_messages]


# definição do modelo
llm = ChatAnthropic(model=MODEL_ANTHROPIC)
# llm_with_tools = llm.bind_tools(tools, parallel_tool_calls=False)
# tool_node = ToolNode(tools)

# definição do grafo
builder = StateGraph(EstadoAgente)


# def assistente
def assistente(state: EstadoAgente):
    sys_msg = SystemMessage(content="Você responde perguntas em PT-BR de matemática nível PhD.")

    # TODO: inserir llm com tools
    return {"messages": [llm.invoke([sys_msg] + state["messages"])]}


# add nós
builder.add_node("assistant", assistente)
# builder.add_node("tools", ToolNode(tools))

# add arestas (START -> (assistant <-> tools) -> end)
builder.add_edge(START, "assistant")
# builder.add_conditional_edges(
#     "assistant",
#     tools_condition,
# )
# builder.add_edge("tools", "assistant")

# buildar app
srag_reporter = builder.compile()

srag_reporter.get_graph().draw_mermaid_png(output_file_path="graph_agentic_workflow.png")

# uso do app
messages = [
    HumanMessage(content="Me dê um exemplo de uma expressão básica em teoria dependente dos tipos.")
]
response = srag_reporter.invoke({"messages": messages})

print(response["messages"][-1].text)

# if __name__ == "__main__":
#     query = {"messages": [("user", "What is 234 plus 567, and then multiply that result by 3?")]}

#     # Stream the steps of the graph execution
#     for chunk in app.stream(query, stream_mode="values"):
#         last_message = chunk["messages"][-1]
#         last_message.pretty_print()
