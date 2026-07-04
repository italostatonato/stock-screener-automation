# Operação e troubleshooting

## Rotina local recomendada

```powershell
cd "C:\Users\Ítalo\OneDrive\stock-screener-automation"
python main.py
python scripts/healthcheck_data.py
pytest tests/ -v
```

## Antes de subir mudanças estruturais

1. Fazer backup de `data/`.
2. Rodar `python main.py`.
3. Rodar `python scripts/healthcheck_data.py`.
4. Rodar `pytest tests/ -v`.
5. Testar dashboard local.
6. Conferir `git status`.
7. Não commitar `backups/`.

## Backup local

```powershell
$BackupRoot = "C:\Users\Ítalo\OneDrive\stock-screener-automation\backups"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Backup = Join-Path $BackupRoot "data_backup_$Timestamp"
New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
Copy-Item -Path ".\data" -Destination $Backup -Recurse -Force
Write-Host "Backup criado em: $Backup"
```

## Healthcheck

```powershell
python scripts/healthcheck_data.py
```

Status esperado:

```text
ok
```

`warn` pode ser aceitável em fases iniciais de histórico ou ML. `error` deve bloquear push até ser investigado.

## Rebuild a partir do lake

```powershell
python scripts/rebuild_from_lake.py
```

Use quando precisar reconstruir derivados de `data/ml` ou `data/backtest` a partir dos snapshots incrementais.

## Corrigir index.json do dashboard

Se o snapshot existir mas o site carregar data antiga:

```powershell
@'
import json
from pathlib import Path

data_dir = Path("docs/data")
index_path = data_dir / "index.json"

datas = sorted(
    [p.stem for p in data_dir.glob("*.json") if p.stem != "index"],
    reverse=True,
)

index_path.write_text(
    json.dumps(datas, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

print("index.json reconstruído:")
for d in datas:
    print("-", d)
'@ | python
```

## Resolver conflito em docs/data/index.json

Durante rebase, reconstruir o índice e marcar como resolvido:

```powershell
git status
# rodar script de reconstrução do index.json
git add docs/data/index.json
$env:GIT_EDITOR="true"
git rebase --continue
```

## Limpar rebase fantasma

Só use quando `HEAD` e `origin/main` forem iguais e o working tree estiver limpo:

```powershell
$head = git rev-parse HEAD
$origin = git rev-parse origin/main
$dirty = git status --porcelain

if ($head -eq $origin -and [string]::IsNullOrWhiteSpace($dirty)) {
    if (Test-Path ".git\rebase-merge") {
        Remove-Item ".git\rebase-merge" -Recurse -Force
    }
    if (Test-Path ".git\rebase-apply") {
        Remove-Item ".git\rebase-apply" -Recurse -Force
    }
    Write-Host "Rebase fantasma limpo com segurança."
} else {
    Write-Host "Não limpei nada. HEAD/origin ou working tree não estão seguros."
}

git status
```

## Subir mudanças

```powershell
git status
git add <arquivos>
git commit -m "Mensagem objetiva"
git pull --rebase origin main
git push origin main
git status
```

## Arquivos que normalmente entram em mudanças estruturais

```text
main.py
requirements.txt
.github/workflows/run_screener.yml
src/*.py
scripts/*.py
tests/*.py
docs/data/
data/lake/
data/ml/
data/backtest/
```

## Arquivos que normalmente entram em mudanças visuais

```text
docs/index.html
src/exporter.py
```

## Não commitar

```text
backups/
.venv/
__pycache__/
.pytest_cache/
logs/
```

## Entrega automática do Excel final

A entrega do Excel final é feita pela camada `src/delivery.py`. Ela é separada do ranking, do lake, do dashboard e dos modelos para que uma falha no OneDrive não corrompa a execução principal.

### Fase 1: cópia local para OneDrive sincronizado

Quando o pipeline roda no notebook Windows, o Excel final é copiado para a pasta configurada em `paths.onedrive_output_dir`:

```yaml
paths:
  onedrive_output_dir: "C:/Users/Ítalo/OneDrive/Tabelas Acoes/Recomendacoes"
```

A entrega gera duas saídas:

```text
Top20_Ranking_YYYY-MM-DD.xlsx
Top20_Ranking_Atual.xlsx
```

O primeiro arquivo mantém histórico por data. O segundo é sempre a versão atual para consulta rápida.

### Segurança no GitHub Actions

O runner do GitHub Actions é Linux e não tem acesso ao caminho local `C:/Users/...`. Por isso, quando o destino configurado é um path Windows local, a entrega é ignorada com segurança no Actions. O Excel continua disponível como artifact do workflow.

### Teste manual da entrega

Depois de rodar `python main.py`, teste a entrega com:

```powershell
python scripts/test_delivery.py
```

Ou informe um arquivo específico:

```powershell
python scripts/test_delivery.py --file data/output/Top20_Ranking_2026-07-04.xlsx
```

### Log de entrega

Quando a entrega é executada localmente, o projeto registra um log em:

```text
data/delivery/delivery_log.jsonl
```

O log registra status, hash SHA256, tamanho do arquivo e nomes dos arquivos entregues, sem gravar tokens ou credenciais.

### Fase 2 futura: Microsoft Graph

A automação 100% remota deve usar Microsoft Graph com credenciais em GitHub Secrets ou OIDC. Não colocar tokens no código, no `config.yaml` ou em arquivos versionados.
