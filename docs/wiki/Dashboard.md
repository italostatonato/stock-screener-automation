# Dashboard e carteira híbrida

Revisado em 12/10/2026 contra `docs/index.html` e `src/exporter.py` da `main` (`99f34f9`).

O [dashboard público](https://italostatonato.github.io/stock-screener-automation/)
é servido pelo GitHub Pages. Ele abre na aba **Introdução** e carrega o snapshot
mais recente de `docs/data/index.json`. Os nomes dos arquivos usam a data da execução em
`America/Sao_Paulo`; o snapshot não é uma cotação em tempo real.

## Versão no Sites

O [site Radar Semanal](https://radar-semanal-italo.italo-st.chatgpt.site/) está público e replica as seis abas principais
do dashboard. O servidor espelha o HTML, os dados e os recursos do GitHub Pages
a cada acesso. Enquanto visível, a aba verifica a versão a cada 60 segundos e
recarrega quando há mudança, aguardando a edição de campos. Em caso de falha,
tenta a cópia incluída na publicação e mostra um aviso com a data dos dados.
O rodapé tem contador de **visitantes únicos por navegador**, com início em
29/09/2026; retornos com o mesmo cookie não aumentam o total. Esse contador
abrange somente o site no Sites, sem somar os acessos ao GitHub Pages.
O HTML original acompanha o Pages pelo espelhamento; Worker, contador,
adaptações próprias e cópia de contingência exigem publicação no Sites.
Essa verificação não altera a frequência semanal da coleta.
Consulte [acesso, visitantes e manutenção](https://github.com/italostatonato/stock-screener-automation/wiki/Site), incluindo os limites da
detecção de mudanças. Informações verificadas em **05/10/2026**.

## Frequência de atualização

A coleta é agendada para **toda segunda-feira, 10h de Brasília**. O novo
snapshot fica disponível após processamento e publicação. Uma execução manual
pode gerar outra data ou substituir o snapshot daquele dia. As tendências nos
cards comparam a coleta selecionada com a anterior disponível, sem pressupor
um intervalo de um dia.

A Visão geral compara com o snapshot mais recente cuja data seja igual ou
anterior a sete dias antes do atual. Se houver lacunas, a comparação cobre mais
de uma semana. Sem essa base, o painel informa que não há comparação disponível.

Liquidez diária, CDI diário e variações de câmbio/cripto em 24h são métricas
dos provedores. Quando faltam cotações de câmbio ou cripto, o navegador tenta
uma consulta pontual às APIs públicas; isso não recalcula o ranking semanal,
os scores, as carteiras ou os modelos ML.

## Navegação

- **Introdução** (padrão ao abrir): guia para iniciantes sobre ações, FIIs,
  cotas, ETFs, renda fixa, proventos, CDI, juros, inflação e índices da bolsa.
  Inclui exemplo fictício de preço versus rendimento, glossário expansível,
  fontes educacionais e atalhos para as outras abas. Reúne também score, pesos,
  elegibilidade, histograma, fontes de dados e informações do projeto. A explicação
  usa uma lista ordenada de 10 DYs para mostrar de onde saem os 80 pontos,
  compara a mesma taxa em outro grupo e explica os limites da escala. Depois,
  junta sete notas em um exemplo fictício com média 70,0.
  Os sete tópicos principais começam recolhidos, com seta e título acionáveis
  por mouse ou teclado. Atalhos e links diretos abrem o tópico de destino;
  abrir o score redimensiona o histograma. A seção de diversificação explica
  a escolha de até 20 ativos por classe com Tang (2004) e Rabelo et al. (2007),
  distingue risco diversificável de risco de mercado e identifica a aplicação
  aos FIIs como adaptação do projeto, sem prometer a mesma redução de risco.
  A curva teórica `100/n` permite comparar 1–100 ativos, destaca 20 e exporta CSV.
  Ela normaliza a parcela diversificável da variância e funciona sem snapshots.
  A explicação é estática e
  permanece legível mesmo sem carregar dados. Navegação reorganizada em 07/10/2026.
- **Visão geral:** entradas, saídas e mudanças de posição na comparação
  semanal descrita acima em resumos compactos, seleções de até 20 ativos por
  classe em cartões alinhados de uma linha com posição, ticker e score (sem
  preço), e desempenho em gráfico de linhas com escolha entre Ações, FIIs e
  Ações + FIIs (50/50), comparadas a CDI, IFIX e IBOV.
  A grade adapta as colunas à largura disponível e empilha as classes no celular.
- **Carteira Híbrida:** alocação entre quatro blocos, perfis, simulação de aporte,
  curva comparativa, contribuições e pesos por ativo.
- **Modelos ML:** rankings sombra, performance, confiabilidade e evolução
  de janelas realizadas.
- **Top 20:** seletor entre Ações, FIIs e Recorrentes, com rankings, preços, scores, indicadores e frequência histórica.
- **Indicadores:** macroeconomia, câmbio, cripto e benchmarks. O atalho `score`
  abre a Introdução, expande o tópico e rola até a explicação da pontuação.

O cabeçalho contém um link externo para a apresentação de leitura do projeto;
a disponibilidade desse recurso depende das permissões no Google.

## Períodos dos gráficos

Os gráficos temporais iniciam em **3M**, com períodos **1M, 3M, 6M, 12M, 18M,
24M e Tudo**. Os meses são contados até a última data disponível no gráfico.
A exibição seleciona a última observação de cada semana de segunda a domingo,
sem criar pontos em semanas ausentes. Selecionar 24M não reconstrói dois anos
de dados: a ampliação do histórico continua dependendo de trabalho separado.

As comparações de retorno das carteiras alinham as séries às mesmas datas e
recalculam o retorno a partir do primeiro valor disponível no período. O cálculo
híbrido preserva os intervalos intermediários de rebalanceamento antes de
selecionar os pontos semanais para exibição.

## Exportação CSV

O botão **Baixar CSV** está disponível nas tabelas, nos gráficos e na barra de
distribuição da carteira híbrida:

- **Tabelas:** exportam as linhas renderizadas, com os valores principais
  formatados. Nomes de ativos/componentes e resultados monetários usam o texto
  principal da célula; cabeçalhos de várias linhas são combinados.
- **Gráficos:** exportam os rótulos e valores do período e universo selecionados,
  sem arredondamento adicional; valores ausentes ficam vazios. Incluem todas as
  séries presentes no gráfico, mesmo quando ocultadas pela legenda, e a unidade
  do eixo quando ela está indicada.
- **Distribuição da carteira:** exporta as colunas `Perfil`, `Componente` e
  `Alocação (%)`, com os pesos atuais dos quatro blocos, inclusive após edição.

O download é gerado no navegador em UTF-8 com BOM, usa ponto e vírgula como
separador e coloca os campos entre aspas. O nome começa por `radar-` e inclui
o título normalizado e a data selecionada. Esses CSVs não acionam coleta,
treinamento nem entrega de Excel.

## Alocação híbrida

Os quatro blocos, na ordem da interface, são Top 20 Ações BR, Top 20 FIIs, CDI
e IVVB11. Os perfis usam os seguintes percentuais nessa ordem:

- Agressivo: **45/20/5/30**.
- Meio-Agressivo: **40/25/10/25**.
- Balanceado, padrão: **30/30/20/20**.
- Conservador: **15/20/55/10**.
- Muito conservador: **5/10/80/5**.

Os pesos são editáveis de 1% em 1%. Ao aumentar um bloco, cada ponto sai do
maior dos demais blocos; ao reduzir, a diferença vai para o maior dos demais.
Empates seguem a ordem dos blocos. O total permanece em 100%.
Distribuição, curvas, contribuições e pesos por ativo acompanham a seleção.

## Simulação do aporte

O valor inicial é **R$ 10.000,00** e o mínimo aceito é **R$ 1.000,00**.
A máscara IMask 7.6.1, distribuída localmente com licença MIT, formata o valor
brasileiro e preserva o cursor. Centavos são completados ao sair do campo;
apagar e redigitar é permitido antes da validação.

A simulação divide o aporte pelos pesos escolhidos e reparte igualmente os
blocos Top 20 entre seus ativos. Usa preços do snapshot e o último fechamento
disponível de IVVB11 até aquela data. Compras são arredondadas para unidades
inteiras; sobras e valores sem cotação/composição ficam no saldo, sem
redistribuição.

As listas aparecem abaixo de cada bloco, com quantidades, valores, pesos
efetivos e detalhes por foco do teclado ou passagem do mouse. O CDI é uma
parcela teórica de renda fixa; o site não escolhe um produto nem envia ordens.

## Como interpretar as curvas

A carteira histórica teórica é rebalanceada a cada nova composição semanal.
Dentro dos blocos Top 20, os ativos têm pesos iguais. As curvas usam pesos
fracionários; a lista de compras usa unidades inteiras. O desempenho mostrado
não reproduz exatamente uma carteira executada com as quantidades simuladas.

As séries Top 20 usam preços dos snapshots, **sem reinvestir proventos**.
A carteira híbrida não inclui custos ou impostos. Ganho/perda estimado em reais
e saldo teórico derivam do aporte e das contribuições históricas; não são
previsões de resultado futuro.

Na Visão geral, **Ações + FIIs (50/50)** combina os retornos das duas classes
com metade do peso em cada uma a cada observação semanal. Usa apenas o intervalo
comum às duas séries; sem histórico comum, o painel aguarda dados. A curva é
teórica e não inclui custos, impostos nem reinvestimento de proventos.

O benchmark IFIX usa **XFIX11 como proxy**. Os scripts auditáveis de backtest
têm outro motor, com entrada no pregão seguinte, preços ajustados e custos;
suas premissas estão em [Backtests](https://github.com/italostatonato/stock-screener-automation/wiki/Backtests).

## ML e qualidade de dados

Uma projeção só é exibida com três janelas do mesmo modelo/classe/horizonte
e magnitude de até 50%. A confiança usa mínimo de uma janela e meta de cinco.
O treino principal usa 7d. Previsões antigas de 30d não são convertidas para
7d. Sem previsão na data/horizonte do snapshot, aparece o baseline atual. Veja [Pipeline ML](https://github.com/italostatonato/stock-screener-automation/wiki/Modelos-ML) e
[Confiabilidade ML](https://github.com/italostatonato/stock-screener-automation/wiki/Confiabilidade-ML).

Quando uma fonte obrigatória falha, o pipeline interrompe a geração do novo
snapshot. O deploy ainda pode publicar a versão disponível da aplicação se
os testes passaram. Um deploy bem-sucedido não comprova uma nova coleta.
