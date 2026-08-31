"""Fundação do backfill point-in-time e estratégia histórica mensal de FIIs.

Dados retroativos vivem em ``data/point_in_time`` e nunca são gravados como se
fossem snapshots observados do lake oficial.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Iterable
from zipfile import ZipFile

import numpy as np
import pandas as pd
import requests

from src.filters import select_top_fiis
from src.scorer import score_fiis

logger = logging.getLogger(__name__)

CVM_FII_URL = (
    "https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/"
    "inf_mensal_fii_{year}.zip"
)
B3_COTAHIST_URL = (
    "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{year}.ZIP"
)


def _atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    frame.to_parquet(tmp, index=False)
    os.replace(tmp, path)


def _atomic_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_archive(url: str, path: str | Path, timeout: float = 300) -> Path:
    """Baixa de forma atômica; arquivo existente é reutilizado."""
    target = Path(path)
    if target.exists() and target.stat().st_size > 0:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    with requests.get(url, timeout=timeout, stream=True) as response:
        response.raise_for_status()
        with tmp.open("wb") as handle:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    handle.write(chunk)
    os.replace(tmp, target)
    return target


def download_point_in_time_sources(
    years: Iterable[int],
    raw_dir: str | Path = "data/raw/point_in_time",
) -> dict[str, list[Path]]:
    root = Path(raw_dir)
    result: dict[str, list[Path]] = {"cvm_fii": [], "b3_cotahist": []}
    for year in sorted(set(int(value) for value in years)):
        result["cvm_fii"].append(
            download_archive(
                CVM_FII_URL.format(year=year), root / "cvm_fii" / f"inf_mensal_fii_{year}.zip"
            )
        )
        result["b3_cotahist"].append(
            download_archive(
                B3_COTAHIST_URL.format(year=year), root / "b3" / f"COTAHIST_A{year}.ZIP"
            )
        )
    return result


def _read_zip_csv(archive: str | Path, contains: str) -> pd.DataFrame:
    with ZipFile(archive) as zipped:
        matches = [name for name in zipped.namelist() if contains.lower() in name.lower()]
        if len(matches) != 1:
            raise RuntimeError(f"Esperava um CSV contendo {contains!r} em {archive}; achei {matches}")
        return pd.read_csv(zipped.open(matches[0]), sep=";", encoding="latin1", low_memory=False)


def load_cvm_fii_archive(archive: str | Path) -> pd.DataFrame:
    """Normaliza Informe Mensal, preservando referência, entrega e versão."""
    geral = _read_zip_csv(archive, "_geral_")
    complemento = _read_zip_csv(archive, "_complemento_")
    keys = ["CNPJ_Fundo_Classe", "Data_Referencia", "Versao"]
    required_geral = set(keys + ["Data_Entrega", "Nome_Fundo_Classe", "Codigo_ISIN"])
    required_complemento = set(
        keys
        + [
            "Patrimonio_Liquido",
            "Cotas_Emitidas",
            "Valor_Patrimonial_Cotas",
            "Percentual_Dividend_Yield_Mes",
            "Total_Numero_Cotistas",
        ]
    )
    if not required_geral.issubset(geral.columns) or not required_complemento.issubset(complemento.columns):
        raise RuntimeError(f"Layout inesperado no Informe Mensal {archive}")
    out = geral[list(required_geral)].merge(
        complemento[list(required_complemento)], on=keys, how="inner"
    )
    out = out.rename(
        columns={
            "CNPJ_Fundo_Classe": "CNPJ",
            "Data_Referencia": "Data_Referencia",
            "Versao": "Versao",
            "Data_Entrega": "Data_Disponibilidade",
            "Nome_Fundo_Classe": "Nome",
            "Codigo_ISIN": "ISIN",
            "Patrimonio_Liquido": "PATRIMÔNIO LÍQUIDO",
            "Cotas_Emitidas": "Cotas_Emitidas",
            "Valor_Patrimonial_Cotas": "VPA",
            "Percentual_Dividend_Yield_Mes": "DIVIDEND YIELD",
            "Total_Numero_Cotistas": "NUM. COTISTAS",
        }
    )
    out["Data_Referencia"] = pd.to_datetime(out["Data_Referencia"], errors="coerce")
    out["Data_Disponibilidade"] = pd.to_datetime(out["Data_Disponibilidade"], errors="coerce")
    out["Versao"] = pd.to_numeric(out["Versao"], errors="coerce")
    for column in (
        "PATRIMÔNIO LÍQUIDO",
        "Cotas_Emitidas",
        "VPA",
        "DIVIDEND YIELD",
        "NUM. COTISTAS",
    ):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    out["ISIN"] = out["ISIN"].astype("string").str.strip().str.upper()
    out["Fonte_Fundamento"] = "CVM_FII_INFORME_MENSAL"
    return out.dropna(subset=["CNPJ", "Data_Referencia", "Data_Disponibilidade"])


def load_cvm_fii_archives(archives: Iterable[str | Path]) -> pd.DataFrame:
    frames = [load_cvm_fii_archive(path) for path in archives]
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True, sort=False)
    return out.sort_values(["CNPJ", "Data_Referencia", "Data_Disponibilidade", "Versao"])


_COTAHIST_WIDTHS = [
    2, 8, 2, 12, 3, 12, 10, 3, 4, 13, 13, 13, 13, 13, 13, 13, 5, 18, 18,
    13, 1, 8, 7, 13, 12, 3,
]
_COTAHIST_NAMES = [
    "TIPREG", "Data", "CODBDI", "Ticker", "TPMERC", "NOMRES", "ESPECI", "PRAZOT",
    "MODREF", "PREABE", "PREMAX", "PREMIN", "PREMED", "PREULT", "PREOFC", "PREOFV",
    "TOTNEG", "QUATOT", "VOLTOT", "PREEXE", "INDOPC", "DATVEN", "FATCOT", "PTOEXE",
    "ISIN", "DISMES",
]


def load_b3_cotahist_archive(archive: str | Path) -> pd.DataFrame:
    """Lê COTAHIST oficial. Os preços permanecem sem ajuste por proventos."""
    with ZipFile(archive) as zipped:
        names = [name for name in zipped.namelist() if name.upper().endswith(".TXT")]
        if len(names) != 1:
            raise RuntimeError(f"TXT COTAHIST não localizado em {archive}")
        frame = pd.read_fwf(
            zipped.open(names[0]),
            widths=_COTAHIST_WIDTHS,
            names=_COTAHIST_NAMES,
            dtype=str,
            encoding="latin1",
        )
    frame = frame[frame["TIPREG"].eq("01") & frame["TPMERC"].eq("010")].copy()
    frame["Data"] = pd.to_datetime(frame["Data"], format="%Y%m%d", errors="coerce")
    frame["Ticker"] = frame["Ticker"].astype("string").str.strip().str.upper()
    frame["ISIN"] = frame["ISIN"].astype("string").str.strip().str.upper()
    for column in ("PREABE", "PREMAX", "PREMIN", "PREMED", "PREULT", "PREOFC", "PREOFV"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce") / 100.0
    frame["QUATOT"] = pd.to_numeric(frame["QUATOT"], errors="coerce")
    frame["VOLTOT"] = pd.to_numeric(frame["VOLTOT"], errors="coerce") / 100.0
    frame = frame.rename(columns={"PREULT": "PREÇO ATUAL (R$)", "VOLTOT": "Volume_Financeiro"})
    frame["Fonte_Preco"] = "B3_COTAHIST_NAO_AJUSTADO"
    keep = [
        "Data", "Ticker", "ISIN", "NOMRES", "ESPECI", "PREÇO ATUAL (R$)",
        "Volume_Financeiro", "QUATOT", "Fonte_Preco",
    ]
    return frame[keep].dropna(subset=["Data", "Ticker", "PREÇO ATUAL (R$)"])


def load_b3_cotahist_archives(archives: Iterable[str | Path]) -> pd.DataFrame:
    frames = [load_b3_cotahist_archive(path) for path in archives]
    if not frames:
        return pd.DataFrame()
    return (
        pd.concat(frames, ignore_index=True, sort=False)
        .sort_values(["Data", "Ticker"])
        .drop_duplicates(["Data", "Ticker"], keep="last")
        .reset_index(drop=True)
    )


def select_available_as_of(
    frame: pd.DataFrame,
    as_of: str | pd.Timestamp,
    entity_col: str,
    reference_col: str = "Data_Referencia",
    availability_col: str = "Data_Disponibilidade",
    version_col: str = "Versao",
) -> pd.DataFrame:
    """Seleciona a última versão que já era pública na data do sinal."""
    cutoff = pd.Timestamp(as_of).normalize()
    data = frame.copy()
    data[reference_col] = pd.to_datetime(data[reference_col], errors="coerce")
    data[availability_col] = pd.to_datetime(data[availability_col], errors="coerce")
    data[version_col] = pd.to_numeric(data[version_col], errors="coerce").fillna(0)
    data = data[
        data[reference_col].le(cutoff)
        & data[availability_col].le(cutoff)
        & data[entity_col].notna()
    ]
    if data.empty:
        return data
    data = data.sort_values(
        [entity_col, reference_col, availability_col, version_col]
    )
    return data.drop_duplicates(entity_col, keep="last").reset_index(drop=True)


def monthly_signal_dates(
    prices: pd.DataFrame,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
) -> list[pd.Timestamp]:
    data = prices.copy()
    data["Data"] = pd.to_datetime(data["Data"], errors="coerce").dt.normalize()
    start_ts, end_ts = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    dates = data.loc[data["Data"].between(start_ts, end_ts), "Data"].dropna().drop_duplicates()
    if dates.empty:
        return []
    return [pd.Timestamp(value) for value in dates.groupby(dates.dt.to_period("M")).max().tolist()]


def build_fii_universe_as_of(
    signal_date: str | pd.Timestamp,
    fundamentals: pd.DataFrame,
    prices: pd.DataFrame,
    lookback_days: int = 120,
) -> pd.DataFrame:
    """Monta o universo FII usando somente dados disponíveis até o sinal."""
    signal = pd.Timestamp(signal_date).normalize()
    available = select_available_as_of(fundamentals, signal, entity_col="CNPJ")
    if available.empty:
        return pd.DataFrame()

    market = prices.copy()
    market["Data"] = pd.to_datetime(market["Data"], errors="coerce").dt.normalize()
    market = market[
        market["Data"].le(signal)
        & market["Data"].ge(signal - pd.Timedelta(int(lookback_days), unit="D"))
    ]
    if market.empty:
        return pd.DataFrame()
    market["ISIN"] = market["ISIN"].astype("string").str.strip().str.upper()
    market["Ticker"] = market["Ticker"].astype("string").str.strip().str.upper()

    latest = (
        market.sort_values(["ISIN", "Data"])
        .dropna(subset=["ISIN"])
        .drop_duplicates("ISIN", keep="last")
    )
    liquidity = market.groupby("ISIN")["Volume_Financeiro"].mean().rename("LIQUIDEZ DIÁRIA (R$)")
    market = market.sort_values(["Ticker", "Data"])
    market["_return"] = market.groupby("Ticker")["PREÇO ATUAL (R$)"].pct_change(fill_method=None)
    volatility = (
        market.groupby("ISIN")["_return"].std() * np.sqrt(252) * 100
    ).rename("VOLATILIDADE")
    features = latest[["ISIN", "Ticker", "Data", "PREÇO ATUAL (R$)", "Fonte_Preco"]].merge(
        liquidity, on="ISIN", how="left"
    ).merge(volatility, on="ISIN", how="left")

    universe = available.merge(features, on="ISIN", how="inner")
    universe = universe.rename(columns={"Ticker": "FUNDOS"})
    universe["P/VP"] = universe["PREÇO ATUAL (R$)"] / universe["VPA"].replace(0, np.nan)
    universe["Data_Execucao"] = signal.strftime("%Y-%m-%d")
    universe["Natureza"] = "SIMULADO_POINT_IN_TIME"
    universe["Strategy_Version"] = "fii_v1_legacy_selection"
    universe["Score"] = score_fiis(universe)
    return universe.sort_values("FUNDOS").reset_index(drop=True)


def build_monthly_fii_backfill(
    fundamentals: pd.DataFrame,
    prices: pd.DataFrame,
    cfg: dict,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    output_dir: str | Path = "data/point_in_time",
) -> dict:
    """Gera snapshots mensais sintéticos, isolados do lake observado."""
    output_root = Path(output_dir)
    dates = monthly_signal_dates(prices, start=start, end=end)
    details = []
    for signal in dates:
        universe = build_fii_universe_as_of(signal, fundamentals, prices)
        if universe.empty:
            details.append({"data": signal.strftime("%Y-%m-%d"), "status": "sem_universo"})
            continue
        top, full = select_top_fiis(universe, cfg)
        snapshot_dir = output_root / "snapshots" / signal.strftime("%Y-%m-%d")
        _atomic_parquet(full, snapshot_dir / "fii_universe.parquet")
        _atomic_parquet(top, snapshot_dir / "top_fiis.parquet")
        target_rows = int(cfg["filters"]["top_n"])
        complete = len(top) == target_rows
        manifest = {
            "data_sinal": signal.strftime("%Y-%m-%d"),
            "natureza": "SIMULADO_POINT_IN_TIME",
            "strategy_version": "fii_v1_legacy_selection",
            "universe_rows": int(len(full)),
            "top_rows": int(len(top)),
            "target_rows": target_rows,
            "carteira_completa": complete,
            "fundamento_mais_recente": pd.to_datetime(full["Data_Referencia"]).max().strftime("%Y-%m-%d"),
            "disponibilidade_mais_recente": pd.to_datetime(full["Data_Disponibilidade"]).max().strftime("%Y-%m-%d"),
        }
        _atomic_json(manifest, snapshot_dir / "manifest.json")
        status = "ok" if complete else "carteira_parcial"
        details.append({"data": signal.strftime("%Y-%m-%d"), "status": status, **manifest})
    global_manifest = {
        "schema_version": 1,
        "natureza": "SIMULADO_POINT_IN_TIME",
        "strategy_version": "fii_v1_legacy_selection",
        "start": pd.Timestamp(start).strftime("%Y-%m-%d"),
        "end": pd.Timestamp(end).strftime("%Y-%m-%d"),
        "snapshots_ok": sum(item["status"] in {"ok", "carteira_parcial"} for item in details),
        "snapshots_completos": sum(item["status"] == "ok" for item in details),
        "snapshots_parciais": sum(item["status"] == "carteira_parcial" for item in details),
        "snapshots": details,
    }
    _atomic_json(global_manifest, output_root / "manifest.json")
    return global_manifest


def load_fii_backfill_portfolios(
    output_dir: str | Path = "data/point_in_time",
) -> pd.DataFrame:
    """Converte snapshots sintéticos em carteiras aceitas pelo motor de backtest."""
    rows: list[pd.DataFrame] = []
    for path in sorted((Path(output_dir) / "snapshots").glob("*/top_fiis.parquet")):
        top = pd.read_parquet(path)
        if top.empty or "FUNDOS" not in top.columns:
            continue
        manifest_path = path.parent / "manifest.json"
        manifest = (
            json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest_path.exists()
            else {}
        )
        frame = pd.DataFrame(
            {
                "Data_Carteira": path.parent.name,
                "Tipo": "FII",
                "Ticker": top["FUNDOS"].astype("string"),
                "Score": pd.to_numeric(top.get("Score"), errors="coerce"),
                "Tipo_Completo": bool(manifest.get("carteira_completa", len(top) == 20)),
                "Natureza": "SIMULADO_POINT_IN_TIME",
                "Strategy_Version": manifest.get(
                    "strategy_version", "fii_v1_legacy_selection"
                ),
            }
        )
        rows.append(frame)
    if not rows:
        return pd.DataFrame(
            columns=[
                "Data_Carteira", "Tipo", "Ticker", "Score", "Tipo_Completo",
                "Natureza", "Strategy_Version",
            ]
        )
    return pd.concat(rows, ignore_index=True, sort=False)


def source_manifest(
    paths: Iterable[str | Path],
    relative_to: str | Path | None = None,
) -> list[dict]:
    base = Path(relative_to).resolve() if relative_to is not None else None
    result = []
    for value in paths:
        path = Path(value)
        display_path = path.resolve().relative_to(base) if base is not None else path
        result.append(
            {
                "path": str(display_path).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return result
