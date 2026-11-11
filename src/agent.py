"""Definições do agente que gera o relatório de SRAG.

Reúne a construção do prompt de sistema do agente, com o contexto, o objetivo, a
descrição do dataset processado, as regras e os passos a seguir, e o esquema do resumo
(`ResumoAgente`) com os valores que preenchem o template do boletim.
"""

from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field

# prompts


def system_prompt_agente():
    """Monta o prompt de sistema do agente que cria o relatório de SRAG.

    O prompt é dividido em blocos XML: `<contexto>` (o que é SRAG), `<objetivo>` (o que o
    agente deve produzir), `<schema_dataset>` (colunas, tipos e valores do dataset),
    `<regras>` (premissas, limitações dos dados e uso da web) e `<passos>` (checklist
    que o agente deve seguir, com as métricas do dataset e a busca de notícias, montado
    por `_prompt_passos_agente`). Os caminhos dos arquivos não aparecem no prompt: são
    injetados do estado do agente nas ferramentas.

    Returns:
        Mensagem de sistema com o prompt do agente.
    """
    prompt = f"""Você é um analista de dados de saúde pública. Responda sempre em PT-BR.

<contexto>
SRAG é a Síndrome Respiratória Aguda Grave: um quadro de síndrome gripal (febre, tosse, \
dor de garganta, entre outros sintomas) acompanhado de dispneia ou desconforto \
respiratório, saturação de O2 abaixo de 95% ou cianose, que leva à hospitalização ou ao \
óbito. Os casos são notificados ao Ministério da Saúde e publicados no Open DATASUS \
(SIVEP-Gripe). A vigilância da SRAG permite acompanhar a circulação de vírus respiratórios \
(como influenza e COVID-19) e a pressão sobre o sistema de saúde.
</contexto>

<objetivo>
Criar um relatório de SRAG a partir do dataset processado, para apoiar a leitura da \
situação epidemiológica. O relatório deve apresentar e interpretar as métricas:
- taxa de aumento de casos;
- taxa de mortalidade;
- taxa de ocupação de UTI (proporção dos casos internados em UTI);
- taxa de vacinação (proporção de vacinados contra COVID-19 entre os casos);
- número diário de casos dos últimos 30 dias;
- número mensal de casos dos últimos 12 meses.
Além das métricas, contextualize a situação com notícias recentes sobre SRAG obtidas na web.
</objetivo>

<schema_dataset>
O dataset é um arquivo parquet com um registro por caso notificado e as colunas:
- NU_NOTIFIC (str): número de registro sequencial da notificação, identifica o caso.
- DT_SIN_PRI (datetime64[ns]): data dos primeiros sintomas do caso. É a data usada para \
contar casos.
- EVOLUCAO (str): evolução do caso. Valores: "cura" ou "obito" (inclui óbito por outras \
causas).
- VACINA_COV (str): se o paciente recebeu vacina contra COVID-19. Valores: "vacinado" ou \
"nao_vacinado".
- UTI (str): se o paciente foi internado em UTI. Valores: "uti" ou "nao_uti".

Registros com EVOLUCAO, VACINA_COV ou UTI ignorados ou nulos foram removidos do dataset.
</schema_dataset>

<regras>
- A taxa de vacinação é a proporção de vacinados entre os casos de SRAG, não a cobertura \
vacinal da população.
- Os caminhos dos arquivos são fornecidos automaticamente às ferramentas. Não os peça nem \
os informe ao chamar uma ferramenta.
- Use a busca e a coleta na web apenas para contextualizar os números, nunca para \
substituí-los: as métricas vêm sempre do dataset. A web é restrita a domínios permitidos \
(portais de notícias e do Ministério da Saúde); não tente acessar outros sites.
- Cite a fonte (título e URL) de toda informação vinda da web. Se a busca não retornar \
nada relevante, diga isso. As ferramentas da web têm um limite de usos por execução, \
então faça buscas objetivas.
- Use apenas os dados e as ferramentas disponíveis. Se uma informação não estiver \
disponível, diga isso em vez de estimá-la.
</regras>

{_prompt_passos_agente()}"""

    return SystemMessage(content=prompt)


