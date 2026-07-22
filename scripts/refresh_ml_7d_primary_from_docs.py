from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ml_models import run_ml_pipeline
from src.exporter import _calc_modelos_ml

DOCS_DATA = ROOT / "docs" / "data"
ML_DIR = ROOT / "data" / "ml"
HORIZONS = (7, 30, 60, 90)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _snapshot_files() -> list[Path]:
    files = sorted([p for p in DOCS_DATA.glob("*.json") if p.name != "index.json"], key=lambda p: p.stem)
    if not files:
        raise RuntimeError("Não encontrei snapshots em docs/data/*.json")
    return files


def _decode_scalar(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _first_present(row: dict[str, Any], candidates: Iterable[str]) -> Any:
    for key in candidates:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _parse_number(value: Any) -> float | None:
    value = _decode_scalar(value)
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
        return float(value)

    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "null", "-", "—", "<na>"}:
        return None

    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]

    s = s.replace("R$", "").replace("%", "").replace("\u00a0", " ").strip()
    s = re.sub(r"[^0-9,\.\-+]", "", s)
    if not s or s in {",", ".", "-", "+"}:
        return None

    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        parts = s.split(".")
        if len(parts) > 2:
            s = "".join(parts[:-1]) + "." + parts[-1]

    try:
        out = float(s)
        return -out if neg else out
    except Exception:
        return None


def _to_number_series(s: pd.Series) -> pd.Series:
    return s.map(_parse_number).astype("float64")


def _ticker_text(v: Any) -> str | None:
    v = _decode_scalar(v)
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    s = str(v).strip().upper()
    if not s or s in {"NAN", "NONE", "NULL", "<NA>"}:
        return None
    return s


def _normalize_rows_from_docs() -> tuple[pd.DataFrame, pd.DataFrame]:
    fii_rows: list[dict[str, Any]] = []
    acao_rows: list[dict[str, Any]] = []

    for path in _snapshot_files():
        payload = _load_json(path)
        data = str(payload.get("data") or path.stem)[:10]

        for raw in payload.get("fiis", []) or []:
            if not isinstance(raw, dict):
                continue
            row = {k: _decode_scalar(v) for k, v in raw.items()}
            ticker = _ticker_text(_first_present(row, ["FUNDOS", "Ticker", "ticker", "Ativo", "Código", "Codigo"]))
            price = _first_present(row, ["PREÇO ATUAL (R$)", "Preço", "PRECO", "Preço Atual", "preco_atual", "price"])
            score = _first_present(row, ["Score", "score", "score_top"])
            if not ticker:
                continue
            row["FUNDOS"] = ticker
            row["PREÇO ATUAL (R$)"] = price
            if score is not None:
                row["Score"] = score
                row["score"] = score
            row["Data_Execucao"] = data
            fii_rows.append(row)

        for raw in payload.get("acoes", []) or []:
            if not isinstance(raw, dict):
                continue
            row = {k: _decode_scalar(v) for k, v in raw.items()}
            ticker = _ticker_text(_first_present(row, ["Ação", "Acao", "Ticker", "ticker", "Ativo", "Código", "Codigo", "Papel"]))
            price = _first_present(row, ["Preço", "PREÇO", "PRECO", "Preço Atual", "PREÇO ATUAL (R$)", "preco_atual", "price"])
            score = _first_present(row, ["Score", "score", "score_top"])
            if not ticker:
                continue
            row["Ação"] = ticker
            row["Preço"] = price
            if score is not None:
                row["Score"] = score
                row["score"] = score
            row["Data_Execucao"] = data
            acao_rows.append(row)

    fiis = pd.DataFrame(fii_rows)
    acoes = pd.DataFrame(acao_rows)
    return fiis, acoes


