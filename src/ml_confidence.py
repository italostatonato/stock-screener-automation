"""ml_confidence.py — maturidade e confiabilidade dos modelos ML.

Esta camada NÃO decide investimento e NÃO troca o ranking oficial. Ela calcula dois
indicadores para o dashboard:

1. Maturidade dos dados: quanto do horizonte principal já foi acumulado.
2. Confiabilidade preditiva real: só sai de 0% quando houver janelas válidas
   suficientes para medir retorno futuro, hit rate, Spearman IC e alpha vs Score Top.

A função principal é build_ml_confidence_summary(). Ela recebe os registros de
performance já exportados pela camada de ML e devolve um payload pronto para JSON.
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

HORIZON_DAYS_DEFAULT = 30
MIN_VALID_WINDOWS_DEFAULT = 5
TARGET_VALID_WINDOWS_DEFAULT = 12


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        value_float = float(value)
        if math.isnan(value_float) or math.isinf(value_float):
            return default
        return value_float
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        value_float = float(value)
        if math.isnan(value_float) or math.isinf(value_float):
            return default
        return int(value_float)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _linear_score(value: Any, low: float, high: float) -> float:
    numeric = _safe_float(value)
    if numeric is None or high == low:
        return 0.0
    return _clamp((numeric - low) / (high - low))


def _confidence_level(confidence_pct: float | None, valid_windows: int, min_valid_windows: int) -> str:
    confidence_pct = _safe_float(confidence_pct, 0.0) or 0.0
    if valid_windows < min_valid_windows or confidence_pct <= 0:
        return "Não mensurável"
    if confidence_pct < 40:
        return "Baixa"
    if confidence_pct < 70:
        return "Média"
    return "Alta"


def _model_confidence(row: dict[str, Any], min_valid_windows: int, target_valid_windows: int) -> dict[str, Any]:
    """Calcula confiança de uma linha de performance de modelo.

    Fórmula conservadora:
    - trava em 0% até existir o mínimo de janelas válidas;
    - 40% peso para cobertura histórica;
    - 25% para hit rate;
    - 25% para Spearman IC;
    - 10% para alpha vs Score Top.

    Escalas adotadas:
    - hit rate: 50% = neutro/aleatório; 65% = forte;
    - Spearman IC: 0 = sem ordenação; 0,30 = bom para ranking financeiro;
    - alpha: 0 p.p. = neutro; 3 p.p. = forte no horizonte medido.
    """
    valid_windows = _safe_int(row.get("Janelas_Validas"), 0)
    model_name = str(row.get("Modelo") or "").strip()

    if valid_windows < min_valid_windows:
        return {
            "Confiabilidade_Pct": 0.0,
            "Nivel_Confiabilidade": "Não mensurável",
            "Componentes_Confiabilidade": {
                "cobertura_historica": round(valid_windows / max(min_valid_windows, 1) * 100, 2),
                "hit_rate": None,
                "spearman_ic": None,
                "alpha_vs_score_top": None,
            },
        }

    coverage_score = _clamp(valid_windows / max(target_valid_windows, 1))
    hit_score = _linear_score(row.get("Hit_Rate_Top20"), 0.50, 0.65)
    ic_score = _linear_score(row.get("Spearman_IC"), 0.00, 0.30)

    alpha_value = _safe_float(row.get("Alpha_vs_Score_Top"))
    if model_name == "Score Top":
        # Baseline não pode ter alpha contra ele mesmo. Mantemos neutro para não
        # punir nem inflar a confiança do modelo oficial atual.
        alpha_score = 0.50
    else:
        alpha_score = _linear_score(alpha_value, 0.00, 0.03)

    confidence = 100.0 * (
        0.40 * coverage_score
        + 0.25 * hit_score
        + 0.25 * ic_score
        + 0.10 * alpha_score
    )
    confidence = round(_clamp(confidence / 100.0) * 100.0, 2)

    return {
        "Confiabilidade_Pct": confidence,
        "Nivel_Confiabilidade": _confidence_level(confidence, valid_windows, min_valid_windows),
        "Componentes_Confiabilidade": {
            "cobertura_historica": round(coverage_score * 100, 2),
            "hit_rate": round(hit_score * 100, 2),
            "spearman_ic": round(ic_score * 100, 2),
            "alpha_vs_score_top": round(alpha_score * 100, 2),
        },
    }


def load_snapshot_dates(docs_data_dir: str | os.PathLike[str] = "docs/data") -> list[str]:
    """Carrega datas do index.json; se faltar, varre docs/data/*.json."""
    data_dir = Path(docs_data_dir)
    index_path = data_dir / "index.json"
    dates: list[str] = []

    if index_path.exists():
        try:
            with index_path.open(encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, list):
                dates = [str(d) for d in loaded if _parse_date(str(d)) is not None]
        except Exception:
            dates = []

    if not dates and data_dir.exists():
        dates = [p.stem for p in data_dir.glob("*.json") if p.stem != "index" and _parse_date(p.stem) is not None]

    return sorted(set(dates))


def _parse_date(value: str) -> datetime | None:
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d")
    except Exception:
        return None


def _maturity_from_dates(dates: Iterable[str], horizon_days: int) -> dict[str, Any]:
    parsed = sorted([d for d in (_parse_date(str(x)) for x in dates) if d is not None])
    if not parsed:
        return {
            "primeiro_snapshot": None,
            "ultimo_snapshot": None,
            "dias_historico": 0,
            "qtd_snapshots": 0,
            "maturidade_dados_pct": 0.0,
        }

    first = parsed[0]
    last = parsed[-1]
    days = max((last - first).days, 0)
    maturity = round(_clamp(days / max(horizon_days, 1)) * 100, 2)
    return {
        "primeiro_snapshot": first.strftime("%Y-%m-%d"),
        "ultimo_snapshot": last.strftime("%Y-%m-%d"),
        "dias_historico": int(days),
        "qtd_snapshots": int(len(parsed)),
        "maturidade_dados_pct": maturity,
    }


def add_confidence_to_performance_records(
    performance_records: list[dict[str, Any]],
    confidence_summary: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Enriquece a tabela de performance com confiabilidade por modelo."""
    if not performance_records:
        return []

    if confidence_summary is None:
        confidence_summary = build_ml_confidence_summary(performance_records=performance_records)

    lookup = {
        (r.get("Tipo"), r.get("Modelo"), r.get("Horizonte")): r
        for r in confidence_summary.get("por_modelo", [])
    }
    enriched: list[dict[str, Any]] = []
    for row in performance_records:
        key = (row.get("Tipo"), row.get("Modelo"), row.get("Horizonte"))
        conf = lookup.get(key, {})
        new_row = dict(row)
        new_row["Confiabilidade_Pct"] = conf.get("Confiabilidade_Pct")
        new_row["Nivel_Confiabilidade"] = conf.get("Nivel_Confiabilidade")
        enriched.append(new_row)
    return enriched


def build_ml_confidence_summary(
    performance_records: list[dict[str, Any]] | None,
    docs_data_dir: str | os.PathLike[str] = "docs/data",
    horizon_days: int = HORIZON_DAYS_DEFAULT,
    min_valid_windows: int = MIN_VALID_WINDOWS_DEFAULT,
    target_valid_windows: int = TARGET_VALID_WINDOWS_DEFAULT,
) -> dict[str, Any]:
    """Monta resumo de maturidade e confiabilidade para o dashboard.

    A confiabilidade preditiva global é o maior score real entre os modelos.
    Enquanto nenhum modelo tiver o mínimo de janelas válidas, ela fica em 0%.
    """
    performance_records = performance_records or []
    dates = load_snapshot_dates(docs_data_dir)
    maturity = _maturity_from_dates(dates, horizon_days=horizon_days)

    per_model: list[dict[str, Any]] = []
    for row in performance_records:
        conf = _model_confidence(row, min_valid_windows=min_valid_windows, target_valid_windows=target_valid_windows)
        payload = {
            "Tipo": row.get("Tipo"),
            "Modelo": row.get("Modelo"),
            "Horizonte": row.get("Horizonte"),
            "Janelas_Validas": _safe_int(row.get("Janelas_Validas"), 0),
            "Hit_Rate_Top20": _safe_float(row.get("Hit_Rate_Top20")),
            "Spearman_IC": _safe_float(row.get("Spearman_IC")),
            "Alpha_vs_Score_Top": _safe_float(row.get("Alpha_vs_Score_Top")),
            **conf,
        }
        per_model.append(payload)

    valid_models = [r for r in per_model if _safe_int(r.get("Janelas_Validas"), 0) >= min_valid_windows]
    if valid_models:
        leader = max(valid_models, key=lambda r: _safe_float(r.get("Confiabilidade_Pct"), 0.0) or 0.0)
        predictive = round(_safe_float(leader.get("Confiabilidade_Pct"), 0.0) or 0.0, 2)
        status = "Ativo"
        message = (
            f"Confiabilidade calculada com base em {leader.get('Janelas_Validas')} janelas válidas. "
            f"Modelo mais confiável no momento: {leader.get('Modelo')} ({leader.get('Tipo')})."
        )
        leader_payload = {
            "Tipo": leader.get("Tipo"),
            "Modelo": leader.get("Modelo"),
            "Horizonte": leader.get("Horizonte"),
            "Confiabilidade_Pct": leader.get("Confiabilidade_Pct"),
        }
    else:
        predictive = 0.0
        status = "Aquecendo"
        message = (
            f"Aguardando pelo menos {min_valid_windows} janelas válidas de {horizon_days} dias. "
            "Até lá, a confiabilidade preditiva real fica em 0% para evitar falso positivo."
        )
        leader_payload = None

    max_windows = max([_safe_int(r.get("Janelas_Validas"), 0) for r in per_model], default=0)

    return {
        "status": status,
        "horizonte_dias": horizon_days,
        "maturidade_dados_pct": maturity["maturidade_dados_pct"],
        "confiabilidade_preditiva_pct": predictive,
        "nivel_confiabilidade": _confidence_level(predictive, max_windows, min_valid_windows),
        "modelo_mais_confiavel": leader_payload,
        "janelas_validas_max": int(max_windows),
        "min_janelas_validas": int(min_valid_windows),
        "target_janelas_validas": int(target_valid_windows),
        "primeiro_snapshot": maturity["primeiro_snapshot"],
        "ultimo_snapshot": maturity["ultimo_snapshot"],
        "dias_historico": maturity["dias_historico"],
        "qtd_snapshots": maturity["qtd_snapshots"],
        "mensagem": message,
        "por_modelo": sorted(
            per_model,
            key=lambda r: (
                str(r.get("Tipo") or ""),
                -(_safe_float(r.get("Confiabilidade_Pct"), 0.0) or 0.0),
                str(r.get("Modelo") or ""),
            ),
        ),
    }
