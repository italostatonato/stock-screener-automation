# Manutenção da documentação e da wiki

Revisão de referência: **15/09/2026**.

## Estado da revisão de 15/09/2026

Esta entrega reúne as correções do código e os guias correspondentes:

- pipeline principal e rebuild com treinamento em 7d, previsões separadas
  por horizonte e targets realizados até a data da previsão;
- healthcheck com `--read-only`, sem escrita em manifesto, índice ou relatório;
- testes Python e JavaScript em pushes de código/documentação e pull requests;
- validação das etapas obrigatórias, persistência de números e datas,
  exportação JSON estrita e escape de metadados na renderização do dashboard;
- diagnóstico de falhas do Fundamentus, intervalos de retry de 15s/30s
  e preservação dos logs de coleta no GitHub Actions.

A validação local concluiu 176 testes Python, incluindo os wrappers dos
46 testes JavaScript, e uma execução integrada offline em cópia dos dados.
O healthcheck apontou apenas os snapshots incompletos já conhecidos de
21, 24 e 25/08/2026. Os dados históricos originais foram preservados.

A coleta continua semanal, segunda-feira às 08h de Brasília, ou manual.
Atualizações por push executam os testes; coleta e deploy permanecem no
workflow semanal/manual. A wiki é sincronizada separadamente do projeto.

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
- `docs/index.html`: telas, perfis híbridos, limites do aporte, premissas e
  textos sobre frequência de atualização.
- Docstrings, comentários de configuração, aba Premissas do Excel e
  descrições exportadas: também podem reapresentar explicações antigas.
- `src/data_lake.py`, `src/delivery.py`, `src/backtest_engine.py`,
  `src/observed_history.py`, `src/point_in_time.py` e `scripts/`: dados,
  entrega, reconstrução, backtests e comandos.
- `.github/workflows/run_screener.yml`: cron, jobs, gatilhos, artefatos,
  arquivos commitados e publicação.

Apresentações, planos e relatórios de QA com data são registros de entregas.
Não devem ser reescritos como documentação operacional nem incluídos por
acidente numa atualização documental.

## Como revisar referências à frequência

Pesquisar `diário`, `diária`, `diariamente`, `daily`, `todos os dias` e
expressões semelhantes em Markdown, HTML, Python, YAML e strings de JSON.
Interpretar cada ocorrência antes de alterar:

- coleta e ranking: semanais, segunda-feira às 08h de Brasília, ou manuais;
- históricos: por data de execução, sem pressupor um registro por dia;
- tendências dos cards: entre coletas disponíveis; a Visão geral busca
  uma referência de pelo menos sete dias antes;
- indicadores de mercado: a frequência da métrica permanece a da fonte;
- horizontes ML: dias corridos de retorno futuro, não agenda de execução;
- revisão documental: segunda-feira às 12h, separada da coleta.

Neste check recorrente, preservar os dados e as evidências históricas.
Rótulos antigos nos JSONs devem ser identificados como metadados de época,
não como descrição da rotina atual; eventual correção desses arquivos exige
trabalho separado. Conferir o gerador para que a descrição correta seja usada
nas próximas exportações.

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
3. Comparar fontes, regras, parâmetros, comandos, arquivos, telas, ML e
   backtests; aplicar a revisão de frequência e distinguir alterações locais
   do comportamento disponível na branch remota e na wiki publicada.
   Guias publicados devem orientar um clone da versão remota; registrar
   implementações ainda locais como pendências até a entrega do código.
4. Corrigir divergências comprovadas; separar limitações e planos futuros
   das funcionalidades já implementadas.
5. Validar caminhos, links e coerência numérica.
6. Preparar um diff somente documental e resumir o que exige atenção.
7. Na revisão recorrente, notificar divergências, correções ou impedimentos;
   permanecer silencioso quando não houver novidade acionável.

Não é necessário executar o screener, refazer o histórico, treinar modelos
ou entregar Excel para conferir documentação. Se um healthcheck for
necessário neste check recorrente, use
`python scripts/healthcheck_data.py --read-only` para inspecionar sem escrita.

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
