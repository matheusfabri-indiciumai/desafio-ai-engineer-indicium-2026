"""Definições do agente que gera o relatório de SRAG.

Reúne a construção do prompt de sistema do agente, com o contexto, o objetivo, os
arquivos de entrada e a descrição do dataset processado.
"""

from langchain_core.messages import SystemMessage

# prompts


def system_prompt_agente(filepath, plot_num_casos_30_d, plot_num_casos_12_m):
    """Monta o prompt de sistema do agente que cria o relatório de SRAG.

    O prompt é dividido em blocos XML: `<contexto>` (o que é SRAG), `<objetivo>` (o que o
    agente deve produzir), `<inputs>` (caminhos dos arquivos), `<schema_dataset>`
    (colunas, tipos e valores do dataset), `<regras>` (premissas e limitações dos dados)
    e `<passos>` (checklist que o agente deve seguir, montado por `_prompt_passos_agente`).

    Args:
        filepath: Caminho do arquivo parquet com o dataset processado.
        plot_num_casos_30_d: Caminho da imagem com o gráfico do número diário de casos
            dos últimos 30 dias.
        plot_num_casos_12_m: Caminho da imagem com o gráfico do número de casos dos
            últimos 12 meses.

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
</objetivo>

<inputs>
<filepath_dataset>{filepath}</filepath_dataset>
<grafico_ultimos_30_dias>{plot_num_casos_30_d}</grafico_ultimos_30_dias>
<grafico_ultimos_12_meses>{plot_num_casos_12_m}</grafico_ultimos_12_meses>
</inputs>

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
- Use apenas os dados e as ferramentas disponíveis. Se uma informação não estiver \
disponível, diga isso em vez de estimá-la.
</regras>

{_prompt_passos_agente()}"""

    return SystemMessage(content=prompt)


def _prompt_passos_agente():
    """Monta o bloco do prompt com os passos que o agente deve seguir no relatório.

    Os passos são um checklist dentro do bloco XML `<passos>`, incluído no prompt de
    sistema por `system_prompt_agente`. Por enquanto há um único passo, e novos passos
    serão acrescentados ao checklist conforme o relatório for construído.

    Returns:
        Texto do bloco `<passos>` com o checklist.
    """
    return """<passos>
Siga o checklist abaixo, na ordem, para criar o relatório:
- [ ] 1. Ler as informações do dataset com a ferramenta `dataframe_info`, usando o caminho \
em <filepath_dataset>.
- [ ] 2. Obter o número mensal de casos dos últimos 12 meses com a ferramenta \
`num_casos_mensal_ultimos_12_m` e o crescimento mês a mês com a ferramenta \
`crescimento_mensal_ultimos_12_m`, usando o caminho em <filepath_dataset>.

Ao concluir todos os passos do checklist, encerre o turno.
</passos>"""
