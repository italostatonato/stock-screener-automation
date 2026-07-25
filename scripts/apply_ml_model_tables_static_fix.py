
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "docs" / "index.html"

STATIC_SECTION_ID = "staticMlModelByModelSection"
STATIC_BLOCK = '<div id="staticMlModelByModelSection" class="panel force-ml-extra" style="margin-top:22px;">\n  <h3>Top 20 por modelo</h3>\n  <p class="desc">Ranking separado de Ações e FIIs para cada modelo. Use esta tabela para comparar se os modelos convergem para ativos parecidos ou se algum deles está gerando sinais muito diferentes.</p>\n  <div id="staticMlModelTables">\n    <div class="muted-cell">Carregando rankings por modelo...</div>\n  </div>\n</div>\n\n<div id="staticMlModelExplainSection" class="panel force-ml-extra" style="margin-top:22px;">\n  <h3>Como cada modelo funciona</h3>\n  <p class="desc">Resumo prático para interpretar os sinais. Nesta fase, os modelos supervisionados devem ser lidos como apoio e validação, não como recomendação automática.</p>\n  <div id="staticMlModelExplainGrid" class="static-ml-explain-grid"></div>\n</div>'
SCRIPT_BLOCK = '<script id="static-ml-model-tables-renderer">\n(function(){\n  const MODELS=[\n    [\'Score Top\',\'score_top\'],\n    [\'Ridge\',\'score_ridge\'],\n    [\'Random Forest\',\'score_random_forest\'],\n    [\'Extra Trees\',\'score_extra_trees\'],\n    [\'XGBoost\',\'score_xgboost\'],\n    [\'LightGBM\',\'score_lightgbm\'],\n    [\'CatBoost\',\'score_catboost\'],\n    [\'Ensemble\',\'score_ensemble\']\n  ];\n\n  const EXPLAIN=[\n    [\'Score Top\',\'Baseline quantitativo\',\'Modelo atual de regras e percentis do projeto. Combina critérios fundamentalistas e de mercado em um score comparável entre ativos.\',\'Serve como régua oficial enquanto os modelos supervisionados acumulam histórico suficiente.\'],\n    [\'Ridge\',\'Regressão linear regularizada\',\'Procura uma relação linear entre indicadores e retorno futuro, penalizando pesos exagerados para reduzir ruído e overfitting.\',\'Bom para capturar sinais simples e estáveis; tende a ser mais conservador.\'],\n    [\'Random Forest\',\'Árvores em conjunto\',\'Treina várias árvores de decisão em amostras diferentes e combina os resultados por média.\',\'Captura relações não lineares e costuma ser mais robusto que uma árvore isolada.\'],\n    [\'Extra Trees\',\'Árvores extremamente aleatórias\',\'Parecido com Random Forest, mas usa cortes mais aleatórios nas árvores para reduzir variância.\',\'Útil para testar se os sinais continuam bons mesmo com maior aleatoriedade.\'],\n    [\'XGBoost\',\'Gradient boosting\',\'Cria árvores em sequência; cada nova árvore tenta corrigir os erros das anteriores.\',\'Pode capturar padrões complexos, mas precisa de cuidado com pouco histórico.\'],\n    [\'LightGBM\',\'Gradient boosting otimizado\',\'Também usa boosting, mas com estratégia eficiente para treinar rápido em dados tabulares.\',\'Bom candidato quando a base crescer; no começo deve ser lido como modo sombra.\'],\n    [\'CatBoost\',\'Gradient boosting robusto\',\'Modelo de boosting desenhado para dados tabulares, com bom tratamento de variáveis categóricas.\',\'Pode ganhar relevância quando houver mais snapshots e variáveis categóricas confiáveis.\'],\n    [\'Ensemble\',\'Combinação de modelos\',\'Combina as previsões dos modelos supervisionados disponíveis, normalmente por média.\',\'Busca um sinal mais estável do que depender de um único modelo.\']\n  ];\n\n  function addStyle(){\n    if(document.getElementById(\'staticMlModelTablesStyle\')) return;\n    const style=document.createElement(\'style\');\n    style.id=\'staticMlModelTablesStyle\';\n    style.textContent=`\n      #staticMlModelTables{display:block}\n      .static-ml-group{margin:14px 0 16px;border:1px solid rgba(148,163,184,.18);border-radius:16px;background:rgba(15,23,42,.35);overflow:hidden}\n      .static-ml-group summary{cursor:pointer;list-style:none;padding:14px 16px;font-weight:800;display:flex;justify-content:space-between;gap:12px}\n      .static-ml-group summary::-webkit-details-marker{display:none}\n      .static-ml-group summary span{color:var(--muted);font-weight:600;font-size:.86rem}\n      .static-ml-group[open] summary{border-bottom:1px solid rgba(148,163,184,.14)}\n      .static-ml-table td,.static-ml-table th{white-space:nowrap}\n      .static-ml-table td:nth-child(3),.static-ml-table td:nth-child(6){font-weight:750}\n      .static-ml-explain-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;margin-top:12px}\n      .static-ml-explain-card{border:1px solid rgba(148,163,184,.18);border-radius:16px;padding:14px;background:rgba(15,23,42,.38)}\n      .static-ml-explain-card h4{margin:0 0 4px;font-size:1rem}\n      .static-ml-explain-card .model-type{font-size:.78rem;color:var(--muted);margin-bottom:8px}\n      .static-ml-explain-card p{margin:8px 0 0;color:var(--muted);font-size:.88rem;line-height:1.45}\n    `;\n    document.head.appendChild(style);\n  }\n\n  function brNumber(v,d=2){\n    const n=Number(v);\n    if(!Number.isFinite(n)) return \'—\';\n    return n.toLocaleString(\'pt-BR\',{minimumFractionDigits:d,maximumFractionDigits:d});\n  }\n\n  function brScore(v){\n    const n=Number(v);\n    return Number.isFinite(n) ? brNumber(n,2) : \'—\';\n  }\n\n  function brReturn(v){\n    const n=Number(v);\n    if(!Number.isFinite(n)) return \'—\';\n    const pct=Math.abs(n)<=1.5 ? n*100 : n;\n    return (pct>0?\'+\':\'\')+brNumber(pct,2)+\'%\';\n  }\n\n  function getTicker(row,kind){\n    if(!row) return \'—\';\n    if(kind===\'acoes\') return row.ticker || row.ativo || row[\'Ação\'] || row.Acao || row.Papel || row.Codigo || row[\'Código\'] || \'—\';\n    return row.ticker || row.ativo || row.FUNDOS || row.Fundo || row.Codigo || row[\'Código\'] || \'—\';\n  }\n\n  function getScore(row,key){\n    if(!row) return null;\n    return row.score_modelo ?? row[key] ?? row.score_ensemble ?? row.score_top ?? row.Score ?? row.score ?? null;\n  }\n\n  function getRet(row){\n    if(!row) return null;\n    return row.retorno_esperado_7d ?? row.Retorno_Esperado_7d ?? row.retorno_esperado_30d ?? row.Retorno_Esperado_30d ?? null;\n  }\n\n  function payloadFromState(){\n    try{\n      if(typeof state !== \'undefined\' && state && state.data && state.data.modelos_ml) return state.data;\n    }catch(e){}\n    return null;\n  }\n\n  async function loadPayload(){\n    const s=payloadFromState();\n    if(s) return s;\n    try{\n      const idx=await fetch(\'data/index.json\',{cache:\'no-store\'}).then(r=>r.json());\n      const latest=[...idx].sort().at(-1);\n      return await fetch(`data/${latest}.json`,{cache:\'no-store\'}).then(r=>r.json());\n    }catch(e){\n      return null;\n    }\n  }\n\n  function rowsByModel(ml,kind,modelName,key){\n    const fromByModel=ml?.ranking_por_modelo?.[kind]?.[modelName];\n    if(Array.isArray(fromByModel) && fromByModel.length) return fromByModel.slice(0,20);\n\n    const base=ml?.ranking?.[kind];\n    if(!Array.isArray(base)) return [];\n    return base\n      .filter(r=>r && r[key]!=null && !Number.isNaN(Number(r[key])))\n      .slice()\n      .sort((a,b)=>Number(b[key])-Number(a[key]))\n      .slice(0,20)\n      .map((r,i)=>Object.assign({},r,{rank:i+1,score_modelo:r[key]}));\n  }\n\n  function renderExplain(ml){\n    const grid=document.getElementById(\'staticMlModelExplainGrid\');\n    if(!grid) return;\n    const data=Array.isArray(ml?.explicacao_modelos) && ml.explicacao_modelos.length\n      ? ml.explicacao_modelos.map(x=>[x.modelo,x.tipo,x.como_funciona,x.como_ler])\n      : EXPLAIN;\n\n    grid.innerHTML=data.map(x=>`\n      <div class="static-ml-explain-card">\n        <h4>${x[0] || \'Modelo\'}</h4>\n        <div class="model-type">${x[1] || \'\'}</div>\n        <p>${x[2] || \'\'}</p>\n        <p><b>Como ler:</b> ${x[3] || \'\'}</p>\n      </div>\n    `).join(\'\');\n  }\n\n  async function render(){\n    addStyle();\n    const container=document.getElementById(\'staticMlModelTables\');\n    if(!container) return;\n\n    const payload=await loadPayload();\n    const ml=payload?.modelos_ml;\n    if(!ml){\n      container.innerHTML=\'<div class="muted-cell">Não consegui carregar os dados de modelos_ml do JSON atual.</div>\';\n      renderExplain({});\n      return;\n    }\n\n    const horizon=ml.horizonte_principal || \'7d\';\n    const html=MODELS.map(([name,key])=>{\n      const acoes=rowsByModel(ml,\'acoes\',name,key);\n      const fiis=rowsByModel(ml,\'fiis\',name,key);\n      if(!acoes.length && !fiis.length) return \'\';\n\n      const rows=Array.from({length:20},(_,i)=>{\n        const a=acoes[i] || {};\n        const f=fiis[i] || {};\n        return `<tr>\n          <td>#${i+1}</td>\n          <td>${getTicker(a,\'acoes\')}</td>\n          <td class="num">${brScore(getScore(a,key))}</td>\n          <td class="num">${brReturn(getRet(a))}</td>\n          <td>${getTicker(f,\'fiis\')}</td>\n          <td class="num">${brScore(getScore(f,key))}</td>\n          <td class="num">${brReturn(getRet(f))}</td>\n        </tr>`;\n      }).join(\'\');\n\n      return `<details class="static-ml-group" ${name===\'Ensemble\'?\'open\':\'\'}>\n        <summary>${name}<span>${acoes.length} ações · ${fiis.length} FIIs · horizonte ${horizon}</span></summary>\n        <div class="table-wrap">\n          <table class="table rec-table static-ml-table">\n            <thead>\n              <tr>\n                <th>#</th>\n                <th>Ação</th>\n                <th>Score modelo</th>\n                <th>Ret. esp.</th>\n                <th>FII</th>\n                <th>Score modelo</th>\n                <th>Ret. esp.</th>\n              </tr>\n            </thead>\n            <tbody>${rows}</tbody>\n          </table>\n        </div>\n      </details>`;\n    }).filter(Boolean).join(\'\');\n\n    container.innerHTML=html || \'<div class="muted-cell">Ainda não há scores por modelo suficientes para montar o Top 20 por modelo.</div>\';\n    renderExplain(ml);\n  }\n\n  document.addEventListener(\'DOMContentLoaded\',()=>{render(); setTimeout(render,500); setTimeout(render,1500);});\n  document.addEventListener(\'click\',e=>{\n    if(e.target && (e.target.closest(\'.tab\') || e.target.closest(\'[data-tab]\') || e.target.closest(\'button\'))){\n      setTimeout(render,300);\n    }\n  });\n  render();\n})();\n</script>'


