"""Renderiza o prompt de sistema do agente em um arquivo markdown para consulta.

Chama `system_prompt_agente` e grava o texto, dentro de um bloco de código, em
`docs/prompt_agente.md`, sobrescrevendo o arquivo. O arquivo é gerado automaticamente pelo
hook de pre-commit `render-prompt`, sempre que `src/agent.py` ou este script mudam, então
não deve ser editado à mão. A data no `<contexto>` do prompt é uma data de exemplo fixa
(`DATA_EXEMPLO`), para que o arquivo só mude quando o prompt mudar, e não a cada dia em que
o script roda.

Uso, a partir da raiz do repositório: `uv run python -m scripts.render_prompts`.
"""

import datetime
from pathlib import Path

from src.agent import system_prompt_agente

ROOT = Path(__file__).resolve().parents[1]
FILEPATH_PROMPT = ROOT / "docs" / "prompt_agente.md"
DATA_EXEMPLO = datetime.date(2026, 1, 1)

HEADER = (
    "# Prompt do agente\n\n"
    "Prompt de sistema do agente que gera o boletim epidemiológico de SRAG, montado por "
    "`system_prompt_agente` em `src/agent.py`. Este arquivo é gerado por "
    "`scripts/render_prompts.py` (hook de pre-commit): não edite manualmente.\n\n"
)

FOOTER = (
    "\nOs campos que o agente preenche com os valores extraídos (passo 8) estão descritos nos "
    "schemas `ResumoAgente` e `ResumoBoletim`, em `src/agent.py`. A data no `<contexto>` é "
    "apenas um exemplo fixo (01/01/2026): na execução do agente, é a data de hoje.\n"
)

markdown_content = HEADER + f"```\n{system_prompt_agente(DATA_EXEMPLO).content}\n```\n" + FOOTER

FILEPATH_PROMPT.write_text(markdown_content, encoding="utf-8")
