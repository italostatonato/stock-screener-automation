// Prova local: executa apenas renderizadores extraídos do código real com DOM simulado.
// Não há navegador, rede, disparo de eventos HTML ou alteração de dados do projeto.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const html = fs.readFileSync(path.join(root, 'docs/index.html'), 'utf8');
const lines = html.split(/\r?\n/);
function source(name) {
  const start = lines.findIndex(line => line.startsWith(`    function ${name}(`));
  assert.ok(start >= 0, `Função ausente: ${name}`);
  if (lines[start].trimEnd().endsWith('}')) return lines[start];
  const end = lines.findIndex((line, index) => index > start && line === '    }');
  assert.ok(end > start);
  return lines.slice(start, end + 1).join('\n');
}
const marker = '<img src=x onerror="globalThis.__auditMarker=1">';
const elements = {};
const doc = {getElementById(id) {return elements[id] ||= {innerHTML:'', textContent:'', value:''};}};
const data = {
  fiis:[{FUNDOS:marker, SETOR:marker}], acoes:[{'Ação':'TEST3', Empresa:marker}],
  recorrentes:{acoes:[{ticker:'TEST3', empresa:marker}], fiis:[]},
  modelos_ml:{ranking:{acoes:[{Tipo:'ACAO',Ticker:'TEST3',Nome:marker}], fiis:[]}},
  indicadores:{cambio:{['USD/'+marker]:{valor:5}}, cripto:[{nome:marker,simbolo:'TEST',preco_brl:1}]}
};
const context = vm.createContext({
  state:{data,marketFallbackAttempted:true}, document:doc,
  scoreOf:()=>0, fmtNum:()=> '0', fmtMoney:()=> 'R$ 0', fmtPct:()=> '0%', fmtBig:()=> '0',
  finite:value=>value!=null&&Number.isFinite(Number(value)),
  recNum:()=> '0',recPct:()=> '0%',mlScore:()=> '0',mlReturn:()=> '0%',
  mlExpectedReturn:()=> '0',mlRankMovement:()=>'',mlStatusClass:()=>'',renderMlPerformanceChart:()=>{},
  trendIcon:()=>'',scoreBar:()=>'',relativeTone:()=>'',metric:()=>'',sectorColor:()=> '#2563EB',
  hybridSettings:{weights:{acoes_top20:.3,fiis_top20:.3}},
  hybridTickers:()=>[marker],fullAssetName:()=>'',signed:()=> '0',
  fmtCryptoPrice:()=> 'R$ 0',changeMarkup:()=>'',
});
vm.runInContext(lines.find(line=>line.startsWith('    const escapeAttr =')),context);
for (const name of ['rankAssetCell','renderRankTable','recurringAssetCell','renderRecorrentesTable',
                    'mlAssetCell','renderMlModelsTables','renderFiiSectorLegend','cardFii','cardAcao',
                    'renderCards','renderHybridHoldings','renderFx']) {
  vm.runInContext(source(name),context,{timeout:1000});
}
const cases = [
  ['Ranking','renderRankTable()','rankTableBody',1797],
  ['Recorrentes','renderRecorrentesTable()','recorrentesTableBody',1822],
  ['Ranking ML','renderMlModelsTables()','mlRankingBody',2043],
  ['Legenda de setores','renderFiiSectorLegend(state.data.fiis)','fiiSectorLegend',2097],
  ['Cards de ações','renderCards("acoes")','acoesGrid',2106],
  ['Cards de FIIs','renderCards("fiis")','fiisGrid',2106],
  ['Carteira híbrida','renderHybridHoldings({})','hybridHoldings',2817],
  ['Câmbio e cripto','renderFx()','fxGrid',3029]
];
const results=cases.map(([label,code,id,line])=>{
  vm.runInContext(code,context,{timeout:1000});
  const output=elements[id].innerHTML;
  assert.ok(output.includes(marker), `${label}: marcador não propagado`);
  return {label,path:'docs/index.html',line,marker_preserved_as_markup:true,
    rendered_excerpt:output.slice(Math.max(0,output.indexOf(marker)-40),output.indexOf(marker)+marker.length+40)};
});
assert.ok(!context.__auditMarker,'O evento HTML não deveria executar nesta prova');
context.marker=marker;
const escaped=vm.runInContext('escapeAttr(marker)',context);
assert.ok(!escaped.includes('<img'));
const result={method:'Renderizadores reais em Node VM; DOM simulado, sem browser ou rede.',
  limitations:['Não executa evento onerror: prova propagação de markup até innerHTML, não exploração em produção.',
    'Formatação numérica, gráficos e seleção de tickers híbridos usam stubs; fluxo da origem é validado separadamente por revisão estática.',
    'Não demonstra que um visitante possa alterar os provedores.'],
  cases:results,unique_sinks:7,checks:8,control:{escapeAttr_neutralizes_marker:true},
  event_executed:false};
fs.writeFileSync(path.join(__dirname,'validacao-xss.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({checks:8,unique_sinks:7,all_preserved_markup:true,escape_control_passed:true,event_executed:false}));
