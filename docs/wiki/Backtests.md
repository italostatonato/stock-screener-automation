# Histórico retroativo e backtest

Revisado em 07/09/2026. Os comandos deste guia são executados separadamente;
não integram o workflow semanal de coleta. Faça backup de `data/` antes de
reprocessar. As curvas teóricas do dashboard têm premissas próprias, descritas
no [guia do dashboard](https://github.com/italostatonato/stock-screener-automation/wiki/Dashboard).

## Separação obrigatória

O histórico observado e o reconstruído têm naturezas diferentes e nunca são
gravados no mesmo lake como se fossem equivalentes.

- `OBSERVADO`: ranking realmente salvo/publicado pelo robô.
- `SIMULADO_POINT_IN_TIME`: ranking reconstituído posteriormente com dados cuja
  data de disponibilização era anterior ou igual à data do sinal.

Essa distinção evita transformar um backfill em evidência de uma decisão que não
foi realmente tomada no passado.

## Histórico observado

```powershell
python scripts/build_observed_history.py
python scripts/run_observed_backtest.py
```

Fontes, em ordem de precedência por data e classe: snapshots do lake, JSONs já
publicados no dashboard e Excels locais. O manifesto registra completude e origem.

Saídas principais:

```text
data/backtest/observed_portfolios.parquet
data/backtest/observed_history_manifest.json
data/backtest/observed_backtest_periods.parquet
data/backtest/observed_backtest_summary.json
data/backtest/observed_curve_fii.parquet
data/backtest/observed_curve_acao.parquet
```

## Backfill point-in-time de FIIs

```powershell
python scripts/build_point_in_time_history.py --start 2021-01-01
python scripts/run_point_in_time_backtest.py
```

O sinal mensal usa o último pregão do mês. Fundamentos vêm do Informe Mensal de
FII da CVM, preservando data de referência, data de entrega e versão. Preço,
liquidez e volatilidade de formação do sinal vêm do COTAHIST oficial da B3. Os
arquivos brutos e a fundação pesada são cache local ignorado pelo Git; hashes e
metadados ficam no manifesto versionável.

O manifesto identifica a versão `fii_v1_legacy_selection`. A construção chama
as funções de score e seleção disponíveis no código atual, mas não dispõe
de todos os sete indicadores da coleta atual. Indicadores ausentes recebem
score neutro e o filtro de DY pode usar o dividendo mensal. Portanto, não
apresente esse backfill como reprodução exata da estratégia atual com todos
os fundamentos históricos disponíveis.

Os snapshots ficam em `data/point_in_time/snapshots/YYYY-MM-DD/`. Carteiras com
menos de 20 ativos são marcadas como parciais e ficam fora do backtest principal.
Elas podem ser incluídas apenas para sensibilidade com `--include-partial`.

## Regras do motor

- sinal calculado no fechamento de D e entrada no próximo pregão;
- carteira equal weight;
- preço ajustado para retorno e benchmark;
- custo de 10 bps multiplicado pelo turnover, configurável por CLI;
- ativo sem preço vira caixa, sem ser removido silenciosamente da média;
- cobertura, tickers ausentes, preços defasados e turnover são salvos por período;
- datas com carteira incompleta são excluídas por padrão.

O benchmark de FIIs usa XFIX11 como **proxy de IFIX**. O custo de 10 bps
corresponde a 0,10% multiplicado pelo turnover; não é uma cobrança fixa
de 10% nem inclui toda a tributação de uma carteira real.

## Execução offline e parâmetros

`--offline` existe em `build_point_in_time_history.py`,
`run_observed_backtest.py` e `run_point_in_time_backtest.py`. Ele reutiliza
arquivos/cache existentes; uma primeira execução sem os dados necessários
precisa obtê-los antes. O consolidado observado não exige esse parâmetro.

```powershell
python scripts/build_point_in_time_history.py --start 2021-01-01 --offline
python scripts/run_observed_backtest.py --offline --end-date 2026-09-06 --transaction-cost-bps 10
python scripts/run_point_in_time_backtest.py --offline --end-date 2026-09-06 --transaction-cost-bps 10
```

A data acima é um exemplo reproduzível, não um corte atualizado automaticamente.
`--include-partial` pertence ao backtest point-in-time e deve ficar identificado
como análise de sensibilidade.

## Limitações atuais

O backtest point-in-time de FIIs usa Yahoo Finance para retorno ajustado. Tickers
renomeados ou extintos não têm cobertura uniforme, portanto o resumo deve ser
tratado como preliminar quando a cobertura média estiver baixa. O COTAHIST da B3
é completo para negociação, mas seus preços não são ajustados por proventos. Por
isso o script também gera uma curva diagnóstica `fii_b3_price_only_curve.parquet`:
ela mede cobertura e retorno de preço, mas não substitui uma série de retorno total.

O retroativo de ações ainda não é publicado. Os demonstrativos ITR/DFP da CVM
têm data de recebimento adequada para point-in-time, mas falta fechar um cadastro
histórico auditável ticker–CNPJ, eventos societários e métricas equivalentes às da
estratégia atual (incluindo EBITDA e dividendos). Até essa fundação existir, criar
rankings históricos de ações produziria viés de sobrevivência e falsa precisão.

## Leitura dos resultados

`data/point_in_time/backtest/fii_summary.json` traz lado a lado a visão ajustada do
Yahoo e o diagnóstico de preço da B3. Para auditoria, use `fii_periods.parquet` e
`fii_b3_price_only_periods.parquet`: cobertura e tickers ausentes estão explícitos.
Não compare o resultado sintético com o histórico observado como se ambos fossem
decisões reais; use o primeiro para pesquisa e o segundo para acompanhamento fora
da amostra.