def _numericize_common(df: pd.DataFrame, id_col: str, date_col: str, price_col: str) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    out[id_col] = out[id_col].map(_ticker_text).astype("string")
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
    out[price_col] = _to_number_series(out[price_col])

    # Converte colunas que são claramente numéricas ou majoritariamente numéricas.
    always_text = {id_col, date_col, "Empresa", "SETOR", "Nome", "Status", "modelo_lider", "motivo_status", "tendencias"}
    for col in list(out.columns):
        if col in always_text:
            if col not in {id_col, date_col}:
                out[col] = out[col].map(_decode_scalar).astype("string")
            continue
        if col == price_col:
            continue

        parsed = out[col].map(_parse_number)
        valid_raw = out[col].notna().sum()
        valid_num = parsed.notna().sum()
        name = str(col).lower()
        numeric_name = any(x in name for x in [
            "preço", "preco", "price", "score", "yield", "dy", "p/vp", "p/vpa",
            "volume", "liquidez", "patrim", "market", "ev/", "margem", "roa",
            "rpl", "vpa", "volatil", "cotistas", "lucro", "retorno", "delta",
        ])
        if numeric_name or (valid_raw and valid_num / valid_raw >= 0.85):
            out[col] = parsed.astype("float64")
        else:
            out[col] = out[col].map(_decode_scalar).astype("string")

    out = out.dropna(subset=[id_col, date_col, price_col])
    out = out[out[id_col].astype(str).str.strip().ne("")]
    out = out.sort_values([date_col, id_col]).drop_duplicates([date_col, id_col], keep="last")
    return out.reset_index(drop=True)


def _add_basic_features(df: pd.DataFrame, id_col: str, date_col: str, price_col: str) -> pd.DataFrame:
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
    out = out.sort_values([id_col, date_col]).reset_index(drop=True)

    out["Preco_Anterior"] = out.groupby(id_col)[price_col].shift(1)
    out["Retorno_Desde_Snapshot_Anterior"] = out[price_col] / out["Preco_Anterior"] - 1.0
    out["Dias_Desde_Snapshot_Anterior"] = out.groupby(id_col)[date_col].diff().dt.days

    if "Score" in out.columns:
        out["Score"] = pd.to_numeric(out["Score"], errors="coerce")
        out["Score_Anterior"] = out.groupby(id_col)["Score"].shift(1)
        out["Delta_Score"] = out["Score"] - out["Score_Anterior"]

    return out


def _add_future_returns(df: pd.DataFrame, id_col: str, date_col: str, price_col: str, horizons: Iterable[int]) -> pd.DataFrame:
    out = df.copy()

    for horizon in horizons:
        out[f"Preco_Futuro_{horizon}d"] = np.nan
        out[f"Data_Futura_{horizon}d"] = pd.NaT
        out[f"Retorno_Futuro_{horizon}d"] = np.nan

    frames: list[pd.DataFrame] = []
    for _, group in out.groupby(id_col, sort=False):
        group = group.sort_values(date_col).copy()
        dates = group[date_col].tolist()
        prices = group[price_col].tolist()

        for idx, row in group.iterrows():
            current_date = row[date_col]
            current_price = row[price_col]
            if pd.isna(current_date) or pd.isna(current_price) or float(current_price) == 0:
                continue

            for horizon in horizons:
                target_date = current_date + pd.Timedelta(days=horizon)
                future_idx = None
                for pos, candidate_date in enumerate(dates):
                    if candidate_date >= target_date:
                        future_idx = pos
                        break
                if future_idx is None:
                    continue

                future_date = dates[future_idx]
                future_price = prices[future_idx]
                if pd.isna(future_price) or float(future_price) == 0:
                    continue

                group.at[idx, f"Preco_Futuro_{horizon}d"] = future_price
                group.at[idx, f"Data_Futura_{horizon}d"] = future_date
                group.at[idx, f"Retorno_Futuro_{horizon}d"] = (float(future_price) / float(current_price)) - 1.0

        frames.append(group)

    if not frames:
        return out

    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values([date_col, id_col]).reset_index(drop=True)
    return out


def _build_dataset(history: pd.DataFrame, id_col: str, date_col: str, price_col: str) -> pd.DataFrame:
    base = _numericize_common(history, id_col, date_col, price_col)
    enriched = _add_basic_features(base, id_col, date_col, price_col)
    enriched = _add_future_returns(enriched, id_col, date_col, price_col, HORIZONS)
    enriched[date_col] = pd.to_datetime(enriched[date_col], errors="coerce").dt.strftime("%Y-%m-%d")

    for horizon in HORIZONS:
        dcol = f"Data_Futura_{horizon}d"
        if dcol in enriched.columns:
            enriched[dcol] = pd.to_datetime(enriched[dcol], errors="coerce").dt.strftime("%Y-%m-%d")

    return enriched


def _save_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def _rebuild_index() -> None:
    datas = sorted([p.stem for p in DOCS_DATA.glob("*.json") if p.name != "index.json"], reverse=True)
    (DOCS_DATA / "index.json").write_text(json.dumps(datas, ensure_ascii=False, indent=2), encoding="utf-8")


