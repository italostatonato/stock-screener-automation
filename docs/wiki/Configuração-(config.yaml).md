# Configuração (config.yaml)

Revisado em 07/09/2026 contra
[config.yaml](https://github.com/italostatonato/stock-screener-automation/blob/main/config.yaml).

## Seções

- `paths`: diretórios relativos de entrada, saída, histórico e logs;
  arquivo local de FIIs e destino opcional da entrega.
- `scraper`: fontes, URLs, timeouts, retries e parâmetros das alternativas.
  O padrão é `acoes_source: fundamentus`; timeout de 30 segundos e duas
  novas tentativas para essa fonte.
- `filters`: pisos de FIIs e `top_n`; a subseção `acoes` controla ações.
- `columns`: colunas percentuais, monetárias, inteiras e numéricas simples
  usadas para normalizar os FIIs.

Não são todos os parâmetros do projeto: pesos do score, regras de ML,
perfis híbridos e cron ficam no código ou no workflow.

## Pisos atuais

FIIs: DY médio de 12 meses maior que 0,3%, liquidez maior que R$ 100 mil,
patrimônio maior que R$ 50 milhões e P/VP positivo; até 20 fundos.
Se a coluna inteira de DY médio não existir, o filtro admite o DY mensal.

Ações: DY maior que 2%, liquidez maior que R$ 500 mil, valor de mercado
maior que R$ 200 milhões, Preço/VPA e EV/EBITDA positivos; até 20 empresas.

Os limites são estritos (`>`), não inclusivos. Não há quartis automáticos
nem garantia de preencher 20 posições. A liquidez de ações vem de
`Liq.2meses` do Fundamentus, apesar do nome legado da coluna mencionar três meses.

## Variáveis e fontes alternativas

`SCREENER_EXCEL_OUTPUT_DIR` ativa a cópia local do Excel. Sem ela, a cópia
é pulada e o arquivo permanece em `data/output/`. Não grave caminhos pessoais
na configuração versionada.

`BRAPI_TOKEN` só é exigido pelo coletor opcional de fundamentos brapi,
escrito para acesso Pro. A execução padrão do Fundamentus não depende dele.
A listagem pública brapi ainda pode enriquecer nomes de ativos.

A existência do arquivo `paths.local_input_file` ativa a entrada local de
FIIs. Para voltar à coleta web, ajuste essa configuração para que não aponte
para um arquivo local existente.

Veja [Metodologia de Filtros](https://github.com/italostatonato/stock-screener-automation/wiki/Metodologia-de-Filtros)
para fatores, critérios e interpretação do score.
