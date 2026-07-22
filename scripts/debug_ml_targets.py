from __future__ import annotations

from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ML = ROOT / "data" / "ml"
DOCS = ROOT / "docs" / "data"


def inspect(path: Path, name: str) -> None:
    print(f"\n{name}: {path}")
    if not path.exists():
        print("  arquivo não existe")
        return
    df = pd.read_parquet(path)
    print(f"  linhas: {len(df)} | colunas: {len(df.columns)}")
    if "Data_Execucao" in df.columns:
        d = pd.to_datetime(df["Data_Execucao"], errors="coerce")
        print(f"  período: {d.min().date()} até {d.max().date()} | datas: {d.dt.normalize().nunique()}")
    for col in ["Retorno_Futuro_7d", "Retorno_Futuro_30d", "score_ridge", "score_random_forest", "score_ensemble"]:
        if col in df.columns:
            valid = pd.to_numeric(df[col], errors="coerce").notna().sum()
            print(f"  {col}: {valid} válidos")
    if "status_modelos" in df.columns:
        print(df["status_modelos"].value_counts(dropna=False).to_string())


def latest_json() -> None:
    index = json.loads((DOCS / "index.json").read_text(encoding="utf-8"))
    latest = sorted(index)[-1]
    payload = json.loads((DOCS / f"{latest}.json").read_text(encoding="utf-8"))
    ml = payload.get("modelos_ml", {})
    print(f"\nJSON mais recente: {latest}")
    print(f"  status: {ml.get('status')}")
    print(f"  horizonte_principal: {ml.get('horizonte_principal')}")
    print(f"  horizonte_estrategico: {ml.get('horizonte_estrategico')}")
    print(f"  ranking ações: {len((ml.get('ranking') or {}).get('acoes', []))}")
    print(f"  ranking fiis: {len((ml.get('ranking') or {}).get('fiis', []))}")
    print(f"  performance: {len(ml.get('performance') or [])}")


def main() -> None:
    inspect(ML / "historico_acoes.parquet", "historico_acoes")
    inspect(ML / "historico_fiis.parquet", "historico_fiis")
    inspect(ML / "dataset_acoes.parquet", "dataset_acoes")
    inspect(ML / "dataset_fiis.parquet", "dataset_fiis")
    inspect(ML / "model_predictions_acoes.parquet", "model_predictions_acoes")
    inspect(ML / "model_predictions_fiis.parquet", "model_predictions_fiis")
    inspect(ML / "model_performance.parquet", "model_performance")
    latest_json()


if __name__ == "__main__":
    main()
