from pathlib import Path


HTML = Path("docs/index.html").read_text(encoding="utf-8")


def test_dashboard_tabs_e_buscas_tem_rotulos_acessiveis():
    assert 'role="tablist" aria-label="Seções do Radar Semanal"' in HTML
    assert HTML.count('role="tab"') == 6
    assert 'aria-controls="introducao" aria-selected="true"' in HTML
    assert 'aria-controls="overview" aria-selected="false"' in HTML
    assert 'for="searchFiis">Buscar FII ou setor</label>' in HTML
    assert 'for="searchAcoes">Buscar ação ou empresa</label>' in HTML
    assert "item.setAttribute('aria-selected',active?'true':'false')" in HTML
    assert "item.setAttribute('aria-hidden',active?'false':'true')" in HTML
    ordem = ["introducao", "overview", "hibrida", "modelos", "top20", "indicadores"]
    posicoes = [HTML.index(f'id="tab-{tab}"') for tab in ordem]
    assert posicoes == sorted(posicoes)


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


def test_dashboard_cards_priorizam_valores_financeiros_sem_corte():
    assert 'grid-template-areas:"label value" "tone tone"!important' in HTML
    assert "grid-template-columns:minmax(0,1fr) max-content!important" in HTML
    assert "font-variant-numeric:tabular-nums" in HTML


def test_dashboard_tooltip_de_ml_e_compacto_e_nao_repete_contexto():
    assert "afterBody:items=>" in HTML
    assert "afterLabel:context=>" not in HTML
    assert "padding:8,bodySpacing:2,titleMarginBottom:4,boxWidth:7,boxHeight:7" in HTML


def test_dashboard_hibrida_exibe_novos_pesos_e_serie_rebalanceada():
    for key, value in [("acoes_top20", 30), ("fiis_top20", 30), ("cdi", 20), ("ivvb11", 20)]:
        assert f'data-hybrid-weight="{key}" min="0" max="100" step="1" value="{value}"' in HTML
    assert HTML.count('type="button" data-hybrid-preset=') == 5
    assert 'for="hybridAmount"' in HTML
    assert 'aria-describedby="hybridWeightStatus"' in HTML
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
    assert "Volume diário médio" in HTML
    assert "o volume usa a média de dois meses" in HTML


def test_dashboard_compensa_cabecalho_fixo_e_respeita_reducao_de_movimento():
    assert "scroll-padding-top:calc(var(--topbar-h,68px) + 16px)" in HTML
    assert "prefers-reduced-motion:reduce" in HTML
    assert "btn.scrollIntoView({behavior,block:'nearest',inline:'center'})" in HTML


def test_dashboard_mobile_tem_alvos_e_textos_mais_legiveis():
    assert ".tab,.kpi-window,.chart-period,.hero-tag-link,.github-top,.ml-chart-toggle{min-height:44px" in HTML
    assert ".kpi .label{font-size:11px!important" in HTML
    assert "#fiis .metric span,#acoes .metric span{font-size:11px!important" in HTML


def test_dashboard_estados_interativos_sao_anunciados():
    assert 'class="about-card" aria-labelledby="aboutItaloTitle"' in HTML
    assert 'id="aboutItaloBtn"' not in HTML
    assert 'aria-pressed="${active===key?' in HTML


def test_dashboard_oferece_janelas_mensais_nos_graficos():
    for months in [1, 3, 6, 12, 18, 24]:
        assert f"'{months}M': {{months:{months}, label:'{months}M'}}" in HTML
    assert "Object.entries(CHART_PERIODS)" in HTML
    assert "chartId==='proxyFiisChart' || chartId==='proxyAcoesChart'" in HTML
    assert "renderProxyCharts();" in HTML


def test_dashboard_hero_e_faixa_de_contexto_sao_compactos():
    assert 'grid-template-areas:"copy about status"' in HTML
    assert ".hero{padding:20px 0 14px!important}" in HTML
    assert ".asof strong{margin-top:5px!important;font-size:14px!important" in HTML
    assert ".signal-cell{display:flex;align-items:center;gap:9px;min-width:0;padding:9px 14px}" in HTML
    assert "DoD:{label:'DoD'" not in HTML


def test_dashboard_histograma_preserva_barras_das_extremidades():
    assert "valueLabelPlugin:{enabled:true,hideZero:true}" in HTML
    assert "offset:true,ticks:{maxRotation:0,minRotation:0}" in HTML
    assert "ticks:{precision:0,padding:6,callback:v=>fmtNum(Number(v),0)}" in HTML


def test_dashboard_reaproveita_payload_atual_sem_carregar_kpis_ocultos():
    assert "fetch('data/kpi-history.json'" not in HTML
    assert "window.__radarLatestPayload = state.data" in HTML
    assert 'fetch("data/index.json"' not in HTML
    assert 'fetch(`data/${latest}.json`' not in HTML


def test_visao_geral_nao_exibe_mais_a_faixa_de_kpis():
    assert 'id="kpis"' not in HTML
    assert "function renderKpis()" not in HTML
    assert "function renderKpiControls()" not in HTML
    assert "preloadSnapshotsForKpis()" not in HTML


def test_dashboard_tabelas_tem_legendas_acessiveis():
    assert HTML.count('<caption class="sr-only">') == 7


def test_visao_geral_prioriza_mudancas_lideres_e_um_unico_grafico():
    assert 'id="weeklyChanges"' in HTML
    assert 'id="overviewTopFive"' in HTML
    assert 'id="overviewPerformanceChart"' in HTML
    assert HTML.count('data-overview-type=') == 3
    assert 'id="rankTableBody"' not in HTML
    assert 'id="overviewFiisBacktestChart"' not in HTML
    assert 'id="overviewAcoesBacktestChart"' not in HTML
    assert "function renderOverviewChanges()" in HTML
    assert "function preloadOverviewComparison()" in HTML


