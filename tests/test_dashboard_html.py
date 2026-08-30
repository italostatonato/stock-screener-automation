from pathlib import Path


HTML = Path("docs/index.html").read_text(encoding="utf-8")


def test_dashboard_tabs_e_buscas_tem_rotulos_acessiveis():
    assert 'role="tablist" aria-label="Seções do Radar Semanal"' in HTML
    assert HTML.count('role="tab"') == 8
    assert 'aria-controls="overview" aria-selected="true"' in HTML
    assert 'for="searchFiis">Buscar FII ou setor</label>' in HTML
    assert 'for="searchAcoes">Buscar ação ou empresa</label>' in HTML
    assert "item.setAttribute('aria-selected',active?'true':'false')" in HTML
    assert "item.setAttribute('aria-hidden',active?'false':'true')" in HTML


def test_dashboard_graficos_tem_descricao_e_textos_revisados():
    assert HTML.count('role="img" aria-label=') >= 9
    assert "Índices em para comparação visual" not in HTML
    assert "Índices em base 100 para comparação visual" in HTML
    assert "Carteira FIIs Top 20 ·" not in HTML
    assert "Carteira Ações Top 20 ·" not in HTML


def test_dashboard_mobile_reduz_histograma_e_nao_forca_scroll_ml():
    assert "compactHistogram?Math.max(4,Math.ceil(span/6))" in HTML
    assert '.ml-control-group{display:grid;width:100%;overflow:visible' in HTML
    assert '.ml-control-group[aria-label="Classe de ativos"]' in HTML


def test_dashboard_tooltip_nao_repete_ticker_como_nome_completo():
    assert "function fullAssetName(rec,ticker,type)" in HTML
    assert "Nome completo não disponível na fonte" in HTML
