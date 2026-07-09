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
    summary = build_ml_confidence_summary(perf, docs_data_dir="docs/data")
    print(summary)
