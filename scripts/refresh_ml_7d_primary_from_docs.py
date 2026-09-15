"""Compatibilidade: reconstroi derivados ML usando o data lake canonico.

O nome antigo e mantido para comandos existentes. JSONs do dashboard contem
apenas o Top N e nao podem substituir o historico do universo completo.
Esta rotina nao altera snapshots JSON; a proxima coleta exporta o dashboard.
Prefira: python scripts/rebuild_from_lake.py
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.rebuild_from_lake import main as rebuild


def main() -> int:
    print("Reconstruindo derivados a partir do lake; JSONs historicos preservados.")
    return rebuild()


if __name__ == "__main__":
    raise SystemExit(main())
