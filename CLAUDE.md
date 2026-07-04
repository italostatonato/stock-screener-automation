# Stock Screener Automation — Contexto para assistentes de IA

## O que é este projeto

Screener automático de FIIs e ações brasileiras. O projeto coleta dados públicos, limpa e normaliza indicadores financeiros, calcula scores, aplica filtros adaptativos por quartis, gera Excel formatado, publica dashboard web via GitHub Pages, acumula histórico em Parquet, mantém um data lake incremental e executa modelos de Machine Learning em modo sombra.

- Dashboard: https://italostatonato.github.io/stock-screener-automation/
- Repositório: https://github.com/italostatonato/stock-screener-automation

O projeto é educacional e analítico. Não tratar como recomendação de investimento.

---

## Estado atual

O projeto já possui:

- coleta diária de FIIs e ações;
- score multifatorial 0-100;
- filtros fixos e filtros móveis por quartis;
- Excel diário formatado;
- dashboard web estático;
- histórico consolidado em Parquet;
- camada incremental `data/lake/snapshots/YYYY-MM-DD/`;
- datasets ML com targets futuros;
- modelos ML em modo sombra;
- carteira histórica para backtest;
- aba de recorrentes;
- aba de modelos ML;
- comparativos em base 100 contra benchmarks;
- healthcheck de dados;
- rebuild a partir do lake;
- GitHub Actions com testes, cache, healthcheck e commit automático dos dados.

---

## Princípios importantes

1. **Não perder histórico.** Nunca sobrescrever `data/` sem backup explícito.
2. **Data lake é a fonte incremental oficial.** Parquets consolidados são derivados/cache.
3. **Dashboard deve ser leve.** `docs/data/*.json` deve conter dados prontos para tela, não histórico bruto inteiro.
4. **ML em modo sombra.** Modelos não substituem o score oficial até existir maturidade estatística.
5. **Tudo gratuito/open source.** Não usar APIs pagas, OpenAI API, cloud paga ou serviços externos pagos.
6. **Sempre testar antes de subir.** Rodar `pytest tests/ -v` e `python scripts/healthcheck_data.py`.

---

## Arquitetura — responsabilidades

```text
main.py                         Orquestra o pipeline completo
config.yaml                     Caminhos, fontes, filtros e colunas
requirements.txt                Dependências Python

src/
  scraper.py                    Selenium: Fundsexplorer + Investsite
  cleaner.py                    Normalização de percentuais, moedas e números
  filters.py                    Filtros fixos + quartis adaptativos
  scorer.py                     Score multifatorial 0-100
  storage.py                    Histórico Excel e snapshots
  formatter.py                  Excel formatado com openpyxl
  market_data.py                Indicadores macro, câmbio e cripto
  benchmark.py                  IBOV, IFIX, IMOB, CDI e séries macro
  backtest.py                   Backtest inicial e carteira histórica
  ml_storage.py                 Append dos históricos consolidados
  dataset_builder.py            Feature engineering e targets futuros
  ml_models.py                  Modelos ML em modo sombra
  data_lake.py                  Snapshots incrementais, manifesto e qualidade
  exporter.py                   Exporta JSON do dashboard

docs/
  index.html                    Dashboard web estático
  data/index.json               Índice de snapshots
  data/YYYY-MM-DD.json          Payload diário
  ARCHITECTURE.md               Arquitetura técnica
  ML_PIPELINE.md                Pipeline ML
  OPERATIONS.md                 Operação e troubleshooting

data/
  old/                          Excel histórico Top 20
  output/                       Excel diário final
  ml/                           Históricos, datasets e previsões ML
  backtest/                     Carteiras históricas
  lake/                         Snapshots incrementais oficiais

scripts/
  healthcheck_data.py           Validação de saúde dos dados
  rebuild_from_lake.py          Reconstrói derivados a partir do lake

tests/                          Testes automatizados
.github/workflows/run_screener.yml
```

---

## Pipeline principal

