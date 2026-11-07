"""TODO: defs"""

from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


# definição estado do agente
class EstadoAgente(TypedDict):
    plot_num_casos_30_d: str
    plot_num_casos_12_m: str
    messages: Annotated[list[AnyMessage], add_messages]
