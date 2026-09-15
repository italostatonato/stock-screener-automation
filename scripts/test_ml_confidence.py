from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ml_confidence import build_ml_confidence_summary

if __name__ == "__main__":
    perf = [
        {
            "Tipo": "ACAO",
            "Modelo": "Random Forest",
            "Horizonte": "30d",
            "Janelas_Validas": 0,
            "Hit_Rate_Top20": None,
            "Spearman_IC": None,
            "Alpha_vs_Score_Top": None,
        }
    ]
    summary = build_ml_confidence_summary(perf, docs_data_dir=str(PROJECT_ROOT / "docs/data"))
    print(summary)
