# PoC — Arquitetura do Assistente HealthCare Bot

- [Contexto](#contexto)
- [Pipeline de Processamento de Dados](#pipeline-de-processamento-de-dados)
- [Fluxo Agêntico](#fluxo-agêntico)
  - [Workflow](#workflow)
  - [Prompt](#prompt)
  - [Ferramentas](#ferramentas)
  - [Boletim Epidemiológico](#boletim-epidemiológico)
- [Monitoramento: MLflow e Logging](#monitoramento-mlflow-e-logging)
  - [MLflow](#mlflow)
  - [Logging](#logging)
- [Possíveis Extensões](#possíveis-extensões)
- [Conclusão](#conclusão)
- [TL;DR](#tldr)

## Contexto

A Indicium HealthCare Inc. quer uma solução baseada em dados que ajude profissionais da área da saúde a acompanhar, em tempo real, a severidade e o avanço de surtos de doenças. Para avaliar a viabilidade dessa solução, foi proposta uma PoC: o **HealthCare Bot**, um agente de IA generativa que consulta os dados de internações por Síndrome Respiratória Aguda Grave (SRAG) do Open DATASUS e notícias recentes sobre o tema, e gera de forma automatizada um **Boletim Epidemiológico**.

O boletim traz as métricas de taxa de aumento de casos, taxa de mortalidade, taxa de ocupação de UTI e taxa de vacinação, além de dois gráficos do número de casos (últimos 30 dias e últimos 12 meses), acompanhados de explicações que ajudam a compreender o cenário. Nas próximas seções descrevemos o pipeline de processamento dos dados, o fluxo agêntico, o monitoramento da aplicação e as possíveis extensões da PoC para criar um produto final.

## Pipeline de Processamento de Dados

Com base na análise exploratória de dados feita no notebook [eda.ipynb](../eda.ipynb), realizamos primeiramente o download, a limpeza e o processamento dos dados, para que o agente possa, com base neles, criar o Boletim Epidemiológico. Todo o processamento é feito pelo [data_fetching_processing.py](../scripts/data_fetching_processing.py), seguindo os passos:
1. Ele lê, a partir da URL passada, um arquivo `parquet` com os dados (a leitura é feita direto da URL, sem salvar o arquivo bruto). Note que aqui lemos somente as colunas de interesse para a análise, sendo estas:
    - `NU_NOTIFIC`: número de registro sequencial da ficha de notificação, gerado automaticamente pelo sistema. Usamos como identificador do caso, então ele serve como proxy para o número de casos através de um `count`.
    - `DT_SIN_PRI`: data dos primeiros sintomas do caso. É a data de referência das séries temporais (casos diários nos últimos 30 dias, casos mensais nos últimos 12 meses e taxa de crescimento de casos). Preferimos esta à data de notificação (`DT_NOTIFIC`) porque as notificações têm uma periodicidade semanal, com queda no fim de semana por falta de registros, enquanto a data dos sintomas reflete melhor quando o caso de fato ocorreu.
    - `EVOLUCAO`: desfecho do caso (1 - cura, 2 - óbito, 3 - óbito por outras causas, 9 - ignorado). Usamos para calcular a taxa de mortalidade.
    - `VACINA_COV`: indica se o paciente recebeu a vacina contra a COVID-19, conferida na caderneta ou em outra documentação (1 - sim, 2 - não, 9 - ignorado). Usamos para calcular a taxa de vacinação entre os casos.
    - `UTI`: indica se o paciente foi internado em UTI (1 - sim, 2 - não, 9 - ignorado). Usamos para calcular a taxa de ocupação de UTI, isto é, a proporção dos casos que foram internados em UTI.
2. Em seguida, rotulamos e agregamos alguns dados, isto é:
    - Agregamos os óbitos por SRAG e por demais causas (`EVOLUCAO` 2 e 3) como `obito` para simplificar a análise, e rotulamos os demais códigos como texto (`cura`, `vacinado`, `nao_vacinado`, `uti` e `nao_uti`).
    - Rotulamos como nulos os campos ignorados (código 9) na ficha de SRAG do Ministério da Saúde, como, por exemplo, o status da vacinação por COVID-19 e a internação ou não na UTI. O mesmo vale para o código 9 de `EVOLUCAO`, que não está no mapeamento.
3. Com isso, descartamos os registros com nulos em `EVOLUCAO`, `VACINA_COV` ou `UTI`, pois estamos interessados nas taxas de mortalidade, de cobertura vacinal e de internação em UTI.
4. Extraímos então a data de extração (presente no nome do arquivo baixado, e.g. `INFLUD26-19-10-2026.parquet`), a data de criação do dataset (dia de execução do script `data_fetching_processing.py`) e a porcentagem dos dados descartados, e salvamos esses valores como metadados da tabela limpa (`data_extracao`, `data_criacao` e `pct_dados_descartados`). A ideia é que o agente possa extrair essas informações diretamente do dataset para contextualizar a análise. Se o nome do arquivo não seguir esse padrão, a data de extração não é salva e o script registra um aviso no log.
5. Com esses metadados e a tabela limpa, salvamos então os dados em `./data/srag_data_2026_clean.parquet` (ou no caminho passado em `-f`).
6. Por fim, sem relação direta com a análise acima, criamos, a partir da tabela limpa, os gráficos do número diário de casos nos últimos 30 dias e nos últimos 12 meses (365 dias) e os salvamos em `./plots/num_casos_30_dias.png` e `./plots/num_casos_12_meses.png`, respectivamente.

Algumas observações:
- **Viés nos dados mais recentes:** no arquivo analisado no EDA, o descarte dos nulos retira aproximadamente 23% dos registros, e aceitamos essa perda. Ela não é uniforme no tempo: casos recentes ainda sem desfecho (`EVOLUCAO` nulo) na data de extração são descartados, o que tende a subestimar o número de casos dos últimos dias. Provavelmente por isso, e também por atraso de notificação, o valor final da série, que coincide com o último dia do dataset, costuma ser o mínimo.
- **Atualização dos casos:** o dataset é um retrato estático do momento da extração (`data_extracao`), então os números mudam a cada novo arquivo publicado pelo Open DATASUS, pois casos novos são notificados e desfechos de casos antigos são preenchidos depois. Por isso consideramos a data mais recente de primeiros sintomas como o fim da janela de análise (e não a data de execução) e, como usamos só o arquivo de 2026, a janela de 12 meses cobre menos de 12 meses reais. Para atualizar o boletim basta rodar de novo o processamento com a URL do arquivo mais novo.
- **Data de notificação x data dos primeiros sintomas:** comparamos as duas séries temporais de número de casos no EDA. A série por data de notificação tem periodicidade semanal (a transformada de Fourier mostra pico por volta de 7 dias), com queda no fim de semana por falta de notificações, e a correlação das duas séries é moderada. Ao suavizar a série de notificação com uma média móvel semanal centrada, a correlação com a série por primeiros sintomas passa a ser alta. Como as duas passam a carregar a mesma informação, o uso das duas seria redundante e ficamos só com `DT_SIN_PRI`.

## Fluxo Agêntico

Nesta seção descrevemos o fluxo de processamento do agente HealthCare Bot, seu prompt e as ferramentas construídas. Começamos com o grafo que define o fluxo que o agente segue, depois descrevemos o prompt que ele segue, as ferramentas às quais ele tem acesso e, por fim, o resultado: o **Boletim Epidemiológico** preenchido.

### Workflow

Para a construção do agente usamos o LangGraph. Isso nos permite definir um grafo de etapas para o agente seguir, com alto controle sobre cada etapa e com a possibilidade de guardar informações necessárias no estado do agente para passá-las ao próximo passo. Todo o procedimento para geração do Boletim Epidemiológico está presente em [agentic_workflow.py](../scripts/agentic_workflow.py), lá realizamos os seguintes passos:
1. Configuramos o MLflow (`mlflow_setup`) para o registro dos traces das execuções do agente (ver [Monitoramento: MLflow e Logging](#monitoramento-mlflow-e-logging)).
2. Definimos o modelo a ser usado, aqui optamos por um modelo Anthropic, `claude-haiku-5-5`, o que exige uma chave de API definida no `.env`. Contudo, o framework é genérico o suficiente para podermos trocar por outro provedor se assim for desejado, exceto pelas ferramentas da web (`busca_web` e `coleta_web`), que rodam nos servidores da Anthropic e teriam de ser substituídas.
3. Adicionamos as ferramentas criadas ao modelo LLM, construindo assim um agente de fato (ver [Ferramentas](#ferramentas)).
4. Definimos o estado do agente, `EstadoAgente`, que guarda as informações necessárias para o processamento: os caminhos do dataset, dos gráficos e do template, o resumo (`summary`) e o histórico de mensagens (ver [Estado do agente](#estado-do-agente)).
5. Com base nesse estado criamos o grafo de processamento que o agente segue, mostrado a seguir:

    ```mermaid
    flowchart TD
        START([__start__]) --> assistente[assistente]
        assistente -- "tool_call" --> tools[tools]
        tools --> assistente
        assistente -- "sem tool_call" --> criar_boletim[criar_boletim]
        criar_boletim --> END([__end__])
    ```
6. O agente então segue os passos definidos pelo grafo:
    - O agente inicia no nó `__start__`.
    - Então, no nó `assistente`, o agente recebe um prompt com todos os passos que deve seguir para preencher o atributo `summary` de `EstadoAgente` com um JSON estruturado, construído para preencher o template do Boletim Epidemiológico (ver [Prompt](#prompt)). O preenchimento é feito pela ferramenta `atualizar_summary`: os caminhos dos gráficos vêm do estado, sem passar pelo modelo, e o `summary` só existe depois dessa chamada.
    - Em `assistente` há duas opções. Caso o modelo faça uma chamada de ferramenta (`tool_call`), o fluxo é redirecionado para o nó `tools`, que executa a ferramenta chamada e devolve a resposta ao nó `assistente`. Isso vale para as ferramentas locais: as da web (`busca_web` e `coleta_web`) rodam nos servidores da Anthropic e não passam pelo nó `tools`. No entanto, caso o modelo não chame ferramentas, o fluxo segue para o próximo nó, `criar_boletim`.
    - Este nó pega o atributo `summary` preenchido no nó anterior, copia o template e o preenche, gerando o boletim em `boletins_epidemiologicos/` (ver [Boletim Epidemiológico](#boletim-epidemiológico)). Note que o preenchimento é determinístico: neste ponto não realizamos uma chamada ao modelo. Se o agente tiver encerrado sem chamar `atualizar_summary`, o nó registra o erro no log e não gera o boletim.
7. Com isso, o fluxo se encerra em `__end__`.

Algumas observações:
- **Prompt inicial e parâmetros iniciais:** o agente é chamado com a mensagem do usuário `Faça o boletim epidemiológico de SRAG.` e com os valores iniciais do estado (os caminhos do dataset, dos dois gráficos e do template), definidos, assim como o modelo usado, por argumentos de linha de comando de `agentic_workflow.py` (`--model`, `--filepath_dataset`, `--filepath_plot_12_m`, `--filepath_plot_30_d` e `--filepath_template`), todos opcionais e com um valor padrão. O prompt de sistema, com os passos que o agente segue, é descrito na seção [Prompt](#prompt).
- **Ordem de execução:** o agente depende dos arquivos gerados pelo `data_fetching_processing.py` (o dataset limpo e os gráficos), então este script deve ser executado antes do agente. O servidor do MLflow também precisa estar no ar, pois a configuração do MLflow é feita ao iniciar o `agentic_workflow.py`. Os comandos estão no [README](../README.md).
- **Módulos auxiliares:** o `agentic_workflow.py` só monta o grafo, e o restante fica em `src/`: o prompt, os schemas do resumo, o estado e os nós em `agent.py`, as ferramentas em `tools.py`, as funções utilitárias (gráficos, logger, template e MLflow) em `utils.py` e o template do boletim em `template_boletim.md`.

#### Estado do agente

O `EstadoAgente` é compartilhado entre os nós do grafo, e cada atributo tem um papel:

| Atributo | Descrição | O que vai no campo |
| --- | --- | --- |
| `filepath_dataset` | Caminho do dataset processado, injetado nas ferramentas locais. | `./data/srag_data_2026_clean.parquet`, gerado pelo `data_fetching_processing.py`. |
| `plot_num_casos_12_m` | Caminho do gráfico do número diário de casos dos últimos 12 meses, injetado em `atualizar_summary`. | `../plots/num_casos_12_meses.png`, relativo à pasta `boletins_epidemiologicos/`, onde o boletim é gravado. |
| `plot_num_casos_30_d` | Caminho do gráfico do número diário de casos dos últimos 30 dias, injetado em `atualizar_summary`. | `../plots/num_casos_30_dias.png`, relativo à pasta `boletins_epidemiologicos/`. |
| `filepath_template` | Caminho do template markdown do boletim. | `./src/template_boletim.md`. |
| `summary` | Resumo com os valores que preenchem o template, com um campo para cada `{campo}` do template (`ResumoBoletim`). | Começa vazio e só existe depois de o agente chamar `atualizar_summary`. O agente preenche os campos de texto e a ferramenta acrescenta os caminhos dos gráficos. O nó `criar_boletim` o lê para preencher o template. |
| `messages` | Histórico de mensagens da conversa, acumulado a cada nó. | Começa com o pedido do usuário (`Faça o boletim epidemiológico de SRAG.`) e recebe as respostas do modelo e das ferramentas. |

Os caminhos e a mensagem inicial são passados na chamada do agente, em `agentic_workflow.py`, e `summary` é o único atributo preenchido durante a execução.

### Prompt

No nó `assistente`, o agente recebe o prompt de sistema para realizar a consulta dos dados e a interpretação, e então escrever o atributo `summary` no estado do agente com as informações necessárias do boletim epidemiológico. O prompt utilizado pelo agente está em [agent.py](../src/agent.py) e o renderizamos para consulta em [prompt_agente.md](prompt_agente.md), por meio do `render_prompts.py` via um hook de pre-commit. O prompt segue as melhores práticas de engenharia de prompt da Anthropic ([Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)) e começa definindo o papel do agente (analista de dados de saúde pública) e o idioma das respostas (PT-BR). Em seguida, é dividido em cinco partes, delimitadas por tags XML: `contexto`, `objetivo`, `schema_dataset`, `regras` e `passos`. Em cada parte temos:
- `contexto`: aqui contextualizamos o agente com a data de emissão do boletim (inserida pelo código), a explicação básica sobre a SRAG e sobre a origem e o monitoramento dos dados.
- `objetivo`: aqui definimos o que o agente deve extrair (número de casos, taxa de aumento de casos, taxas de mortalidade e de ocupação de UTI e taxa de vacinação), a busca de notícias para contextualização e a realização de interpretações dos dados, com conclusão e recomendações.
- `schema_dataset`: informação básica sobre as colunas do dataset, como nomes, tipos, descrição e valores possíveis, com o aviso de que os registros ignorados ou nulos foram removidos.
- `regras`: restrições ao comportamento do agente:
    - a taxa de vacinação é a proporção de vacinados entre os casos, não a cobertura vacinal da população;
    - os valores finais seguem o padrão brasileiro (datas em DD/MM/AAAA, ponto nos milhares, vírgula nos decimais e taxas com duas casas e o símbolo %), e o agente converte o que as ferramentas devolvem;
    - os caminhos dos arquivos são injetados nas ferramentas, então o agente não os pede nem os informa;
    - a web só contextualiza os números, nunca os substitui, e é restrita a domínios permitidos, com citação obrigatória da fonte e um limite de usos por execução;
    - o agente não estima informações indisponíveis.
- `passos`: aqui temos o fluxo seguido pelo agente em si, um checklist de oito passos seguidos na ordem, cada um com a ferramenta a chamar e o que extrair do dataset já limpo e processado:
    1. `dataframe_info`, para as datas do período e os metadados do dataset.
    2. `estatisticas_num_casos`, para as estatísticas do número de casos em 30 dias e em 12 meses.
    3. `num_casos_mensal_ultimos_12_m` e `crescimento_mensal_ultimos_12_m`, para a tabela de crescimento mensal.
    4. `taxa_de_vacinacao`, para a proporção de vacinados e de não vacinados.
    5. `taxa_periodo`, chamada quatro vezes, para as taxas de mortalidade e de ocupação de UTI em 30 dias e em 12 meses.
    6. Busca e leitura de notícias recentes sobre SRAG na web.
    7. Redação do resumo, das interpretações, da conclusão e das recomendações.
    8. `atualizar_summary`, chamada uma única vez, com todas as informações extraídas, processadas, analisadas e contextualizadas para a criação do boletim epidemiológico. Os caminhos dos gráficos não são preenchidos pelo agente: são adicionados automaticamente.

Ao realizar todos os passos, o agente recebe a confirmação de `atualizar_summary` e encerra o turno sem repetir o resumo. Como não há mais chamadas de ferramenta, o fluxo segue para o nó `criar_boletim`.

### Ferramentas

As ferramentas utilizadas pelo agente são descritas na tabela a seguir e estão todas presentes em [tools.py](../src/tools.py):

| Ferramenta | Descrição |
| --- | --- |
| `dataframe_info` | Informações gerais do dataset: dimensões, datas mínima e máxima de `DT_SIN_PRI` e os metadados do arquivo (`data_criacao`, `data_extracao` e `pct_dados_descartados`). |
| `estatisticas_num_casos` | Estatísticas do número diário de casos nos últimos 30 dias e 12 meses: total, média, desvio padrão e os dias de máximo e de mínimo, com a quantidade e a data. |
| `num_casos_mensal_ultimos_12_m` | Número de casos por mês nos últimos 12 meses, indexado pelo último dia de cada mês. O primeiro e o último mês podem ser parciais. |
| `crescimento_mensal_ultimos_12_m` | Variação percentual do número de casos de cada mês em relação ao mês anterior, nos últimos 12 meses. O primeiro mês não tem variação, e a do último mês, parcial, tende a ser fortemente negativa sem representar uma queda real. |
| `taxa_de_vacinacao` | Número de casos e porcentagem por situação de vacinação contra a COVID-19 (`vacinado` e `nao_vacinado`), em todo o dataset. É a proporção de vacinados entre os casos, não a cobertura vacinal da população. |
| `taxa_periodo` | Número de casos e porcentagem por categoria de `EVOLUCAO` ou `UTI` nos últimos `dias_filtro` dias, base das taxas de mortalidade e de ocupação de UTI. O agente informa `dias_filtro` e a coluna (`col_target`). |
| `atualizar_summary` | Grava no estado do agente o resumo (`summary`) com os valores que preenchem o boletim. Acrescenta ao resumo os caminhos dos gráficos, vindos do estado, e responde com uma confirmação curta. Deve ser chamada uma única vez, e uma nova chamada substitui o resumo anterior. |
| `busca_web` (`web_search`) | Busca de notícias recentes sobre SRAG na web, restrita a domínios permitidos. |
| `coleta_web` (`web_fetch`) | Leitura do conteúdo das páginas encontradas na busca, também restrita a domínios permitidos. |

Algumas observações:
- **Ferramentas da web:** `busca_web` e `coleta_web` rodam nos servidores da Anthropic, e não localmente. Por isso são ligadas apenas ao modelo (`bind_tools`) e ficam fora do nó `tools`. Cada uma tem um limite de 5 usos por execução e só acessa os domínios permitidos (`cnnbrasil.com.br`, `agencia.fiocruz.br`, `agenciabrasil.ebc.com.br` e as páginas de SRAG do Ministério da Saúde em `gov.br/saude/pt-br`). Os nomes entre parênteses na tabela são os usados pela API e pelo prompt.
- **Ferramentas de leitura de dados:** as seis primeiras da tabela leem o dataset limpo, gerado pelo `data_fetching_processing.py`. O caminho do arquivo é injetado do estado do agente (`filepath_dataset`), então o modelo não o informa nem o vê. O mesmo vale para os caminhos dos gráficos em `atualizar_summary`.
- **Janelas de tempo:** as janelas de 30 dias e de 12 meses (365 dias) terminam na data mais recente de primeiros sintomas do dataset, e não na data de execução. Como os últimos dias estão incompletos por atraso de notificação, o mínimo do número diário de casos costuma cair nesse período.
- **Formato dos retornos:** as ferramentas devolvem dados serializáveis em JSON, com datas em `AAAA-MM-DD` e números com ponto decimal. A conversão para o padrão brasileiro (datas em DD/MM/AAAA e vírgula nos decimais) é feita pelo agente, conforme as regras do prompt.

### Boletim Epidemiológico

O objetivo final do fluxo agêntico é a criação do **Boletim Epidemiológico de SRAG** em markdown. O nó `criar_boletim` copia o template do boletim (presente em [template_boletim.md](../src/template_boletim.md)) para o diretório [boletins_epidemiologicos](../boletins_epidemiologicos/) e preenche a cópia. Note que este passo é determinístico: o agente somente preenche `summary` e nós usamos as informações presentes nele para substituir cada campo `{campo}` do template. O Boletim Epidemiológico é nomeado com o timestamp no padrão `boletim_epidemiologico_srag__YYYY_MM_DD__HH_MM_SS.md`, para não sobrescrever boletins anteriores, e segue um formato fixo, para padronização, com as seguintes partes:
- **Header:** título, destinatário (Indicium HealthCare Inc.), autoria (HealthCare Bot, o agente de IA), data de emissão, período analisado e fonte dos dados, com a data de extração. Traz também o aviso de que o documento foi gerado automaticamente por um agente de IA e deve ser revisado por um profissional antes de ser usado em decisões.
- **Resumo:** parágrafo curto, escrito pelo agente, com a situação do número de casos, as principais taxas e o contexto trazido pelas notícias.
- **Sumário:** índice com links para as seções e subseções do boletim.
- **Introdução:** texto fixo sobre o que é a SRAG e sobre o objetivo do boletim para o período analisado.
- **Métodos:** texto fixo que descreve o estudo (descritivo), o banco de dados (Sivep-Gripe, publicado no Open DATASUS, e as notícias da web como fonte complementar), a definição de casos, a coleta e o tratamento dos dados (colunas usadas, rotulagem e descarte dos nulos, com a porcentagem descartada e a data de extração) e as análises (janelas de tempo, estatísticas e taxas). O período, a data de extração e a porcentagem de dados descartados são preenchidos a partir do `summary`.
- **Resultados e Discussão:** dividido em duas partes:
    - *Número de casos:* os gráficos dos últimos 30 dias e dos últimos 12 meses, com a interpretação do agente; a tabela de estatísticas (total, média, desvio padrão e dias de máximo e de mínimo); e a tabela de crescimento mensal, com uma nota sobre os dados incompletos dos últimos dias e a interpretação do agente.
    - *Demais métricas:* as tabelas de mortalidade e ocupação de UTI (30 dias e 12 meses) e de vacinação, com uma interpretação do agente.
- **Últimas notícias sobre SRAG:** lista das notícias encontradas na web (título, fonte, URL e um resumo de cada uma) e a análise do impacto delas e de sua relação com os dados.
- **Conclusão e recomendações:** conclusão do agente, retomando os principais achados, e recomendações para a Indicium HealthCare Inc., cada uma ligada a um achado dos dados.
- **Referências bibliográficas:** as fontes dos dados (Open DATASUS e o dicionário de dados) e a referência metodológica (Boletim Epidemiológico do Ministério da Saúde), que são fixas no template, e as fontes das demais informações, como as notícias, preenchidas pelo agente.

Em [boletim_epidemiologico_srag_exemplo.md](boletim_epidemiologico_srag_exemplo.md) fornecemos um exemplo de Boletim Epidemiológico preenchido.

## Monitoramento: MLflow e Logging

O monitoramento da aplicação é feito por dois mecanismos complementares: o MLflow, para o comportamento do agente a cada execução, e o logging padrão do Python, para o andamento dos scripts. A seguir detalhamos cada um.

### MLflow

O MLflow registra o comportamento do agente em cada execução. Ao iniciar, o [agentic_workflow.py](../scripts/agentic_workflow.py) chama `mlflow_setup` (em [utils.py](../src/utils.py)), que:
1. conecta ao servidor de tracking em `http://localhost:5000`;
2. cria o experimento `boletim_epidemiologico`, caso ele ainda não exista, e registra no log se o experimento foi encontrado ou criado;
3. liga o `mlflow.langchain.autolog()`, que registra automaticamente os traces do LangChain e do LangGraph;
4. define esse experimento como o ativo.

Com isso, todas as execuções ficam no mesmo experimento, e cada uma gera um trace com as chamadas feitas ao modelo e às ferramentas. Em cada trace é possível ver a entrada e a saída de cada etapa, a latência, o uso de tokens e o custo estimado.

Para subir o servidor, basta usar `make mlflow` em um terminal separado ou, mais diretamente, `uv run mlflow server --host 127.0.0.1 --port 5000`. A interface fica em http://localhost:5000, e os dados são guardados no banco `mlflow.db`, na raiz do repositório, que é ignorado pelo git e removido por `make clean`. O servidor precisa estar no ar antes de o `agentic_workflow.py` ser executado: sem ele, o script falha já ao configurar o MLflow, antes de chamar o agente.

### Logging

O logging acompanha o andamento dos scripts. Tanto o [agentic_workflow.py](../scripts/agentic_workflow.py) quanto o [data_fetching_processing.py](../scripts/data_fetching_processing.py) usam `build_logger` (em [utils.py](../src/utils.py)), que configura o `logging` do Python com nível `INFO` e formato `data - nível - mensagem`, gravando em `logs/<script>.py.log`. O arquivo é sobrescrito a cada execução, e os `.log` são ignorados pelo git e removidos por `make clean`. O módulo [agent.py](../src/agent.py) também registra no mesmo arquivo. Para cada script, o log registra:
- `agentic_workflow.py`: se o experimento do MLflow foi encontrado ou criado, o início da execução, com o modelo e o dataset usados, as mensagens de cada nó (`[tipo] texto`, incluindo as chamadas e as respostas das ferramentas) à medida que o nó termina, e o caminho do boletim gerado. Se o agente encerrar sem chamar `atualizar_summary`, registra o erro e o boletim não é gerado. Em caso de falha na execução, registra a exceção com o traceback.
- `data_fetching_processing.py`: a leitura dos argumentos, a URL lida e o número de registros rotulados, a porcentagem de dados descartados, o tamanho da tabela limpa, um aviso quando a data de extração não é encontrada no nome do arquivo, o caminho dos dados e dos gráficos salvos e, em caso de falha na leitura ou na gravação, a exceção com o traceback.

O MLflow mostra em detalhe cada chamada do agente, enquanto o log dá uma visão linear da execução dos scripts, incluindo o pipeline de dados, que o MLflow não cobre.

## Possíveis Extensões

Este repositório é uma PoC da solução proposta. Para colocá-la em produção, poderíamos realizar uma série de mudanças:
- **Trigger:** Neste PoC não definimos o gatilho do processamento. Um caminho possível é gerar o relatório periodicamente, por exemplo toda semana, por meio de um job em uma plataforma como Airflow ou Databricks. Caso desejemos que analistas, médicos e outros profissionais interessados possam gerar relatórios sob demanda, poderíamos colocar um trigger via Slack (caso a companhia o utilize) no qual, por meio de um comando, como `/gerar-relatorio-srag`, os usuários poderiam gerar relatórios e recebê-los via Slack ou e-mail.
- **Fontes:** Hoje o agente busca notícias na web em quatro fontes (Ministério da Saúde, Fiocruz, Agência Brasil e CNN Brasil), com um limite de 5 usos por execução de cada ferramenta da web. Poderíamos realizar uma análise profunda de possíveis fontes em que diferentes agentes reuniriam a informação de fontes distintas, como notícias de imprensa, agências governamentais e periódicos médicos. Em seguida, reuniríamos todas essas afirmações e as sintetizaríamos em um Boletim Epidemiológico.
- **Plataforma de dados:** Poderíamos utilizar uma plataforma de dados com suporte robusto a processamento de dados e modelos de IA, como o Databricks. Lá já teríamos uma plataforma tanto para armazenamento e processamento de dados quanto para o uso de uma ampla gama de modelos de IA comerciais e open-source via Databricks AI Gateway, com governança unificada e extenso monitoramento via MLflow, nativamente integrado à plataforma.
- **Processamento e Armazenamento de dados:** Um excelente uso do Databricks seria para a criação de jobs de extração e processamento dos dados com ativação periódica (por exemplo, diária ou semanal). Poderíamos extrair dados de diferentes fontes, agregá-los e processá-los via Lakeflow Jobs ou ferramentas open-source como o dbt, para termos dados unificados, limpos e preparados para a análise. Além disso, todos os dados seriam armazenados em tabelas Delta, com consultas feitas via SQL, o que nos leva ao próximo ponto.
- **Extensão das ferramentas:** Com os dados já limpos, processados e armazenados em tabelas Delta, poderíamos dar ao agente instruções e acesso (somente de consulta, `SELECT`) às tabelas para ele decidir quais métricas extrair, permitindo maior flexibilidade, porém com maior complexidade de orquestração. Isso tornaria a solução altamente adaptável ao cenário epidemiológico. Além disso, poderíamos estender a análise não somente para o entendimento de dados históricos, mas também para uma análise preditiva, usando modelos de ML que nos permitiriam explorar cenários epidemiológicos, tudo isso de maneira nativa no Databricks, utilizando modelos registrados e treinados com os nossos dados.
- **Arquitetura:** Para uma solução em produção, poderíamos explorar arquiteturas multiagentes, com cada agente focado em uma tarefa, como cálculo estatístico, análise preditiva, busca de notícias e boletins governamentais e síntese de informações de diferentes fontes. Os agentes por fonte, descritos no item **Fontes**, são um exemplo disso. Além disso, passaríamos do uso apenas de prompts para prompts combinados com skills, introduzindo contexto valioso de negócio aos agentes.
- **Integrações Externas:** Para a publicação do Boletim Epidemiológico, poderíamos utilizar plataformas externas, como Google Docs/Drive, para disponibilizar o relatório em um formato familiar a todos os usuários, em que eles poderiam ler e interagir de maneira mais intuitiva com o boletim gerado.

Dessa forma, vemos que é possível expandir o PoC de diferentes maneiras. A escolha da melhor solução depende de restrições orçamentárias, de pessoal, de acesso às tecnologias e regulatórias, além do objetivo de negócio.

## Conclusão

A solução proposta é, hoje, simples, mas já demonstra robustez, como mostra o [boletim de exemplo](boletim_epidemiologico_srag_exemplo.md) gerado pelo agente: um documento padronizado, com as métricas, os gráficos, as interpretações e as notícias que o desafio pede. Ela também agrega valor ao liberar os analistas da tarefa repetitiva de produzir relatórios periodicamente, para que se dediquem a atividades mais produtivas, como o entendimento do cenário epidemiológico e a tomada de decisão.

Para a orquestração do agente escolhemos o LangGraph, uma ferramenta open-source, amplamente usada e robusta, o que favorece o desenvolvimento de uma solução estável e de alto valor. Com ele, o fluxo é um grafo explícito, com estado compartilhado e etapas bem definidas, e o preenchimento do boletim é determinístico, o que separa a análise feita pelo modelo da formatação do documento. Outras decisões de projeto contribuem para a confiabilidade da solução: as métricas vêm sempre do dataset, por meio de ferramentas, e a web serve apenas para contextualizá-las; cada execução fica registrada nos traces do MLflow e nos logs; e as etapas podem ser reproduzidas com os comandos do [README](../README.md) e do Makefile.

Por fim, a PoC tem limitações que devem ser consideradas. O boletim é gerado por um agente de IA e deve ser revisado por um profissional antes de ser usado em decisões, e os números herdam as limitações dos dados: o descarte dos registros sem desfecho, a subestimação dos casos mais recentes e o uso apenas do arquivo de 2026. Apresentamos também possíveis extensões, na seção [Possíveis Extensões](#possíveis-extensões), para a criação de uma solução robusta em produção.

## TL;DR

- **Contexto:** a Indicium HealthCare Inc. quer acompanhar surtos de doenças em tempo real. A PoC é o HealthCare Bot, um agente de IA que gera um Boletim Epidemiológico de SRAG com dados do Open DATASUS e notícias recentes.
- **Pipeline de dados:** o `data_fetching_processing.py` lê o dataset, mantém cinco colunas, rotula os valores, descarta os registros com nulos, salva o dataset limpo com metadados e gera os gráficos de casos dos últimos 30 dias e 12 meses.
- **Fluxo agêntico:** o agente é um grafo LangGraph com os nós `assistente` e `tools`, em ciclo, e `criar_boletim`. Um prompt de sistema em cinco partes guia o agente por um checklist de oito passos, com sete ferramentas locais para consultar os dados e gravar o resumo, e duas ferramentas de web para as notícias.
- **Boletim:** o nó `criar_boletim` preenche de forma determinística o template com o resumo gravado pelo agente, gerando um boletim em markdown com formato fixo.
- **Monitoramento:** o MLflow registra os traces de cada execução (chamadas, latência, tokens e custo), e o logging registra o andamento de cada script em `logs/`.
- **Possíveis extensões:** gatilho periódico ou via Slack, mais fontes de notícias, plataforma de dados como o Databricks, agentes que consultam as tabelas, arquitetura multiagente e integrações como o Google Docs.
- **Conclusão:** a solução é simples, mas robusta, libera os analistas de tarefas repetitivas e usa o LangGraph para a orquestração. Por ser uma PoC, o boletim deve ser revisado por um profissional.
