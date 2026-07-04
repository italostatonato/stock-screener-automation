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
