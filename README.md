# Desafio Artificial Intelligence Engineer Certification 2026

## Como executar

Execute os comandos sempre a partir da raiz do repositório, pois os scripts usam caminhos
relativos a ela.

Processar os dados (baixa, limpa e gera os gráficos):

```bash
uv run python -m scripts.data_fetching_processing <url_fonte> [-f <filepath>]
```

URL = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2026/INFLUD26-19-10-2026.parquet"

Gerar o boletim epidemiológico com o agente (requer `ANTHROPIC_API_KEY` no `.env` e o dataset processado no passo anterior):

```bash
uv run python -m scripts.agentic_workflow
```

Ver o prompt de sistema do agente:

```bash
uv run python -m scripts.render_prompts
```

## Análise exploratória

O [eda.ipynb](eda.ipynb) documenta a exploração dos dados que embasa as escolhas do processamento (colunas usadas, tratamento de nulos e data de referência dos casos). Ele é independente dos scripts: baixa o próprio dataset bruto em `data/srag_data_2026.parquet`. Abra-o no VS Code ou no Jupyter com o kernel do `.venv` (o `ipykernel` vem no extra `dev`: `uv sync --extra dev`).

## Estrutura do projeto

```text
.
├── .githooks/
│   └── commit-msg                   # Valida o formato Conventional Commits
├── boletins_epidemiologicos/        # Boletins gerados pelo agente (arquivos .md ignorados pelo git)
├── data/                            # Datasets baixados e processados (arquivos .parquet ignorados pelo git)
├── docs/
│   ├── graph_agentic_workflow.png   # Diagrama do grafo do agente
│   └── planning.md                  # Planejamento da solução e das etapas do desafio
├── logs/                            # Logs de execução dos scripts
├── plots/                           # Gráficos gerados pelo script de processamento (.png ignorados pelo git)
├── scripts/
│   ├── __init__.py
│   ├── agentic_workflow.py          # Fluxo agêntico com LangGraph que gera o boletim
│   ├── data_fetching_processing.py  # Download, limpeza e gráficos dos dados
│   └── render_prompts.py            # Imprime o prompt de sistema do agente
├── src/
│   ├── __init__.py
│   ├── agent.py                     # Prompt do agente e schemas do resumo do boletim
│   ├── template_boletim.md          # Template markdown do boletim epidemiológico
│   ├── tools.py                     # Ferramentas do agente
│   └── utils.py                     # Funções utilitárias: filtro de casos, gráfico, logger e template
├── .env.example                     # Modelo das variáveis de ambiente (copie para .env e preencha)
├── .gitignore
├── .pre-commit-config.yaml          # Hooks de pre-commit (ruff, basedpyright, entre outros)
├── .python-version                  # Versão do Python usada no projeto
├── eda.ipynb                        # Análise exploratória dos dados
├── pyproject.toml                   # Dependências e configuração das ferramentas (ruff, basedpyright)
├── README.md
└── uv.lock                          # Versões travadas das dependências
```
