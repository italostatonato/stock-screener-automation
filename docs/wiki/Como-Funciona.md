# Como Funciona

Revisado em 07/09/2026. O Radar Semanal executa uma coleta semanal de FIIs e
ações, gera rankings e derivados e publica um dashboard estático.

## Ingestão e seleção

`main.py` carrega `config.yaml` por `src/config.py` e usa a data civil de
`America/Sao_Paulo` para nomear logs e snapshots. Um arquivo em
`paths.local_input_file` substitui a coleta de FIIs quando existe; do contrário,
`src/scraper.py` usa Selenium/Chrome no Fundsexplorer. A fonte padrão de ações
é a tabela HTTP do Fundamentus.

`src/cleaner.py` normaliza os FIIs. O adaptador de ações já entrega as colunas
numéricas compatíveis. `src/scorer.py` calcula sete percentis com pesos iguais
no universo completo. `src/filters.py` aplica pisos de elegibilidade, ordena
pelo score, desempata pelo ticker e limita o Top N. A seleção de ações também
remove classes duplicadas de uma mesma empresa. Veja [Metodologia](https://github.com/italostatonato/stock-screener-automation/blob/main/docs/METHODOLOGY.md).

Um Top FII vazio interrompe a execução antes das escritas de histórico.
Coleta, score e Top Ações não vazio também são obrigatórios. Uma falha de
ações ocorre antes do snapshot do lake e do JSON novo, mas os históricos
locais de FIIs já podem ter sido atualizados. O pipeline não é uma transação
única entre todos os arquivos.

## Persistência

- `src/storage.py`: Excels históricos em `data/old/` e Excel final em
  `data/output/`, ignorados pelo Git.
- `src/ml_storage.py`: históricos dos universos com `Data_Execucao`.
- `src/backtest.py`: carteira histórica com preço de entrada e backtest legado.
- `src/data_lake.py`: snapshots por data, manifestos, reconstrução e qualidade.
- `src/delivery.py`: cópia opcional do Excel e log em `data/delivery/`.

```text
data/lake/snapshots/YYYY-MM-DD/
  fii_universe.parquet
  acoes_universe.parquet
  top_fiis.parquet
  top_acoes.parquet
  carteira.parquet
  manifest.json

data/lake/manifest.json
data/lake/quality_report.json
data/lake/known_incomplete_snapshots.json
```

O lake é a fonte oficial do histórico observado. Os caminhos são particionados
por data, não por ID da execução: rodar novamente no mesmo dia atualiza a
partição daquela data. Snapshots históricos reconhecidos como incompletos
são preservados e identificados no arquivo de exceções.

Depois de salvar o lake, `main.py` chama `rebuild_legacy_tables_from_lake()`
para reconstruir os históricos de `data/ml/` e a carteira de `data/backtest/`.

## Derivados analíticos

`src/dataset_builder.py` cria features e targets de 7, 30, 60 e 90 dias.
`src/ml_models.py` treina e calcula previsões em modo sombra.
`src/ml_confidence.py` resume maturidade e desempenho validado.
Treino e previsão ainda acontecem juntos. A chamada principal usa 30d,
enquanto o exporter declara 7d como horizonte principal da tela.
Leia [Pipeline ML](https://github.com/italostatonato/stock-screener-automation/wiki/Modelos-ML) para essa diferença operacional.

O histórico retroativo é separado da execução semanal:

- `src/observed_history.py`: consolida carteiras realmente publicadas.
- `src/point_in_time.py`: reconstrói sinais mensais de FIIs com dados CVM/B3.
- `src/backtest_engine.py`: aplica calendário, preços ajustados, custos,
  turnover e auditoria de cobertura.
- `data/point_in_time/`: snapshots sintéticos e resultados isolados do lake.

Esses scripts não são chamados pelo workflow semanal. Suas premissas diferem
das curvas de preço do dashboard. Veja [Backtests](https://github.com/italostatonato/stock-screener-automation/wiki/Backtests).

## Exportação e interface

`src/market_data.py` coleta indicadores e nomes de ativos.
`src/benchmark.py` prepara séries de mercado e macroeconomia.
`src/formatter.py` formata o Excel.
`src/exporter.py` gera `docs/data/YYYY-MM-DD.json` e reconstrói o índice de datas.

`docs/index.html` concentra HTML, CSS e JavaScript da aplicação. O navegador
consome os snapshots e calcula a alocação, as quantidades inteiras e as curvas
da carteira híbrida com os pesos selecionados. A máscara IMask é distribuída
localmente em `docs/assets/vendor/`. Não há backend de ordens ou autenticação
própria no dashboard. O link de apresentação abre um recurso externo de leitura.

```text
Coleta → Normalização → Score → Elegibilidade/Top N
       → Históricos e lake → Reconstrução → Datasets/ML
       → Excel e JSON → Qualidade → Entrega local opcional

Lake/JSON/Excel observados → Histórico observado → Motor de backtest
CVM/B3 → Histórico point-in-time isolado → Motor de backtest
JSON → Dashboard → Simulação de alocação no navegador
```

O JSON é uma saída de apresentação. A recuperação histórica pode usá-lo como
fonte secundária quando o lake não cobre uma data; esse é um caminho explícito
de recuperação, não a fonte primária da coleta.

## Orquestração e limites

O workflow [run_screener.yml](https://github.com/italostatonato/stock-screener-automation/blob/main/.github/workflows/run_screener.yml) roda às
segundas, 08h de São Paulo, ou por acionamento manual. `test` precede `screener`.
O job `deploy` consulta a `main` atual e roda quando os testes passam, mesmo
se `screener` falhar. A etapa independente de healthcheck bloqueia o commit
automático em caso de `error`; vários erros de módulos auxiliares dentro de
`main.py` são registrados em log e não interrompem sozinhos a execução.

Os principais limites são dependência de fontes públicas, crescimento de
binários no Git, cobertura de preços históricos e maturidade estatística.
Particionamento adicional, separação de treino/previsão e entrega remota via
Microsoft Graph permanecem evoluções futuras.
