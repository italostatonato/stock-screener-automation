# Stock Screener Automation

[![Dashboard](https://img.shields.io/badge/dashboard-online-1F4E79)](https://italostatonato.github.io/stock-screener-automation/)
[![Python](https://img.shields.io/badge/python-3.11+-3776AB)](https://www.python.org/)
[![GitHub Actions](https://img.shields.io/badge/automation-GitHub%20Actions-24292F)](https://github.com/italostatonato/stock-screener-automation/actions)

Screener automático de **FIIs** e **ações brasileiras**, com coleta via Selenium, limpeza e normalização de dados, score multifatorial, filtros adaptativos por quartis, geração de Excel formatado, histórico em Parquet, base para Machine Learning, backtest e dashboard web publicado via GitHub Pages.

**Dashboard ao vivo:** https://italostatonato.github.io/stock-screener-automation/

> Este projeto é educacional e analítico. Não constitui recomendação de investimento.

---

## Visão geral

O projeto roda automaticamente em dias úteis e gera um ranking dos ativos mais bem posicionados segundo critérios quantitativos. O fluxo atual combina:

- coleta diária de FIIs no Fundsexplorer;
- coleta diária de ações no Investsite;
- limpeza de dados financeiros em formatos brasileiros;
- score de 0 a 100 calculado sobre o universo completo;
- filtro em duas camadas: critérios mínimos + quartis móveis;
- Top 20 FIIs e Top 20 ações;
- Excel formatado com recomendações, premissas, bases completas e gráficos;
- dashboard web com visão geral, rankings, recorrência, indicadores e comparativos;
- histórico em Parquet para futuras etapas de Machine Learning;
- backtest e acompanhamento de carteiras Top 20 em base 100.

---

## Arquitetura do projeto

```text
main.py                         Orquestra o pipeline completo
config.yaml                     Configura caminhos, fontes, filtros e colunas
requirements.txt                Dependências Python

src/
  scraper.py                    Coleta FIIs e ações via Selenium
  cleaner.py                    Limpa percentuais, moedas, inteiros e floats
  filters.py                    Aplica filtros fixos e adaptativos por quartis
  scorer.py                     Calcula score multifatorial 0-100
  storage.py                    Atualiza históricos Excel e salva snapshot
  formatter.py                  Formata o Excel final com openpyxl
  market_data.py                Coleta IPCA, Selic, IGP-M, câmbio e cripto
  benchmark.py                  Coleta IBOV, IFIX, IMOB, CDI e séries macro
  backtest.py                   Executa backtest inicial e carteira histórica
  ml_storage.py                 Salva histórico completo em Parquet
  dataset_builder.py            Gera datasets derivados para ML
  exporter.py                   Exporta JSON para o dashboard

docs/
  index.html                    Dashboard web estático
  data/
    index.json                  Lista de snapshots disponíveis
    YYYY-MM-DD.json             Payload diário usado pelo dashboard

data/
  input/                        Arquivos de entrada e downloads temporários
  old/                          Históricos Excel do Top 20
  output/                       Snapshots Excel diários
  ml/                           Históricos e datasets em Parquet
  backtest/                     Carteiras históricas para avaliação

tests/
  test_cleaner.py               Testes de parsing e limpeza
  test_filters.py               Testes dos filtros

.github/workflows/
  run_screener.yml              Automação diária via GitHub Actions
```

---

## Pipeline diário

1. Carrega `config.yaml` e configura logs.
2. Coleta FIIs via Fundsexplorer ou arquivo local.
3. Limpa e normaliza os dados de FIIs.
4. Calcula score FIIs no universo completo.
5. Aplica filtros fixos e filtros por quartil.
6. Atualiza histórico Excel do Top 20 FIIs.
7. Salva universo completo de FIIs em `data/ml/historico_fiis.parquet`.
8. Coleta ações via Investsite.
9. Calcula score ações no universo completo.
10. Aplica filtros fixos e filtros por quartil.
11. Atualiza histórico Excel do Top 20 ações.
12. Salva universo completo de ações em `data/ml/historico_acoes.parquet`.
13. Coleta indicadores de mercado e benchmarks.
14. Atualiza backtest e carteira histórica.
15. Gera snapshot Excel em `data/output/`.
16. Exporta JSON do dashboard em `docs/data/`.
17. Copia o Excel para OneDrive local quando configurado.

---

## Dashboard

O dashboard web é publicado via GitHub Pages e sempre carrega o snapshot mais recente disponível em `docs/data/index.json`.

Principais telas:

- **Visão geral**: KPIs comparativos, score, resumo Top 20 e comparativos em base 100.
- **Ações**: cards do ranking de ações, com preço, score e principais indicadores.
- **FIIs**: cards do ranking de FIIs, com preço, score, DY, P/VP, liquidez e setor.
- **Recorrentes**: ativos que mais apareceram no Top 20 histórico, com aparições e score médio.
- **Indicadores**: mercado, macro, câmbio, cripto e benchmarks.
- **Info**: metodologia, premissas e limitações.

Cores principais usadas no dashboard:

- Ações: `#1F4E79`
- FIIs: `#7A869A`
- Positivo: verde
- Negativo: vermelho
- Fundo: neutro escuro

---

## Histórico, ML e backtest

O projeto já possui uma camada de histórico para evoluções quantitativas e de Machine Learning.

Arquivos principais:

```text
data/ml/historico_fiis.parquet
data/ml/historico_acoes.parquet
data/ml/dataset_fiis.parquet
data/ml/dataset_acoes.parquet
data/backtest/carteiras_historicas.parquet
```

A lógica atual é acumular dados diariamente. Com o tempo, o dataset passa a permitir:

- retorno futuro de 7, 30, 60 e 90 dias;
- comparação contra benchmarks;
- análise de recorrência no Top 20;
- treinamento futuro com Random Forest, XGBoost ou LightGBM;
- explicabilidade com SHAP.

Para gerar os datasets manualmente:

```bash
python -m src.dataset_builder
```

---

## Automação

O workflow `.github/workflows/run_screener.yml`:

- roda testes automatizados;
- executa o screener em dias úteis;
- usa cron `0 11 * * 1-5`, equivalente a **08h BRT**;
- salva o Excel como artefato do GitHub Actions;
- atualiza `docs/data/` e publica o dashboard via GitHub Pages;
- notifica falha via Telegram, quando os secrets estão configurados.

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

## Rodar testes

```bash
pytest tests/ -v
```

---

## Testar dashboard localmente

```bash
python -m http.server 8000
```

Acesse:

```text
http://localhost:8000/docs/
```

---

## Cuidados importantes

- Não sobrescrever a pasta `data/` em pacotes de alteração visual.
- Antes de mudanças que mexam em histórico, fazer backup de `data/`.
- Sempre usar `encoding="utf-8"` ao ler e escrever arquivos.
- Não normalizar nomes de colunas de entrada sem ajustar todo o pipeline.
- FIIs e ações usam nomes de colunas diferentes por causa das fontes originais.
- Parquet exige `pyarrow` ou engine compatível instalada.

---

## Roadmap

### Próximos passos técnicos

- Integrar `dataset_builder.py` ao `main.py` de forma controlada.
- Criar relatório de maturidade do dataset ML.
- Expandir backtest para janelas de 7, 30, 60 e 90 dias.
- Treinar primeiro modelo Random Forest quando houver target suficiente.
- Testar XGBoost e comparar contra score atual.
- Adicionar explicabilidade com SHAP.

### Produto e dashboard

- Melhorar textos explicativos para público leigo.
- Incluir filtros de visualização no dashboard.
- Criar visão de evolução de recorrentes.
- Adicionar domínio próprio ou encurtador.
- Adicionar Open Graph tags para preview em redes sociais.

---

## Licença

Projeto pessoal para estudo, portfólio e análise quantitativa. Uso por terceiros deve considerar limitações das fontes públicas e das metodologias utilizadas.
