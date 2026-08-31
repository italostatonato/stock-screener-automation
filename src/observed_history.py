"""Reconstrói as carteiras que foram efetivamente publicadas.

Esta camada é deliberadamente separada do data lake de universos completos.
Um JSON do dashboard contém apenas o Top N; promovê-lo a ``*_universe``
inventaria observações ausentes e contaminaria datasets de ML.
"""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

logger = logging.getLogger(__name__)

OBSERVED_COLUMNS = [
    "Data_Carteira",
    "Tipo",
    "Ticker",
    "Preco_Entrada",
    "Score",
    "Posicao",
    "Origem",
    "Natureza",
    "Strategy_Version",
    "Tipo_Completo",
    "Snapshot_Completo",
    "Schema_Version",
]

_TICKER_RE = re.compile(r"^[A-Z]{4}[A-Z0-9]{1,3}$")


def _normalize_label(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)

    text = str(value).strip().replace("R$", "").replace("%", "")
    text = re.sub(r"[^0-9,\.\-+]", "", text)
    if not text or text in {"-", "+", ".", ","}:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _ticker_from_row(row: dict[str, Any], tipo: str) -> str | None:
    preferred = ("FUNDOS",) if tipo == "FII" else ("Ação", "Acao", "AÇÃO", "Ticker", "Papel")
    normalized = {_normalize_label(key): value for key, value in row.items()}
    for key in preferred:
        value = normalized.get(_normalize_label(key))
        if value is not None:
            ticker = str(value).strip().upper()
            if _TICKER_RE.fullmatch(ticker):
                return ticker

    # Alguns JSONs antigos perderam os bytes dos acentos ("A��o"). O valor
    # continua íntegro, então a forma segura é reconhecer o próprio ticker.
    for value in row.values():
        ticker = str(value).strip().upper()
        if _TICKER_RE.fullmatch(ticker):
            return ticker
    return None


def _field(row: dict[str, Any], aliases: Iterable[str]) -> Any:
    normalized = {_normalize_label(key): value for key, value in row.items()}
    for alias in aliases:
        value = normalized.get(_normalize_label(alias))
        if value not in (None, ""):
            return value
    return None


def _price_from_row(row: dict[str, Any], tipo: str) -> float | None:
    aliases = (
        ("PREÇO ATUAL (R$)", "PRECO ATUAL (R$)", "Preço", "Preco", "price")
        if tipo == "FII"
        else ("Preço", "Preco", "PREÇO ATUAL (R$)", "PRECO ATUAL (R$)", "price")
    )
    value = _field(row, aliases)
    if value is not None:
        return _number(value)

    # Fallback para cabeçalhos irrecuperavelmente mojibake: usa apenas uma
    # coluna de preço sem barra, evitando múltiplos como Preço/VPA.
    for key, candidate in row.items():
        label = _normalize_label(key)
        if label.startswith("pre") and "/" not in str(key) and "lucro" not in label:
            numeric = _number(candidate)
            if numeric is not None:
                return numeric
    return None


def _rows_from_records(
    records: Iterable[dict[str, Any]],
    tipo: str,
    date_str: str,
    origem: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    position = 0
    for raw in records:
        if not isinstance(raw, dict):
            continue
        ticker = _ticker_from_row(raw, tipo)
        if not ticker:
            continue
        position += 1
        rows.append(
            {
                "Data_Carteira": date_str,
                "Tipo": tipo,
                "Ticker": ticker,
                "Preco_Entrada": _price_from_row(raw, tipo),
                "Score": _number(_field(raw, ("Score", "score", "score_top"))),
                "Posicao": position,
                "Origem": origem,
                "Natureza": "OBSERVADO",
                "Strategy_Version": "published",
                "Schema_Version": 1,
            }
        )
    return rows


def load_dashboard_portfolios(docs_data_dir: str | Path) -> pd.DataFrame:
    """Lê Top FIIs/Ações dos JSONs históricos do dashboard."""
    root = Path(docs_data_dir)
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        if path.name == "index.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        date_str = pd.to_datetime(payload.get("data") or path.stem).strftime("%Y-%m-%d")
        rows.extend(_rows_from_records(payload.get("fiis") or [], "FII", date_str, "dashboard_json"))
        rows.extend(_rows_from_records(payload.get("acoes") or [], "ACAO", date_str, "dashboard_json"))
    return pd.DataFrame(rows)


def load_lake_portfolios(data_dir: str | Path) -> pd.DataFrame:
    """Lê carteiras do lake, priorizando Top N sobre resíduos de carteira."""
    from src.data_lake import _portfolio_from_top, list_lake_dates

    data_dir = Path(data_dir)
    rows = []
    for date_str in list_lake_dates(data_dir):
        snap = data_dir / "lake" / "snapshots" / date_str
        frames = []
        for filename, tipo in (("top_fiis.parquet", "FII"), ("top_acoes.parquet", "ACAO")):
            path = snap / filename
            if path.exists():
                portfolio = _portfolio_from_top(pd.read_parquet(path), tipo, date_str)
                if not portfolio.empty:
                    frames.append(portfolio)
        if frames:
            frame = pd.concat(frames, ignore_index=True)
            frame["Origem"] = "lake_top"
            frame["Natureza"] = "OBSERVADO"
            frame["Strategy_Version"] = "published"
            frame["Schema_Version"] = 1
            rows.append(frame)
    return pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()


def _excel_type(sheet_name: str, frame: pd.DataFrame) -> str | None:
    label = _normalize_label(sheet_name)
    columns = {_normalize_label(column) for column in frame.columns}
    if "base" in label or "completa" in label:
        return None
    if "fii" in label or "fundos" in columns:
        return "FII"
    if "acao" in label or "acoes" in label:
        return "ACAO"
    if any(column.startswith("ao") or column == "acao" for column in columns):
        return "ACAO"
    return None


def load_excel_portfolios(excel_dirs: Iterable[str | Path]) -> pd.DataFrame:
    """Recupera snapshots locais antigos; a data do nome do arquivo é autoritativa."""
    rows: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()
    for directory in excel_dirs:
        root = Path(directory)
        if not root.exists():
            continue
        for path in sorted(root.glob("Top20_Ranking_*.xlsx")):
            resolved = path.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            match = re.search(r"(\d{4}-\d{2}-\d{2})", path.stem)
            if not match:
                continue
            date_str = match.group(1)
            workbook = pd.ExcelFile(path)
            for sheet in workbook.sheet_names:
                frame = pd.read_excel(path, sheet_name=sheet)
                tipo = _excel_type(sheet, frame)
                if tipo is None or frame.empty:
                    continue
                rows.extend(
                    _rows_from_records(
                        frame.to_dict(orient="records"),
                        tipo,
                        date_str,
                        "excel_output",
                    )
                )
    return pd.DataFrame(rows)


def _atomic_write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)


