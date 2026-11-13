# Desafio Artificial Intelligence Engineer Certification 2026

## Como executar

Execute os comandos sempre a partir da raiz do repositório, pois os scripts usam caminhos relativos a ela. O andamento de cada script é registrado em `logs/<script>.py.log`.

Processar os dados (baixa, limpa e gera os gráficos):

```bash
uv run python -m scripts.data_fetching_processing <url_fonte> [-f <filepath>]
```

URL = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2026/INFLUD26-19-10-2026.parquet"

Iniciar o servidor do MLflow, que recebe os traces das execuções do agente. Deixe-o rodando em um terminal separado, pois o `agentic_workflow` se conecta a ele ao iniciar. A interface fica em http://localhost:5000:

```bash
mlflow server --host 0.0.0.0 --port 5000
```

Gerar o boletim epidemiológico com o agente (requer `ANTHROPIC_API_KEY` no `.env`, o dataset processado no passo anterior e o servidor do MLflow no ar). O boletim é gravado em `boletins_epidemiologicos/`, as mensagens da conversa com o agente vão para o log à medida que cada nó termina, e os traces ficam no experimento `boletim_epidemiologico` do MLflow:

```bash
uv run python -m scripts.agentic_workflow
```

Renderizar o prompt de sistema do agente em [docs/prompt_agente.md](docs/prompt_agente.md). O hook de pre-commit `render-prompt` faz isso sozinho quando `src/agent.py` ou o script mudam: nesse caso o commit é interrompido para você adicionar o arquivo atualizado (`git add docs/prompt_agente.md`) e commitar de novo.

```bash
uv run python -m scripts.render_prompts
```

### Atalhos com make

O [Makefile](Makefile) tem um alvo para cada etapa acima, e `make help` lista todos: `make data` (aceita outra fonte com `make data URL=<url>`), `make mlflow` (em um terminal separado), `make agent`, `make prompt` e `make clean`. O `make clean` remove os logs, os gráficos, os boletins gerados, o banco do MLflow (`mlflow.db`) e os datasets em `data/`, então será preciso rodar `make data` de novo.

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
│   ├── graph_agentic_workflow.png   # Diagrama do grafo do agente (gerado pelo agentic_workflow.py)
│   ├── planning.md                  # Planejamento da solução e das etapas do desafio
│   └── prompt_agente.md             # Prompt de sistema do agente (gerado pelo render_prompts.py)
├── logs/                            # Logs de execução dos scripts (arquivos .log ignorados pelo git)
├── plots/                           # Gráficos gerados pelo script de processamento (.png ignorados pelo git)
├── scripts/
│   ├── __init__.py
│   ├── agentic_workflow.py          # Constrói e executa o grafo do agente (LangGraph) que gera o boletim
│   ├── data_fetching_processing.py  # Download, limpeza e gráficos dos dados
│   └── render_prompts.py            # Renderiza o prompt de sistema do agente em docs/prompt_agente.md
├── src/
│   ├── __init__.py
│   ├── agent.py                     # Prompt, schemas do resumo, estado e nós do agente
│   ├── template_boletim.md          # Template markdown do boletim epidemiológico
│   ├── tools.py                     # Ferramentas do agente
│   └── utils.py                     # Funções utilitárias: filtro de casos, gráfico, logger, template e MLflow
├── .env.example                     # Modelo das variáveis de ambiente (copie para .env e preencha)
├── .gitignore
├── .pre-commit-config.yaml          # Hooks de pre-commit (ruff, basedpyright, render do prompt, entre outros)
├── .python-version                  # Versão do Python usada no projeto
├── eda.ipynb                        # Análise exploratória dos dados
├── Makefile                         # Atalhos para cada etapa (dados, MLflow, agente, prompt, limpeza)
├── pyproject.toml                   # Dependências e configuração das ferramentas (ruff, basedpyright)
├── README.md
└── uv.lock                          # Versões travadas das dependências
```
