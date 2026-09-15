# Como Rodar Localmente

Revisado em 15/09/2026. Use Git, Python 3.11 ou superior e Chrome para coletar
FIIs. Node.js 24 permite executar os testes JavaScript do simulador e da renderização.

```bash
git clone https://github.com/italostatonato/stock-screener-automation.git
cd stock-screener-automation
python -m venv .venv
```

No Windows/PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

No Linux/macOS:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

A coleta automática inicia segunda-feira às **08h de Brasília**. Os
comandos abaixo permitem execução manual; datas nos arquivos não representam
um agendamento diário. A revisão documental ocorre separadamente, segunda
às **12h de Brasília**.

## Execução

Na raiz do projeto:

```bash
python main.py
python scripts/healthcheck_data.py
python -m pytest tests/ -v
python -m http.server 8000 --directory docs
```

Abra [localhost:8000](http://localhost:8000/). O pipeline gera Excel em
`data/output/Top20_Ranking_YYYY-MM-DD.xlsx`, logs em `logs/`, lake,
históricos, modelos e JSON do dashboard. A data usa `America/Sao_Paulo`.

Se `paths.local_input_file` existir, esse Excel substitui a coleta de FIIs.
Ações usam Fundamentus por padrão, sem token. Para entrega opcional do Excel,
defina `SCREENER_EXCEL_OUTPUT_DIR` na máquina local antes da execução.

`main.py` e o healthcheck padrão escrevem dados. Use
`python scripts/healthcheck_data.py --read-only` para inspecionar sem escrita.
Antes de reprocessar, siga as instruções de backup e reconstrução em
[Operação e troubleshooting](https://github.com/italostatonato/stock-screener-automation/wiki/Troubleshooting).
