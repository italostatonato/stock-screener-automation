// Exercises the JavaScript shipped in the dashboard, without network or a browser.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../docs/index.html'),'utf8');
const between=(start,end)=>html.slice(html.indexOf(start),html.indexOf(end,html.indexOf(start)));

function loadDashboard(data=fixture()){
  class Element{
    constructor(dataset={}){this.dataset=dataset;this.value='';this.innerHTML='';this.textContent='';this.hidden=false;this.children=[];this.attributes={};this.listeners={};}
    setAttribute(name,value){this.attributes[name]=value;}
    addEventListener(name,fn){(this.listeners[name]??=[]).push(fn);}
    removeEventListener(name,fn){this.listeners[name]=(this.listeners[name]||[]).filter(listener=>listener!==fn);}
    getRootNode(){return context.document;}
    setSelectionRange(start,end){this.selectionStart=start;this.selectionEnd=end;}
    edit(text,start=0,end=this.value.length){
      context.document.activeElement=this;
      this.setSelectionRange(start,end);
      this.dispatch('keydown',{key:'Unidentified'});
      let prevented=false;
      this.dispatch('beforeinput',{cancelable:true,inputType:'insertText',data:text,preventDefault:()=>{prevented=true;}});
      if(prevented) return;
      this.value=this.value.slice(0,start)+text+this.value.slice(end);
      this.setSelectionRange(start+text.length,start+text.length);
      this.dispatch('input');
    }
    querySelectorAll(selector){return selector==='[data-hybrid-preset]'?presets:[];}
    dispatch(name,event={}){this.listeners[name]?.forEach(listener=>listener(event));}
  }
  const keys=['acoes_top20','fiis_top20','cdi','ivvb11'];
  const presets=['agressivo','meio_agressivo','balanceado','conservador','muito_conservador'].map(key=>new Element({hybridPreset:key}));
  const inputs=keys.map(key=>new Element({hybridWeight:key}));
  const feet=keys.map(key=>new Element({hybridFoot:key}));
  const elements=Object.fromEntries(['hybridControls','hybridAmount','hybridWeightStatus','hybridProfileName','hybridResults','hybridAmountStatus','hybridSimulationNote','hybridSimulationSummary','hybridHoldings','hybridCompositionBody','hybridPortfolioNote','hybridUnavailable','hybridDistributionBar','hybridDistributionLegend',...keys.map(key=>`hybridSimulation-${key}`)].map(id=>[id,new Element()]));
  inputs.forEach((input,index)=>elements[`hybridWeight-${keys[index]}`]=input);
  const context=vm.createContext({
    state:{data,charts:{},chartWindows:{}},BR:'pt-BR',
    document:{getElementById:id=>elements[id],addEventListener:()=>{},removeEventListener:()=>{},querySelectorAll:selector=>({'[data-hybrid-preset]':presets,'[data-hybrid-weight]':inputs,'[data-hybrid-foot]':feet}[selector]||[])},
    getComputedStyle:()=>({getPropertyValue:()=>''}),
    setTimeout:()=>1,clearTimeout:()=>{},
    ensureChartPeriodControls:()=>{},filteredLabelsForPeriod:labels=>labels,
    makeChart:(id,config)=>context.chart=config,baseOptions:options=>options,
    axisTitle:()=>({}),chartMaxTicks:()=>6,diffPhrase:()=>'',
    emptyPortfolioChart:()=>{context.chart=null;}
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../docs/assets/vendor/imask-7.6.1.min.js'),'utf8'),context);
  vm.runInContext([
    between('    const fmtNum =','    function mergeDeep'),
    between('    function seriesMap','    function emptyLineChart'),
    between('    function lastNumeric','    function diffPhrase'),
    between('const CHART_PERIODS','    function ensureChartPeriodControls'),
    between('    function alignedReturnForWindow','    function renderPortfolioComparison')
  ].join('\n'),context);
  return {context,elements,presets,inputs,feet,run:code=>vm.runInContext(code,context)};
}
function fixture(){
  return {data:'2026-01-16',acoes:[{'Ação':'AAAA3','Preço':10},{'Ação':'BBBB4','Preço':25}],fiis:[{FUNDOS:'CCCC11','PREÇO ATUAL (R$)':20}],benchmarks:{IVVB11:[{data:'2026-01-16',valor:50}]}};
}
function history(){
  const dates=['2026-01-02','2026-01-09','2026-01-16'];
  const components=['acoes_top20','fiis_top20','cdi','ivvb11'].map(key=>({chave:key,nome:key,serie:dates.map((date,index)=>({data:date,valor:key==='acoes_top20'?[100,110,99][index]:100}))}));
  return {disponivel:true,componentes:components,serie:dates.map(data=>({data,valor:100})),comparativos:{},ativos:{}};
}
const close=(actual,expected,epsilon=1e-8)=>assert.ok(Math.abs(actual-expected)<epsilon,`${actual} != ${expected}`);

test('all inline scripts compile',()=>{
  const scripts=[...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)];
  scripts.forEach((match,index)=>new vm.Script(match[1],{filename:`dashboard-script-${index}`}));
});

test('five presets total 100%, preserve balanced and increase CDI progressively',()=>{
  const {run}=loadDashboard();
  assert.equal(run('Object.keys(HYBRID_PRESETS).length'),5);
  assert.equal(run('Object.values(HYBRID_PRESETS).every(p=>validHybridWeights(p.weights))'),true);
  assert.equal(run('JSON.stringify(HYBRID_PRESETS.balanceado.weights)'),JSON.stringify({acoes_top20:.3,fiis_top20:.3,cdi:.2,ivvb11:.2}));
  assert.equal(run('Object.values(HYBRID_PRESETS).map(p=>p.weights.cdi).join(",")'),'0.05,0.1,0.2,0.55,0.8');
});

test('BRL mask separates the numeric value from Brazilian formatting',()=>{
  const {context,run}=loadDashboard();
  run('const mask=createHybridAmountMask(document.getElementById("hybridAmount"))');
  for(const [text,value,formatted] of [['10.000,00',10000,'10.000,00'],['R$ 1.234,56',1234.56,'1.234,56'],['10000',10000,'10.000,00'],['1.000',1000,'1.000,00']]){
    context.input=text;
    run('mask.value=input');
    assert.equal(run('mask.typedValue'),value);
    assert.equal(run('mask.value'),formatted);
  }
});

test('currency edits regroup thousands, preserve the caret and update simulation values',()=>{
  for(const [text,start,end,expected,value,caret] of [
    ['5',0,0,'510.000,00',510000,1],
    ['5',4,4,'100.500,00',100500,5],
    ['5',6,6,'100.005,00',100005,7],
    ['9',7,8,'10.000,90',10000.9,8],
    ['9',7,7,'10.000,90',10000.9,8],
    ['9',8,8,'10.000,09',10000.09,9],
    ['',1,2,'1.000,00',1000,1],
    ['250',0,2,'250.000,00',250000,3]
  ]){
    const {run,elements}=loadDashboard(); run('renderHybridPortfolio()');
    elements.hybridAmount.edit(text,start,end);
    assert.equal(elements.hybridAmount.value,expected);
    assert.equal(elements.hybridAmount.selectionStart,caret);
    assert.equal(run('hybridSettings.amount'),value);
    assert.equal(elements.hybridAmount.attributes['aria-invalid'],'false');
  }
});

test('currency input accepts paste and intermediate edits, then pads cents on blur',()=>{
  const {run,elements}=loadDashboard(); run('renderHybridPortfolio()');
  const input=elements.hybridAmount;
  for(const [text,value] of [['R$ 25.678,90',25678.9],['25678.90',25678.9],['25.678',25678],['1000000000001',null],['',null]]){
    input.edit(text);
    assert.equal(run('hybridSettings.amount'),value,text);
  }
  for(const digit of '1234') input.edit(digit,input.value.length,input.value.length);
  assert.equal(input.value,'1.234');
  assert.equal(run('hybridSettings.amount'),1234);
  input.dispatch('blur');
  assert.equal(input.value,'1.234,00');
});

test('purchase quantities use snapshot prices, whole units and direct CDI allocation',()=>{
  const {run}=loadDashboard();
  const result=run('buildHybridSimulation(state.data,HYBRID_TARGET_WEIGHTS,1000)');
  assert.equal(result.totalCents,100000);
  assert.equal(result.cdiCents,20000);
  assert.equal(result.securitiesCents,80000);
  assert.equal(result.remainingCents,0);
  assert.equal(result.groups[0].rows[0].quantity,15);
  assert.equal(result.groups[0].rows[1].quantity,6);
  assert.equal(result.groups[1].rows[0].quantity,15);
  assert.equal(result.groups[3].rows[0].quantity,4);
});

test('all presets conserve cents, never exceed an asset target, and keep residual cash',()=>{
  const {context,run}=loadDashboard();
  for(const amount of [1000,1000.01,1000.02,1000.03,1234.56,10000.01,1000000000000]){
    context.amount=amount;
    const results=run('Object.values(HYBRID_PRESETS).map(p=>buildHybridSimulation(state.data,p.weights,amount))');
    for(const result of results){
      assert.equal(result.totalCents,Math.round(amount*100));
      assert.equal(result.investedCents+result.remainingCents,result.totalCents);
      assert.equal(result.groups.reduce((sum,group)=>sum+group.budgetCents,0),result.totalCents);
      for(const row of result.groups.flatMap(group=>group.rows)){
        assert.equal(row.investedCents+row.remainingCents,row.targetCents);
        assert.ok(row.remainingCents>=0);
        if(row.quantity!==null) assert.ok(Number.isInteger(row.quantity));
      }
    }
  }
});

test('missing prices and compositions stay in cash; IVVB11 never uses a future quote or base 100',()=>{
  const data=fixture();
  data.acoes[0]['Preço']=null;
  data.fiis=[];
  data.benchmarks.IVVB11=[{data:'2026-01-17',valor:1}];
  data.carteira_vs={carteira_hibrida:history()};
  const {run}=loadDashboard(data);
  const result=run('buildHybridSimulation(state.data,HYBRID_TARGET_WEIGHTS,1000)');
  assert.equal(result.remainingCents,65000);
  assert.equal(result.groups[0].rows[0].quantity,null);
  assert.equal(result.groups[1].rows[0].ticker,null);
  assert.equal(result.groups[3].rows[0].priceCents,null);
  assert.equal(result.groups[3].rows[0].investedCents,0);
});

test('latest IVVB11 quote on or before snapshot is used regardless of series order',()=>{
  const data=fixture();
  data.benchmarks.IVVB11=[{data:'2026-01-15',valor:40},{data:'2026-01-17',valor:1},{data:'2026-01-14',valor:20}];
  const {run}=loadDashboard(data);
  const row=run('buildHybridSimulation(state.data,HYBRID_TARGET_WEIGHTS,1000).groups[3].rows[0]');
  assert.equal(row.quantity,5);
  assert.equal(row.quoteDate,'2026-01-15');
  assert.equal(row.priceCents,4000);
});

test('invalid and zero-sum allocations do not produce a simulation',()=>{
  const {run}=loadDashboard();
  for(const weights of ['{acoes_top20:0,fiis_top20:0,cdi:0,ivvb11:0}','{acoes_top20:-.1,fiis_top20:.3,cdi:.6,ivvb11:.2}','{acoes_top20:NaN,fiis_top20:.3,cdi:.2,ivvb11:.2}']){
    assert.equal(run(`buildHybridSimulation(state.data,${weights},1000)`),null);
  }
  assert.equal(run('buildHybridSimulation(state.data,HYBRID_TARGET_WEIGHTS,null)'),null);
  assert.equal(run('buildHybridSimulation(state.data,HYBRID_TARGET_WEIGHTS,0)'),null);
  assert.equal(run('buildHybridSimulation(state.data,HYBRID_TARGET_WEIGHTS,999.99)'),null);
});

test('100% CDI works and zero-weight blocks never buy units',()=>{
  const {run}=loadDashboard();
  const result=run('buildHybridSimulation(state.data,{acoes_top20:0,fiis_top20:0,cdi:1,ivvb11:0},1123.45)');
  assert.equal(result.cdiCents,112345);
  assert.equal(result.securitiesCents,0);
  assert.equal(result.remainingCents,0);
});

test('custom percentages use whole points and require an exact 100% total',()=>{
  const {run}=loadDashboard();
  assert.equal(run('validHybridWeights({acoes_top20:.33,fiis_top20:.33,cdi:.17,ivvb11:.17})'),true);
  assert.equal(run('validHybridWeights({acoes_top20:.3333,fiis_top20:.3333,cdi:.1667,ivvb11:.1667})'),false);
  assert.equal(run('validHybridWeights({acoes_top20:.33333,fiis_top20:.33333,cdi:.16667,ivvb11:.16667})'),false);
  assert.equal(run('validHybridWeights({acoes_top20:.3,fiis_top20:.3,cdi:.2,ivvb11:.200000001})'),false);
  const result=run('buildHybridSimulation(state.data,{acoes_top20:.33,fiis_top20:.33,cdi:.17,ivvb11:.17},9999.99)');
  assert.equal(result.investedCents+result.remainingCents,999999);
});

test('increasing a weight takes one point from the largest other block; decreasing returns it',()=>{
  const {run}=loadDashboard();
  const up=run('rebalanceHybridWeights(HYBRID_TARGET_WEIGHTS,"acoes_top20",31)');
  close(up.acoes_top20,.31); close(up.fiis_top20,.29); close(up.cdi,.2); close(up.ivvb11,.2);
  const down=run('rebalanceHybridWeights(HYBRID_TARGET_WEIGHTS,"cdi",19)');
  close(down.acoes_top20,.31); close(down.fiis_top20,.3); close(down.cdi,.19); close(down.ivvb11,.2);
  // The changed block stays selected even when it is already the largest.
  const largest=run('rebalanceHybridWeights(HYBRID_PRESETS.agressivo.weights,"acoes_top20",46)');
  close(largest.acoes_top20,.46); close(largest.ivvb11,.29);
});

test('typed jumps reevaluate the largest donor and can reach 0% or 100% without negative weights',()=>{
  const {context,run}=loadDashboard();
  const jump=run('rebalanceHybridWeights(HYBRID_TARGET_WEIGHTS,"cdi",23)');
  close(jump.acoes_top20,.28); close(jump.fiis_top20,.29); close(jump.cdi,.23);
  for(const key of ['acoes_top20','fiis_top20','cdi','ivvb11']){
    context.key=key;
    for(let target=0;target<=100;target++){
      context.target=target;
      assert.equal(run('validHybridWeights(rebalanceHybridWeights(HYBRID_TARGET_WEIGHTS,key,target))'),true);
      close(run('rebalanceHybridWeights(HYBRID_TARGET_WEIGHTS,key,target)[key]'),target/100);
    }
  }
  run('hybridSettings.weights=rebalanceHybridWeights(HYBRID_TARGET_WEIGHTS,"cdi",100)');
  const fromZero=run('rebalanceHybridWeights(hybridSettings.weights,"acoes_top20",1)');
  close(fromZero.acoes_top20,.01); close(fromZero.cdi,.99);
  for(const target of [-1,101,20.5,NaN]){
    context.target=target;
    assert.equal(run('rebalanceHybridWeights(HYBRID_TARGET_WEIGHTS,"cdi",target)'),null);
  }
});

test('historical returns compound at each rebalance and contributions reconcile',()=>{
  const {context,run}=loadDashboard();
  context.hybrid=history();
  const result=run('calculateHybridHistory(hybrid.componentes,hybrid.serie.map(row=>row.data),HYBRID_TARGET_WEIGHTS)');
  close(result.weightedReturn[1],3);
  close(result.weightedReturn[2],-.09);
  close(Object.values(result.componentReturns.contributions).reduce((a,b)=>a+b,0),-.09);
  const aggressive=run('calculateHybridHistory(hybrid.componentes,hybrid.serie.map(row=>row.data),HYBRID_PRESETS.agressivo.weights)');
  close(aggressive.weightedReturn[2],-.2025);
  const window=run('calculateHybridHistory(hybrid.componentes,hybrid.serie.slice(1).map(row=>row.data),HYBRID_TARGET_WEIGHTS)');
  close(window.weightedReturn[0],0);
  close(window.weightedReturn[1],-3);
});

test('missing active history does not display a partial total; zero-weight history is optional',()=>{
  const {context,run}=loadDashboard();
  context.hybrid=history();
  run('hybrid.componentes[3].serie=[]');
  const missing=run('calculateHybridHistory(hybrid.componentes,hybrid.serie.map(row=>row.data),HYBRID_TARGET_WEIGHTS)');
  assert.ok(missing.weightedReturn.every(value=>value===null));
  assert.equal(missing.componentReturns.contributions.acoes_top20,null);
  const cdi=run('calculateHybridHistory(hybrid.componentes,hybrid.serie.map(row=>row.data),{acoes_top20:0,fiis_top20:0,cdi:1,ivvb11:0})');
  assert.ok(cdi.weightedReturn.every(value=>value===0));
});

test('balanced history matches exported snapshot within its rounding precision',()=>{
  const dates=JSON.parse(fs.readFileSync(path.join(__dirname,'../docs/data/index.json'),'utf8'));
  const data=JSON.parse(fs.readFileSync(path.join(__dirname,`../docs/data/${dates[0]}.json`),'utf8'));
  const {run}=loadDashboard(data);
  const result=run('calculateHybridHistory(state.data.carteira_vs.carteira_hibrida.componentes,state.data.carteira_vs.carteira_hibrida.serie.map(row=>row.data),HYBRID_TARGET_WEIGHTS)');
  const hybrid=data.carteira_vs.carteira_hibrida;
  result.weightedReturn.forEach((value,index)=>close(value,hybrid.serie[index].valor-100,.001));
});

test('preset and input events update weights, holdings, purchases, table and chart together',()=>{
  const data=fixture(); data.carteira_vs={carteira_hibrida:history()};
  const {context,run,elements,presets,inputs,feet}=loadDashboard(data);
  run('renderHybridPortfolio()');
  presets[0].dispatch('click');
  assert.equal(inputs[0].value,'45');
  assert.equal(presets[0].attributes['aria-pressed'],'true');
  assert.equal(presets[2].attributes['aria-pressed'],'false');
  assert.match(elements.hybridHoldings.innerHTML,/22,50% por ativo/);
  assert.match(elements.hybridCompositionBody.innerHTML,/45,00%/);
  assert.match(elements['hybridSimulation-acoes_top20'].innerHTML,/225 ações/);
  assert.match(feet[0].innerHTML,/22,50% por ativo/);
  assert.match(context.chart.data.datasets[0].label,/Agressivo/);
  assert.equal(elements.hybridDistributionBar.attributes['aria-label'],'Ações BR: 45%; FIIs: 20%; CDI: 5%; IVVB11: 30%');
  assert.match(elements.hybridDistributionBar.innerHTML,/width:45%/);
  close(context.chart.data.datasets[0].data[2],-.2025);
  inputs[0].value='40'; inputs[0].dispatch('input');
  assert.equal(elements.hybridResults.hidden,false);
  assert.equal(inputs[3].value,'35');
  assert.equal(elements.hybridDistributionBar.attributes['aria-label'],'Ações BR: 40%; FIIs: 20%; CDI: 5%; IVVB11: 35%');
  assert.match(elements.hybridWeightStatus.textContent,/Total: 100%/);
  inputs[2].value='10'; inputs[2].dispatch('input');
  assert.equal(elements.hybridResults.hidden,false);
  assert.equal(inputs[0].value,'35');
  assert.match(elements.hybridProfileName.textContent,/Personalizado/);
  elements.hybridAmount.edit('1.000,00');
  assert.match(elements['hybridSimulation-acoes_top20'].innerHTML,/17 ações/);
  elements.hybridAmount.edit('-1');
  assert.equal(elements.hybridAmount.attributes['aria-invalid'],'true');
  assert.match(elements['hybridSimulation-acoes_top20'].innerHTML,/Informe um aporte válido/);
  assert.equal(elements.hybridResults.hidden,false);
});

test('snapshot changes refresh purchase prices while retaining chosen allocation and amount',()=>{
  const {run,elements}=loadDashboard();
  run('renderHybridPortfolio(); hybridSettings.amount=1000; state.data.acoes[0]["Preço"]=20; renderHybridPortfolio()');
  assert.match(elements['hybridSimulation-acoes_top20'].innerHTML,/7 ações/);
  assert.match(elements.hybridSimulationSummary.innerHTML,/10,00/);
  assert.equal(run('hybridSettings.weights.acoes_top20'),.3);
});

test('fresh load defaults to R$ 10,000 and renders all four purchase lists without expanders',()=>{
  const {run,elements}=loadDashboard();
  run('renderHybridPortfolio()');
  assert.equal(elements.hybridAmount.value,'10.000,00');
  assert.equal(run('hybridSettings.amount'),10000);
  assert.match(elements['hybridSimulation-acoes_top20'].innerHTML,/<b>AAAA3F<\/b>/);
  assert.match(elements['hybridSimulation-acoes_top20'].innerHTML,/<b>BBBB4F<\/b>/);
  assert.match(elements['hybridSimulation-fiis_top20'].innerHTML,/<b>CCCC11<\/b>/);
  assert.match(elements['hybridSimulation-ivvb11'].innerHTML,/<b>IVVB11<\/b>/);
  for(const key of ['acoes_top20','fiis_top20','cdi','ivvb11']){
    const list=elements[`hybridSimulation-${key}`].innerHTML;
    assert.match(list,/<ul><li\b/);
    assert.doesNotMatch(list,/<details|<summary/);
  }
  run('state.data.acoes[0]["Preço"]=15;renderHybridPortfolio()');
  assert.match(elements['hybridSimulation-acoes_top20'].innerHTML,/<b>AAAA3<\/b>/);
  run('hybridSettings.weights={acoes_top20:0,fiis_top20:0,cdi:1,ivvb11:0};renderHybridPortfolio()');
  assert.doesNotMatch(elements['hybridSimulation-acoes_top20'].innerHTML,/<b>AAAA3F<\/b>/);
});

test('unfinished or invalid edits keep the valid 100% allocation and restore the input on blur',()=>{
  const {run,elements,inputs}=loadDashboard();
  run('renderHybridPortfolio()');
  inputs[0].value=''; inputs[0].dispatch('input');
  assert.equal(run('validHybridWeights(hybridSettings.weights)'),true);
  assert.equal(elements.hybridResults.hidden,false);
  assert.equal(inputs[0].attributes['aria-invalid'],'true');
  inputs[0].dispatch('blur');
  assert.equal(inputs[0].value,'30');
  assert.equal(inputs[0].attributes['aria-invalid'],'false');
  inputs[0].value='30.5'; inputs[0].dispatch('input');
  close(run('hybridSettings.weights.acoes_top20'),.3);
  assert.equal(inputs[0].value,'30');
  for(const invalid of ['-1','101','1e1','Infinity']){
    inputs[0].value=invalid; inputs[0].dispatch('input');
    assert.equal(inputs[0].value,'30');
    assert.equal(run('validHybridWeights(hybridSettings.weights)'),true);
  }
  inputs[0].value='31'; inputs[0].dispatch('input');
  close(run('hybridSettings.weights.acoes_top20'),.31);
  assert.equal(inputs[1].value,'29');
});

test('amounts below R$ 1,000 clear purchases and monetary estimates immediately',()=>{
  const data=fixture(); data.carteira_vs={carteira_hibrida:history()};
  const {run,elements}=loadDashboard(data);
  run('renderHybridPortfolio()');
  elements.hybridAmount.edit('999,99');
  assert.equal(elements.hybridAmount.attributes['aria-invalid'],'true');
  assert.match(elements.hybridAmountStatus.textContent,/pelo menos R\$ 1\.000,00/);
  assert.match(elements.hybridCompositionBody.innerHTML,/aporte mínimo/);
  assert.equal(elements.hybridSimulationSummary.innerHTML,'');
  elements.hybridAmount.edit('1.000,00');
  assert.equal(elements.hybridAmount.attributes['aria-invalid'],'false');
  assert.match(elements.hybridCompositionBody.innerHTML,/Saldo teórico/);
});

test('monetary results use historical contributions and update when the investment changes',()=>{
  const data=fixture(); data.carteira_vs={carteira_hibrida:history()};
  const {run,elements}=loadDashboard(data);
  run('renderHybridPortfolio()');
  assert.equal(run('hybridEstimatedCents(-.09,10000)'),-900);
  assert.equal(run('hybridEstimatedCents(3,10000)'),30000);
  assert.equal(run('hybridEstimatedCents(null,10000)'),null);
  assert.match(elements.hybridCompositionBody.innerHTML,/-R\$\s9,00/);
  assert.match(elements.hybridCompositionBody.innerHTML,/Saldo teórico: R\$\s9\.991,00/);
  elements.hybridAmount.edit('20.000,00');
  assert.match(elements.hybridCompositionBody.innerHTML,/-R\$\s18,00/);
  assert.match(elements.hybridCompositionBody.innerHTML,/Saldo teórico: R\$\s19\.982,00/);
  assert.equal((elements.hybridCompositionBody.innerHTML.match(/<td(?:\s|>)/g)||[]).length,25);
});

test('every time-series chart starts at 90D and preserves a later explicit period selection',()=>{
  const {context,run}=loadDashboard();
  context.dates=['2025-01-01','2026-01-01','2026-06-01','2026-08-01','2026-09-01'];
  for(const chartId of ['hybridPortfolioChart','proxyFiisChart','proxyAcoesChart','overviewFiisBacktestChart','overviewAcoesBacktestChart','marketChart','macroChart','mlPerformanceChart']){
    context.chartId=chartId;
    assert.equal(run('filteredLabelsForPeriod(dates,chartId).join(",")'),'2026-08-01,2026-09-01');
    assert.equal(run('state.chartWindows[chartId]'),'90D');
  }
  assert.equal(run('defaultChartPeriod([])'),'90D');
  run('state.chartWindows.hybridPortfolioChart="ALL"');
  assert.equal(run('filteredLabelsForPeriod(dates,"hybridPortfolioChart").length'),5);
});

test('market, macro and ML renderers apply the selected time window and retain matching metadata',()=>{
  const {context,run}=loadDashboard();
  context.series=[{data:'2026-01-01',valor:100},{data:'2026-08-01',valor:120},{data:'2026-09-01',valor:132}];
  context.benchmarkBase100=()=>context.series;
  context.state.data.indicadores={selic:context.series};
  vm.runInContext(between('    function base100ToReturn','    function renderProxyCharts'),context);
  run('renderMarketChart()');
  assert.equal(context.chart.data.labels.join(','),'2026-08-01,2026-09-01');
  close(context.chart.data.datasets[0].data[0],0);
  close(context.chart.data.datasets[0].data[1],10);
  run('renderMacroChart()');
  assert.equal(context.chart.data.labels.join(','),'2026-08-01,2026-09-01');
  assert.equal(context.chart.data.datasets[0].data.join(','),'120,132');
  context.RADAR_FONT_FAMILY='Arial';
  context.fmtDateShort=date=>date;
  context.mlEvolutionData=()=>({
    labels:context.series.map(row=>row.data),
    datasets:[{label:'Ridge',data:[1,2,3],metaRows:context.series.map(row=>({Data_Resultado:row.data}))}],
    metric:{format:value=>String(value),axis:'Retorno'},realized:true
  });
  vm.runInContext(between('    function mlEvolutionStat','    function previousSnapshot'),context);
  run('renderMlPerformanceChart()');
  assert.equal(context.chart.data.labels.join(','),'2026-08-01,2026-09-01');
  assert.equal(context.chart.data.datasets[0].data.join(','),'2,3');
  assert.equal(context.chart.data.datasets[0].metaRows[0].Data_Resultado,'2026-08-01');
  run('state.chartWindows.marketChart="ALL";renderMarketChart()');
  assert.equal(context.chart.data.labels.length,3);
});
