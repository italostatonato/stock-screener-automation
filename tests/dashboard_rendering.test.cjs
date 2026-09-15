const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const test = require('node:test');

const html = fs.readFileSync(path.join(__dirname, '../docs/index.html'), 'utf8');
const lines = html.split(/\r?\n/);
function source(name) {
  const start = lines.findIndex(line => new RegExp(`^    (?:async )?function ${name}\\(`).test(line));
  assert.ok(start >= 0, `Função ausente: ${name}`);
  if (lines[start].trimEnd().endsWith('}')) return lines[start];
  const end = lines.findIndex((line, i) => i > start && line === '    }');
  assert.ok(end > start);
  return lines.slice(start, end + 1).join('\n');
}

function renderingContext(data = {}) {
  const elements = {};
  const context = vm.createContext({
    state: {data, marketFallbackAttempted: true},
    document: {getElementById(id) { return elements[id] ||= {innerHTML:'', textContent:'', value:''}; }},
    scoreOf:()=>0, fmtNum:value=>Number(value).toFixed(2), fmtMoney:()=> 'R$ 10,00',
    fmtPct:()=> '1,00%', fmtBig:()=> '10',
    finite:value=>value!=null&&Number.isFinite(Number(value)),
    recNum:()=> '0',recPct:()=> '0%',mlScore:()=> '0',mlReturn:()=> '0%',
    mlExpectedReturn:()=> '0',mlRankMovement:()=>'',mlStatusClass:()=>'',renderMlPerformanceChart:()=>{},
    trendIcon:()=>'',scoreBar:()=>'',relativeTone:()=>'',metric:()=>'',sectorColor:()=> '#2563EB',
    hybridSettings:{weights:{acoes_top20:.3,fiis_top20:.3}},
    fullAssetName:()=>'',signed:()=> '0',fmtCryptoPrice:()=> 'R$ 10,00',changeMarkup:()=>'',
  });
  vm.runInContext(lines.find(line=>line.startsWith('    const escapeAttr =')), context);
  for (const name of ['recurringAssetCell','renderRecorrentesTable','mlAssetCell',
                      'renderMlModelsTables','renderFiiSectorLegend','cardFii','cardAcao',
                      'renderCards','hybridTickers','renderHybridHoldings','renderFx','loadLiveMarketFallback']) {
    vm.runInContext(source(name), context);
  }
  return {context, elements};
}

const cases = [
  ['ticker recorrente', m=>({recorrentes:{acoes:[{ticker:m}]}}), 'renderRecorrentesTable()', 'recorrentesTableBody'],
  ['alias ticker recorrente', m=>({recorrentes:{fiis:[{Ticker:m}]}}), 'renderRecorrentesTable()', 'recorrentesTableBody'],
  ['empresa recorrente', m=>({recorrentes:{acoes:[{ticker:'TEST3',empresa:m}]}}), 'renderRecorrentesTable()', 'recorrentesTableBody'],
  ['setor recorrente', m=>({recorrentes:{fiis:[{ticker:'TEST11',setor:m}]}}), 'renderRecorrentesTable()', 'recorrentesTableBody'],
  ['data recorrente', m=>({recorrentes:{fiis:[{ticker:'TEST11',ultima_aparicao:m}]}}), 'renderRecorrentesTable()', 'recorrentesTableBody'],
  ['ticker ML', m=>({modelos_ml:{ranking:{acoes:[{Tipo:'ACAO',Ticker:m}]}}}), 'renderMlModelsTables()', 'mlRankingBody'],
  ['nome ML', m=>({modelos_ml:{ranking:{acoes:[{Tipo:'ACAO',Ticker:'TEST3',Nome:m}]}}}), 'renderMlModelsTables()', 'mlRankingBody'],
  ['legenda FII', m=>({fiis:[{SETOR:m}]}), 'renderFiiSectorLegend(state.data.fiis)', 'fiiSectorLegend'],
  ['ticker ação', m=>({acoes:[{'Ação':m}]}), 'renderCards("acoes")', 'acoesGrid'],
  ['nome ação', m=>({acoes:[{'Ação':'TEST3',Empresa:m}]}), 'renderCards("acoes")', 'acoesGrid'],
  ['ticker FII', m=>({fiis:[{FUNDOS:m}]}), 'renderCards("fiis")', 'fiisGrid'],
  ['setor FII', m=>({fiis:[{FUNDOS:'TEST11',SETOR:m}]}), 'renderCards("fiis")', 'fiisGrid'],
  ['ticker híbrida exportado', m=>({carteira_vs:{carteira_hibrida:{ativos:{acoes_top20:{tickers:[m]}}}}}), 'renderHybridHoldings({})', 'hybridHoldings'],
  ['ticker híbrida fallback', m=>({fiis:[{FUNDOS:m}]}), 'renderHybridHoldings({})', 'hybridHoldings'],
  ['par de câmbio', m=>({indicadores:{cambio:{['USD/'+m]:{valor:10}}}}), 'renderFx()', 'fxGrid'],
  ['nome cripto', m=>({indicadores:{cripto:[{nome:m,preco_brl:10}]}}), 'renderFx()', 'fxGrid'],
  ['símbolo cripto', m=>({indicadores:{cripto:[{simbolo:m,preco_brl:10}]}}), 'renderFx()', 'fxGrid'],
  ['ranking cripto', m=>({indicadores:{cripto:[{ranking_market_cap:m,preco_brl:10}]}}), 'renderFx()', 'fxGrid'],
];

