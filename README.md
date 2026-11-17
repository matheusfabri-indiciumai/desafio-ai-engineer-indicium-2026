# Desafio Artificial Intelligence Engineer Certification 2026

A Indicium HealthCare Inc. quer uma solução baseada em dados que ajude profissionais da área da saúde a acompanhar, em tempo real, a severidade e o avanço de surtos de doenças. Neste repositório criamos uma PoC para avaliar a viabilidade do projeto: um fluxo agêntico com LangGraph e Claude que gera relatórios automatizados sobre a Síndrome Respiratória Aguda Grave (SRAG) a partir de dados do Open DATASUS e de notícias recentes. O produto final é um Boletim Epidemiológico com uma análise estatística dos dados do Open DATASUS e a contextualização das informações coletadas de fontes externas.

- [Features](#features)
- [Requisitos](#requisitos)
- [Configuração](#configuração)
- [Como utilizar](#como-utilizar)
  - [Atalhos com make](#atalhos-com-make)
- [Análise exploratória](#análise-exploratória)
- [Documentação](#documentação)
- [Estrutura do projeto](#estrutura-do-projeto)
- [TL;DR](#tldr)

## Features

- **Fluxo agêntico com LangGraph e Claude:** o agente é um grafo com os nós `assistente`, `tools` e `criar_boletim`, que usa um modelo da Anthropic (por padrão `claude-haiku-5-5`, configurável com `--model`).
- **Múltiplas ferramentas:** sete ferramentas locais consultam o dataset limpo (estatísticas do número de casos, crescimento mensal e taxas de mortalidade, de ocupação de UTI e de vacinação) e gravam o resumo do boletim.
- **Busca e coleta de informações na web:** duas ferramentas da web buscam e leem notícias recentes sobre SRAG, em domínios permitidos, para contextualizar os números.
- **Análise exploratória dos dados:** o [eda.ipynb](eda.ipynb) documenta a exploração dos dados, para uma melhor compreensão do cenário e para embasar as escolhas do processamento.
- **Pipeline de processamento de dados:** o [data_fetching_processing.py](scripts/data_fetching_processing.py) lê o dataset do Open DATASUS direto da URL, mantém as colunas de interesse, rotula os valores e descarta os registros com nulos. Depois salva o dataset limpo, com metadados (data de extração, data de criação e porcentagem de dados descartados), e gera os gráficos de casos dos últimos 30 dias e 12 meses.
- **Boletim epidemiológico a partir de um template fixo:** o agente grava um resumo, e o template é preenchido de forma determinística, gerando um boletim padronizado em markdown ([exemplo](docs/boletim_epidemiologico_srag_exemplo.md)).
- **Monitoramento com MLflow:** os traces de cada execução do agente (chamadas, latência, tokens e custo) ficam registrados no MLflow, e o andamento dos scripts, nos logs.

## Requisitos

- **Python 3.11 ou superior:** o projeto fixa a versão 3.11 em `.python-version`, e o `uv` a instala caso ela não esteja disponível.
- **[uv](https://docs.astral.sh/uv/):** gerenciador de pacotes e ambientes usado para instalar as dependências travadas em `uv.lock` e executar os scripts (`uv run`).
- **make (opcional):** usado pelos atalhos do [Makefile](Makefile), geralmente já instalado em Linux e macOS. Os comandos equivalentes estão em [Como utilizar](#como-utilizar).
- **Chave de API da Anthropic:** a variável `ANTHROPIC_API_KEY`, definida em um arquivo `.env` (o `.env.example` é o modelo), com acesso ao modelo usado pelo agente e às ferramentas de busca e coleta na web.

## Configuração

Para a configuração inicial execute os comandos a seguir na root do repositório. Para instalar as dependências do projeto usamos:
```bash
uv sync
```
Esse comando cria o ambiente virtual `.venv` com as versões travadas em `uv.lock`. Já para instalar as dependências para desenvolvimento, que incluem, além das de uso, o `ipykernel` (para abrir o [eda.ipynb](eda.ipynb)), o `ruff`, o `basedpyright` e o `pre-commit` use:
```bash
uv sync --extra dev
```
Para contribuir com o código é sugerido instalar os hooks de pre-commit, que formatam e verificam o código, validam o formato das mensagens de commit e renderizam o prompt do agente:
```bash
uv run pre-commit install
```
Para o uso de modelos Anthropic é necessário gerar uma chave de API da Anthropic no [Console da Anthropic](https://platform.claude.com/settings/keys): em **Settings → API keys**, clique em **Create key**, dê um nome à chave e copie o valor, que só é exibido uma vez. Em seguida, crie o arquivo `.env` a partir do modelo e preencha a variável `ANTHROPIC_API_KEY` com a chave. O `.env` é ignorado pelo git, então a chave não vai para o repositório. Para a cópia do `.env.example` utilize:
```bash
cp .env.example .env
```

## Como utilizar

Execute os comandos sempre a partir da raiz do repositório, pois os scripts usam caminhos relativos a ela. O andamento de cada script é registrado em `logs/<script>.py.log`.

Processar os dados (baixa, limpa e gera os gráficos):

```bash
uv run python -m scripts.data_fetching_processing <url_fonte> [-f <filepath>]
```

Por exemplo, para usar o arquivo extraído do Open DATASUS em 19/10/2026, a `<url_fonte>` é `https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2026/INFLUD26-19-10-2026.parquet`.

Iniciar o servidor do MLflow, que recebe os traces das execuções do agente. Deixe-o rodando em um terminal separado, pois o `agentic_workflow` se conecta a ele ao iniciar. A interface fica em http://localhost:5000:

```bash
uv run mlflow server --host 127.0.0.1 --port 5000
```

Gerar o boletim epidemiológico com o agente (requer `ANTHROPIC_API_KEY` no `.env`, o dataset processado no passo anterior e o servidor do MLflow no ar). O boletim é gravado em `boletins_epidemiologicos/`, as mensagens da conversa com o agente vão para o log à medida que cada nó termina, e os traces ficam no experimento `boletim_epidemiologico` do MLflow:

```bash
uv run python -m scripts.agentic_workflow [--model <modelo>] [--filepath_dataset <filepath>] [--filepath_template <filepath>]
```

Todos os argumentos são opcionais. Além dos acima, `--filepath_plot_12_m` e `--filepath_plot_30_d` definem os caminhos dos gráficos como serão referenciados no boletim, e `--help` mostra os valores padrão.

Renderizar o prompt de sistema do agente em [docs/prompt_agente.md](docs/prompt_agente.md). O hook de pre-commit `render-prompt` faz isso sozinho quando `src/agent.py` ou o script mudam: nesse caso o commit é interrompido para você adicionar o arquivo atualizado (`git add docs/prompt_agente.md`) e commitar de novo.

```bash
uv run python -m scripts.render_prompts
```

### Atalhos com make

O [Makefile](Makefile) tem um alvo para cada etapa acima, e `make help` lista todos: `make data` (aceita outra fonte com `make data URL=<url>`), `make mlflow` (em um terminal separado), `make agent`, `make prompt` e `make clean`. O `make clean` remove os logs, os gráficos, os boletins gerados, o banco do MLflow (`mlflow.db`) e os datasets em `data/`, então será preciso rodar `make data` de novo.

## Análise exploratória

O [eda.ipynb](eda.ipynb) documenta a exploração dos dados que embasa as escolhas do processamento (colunas usadas, tratamento de nulos e data de referência dos casos). Ele é independente dos scripts: baixa o próprio dataset bruto em `data/srag_data_2026.parquet`. Abra-o no VS Code ou no Jupyter com o kernel do `.venv` (o `ipykernel` vem no extra `dev`: `uv sync --extra dev`).

## Documentação

- [docs/arquitetura.md](docs/arquitetura.md): arquitetura da solução, com o pipeline de processamento dos dados, o fluxo do agente (prompt, ferramentas e boletim) e o monitoramento com MLflow e logging.
- [docs/boletim_epidemiologico_srag_exemplo.md](docs/boletim_epidemiologico_srag_exemplo.md): exemplo de boletim epidemiológico preenchido.
- [docs/prompt_agente.md](docs/prompt_agente.md): prompt de sistema do agente.
- [docs/planning.md](docs/planning.md): planejamento da solução e das etapas do desafio.

## Estrutura do projeto

```text
.
├── .githooks/
│   └── commit-msg                   # Valida o formato Conventional Commits
├── boletins_epidemiologicos/        # Boletins gerados pelo agente (arquivos .md ignorados pelo git)
├── data/                            # Datasets baixados e processados (arquivos .parquet ignorados pelo git)
├── docs/
│   ├── arquitetura.md               # Arquitetura da solução: pipeline de dados e fluxo do agente
│   ├── assets/                      # Imagens usadas nos documentos (gráficos do boletim de exemplo)
│   ├── boletim_epidemiologico_srag_exemplo.md  # Exemplo de boletim preenchido pelo agente
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

## TL;DR
