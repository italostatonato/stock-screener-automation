# Troubleshooting

Revisado em 07/09/2026.

## Preparar e executar

Use Git, Python 3.11 ou superior e Chrome para a coleta de FIIs.
Instale as dependências de `requirements.txt` num ambiente virtual. Node.js
permite executar o teste JavaScript da carteira híbrida.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
python scripts/healthcheck_data.py
python -m pytest tests/ -v
```

No Linux/macOS, ative o ambiente com `source .venv/bin/activate`.
Execute os comandos na raiz do projeto. Se houver erro ao importar `src`,
confira o diretório atual, o interpretador ativo e a presença de
`src/__init__.py`; não presuma que o arquivo esteja faltando.

O arquivo `paths.local_input_file`, quando presente, substitui a coleta de
FIIs. Logs ficam em `logs/YYYY-MM-DD.log`, o Excel em
`data/output/Top20_Ranking_YYYY-MM-DD.xlsx` e o JSON em
`docs/data/YYYY-MM-DD.json`. A data usa `America/Sao_Paulo`.
Reexecutar no mesmo dia atualiza os arquivos daquela data.

## Backup e escopo

Antes de reprocessar ou alterar dados, preserve uma cópia de `data/`.
Preserve também `docs/data/` quando a operação for reescrever snapshots do
dashboard. Use uma pasta externa ou temporária para não incluir o backup
num commit por acidente:

```powershell
$BackupDir = Join-Path $env:TEMP ("radar-backup-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $BackupDir | Out-Null
Copy-Item -LiteralPath "data" -Destination $BackupDir -Recurse
Copy-Item -LiteralPath "docs/data" -Destination (Join-Path $BackupDir "dashboard-data") -Recurse
```

Uma mudança apenas documental não precisa executar `main.py`. Esse comando
coleta dados, treina modelos e pode entregar Excel. Revise e adicione ao Git
somente os arquivos relacionados à mudança; preserve trabalhos locais de
outras tarefas.

## Healthcheck

```powershell
python scripts/healthcheck_data.py
```

O comando atualiza o manifesto do lake, reconstrói o índice do dashboard e
grava `data/lake/quality_report.json`. Portanto, não é somente leitura.
O retorno é código 1 para `error` e código 0 para `ok` ou `warn`.

A verificação cobre chaves nulas e duplicadas, esquema e preço de entrada
da carteira, cobertura de FII/ACAO nas datas recentes, legibilidade de
Parquets e coerência entre o lake e o índice do dashboard.
Snapshots históricos listados em `known_incomplete_snapshots.json` podem gerar
avisos conhecidos; investigue avisos novos em vez de suprimi-los.

Para conferir os dados numa auditoria documental, copie os dados e os módulos
necessários para uma pasta temporária e rode o healthcheck nessa cópia.
Não publique alterações de manifesto/relatório produzidas só pela auditoria.

## Workflow e publicação

[Weekly FII Screener](https://github.com/italostatonato/stock-screener-automation/blob/main/.github/workflows/run_screener.yml) roda toda segunda,
**08h de São Paulo** (`0 11 * * 1`), ou por **Actions → Weekly FII Screener →
Run workflow**. Não possui gatilho de push.

- `test`: Python 3.11, instalação com cache pip e `pytest tests/ -v`.
- `screener`: depende dos testes; prepara Chrome, sincroniza a `main`,
  executa pipeline e healthcheck, salva artefatos por 90 dias e commita
  `docs/data/`, `data/lake/`, `data/ml/`, `data/backtest/` e `data/delivery/`.
- `deploy`: usa a `main` atual e publica `docs/` no GitHub Pages quando
  os testes passam, mesmo se o screener falhar.

Os timeouts são 25 minutos para testes e 60 para coleta. A concorrência é
controlada por branch e não cancela a execução já em andamento.
A etapa opcional de notificação de falha do screener usa
`TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` nos Secrets.

Para problemas de push, confira remote, credenciais e permissão de escrita.
O workflow já declara `contents: write`; a publicação usa
`pages: write` e `id-token: write` no job de deploy.
Uma edição documental não inicia automaticamente uma coleta nem um deploy.

A revisão documental semanal é separada, **segunda-feira às 12h de São Paulo**,
e é administrada no Codex. Veja [Manutenção da documentação](https://github.com/italostatonato/stock-screener-automation/wiki/Manutencao-da-Documentacao).

## Fonte indisponível ou seleção vazia

Consulte o log e repita a execução quando a fonte estiver disponível.
O Fundamentus usa timeout e novas tentativas configuráveis. A coleta de FIIs
depende de Chrome e do HTML do Fundsexplorer.

Não existe fallback de quartis. Se a seleção ficar vazia, confira colunas,
unidades percentuais e pisos em `config.yaml`. O pipeline interrompe a
geração de um novo snapshot quando a coleta/seleção obrigatória falha.
Os históricos locais de FIIs podem já ter sido atualizados antes de uma
falha posterior de ações; não trate todos os arquivos como uma transação atômica.

Falhas em indicadores, ML, exportação ou entrega podem aparecer apenas nos
logs de `main.py`. Confira o healthcheck e as saídas esperadas mesmo quando
a última linha do pipeline indicar conclusão.

## Rebuild e scripts históricos

```powershell
python scripts/rebuild_from_lake.py
```

O rebuild não coleta fontes: reconstrói históricos, carteira, datasets e
previsões ML em 30d, atualiza manifesto/índice e roda qualidade.
Ele não recria os payloads completos do dashboard nem os Excels finais.

Os scripts de pesquisa são executados separadamente:

```powershell
python scripts/build_observed_history.py
python scripts/run_observed_backtest.py
python scripts/build_point_in_time_history.py --start 2021-01-01
python scripts/run_point_in_time_backtest.py
```

`--offline` está disponível em `build_point_in_time_history.py`,
`run_observed_backtest.py` e `run_point_in_time_backtest.py`; exige caches já
preenchidos. Leia [Backtests](https://github.com/italostatonato/stock-screener-automation/wiki/Backtests) antes de reprocessar.
Não copie snapshots sintéticos para o lake observado.

`scripts/refresh_ml_7d_primary_from_docs.py` regrava derivados ML e o JSON mais
recente a partir dos snapshots; não faz parte da rotina semanal.
Os scripts `apply_ml_*` são patches de migração, não comandos de setup.

## Dashboard com data antiga

Confira se a coleta realmente concluiu e se o JSON esperado existe.
Reconstrua apenas o índice com a função oficial:

```powershell
python -c "from src.data_lake import rebuild_dashboard_index; print(rebuild_dashboard_index('docs/data'))"
```

Esse comando altera `docs/data/index.json`. Para um conflito de Git nesse
arquivo, confira os snapshots existentes antes de reconstruir e marcar a
resolução. Use `git status` para verificar o estado de um rebase; não apague
diretórios internos de `.git` como rotina de troubleshooting.

Para servir o dashboard localmente:

```powershell
python -m http.server 8000 --directory docs
```

Abra [localhost:8000](http://localhost:8000/).

## Entrega local do Excel

`src/delivery.py` copia o Excel para `paths.onedrive_output_dir`, resolvido
pela variável `SCREENER_EXCEL_OUTPUT_DIR`:

```powershell
$env:SCREENER_EXCEL_OUTPUT_DIR = "C:/Users/<voce>/OneDrive/Recomendacoes"
python main.py
```

Sem variável, a cópia é pulada e o Excel permanece em `data/output/`.
O destino recebe `Top20_Ranking_YYYY-MM-DD.xlsx` e
`Top20_Ranking_Atual.xlsx`. O log `data/delivery/delivery_log.jsonl` registra
status, SHA256, tamanho e nomes de arquivo.

O runner Linux não acessa uma pasta Windows local; no Actions, consulte os
artefatos. Para testar uma entrega já configurada:

```powershell
python scripts/test_delivery.py --file data/output/Top20_Ranking_YYYY-MM-DD.xlsx
```

Substitua a data por um arquivo existente. Esse comando efetua a cópia e
registra entrega. Microsoft Graph permanece uma etapa futura.
