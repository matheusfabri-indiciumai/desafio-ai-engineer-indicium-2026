# Desafio Artificial Intelligence Engineer Certification 2026

## Comando

```bash
uv run src/data_fetching_processing.py <url_fonte> [-f <filepath>]
```

URL = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2026/INFLUD26-19-10-2026.parquet"

## Estrutura do projeto

```text
.
├── .githooks/
│   └── commit-msg                   # Valida o formato Conventional Commits
├── data/                            # Datasets baixados e processados (arquivos .parquet ignorados pelo git)
├── docs/
│   └── planning.md                  # Planejamento da solução e das etapas do desafio
├── plots/                           # Gráficos gerados pelo script de processamento (.png ignorados pelo git)
├── src/
│   ├── __init__.py
│   ├── agent.py                     # Estado do agente (em desenvolvimento)
│   ├── data_fetching_processing.py  # Script de download, limpeza e gráficos dos dados
│   ├── tools.py                     # Ferramentas do agente (em desenvolvimento)
│   └── utils.py                     # Funções utilitárias: filtro de casos, gráfico e logger
├── .env.example                     # Modelo das variáveis de ambiente (copie para .env e preencha)
├── .gitignore
├── .pre-commit-config.yaml          # Hooks de pre-commit (ruff, basedpyright, entre outros)
├── .python-version                  # Versão do Python usada no projeto
├── agentic_workflow.py              # Fluxo agêntico com LangGraph (em desenvolvimento)
├── eda.ipynb                        # Análise exploratória dos dados
├── pyproject.toml                   # Dependências e configuração das ferramentas (ruff, basedpyright)
├── README.md
└── uv.lock                          # Versões travadas das dependências
```
