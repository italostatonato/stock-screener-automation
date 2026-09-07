# Fontes de Dados

Revisado em 07/09/2026.

## Fontes e adaptações

**FIIs:** Fundsexplorer, com Selenium/Chrome, ou o Excel em
`paths.local_input_file` quando esse arquivo existe.

**Ações:** tabela pública do Fundamentus, via HTTP, sem token na execução
padrão. O timeout é de 30 segundos, com duas novas tentativas configuradas.
Uma execução bem-sucedida pode usar uma requisição; falhas podem causar retries.

O adaptador preserva nomes legados de colunas:

- `Volume Diário Médio (3 meses)` recebe `Liq.2meses`: são **dois meses**
  na fonte padrão, apesar do nome da coluna.
- `RPL` recebe ROE; `ROInvC`, ROIC.
- ROA é aproximado por `P/Ativo ÷ P/L`.
- Market Cap é calculado por `P/VP × Patrimônio Líquido`.
- `Passivo/Patrimônio Líquido` recebe dívida líquida/patrimônio e não participa
  do score atual.

O código mantém alternativas `brapi` e `investsite`; não são a fonte padrão.
O coletor de fundamentos brapi exige `BRAPI_TOKEN` e foi escrito para acesso
Pro. A listagem pública brapi e a busca do Yahoo podem ser consultadas
separadamente para enriquecer nomes de ativos.

**Indicadores:** SGS/BCB para IPCA, Selic e IGP-M; câmbio de AwesomeAPI com
fallback Frankfurter; cinco maiores criptomoedas por valor de mercado via
CoinGecko, em BRL.

**Benchmarks:** Yahoo/yfinance para IBOV (`^BVSP`), IMOB (`IMOB.SA`) e
IVVB11 (`IVVB11.SA`). A série rotulada IFIX usa **XFIX11.SA como proxy**.
CDI usa a série 12 do SGS/BCB; as variações de CDI, IPCA e IGP-M são acumuladas
conforme `src/benchmark.py`.

**Pesquisa retroativa:** informes mensais de FIIs da CVM, com data de entrega,
e COTAHIST da B3 para negociação. O motor de retorno ajustado usa Yahoo e
registra cobertura. Veja [Backtests](https://github.com/italostatonato/stock-screener-automation/wiki/Backtests).

## Configuração e limites

`config.yaml` concentra caminhos, fontes/timeouts, pisos e mapeamento de
colunas. Os pesos/direções do score, limites de ML, perfis híbridos e cron
ficam no código ou no YAML do workflow.

O score é relativo ao universo coletado naquela data. Uma nota alta não é
uma probabilidade de ganho nem garante retorno ou segurança. A disponibilidade
das fontes e os dados ausentes afetam o resultado.
