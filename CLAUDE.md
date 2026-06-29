# Stock Screener Automation — Contexto para assistentes de IA

## O que é este projeto

Screener automático de FIIs e ações brasileiras.

O projeto coleta dados públicos, limpa e normaliza indicadores financeiros, calcula scores, aplica filtros adaptativos por quartis, gera Excel formatado, publica dashboard web via GitHub Pages e acumula histórico em Parquet para futuras etapas de Machine Learning.

**Dashboard:** https://italostatonato.github.io/stock-screener-automation/
**Repositório:** https://github.com/italostatonato/stock-screener-automation

Este projeto é educacional e analítico. Não tratar como recomendação de investimento.

---

## Estado atual do projeto

O projeto já possui:

- coleta diária de FIIs e ações;
- score multifatorial 0-100;
- filtros fixos e filtros móveis por quartis;
- Excel diário formatado;
- dashboard web estático;
- histórico ML em Parquet;
- carteira histórica para backtest;
- aba de recorrentes no dashboard;
- comparativos em base 100 contra benchmarks.

---

## Arquitetura — responsabilidades

```text
main.py                         Orquestra o pipeline completo
config.yaml                     Centraliza caminhos, filtros, fontes e colunas
requirements.txt                Dependências

src/
  scraper.py                    Selenium: Fundsexplorer + Investsite
  cleaner.py                    Normalização de percentuais, moedas e números
  filters.py                    Filtro fixo + quartil adaptativo
  scorer.py                     Score 0-100 por posição percentílica
  storage.py                    Históricos Excel e snapshots
  formatter.py                  Formatação do Excel com openpyxl
  market_data.py                BCB SGS + AwesomeAPI
  benchmark.py                  IBOV, IFIX, IMOB, CDI, IPCA via yfinance/BCB
  backtest.py                   Backtest inicial e carteira histórica
  ml_storage.py                 Append de histórico completo em Parquet
  dataset_builder.py            Feature engineering e targets futuros
  exporter.py                   JSON para o dashboard

docs/
  index.html                    Dashboard web sem framework
  data/index.json               Lista de snapshots disponíveis
  data/YYYY-MM-DD.json          Payload diário do dashboard

data/
  old/                          Excel histórico Top 20
  output/                       Excel diário final
  ml/                           Parquets de histórico e dataset
  backtest/                     Carteiras históricas
```

---

## Pipeline principal

1. Carrega `config.yaml`.
2. Configura logs.
3. Coleta FIIs.
4. Limpa FIIs.
5. Calcula score FIIs no universo completo.
6. Seleciona Top 20 FIIs.
7. Atualiza histórico Excel FIIs.
8. Salva universo FIIs em Parquet.
9. Coleta ações.
10. Calcula score ações no universo completo.
11. Seleciona Top 20 ações.
12. Atualiza histórico Excel ações.
13. Salva universo ações em Parquet.
14. Coleta indicadores e benchmarks.
15. Executa backtest inicial.
16. Salva Excel diário.
17. Formata Excel.
18. Exporta JSON para `docs/data/`.
19. Copia Excel para OneDrive local se configurado.

---

## Convenções críticas

### Encoding

Sempre usar:

```python
encoding="utf-8"
```

Evitar editar arquivos com acentuação no Bloco de Notas. Preferir VS Code ou scripts Python.

### Nomes de colunas

Não renomear colunas de entrada sem revisar todo o pipeline.

FIIs usam nomes como:

```text
FUNDOS
PREÇO ATUAL (R$)
DIVIDEND YIELD
P/VP
LIQUIDEZ DIÁRIA (R$)
```

Ações usam nomes como:

```text
Ação
Preço
Dividend Yield
Preço/VPA
ROA
Margem Líquida
```

A diferença vem das fontes originais.

### Configuração

Não hardcode caminhos, filtros ou URLs. Usar `config.yaml`.

Atenção: manter `config.yaml` limpo, sem chaves duplicadas. YAML com chaves repetidas pode funcionar “por sorte”, mas é perigoso.

---

## Histórico e segurança dos dados

A pasta `data/` contém histórico importante.

Não enviar pacotes que sobrescrevam `data/` sem autorização explícita.

Arquivos críticos:

```text
data/ml/historico_fiis.parquet
data/ml/historico_acoes.parquet
data/ml/dataset_fiis.parquet
data/ml/dataset_acoes.parquet
data/backtest/carteiras_historicas.parquet
```