for (const [label, makeData, code, id] of cases) {
  test(`${label}: metadados são texto, inclusive entidades em atributos`, () => {
    for (const marker of ['<img src=x onerror="&#97;&#108;&#101;&#114;&#116;(1)">', '<svg onload="1">']) {
      const {context, elements} = renderingContext(makeData(marker));
      vm.runInContext(code, context);
      assert.doesNotMatch(elements[id].innerHTML, /<(?:img|svg)\b/i);
      assert.match(elements[id].innerHTML, /&lt;(?:img|svg)/i);
    }
  });
}

test('timestamp de câmbio é escapado mesmo depois de truncado', () => {
  const {context, elements} = renderingContext({indicadores:{cambio:{'USD/BRL':{valor:10,atualizado_em:'<b>X</b>'}}}});
  vm.runInContext('renderFx()', context);
  assert.doesNotMatch(elements.fxGrid.innerHTML, /<b>X<\/b>/);
  assert.match(elements.fxGrid.innerHTML, /&lt;b&gt;X&lt;\/b&gt;/);
});

test('texto legítimo e preço conservam o conteúdo', () => {
  const {context, elements} = renderingContext({acoes:[{'Ação':'TEST3',Empresa:'A&B "Holding" <Classe> D\'Agua'}]});
  vm.runInContext('renderCards("acoes")', context);
  assert.match(elements.acoesGrid.innerHTML, /TEST3/);
  assert.match(elements.acoesGrid.innerHTML, /A&amp;B &quot;Holding&quot; &lt;Classe&gt; D'Agua/);
  const cell = vm.runInContext('mlAssetCell({Ticker:"TEST3",Nome:"Empresa",preco_atual:10})', context);
  assert.match(cell, /R\$ 10,00/);
});

test('fallback ao vivo usa os mesmos destinos protegidos e normaliza ranking', async () => {
  const marker = '<img src=x onerror="1">';
  const {context, elements} = renderingContext({});
  context.state.marketFallbackAttempted = false;
  context.fetch = async url => ({ok:true,json:async()=>url.includes('coingecko')
    ? [{name:marker,symbol:marker,market_cap_rank:marker,current_price:10}]
    : {USD:{code:'USD',codein:marker,bid:'10',create_date:'<b>X</b>'}}});
  await vm.runInContext('loadLiveMarketFallback()', context);
  assert.doesNotMatch(elements.fxGrid.innerHTML, /<(?:img|b)\b/i);
  assert.equal(context.state.data.indicadores.cripto[0].ranking_market_cap, 1);
});
