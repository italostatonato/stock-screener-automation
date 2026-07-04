# Arquitetura técnica

## Objetivo

Manter uma pipeline quantitativa diária para FIIs e ações brasileiras, com histórico, dashboard, backtest e modelos ML em modo sombra.

## Camadas

### 1. Ingestão

Fontes públicas coletadas via Selenium e bibliotecas gratuitas.

Componentes:

- `src/scraper.py`
- `src/market_data.py`
- `src/benchmark.py`

### 2. Limpeza e score

Responsável por transformar dados brutos em indicadores numéricos comparáveis.

Componentes:

- `src/cleaner.py`
- `src/scorer.py`
- `src/filters.py`

### 3. Seleção

Define Top 20 FIIs e Top 20 ações usando critérios fixos e quartis móveis.

Resultado:

- ranking diário;
- universo completo com status;
- score por ativo.

### 4. Persistência

Três níveis:

```text
data/lake/       snapshots incrementais oficiais
data/ml/         históricos, datasets e previsões
data/backtest/   carteiras históricas
```

`data/lake` é a fonte mais segura para reconstrução futura.

### 5. Derivados analíticos

Componentes:

- `src/dataset_builder.py`
- `src/ml_models.py`
- `src/backtest.py`

Saídas:

- datasets com targets futuros;
- previsões por modelo;
- performance por modelo;
- carteira histórica.

### 6. Apresentação

Componentes:

- `src/exporter.py`
- `docs/index.html`
- `docs/data/*.json`

O frontend deve consumir JSONs leves e prontos para visualização.

---

## Regra de dependência

```text
Scraper → Cleaner → Scorer/Filters → Storage/Data Lake → Dataset/ML/Backtest → Exporter → Dashboard
```

Evitar dependência reversa. O dashboard nunca deve ser fonte de dados para processamento.

---

## Escalabilidade

A arquitetura atual escala melhor porque:

- salva snapshots diários separados;
- mantém manifesto global;
- roda healthcheck;
- permite rebuild dos derivados;
- separa dados brutos, derivados e JSON de frontend.

Limitações futuras esperadas:

- binários versionados no Git podem crescer;
- modelos podem ficar pesados se treinarem diariamente;
- tabelas do dashboard podem precisar de paginação/busca.

Mitigações planejadas:

- particionar histórico por ano/mês;
- separar treino e previsão;
- limitar JSONs a agregados;
- manter dados pesados fora do frontend.