def _latest_dashboard_payload() -> tuple[str, Path, dict[str, Any]]:
    latest_path = _snapshot_files()[-1]
    payload = _load_json(latest_path)
    latest = str(payload.get("data") or latest_path.stem)[:10]
    return latest, latest_path, payload


def _count_valid(df: pd.DataFrame, col: str) -> int:
    if col not in df.columns:
        return 0
    return int(pd.to_numeric(df[col], errors="coerce").notna().sum())


def _period(df: pd.DataFrame, date_col: str = "Data_Execucao") -> str:
    if df.empty or date_col not in df.columns:
        return "sem datas"
    d = pd.to_datetime(df[date_col], errors="coerce")
    return f"{d.min().date()} até {d.max().date()} | {d.dt.normalize().nunique()} datas"


def main() -> None:
    print("Reconstruindo histórico ML direto de docs/data/*.json...")
    raw_fiis, raw_acoes = _normalize_rows_from_docs()

    hist_fiis = _numericize_common(raw_fiis, "FUNDOS", "Data_Execucao", "PREÇO ATUAL (R$)")
    hist_acoes = _numericize_common(raw_acoes, "Ação", "Data_Execucao", "Preço")

    _save_parquet(hist_fiis, ML_DIR / "historico_fiis.parquet")
    _save_parquet(hist_acoes, ML_DIR / "historico_acoes.parquet")

    print(f"[OK] historico_fiis: {len(hist_fiis)} linhas | {_period(hist_fiis)}")
    print(f"[OK] historico_acoes: {len(hist_acoes)} linhas | {_period(hist_acoes)}")

    print("\nGerando datasets com targets 7d e 30d...")
    dataset_fiis = _build_dataset(hist_fiis, "FUNDOS", "Data_Execucao", "PREÇO ATUAL (R$)")
    dataset_acoes = _build_dataset(hist_acoes, "Ação", "Data_Execucao", "Preço")

    _save_parquet(dataset_fiis, ML_DIR / "dataset_fiis.parquet")
    _save_parquet(dataset_acoes, ML_DIR / "dataset_acoes.parquet")

    print(f"[OK] dataset_fiis: {len(dataset_fiis)} linhas | {_period(dataset_fiis)}")
    print(f"     Retorno_Futuro_7d: {_count_valid(dataset_fiis, 'Retorno_Futuro_7d')} válidos")
    print(f"     Retorno_Futuro_30d: {_count_valid(dataset_fiis, 'Retorno_Futuro_30d')} válidos")

    print(f"[OK] dataset_acoes: {len(dataset_acoes)} linhas | {_period(dataset_acoes)}")
    print(f"     Retorno_Futuro_7d: {_count_valid(dataset_acoes, 'Retorno_Futuro_7d')} válidos")
    print(f"     Retorno_Futuro_30d: {_count_valid(dataset_acoes, 'Retorno_Futuro_30d')} válidos")

    print("\nRodando ML com horizonte principal 7d...")
    run_ml_pipeline(data_dir="data", horizon=7)

    latest, json_path, payload = _latest_dashboard_payload()
    print(f"\nAtualizando JSON do dashboard: {latest}")

    payload["modelos_ml"] = _calc_modelos_ml()
    payload["modelos_ml"]["horizonte_principal"] = "7d"
    payload["modelos_ml"]["horizonte_estrategico"] = "30d"
    payload["modelos_ml"]["observacao"] = (
        "O horizonte 7d é usado como modelo inicial porque já possui amostra validável. "
        "O horizonte 30d segue em maturação até acumular mais exemplos."
    )
    payload["modelos_ml"]["maturacao_30d"] = {
        "status": "Maturando",
        "retornos_validos_acoes": _count_valid(dataset_acoes, "Retorno_Futuro_30d"),
        "retornos_validos_fiis": _count_valid(dataset_fiis, "Retorno_Futuro_30d"),
    }

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _rebuild_index()

    ml = payload.get("modelos_ml", {})
    ranking = ml.get("ranking", {})
    perf = ml.get("performance", [])

    print("\nOK.")
    print(f"Status ML: {ml.get('status')}")
    print(f"Horizonte principal: {ml.get('horizonte_principal')}")
    print(f"Ações no ranking: {len(ranking.get('acoes', []))}")
    print(f"FIIs no ranking: {len(ranking.get('fiis', []))}")
    print(f"Performance: {len(perf)} linhas")
    print(f"JSON atualizado: {json_path}")


if __name__ == "__main__":
    main()
