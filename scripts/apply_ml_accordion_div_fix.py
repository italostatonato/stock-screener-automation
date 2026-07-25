
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "docs" / "index.html"
CONTROLLER_JS = '<script id="ml-accordion-div-controller">\n(function(){\n  const SOURCE_SELECTOR=\'details.static-ml-group, details.force-ml-group, details.ml-model-group\';\n\n  function addStyle(){\n    if(document.getElementById(\'mlAccordionDivStyle\')) return;\n    const style=document.createElement(\'style\');\n    style.id=\'mlAccordionDivStyle\';\n    style.textContent=`\n      .ml-acc-card{margin:14px 0 16px;border:1px solid rgba(148,163,184,.18);border-radius:16px;background:rgba(15,23,42,.35);overflow:hidden}\n      .ml-acc-head{width:100%;border:0;background:transparent;color:inherit;cursor:pointer;padding:14px 16px;font:inherit;font-weight:800;display:flex;align-items:center;justify-content:space-between;gap:12px;text-align:left}\n      .ml-acc-head:hover{background:rgba(148,163,184,.06)}\n      .ml-acc-head .ml-acc-meta{color:var(--muted);font-weight:600;font-size:.86rem;margin-left:auto}\n      .ml-acc-head::after{content:\'+\';font-weight:900;color:var(--muted);margin-left:12px}\n      .ml-acc-card.is-open .ml-acc-head{border-bottom:1px solid rgba(148,163,184,.14)}\n      .ml-acc-card.is-open .ml-acc-head::after{content:\'−\'}\n      .ml-acc-body{display:none}\n      .ml-acc-card.is-open .ml-acc-body{display:block}\n      .ml-acc-card .table-wrap{margin:0}\n    `;\n    document.head.appendChild(style);\n  }\n\n  function normalizeHeaderHtml(summary){\n    const clone=summary.cloneNode(true);\n    const spans=[...clone.querySelectorAll(\'span\')];\n    spans.forEach(s=>{\n      if(!s.classList.contains(\'ml-rank-badge\')){\n        s.classList.add(\'ml-acc-meta\');\n      }\n    });\n    return clone.innerHTML;\n  }\n\n  function convertOne(detail){\n    if(!detail || detail.dataset.mlConvertedToDiv===\'1\') return;\n\n    const summary=detail.querySelector(\':scope > summary\');\n    if(!summary) return;\n\n    const card=document.createElement(\'div\');\n    card.className=\'ml-acc-card\';\n    card.dataset.mlAccordionCard=\'1\';\n\n    const btn=document.createElement(\'button\');\n    btn.type=\'button\';\n    btn.className=\'ml-acc-head\';\n    btn.innerHTML=normalizeHeaderHtml(summary);\n\n    const body=document.createElement(\'div\');\n    body.className=\'ml-acc-body\';\n\n    [...detail.childNodes].forEach(node=>{\n      if(node===summary) return;\n      body.appendChild(node.cloneNode(true));\n    });\n\n    card.appendChild(btn);\n    card.appendChild(body);\n    detail.replaceWith(card);\n  }\n\n  function convertAll(){\n    addStyle();\n    document.querySelectorAll(SOURCE_SELECTOR).forEach(convertOne);\n  }\n\n  document.addEventListener(\'click\',function(e){\n    const btn=e.target.closest(\'.ml-acc-head\');\n    if(!btn) return;\n\n    e.preventDefault();\n    e.stopPropagation();\n    if(e.stopImmediatePropagation) e.stopImmediatePropagation();\n\n    const card=btn.closest(\'.ml-acc-card\');\n    if(!card) return;\n\n    card.classList.toggle(\'is-open\');\n  },true);\n\n  function schedule(){\n    convertAll();\n    setTimeout(convertAll,250);\n    setTimeout(convertAll,900);\n    setTimeout(convertAll,1800);\n  }\n\n  document.addEventListener(\'DOMContentLoaded\',schedule);\n\n  document.addEventListener(\'click\',function(e){\n    if(e.target && (e.target.closest(\'.tab\') || e.target.closest(\'[data-tab]\') || e.target.closest(\'button\'))){\n      setTimeout(convertAll,200);\n    }\n  });\n\n  const observer=new MutationObserver(()=>setTimeout(convertAll,80));\n  observer.observe(document.documentElement,{childList:true,subtree:true});\n\n  schedule();\n})();\n</script>'


def main() -> None:
    if not HTML.exists():
        raise FileNotFoundError(f"Não encontrei {HTML}")

    text = HTML.read_text(encoding="utf-8")

    for script_id in [
        "ml-accordion-collapse-fix",
        "ml-accordion-manual-controller",
        "ml-accordion-div-controller",
    ]:
        text = re.sub(
            rf'\n?<script id="{script_id}">.*?</script>\n?',
            "\n",
            text,
            flags=re.S,
        )

    for old in [
        "${name==='Ensemble'?'open':''}",
        '${name==="Ensemble"?"open":""}',
        "${model.name==='Ensemble'?'open':''}",
        '${model.name==="Ensemble"?"open":""}',
    ]:
        text = text.replace(old, "")

    text = text.replace(" || e.target.closest('summary')", "")
    text = text.replace(' || e.target.closest("summary")', "")

    idx = text.lower().rfind("</body>")
    if idx >= 0:
        text = text[:idx] + "\n" + CONTROLLER_JS + "\n" + text[idx:]
    else:
        text = text.rstrip() + "\n" + CONTROLLER_JS + "\n"

    HTML.write_text(text, encoding="utf-8")

    print("[OK] Accordion trocado para DIV + button.")
    print("[OK] Não depende mais de <details>/<summary>.")
    print("[OK] Clique no card deve abrir; clique de novo deve fechar.")


if __name__ == "__main__":
    main()
