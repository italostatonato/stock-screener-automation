# Stock Screener Automation

[![Dashboard](https://img.shields.io/badge/dashboard-online-1F4E79)](https://italostatonato.github.io/stock-screener-automation/)
[![Python](https://img.shields.io/badge/python-3.11+-3776AB)](https://www.python.org/)
[![GitHub Actions](https://img.shields.io/badge/automation-GitHub%20Actions-24292F)](https://github.com/italostatonato/stock-screener-automation/actions)

Screener automático de **FIIs** e **ações brasileiras** com coleta de dados públicos, limpeza e normalização, score multifatorial, filtros adaptativos por quartis, geração de Excel, histórico em Parquet, camada incremental de dados, modelos de Machine Learning em modo sombra, backtest e dashboard web no GitHub Pages.

**Dashboard ao vivo:** https://italostatonato.github.io/stock-screener-automation/

> Projeto educacional e analítico. Não constitui recomendação de investimento.

---

## Visão geral

O projeto roda automaticamente em dias úteis e gera um ranking quantitativo dos ativos mais bem posicionados dentro do universo coletado.

O fluxo atual combina:

- coleta diária de FIIs no Fundsexplorer;
- coleta diária de ações no Investsite;
- limpeza de números, percentuais e moedas no formato brasileiro;
- score de 0 a 100 calculado no universo completo;
- filtro em duas camadas: critérios mínimos + quartis móveis;
- Top 20 FIIs e Top 20 ações;
- Excel diário formatado;
- dashboard web com rankings, recorrência, indicadores, backtests e modelos ML;
- histórico consolidado em Parquet;
- camada incremental em `data/lake/snapshots/YYYY-MM-DD/`;
- datasets derivados para Machine Learning;
- modelos ML em modo sombra para comparação contra o score atual;
- healthcheck de dados e reconstrução a partir do lake.

---

## Arquitetura

```text
main.py                         Orquestra o pipeline completo
config.yaml                     Caminhos, fontes, filtros e colunas
requirements.txt                Dependências Python

src/
  scraper.py                    Coleta FIIs e ações via Selenium
  cleaner.py                    Limpeza e normalização de dados financeiros
  filters.py                    Filtros fixos e adaptativos por quartis
  scorer.py                     Score multifatorial 0-100
  storage.py                    Histórico Excel e snapshots
  formatter.py                  Formatação do Excel final
  market_data.py                IPCA, Selic, IGP-M, câmbio e cripto
  benchmark.py                  IBOV, IFIX, IMOB, CDI e séries de mercado
  backtest.py                   Backtest e carteira histórica Top 20
  ml_storage.py                 Append dos históricos consolidados em Parquet
  dataset_builder.py            Feature engineering e targets futuros
  ml_models.py                  Modelos ML em modo sombra
  data_lake.py                  Camada incremental, manifesto e qualidade
  exporter.py                   JSON do dashboard

docs/
  index.html                    Dashboard web estático
  data/index.json               Índice de snapshots do dashboard
  data/YYYY-MM-DD.json          Payload diário do dashboard
  ARCHITECTURE.md               Arquitetura técnica
  ML_PIPELINE.md                Pipeline de Machine Learning
  OPERATIONS.md                 Operação, validação e troubleshooting

data/
  old/                          Históricos Excel Top 20
  output/                       Excel diário final
  ml/                           Históricos, datasets e previsões ML
  backtest/                     Carteiras históricas
  lake/                         Fonte incremental oficial
    manifest.json               Manifesto global do lake
    quality_report.json         Último relatório de qualidade
    snapshots/YYYY-MM-DD/       Snapshot diário particionado

scripts/
  healthcheck_data.py           Validação de dados, duplicatas e dashboard
  rebuild_from_lake.py          Reconstrução de derivados a partir do lake

tests/                          Testes automatizados
.github/workflows/
  run_screener.yml              Automação diária via GitHub Actions
```

---

## Pipeline diário

1. Carrega `config.yaml` e configura logs.
2. Coleta FIIs ou usa arquivo local quando configurado.
3. Limpa e normaliza FIIs.
4. Calcula score FIIs no universo completo.
5. Aplica filtros fixos e filtros por quartil.
6. Atualiza histórico Excel do Top 20 FIIs.
7. Salva universo FIIs em `data/ml/historico_fiis.parquet`.
8. Coleta ações no Investsite.
9. Calcula score ações no universo completo.
10. Aplica filtros fixos e filtros por quartil.
11. Atualiza histórico Excel do Top 20 ações.
12. Salva universo ações em `data/ml/historico_acoes.parquet`.
13. Coleta indicadores de mercado e benchmarks.
14. Atualiza carteira histórica em `data/backtest/carteiras_historicas.parquet`.
15. Salva snapshot incremental em `data/lake/snapshots/YYYY-MM-DD/`.
16. Gera datasets derivados com targets futuros.
17. Executa modelos ML em modo sombra.
18. Gera snapshot Excel em `data/output/`.
19. Exporta JSON diário em `docs/data/YYYY-MM-DD.json`.
20. Reconstrói `docs/data/index.json` com snapshots existentes.
21. Executa checagens de qualidade.
22. Copia o Excel para OneDrive local quando configurado.

---

## Dashboard

O dashboard web é publicado via GitHub Pages e carrega sempre o snapshot mais recente listado em `docs/data/index.json`.

Principais telas:

- **Visão geral**: KPIs comparativos, score, resumo Top 20 e comparativos em base 100.
- **Ações**: ranking de ações com preço, score e principais indicadores.
- **FIIs**: ranking de FIIs com preço, score, DY, P/VP, liquidez e setor.
- **Recorrentes**: ativos que mais apareceram no Top 20 histórico, com indicadores atuais.
- **Modelos ML**: comparação entre score atual e modelos preditivos em modo sombra.
- **Indicadores**: mercado, macro, câmbio, cripto e benchmarks.
- **Info**: metodologia, premissas e limitações.

Cores principais:

- Ações: `#1F4E79`
- FIIs: `#7A869A`
- Positivo: verde
- Negativo: vermelho
- Fundo: escuro neutro

---

## Camada de dados

O projeto usa três camadas:

### 1. Lake incremental

Fonte oficial para crescimento de longo prazo:

```text
data/lake/snapshots/YYYY-MM-DD/
  fii_universe.parquet
  acoes_universe.parquet
  top_fiis.parquet
  top_acoes.parquet
  carteira.parquet
  manifest.json
```

Também existem:

```text
data/lake/manifest.json
data/lake/quality_report.json
```

### 2. Parquets consolidados

Compatibilidade e consumo rápido:

```text
data/ml/historico_fiis.parquet
data/ml/historico_acoes.parquet
data/ml/dataset_fiis.parquet
data/ml/dataset_acoes.parquet
data/backtest/carteiras_historicas.parquet
```

### 3. JSONs do dashboard

Camada leve para frontend:

```text
docs/data/index.json
docs/data/YYYY-MM-DD.json
```

O dashboard deve receber dados agregados e prontos para tela. Histórico bruto deve ficar no lake e nos Parquets.

---

## Machine Learning em modo sombra

Os modelos rodam sem substituir o ranking oficial. Eles são usados para aprender, comparar e medir performance contra o score atual.

Modelos atuais:

- Score Top atual, usado como baseline;
- Ridge Regression;
- Random Forest;
- Extra Trees;
- XGBoost;
- LightGBM;
- CatBoost;
- Ensemble médio.

Arquivos gerados:

```text
data/ml/model_predictions_fiis.parquet
data/ml/model_predictions_acoes.parquet
data/ml/model_performance.parquet
```

Métricas monitoradas:

- retorno médio dos Top 20 escolhidos pelo modelo;
- hit rate;
- Spearman IC;
- alpha contra o Score Top atual;
- número de janelas válidas;
- status de maturidade.

No começo, os modelos podem aparecer como **Aquecendo**, porque ainda faltam janelas futuras suficientes para validação.

---

## Automação

O workflow `.github/workflows/run_screener.yml`:

- roda em dias úteis;
- usa cron `0 11 * * 1-5`, equivalente a **08h BRT**;
- permite execução manual por `workflow_dispatch`;
- usa cache de `pip`;
- roda testes antes do screener;
- executa `python main.py`;
- executa `python scripts/healthcheck_data.py`;
- salva artefatos da execução;
- commita dados gerados em:
  - `docs/data/`
  - `data/lake/`
  - `data/ml/`
  - `data/backtest/`
- usa `concurrency` para evitar execuções simultâneas;
- notifica falha via Telegram quando os secrets estão configurados.

---

## Setup local

```bash
git clone https://github.com/italostatonato/stock-screener-automation.git
cd stock-screener-automation
python -m venv .venv
```

### Windows

```bash
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Linux/macOS

```bash
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

---

## Validação local

Rodar testes:

```bash
pytest tests/ -v
```

Rodar healthcheck:

```bash
python scripts/healthcheck_data.py
```

Reconstruir derivados a partir do lake:

```bash
python scripts/rebuild_from_lake.py
```

Testar dashboard localmente:

```bash
python -m http.server 8000
```

Acesse:

```text
http://localhost:8000/docs/
```

---

## Cuidados importantes

- Não sobrescrever a pasta `data/` em pacotes visuais.
- Antes de mudanças estruturais, fazer backup de `data/`.
- `data/lake/` é a fonte incremental oficial.
- `data/ml/` e `data/backtest/` são derivados/cache e podem ser reconstruídos.
- `docs/data/` deve conter apenas payloads leves para o dashboard.
- Parquets e Excel são binários; não revisar por diff textual.
- Sempre rodar `pytest tests/ -v` e `python scripts/healthcheck_data.py` antes de subir mudanças estruturais.
- Não commitar `backups/`.
- Evitar mudar nomes de colunas sem atualizar todo o pipeline.

---

## Roadmap

### Curto prazo

- Melhorar legibilidade e completude dos gráficos do dashboard.
- Adicionar busca/ordenação nas tabelas grandes.
- Monitorar Action após a nova camada `data/lake`.
- Confirmar maturidade inicial dos modelos ML.

### Médio prazo

- Separar treino e previsão dos modelos.
- Treinar modelos com frequência menor que a previsão diária.
- Criar critério formal para modelo líder.
- Adicionar explicabilidade com SHAP ou importância de variáveis.
- Particionar históricos por ano/mês se o repo crescer demais.

### Longo prazo

- Reduzir dependência de binários versionados diariamente.
- Avaliar armazenamento externo gratuito/barato para histórico pesado.
- Criar relatório automático de performance dos modelos.
- Criar documentação pública mais visual para portfólio.

---

## Licença

Projeto pessoal para estudo, portfólio e análise quantitativa. Uso por terceiros deve considerar limitações das fontes públicas, disponibilidade dos sites coletados e premissas metodológicas.
