"""data_lake.py — camada de dados escalável do stock screener.

Princípios:
- data/lake/snapshots/YYYY-MM-DD/ é a fonte incremental oficial.
- data/ml/*.parquet e data/backtest/*.parquet continuam existindo como derivados/cache.
- docs/data/*.json é camada leve para dashboard.
- Nenhuma rotina apaga snapshots históricos de datas anteriores.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LakeFileInfo:
    name: str
    path: str
    rows: int
    columns: int
    sha256: str | None


def _safe_df(df: pd.DataFrame | None) -> pd.DataFrame:
    return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()


def _atomic_write_parquet(df: pd.DataFrame, path: Path) -> None:
    """Escreve parquet de forma segura usando arquivo temporário no mesmo diretório."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as exc:
        logger.warning("Nao foi possivel calcular hash de %s: %s", path, exc)
        return None


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Nao foi possivel ler JSON %s: %s", path, exc)
        return default


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _normal_date(date_str: str | None = None) -> str:
    if date_str:
        return pd.to_datetime(date_str).strftime("%Y-%m-%d")
    return datetime.today().strftime("%Y-%m-%d")


def _snapshot_dir(data_dir: str | Path, data_execucao: str) -> Path:
    return Path(data_dir) / "lake" / "snapshots" / _normal_date(data_execucao)


def _write_frame(snapshot_dir: Path, filename: str, df: pd.DataFrame | None) -> LakeFileInfo:
    frame = _safe_df(df)
    path = snapshot_dir / filename
    _atomic_write_parquet(frame, path)
    return LakeFileInfo(
        name=filename,
        path=str(path).replace("\\", "/"),
        rows=int(len(frame)),
        columns=int(len(frame.columns)),
        sha256=_sha256(path),
    )


