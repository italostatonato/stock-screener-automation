# Radar Semanal — Contexto para assistentes de IA

Revisado em 12/10/2026 contra a implementação da `main` (`99f34f9`).
Consulte [o procedimento de revisão](docs/DOCUMENTATION.md).

## Projeto e documentação

Screener semanal de FIIs e ações brasileiras com score, Top 20, Excel,
dashboard, lake incremental, backtests e ML em modo sombra.

Coleta agendada: segunda-feira, 10h de Brasília. Revisão documental: segunda,
12h, em tarefa separada. Snapshots são por data de execução, inclusive manual.
Liquidez diária, CDI diário, variações em 24h e horizontes ML em dias não
significam que os rankings sejam atualizados diariamente. Revise também textos
da interface, docstrings e descrições exportadas ao conferir a cadência.

- [Site Radar Semanal](https://radar-semanal-italo.italo-st.chatgpt.site/)
- [Dashboard no GitHub Pages](https://italostatonato.github.io/stock-screener-automation/)
- [Repositório](https://github.com/italostatonato/stock-screener-automation)
- [Wiki](https://github.com/italostatonato/stock-screener-automation/wiki)

Projeto educacional e analítico, não uma recomendação de investimento.
O [README](README.md) orienta o setup. Consulte os guias de
[arquitetura](docs/ARCHITECTURE.md), [metodologia](docs/METHODOLOGY.md),
[dashboard](docs/DASHBOARD.md), [ML](docs/ML_PIPELINE.md),
[confiabilidade](docs/ML_CONFIDENCE.md), [backtests](docs/BACKTEST_RETROATIVO.md)
e [operação](docs/OPERATIONS.md). A wiki também tem cópia em `docs/wiki/`.

O [site no Sites](docs/SITE.md), verificado em 05/10/2026, é uma publicação
separada e pública cujo servidor espelha o HTML, os dados e os recursos do
GitHub Pages, com cópia incluída para contingência. A aba visível verifica a
versão a cada 60 segundos e pode recarregar, aguardando a edição de campos.
Isso não muda o cron da coleta. O rodapé conta navegadores únicos desde
29/09/2026, com cookie e persistência no servidor. Worker, contador, adaptações
próprias e cópia de contingência são mantidos e publicados no projeto do Sites;
um clone deste repositório não inclui esse código. O HTML original atualizado
no Pages chega pelo espelhamento sem nova publicação no Sites.

## Princípios

1. **Preservar histórico.** Faça backup antes de alterar/reprocessar `data/`.
   Preserve também `docs/data/` se for reescrever snapshots.
2. **Lake como fonte oficial observada.** Históricos consolidados são derivados;
   dados sintéticos point-in-time ficam separados.
3. **Dashboard leve.** Exporte JSONs prontos para apresentação; o navegador
   pode calcular alocações e simulações a partir deles.
4. **ML em modo sombra.** Modelos não substituem o ranking oficial.
5. **Operação padrão gratuita.** Não introduza APIs, serviços ou cloud pagos.
6. **Testar antes de publicar.** Rode `python -m pytest tests/ -v` e o
   healthcheck. Em inspeções, use `python scripts/healthcheck_data.py --read-only`
   para preservar manifesto, índice e relatório.

## Regras implementadas

- FIIs: Fundsexplorer via Selenium/Chrome, ou Excel local quando presente.
- Ações: tabela HTTP do Fundamentus; brapi/investsite são alternativas.
  Até cinco tentativas em falhas transitórias, com pausas de 30/60/120/120s,
  conexão limitada a 10s e resposta a 30s. HTTP 403/404 e TLS inválido não repetem.
- Score no universo completo, antes da seleção: sete fatores por classe,
  peso `1/7`, percentis invertidos para menor-é-melhor e nota neutra 50
  para dado ausente.
- Pisos de elegibilidade com limites estritos `>`, ordem por score e ticker,
  até 20 selecionados. Ações são deduplicadas por empresa.
- Não há filtro de quartis nem fallback automático para completar Top 20.
- `Volume Diário Médio (3 meses)` recebe a liquidez de dois meses do
  Fundamentus; `RPL` é ROE e `ROInvC` é ROIC.
- IFIX é representado pela proxy XFIX11.
- A data oficial dos snapshots e logs usa `America/Sao_Paulo`.

A carteira híbrida possui quatro blocos, cinco perfis, pesos editáveis com
total de 100% e simulação de compras em unidades inteiras. Aporte padrão
R$ 10.000 e mínimo R$ 1.000. Os gráficos temporais iniciam em 3M.
O histórico teórico usa pesos fracionários; as séries Top 20 não reinvestem
proventos e a simulação híbrida não inclui custos/impostos.

A coleta BCB de indicadores e benchmarks tenta até três vezes em falhas
temporárias, com pausas de 1s e 2s.
Sem histórico dos quatro componentes, a híbrida informa a indisponibilidade
e não plota um retorno fictício. Reparos de benchmark preservam os rankings
e os demais campos do snapshot, com backup anterior fora do Git.

O dashboard tem seis abas principais: Introdução, Visão geral, Carteira Híbrida,
Modelos ML, Top 20 e Indicadores. A aba Top 20 reúne Ações, FIIs e
Recorrentes num seletor. Ele abre em Introdução, com conteúdo estático para
iniciantes, exemplos fictícios, glossário expansível e atalhos para as demais abas.
A Introdução também reúne score, fontes e informações do projeto, com exemplo
numérico dos sete percentis e a média final, além de elegibilidade e histograma.
A tabela de DY mostra 10 valores ordenados: DY de 9% na 8ª posição vale 80;
em outro grupo, o mesmo DY na 5ª posição vale 50. Sem empates, o menor DY
recebe 100/N pontos e o maior recebe 100; os pesos e o algoritmo são preservados.
A explicação não depende dos snapshots; o histograma usa os dados carregados.
Ao explicar indicadores,
diferencie referências de produtos, preço de proventos e histórico de previsão.

Os períodos são 1M, 3M, 6M, 12M, 18M, 24M e Tudo, com a última observação de
cada semana e sem criar dados ausentes. O cálculo híbrido conserva os intervalos
intermediários. Baixar CSV está disponível em tabelas, gráficos e na distribuição
da carteira: esta última exporta perfil, componente e alocação em percentuais.

## Pipeline e dados

`main.py`: configuração → FIIs → ações → indicadores/benchmarks → carteira
histórica → lake → reconstrução de consolidados → datasets/ML → Excel/JSON
→ qualidade → entrega opcional.

Top vazio ou falha de ações interrompe antes das escritas de histórico.
Falhas de lake, reconstrução, exportação ou qualidade com `error` interrompem
a execução. Indicadores, ML e entrega opcional possuem tratamento por log.
O ranking Excel substitui a composição completa de cada data recebida.

```text
data/lake/snapshots/YYYY-MM-DD/       fonte oficial observada por data
data/ml/                            históricos, datasets, previsões e performance
data/backtest/                      carteira, preços e backtests observados
data/point_in_time/                  pesquisa sintética isolada
data/old/ e data/output/             Excel local, ignorado pelo Git
data/delivery/                      auditoria da entrega
docs/data/                          payloads e índice do dashboard
```

Chaves sem nulos/duplicatas:

- FIIs: `Data_Execucao` + `FUNDOS`.
- Ações: `Data_Execucao` + `Ação`.
- Carteiras: `Data_Carteira` + `Tipo` + `Ticker`.

O esquema da carteira inclui `Preco_Entrada`, `Score` e `Posicao`.
Preserve a grafia `Ação`; variantes são compatibilidade de leitura.
Novas execuções precisam dos tipos FII e ACAO. Exceções históricas conhecidas
são registradas em `data/lake/known_incomplete_snapshots.json`.

## ML: horizontes e limites

Datasets possuem targets de 7, 30, 60 e 90 dias corridos.
`run_ml_pipeline()`, `main.py` e o rebuild usam 7d. Targets de treino precisam
estar realizados até a data prevista. Previsões preservam seu `Horizonte`.
O exporter declara principal 7d, estratégico 30d e histórico realizado de 7d;
a performance agregada mantém seu próprio `Horizonte`.
Não apresente métricas de horizontes diferentes como equivalentes.

Modelos: Score Top, Ridge, Random Forest, Extra Trees, XGBoost, LightGBM,
CatBoost e Ensemble. O mínimo de treino é 20 linhas e uma data anterior.

Confiabilidade: mínimo de uma janela, meta de cinco. Projeção visível:
três janelas do mesmo modelo/classe/horizonte e magnitude de até 50%.
`modelo_lider` por ativo não é promoção automática do modelo à estratégia.

## Workflow e manutenção

`Weekly FII Screener` roda segunda-feira às 10h BRT (`0 13 * * 1`) ou
manualmente. Jobs: testes → screener → deploy; a publicação da coleta exige
testes e screener bem-sucedidos. Pushes de interface continuam publicando após
os testes, com screener ignorado. Publica `docs/`. Artefatos de saída são retidos por 90 dias;
diagnósticos de falha, por 30 dias. Commita
`docs/data/`, `data/lake/`, `data/ml/`, `data/backtest/` e `data/delivery/`.
`tests.yml` valida pushes de código/documentação e pull requests, sem coleta
ou deploy. Os testes usam Python e Node 24.
Pushes da `main` que alteram `docs/index.html`, `docs/assets/` ou
`.github/workflows/run_screener.yml` acionam o próprio `run_screener.yml`: testes → deploy,
com `screener` ignorado. A coleta semanal e a execução manual mantêm os três jobs.
A Visão geral mostra até 20 ativos por classe em cartões uniformes com posição,
ticker e score, sem preço. O gráfico de desempenho permite Ações, FIIs ou
Ações + FIIs (50/50), com CDI, IFIX e IBOV como referências.

A revisão documental é uma automação separada do Codex, solicitada para
segunda-feira às 12h em São Paulo. Procedimento em
[Manutenção da documentação](docs/DOCUMENTATION.md).

Ao alterar comportamento, atualize README, este contexto, guias e wiki.
Mudanças visuais normalmente envolvem `docs/index.html` e, quando preciso,
`src/exporter.py`; inclua testes ou assets somente quando a mudança exigir.
Não adicione caminhos pessoais a `config.yaml`, não commite backups e
preserve trabalhos locais de outras tarefas. Publicar `docs/wiki/` no projeto
não publica a wiki: ela tem repositório Git separado.
