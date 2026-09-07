# Radar Semanal

Boletim quantitativo semanal de ações e FIIs brasileiros, com dados públicos,
score multifatorial, Excel, dashboard, histórico, backtests e ML em modo sombra.

**Revisado em 07/09/2026.** A documentação descreve o código atual; snapshots
históricos podem refletir regras anteriores. Projeto educacional e analítico,
não uma recomendação de investimento.

## Funcionamento atual

- FIIs via Fundsexplorer/Selenium ou Excel local; ações via Fundamentus/HTTP.
- Score no universo completo, com sete fatores de peso 1/7 por classe.
- Pisos de elegibilidade, ordenação por score/ticker e até 20 ativos.
  Ações são deduplicadas por empresa. Não há seleção por quartis.
- Dashboard com carteira híbrida configurável, cinco perfis e simulador de aporte.
- Lake observado, históricos Parquet, Excel local e JSON por data de execução.
- Pesquisa point-in-time de FIIs em uma camada separada.
- ML em modo sombra: mínimo de uma janela para confiança, meta de cinco e
  três janelas para liberar projeções dentro dos limites de exibição.

O screener roda segunda-feira às **08h de São Paulo** ou por acionamento manual.
A revisão documental semanal foi solicitada para **segunda-feira às 12h** no
mesmo fuso e é administrada separadamente no Codex.

Resultados no [dashboard](https://italostatonato.github.io/stock-screener-automation/)
e nos artefatos do [workflow](https://github.com/italostatonato/stock-screener-automation/actions/workflows/run_screener.yml).
A entrega local de Excel depende de `SCREENER_EXCEL_OUTPUT_DIR`.

## Guias

- [Como funciona](https://github.com/italostatonato/stock-screener-automation/wiki/Como-Funciona)
- [Dashboard](https://github.com/italostatonato/stock-screener-automation/wiki/Dashboard)
- [Metodologia de filtros e score](https://github.com/italostatonato/stock-screener-automation/wiki/Metodologia-de-Filtros)
- [Modelos ML](https://github.com/italostatonato/stock-screener-automation/wiki/Modelos-ML)
- [Confiabilidade ML](https://github.com/italostatonato/stock-screener-automation/wiki/Confiabilidade-ML)
- [Backtests](https://github.com/italostatonato/stock-screener-automation/wiki/Backtests)
- [Configuração (config.yaml)](https://github.com/italostatonato/stock-screener-automation/wiki/Configura%C3%A7%C3%A3o-%28config.yaml%29)
- [Fontes de dados](https://github.com/italostatonato/stock-screener-automation/wiki/Fontes-de-Dados)
- [Como rodar localmente](https://github.com/italostatonato/stock-screener-automation/wiki/Como-Rodar-Localmente)
- [Troubleshooting](https://github.com/italostatonato/stock-screener-automation/wiki/Troubleshooting)
- [Manutenção da documentação](https://github.com/italostatonato/stock-screener-automation/wiki/Manutencao-da-Documentacao)

A cópia versionada destas páginas fica em
[docs/wiki](https://github.com/italostatonato/stock-screener-automation/tree/main/docs/wiki).
A revisão e a publicação nos dois repositórios são descritas no guia de manutenção.