def _prompt_passos_agente():
    """Monta o bloco do prompt com os passos que o agente deve seguir no relatório.

    Os passos são um checklist dentro do bloco XML `<passos>`, incluído no prompt de
    sistema por `system_prompt_agente`. O checklist obtém as métricas do dataset e as notícias
    da web com as ferramentas, e novos passos serão acrescentados conforme o relatório
    for construído.

    Returns:
        Texto do bloco `<passos>` com o checklist.
    """
    return """<passos>
Siga o checklist abaixo, na ordem, para criar o relatório:
- [ ] 1. Ler as informações do dataset com a ferramenta `dataframe_info`.
- [ ] 2. Obter o número mensal de casos dos últimos 12 meses com a ferramenta \
`num_casos_mensal_ultimos_12_m` e o crescimento mês a mês com a ferramenta \
`crescimento_mensal_ultimos_12_m`.
- [ ] 3. Obter a taxa de vacinação com a ferramenta `taxa_de_vacinacao`.
- [ ] 4. Obter as taxas de mortalidade e de internação em UTI com a ferramenta \
`taxa_periodo`, chamando-a com `col_target` igual a "EVOLUCAO" (mortalidade) e igual a \
"UTI" (internação em UTI), para a janela de 30 dias (`dias_filtro` igual a 30) e para a \
de 12 meses (`dias_filtro` igual a 365).
- [ ] 5. Buscar notícias recentes sobre SRAG com a ferramenta `web_search`, para \
contextualizar as métricas (por exemplo, circulação de vírus respiratórios, campanhas de \
vacinação e situação da rede de saúde).
- [ ] 6. Coletar o conteúdo das notícias mais relevantes com a ferramenta `web_fetch`, \
usando apenas as URLs retornadas pela busca, e extrair as informações pertinentes.

Ao concluir todos os passos do checklist, encerre o turno.
</passos>"""


# schemas


