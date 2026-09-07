# Manutenção da documentação e da wiki

Revisão de referência: **07/09/2026**.

## Escopo e fontes de verdade

A revisão compara o código com o README, os guias de `docs/`, `CLAUDE.md` e
todas as páginas da wiki. Afirmações sobre comportamento atual devem ter
evidência em código, configuração ou teste verificável.

- `main.py`: ordem do pipeline, data/fuso, falhas obrigatórias e chamadas ML.
- `config.yaml`: caminhos, fontes, retries, pisos e Top N.
- `src/scorer.py` e `src/filters.py`: fatores, pesos, dados ausentes,
  limites estritos e deduplicação por empresa.
- `src/scraper.py`, `src/market_data.py` e `src/benchmark.py`: fontes,
  aliases, proxies e alternativas.
- `src/dataset_builder.py`, `src/ml_models.py`, `src/ml_confidence.py` e
  `src/exporter.py`: targets, horizontes, maturidade e proteção de projeções.
- `docs/index.html`: telas, perfis híbridos, limites do aporte e premissas.
- `src/data_lake.py`, `src/delivery.py`, `src/backtest_engine.py`,
  `src/observed_history.py`, `src/point_in_time.py` e `scripts/`: dados,
  entrega, reconstrução, backtests e comandos.
- `.github/workflows/run_screener.yml`: cron, jobs, gatilhos, artefatos,
  arquivos commitados e publicação.

Apresentações, planos e relatórios de QA com data são registros de entregas.
Não devem ser reescritos como documentação operacional nem incluídos por
acidente numa atualização documental.

## Revisão semanal

Cadência solicitada: **toda segunda-feira, 12h, America/Sao_Paulo**.
O agendador é uma automação do Codex associada à tarefa de revisão; seu estado
ativo é mantido no aplicativo, fora deste repositório.

Como a tarefa acessa arquivos locais, o computador precisa estar ligado e o
aplicativo em execução no horário agendado, conforme a
[documentação de tarefas agendadas](https://learn.chatgpt.com/docs/automations?surface=app).

O screener mantém seu cron próprio, **segunda-feira às 08h de São Paulo**
(`0 11 * * 1`). A revisão documental não altera o cron de coleta.

Procedimento:

1. Conferir alterações locais e consultar a versão atual da branch padrão.
2. Ler os commits desde a revisão anterior e conferir as páginas da wiki.
3. Comparar fontes, regras, parâmetros, comandos, arquivos, telas, ML e backtests.
4. Corrigir divergências comprovadas; separar limitações e planos futuros
   das funcionalidades já implementadas.
5. Validar caminhos, links e coerência numérica.
6. Preparar um diff somente documental e resumir o que exige atenção.
7. Na revisão recorrente, notificar divergências, correções ou impedimentos;
   permanecer silencioso quando não houver novidade acionável.

Não é necessário executar o screener, refazer o histórico, treinar modelos
ou entregar Excel para conferir documentação. O healthcheck escreve manifesto,
índice e relatório: em auditorias documentais, execute-o numa cópia temporária.

## Cópia versionada da wiki

As páginas publicadas ficam no repositório Git separado:

```text
https://github.com/italostatonato/stock-screener-automation.wiki.git
```

`docs/wiki/` mantém a cópia revisável junto com o código. Alterar essa pasta
ou publicar GitHub Pages **não atualiza a wiki automaticamente**.

Antes de publicar, obtenha a versão atual da wiki, compare-a com a cópia
versionada e incorpore eventuais edições feitas diretamente no GitHub. Revise
o diff e valide os links. Publique no projeto e na wiki com commits normais,
sem force-push e sem apagar páginas de terceiros.

Exemplo de preparação em PowerShell, usando uma pasta temporária nova:

```powershell
$WikiDir = Join-Path $env:TEMP ("radar-wiki-" + [guid]::NewGuid().ToString("N"))
git clone https://github.com/italostatonato/stock-screener-automation.wiki.git $WikiDir
git -C $WikiDir status --short
# Comparar com docs/wiki e incorporar mudanças remotas antes de copiar.
Copy-Item -Path "docs/wiki/*.md" -Destination $WikiDir
git -C $WikiDir diff --check
git -C $WikiDir diff --stat
# Depois da revisão do diff e da autorização para publicar:
git -C $WikiDir add -- "*.md"
git -C $WikiDir commit -m "docs: sincroniza wiki com o projeto"
git -C $WikiDir push
```

Use o remote da clonagem; não presuma que a branch da wiki tenha o mesmo nome
da branch do projeto. Preserve os nomes das páginas para não quebrar URLs e
atualize `Home.md` e `_Sidebar.md` ao criar páginas.
