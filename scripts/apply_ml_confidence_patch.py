"""Aplica patch de confiabilidade ML sem sobrescrever arquivos grandes.

Uso:
    python scripts/apply_ml_confidence_patch.py

O script altera:
- src/exporter.py: inclui resumo de confiabilidade em modelos_ml.confiabilidade
  e adiciona colunas de confiabilidade na tabela de performance.
- docs/index.html: adiciona um card visual na aba Modelos ML, carregado via JS
  a partir do snapshot mais recente.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_exporter() -> None:
    path = ROOT / "src" / "exporter.py"
    text = _read(path)

    import_line = "from src.ml_confidence import add_confidence_to_performance_records, build_ml_confidence_summary\n"
    if import_line not in text:
        anchor = "logger = logging.getLogger(__name__)"
        if anchor in text:
            text = text.replace(anchor, import_line + anchor, 1)
        else:
            raise RuntimeError("Não encontrei anchor de logger em src/exporter.py")

    if "confidence = build_ml_confidence_summary(" not in text:
        anchor = 'performance = _performance_records(os.path.join(ml_dir, "model_performance.parquet"))'
        if anchor not in text:
            raise RuntimeError("Não encontrei a linha de performance em _calc_modelos_ml().")
        replacement = anchor + "\n" + " " * 4 + "confidence = build_ml_confidence_summary(\n" + \
            " " * 8 + "performance_records=performance,\n" + \
            " " * 8 + 'docs_data_dir=os.path.join("docs", "data"),\n' + \
            " " * 8 + "horizon_days=30,\n" + \
            " " * 4 + ")\n" + \
            " " * 4 + "performance = add_confidence_to_performance_records(performance, confidence)"
        text = text.replace(anchor, replacement, 1)

    if '"confiabilidade": confidence,' not in text:
        anchor = '"horizonte_principal": "30d",'
        if anchor not in text:
            raise RuntimeError("Não encontrei horizonte_principal no retorno de _calc_modelos_ml().")
        text = text.replace(anchor, anchor + '\n        "confiabilidade": confidence,', 1)

    if "Confiabilidade_Pct" not in text:
        anchor = '"Alpha_vs_Score_Top", "Status",'
        if anchor in text:
            text = text.replace(
                anchor,
                '"Alpha_vs_Score_Top", "Confiabilidade_Pct", "Nivel_Confiabilidade", "Status",',
                1,
            )
        else:
            # Fallback para formato multilinha da lista cols.
            anchor = '"Alpha_vs_Score_Top",\n        "Status",'
            if anchor in text:
                text = text.replace(
                    anchor,
                    '"Alpha_vs_Score_Top",\n        "Confiabilidade_Pct",\n        "Nivel_Confiabilidade",\n        "Status",',
                    1,
                )

    _write(path, text)
    print("OK: src/exporter.py atualizado")


def patch_dashboard() -> None:
    path = ROOT / "docs" / "index.html"
    text = _read(path)

    panel = """
<div id="ml-confidence-panel" style="margin: 16px 0 22px; padding: 16px; border: 1px solid rgba(148,163,184,.25); border-radius: 16px; background: rgba(15,23,42,.45);">
  <h3 style="margin:0 0 10px;">Status e confiabilidade dos modelos</h3>
  <div id="ml-confidence-grid" style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px;"></div>
  <p id="ml-confidence-message" style="margin:12px 0 0; color:#94a3b8; font-size:.92rem;"></p>
</div>
""".strip()

    if "ml-confidence-panel" not in text:
        anchors = ["<h3>Ranking dos modelos</h3>", "Ranking dos modelos"]
        for anchor in anchors:
            if anchor in text:
                text = text.replace(anchor, panel + "\n" + anchor, 1)
                break
        else:
            # Fallback: coloca antes do fechamento do body se o template for diferente.
            if "</body>" in text:
                text = text.replace("</body>", panel + "\n</body>", 1)
            else:
                text += "\n" + panel + "\n"

    js = r'''
<script id="ml-confidence-renderer">
(function () {
  function fmtPct(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return "—";
    return `${n.toFixed(1)}%`;
  }

  function card(label, value, sub) {
    return `
      <div style="padding:12px; border:1px solid rgba(148,163,184,.18); border-radius:14px; background:rgba(2,6,23,.28);">
        <div style="color:#94a3b8; font-size:.82rem; margin-bottom:6px;">${label}</div>
        <div style="font-size:1.45rem; font-weight:700;">${value}</div>
        <div style="color:#94a3b8; font-size:.78rem; margin-top:4px;">${sub || ""}</div>
      </div>`;
  }

  function render(conf) {
    const grid = document.getElementById("ml-confidence-grid");
    const msg = document.getElementById("ml-confidence-message");
    if (!grid || !msg) return;

    conf = conf || {};
    const leader = conf.modelo_mais_confiavel;
    grid.innerHTML = [
      card("Maturidade dos dados", fmtPct(conf.maturidade_dados_pct), `${conf.dias_historico || 0} dias de histórico · alvo ${conf.horizonte_dias || 30}d`),
      card("Confiabilidade preditiva", fmtPct(conf.confiabilidade_preditiva_pct), conf.nivel_confiabilidade || "Não mensurável"),
      card("Janelas válidas", `${conf.janelas_validas_max || 0}/${conf.min_janelas_validas || 5}`, "mínimo para liberar confiança real"),
      card("Modelo mais confiável", leader ? `${leader.Modelo} · ${leader.Tipo}` : "—", leader ? fmtPct(leader.Confiabilidade_Pct) : "aguardando validação")
    ].join("");
    msg.textContent = conf.mensagem || "Aguardando dados de retorno futuro para calcular confiabilidade real.";
  }

  async function loadLatestConfidence() {
    try {
      const index = await fetch("data/index.json", { cache: "no-store" }).then(r => r.json());
      const latest = Array.isArray(index) ? index[0] : null;
      if (!latest) return render({});
      const payload = await fetch(`data/${latest}.json`, { cache: "no-store" }).then(r => r.json());
      render(payload && payload.modelos_ml && payload.modelos_ml.confiabilidade);
    } catch (err) {
      render({ mensagem: "Não foi possível carregar a confiabilidade dos modelos neste momento." });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadLatestConfidence);
  } else {
    loadLatestConfidence();
  }
})();
</script>
'''.strip()

    if "ml-confidence-renderer" not in text:
        if "</body>" in text:
            text = text.replace("</body>", js + "\n</body>", 1)
        else:
            text += "\n" + js + "\n"

    _write(path, text)
    print("OK: docs/index.html atualizado")


def main() -> None:
    patch_exporter()
    patch_dashboard()
    print("Patch de confiabilidade ML aplicado com sucesso.")


if __name__ == "__main__":
    main()
