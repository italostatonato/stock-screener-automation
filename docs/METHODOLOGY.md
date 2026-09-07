# Metodologia de seleção e fontes

Revisado em 07/09/2026 contra `config.yaml`, `src/scorer.py`,
`src/filters.py`, `src/scraper.py`, `src/market_data.py` e `src/benchmark.py`.

## Ordem de processamento

O score é calculado no universo completo da execução, antes dos pisos de
elegibilidade. Cada indicador vira um ranking percentílico. Para indicadores
em que menor é melhor, o percentil é invertido por `100 - percentil`.
O score é a média de **sete fatores com peso 1/7**, limitado a 0–100 e
arredondado a uma casa decimal. Valores ou colunas ausentes recebem nota 50.

A seleção aplica os critérios mínimos, ordena por score decrescente,
desempata pelo ticker em ordem alfabética e limita o resultado a `top_n`.
As ações são deduplicadas por empresa após a ordenação: fica a classe com
melhor posição. A chave usa o nome normalizado ou o radical do ticker quando
o nome não está disponível.

O código atual não aplica cortes Q25/Q75 nem tem fallback de quartis.
Pode haver menos de 20 ativos. Se o Top FII ou Top Ações ficar vazio,
`main.py` interrompe a execução.

## FIIs

Sete fatores do score:

- `DY (12M) MÉDIA`: maior é melhor;
- `P/VP`: menor é melhor;
- `LIQUIDEZ DIÁRIA (R$)`: maior é melhor;
- `PATRIMÔNIO LÍQUIDO`: maior é melhor;
- `RENTAB. PERÍODO`: maior é melhor;
- `TAX. ADMINISTRAÇÃO`: menor é melhor;
- `TAX. PERFORMANCE`: menor é melhor.

Pisos atuais de `config.yaml`:

- P/VP presente e maior que zero;
- DY médio de 12 meses presente e **maior que 0,3%** (`0.003`);
- liquidez diária presente e **maior que R$ 100.000**;
- patrimônio líquido presente e **maior que R$ 50.000.000**;
- até 20 FIIs.

Na elegibilidade, se a coluna inteira `DY (12M) MÉDIA` não existir, o filtro
usa `DIVIDEND YIELD` para compatibilidade histórica. Um valor nulo numa coluna
existente não aciona esse fallback. O score continua usando seus sete fatores:
o DY médio ausente recebe nota neutra.

## Ações

Sete fatores do score:

- `Dividend Yield`: maior é melhor;
- `Preço/VPA`: menor é melhor;
- `EV/EBITDA`: menor é melhor;
- `Margem Líquida`: maior é melhor;
- `ROInvC` (ROIC): maior é melhor;
- `RPL` (ROE): maior é melhor;
- `Volume Diário Médio (3 meses)`: maior é melhor.

Pisos atuais:

- ticker e preço presentes; tickers repetidos são removidos;
- Preço/VPA e EV/EBITDA presentes e maiores que zero;
- Dividend Yield presente e **maior que 2%** (`0.02`);
- liquidez presente e **maior que R$ 500.000**;
- valor de mercado presente e **maior que R$ 200.000.000**;
- até 20 empresas.

Margem Líquida e ROA positivos não são filtros fixos atuais. ROA, P/L e
EV/EBIT não integram os sete fatores do score de ações.

## Como ler Status

- `Rank #N`: posição no Top N.
- `Aprovado (fora do Top N)`: passou nos pisos e ficou fora do limite.
- `Eliminado no filtro fixo: ...`: primeira condição que falhou.
- `Eliminado por duplicidade da empresa`: outra classe da mesma empresa foi
  priorizada na seleção de ações.

Snapshots antigos podem guardar metodologia e rótulos anteriores. Atualizar
a documentação não recalcula o histórico já observado.

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
registra cobertura. Veja [Backtests](BACKTEST_RETROATIVO.md).

## Configuração e limites

`config.yaml` concentra caminhos, fontes/timeouts, pisos e mapeamento de
colunas. Os pesos/direções do score, limites de ML, perfis híbridos e cron
ficam no código ou no YAML do workflow.

O score é relativo ao universo coletado naquela data. Uma nota alta não é
uma probabilidade de ganho nem garante retorno ou segurança. A disponibilidade
das fontes e os dados ausentes afetam o resultado.
