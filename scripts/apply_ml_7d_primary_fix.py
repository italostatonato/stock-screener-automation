from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def replace_many(path: Path, replacements: list[tuple[str, str]]) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new in replacements:
        text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_ml_models() -> None:
    path = ROOT / "src" / "ml_models.py"
    if not path.exists():
        print(f"[AVISO] não encontrei {path}")
        return

    text = path.read_text(encoding="utf-8")
    original = text

    text = re.sub(r"DEFAULT_HORIZON\s*=\s*\d+", "DEFAULT_HORIZON = 7", text)
    text = re.sub(r"MIN_TRAIN_ROWS\s*=\s*\d+", "MIN_TRAIN_ROWS = 20", text)
    text = re.sub(r"MIN_TRAIN_DATES\s*=\s*\d+", "MIN_TRAIN_DATES = 1", text)

    text = text.replace('"Status": "Ativo" if valid_windows >= 5 else "Aquecendo"', '"Status": "Ativo" if valid_windows >= 1 else "Aquecendo"')
    text = text.replace('"Status": "Ativo" if valid_windows >= 3 else "Aquecendo"', '"Status": "Ativo" if valid_windows >= 1 else "Aquecendo"')

    text = text.replace("Aguardando histórico com retornos futuros suficientes para treinamento.", "Aguardando histórico suficiente para o horizonte selecionado.")
    text = text.replace("Mínimo: 80 linhas e 5 datas.", "Mínimo: 20 linhas e 1 data válida.")
    text = text.replace("Minimo: 80 linhas e 5 datas.", "Minimo: 20 linhas e 1 data valida.")

    if text != original:
        path.write_text(text, encoding="utf-8")
        print("[OK] src/ml_models.py ajustado para horizonte principal 7d")
    else:
        print("[OK] src/ml_models.py já estava ajustado")


def patch_ml_confidence() -> None:
    path = ROOT / "src" / "ml_confidence.py"
    if not path.exists():
        print(f"[AVISO] não encontrei {path}")
        return

    text = path.read_text(encoding="utf-8")
    original = text

    text = re.sub(r"MIN_VALID_WINDOWS_DEFAULT\s*=\s*\d+", "MIN_VALID_WINDOWS_DEFAULT = 1", text)
    text = re.sub(r"TARGET_VALID_WINDOWS_DEFAULT\s*=\s*\d+", "TARGET_VALID_WINDOWS_DEFAULT = 5", text)
    text = text.replace("Aguardando pelo menos 5 janelas válidas de 30 dias.", "Aguardando pelo menos 1 janela válida do horizonte principal.")
    text = text.replace("Aguardando pelo menos 5 janelas válidas", "Aguardando pelo menos 1 janela válida")
    text = text.replace("Até lá, a confiabilidade preditiva real fica em 0% para evitar falso positivo.", "Até lá, a confiança permanece inicial para evitar falso positivo.")

    if text != original:
        path.write_text(text, encoding="utf-8")
        print("[OK] src/ml_confidence.py ajustado")
    else:
        print("[OK] src/ml_confidence.py já estava ajustado")


def patch_exporter() -> None:
    path = ROOT / "src" / "exporter.py"
    if not path.exists():
        print(f"[AVISO] não encontrei {path}")
        return

    text = path.read_text(encoding="utf-8")
    original = text

    text = text.replace("horizon_days=30", "horizon_days=7")
    text = text.replace('"horizonte_principal": "30d"', '"horizonte_principal": "7d",\n        "horizonte_estrategico": "30d"')

    # Ranking deve expor retorno esperado 7d. Mantém 30d como compatibilidade.
    if '"retorno_esperado_7d",' not in text:
        text = text.replace('"retorno_esperado_30d",', '"retorno_esperado_7d",\n        "retorno_esperado_30d",')

    text = text.replace(
        "Esta seção é apenas para acompanhar, no tempo, quais modelos começam a superar o baseline.",
        "Esta seção acompanha o horizonte curto de 7d como modelo inicial e mantém 30d como horizonte estratégico em maturação.",
    )

    if text != original:
        path.write_text(text, encoding="utf-8")
        print("[OK] src/exporter.py ajustado para ML 7d principal")
    else:
        print("[OK] src/exporter.py já estava ajustado")


def patch_main() -> None:
    path = ROOT / "main.py"
    if not path.exists():
        print(f"[AVISO] não encontrei {path}")
        return

    text = path.read_text(encoding="utf-8")
    original = text

    text = text.replace("run_ml_pipeline(data_dir=\"data\", horizon=30)", "run_ml_pipeline(data_dir=\"data\", horizon=7)")
    text = text.replace("run_ml_pipeline(data_dir='data', horizon=30)", "run_ml_pipeline(data_dir='data', horizon=7)")
    text = text.replace("run_ml_pipeline(data_dir=\"data\")", "run_ml_pipeline(data_dir=\"data\", horizon=7)")
    text = text.replace("run_ml_pipeline(data_dir='data')", "run_ml_pipeline(data_dir='data', horizon=7)")

    if text != original:
        path.write_text(text, encoding="utf-8")
        print("[OK] main.py ajustado para rodar ML 7d")
    else:
        print("[OK] main.py já estava ajustado ou não tinha chamada explícita")


def patch_dashboard() -> None:
    path = ROOT / "docs" / "index.html"
    if not path.exists():
        print(f"[AVISO] não encontrei {path}")
        return

    text = path.read_text(encoding="utf-8")
    original = text

    text = text.replace("Ret. esp. 30d", "Ret. esp.")
    text = text.replace("Retorno esperado 30d", "Retorno esperado")
    text = text.replace("r.retorno_esperado_30d", "(r.retorno_esperado_7d ?? r.retorno_esperado_30d)")

    text = text.replace(
        "Os demais modelos ficam em modo sombra até existir histórico suficiente com retorno futuro.",
        "Os demais modelos usam 7d como horizonte inicial porque já existe amostra validável; o horizonte 30d segue maturando até acumular mais exemplos.",
    )
    text = text.replace(
        "horizonte principal: ${ml.horizonte_principal || '30d'}",
        "horizonte principal: ${ml.horizonte_principal || '7d'}"
    )

    if text != original:
        path.write_text(text, encoding="utf-8")
        print("[OK] docs/index.html ajustado para exibir ML 7d")
    else:
        print("[OK] docs/index.html já estava ajustado ou padrão não encontrado")


def main() -> None:
    patch_ml_models()
    patch_ml_confidence()
    patch_exporter()
    patch_main()
    patch_dashboard()
    print("\nAgora rode:")
    print("$env:PYTHONPATH = (Get-Location).Path")
    print("python scripts\\refresh_ml_7d_primary_from_docs.py")
    print("python scripts\\debug_ml_targets.py")


if __name__ == "__main__":
    main()
