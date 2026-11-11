# Boletim Epidemiológico de SRAG

**Indicium HealthCare Inc.** · Período analisado: {data_inicio} a {data_fim}

|  |  |
| --- | --- |
| **Elaborado por** | HealthCare Bot (agente de IA) |
| **Destinatário** | Indicium HealthCare Inc. |
| **Data de emissão** | {data_relatorio} |
| **Período analisado** | {data_inicio} a {data_fim} |
| **Fonte dos dados** | Open DATASUS (Sivep-Gripe), extração em {data_extracao} |

> Documento gerado automaticamente por um agente de IA. Recomenda-se a revisão por um profissional antes do uso em decisões.

## Resumo

{resumo}

## Sumário

- [Introdução](#introdução)
- [Métodos](#métodos)
  - [Banco de dados](#banco-de-dados)
  - [Confirmação de casos](#confirmação-de-casos)
  - [Coleta e tratamento dos dados](#coleta-e-tratamento-dos-dados)
  - [Análises dos dados](#análises-dos-dados)
- [Resultados e Discussão](#resultados-e-discussão)
  - [Número de casos](#número-de-casos)
    - [Evolução dos casos](#evolução-dos-casos)
    - [Estatísticas](#estatísticas)
    - [Crescimento mensal](#crescimento-mensal)
  - [Demais métricas](#demais-métricas)
- [Últimas notícias sobre SRAG](#últimas-notícias-sobre-srag)
- [Conclusão e recomendações](#conclusão-e-recomendações)
- [Referências bibliográficas](#referências-bibliográficas)

## Introdução

A **Síndrome Respiratória Aguda Grave (SRAG)** é um quadro de síndrome gripal (febre, tosse, dor de garganta, entre outros sintomas) acompanhado de dispneia ou desconforto respiratório, saturação de O2 abaixo de 95% ou cianose, que leva à hospitalização ou ao óbito. Os casos são notificados ao Ministério da Saúde e publicados no Open DATASUS (SIVEP-Gripe). A vigilância da SRAG permite acompanhar a circulação de vírus respiratórios, como influenza e COVID-19, e a pressão sobre o sistema de saúde.

O objetivo deste boletim é apoiar a leitura da situação epidemiológica da SRAG entre {data_inicio} e {data_fim}, apresentando a evolução do número de casos, as taxas de vacinação, de mortalidade e de ocupação de UTI, e o contexto trazido pelas notícias mais recentes, com recomendações para a Indicium HealthCare Inc.

## Métodos

Trata-se de estudo epidemiológico descritivo, com base nos registros de casos de SRAG notificados no Brasil entre {data_inicio} e {data_fim}.

### Banco de dados

Foi utilizado o Sivep-Gripe (Sistema de Informação da Vigilância Epidemiológica da Gripe), cujos registros de SRAG são publicados no Open DATASUS (conjunto de dados SRAG 2019 a 2026). Como fonte complementar, notícias recentes sobre SRAG foram obtidas por busca na web em domínios institucionais e de imprensa previamente selecionados: Ministério da Saúde, Fiocruz, Agência Brasil e CNN Brasil.

### Confirmação de casos

Para a definição de casos de SRAG, foram considerados os critérios clínicos do Sivep-Gripe: indivíduos hospitalizados por síndrome gripal (SG), ou que evoluíram para óbito independentemente de hospitalização, e que apresentaram pelo menos um dos seguintes sinais de gravidade: dispneia, desconforto respiratório ou saturação de oxigênio inferior a 95%.

### Coleta e tratamento dos dados

Os dados foram extraídos do Open DATASUS em {data_extracao}. Entre as colunas do arquivo, foram selecionadas cinco variáveis:

- "número de notificação" (`NU_NOTIFIC`);
- "data de início dos sintomas" (`DT_SIN_PRI`);
- "evolução do caso" (`EVOLUCAO`);
- "vacina contra covid-19" (`VACINA_COV`);
- "internação em UTI" (`UTI`).

No tratamento, os valores foram rotulados (evolução em cura ou óbito, agrupando o óbito por outras causas com o óbito; vacinação em vacinado ou não vacinado; UTI em sim ou não), e os valores ignorados foram tratados como nulos. Os registros com evolução, vacinação ou internação em UTI nulos foram removidos, o que correspondeu a {pct_dados_descartados} dos registros. Como os casos ainda sem desfecho na data de extração são descartados, o número de casos mais recentes tende a ser subestimado.

### Análises dos dados

Os casos foram contabilizados por data de início dos sintomas. A série por data de notificação apresentou periodicidade semanal e, com média móvel semanal, ficou altamente correlacionada com a série por data de início dos sintomas, de modo que apenas a segunda foi utilizada. As análises consideraram os últimos 30 dias e os últimos 12 meses (365 dias), com as duas janelas terminando na data mais recente de início dos sintomas do dataset.

Para o número de casos, foram calculadas a frequência absoluta diária e, em cada janela, o total, a média, o desvio padrão, o máximo e o mínimo. O crescimento foi medido pela variação percentual do número de casos de cada mês em relação ao mês anterior. As taxas, apresentadas em porcentagem com duas casas decimais, foram calculadas da seguinte forma:

- **Mortalidade:** proporção de óbitos entre os casos com desfecho, nas duas janelas;
- **Ocupação de UTI:** proporção de casos internados em UTI entre o total de casos, nas duas janelas;
- **Vacinação:** proporção de casos vacinados contra covid-19 entre o total de casos de SRAG em todo o dataset, e não a cobertura vacinal da população.

O processamento, o tratamento e as análises foram realizados em Python (pandas, matplotlib e seaborn). A interpretação dos resultados e a redação deste boletim foram feitas por um agente baseado em modelo de linguagem (Claude, da Anthropic), orquestrado com LangGraph, que também consultou as notícias na web.

## Resultados e Discussão

### Número de casos

#### Evolução dos casos

**Últimos 30 dias**

![Número diário de casos nos últimos 30 dias]({plot_num_casos_30_d})

**Últimos 12 meses**

![Número diário de casos nos últimos 12 meses]({plot_num_casos_12_m})

{interpretacao_evolucao_casos}

#### Estatísticas

| Estatística | Últimos 30 dias | Últimos 12 meses |
| --- | --- | --- |
| Total de casos | {total_casos_30_d} | {total_casos_12_m} |
| Média diária de casos | {media_casos_30_d} | {media_casos_12_m} |
| Desvio padrão diário | {desvio_casos_30_d} | {desvio_casos_12_m} |
| Dia com mais casos | {max_casos_30_d} | {max_casos_12_m} |
| Dia com menos casos | {min_casos_30_d} | {min_casos_12_m} |

#### Crescimento mensal

Variação percentual do número de casos de cada mês em relação ao mês anterior.

{tabela_crescimento_mensal}

> **Nota sobre os dados:** a data mais recente do dataset ({data_fim}) é tratada como o fim das janelas de análise. Os últimos dias e o último mês estão incompletos por atraso de notificação, então a queda observada nesse período não deve ser interpretada como redução real de casos.

{interpretacao_crescimento_mensal}

### Demais métricas

#### Mortalidade e ocupação de UTI

| Métrica | Últimos 30 dias | Últimos 12 meses |
| --- | --- | --- |
| Taxa de mortalidade (óbitos entre os casos com desfecho) | {taxa_mortalidade_30_d} | {taxa_mortalidade_12_m} |
| Taxa de ocupação de UTI (casos internados em UTI) | {taxa_uti_30_d} | {taxa_uti_12_m} |

#### Vacinação

| Situação vacinal contra COVID-19 | Casos | Proporção dos casos |
| --- | --- | --- |
| Vacinados | {casos_vacinados} | {taxa_vacinados} |
| Não vacinados | {casos_nao_vacinados} | {taxa_nao_vacinados} |

A taxa de vacinação é a proporção de vacinados entre os casos de SRAG, e não a cobertura vacinal da população.

#### Interpretação

{interpretacao_metricas}

## Últimas notícias sobre SRAG

{lista_noticias}

### Impacto e relação com os dados

{impacto_noticias}

## Conclusão e recomendações

{conclusao}

**Recomendações para a Indicium HealthCare Inc.**

{recomendacoes}

## Referências bibliográficas

**Fonte dos dados**

- MINISTÉRIO DA SAÚDE. **Open DATASUS: SRAG 2019 a 2026** (SIVEP-Gripe). Disponível em: <https://dadosabertos.saude.gov.br/dataset/srag-2019-a-2026>. Acesso em: {data_relatorio}.
- MINISTÉRIO DA SAÚDE. **Open DATASUS: SRAG, dicionário de dados**. Disponível em: <https://dadosabertos.saude.gov.br/dataset/srag-2019-a-2026/resource/3135ac9c-2019-4989-a893-2ed50ebd8e68>. Acesso em: {data_relatorio}.

**Referência metodológica**

- BRASIL. Ministério da Saúde. Secretaria de Vigilância em Saúde e Ambiente. **Boletim Epidemiológico**, v. 57, n. 4, 7 ago. 2026: cenário epidemiológico da covid-19, da influenza e de outros vírus respiratórios no Brasil em 2025. Disponível em: <https://www.gov.br/saude/pt-br/centrais-de-conteudo/publicacoes/boletins/epidemiologicos/edicoes/2026/boletim-epidemiologico-volume-57-no-4.pdf/@@download/file>. Acesso em: {data_relatorio}.

**Fonte das demais informações**

{fontes_informacoes}
