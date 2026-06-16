# 📊 Stock Screener Automation

Screener automático de FIIs (Fundos Imobiliários) com coleta diária via Selenium e ranking por DY, P/VP e liquidez.

## Como funciona

1. Coleta a tabela de ranking do [Fundsexplorer](https://www.fundsexplorer.com.br/ranking)
2. Limpa e normaliza os dados
3. Aplica filtros configuráveis (`config.yaml`)
4. Salva snapshot diário em Excel + atualiza histórico

## Setup local

```bash
git clone https://github.com/SEU_USER/stock-screener-automation.git
cd stock-screener-automation
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Configuração

Edite `config.yaml` para ajustar filtros (P/VP, DY mínimo, liquidez etc.) e caminhos.

## Automação

O workflow `.github/workflows/run_screener.yml` roda automaticamente todo dia útil às 09:00 BRT.