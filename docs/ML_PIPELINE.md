# Pipeline de Machine Learning

## Objetivo

Comparar o score atual do screener com modelos preditivos, sem substituir a regra oficial antes de haver evidência suficiente.

## Modo sombra

Os modelos rodam em paralelo ao score atual. Eles geram previsões e métricas, mas o ranking oficial continua sendo o Top 20 calculado por score multifatorial.

## Dados de entrada

```text
data/ml/dataset_fiis.parquet
data/ml/dataset_acoes.parquet
```

Esses datasets derivam de:

```text
data/ml/historico_fiis.parquet
data/ml/historico_acoes.parquet
```

E podem ser reconstruídos a partir de:

```text
data/lake/snapshots/YYYY-MM-DD/
```

## Targets

Horizontes previstos:

- 7 dias;
- 30 dias;
- 60 dias;
- 90 dias.

Horizonte principal recomendado para decisão:

```text
30 dias
```

## Modelos

- Score Top atual, baseline;
- Ridge Regression;
- Random Forest;
- Extra Trees;
- XGBoost;
- LightGBM;
- CatBoost;
- Ensemble médio.

## Saídas

```text
data/ml/model_predictions_fiis.parquet
data/ml/model_predictions_acoes.parquet
data/ml/model_performance.parquet
```

## Métricas

- Retorno médio Top 20;
- Hit rate;
- Spearman IC;
- Alpha vs Score Top;
- Janelas válidas;
- Status de maturidade.

## Critério para modelo líder

Um modelo só deve virar candidato a líder quando:

1. tiver janelas válidas suficientes;
2. bater o Score Top em retorno médio;
3. tiver alpha positivo de forma consistente;
4. não trocar a carteira de forma excessivamente instável;
5. passar por mais de um ciclo de mercado/dados.

## Cadência futura recomendada

Hoje o pipeline pode treinar diariamente porque o histórico ainda é pequeno. No futuro, o ideal é separar:

```text
previsão: diária
treinamento: semanal ou quando novos targets futuros forem preenchidos
```

## Status Aquecendo

Enquanto os targets futuros ainda não existem em quantidade suficiente, os modelos devem ser exibidos como **Aquecendo**. Isso evita decisões prematuras.