def remove_old_force_patch(text: str) -> str:
    return re.sub(
        r"\n?<!-- BEGIN FORCE ML MODEL TABLES -->.*?<!-- END FORCE ML MODEL TABLES -->\n?",
        "\n",
        text,
        flags=re.S,
    )


def insert_static_section(text: str) -> str:
    if STATIC_SECTION_ID in text:
        return text

    marker = 'id="mlRankingBody"'
    pos = text.find(marker)
    if pos < 0:
        raise RuntimeError('Não encontrei id="mlRankingBody" no docs/index.html')

    table_end = text.find("</table>", pos)
    if table_end < 0:
        raise RuntimeError("Encontrei mlRankingBody, mas não encontrei </table> depois dele")

    insert_at = table_end + len("</table>")

    div_end = text.find("</div>", insert_at)
    if div_end >= 0 and div_end - insert_at < 300:
        insert_at = div_end + len("</div>")

    return text[:insert_at] + "\n" + STATIC_BLOCK.strip() + "\n" + text[insert_at:]


def insert_script(text: str) -> str:
    text = re.sub(
        r"\n?<script id=\"static-ml-model-tables-renderer\">.*?</script>\n?",
        "\n",
        text,
        flags=re.S,
    )

    idx = text.lower().rfind("</body>")
    if idx >= 0:
        return text[:idx] + "\n" + SCRIPT_BLOCK.strip() + "\n" + text[idx:]

    return text.rstrip() + "\n" + SCRIPT_BLOCK.strip() + "\n"


def main() -> None:
    if not HTML.exists():
        raise FileNotFoundError(f"Não encontrei {HTML}")

    text = HTML.read_text(encoding="utf-8")
    text = remove_old_force_patch(text)
    text = insert_static_section(text)
    text = insert_script(text)
    HTML.write_text(text, encoding="utf-8")

    print("[OK] Seção estática inserida logo depois da tabela atual de Modelos ML.")
    print("[OK] Script de preenchimento inserido no fim do HTML.")
    print("[OK] Mesmo se o JS falhar, o título 'Top 20 por modelo' agora deve aparecer na tela.")


if __name__ == "__main__":
    main()
