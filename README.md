# 📊 Stock Screener Automation

### 🔗 [Acesse o dashboard ao vivo](https://italostatonato.github.io/stock-screener-automation/)

Screener automático de FIIs (Fundos Imobiliários) e Ações brasileiras, com filtro adaptativo por quartis, rodando diariamente via GitHub Actions.

📖 **Documentação completa:** [Wiki do projeto](../../wiki)

## Como funciona

1. Coleta dados de FIIs ([Fundsexplorer](https://www.fundsexplorer.com.br/ranking)) e Ações BR ([Investsite](https://www.investsite.com.br/seleciona_acoes.php)) via Selenium
2. Limpa e normaliza os dados (valores monetários, percentuais, inteiros)
3. Aplica filtro em duas camadas — fixo + quartil móvel adaptativo (sempre seleciona os melhores 25% do universo do dia)
4. Gera um Excel com:
   - **Recomendações** — Top 20 FIIs e Top 20 Ações
   - **Indicadores** — IPCA, Selic, IGP-M, câmbio (via API do Banco Central)
   - **Premissas** — metodologia e critérios usados, em linguagem clara
   - **Bases Completas** — todos os ativos analisados, com coluna de auditoria explicando por que cada um entrou ou saiu
   - **Gráficos** — distribuições visuais dos principais indicadores

## Setup local

```bash
git clone https://github.com/italostatonato/stock-screener-automation.git
cd stock-screener-automation
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Rodando os testes

```bash
pip install pytest
pytest tests/ -v
```

## Configuração

Edite `config.yaml` para ajustar filtros, fontes de dados e caminhos de saída. Veja a [página de Configuração na Wiki](../../wiki/Configuração-(config.yaml)) para detalhes de cada parâmetro.

## Automação

O workflow `.github/workflows/run_screener.yml`:
- Roda testes automatizados antes de qualquer execução
- Executa o screener todo dia útil às 09:00 BRT
- Salva o resultado como artefato do GitHub (90 dias de retenção)
- Notifica via Telegram em caso de falha

## Onde pegar o resultado

- **Dashboard web**: [italostatonato.github.io/stock-screener-automation](https://italostatonato.github.io/stock-screener-automation/) — atualizado automaticamente todo dia útil
- **Artefato no GitHub**: aba *Actions* → última execução → seção *Artifacts*
- **OneDrive local** (apenas em execuções locais): pasta configurada em `onedrive_output_dir` no `config.yaml`

## Metodologia

Veja a explicação completa do filtro em duas camadas (fixo + quartil) na [página de Metodologia na Wiki](../../wiki/Metodologia-de-Filtros).
