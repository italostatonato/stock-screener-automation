# Confiabilidade dos modelos ML

O dashboard passa a separar dois conceitos:

1. **Maturidade dos dados**: percentual do caminho até o horizonte principal de 30 dias, calculado a partir dos snapshots disponíveis.
2. **Confiabilidade preditiva real**: percentual conservador baseado em performance validada. Fica em 0% até existirem janelas válidas suficientes.

## Fórmula da confiabilidade real

Enquanto `Janelas_Validas < 5`, a confiabilidade preditiva fica em `0%`.

Depois disso, a pontuação usa:

- 40% cobertura histórica
- 25% hit rate do Top 20
- 25% Spearman IC
- 10% alpha contra o Score Top

Escalas usadas:

- Hit rate: 50% = neutro; 65% = forte
- Spearman IC: 0 = sem ordenação; 0,30 = forte para ranking financeiro
- Alpha: 0 p.p. = neutro; 3 p.p. = forte no horizonte medido

## Saída no JSON

A chave `modelos_ml.confiabilidade` contém:

- `maturidade_dados_pct`
- `confiabilidade_preditiva_pct`
- `nivel_confiabilidade`
- `modelo_mais_confiavel`
- `janelas_validas_max`
- `min_janelas_validas`
- `mensagem`
- `por_modelo`

Essa camada não altera o ranking oficial. Ela apenas prepara o projeto para avaliar, no futuro, quando um modelo supervisionado estiver maduro o bastante para competir com o Score Top.