def test_score_fontes_e_histograma_ficam_na_introducao():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(HTML, "html.parser")
    score = soup.find(id="score")
    assert score.find_parent(id="introducao") is not None
    assert score.find(id="scoreChart") is not None
    assert "Fontes de dados" in score.get_text()
    assert "Sobre o projeto" in score.get_text()
    assert soup.select_one("#indicadores #score") is None
    assert soup.find(id="tab-indicadores").get_text(strip=True) == "Indicadores"
    assert soup.select_one('#introducao .intro-route a[href="#score"]') is not None
    assert "if(scoreRequested) tabId='introducao';" in HTML
    assert "não devem ser comparados como se fossem a mesma escala econômica" in HTML


def test_exemplo_do_score_confere_com_o_calculo_real():
    from bs4 import BeautifulSoup
    import pandas as pd
    from src.scorer import ACOES_WEIGHTS, _percentil_score, ACOES_DIRECTION, score_acoes

    soup = BeautifulSoup(HTML, "html.parser")
    table = soup.find(id="scoreExampleTable")
    assert "score-example-data" in table.parent.get("class", [])
    assert len(soup.select_one(".score-example-layout").find_all(recursive=False)) == 2
    notes = [float(row.find_all("td")[-1].get_text()) for row in table.select("tbody tr")]
    ranks = [8, 3, 4, 5, 9, 4, 10]
    universe = pd.DataFrame({
        key: [rank] + [value for value in range(1, 11) if value != rank]
        for key, rank in zip(ACOES_WEIGHTS, ranks)
    })
    calculated = [_percentil_score(universe[key], ACOES_DIRECTION[key]).iloc[0] for key in ACOES_WEIGHTS]
    assert notes == calculated
    assert len(notes) == 7
    assert sum(notes) == 490
    assert sum(notes) / 7 == score_acoes(universe).iloc[0] == 70
    assert soup.select_one(".score-example-number").get_text() == "70,0"


def test_guia_do_score_explica_dados_ausentes_e_selecao_separada():
    from bs4 import BeautifulSoup

    text = BeautifulSoup(HTML, "html.parser").find(id="score").get_text(" ", strip=True)
    assert "antes dos filtros de seleção" in text
    assert "50 pontos e mantém seu peso de 1/7" in text
    assert "posição média das colocações empatadas" in text
    assert "uma casa decimal" in text
    assert "não são pontos extras no score" in text
    assert "não significa 70% de chance de lucro" in text



def test_tabela_de_dy_mostra_como_os_valores_viram_pontos():
    from bs4 import BeautifulSoup
    import pandas as pd
    from src.scorer import _percentil_score

    soup = BeautifulSoup(HTML, "html.parser")
    table = soup.find(id="scoreDyExampleTable")
    rows = [[cell.get_text(strip=True) for cell in row.find_all("td")] for row in table.select("tbody tr")]
    values = pd.Series([float(row[2].rstrip("%")) for row in rows])
    notes = [float(row[3]) for row in rows]
    assert values.tolist() == [2, 3, 4, 5, 6, 7, 8, 9, 10, 12]
    assert [int(row[0]) for row in rows] == list(range(1, 11))
    assert notes == _percentil_score(values, "max").tolist()
    assert rows[7] == ["8", "Ativo H", "9%", "80"]
    assert table.select_one("tr.dy-highlight").find_all("td")[1].get_text() == "Ativo H"
    assert "score-dy-data" in table.parent.get("class", [])
    assert len(soup.select_one(".score-dy-layout").find_all(recursive=False)) == 2
    text = soup.find(id="score-dy-example").get_text(" ", strip=True)
    assert "quantidade de DYs conhecidos" in text
    assert "o menor DY recebe 10 pontos" in text
    assert "não força o menor DY a receber zero" in text


def test_mesmo_dy_muda_de_nota_quando_o_grupo_muda():
    from bs4 import BeautifulSoup
    import pandas as pd
    import re
    from src.scorer import _percentil_score

    soup = BeautifulSoup(HTML, "html.parser")
    values = [float(value) for value in re.findall(r"\d+(?=%)", soup.find(id="scoreDyOtherValues").get_text())]
    assert values == [2, 3, 4, 5, 9, 10, 11, 12, 13, 14]
    index = values.index(9)
    score = _percentil_score(pd.Series(values), "max").iloc[index]
    assert score == 50
    assert soup.select_one(".score-dy-other-result").get_text() == "50 pontos"


def test_resumo_de_fiis_explica_limite_dos_proventos():
    assert "a carteira de FIIs considera a variação dos preços e não reinveste os proventos" in HTML


def test_simulacao_fica_aberta_abaixo_do_card_do_bloco_correspondente():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(HTML, "html.parser")
    columns = soup.select("#hibrida .hybrid-column")
    assert len(columns) == 4
    for column in columns:
        key = column.select_one("[data-hybrid-weight]")["data-hybrid-weight"]
        assert column.select_one(f"#hybridSimulation-{key}") is not None
        assert column.find("details") is None
    assert soup.find(id="hybridAmount")["value"] == "10.000,00"


def test_dashboard_apresentacao_abre_em_visualizacao_protegida():
    assert "/presentation/d/1I61xKNvQ8kfBDXqel5YaoVeTCqhdRXxYmw3mCQqed60/preview?rm=minimal" in HTML
    assert 'class="hero-tag-link presentation-link"' in HTML
    assert 'target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer"' in HTML
    assert 'aria-label="Abrir apresentação do Radar Semanal em modo somente leitura"' in HTML
