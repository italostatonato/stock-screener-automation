# Confiabilidade dos modelos ML

Revisado em 07/09/2026 contra `src/ml_confidence.py` e `src/exporter.py`.

## Três medidas distintas

**Maturidade dos dados** mede a extensão do histórico: dias entre o primeiro e
o último snapshot divididos pelo horizonte, limitada a 100%. O exporter usa
sete dias nesse cálculo. Ter 100% de maturidade não comprova capacidade preditiva.

**Confiabilidade preditiva** é uma pontuação heurística de cobertura e desempenho.
O mínimo atual é **uma janela válida**, e a meta de cobertura é **cinco janelas**.
O valor fica em zero quando não há a janela mínima. Ele não é uma probabilidade
calibrada de acerto nem uma autorização para substituir o ranking oficial.

**Exibição da projeção de retorno** usa outra regra: pelo menos **três janelas**
do mesmo modelo, tipo de ativo e horizonte; retorno finito e magnitude de até
**50%**. Uma confiabilidade positiva não libera por si só a projeção.

## Fórmula implementada

Para cada linha de performance com uma ou mais janelas:

```text
clip(x) = limitar x ao intervalo [0, 1]
cobertura = clip(Janelas_Validas / 5)
hit = clip((Hit_Rate_Top20 - 0,50) / 0,15)
ic = clip(Spearman_IC / 0,30)
alpha = clip(Alpha_vs_Score_Top / 0,03)

Confiabilidade_Pct = 100 × (0,40 × cobertura + 0,25 × hit
                           + 0,25 × ic + 0,10 × alpha)
```

Métricas ausentes contribuem zero. Para o baseline `Score Top`, o componente
alpha é fixado em `0,50`, pois comparar o baseline consigo mesmo não mede ganho
adicional. O resultado é arredondado a duas casas decimais.

Os níveis são `Não mensurável` sem janela mínima ou com pontuação zero,
`Baixa` abaixo de 40%, `Média` de 40% até menos de 70%, e `Alta` a partir de 70%.
O resumo global usa o maior score entre as linhas elegíveis, incluindo o
baseline; não é a média de todos os modelos.

## Horizontes e limites

O exporter declara 7d como principal e 30d como estratégico. Entretanto, o
pipeline principal treina em 30d e o Parquet de performance preserva o horizonte
avaliado. `build_ml_confidence_summary()` não filtra nem converte as linhas pelo
argumento `horizon_days`: esse argumento orienta a maturidade e o texto do resumo.
Confira `Horizonte` de cada linha e do modelo mais confiável. Detalhes em
[Pipeline ML](https://github.com/italostatonato/stock-screener-automation/wiki/Modelos-ML).

O bloqueio de projeções é definido em `src/exporter.py` por
`ML_MIN_VALID_WINDOWS = 3` e `ML_MAX_ABS_EXPECTED_RETURN = 0.50`. O valor bruto
é mantido para auditoria; `retorno_esperado_exibicao` recebe `null` quando a
regra não é atendida. O JSON informa `retorno_esperado_horizonte`,
`projecao_confiavel`, `projecao_outlier`, `janelas_validas_modelo`,
`min_janelas_validas_projecao` e `motivo_projecao`.

## Saída no JSON

`modelos_ml.confiabilidade` contém:

- `status`, `horizonte_dias` e `mensagem`;
- `maturidade_dados_pct` e `confiabilidade_preditiva_pct`;
- `nivel_confiabilidade` e `modelo_mais_confiavel`;
- `janelas_validas_max`, `min_janelas_validas` e `target_janelas_validas`;
- `primeiro_snapshot`, `ultimo_snapshot`, `dias_historico` e `qtd_snapshots`;
- `por_modelo`, com classe, modelo, horizonte, métricas e componentes da fórmula.

O resumo fica `Aquecendo` quando nenhuma linha atinge o mínimo e `Ativo` quando
há alguma elegível. Esses estados descrevem disponibilidade de cálculo, não
validação conclusiva da estratégia.
