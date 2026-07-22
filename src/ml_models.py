"""ml_models.py — Pipeline sombra de modelos de Machine Learning.

Esta camada prepara o projeto para comparar o score multifatorial atual contra
modelos supervisionados. Ela não substitui o ranking oficial: os modelos rodam
em modo sombra, salvam previsões e acumulam métricas para avaliação futura.

Entradas esperadas:
- data/ml/dataset_fiis.parquet
- data/ml/dataset_acoes.parquet

Saídas geradas:
- data/ml/model_predictions_fiis.parquet
- data/ml/model_predictions_acoes.parquet
- data/ml/model_performance.parquet

Modelos avaliados:
- Score Top atual (baseline)
- Ridge Regression
- Random Forest
- Extra Trees
- XGBoost
- LightGBM
- CatBoost
- Ensemble médio dos modelos disponíveis
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_HORIZON = 7
MIN_TRAIN_ROWS = 20
MIN_TRAIN_DATES = 1
TOP_N_PERFORMANCE = 20

MODEL_SCORE_COLUMNS = {
    "score_top": "Score Top",
    "score_ridge": "Ridge",
    "score_random_forest": "Random Forest",
    "score_extra_trees": "Extra Trees",
    "score_xgboost": "XGBoost",
    "score_lightgbm": "LightGBM",
    "score_catboost": "CatBoost",
    "score_ensemble": "Ensemble",
}

OPTIONAL_IMPORT_ERRORS: dict[str, str] = {}

try:
    from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
except Exception as exc:  # pragma: no cover - depende do ambiente
    ExtraTreesRegressor = None
    RandomForestRegressor = None
    SimpleImputer = None
    Ridge = None
    Pipeline = None
    StandardScaler = None
    OPTIONAL_IMPORT_ERRORS["sklearn"] = str(exc)

try:
    from xgboost import XGBRegressor
except Exception as exc:  # pragma: no cover - depende do ambiente
    XGBRegressor = None
    OPTIONAL_IMPORT_ERRORS["xgboost"] = str(exc)

try:
    from lightgbm import LGBMRegressor
except Exception as exc:  # pragma: no cover - depende do ambiente
    LGBMRegressor = None
    OPTIONAL_IMPORT_ERRORS["lightgbm"] = str(exc)

try:
    from catboost import CatBoostRegressor
except Exception as exc:  # pragma: no cover - depende do ambiente
    CatBoostRegressor = None
    OPTIONAL_IMPORT_ERRORS["catboost"] = str(exc)


@dataclass(frozen=True)
class AssetSpec:
    tipo: str
    dataset_filename: str
    predictions_filename: str
    ticker_col: str
    date_col: str
    price_col: str
    name_col: str | None
    dy_col: str | None
    multiple_col: str | None


SPECS = {
    "fiis": AssetSpec(
        tipo="FII",
        dataset_filename="dataset_fiis.parquet",
        predictions_filename="model_predictions_fiis.parquet",
        ticker_col="FUNDOS",
        date_col="Data_Execucao",
        price_col="PREÇO ATUAL (R$)",
        name_col="SETOR",
        dy_col="DIVIDEND YIELD",
        multiple_col="P/VP",
    ),
    "acoes": AssetSpec(
        tipo="ACAO",
        dataset_filename="dataset_acoes.parquet",
        predictions_filename="model_predictions_acoes.parquet",
        ticker_col="Ação",
        date_col="Data_Execucao",
        price_col="Preço",
        name_col="Empresa",
        dy_col="Dividend Yield",
        multiple_col="Preço/VPA",
    ),
}


def _safe_read_parquet(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        logger.warning("Arquivo não encontrado: %s", path)
        return pd.DataFrame()
    try:
        return pd.read_parquet(path)
    except Exception as exc:
        logger.error("Falha ao ler parquet %s: %s", path, exc)
        return pd.DataFrame()


def _safe_to_parquet(df: pd.DataFrame, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_parquet(path, index=False)


def _normalize_ticker(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.upper()


def _percentile_score(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    if numeric.dropna().empty:
        return pd.Series(np.nan, index=values.index, dtype="float64")
    if numeric.dropna().nunique() <= 1:
        return pd.Series(50.0, index=values.index, dtype="float64")
    return numeric.rank(pct=True, method="average") * 100.0


def _model_factories() -> dict[str, Callable[[], object]]:
    factories: dict[str, Callable[[], object]] = {}

    if Pipeline is not None and Ridge is not None and SimpleImputer is not None and StandardScaler is not None:
        factories["score_ridge"] = lambda: Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("model", Ridge(alpha=1.0)),
            ]
        )

    if RandomForestRegressor is not None:
        factories["score_random_forest"] = lambda: RandomForestRegressor(
            n_estimators=250,
            max_depth=7,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        )

    if ExtraTreesRegressor is not None:
        factories["score_extra_trees"] = lambda: ExtraTreesRegressor(
            n_estimators=250,
            max_depth=7,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1,
        )

    if XGBRegressor is not None:
        factories["score_xgboost"] = lambda: XGBRegressor(
            n_estimators=250,
            max_depth=4,
            learning_rate=0.04,
            subsample=0.85,
            colsample_bytree=0.85,
            objective="reg:squarederror",
            random_state=42,
            n_jobs=2,
            verbosity=0,
        )

    if LGBMRegressor is not None:
        factories["score_lightgbm"] = lambda: LGBMRegressor(
            n_estimators=250,
            learning_rate=0.04,
            num_leaves=31,
            min_child_samples=10,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=42,
            verbosity=-1,
        )

    if CatBoostRegressor is not None:
        factories["score_catboost"] = lambda: CatBoostRegressor(
            iterations=250,
            depth=5,
            learning_rate=0.04,
            loss_function="RMSE",
            random_seed=42,
            verbose=False,
            allow_writing_files=False,
        )

    return factories


def _feature_columns(df: pd.DataFrame, spec: AssetSpec, target_col: str) -> list[str]:
    excluded_exact = {
        spec.ticker_col,
        spec.date_col,
        spec.name_col,
        target_col,
        "Ticker",
        "Ticker_norm",
        "Tipo",
        "Status",
    }
    excluded_prefixes = ("Retorno_Futuro_", "Preco_Futuro_", "Data_Futura_")

    numeric_cols = []
    for col in df.columns:
        if col in excluded_exact or any(str(col).startswith(p) for p in excluded_prefixes):
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            numeric_cols.append(col)
        else:
            converted = pd.to_numeric(df[col], errors="coerce")
            if converted.notna().mean() >= 0.80:
                df[col] = converted
                numeric_cols.append(col)

    return numeric_cols


def _prepare_dataset(df: pd.DataFrame, spec: AssetSpec) -> pd.DataFrame:
    required = [spec.ticker_col, spec.date_col, spec.price_col]
    missing = [col for col in required if col not in df.columns]
    if missing:
        logger.warning("Dataset %s sem colunas obrigatórias: %s", spec.tipo, missing)
        return pd.DataFrame()

    out = df.copy()
    out[spec.ticker_col] = _normalize_ticker(out[spec.ticker_col])
    out[spec.date_col] = pd.to_datetime(out[spec.date_col], errors="coerce")
    out = out.dropna(subset=[spec.ticker_col, spec.date_col])
    out = out[out[spec.ticker_col].ne("")]
    out = out.sort_values([spec.date_col, spec.ticker_col]).drop_duplicates(
        [spec.date_col, spec.ticker_col],
        keep="last",
    )
    return out


def _empty_prediction_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "Data_Execucao",
            "Tipo",
            "Ticker",
            "Nome",
            "preco_atual",
            "dy_atual",
            "multiplo_atual",
            "score_top",
            "score_ridge",
            "score_random_forest",
            "score_extra_trees",
            "score_xgboost",
            "score_lightgbm",
            "score_catboost",
            "score_ensemble",
            "retorno_esperado_30d",
            "modelo_lider",
            "status_modelos",
            "motivo_status",
        ]
    )


def _build_latest_base(df: pd.DataFrame, spec: AssetSpec, horizon: int) -> pd.DataFrame:
    latest_date = df[spec.date_col].max()
    latest = df[df[spec.date_col].eq(latest_date)].copy()

    out = pd.DataFrame()
    out["Data_Execucao"] = latest[spec.date_col].dt.strftime("%Y-%m-%d")
    out["Tipo"] = spec.tipo
    out["Ticker"] = latest[spec.ticker_col].astype(str).str.upper().values
    out["Nome"] = latest[spec.name_col].values if spec.name_col and spec.name_col in latest.columns else None
    out["preco_atual"] = pd.to_numeric(latest[spec.price_col], errors="coerce").values
    out["dy_atual"] = pd.to_numeric(latest[spec.dy_col], errors="coerce").values if spec.dy_col and spec.dy_col in latest.columns else np.nan
    out["multiplo_atual"] = pd.to_numeric(latest[spec.multiple_col], errors="coerce").values if spec.multiple_col and spec.multiple_col in latest.columns else np.nan
    out["score_top"] = pd.to_numeric(latest.get("Score"), errors="coerce").values if "Score" in latest.columns else np.nan

    for col in MODEL_SCORE_COLUMNS:
        if col != "score_top":
            out[col] = np.nan

    out[f"retorno_esperado_{horizon}d"] = np.nan
    out["modelo_lider"] = "Score Top"
    out["status_modelos"] = "Aquecendo"
    out["motivo_status"] = "Aguardando histórico suficiente para o horizonte selecionado."
    out["_source_index"] = latest.index.values
    return out


def _train_predict_models(df: pd.DataFrame, spec: AssetSpec, horizon: int) -> pd.DataFrame:
    target_col = f"Retorno_Futuro_{horizon}d"
    predictions = _empty_prediction_frame()

    if df.empty or target_col not in df.columns:
        logger.warning("%s sem target %s para ML.", spec.tipo, target_col)
        return predictions

    data = _prepare_dataset(df, spec)
    if data.empty:
        return predictions

    latest_base = _build_latest_base(data, spec, horizon)
    latest_date = pd.to_datetime(latest_base["Data_Execucao"].iloc[0]) if not latest_base.empty else None
    if latest_date is None:
        return predictions

    feature_cols = _feature_columns(data, spec, target_col)
    if not feature_cols:
        latest_base["motivo_status"] = "Nenhuma feature numérica disponível para treinamento."
        return latest_base.drop(columns=["_source_index"], errors="ignore")

    train = data[
        data[spec.date_col].lt(latest_date)
        & pd.to_numeric(data[target_col], errors="coerce").notna()
    ].copy()

    train_dates = train[spec.date_col].dt.normalize().nunique() if not train.empty else 0
    if len(train) < MIN_TRAIN_ROWS or train_dates < MIN_TRAIN_DATES:
        latest_base["motivo_status"] = (
            f"Aguardando dados: {len(train)} linhas treináveis e {train_dates} datas "
            f"com target {horizon}d. Mínimo: {MIN_TRAIN_ROWS} linhas e {MIN_TRAIN_DATES} datas."
        )
        return latest_base.drop(columns=["_source_index"], errors="ignore")

    latest_rows = data.loc[latest_base["_source_index"].values].copy()
    x_train = train[feature_cols].apply(pd.to_numeric, errors="coerce")
    y_train = pd.to_numeric(train[target_col], errors="coerce")
    x_latest = latest_rows[feature_cols].apply(pd.to_numeric, errors="coerce")

    factories = _model_factories()
    expected_return_cols = []

    for score_col, factory in factories.items():
        try:
            model = factory()
            model.fit(x_train, y_train)
            pred_return = pd.Series(model.predict(x_latest), index=latest_base.index, dtype="float64")
            score = _percentile_score(pred_return)
            latest_base[score_col] = score.values
            latest_base[f"retorno_previsto_{score_col}_{horizon}d"] = pred_return.values
            expected_return_cols.append(f"retorno_previsto_{score_col}_{horizon}d")
            logger.info("Modelo %s treinado para %s.", score_col, spec.tipo)
        except Exception as exc:
            logger.warning("Falha ao treinar %s para %s: %s", score_col, spec.tipo, exc)

    available_score_cols = [
        col for col in [
            "score_ridge",
            "score_random_forest",
            "score_extra_trees",
            "score_xgboost",
            "score_lightgbm",
            "score_catboost",
        ]
        if col in latest_base.columns and pd.to_numeric(latest_base[col], errors="coerce").notna().any()
    ]

    if available_score_cols:
        latest_base["score_ensemble"] = latest_base[available_score_cols].mean(axis=1, skipna=True)
        if expected_return_cols:
            latest_base[f"retorno_esperado_{horizon}d"] = latest_base[expected_return_cols].mean(axis=1, skipna=True)

        def leader(row: pd.Series) -> str:
            values = row[available_score_cols].dropna()
            if values.empty:
                return "Score Top"
            return MODEL_SCORE_COLUMNS.get(values.idxmax(), values.idxmax())

        latest_base["modelo_lider"] = latest_base.apply(leader, axis=1)
        latest_base["status_modelos"] = "Ativo"
        latest_base["motivo_status"] = f"Modelos treinados com {len(train)} linhas e {train_dates} datas."
    else:
        latest_base["status_modelos"] = "Aquecendo"
        latest_base["motivo_status"] = "Nenhum modelo supervisionado disponível; usando Score Top como baseline."

    return latest_base.drop(columns=["_source_index"], errors="ignore")


def _append_predictions(new_predictions: pd.DataFrame, path: str) -> pd.DataFrame:
    if new_predictions.empty:
        return _safe_read_parquet(path)

    existing = _safe_read_parquet(path)
    combined = pd.concat([existing, new_predictions], ignore_index=True, sort=False) if not existing.empty else new_predictions.copy()
    combined["Data_Execucao"] = pd.to_datetime(combined["Data_Execucao"], errors="coerce").dt.strftime("%Y-%m-%d")
    combined["Ticker"] = _normalize_ticker(combined["Ticker"])
    combined = combined.dropna(subset=["Data_Execucao", "Ticker"])
    combined = combined.drop_duplicates(["Data_Execucao", "Tipo", "Ticker"], keep="last")
    combined = combined.sort_values(["Tipo", "Data_Execucao", "Ticker"]).reset_index(drop=True)
    _safe_to_parquet(combined, path)
    logger.info("Previsões ML salvas: %s (%s linhas)", path, len(combined))
    return combined


def _performance_for_predictions(pred: pd.DataFrame, dataset: pd.DataFrame, spec: AssetSpec, horizon: int) -> pd.DataFrame:
    target_col = f"Retorno_Futuro_{horizon}d"
    if pred.empty or dataset.empty or target_col not in dataset.columns:
        return pd.DataFrame()

    target = dataset[[spec.date_col, spec.ticker_col, target_col]].copy()
    target["Data_Execucao"] = pd.to_datetime(target[spec.date_col], errors="coerce").dt.strftime("%Y-%m-%d")
    target["Ticker"] = _normalize_ticker(target[spec.ticker_col])
    target[target_col] = pd.to_numeric(target[target_col], errors="coerce")
    target = target.dropna(subset=["Data_Execucao", "Ticker", target_col])
    if target.empty:
        return pd.DataFrame()

    base = pred.copy()
    base["Data_Execucao"] = pd.to_datetime(base["Data_Execucao"], errors="coerce").dt.strftime("%Y-%m-%d")
    base["Ticker"] = _normalize_ticker(base["Ticker"])
    merged = base.merge(target[["Data_Execucao", "Ticker", target_col]], on=["Data_Execucao", "Ticker"], how="inner")
    if merged.empty:
        return pd.DataFrame()

    rows = []
    baseline_returns = {}

    for model_col, model_name in MODEL_SCORE_COLUMNS.items():
        if model_col not in merged.columns:
            continue
        model_data = merged[pd.to_numeric(merged[model_col], errors="coerce").notna()].copy()
        if model_data.empty:
            continue

        top_returns = []
        hit_rates = []
        ic_values = []
        valid_windows = 0

        for date, group in model_data.groupby("Data_Execucao"):
            group = group.copy()
            if len(group) < 5:
                continue
            valid_windows += 1
            group["_score"] = pd.to_numeric(group[model_col], errors="coerce")
            group["_target"] = pd.to_numeric(group[target_col], errors="coerce")
            top = group.sort_values("_score", ascending=False).head(TOP_N_PERFORMANCE)
            top_return = top["_target"].mean()
            top_returns.append(top_return)
            hit_rates.append((top["_target"] > 0).mean())
            ic = group[["_score", "_target"]].corr(method="spearman").iloc[0, 1]
            if pd.notna(ic):
                ic_values.append(ic)
            if model_col == "score_top":
                baseline_returns[date] = top_return

        if valid_windows == 0:
            continue

        retorno_medio = float(np.nanmean(top_returns)) if top_returns else np.nan
        hit_rate = float(np.nanmean(hit_rates)) if hit_rates else np.nan
        spearman_ic = float(np.nanmean(ic_values)) if ic_values else np.nan

        alpha = np.nan
        if model_col != "score_top" and baseline_returns:
            diffs = []
            for date, group in model_data.groupby("Data_Execucao"):
                if date not in baseline_returns or len(group) < 5:
                    continue
                group = group.copy()
                group["_score"] = pd.to_numeric(group[model_col], errors="coerce")
                top = group.sort_values("_score", ascending=False).head(TOP_N_PERFORMANCE)
                diffs.append(top[target_col].mean() - baseline_returns[date])
            if diffs:
                alpha = float(np.nanmean(diffs))
        elif model_col == "score_top":
            alpha = 0.0

        rows.append(
            {
                "Tipo": spec.tipo,
                "Modelo": model_name,
                "Horizonte": f"{horizon}d",
                "Janelas_Validas": int(valid_windows),
                "Retorno_Medio_Top20": retorno_medio,
                "Hit_Rate_Top20": hit_rate,
                "Spearman_IC": spearman_ic,
                "Alpha_vs_Score_Top": alpha,
                "Status": "Ativo" if valid_windows >= 1 else "Aquecendo",
            }
        )

    return pd.DataFrame(rows)


def _warmup_performance_rows(tipo: str, horizon: int) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Tipo": tipo,
                "Modelo": model_name,
                "Horizonte": f"{horizon}d",
                "Janelas_Validas": 0,
                "Retorno_Medio_Top20": np.nan,
                "Hit_Rate_Top20": np.nan,
                "Spearman_IC": np.nan,
                "Alpha_vs_Score_Top": 0.0 if model_col == "score_top" else np.nan,
                "Status": "Aquecendo",
            }
            for model_col, model_name in MODEL_SCORE_COLUMNS.items()
        ]
    )


def run_ml_pipeline(
    data_dir: str = "data",
    horizon: int = DEFAULT_HORIZON,
) -> dict[str, pd.DataFrame]:
    """Executa a camada ML em modo sombra.

    A função é segura para rodar diariamente. Ela não altera rankings oficiais,
    não sobrescreve históricos principais e só atualiza os parquets próprios da
    camada de modelos.
    """
    ml_dir = os.path.join(data_dir, "ml")
    os.makedirs(ml_dir, exist_ok=True)

    all_predictions: dict[str, pd.DataFrame] = {}
    performance_frames = []

    if OPTIONAL_IMPORT_ERRORS:
        logger.warning("Dependências opcionais indisponíveis: %s", OPTIONAL_IMPORT_ERRORS)

    for key, spec in SPECS.items():
        dataset_path = os.path.join(ml_dir, spec.dataset_filename)
        predictions_path = os.path.join(ml_dir, spec.predictions_filename)

        dataset = _safe_read_parquet(dataset_path)
        prediction_today = _train_predict_models(dataset, spec, horizon=horizon)
        predictions_all = _append_predictions(prediction_today, predictions_path)
        all_predictions[key] = predictions_all

        perf = _performance_for_predictions(predictions_all, dataset, spec, horizon=horizon)
        if perf.empty:
            perf = _warmup_performance_rows(spec.tipo, horizon)
        performance_frames.append(perf)

    performance = pd.concat(performance_frames, ignore_index=True, sort=False) if performance_frames else pd.DataFrame()
    performance_path = os.path.join(ml_dir, "model_performance.parquet")
    if not performance.empty:
        performance = performance.sort_values(["Tipo", "Modelo", "Horizonte"]).reset_index(drop=True)
        _safe_to_parquet(performance, performance_path)
        logger.info("Performance ML salva: %s (%s linhas)", performance_path, len(performance))

    return {
        "predictions_fiis": all_predictions.get("fiis", pd.DataFrame()),
        "predictions_acoes": all_predictions.get("acoes", pd.DataFrame()),
        "performance": performance,
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )
    run_ml_pipeline()
