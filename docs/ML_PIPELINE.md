# Pipeline de Machine Learning

Revisado em 15/09/2026 contra `main.py`, `src/dataset_builder.py`,
`src/ml_models.py` e `src/exporter.py`.

## Entradas e modo sombra

O ranking oficial continua sendo o Top N de `src/scorer.py` e `src/filters.py`.
Os modelos geram rankings experimentais, previsões e métricas sem promover
automaticamente um modelo ao lugar do score.

O treino acompanha a execução semanal ou o acionamento manual. Os históricos
acumulam snapshots por data de coleta. Os horizontes em dias abaixo indicam
prazos de retorno futuro, não a frequência de coleta ou treinamento.

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
Sem observação futura, o target permanece nulo. Tickers ausentes/vazios e
preços não positivos ou infinitos são descartados. A feature `Aprovado_Filtro`
inclui tanto `Rank #N` quanto os aprovados fora do Top N. Históricos inválidos
interrompem a construção para não reutilizar silenciosamente um dataset antigo. São retornos entre preços dos
snapshots, diferentes da série ajustada do motor de backtest separado.

## Horizontes realmente executados

`run_ml_pipeline()`, `main.py` e `scripts/rebuild_from_lake.py` usam **7d**.
O exporter declara 7d como principal e 30d como estratégico; targets de 30,
60 e 90 dias permanecem disponíveis para experimentos separados.

Cada previsão recebe `Horizonte`. A persistência deduplica por data, classe,
ticker e horizonte, permitindo guardar previsões 7d e 30d do mesmo ativo.
`src/ml_horizons.py` identifica previsões antigas apenas quando as colunas de
retorno permitem determinar um único horizonte; casos ambíguos ficam
`indefinido`. Scores supervisionados de outro horizonte não entram na
avaliação de 7d. O baseline Score Top independe de horizonte.

O ranking exibido usa previsões da mesma data e horizonte do snapshot.
Sem correspondência, usa o baseline atual. Previsões históricas de 30d e
JSONs publicados são preservados; a correção não fabrica previsões passadas
de 7d. Por isso, o painel pode voltar ao estado de aquecimento.

`scripts/refresh_ml_7d_primary_from_docs.py` é um alias de compatibilidade
para o rebuild canônico do lake. Não reconstrói o universo a partir do Top N
dos JSONs nem altera snapshots do dashboard. Os scripts `apply_ml_*` apenas
informam que as migrações já foram incorporadas, sem modificar arquivos.

Na reconstrução, rentabilidade do período e taxas de administração e
performance de FIIs são normalizadas: snapshots antigos usam texto com `%`,
os novos usam frações numéricas. A conversão ocorre nos derivados e preserva
as partições originais do lake.

## Treinamento e modelos

A data mais recente recebe as previsões. O treino usa linhas de datas
anteriores com target preenchido e `Data_Futura_*` até a data prevista.
Datas de realização ausentes suspendem o treino para evitar uso de informação futura. O mínimo operacional é de **20 linhas
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
esperado agregado é a média das previsões disponíveis, identificada por
`modelo_projecao: Ensemble`. As janelas do Ensemble liberam essa projeção.
`modelo_lider` indica
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
[Confiabilidade ML](ML_CONFIDENCE.md).

## Evoluções pendentes

Separar treino e previsão e avaliar estabilidade,
turnover e desempenho em mais ciclos são próximos passos. Ainda não existe
regra implementada de promoção automática do modelo mais confiável ao ranking
oficial.
