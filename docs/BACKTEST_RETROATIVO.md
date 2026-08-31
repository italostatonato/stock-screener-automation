# Histórico retroativo e backtest

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
