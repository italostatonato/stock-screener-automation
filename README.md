# Radar Semanal

[![Radar Semanal](https://img.shields.io/badge/Radar%20Semanal-online-E3BE72)](https://italostatonato.github.io/stock-screener-automation/)
[![Python](https://img.shields.io/badge/python-3.11+-3776AB)](https://www.python.org/)
[![GitHub Actions](https://img.shields.io/badge/automation-GitHub%20Actions-24292F)](https://github.com/italostatonato/stock-screener-automation/actions)

Boletim quantitativo semanal de **FIIs** e **ações brasileiras**, com coleta de dados públicos, score multifatorial, histórico, backtest e dashboard web no GitHub Pages.

**[Dashboard ao vivo](https://italostatonato.github.io/stock-screener-automation/)** · **[Wiki](https://github.com/italostatonato/stock-screener-automation/wiki)**

Documentação revisada em **07/09/2026** contra o código e a configuração versionados.

> Projeto educacional e analítico. Não constitui recomendação de investimento.

---

## Visão geral

O projeto roda automaticamente uma vez por semana e gera um ranking quantitativo dos ativos mais bem posicionados dentro do universo coletado.

O fluxo atual combina:

- coleta semanal de FIIs no Fundsexplorer;
- coleta semanal de ações na tabela pública do Fundamentus;
- limpeza de números, percentuais e moedas no formato brasileiro;
- score de 0 a 100 calculado no universo completo;
- pisos de elegibilidade, seguidos de ordenação pelo score de sete fatores com pesos iguais;
- Top 20 FIIs e Top 20 ações;
- Excel semanal formatado;
- dashboard web com rankings, recorrência, indicadores, backtests, carteira híbrida e modelos ML;
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
  config.py                     Carrega config.yaml com caminhos portáveis
  scraper.py                    Coleta FIIs via Selenium e ações por tabela pública
  cleaner.py                    Limpeza e normalização de dados financeiros
  filters.py                    Elegibilidade e seleção pelo score já calculado
  scorer.py                     Score multifatorial 0-100
  storage.py                    Histórico Excel e snapshots
  formatter.py                  Formatação do Excel final
  market_data.py                IPCA, Selic, IGP-M, câmbio e cripto
  benchmark.py                  IBOV, IFIX, IMOB, CDI e séries de mercado
  backtest.py                   Backtest e carteira histórica Top 20
  backtest_engine.py            Backtest auditável com calendário, custos e cobertura
  observed_history.py           Recupera carteiras realmente publicadas
  point_in_time.py              Backfill mensal sem look-ahead com CVM + B3
  ml_storage.py                 Append dos históricos consolidados em Parquet
  dataset_builder.py            Feature engineering e targets futuros
  ml_models.py                  Modelos ML em modo sombra
  ml_confidence.py              Maturidade, confiabilidade e janelas válidas
  data_lake.py                  Camada incremental, manifesto e qualidade
  delivery.py                   Entrega opcional do Excel e log de auditoria
  exporter.py                   JSON do dashboard

docs/
  index.html                    Dashboard web estático
  data/index.json               Índice de snapshots do dashboard
  data/YYYY-MM-DD.json          Payload por data de execução (America/Sao_Paulo)
  ARCHITECTURE.md               Arquitetura técnica
  ML_PIPELINE.md                Pipeline de Machine Learning
  ML_CONFIDENCE.md              Fórmula de confiabilidade e limites de exibição
  METHODOLOGY.md                Score, elegibilidade e fontes de dados
  DASHBOARD.md                  Telas, carteira híbrida e simulador
  BACKTEST_RETROATIVO.md        Histórico observado e simulações point-in-time
  OPERATIONS.md                 Operação, validação e troubleshooting
  DOCUMENTATION.md              Revisão e publicação da documentação e da wiki
  wiki/                         Cópia versionada das páginas da wiki

data/
  old/                          Históricos Excel Top 20
  output/                       Excel final por execução
  delivery/                     Log das entregas locais
  ml/                           Históricos, datasets e previsões ML
  backtest/                     Carteiras históricas
  point_in_time/                Rankings retroativos sintéticos, isolados do observado
  lake/                         Fonte incremental oficial
    manifest.json               Manifesto global do lake
    quality_report.json         Último relatório de qualidade
    snapshots/YYYY-MM-DD/       Snapshot por data de execução

scripts/
  healthcheck_data.py           Validação de dados, duplicatas e dashboard
  rebuild_from_lake.py          Reconstrução de derivados a partir do lake
  build_observed_history.py     Consolida o histórico realmente observado
  build_point_in_time_history.py Backfill mensal de FIIs desde 2021
  run_observed_backtest.py      Backtest das carteiras publicadas
  run_point_in_time_backtest.py Backtest do histórico sintético point-in-time

tests/                          Testes automatizados
.github/workflows/
  run_screener.yml              Automação semanal via GitHub Actions
```

---

## Pipeline semanal

1. Carrega `config.yaml` e configura logs.
2. Coleta FIIs ou usa arquivo local quando configurado.
3. Limpa e normaliza FIIs.
4. Calcula score FIIs no universo completo.
5. Aplica pisos de elegibilidade e ordena pelo score de sete fatores iguais.
6. Atualiza histórico Excel do Top 20 FIIs.
7. Salva universo FIIs em `data/ml/historico_fiis.parquet`.
8. Coleta ações na tabela pública do Fundamentus.
9. Calcula score ações no universo completo.
10. Aplica pisos de elegibilidade e ordena pelo score de sete fatores iguais.
11. Atualiza histórico Excel do Top 20 ações.
12. Salva universo ações em `data/ml/historico_acoes.parquet`.
13. Coleta indicadores de mercado e benchmarks.
14. Atualiza carteira histórica em `data/backtest/carteiras_historicas.parquet`.
15. Salva snapshot incremental em `data/lake/snapshots/YYYY-MM-DD/`.
16. Reconstrói os históricos consolidados e a carteira a partir do lake.
17. Gera datasets com targets de 7, 30, 60 e 90 dias e executa os modelos ML em modo sombra.
18. Gera snapshot Excel em `data/output/`.
19. Exporta JSON da execução em `docs/data/YYYY-MM-DD.json`.
20. Reconstrói `docs/data/index.json` com snapshots existentes.
21. Executa checagens de qualidade.
22. Copia o Excel para OneDrive local quando configurado.

O score é calculado no universo completo **antes** dos filtros. Cada classe usa
sete indicadores com peso `1/7`; dados ausentes recebem percentil neutro 50.
A seleção aplica os pisos de `config.yaml`, ordena por score decrescente e
desempata pelo ticker. Ações também são deduplicadas por empresa. Os limites
de DY, liquidez e patrimônio/valor de mercado são estritos (`>`); pode haver
menos de 20 aprovados. Veja a [metodologia completa](docs/METHODOLOGY.md).

---

## Dashboard

O dashboard web é publicado via GitHub Pages e carrega sempre o snapshot mais recente listado em `docs/data/index.json`.

Principais telas:

- **Visão geral**: KPIs comparativos, score, resumo Top 20 e comparativos em base 100.
- **Carteira Híbrida**: percentuais editáveis de 1% em 1% para Top 20 Ações BR, Top 20 FIIs, CDI e IVVB11. Ao aumentar um bloco, cada ponto sai do maior dos outros blocos; ao reduzir, a diferença vai para o maior dos demais. Empates seguem a ordem dos blocos na tela. O total permanece em 100%. Cinco perfis de simulação (na mesma ordem dos blocos): Agressivo 45/20/5/30, Meio-Agressivo 40/25/10/25, Balanceado 30/30/20/20, Conservador 15/20/55/10 e Muito conservador 5/10/80/5. O Balanceado preserva a configuração original. Gráfico, contribuições e pesos por ativo acompanham a seleção, com rebalanceamento a cada nova composição semanal. O simulador inicia com R$ 10.000,00 e exibe as compras em listas abertas abaixo do card de cada bloco, na mesma coluna. Usa os preços do snapshot selecionado e o último fechamento disponível de IVVB11 até essa data, calcula unidades inteiras, destino ao CDI, percentuais efetivos e saldo não aplicado, sem redistribuir sobras. O desempenho histórico continua teórico, sem arredondamento de quantidades. Valores sem cotação ou composição ficam no saldo.
- **Ações**: ranking de ações com preço, score e principais indicadores.
- **FIIs**: ranking de FIIs com preço, score, DY, P/VP, liquidez e setor.
- **Recorrentes**: ativos que mais apareceram no Top 20 histórico, com indicadores atuais.
- **Modelos ML**: comparação entre score atual e modelos preditivos em modo sombra.
- **Indicadores**: mercado, macro, câmbio, cripto e benchmarks.
- **Score e Info**: metodologia, premissas, fontes e limitações.

Os gráficos com eixo de tempo abrem em **90D**, com seleção manual dos outros períodos. Na Carteira Híbrida, o aporte mínimo é **R$ 1.000,00**; uma barra colorida representa os quatro blocos, as compras usam linhas compactas com detalhes ao passar o mouse ou focar pelo teclado, e a tabela mostra o ganho/perda estimado em reais a partir do aporte e das contribuições históricas, além do saldo teórico total.

O campo de aporte usa a máscara numérica [IMask](https://imask.js.org/guide.html#masked-number) 7.6.1, distribuída localmente em `docs/assets/vendor/` com licença MIT. Os separadores de milhar se ajustam durante a edição, preservando o cursor; os centavos são completados ao sair do campo. A validação do mínimo é separada da máscara para permitir apagar e redigitar o valor.

As séries Top 20 da carteira híbrida usam preços dos snapshots, sem reinvestimento
de proventos, custos ou impostos. O benchmark rotulado IFIX usa o ETF **XFIX11**
como proxy. Essas curvas têm premissas diferentes dos scripts de backtest com
preços ajustados e custos. Consulte o [guia do dashboard](docs/DASHBOARD.md).

Cores principais:

- Ações: `#54C7FF`
- FIIs: `#B6C0D2`
- Positivo: verde
- Negativo: vermelho
- Fundo: escuro neutro

---

## Camada de dados

O projeto organiza os dados nas seguintes camadas:

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

### 4. Histórico retroativo e backtests auditáveis

O projeto mantém duas naturezas de dado sem misturá-las:

- `OBSERVADO`: carteira que foi efetivamente publicada na data registrada;
- `SIMULADO_POINT_IN_TIME`: ranking reconstruído depois, usando apenas informação que já estava pública na data do sinal.

Para reconstruir e testar:

```powershell
python scripts/build_observed_history.py
python scripts/run_observed_backtest.py
python scripts/build_point_in_time_history.py --start 2021-01-01
python scripts/run_point_in_time_backtest.py
```

O motor entra no pregão seguinte ao sinal, usa preços ajustados, equal weight,
10 bps de custo por turnover por padrão e audita ativos sem preço. Veja
[Histórico retroativo e backtest](docs/BACKTEST_RETROATIVO.md) para premissas,
saídas e limitações. Esses scripts são executados separadamente; o workflow
semanal não reconstrói automaticamente o histórico point-in-time.

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

O dashboard declara 7d como horizonte principal e 30d como estratégico, mas
`main.py` e `scripts/rebuild_from_lake.py` passam explicitamente `horizon=30`
ao treinamento. O padrão da função `run_ml_pipeline()` é 7. Portanto, confira
o campo `Horizonte` de cada métrica e `retorno_esperado_horizonte` de cada ativo;
o rótulo principal da tela não converte métricas de 30d em 7d.

A confiabilidade começa com **1 janela válida** e usa **5 janelas** como meta
de cobertura. Exibir uma projeção de retorno exige **3 janelas** do mesmo
modelo, classe e horizonte, além de magnitude de no máximo **50%**. Sem dados
suficientes, o ranking sombra pode continuar disponível com projeção oculta.
Detalhes em [Pipeline ML](docs/ML_PIPELINE.md) e
[Confiabilidade ML](docs/ML_CONFIDENCE.md).

---

## Automação

O workflow `.github/workflows/run_screener.yml`:

- roda uma vez por semana, às segundas-feiras;
- usa cron `0 11 * * 1`, equivalente a **08h BRT**;
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
  - `data/delivery/`
- usa `concurrency` para evitar execuções simultâneas;
- publica o GitHub Pages após os testes, inclusive quando uma fonte pública
  falhar temporariamente; quando a coleta conclui, o deploy usa o snapshot
  novo gerado pela própria execução;
- notifica falha via Telegram quando os secrets estão configurados.

O workflow tem os jobs `test`, `screener` e `deploy`, com Python 3.11 e Chrome
no runner de coleta. Os artefatos ficam retidos por 90 dias. Não há gatilho de
push: uma atualização apenas documental não inicia o screener nem um novo
deploy por si só.

A revisão semanal de documentação é uma tarefa separada, solicitada para
**segunda-feira às 12h, America/Sao_Paulo**. Seu procedimento está em
[Manutenção da documentação](docs/DOCUMENTATION.md).

---

## Setup local

Use Python 3.11 ou superior, Git e Google Chrome instalado para a coleta de
FIIs. Node.js é usado pelo teste JavaScript do simulador; o dashboard publicado
é estático e não exige Node para servir os arquivos.

```bash
git clone https://github.com/italostatonato/stock-screener-automation.git
cd stock-screener-automation
python -m venv .venv
```

### Windows

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

### Linux/macOS

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

### Destino local opcional do Excel

O `config.yaml` é versionado e não contém caminho de máquina de ninguém. Para
copiar o Excel final para uma pasta sincronizada (OneDrive, Dropbox, rede),
defina a variável de ambiente antes de rodar:

```powershell
$env:SCREENER_EXCEL_OUTPUT_DIR = "C:/Users/<voce>/OneDrive/Tabelas Acoes/Recomendacoes"
```

```bash
export SCREENER_EXCEL_OUTPUT_DIR="$HOME/OneDrive/Tabelas Acoes/Recomendacoes"
```

Sem a variável, a cópia local é pulada e o Excel continua em `data/output/`.

### Fonte de ações sem custo

Por padrão, as ações são coletadas da tabela pública do
[Fundamentus](https://www.fundamentus.com.br/resultado.php), em **uma requisição
por tentativa**, sem conta ou token. A configuração permite duas novas
tentativas após falha. Ela fornece cotação,
múltiplos, margens, ROIC/ROE, liquidez de dois meses, patrimônio, dívida
líquida e crescimento de receita.

O projeto calcula o ROA por `P/Ativo ÷ P/L` e o valor de mercado por
`P/VP × Patrimônio Líquido`. A coluna legada
`Passivo/Patrimônio Líquido` passa a receber `Dívida Líquida/Patrimônio`, que
é o indicador efetivamente disponibilizado pela fonte; ela não participa do
score atual. Não é necessário configurar `BRAPI_TOKEN` nem mantê-lo nos
Secrets do GitHub para a execução padrão.

A coluna legada `Volume Diário Médio (3 meses)` recebe `Liq.2meses` do
Fundamentus; a janela da fonte padrão é de **dois meses**. `RPL` corresponde
a ROE e `ROInvC` a ROIC. A coleta complementar de nomes ainda pode consultar
a listagem pública da brapi e a busca do Yahoo, sem trocar a fonte dos fundamentos.

A brapi continua disponível apenas como alternativa opcional: defina
`acoes_source: "brapi"` no `config.yaml` e forneça `BRAPI_TOKEN` com acesso
aos fundamentos exigidos pelo coletor. O código dessa alternativa foi escrito
para o plano Pro; ela não integra a execução padrão sem credenciais.

---

## Validação local

Rodar testes:

```bash
python -m pytest tests/ -v
```

Rodar healthcheck:

```bash
python scripts/healthcheck_data.py
```

O healthcheck atualiza o manifesto do lake, o índice do dashboard e o relatório
de qualidade. `error` encerra com código 1; `ok` e `warn`, com 0. Para revisar
somente documentação, execute-o numa cópia temporária dos dados. Consulte
[Operação](docs/OPERATIONS.md) antes de rodar comandos que reconstroem derivados.

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

## Limitações e próximos passos

- Alinhar a chamada de treino em 30d com o horizonte principal de 7d do dashboard;
  separar treino e previsão ainda é uma evolução futura.
- Validar modelos em mais janelas e definir um critério de promoção. O campo
  `modelo_lider` atual não substitui automaticamente o ranking oficial.
- Completar a base histórica auditável de ações; o backfill point-in-time
  disponível hoje cobre FIIs e tem limitações de cobertura e de indicadores.
- Melhorar cobertura de preços de ativos renomeados/extintos e manter explícita
  a diferença entre retorno de preço, retorno ajustado e simulação de aporte.
- Avaliar particionamento ou armazenamento externo se os binários versionados
  crescerem demais.
- A entrega remota por Microsoft Graph permanece futura; hoje a cópia do Excel
  depende de uma pasta local sincronizada.

---

## Uso e licenciamento

Projeto pessoal para estudo, portfólio e análise quantitativa. O repositório
não contém um arquivo de licença geral. A licença MIT da dependência IMask
está em `docs/assets/vendor/imask-LICENSE.txt` e se aplica a essa dependência.
Uso por terceiros deve considerar as limitações das fontes e as premissas
metodológicas documentadas.