def build_observed_history(
    data_dir: str | Path = "data",
    docs_data_dir: str | Path = "docs/data",
    excel_dirs: Iterable[str | Path] = (),
    output_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Consolida fontes reais sem transformar Top N em universo completo."""
    data_dir = Path(data_dir)
    output = Path(output_path) if output_path else data_dir / "backtest" / "observed_portfolios.parquet"
    manifest_file = (
        Path(manifest_path)
        if manifest_path
        else data_dir / "backtest" / "observed_history_manifest.json"
    )

    frames = [
        load_excel_portfolios(excel_dirs),
        load_dashboard_portfolios(docs_data_dir),
        load_lake_portfolios(data_dir),
    ]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        raise RuntimeError("Nenhuma carteira observada foi encontrada.")

    combined = pd.concat(frames, ignore_index=True, sort=False)
    combined["Data_Carteira"] = pd.to_datetime(
        combined["Data_Carteira"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    combined["Ticker"] = combined["Ticker"].astype(str).str.strip().str.upper()
    combined["_priority"] = combined["Origem"].map(
        {"excel_output": 1, "dashboard_json": 2, "lake_top": 3}
    ).fillna(0)
    # A precedência vale para o snapshot inteiro, não somente para tickers
    # repetidos. Caso contrário, a Base Completa de um Excel acrescentaria
    # centenas de ativos que não estavam no Top N do JSON/lake prioritário.
    max_priority = combined.groupby(["Data_Carteira", "Tipo"])["_priority"].transform("max")
    combined = combined[combined["_priority"].eq(max_priority)].copy()
    combined = combined.sort_values(
        ["Data_Carteira", "Tipo", "Ticker", "_priority"]
    ).drop_duplicates(["Data_Carteira", "Tipo", "Ticker"], keep="last")

    counts = combined.groupby(["Data_Carteira", "Tipo"]).size()
    completeness = {
        date: all(int(counts.get((date, tipo), 0)) >= 20 for tipo in ("FII", "ACAO"))
        for date in sorted(combined["Data_Carteira"].dropna().unique())
    }
    type_completeness = {
        (date, tipo): int(counts.get((date, tipo), 0)) >= 20
        for date in completeness
        for tipo in ("FII", "ACAO")
    }
    combined["Tipo_Completo"] = [
        type_completeness.get((date, tipo), False)
        for date, tipo in zip(combined["Data_Carteira"], combined["Tipo"])
    ]
    combined["Snapshot_Completo"] = combined["Data_Carteira"].map(completeness).fillna(False)
    combined = combined.sort_values(
        ["Data_Carteira", "Tipo", "Posicao", "Ticker"], na_position="last"
    ).reset_index(drop=True)
    combined = combined.reindex(columns=OBSERVED_COLUMNS)

    date_details = []
    for date_str in sorted(completeness):
        fii_count = int(counts.get((date_str, "FII"), 0))
        acao_count = int(counts.get((date_str, "ACAO"), 0))
        origins = sorted(
            combined.loc[combined["Data_Carteira"].eq(date_str), "Origem"]
            .dropna()
            .unique()
            .tolist()
        )
        date_details.append(
            {
                "data": date_str,
                "fiis": fii_count,
                "acoes": acao_count,
                "completo": bool(completeness[date_str]),
                "origens": origins,
            }
        )

    manifest = {
        "schema_version": 1,
        "natureza": "OBSERVADO",
        "descricao": "Carteiras efetivamente publicadas; não representa universo histórico completo.",
        "primeira_data": date_details[0]["data"],
        "ultima_data": date_details[-1]["data"],
        "total_datas": len(date_details),
        "datas_completas": sum(1 for item in date_details if item["completo"]),
        "datas_incompletas": [item["data"] for item in date_details if not item["completo"]],
        "total_linhas": int(len(combined)),
        "datas": date_details,
    }

    _atomic_write_parquet(combined, output)
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_manifest = manifest_file.with_name(manifest_file.name + ".tmp")
    tmp_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(tmp_manifest, manifest_file)
    logger.info("Histórico observado salvo em %s (%d linhas)", output, len(combined))
    return combined, manifest