class ResumoAgente(BaseModel):
    """Valores que preenchem os campos `{...}` do template do boletim.

    Há um campo para cada chave de `src/template_report.md`, na ordem em que aparecem.
    Todos são texto, já no formato em que serão inseridos no boletim: datas em
    DD/MM/AAAA, números no padrão brasileiro (separador de milhar com ponto e vírgula
    decimal) e tabelas e listas em markdown.
    """

    # cabeçalho e metadados
    data_inicio: str = Field(
        description=(
            "Data inicial do período analisado, no formato DD/MM/AAAA: a mais recente entre "
            "o início da janela de 12 meses e a data mais antiga de início dos sintomas do "
            "dataset."
        )
    )
    data_fim: str = Field(
        description=(
            "Data final do período analisado, no formato DD/MM/AAAA: a data mais recente de "
            "início dos sintomas do dataset."
        )
    )
    data_relatorio: str = Field(description="Data de emissão do boletim, no formato DD/MM/AAAA.")
    data_extracao: str = Field(
        description=(
            "Data de extração dos dados do Open DATASUS, no formato DD/MM/AAAA. Consta no "
            "nome do arquivo baixado (por exemplo, INFLUD26-19-10-2026 indica 19/10/2026)."
        )
    )
    pct_dados_descartados: str = Field(
        description=(
            "Porcentagem de registros removidos por terem evolução, vacinação ou internação "
            "em UTI nulos ou ignorados, com duas casas decimais e o símbolo %. Ex.: 13,55%."
        )
    )

    # resumo
    resumo: str = Field(
        description=(
            "Resumo do boletim em um parágrafo curto: situação do número de casos, principais "
            "taxas e o contexto trazido pelas notícias."
        )
    )

    # resultados: número de casos
    plot_num_casos_30_d: str = Field(
        description=(
            "Caminho da imagem do gráfico do número diário de casos dos últimos 30 dias. "
            "Vem do estado do agente (`plot_num_casos_30_d`), não deve ser inventado."
        )
    )
    plot_num_casos_12_m: str = Field(
        description=(
            "Caminho da imagem do gráfico do número diário de casos dos últimos 12 meses. "
            "Vem do estado do agente (`plot_num_casos_12_m`), não deve ser inventado."
        )
    )
    interpretacao_evolucao_casos: str = Field(
        description=(
            "Interpretação da evolução diária dos casos nos gráficos de 30 dias e de 12 meses: "
            "tendência, picos e vales, lembrando que os últimos dias do dataset estão "
            "incompletos por atraso de notificação."
        )
    )
    total_casos_30_d: str = Field(
        description="Total de casos nos últimos 30 dias, inteiro com separador de milhar. Ex.: 5.054."
    )
    total_casos_12_m: str = Field(
        description="Total de casos nos últimos 12 meses, inteiro com separador de milhar."
    )
    media_casos_30_d: str = Field(
        description="Média diária de casos nos últimos 30 dias, com duas casas decimais. Ex.: 168,47."
    )
    media_casos_12_m: str = Field(
        description="Média diária de casos nos últimos 12 meses, com duas casas decimais."
    )
    desvio_casos_30_d: str = Field(
        description="Desvio padrão do número diário de casos nos últimos 30 dias, com duas casas decimais."
    )
    desvio_casos_12_m: str = Field(
        description="Desvio padrão do número diário de casos nos últimos 12 meses, com duas casas decimais."
    )
    max_casos_30_d: str = Field(
        description=(
            "Dia com mais casos nos últimos 30 dias, no formato `quantidade (DD/MM/AAAA)`. "
            "Ex.: 388 (20/09/2026)."
        )
    )
    max_casos_12_m: str = Field(
        description="Dia com mais casos nos últimos 12 meses, no formato `quantidade (DD/MM/AAAA)`."
    )
    min_casos_30_d: str = Field(
        description="Dia com menos casos nos últimos 30 dias, no formato `quantidade (DD/MM/AAAA)`."
    )
    min_casos_12_m: str = Field(
        description="Dia com menos casos nos últimos 12 meses, no formato `quantidade (DD/MM/AAAA)`."
    )
    tabela_crescimento_mensal: str = Field(
        description=(
            "Tabela em markdown com uma linha por mês e as colunas `Mês`, `Casos` e "
            "`Crescimento (%)`, com a variação em relação ao mês anterior. O primeiro mês não "
            "tem mês anterior e fica sem crescimento."
        )
    )
    interpretacao_crescimento_mensal: str = Field(
        description=(
            "Interpretação do crescimento mês a mês: períodos de alta e de queda. O último mês "
            "é parcial, então sua queda não deve ser apresentada como redução real de casos."
        )
    )

    # resultados: demais métricas
    taxa_mortalidade_30_d: str = Field(
        description=(
            "Taxa de mortalidade nos últimos 30 dias (óbitos entre os casos com desfecho), "
            "com duas casas decimais e o símbolo %. Ex.: 6,87%."
        )
    )
    taxa_mortalidade_12_m: str = Field(
        description="Taxa de mortalidade nos últimos 12 meses, com duas casas decimais e o símbolo %."
    )
    taxa_uti_30_d: str = Field(
        description=(
            "Taxa de ocupação de UTI nos últimos 30 dias (casos internados em UTI entre o total "
            "de casos), com duas casas decimais e o símbolo %. Ex.: 26,14%."
        )
    )
    taxa_uti_12_m: str = Field(
        description="Taxa de ocupação de UTI nos últimos 12 meses, com duas casas decimais e o símbolo %."
    )
    casos_vacinados: str = Field(
        description="Número de casos vacinados contra COVID-19, inteiro com separador de milhar."
    )
    casos_nao_vacinados: str = Field(
        description="Número de casos não vacinados contra COVID-19, inteiro com separador de milhar."
    )
    taxa_vacinados: str = Field(
        description=(
            "Proporção de vacinados entre os casos de SRAG, com duas casas decimais e o "
            "símbolo %. Ex.: 38,85%. Não é a cobertura vacinal da população."
        )
    )
    taxa_nao_vacinados: str = Field(
        description="Proporção de não vacinados entre os casos de SRAG, com duas casas decimais e o símbolo %."
    )
    interpretacao_metricas: str = Field(
        description=(
            "Interpretação conjunta das taxas de mortalidade, de ocupação de UTI e de "
            "vacinação, comparando as janelas de 30 dias e de 12 meses."
        )
    )

    # notícias
    lista_noticias: str = Field(
        description=(
            "Lista em markdown das notícias recentes sobre SRAG, cada item com título, fonte, "
            "URL e uma frase de resumo. Usar só notícias dos domínios permitidos; se nada "
            "relevante for encontrado, dizer isso."
        )
    )
    impacto_noticias: str = Field(
        description=(
            "Análise do impacto das notícias e de sua relação com os dados apresentados. As "
            "métricas vêm sempre do dataset, e as notícias só as contextualizam."
        )
    )

    # conclusão e referências
    conclusao: str = Field(
        description="Conclusão do boletim, retomando os principais achados sobre casos, taxas e contexto."
    )
    recomendacoes: str = Field(
        description=(
            "Lista numerada em markdown de recomendações para a Indicium HealthCare Inc., cada "
            "uma ligada a um achado dos dados."
        )
    )
    fontes_informacoes: str = Field(
        description=(
            "Lista em markdown das fontes (título e URL) das informações que não vêm do "
            "dataset, como as notícias."
        )
    )