Antes de qualquer mudança em histórico, recomendar backup:

```powershell
$Projeto = "C:\Users\Ítalo\OneDrive\stock-screener-automation"
$BackupRoot = Join-Path $Projeto "backups"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Backup = Join-Path $BackupRoot "data_backup_$Timestamp"
New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
Copy-Item -Path "$Projeto\data" -Destination $Backup -Recurse -Force
```

---

## Dashboard

O dashboard carrega sempre a data mais recente disponível em `docs/data/index.json`. Não há dropdown de data.

Abas atuais:

- Visão geral
- Ações
- FIIs
- Recorrentes
- Indicadores
- Info

Padrão visual:

- Ações: `#1F4E79`
- FIIs: `#7A869A`
- Fundo neutro escuro
- Positivo: verde
- Negativo: vermelho

Comparativos de performance devem ser sempre em **base 100**, nunca misturar carteira percentual com índice em pontos.

### Comparativos atuais

FIIs Top 20:

```text
Carteira FIIs vs IFIX vs IMOB vs CDI
```

Ações Top 20:

```text
Carteira Ações vs IBOV vs IPCA vs CDI
```

As linhas das carteiras começam somente quando existe histórico real em `data/backtest/carteiras_historicas.parquet`.

---

## Recorrentes

A aba Recorrentes usa `data/backtest/carteiras_historicas.parquet`.

Objetivo:

- listar todos os ativos que já apareceram no Top 20;
- mostrar quantidade de aparições;
- mostrar score médio;
- ordenar por aparições e score.

Não limitar automaticamente a 20 linhas, salvo se o usuário pedir.

---

## Machine Learning

Ainda não treinar modelos com pouco histórico.

A ordem correta é:

1. Acumular histórico diário.
2. Construir dataset com `dataset_builder.py`.
3. Monitorar maturidade dos targets.
4. Criar target de retorno futuro 7/30/60/90 dias.
5. Testar Random Forest.
6. Testar XGBoost.
7. Adicionar explicabilidade com SHAP.

O score atual deve ser mantido como feature do modelo, não removido.

---

## Fontes de dados

| Dado | Fonte | Método |
|---|---|---|
| FIIs | Fundsexplorer | Selenium |
| Ações BR | Investsite | Selenium + Excel |
| IPCA, Selic, IGP-M, CDI | BCB SGS | REST |
| Câmbio e BTC | AwesomeAPI | REST |
| IBOV, IFIX, IMOB | Yahoo Finance | yfinance |

---

## Armadilhas conhecidas

1. Fundsexplorer oculta colunas por padrão; scraper deve selecionar todas.
2. Investsite usa cabeçalho em linha específica do Excel.
3. Investsite pode trazer rodapé/legenda; precisa limpar antes de salvar Parquet.
4. `yfinance` pode retornar MultiIndex.
5. Alguns tickers de FIIs podem não existir no Yahoo.
6. GitHub Actions pode pausar cron após longo período sem atividade.
7. OneDrive local não existe no GitHub Actions; erros de cópia devem ser tratados.
8. Não comparar IBOV em pontos com carteira em percentual; usar base 100.
9. Evitar pacotes que contenham `data/` para não arriscar histórico.
10. Em fim de semana, rankings podem repetir por ausência de novos dados de mercado.

---

## Backlog recomendado

### Curto prazo

- Limpar e validar `config.yaml`.
- Integrar `dataset_builder.py` ao pipeline principal com segurança.
- Criar relatório de maturidade do dataset ML.
- Investigar por que algumas execuções locais podem gerar snapshots em fim de semana.
- Validar contagem de FIIs quando houver 21 itens no histórico.

### Médio prazo

- Backtest por janelas 7, 30, 60 e 90 dias.
- Criar métricas de turnover do Top 20.
- Criar evolução temporal dos recorrentes.
- Criar matriz de estabilidade do ranking.
- Primeiro modelo Random Forest.
- Modelo XGBoost.

### Longo prazo

- SHAP para explicabilidade.
- Score IA no dashboard.
- Backtesting mais robusto com custos e rebalanceamento.
- Open Graph tags.
- Domínio próprio ou encurtador.

---

## Como rodar

```bash
pip install -r requirements.txt
python main.py
```

## Testes

```bash
pytest tests/ -v
```

## Dataset ML

```bash
python -m src.dataset_builder
```

## Dashboard local

```bash
python -m http.server 8000
```

Abrir:

```text
http://localhost:8000/docs/
```
