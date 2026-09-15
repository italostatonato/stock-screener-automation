# Dashboard e carteira híbrida

Revisado em 15/09/2026 contra `docs/index.html` e `src/exporter.py`.

O [dashboard público](https://italostatonato.github.io/stock-screener-automation/)
é servido pelo GitHub Pages. Ele inicia pelo snapshot mais recente de
`docs/data/index.json`. Os nomes dos arquivos usam a data da execução em
`America/Sao_Paulo`; o snapshot não é uma cotação em tempo real.

## Frequência de atualização

A coleta é agendada para **toda segunda-feira, 08h de Brasília**. O novo
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

- **Visão geral:** entradas, saídas e mudanças de posição na comparação
  semanal descrita acima, líderes Top 5 por classe e desempenho contra referências.
- **Carteira Híbrida:** alocação entre quatro blocos, perfis, simulação de aporte,
  curva comparativa, contribuições e pesos por ativo.
- **Modelos ML:** rankings sombra, performance, confiabilidade e evolução
  de janelas realizadas.
- **Recorrentes:** frequência histórica de presença no Top 20.
- **Ações** e **FIIs:** rankings, preços, scores e indicadores.
- **Indicadores:** macroeconomia, câmbio, cripto e benchmarks.
- **Score e Info:** metodologia, fontes e limitações.

Os gráficos temporais iniciam em **90D** e oferecem outros períodos.
O cabeçalho contém um link externo para a apresentação de leitura do projeto;
a disponibilidade desse recurso depende das permissões no Google.

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

O benchmark IFIX usa **XFIX11 como proxy**. Os scripts auditáveis de backtest
têm outro motor, com entrada no pregão seguinte, preços ajustados e custos;
suas premissas estão em [Backtests](BACKTEST_RETROATIVO.md).

## ML e qualidade de dados

Uma projeção só é exibida com três janelas do mesmo modelo/classe/horizonte
e magnitude de até 50%. A confiança usa mínimo de uma janela e meta de cinco.
O treino principal usa 7d. Previsões antigas de 30d não são convertidas para
7d. Sem previsão na data/horizonte do snapshot, aparece o baseline atual. Veja [Pipeline ML](ML_PIPELINE.md) e
[Confiabilidade ML](ML_CONFIDENCE.md).

Quando uma fonte obrigatória falha, o pipeline interrompe a geração do novo
snapshot. O deploy ainda pode publicar a versão disponível da aplicação se
os testes passaram. Um deploy bem-sucedido não comprova uma nova coleta.