1. Carrega `config.yaml`.
2. Configura logs.
3. Coleta FIIs.
4. Limpa FIIs.
5. Calcula score FIIs no universo completo.
6. Seleciona Top 20 FIIs.
7. Atualiza histórico Excel FIIs.
8. Salva universo FIIs em `data/ml/historico_fiis.parquet`.
9. Coleta ações.
10. Calcula score ações no universo completo.
11. Seleciona Top 20 ações.
12. Atualiza histórico Excel ações.
13. Salva universo ações em `data/ml/historico_acoes.parquet`.
14. Coleta indicadores e benchmarks.
15. Atualiza carteira histórica.
16. Salva snapshot incremental em `data/lake/snapshots/YYYY-MM-DD/`.
17. Gera datasets ML.
18. Roda pipeline ML sombra.
19. Gera Excel diário.
20. Exporta JSON do dashboard.
21. Reconstrói índice do dashboard.
22. Executa quality checks.

---

## Data lake

Estrutura:

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
```

Objetivo:

- reduzir risco de perda de histórico;
- permitir rebuild dos derivados;
- evitar dependência exclusiva de parquets consolidados que mudam diariamente;
- preparar evolução para particionamento futuro.

---

## Arquivos de dados importantes

```text
data/ml/historico_fiis.parquet
data/ml/historico_acoes.parquet
data/ml/dataset_fiis.parquet
data/ml/dataset_acoes.parquet
data/ml/model_predictions_fiis.parquet
data/ml/model_predictions_acoes.parquet
data/ml/model_performance.parquet
data/backtest/carteiras_historicas.parquet
```

Chaves esperadas:

- FIIs histórico: `Data_Execucao` + `FUNDOS`
- Ações histórico: `Data_Execucao` + `Ação`
- Carteiras: `Data_Carteira` + `Tipo` + `Ticker`

Essas chaves não devem ter duplicatas.

---

## Modelos ML

Modelos atuais:

- Score Top atual;
- Ridge;
- Random Forest;
- Extra Trees;
- XGBoost;
- LightGBM;
- CatBoost;
- Ensemble.

Métrica principal sugerida: retorno médio do Top 20 em horizonte de 30 dias.

Métricas auxiliares:

- hit rate;
- Spearman IC;
- alpha vs Score Top;
- janelas válidas;
- maturidade/status.

Enquanto houver pouco histórico, manter status **Aquecendo**.

---

## Workflow GitHub Actions

O workflow diário:

- roda testes;
- instala dependências com cache de pip;
- executa `python main.py`;
- roda `python scripts/healthcheck_data.py`;
- salva artefatos;
- commita dados gerados em:
  - `docs/data/`
  - `data/lake/`
  - `data/ml/`
  - `data/backtest/`
- usa cron `0 11 * * 1-5`, equivalente a 08h BRT;
- usa `concurrency` para evitar sobreposição;
- pode notificar falha via Telegram.

---

## Comandos úteis

Rodar pipeline:

```powershell
python main.py
```

Rodar testes:

```powershell
pytest tests/ -v
```

Healthcheck:

```powershell
python scripts/healthcheck_data.py
```

Rebuild:

```powershell
python scripts/rebuild_from_lake.py
```

Dashboard local:

```powershell
python -m http.server 8000
```

Acessar:

```text
http://localhost:8000/docs/
```

---

## Regras para alterações futuras

- Pacotes visuais devem mexer só em `docs/index.html` e, se necessário, `src/exporter.py`.
- Alterações que tocam `data/` exigem backup antes.
- Não commitar `backups/`.
- Não trocar nomes de colunas sem atualizar filtros, scorer, exporter e testes.
- Ao alterar pipeline, atualizar README, CLAUDE e docs técnicos.
- Ao alterar dashboard, verificar se `docs/data/index.json` aponta para o snapshot mais recente.
- Em conflitos de `docs/data/index.json`, reconstruir o índice varrendo `docs/data/*.json`.

---

## Estado desejado de longo prazo

- `data/lake` como fonte oficial.
- Parquets consolidados reconstruíveis.
- ML treinando em cadência controlada.
- Previsão diária separada de treinamento.
- Dashboard carregando somente dados agregados.
- Histórico particionado por período se o repo crescer demais.
