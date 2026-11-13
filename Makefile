URL ?= https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/2026/INFLUD26-19-10-2026.parquet

.PHONY: help data prompt mlflow agent clean

help:  ## lista os alvos
	@grep -E '^[a-z_]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/'

data:  ## baixa, limpa e gera os gráficos
	uv run python -m scripts.data_fetching_processing "$(URL)"

prompt:  ## renderiza o prompt em docs/
	uv run python -m scripts.render_prompts

mlflow:  ## sobe o servidor do MLflow (terminal separado)
	uv run mlflow server --host 127.0.0.1 --port 5000

agent:  ## gera o boletim (requer `make data` e `make mlflow` antes)
	uv run python -m scripts.agentic_workflow

clean:  ## remove logs, gráficos, boletins e o banco do MLflow
	rm -f logs/*.log plots/*.png boletins_epidemiologicos/*.md mlflow.db data/*.parquet
