# Modelos ML

Revisado em 07/09/2026 contra `main.py`, `src/dataset_builder.py`,
`src/ml_models.py` e `src/exporter.py`.

## Entradas e modo sombra

O ranking oficial continua sendo o Top N de `src/scorer.py` e `src/filters.py`.
Os modelos geram rankings experimentais, previsões e métricas sem promover
automaticamente um modelo ao lugar do score.

```text
data/lake/snapshots/YYYY-MM-DD/
  → data/ml/historico_fiis.parquet
  → data/ml/historico_acoes.parquet
  → data/ml/dataset_fiis.parquet
  → data/ml/dataset_acoes.parquet
```

Os datasets contêm features numéricas e targets para 7, 30, 60 e 90 dias
corridos. Para cada ativo, o target usa a primeira observação disponível em
data igual ou posterior à data de origem mais o horizonte. Um retorno rotulado
7d pode cobrir mais de sete dias quando há lacunas entre coletas.
Sem observação futura, o target permanece nulo. São retornos entre preços dos
snapshots, diferentes da série ajustada do motor de backtest separado.

## Horizontes realmente executados

- `run_ml_pipeline()` tem `DEFAULT_HORIZON = 7`.
- `main.py` passa explicitamente `horizon=30`.
- `scripts/rebuild_from_lake.py` também passa `horizon=30`.
- O exporter declara `horizonte_principal: 7d` e
  `horizonte_estrategico: 30d`, calcula maturidade com sete dias e constrói
  `performance_historica` com targets de 7d.
- `modelos_ml.performance` vem do Parquet de performance e preserva
  `Horizonte`; a confiabilidade recebe essas linhas sem convertê-las.
- Para projeções, o exporter prefere `retorno_esperado_7d` quando disponível;
  caso contrário, usa `retorno_esperado_30d` e informa o horizonte escolhido.

Existe uma diferença entre a chamada operacional de treinamento e o horizonte
principal declarado pela tela. Cada métrica deve ser lida com seu próprio
`Horizonte`. Alinhar esses caminhos é trabalho futuro; a rotina atual não
garante treinamento e avaliação simultâneos nos dois horizontes.

`scripts/refresh_ml_7d_primary_from_docs.py` é uma ferramenta de
reprocessamento: recupera bases dos JSONs, regrava históricos/datasets, roda
ML em 7d e atualiza o payload mais recente. Não integra o workflow semanal
e exige backup antes do uso. Os scripts `apply_ml_*` são utilitários de
migração/patch, não etapas de instalação de um clone atualizado.

## Treinamento e modelos

A data mais recente recebe as previsões. O treino usa linhas de datas
anteriores com target preenchido. O mínimo operacional é de **20 linhas
treináveis e uma data anterior**, definido por `MIN_TRAIN_ROWS` e
`MIN_TRAIN_DATES`. Isso permite iniciar o experimento e não representa
maturidade estatística.

Modelos disponíveis quando suas bibliotecas carregam e o treino conclui:

- Score Top, baseline;
- Ridge Regression;
- Random Forest;
- Extra Trees;
- XGBoost;
- LightGBM;
- CatBoost;
- Ensemble, média dos scores dos modelos supervisionados disponíveis.

Os retornos previstos são convertidos em percentis para ordenação. O retorno
esperado agregado é a média das previsões disponíveis. `modelo_lider` indica
o modelo com maior score para aquele ativo; não é uma promoção baseada no
melhor desempenho fora da amostra. Falhas de bibliotecas ou treino ficam nos
logs e podem deixar apenas parte dos modelos ou o baseline disponível.

## Saídas e métricas

```text
data/ml/model_predictions_fiis.parquet
data/ml/model_predictions_acoes.parquet
data/ml/model_performance.parquet
```

A avaliação cruza previsões registradas com targets já observados. Uma janela
é uma data de previsão com pelo menos **cinco ativos avaliáveis** para o modelo.
O Top 20 dessa avaliação pode conter menos de 20 ativos se faltarem dados.

As métricas são retorno médio do Top 20, proporção de retornos positivos
(`Hit_Rate_Top20`), correlação de postos (`Spearman_IC`), diferença de retorno
contra Score Top (`Alpha_vs_Score_Top`) e `Janelas_Validas`.
Janelas sobrepostas não constituem períodos independentes de uma carteira.
`performance_historica` preserva data de previsão, data do resultado e número
de ativos; essas janelas não devem ser compostas como retorno acumulado.

## Status e proteção de projeções

Sem dados suficientes, a interface pode mostrar `Sem dados`, `Baseline` ou
`Aquecendo`. A disponibilidade operacional `Ativo` não comprova robustez.
A exibição marca modelos supervisionados com menos de três janelas como
`Em validação`.

A confiabilidade começa em uma janela válida, com meta de cobertura de cinco.
A projeção de retorno só é exibida com três janelas do mesmo modelo, classe e
horizonte e valor finito dentro de ±50%. O ranking experimental pode permanecer
visível enquanto a projeção está oculta. Fórmula e limites estão em
[Confiabilidade ML](https://github.com/italostatonato/stock-screener-automation/wiki/Confiabilidade-ML).

## Evoluções pendentes

Separar treino e previsão, alinhar os horizontes e avaliar estabilidade,
turnover e desempenho em mais ciclos são próximos passos. Ainda não existe
regra implementada de promoção automática do modelo mais confiável ao ranking
oficial.
