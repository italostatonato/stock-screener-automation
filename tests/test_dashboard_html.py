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


def test_dashboard_hibrida_exibe_novos_pesos_e_serie_rebalanceada():
    assert '<strong>30%</strong><span class="allocation-role">Motor de crescimento' in HTML
    assert '<strong>30%</strong><span class="allocation-role">Renda + imóveis' in HTML
    assert HTML.count('<strong>20%</strong>') >= 2
    assert "const HYBRID_TARGET_WEIGHTS={acoes_top20:.30,fiis_top20:.30,cdi:.20,ivvb11:.20}" in HTML
    assert "portfolioValue=previousPortfolio*(1+intervalReturn)" in HTML
    assert "Pesos-alvo reaplicados a cada nova composição semanal" in HTML


def test_dashboard_exibe_sete_indicadores_com_pesos_iguais_por_classe():
    assert HTML.count("Sete indicadores igualmente ponderados") == 2
    assert HTML.count("<td>14,29%</td>") == 14
    assert "DY médio (12 meses)" in HTML
    assert "Rentabilidade do período" in HTML
    assert "Taxa de administração" in HTML
    assert "Taxa de performance" in HTML
    assert "ROIC (ROInvC)" in HTML
    assert "ROE (RPL)" in HTML
    assert "Volume diário médio (3 meses)" in HTML
