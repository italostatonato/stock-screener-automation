# Stock Screener Automation — Contexto para Claude Code

## O que é esse projeto

Screener automático de FIIs (Fundos Imobiliários) e Ações brasileiras.
Roda diariamente via GitHub Actions às 08h BRT, coleta dados via Selenium,
aplica filtros adaptativos por quartis, gera Excel formatado e publica
um dashboard web via GitHub Pages.

**Dashboard ao vivo:** https://italostatonato.github.io/stock-screener-automation/
**Repositório:** https://github.com/italostatonato/stock-screener-automation

---

## Arquitetura — mapa de responsabilidades

```
main.py                  Orquestra o pipeline completo
src/
  scraper.py             Coleta via Selenium (Fundsexplorer FIIs + Investsite Ações)
  cleaner.py             Normaliza tipos: percentuais, monetários, inteiros, floats
  filters.py             Filtro em duas camadas: fixo + quartil adaptativo
  scorer.py              Score composto 0-100 por posição percentílica
  storage.py             Salva histórico e snapshot Excel
  formatter.py           Formatação visual do Excel (openpyxl)
  market_data.py         Indicadores de mercado: BCB SGS + AwesomeAPI
  benchmark.py           Benchmarks: IBOV, IFIX, IMOB, CDI via yfinance + BCB
  exporter.py            Exporta JSON para o dashboard web (docs/data/)
docs/
  index.html             Dashboard web (HTML+JS, sem framework)
  data/
    index.json           Lista de datas disponíveis
    YYYY-MM-DD.json      Payload completo de cada dia
config.yaml              TODOS os parâmetros editáveis (filtros, paths, urls)
tests/
  test_cleaner.py        Testes do cleaner (parsing de formatos BR)
  test_filters.py        Testes dos filtros com dados sintéticos
.github/workflows/
  run_screener.yml       GitHub Actions: test → screener → artefato → commit docs/data
```

---

## Pipeline de execução (main.py)

1. Coleta FIIs via Selenium (Fundsexplorer) ou arquivo local
2. Limpa e normaliza os dados (cleaner.py)
3. Calcula score FII no universo completo (scorer.py)
4. Aplica filtros (filters.py) → retorna (top_fiis, fii_base_completa)
5. Coleta Ações via Selenium + download Excel (Investsite)
6. Calcula score Ações no universo completo
7. Aplica filtros Ações → retorna (top_acoes, acoes_base_completa)
8. Coleta indicadores de mercado (market_data.py)
9. Coleta benchmarks IBOV/IFIX/IMOB/CDI (benchmark.py)
10. Salva histórico Excel (storage.py)
11. Gera snapshot Excel formatado (formatter.py)
12. Exporta JSON do dashboard (exporter.py) → docs/data/YYYY-MM-DD.json
13. Copia Excel para OneDrive local (se configurado)

---

## Configuração central (config.yaml)

Nunca hardcode paths, filtros ou URLs no código — tudo vai em config.yaml.

Seções:
- `paths`: base_dir, data_dir, input/output/old/logs, onedrive_output_dir
- `scraper`: urls de coleta, timeouts, cookie button id, download_dir
- `filters`: filtros fixos FII (dy_min, liquidez_min, patrimonio_min, top_n)
  - `filters.acoes`: filtros fixos Ações (dy_min, volume_min, market_cap_min, top_n)
- `columns`: mapeamento de colunas por tipo (percent, money, integer, float_simple)

---

## Convenções críticas

### Encoding
- **SEMPRE** usar `encoding="utf-8"` ao abrir/salvar arquivos
- **NUNCA** usar Notepad para editar arquivos com acentuação (corrompe encoding)
- Usar VS Code ou gerar arquivos via script Python com encoding explícito

### Nomes de colunas
- FIIs: MAIÚSCULAS com acentuação (ex: `"DIVIDEND YIELD"`, `"LIQUIDEZ DIÁRIA (R$)"`)
- Ações: capitalização mista (ex: `"Dividend Yield"`, `"Preço/VPA"`)
- Isso reflete o que o site retorna — não normalizar para evitar bugs silenciosos

### Filtros (filters.py)
- `select_top_fiis(df, cfg)` e `select_top_acoes(df, cfg)` recebem o **cfg completo** (não cfg["filters"])
- Ambas retornam uma TUPLA: (top_df, base_completa_com_status)
- Os quartis são recalculados a cada execução — não há parâmetros fixos para Q25/Q75

### Scores (scorer.py)
- Score calculado no universo COMPLETO antes do filtro, não só nos aprovados
- Isso garante que o percentil reflita a posição real no mercado

### Dashboard JSON
- Valor absoluto nos gráficos — nunca variação percentual
- Tendências: comparação com JSON do dia anterior via index.json
- Benchmarks em valor absoluto (IBOV em pontos, CDI base 100, câmbio em R$)

---

## Fontes de dados

| Dado | Fonte | Método | Chave necessária |
|---|---|---|---|
| FIIs | fundsexplorer.com.br/ranking | Selenium + clicar "Selecionar Todos" | Não |
| Ações BR | investsite.com.br/seleciona_acoes.php | Selenium + download Excel (header na linha 2) | Não |
| IPCA, Selic, IGP-M, CDI | api.bcb.gov.br (SGS) | REST | Não |
| Câmbio, BTC | economia.awesomeapi.com.br | REST | Não |
| IBOV, IFIX, IMOB | Yahoo Finance | yfinance | Não |

---

## Armadilhas conhecidas

1. **Fundsexplorer oculta colunas por padrão** — o scraper precisa clicar no checkbox "Selecionar Todos" (id: `colunas-ranking__todos`) antes de extrair a tabela.

2. **Investsite usa header na linha 2** — `pd.read_excel(file, header=2)`.

3. **PowerShell quebra heredoc Python** — para escrever arquivos `.py` com acentos via terminal, usar `notepad script.py` ou um arquivo auxiliar Python com `open(..., encoding='utf-8')`.

4. **yfinance retorna MultiIndex** — em versões >= 0.2, `df.columns` é um MultiIndex; usar `df.columns = df.columns.droplevel(1)` para normalizar.

5. **GitHub Actions pausar agendamento** — se o repo ficar 60 dias sem commit ou execução manual, o cron é pausado automaticamente pelo GitHub.

6. **OneDrive path no Actions** — a cópia para `onedrive_output_dir` é envolta em `try/except` propositalmente; no servidor Linux do Actions esse path não existe e o erro é esperado/ignorado.

7. **Encoding no Bloco 4 de verificação** — o `findstr` do Windows exibe acentos corrompidos no console mas o arquivo pode estar correto; usar `python -c "open(..., encoding='utf-8').read()"` para verificar de verdade.

---

## Backlog atual

### Limpeza pendente
- Remover `filters_content.txt` e `write_filters.py` da raiz
- Confirmar que `.pytest_cache` está no `.gitignore`

### Produto — próximas evoluções
- Validação de dados: abortar se scraping retornar < 100 linhas
- Histórico de performance: tempo que um ativo se mantém no Top 20
- Backtesting da metodologia de quartis
- Domínio próprio / encurtador de link para o dashboard
- Open Graph tags para preview bonito ao compartilhar o link

---

## Como rodar localmente

```bash
pip install -r requirements.txt
python main.py
```

## Como rodar os testes

```bash
pip install pytest
pytest tests/ -v
```

## Como publicar mudanças no dashboard

O dashboard é atualizado automaticamente a cada execução do screener.
Para mudanças no `docs/index.html`, basta commitar — o GitHub Pages publica em 1-2 min.