def _ensure_exec_date(df: pd.DataFrame, date_str: str, date_col: str = "Data_Execucao") -> pd.DataFrame:
    out = df.copy()
    if date_col not in out.columns:
        out[date_col] = date_str
    else:
        out[date_col] = pd.to_datetime(out[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
        out[date_col] = out[date_col].fillna(date_str)
    return out


def save_lake_snapshot(
    data_dir: str | Path,
    data_execucao: str,
    fii_universe: pd.DataFrame | None = None,
    acoes_universe: pd.DataFrame | None = None,
    top_fiis: pd.DataFrame | None = None,
    top_acoes: pd.DataFrame | None = None,
    carteira_snapshot: pd.DataFrame | None = None,
) -> dict:
    """Salva snapshot diário incremental em data/lake/snapshots/YYYY-MM-DD/.

    Reexecutar o mesmo dia substitui apenas a pasta daquele dia. Datas anteriores
    não são tocadas.
    """
    date_str = _normal_date(data_execucao)
    snap_dir = _snapshot_dir(data_dir, date_str)
    snap_dir.mkdir(parents=True, exist_ok=True)

    files = [
        _write_frame(snap_dir, "fii_universe.parquet", _ensure_exec_date(_safe_df(fii_universe), date_str)),
        _write_frame(snap_dir, "acoes_universe.parquet", _ensure_exec_date(_safe_df(acoes_universe), date_str)),
        _write_frame(snap_dir, "top_fiis.parquet", _safe_df(top_fiis)),
        _write_frame(snap_dir, "top_acoes.parquet", _safe_df(top_acoes)),
    ]

    if carteira_snapshot is not None:
        files.append(_write_frame(snap_dir, "carteira.parquet", carteira_snapshot))

    manifest = {
        "data_execucao": date_str,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "layer": "lake_snapshot",
        "schema_version": 1,
        "files": [info.__dict__ for info in files],
    }
    _write_json(snap_dir / "manifest.json", manifest)
    update_lake_manifest(data_dir)
    logger.info("Snapshot incremental do data lake salvo em %s", snap_dir)
    return manifest


def list_lake_dates(data_dir: str | Path) -> list[str]:
    root = Path(data_dir) / "lake" / "snapshots"
    if not root.exists():
        return []
    dates = []
    for p in root.iterdir():
        if not p.is_dir():
            continue
        try:
            dates.append(pd.to_datetime(p.name).strftime("%Y-%m-%d"))
        except Exception:
            continue
    return sorted(set(dates))


def update_lake_manifest(data_dir: str | Path) -> dict:
    """Reconstrói o manifesto global a partir dos snapshots existentes."""
    data_dir = Path(data_dir)
    root = data_dir / "lake" / "snapshots"
    manifest_path = data_dir / "lake" / "manifest.json"

    snapshots = []
    for date_str in list_lake_dates(data_dir):
        snap_manifest = _load_json(root / date_str / "manifest.json", {})
        files = snap_manifest.get("files", []) if isinstance(snap_manifest, dict) else []
        snapshots.append({
            "data_execucao": date_str,
            "files": files,
            "total_rows": int(sum(int(f.get("rows", 0) or 0) for f in files if isinstance(f, dict))),
        })

    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "latest": snapshots[-1]["data_execucao"] if snapshots else None,
        "total_snapshots": len(snapshots),
        "snapshots": snapshots,
    }
    _write_json(manifest_path, payload)
    return payload


def read_lake_dataset(data_dir: str | Path, filename: str, dates: Iterable[str] | None = None) -> pd.DataFrame:
    """Lê e concatena um arquivo específico de todos os snapshots.

    Exemplo: read_lake_dataset("data", "acoes_universe.parquet")
    """
    selected_dates = list(dates) if dates is not None else list_lake_dates(data_dir)
    frames = []
    for date_str in selected_dates:
        path = _snapshot_dir(data_dir, date_str) / filename
        if not path.exists():
            continue
        try:
            df = pd.read_parquet(path)
            df = _ensure_exec_date(df, date_str)
            frames.append(df)
        except Exception as exc:
            logger.warning("Nao foi possivel ler snapshot %s: %s", path, exc)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def _dedupe_history(df: pd.DataFrame, subset: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    existing = [c for c in subset if c in df.columns]
    out = df.copy()
    for c in existing:
        if "Data" in c:
            out[c] = pd.to_datetime(out[c], errors="coerce").dt.strftime("%Y-%m-%d")
    if existing:
        out = out.drop_duplicates(subset=existing, keep="last")
    return out.reset_index(drop=True)


def _portfolio_from_top(df: pd.DataFrame, tipo: str, date_str: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Data_Carteira", "Tipo", "Ticker", "Preco_Entrada", "Score", "Posicao"])

    if tipo == "FII":
        ticker_col = "FUNDOS"
        price_candidates = ["PREÇO ATUAL (R$)", "Preço", "Preco", "Preço Atual"]
    else:
        ticker_col = "Ação"
        price_candidates = ["Preço", "PREÇO ATUAL (R$)", "Preco"]

    if ticker_col not in df.columns:
        return pd.DataFrame(columns=["Data_Carteira", "Tipo", "Ticker", "Preco_Entrada", "Score", "Posicao"])

    price_col = next((c for c in price_candidates if c in df.columns), None)
    score_col = "Score" if "Score" in df.columns else None

    out = pd.DataFrame()
    out["Data_Carteira"] = date_str
    out["Tipo"] = tipo
    out["Ticker"] = df[ticker_col].astype(str).str.strip().str.upper()
    out["Preco_Entrada"] = pd.to_numeric(df[price_col], errors="coerce") if price_col else pd.NA
    out["Score"] = pd.to_numeric(df[score_col], errors="coerce") if score_col else pd.NA
    out["Posicao"] = range(1, len(out) + 1)
    return out


def rebuild_legacy_tables_from_lake(data_dir: str | Path = "data") -> dict:
    """Reconstrói parquets consolidados derivados a partir do data lake.

    Útil quando algum parquet consolidado é corrompido, quando o histórico precisa
    ser auditado ou quando a pipeline deve ser reconstruída do zero.
    """
    data_dir = Path(data_dir)
    ml_dir = data_dir / "ml"
    backtest_dir = data_dir / "backtest"
    ml_dir.mkdir(parents=True, exist_ok=True)
    backtest_dir.mkdir(parents=True, exist_ok=True)

    fiis = read_lake_dataset(data_dir, "fii_universe.parquet")
    acoes = read_lake_dataset(data_dir, "acoes_universe.parquet")

    if not fiis.empty:
        fiis = _dedupe_history(fiis, ["Data_Execucao", "FUNDOS"])
        _atomic_write_parquet(fiis, ml_dir / "historico_fiis.parquet")

    if not acoes.empty:
        acoes = _dedupe_history(acoes, ["Data_Execucao", "Ação"])
        _atomic_write_parquet(acoes, ml_dir / "historico_acoes.parquet")

    carteira_frames = []
    carteira_direct = read_lake_dataset(data_dir, "carteira.parquet")
    if not carteira_direct.empty and {"Data_Carteira", "Tipo", "Ticker"}.issubset(carteira_direct.columns):
        carteira_frames.append(carteira_direct)

    for date_str in list_lake_dates(data_dir):
        top_fiis_path = _snapshot_dir(data_dir, date_str) / "top_fiis.parquet"
        top_acoes_path = _snapshot_dir(data_dir, date_str) / "top_acoes.parquet"
        try:
            if top_fiis_path.exists():
                carteira_frames.append(_portfolio_from_top(pd.read_parquet(top_fiis_path), "FII", date_str))
            if top_acoes_path.exists():
                carteira_frames.append(_portfolio_from_top(pd.read_parquet(top_acoes_path), "ACAO", date_str))
        except Exception as exc:
            logger.warning("Falha ao reconstruir carteira do snapshot %s: %s", date_str, exc)

    if carteira_frames:
        carteira = pd.concat(carteira_frames, ignore_index=True, sort=False)
        carteira = _dedupe_history(carteira, ["Data_Carteira", "Tipo", "Ticker"])
        if not carteira.empty:
            carteira["Data_Carteira"] = pd.to_datetime(carteira["Data_Carteira"], errors="coerce").dt.strftime("%Y-%m-%d")
            carteira = carteira.sort_values(["Data_Carteira", "Tipo", "Posicao", "Ticker"], na_position="last")
        _atomic_write_parquet(carteira, backtest_dir / "carteiras_historicas.parquet")
    else:
        carteira = pd.DataFrame()

    result = {
        "historico_fiis_rows": int(len(fiis)),
        "historico_acoes_rows": int(len(acoes)),
        "carteiras_rows": int(len(carteira)),
    }
    logger.info("Reconstrução lake → consolidados concluída: %s", result)
    return result


def rebuild_dashboard_index(output_dir: str | Path) -> list[str]:
    """Reconstrói docs/data/index.json com base nos JSONs existentes."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    dates = []
    for p in output_dir.glob("*.json"):
        if p.stem == "index":
            continue
        try:
            dates.append(pd.to_datetime(p.stem).strftime("%Y-%m-%d"))
        except Exception:
            continue
    dates = sorted(set(dates), reverse=True)
    _write_json(output_dir / "index.json", dates)
    logger.info("Indice do dashboard reconstruido com %s datas.", len(dates))
    return dates


def run_data_quality_checks(data_dir: str | Path, dashboard_dir: str | Path | None = None) -> dict:
    """Executa checagens leves para detectar problemas antes do commit/deploy."""
    data_dir = Path(data_dir)
    checks: list[dict] = []

    def add_check(name: str, status: str, detail: str = ""):
        checks.append({"name": name, "status": status, "detail": detail})

    dates = list_lake_dates(data_dir)
    add_check(
        "lake_snapshots",
        "ok" if dates else "warn",
        f"{len(dates)} snapshots encontrados" if dates else "nenhum snapshot incremental encontrado",
    )

    latest_lake = dates[-1] if dates else None
    manifest = update_lake_manifest(data_dir)
    add_check("lake_manifest", "ok" if manifest.get("total_snapshots", 0) == len(dates) else "warn", f"latest={manifest.get('latest')}")

    required_snapshot_files = ["fii_universe.parquet", "acoes_universe.parquet", "top_fiis.parquet", "top_acoes.parquet", "manifest.json"]
    for date_str in dates[-5:]:
        snap = _snapshot_dir(data_dir, date_str)
        missing = [name for name in required_snapshot_files if not (snap / name).exists()]
        add_check(f"snapshot_{date_str}_files", "ok" if not missing else "error", "ok" if not missing else f"faltando: {missing}")

    legacy_files = [
        data_dir / "ml" / "historico_fiis.parquet",
        data_dir / "ml" / "historico_acoes.parquet",
        data_dir / "backtest" / "carteiras_historicas.parquet",
        data_dir / "ml" / "dataset_fiis.parquet",
        data_dir / "ml" / "dataset_acoes.parquet",
        data_dir / "ml" / "model_predictions_fiis.parquet",
        data_dir / "ml" / "model_predictions_acoes.parquet",
        data_dir / "ml" / "model_performance.parquet",
    ]
    for path in legacy_files:
        if not path.exists():
            add_check(path.as_posix(), "warn", "arquivo não encontrado")
            continue
        try:
            df = pd.read_parquet(path)
            add_check(path.as_posix(), "ok" if len(df) > 0 else "warn", f"{len(df)} linhas")
        except Exception as exc:
            add_check(path.as_posix(), "error", str(exc))

    for path, subset in [
        (data_dir / "ml" / "historico_fiis.parquet", ["Data_Execucao", "FUNDOS"]),
        (data_dir / "ml" / "historico_acoes.parquet", ["Data_Execucao", "Ação"]),
        (data_dir / "backtest" / "carteiras_historicas.parquet", ["Data_Carteira", "Tipo", "Ticker"]),
    ]:
        if not path.exists():
            continue
        try:
            df = pd.read_parquet(path)
            if set(subset).issubset(df.columns):
                dups = int(df.duplicated(subset=subset).sum())
                add_check(f"duplicatas_{path.name}", "ok" if dups == 0 else "error", f"{dups} duplicatas em {subset}")
            else:
                add_check(f"colunas_{path.name}", "error", f"faltam colunas: {sorted(set(subset) - set(df.columns))}")
        except Exception as exc:
            add_check(f"duplicatas_{path.name}", "error", str(exc))

    carteira_path = data_dir / "backtest" / "carteiras_historicas.parquet"
    if carteira_path.exists():
        try:
            cart = pd.read_parquet(carteira_path)
            required = {"Data_Carteira", "Tipo", "Ticker"}
            if required.issubset(cart.columns):
                counts = cart.groupby(["Data_Carteira", "Tipo"]).size()
                unusual = counts[(counts < 15) | (counts > 25)]
                add_check(
                    "carteira_tamanho_top",
                    "ok" if unusual.empty else "warn",
                    "tamanhos dentro do esperado" if unusual.empty else unusual.to_string(),
                )
        except Exception as exc:
            add_check("carteira_checks", "error", str(exc))

    if dashboard_dir is not None:
        dashboard_dir = Path(dashboard_dir)
        json_dates = rebuild_dashboard_index(dashboard_dir)
        add_check("dashboard_index", "ok" if json_dates else "warn", f"{len(json_dates)} datas no index.json")
        if latest_lake and json_dates:
            add_check(
                "dashboard_latest_vs_lake",
                "ok" if json_dates[0] >= latest_lake else "warn",
                f"dashboard_latest={json_dates[0]}, lake_latest={latest_lake}",
            )

    status = "ok"
    if any(c["status"] == "error" for c in checks):
        status = "error"
    elif any(c["status"] == "warn" for c in checks):
        status = "warn"

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "checks": checks,
    }

    report_path = data_dir / "lake" / "quality_report.json"
    _write_json(report_path, report)
    logger.info("Relatorio de qualidade salvo em %s com status %s", report_path, status)
    return report
