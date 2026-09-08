import fs from 'node:fs';
const root=new URL('./',import.meta.url);
const raw=JSON.parse(fs.readFileSync(new URL('raw-template.json',root),'utf8'));
const source=raw.structuredContent.result||raw.structuredContent;
const C={bg:'070A12',navy:'111A2D',white:'F5F7FB',muted:'9CA9BF',line:'2C3952',gold:'E3BE72'};
const rgb=h=>({red:parseInt(h.slice(0,2),16)/255,green:parseInt(h.slice(2,4),16)/255,blue:parseInt(h.slice(4,6),16)/255});
const pt=magnitude=>({magnitude,unit:'PT'}),all={type:'ALL'},q=[];
const execId='rs26_exec_summary',sourceExec=source.slides.find(s=>s.objectId==='p8');
const maps=Object.fromEntries(sourceExec.pageElements.map((e,i)=>[e.objectId,`rs26_exec_element_${i}`]));maps.p8=execId;
q.push({duplicateObject:{objectId:'p8',objectIds:maps}});
const m=n=>maps[`rs26_p8_${n}`];
const replace=(objectId,text)=>q.push({deleteText:{objectId,textRange:all}},{insertText:{objectId,text,insertionIndex:0}});
const style=(objectId,size,color,bold=false)=>q.push({updateTextStyle:{objectId,textRange:all,style:{fontFamily:'Proxima Nova',fontSize:pt(size),bold,foregroundColor:{opaqueColor:{rgbColor:rgb(color)}}},fields:'fontFamily,fontSize,bold,foregroundColor'}});
function move(objectId,x,y){q.push({updatePageElementTransform:{objectId,applyMode:'ABSOLUTE',transform:{scaleX:1,scaleY:1,translateX:x,translateY:y,unit:'PT'}}});}
function reshape(objectId,x,y,w,h){const e=sourceExec.pageElements.find(e=>maps[e.objectId]===objectId)||source.slides.flatMap(s=>s.pageElements).find(e=>e.objectId===objectId);let uw=e.size.width,uh=e.size.height;let sx=w/(uw.magnitude/(uw.unit==='EMU'?12700:1)),sy=h/(uh.magnitude/(uh.unit==='EMU'?12700:1));q.push({updatePageElementTransform:{objectId,applyMode:'ABSOLUTE',transform:{scaleX:sx,scaleY:sy,translateX:x,translateY:y,unit:'PT'}}});}
// Native text retains the source box size; the explicit transforms below adjust only its position.
function edit(objectId,t,x,y,size,color,bold=false){replace(objectId,t);move(objectId,x,y);style(objectId,size,color,bold);}
function addText(objectId,page,t,x,y,w,h,size,color,bold=false,link=null){q.push({createShape:{objectId,shapeType:'TEXT_BOX',elementProperties:{pageObjectId:page,size:{width:pt(w),height:pt(h)},transform:{scaleX:1,scaleY:1,translateX:x,translateY:y,unit:'PT'}}}},{insertText:{objectId,text:t,insertionIndex:0}},{updateShapeProperties:{objectId,shapeProperties:{shapeBackgroundFill:{propertyState:'NOT_RENDERED'},outline:{propertyState:'NOT_RENDERED'},contentAlignment:'TOP',autofit:{autofitType:'NONE'}},fields:'shapeBackgroundFill,outline,contentAlignment,autofit.autofitType'}},{updateTextStyle:{objectId,textRange:all,style:{fontFamily:'Proxima Nova',fontSize:pt(size),bold,foregroundColor:{opaqueColor:{rgbColor:rgb(color)}},...(link?{link:{url:link},underline:true}:{})},fields:'fontFamily,fontSize,bold,foregroundColor'+(link?',link,underline':'')}},{updateParagraphStyle:{objectId,textRange:all,style:{lineSpacing:105,spaceAbove:pt(0),spaceBelow:pt(0)},fields:'lineSpacing,spaceAbove,spaceBelow'}});}
function line(objectId,page,x,y,w){q.push({createShape:{objectId,shapeType:'RECTANGLE',elementProperties:{pageObjectId:page,size:{width:pt(w),height:pt(.7)},transform:{scaleX:1,scaleY:1,translateX:x,translateY:y,unit:'PT'}}}},{updateShapeProperties:{objectId,shapeProperties:{shapeBackgroundFill:{solidFill:{color:{rgbColor:rgb(C.line)},alpha:1}},outline:{propertyState:'NOT_RENDERED'}},fields:'shapeBackgroundFill,outline'}});}
q.push({deleteObject:{objectId:m('text_1')}});
replace(m('text_2'),'02');replace(m('text_4'),'RESUMO EXECUTIVO');
edit(m('text_5'),'Radar Semanal\nem uma página',48,104,43,C.white,true);
edit(m('text_6'),'Dados públicos organizados\npara priorizar o estudo\nde ações e FIIs.',49,241,22,C.muted);
edit(m('text_7'),'O problema',535,60,22,C.gold,true);
edit(m('text_8'),'Muitos ativos e indicadores dispersos.\nO Radar reduz o esforço de triagem.',535,101,18,C.white);
move(m('rect_9'),539,182);
edit(m('text_10'),'O método',535,196,22,C.gold,true);
edit(m('text_11'),'Fontes públicas, score de 0 a 100\ne filtros. Seleção atualizada toda semana.',535,237,18,C.white);
move(m('rect_12'),539,318);
edit(m('text_13'),'O site',535,332,22,C.gold,true);
// The old last body had one short line; replace it with a native box sized for executive copy.
q.push({deleteObject:{objectId:m('text_14')}});
addText('rs26_exec_site',execId,'Ranking, indicadores, recorrência\ne fontes para aprofundar a análise.',535,372,363,62,18,C.white);
line('rs26_exec_line3',execId,539,449,365);
addText('rs26_exec_portfolio_title',execId,'Carteira configurável',535,462,363,34,22,C.gold,true);
addText('rs26_exec_portfolio_body',execId,'5 presets, valor e percentuais ajustáveis.',535,500,363,27,17,C.white);
addText('rs26_exec_metric',execId,'20 + 20',48,345,410,83,60,C.gold,true);
addText('rs26_exec_metric_label',execId,'ações brasileiras e FIIs',49,424,380,31,18,C.white);
addText('rs26_exec_cta',execId,'Explorar o Radar Semanal',49,469,390,33,19,C.gold,true,'https://italostatonato.github.io/stock-screener-automation/');
addText('rs26_exec_education',execId,'Educacional. Sem recomendação de investimento.',49,509,414,22,10.5,C.muted);

// Update the allocation slide without replacing its native 30/30/20/20 evidence.
replace('rs26_p5_title_3','Uma carteira com valor\ne distribuição ajustáveis');
addText('rs26_p5_preset_example','p5','EXEMPLO BALANCEADO: R$ 10.000',49,172,508,24,12,C.gold,true);
edit('rs26_p5_text_20','Presets',599,190,22,C.gold,true);
// Remove the one-line source box because the five preset names need three lines.
q.push({deleteObject:{objectId:'rs26_p5_text_21'}});
addText('rs26_p5_presets','p5','Agressivo, Meio-Agressivo,\nBalanceado, Conservador e\nMuito conservador.',599,225,313,76,18,C.muted);
edit('rs26_p5_text_22','Valor investido',599,310,22,C.gold,true);
edit('rs26_p5_text_23','Informe quanto quer simular.',599,346,18,C.white);
edit('rs26_p5_text_24','Pesos ajustáveis',599,397,22,C.gold,true);
addText('rs26_p5_weights','p5','Ajustes de 1% em 1%.\nO total permanece em 100%.',599,435,313,50,18,C.white);
replace('rs26_p5_text_26','Exemplo educacional do preset Balanceado. O simulador calcula unidades inteiras e separa o saldo.');
replace('rs26_p6_text_1','EXEMPLO BALANCEADO: AÇÕES');
replace('rs26_p7_text_1','EXEMPLO BALANCEADO: RENDA FIXA');
for(let n=2;n<=10;n++)replace(`rs26_p${n}_text_2`,String(n+1).padStart(2,'0'));
const notes=source.slides.find(s=>s.objectId==='p5').slideProperties.notesPage.notesProperties.speakerNotesObjectId;
replace(notes,'Carteira híbrida configurável. A interface permite escolher um dos cinco presets, informar o valor do aporte e mudar percentuais em passos de 1%. O ajuste dos demais blocos mantém o total em 100%.\nPresets na ordem ações / FIIs / CDI / IVVB11: Agressivo 45/20/5/30; Meio-Agressivo 40/25/10/25; Balanceado 30/30/20/20; Conservador 15/20/55/10; Muito conservador 5/10/80/5. São configurações do produto, não uma avaliação de adequação ao perfil do investidor.\nEste slide mantém o exemplo Balanceado de R$ 10.000: R$ 3.000 em ações, R$ 3.000 em FIIs, R$ 2.000 em renda fixa e R$ 2.000 em IVVB11. A alocação não é fixa para todos os usuários. Dentro de cada Top 20, o alvo se divide igualmente pelos ativos. O simulador usa unidades inteiras de ações e cotas, arredonda para baixo e mantém o saldo separado, sem redistribuição automática. CDI é um valor destinado à renda fixa. Não considera custos, impostos ou mínimos dos produtos. O campo de aporte aceita valores a partir de R$ 1.000. Os valores e percentuais recalculam a simulação no site.\nFonte: docs/index.html, HYBRID_PRESETS, rebalanceHybridWeights e buildHybridSimulation, versão conferida em 06/09/2026. https://italostatonato.github.io/stock-screener-automation/\nIVVB11: https://www.blackrock.com/br/products/251902/ishares-sp-500-fi-em-cotas-de-fundo-de-ndice-inv-no-exterior-fund\nConteúdo educacional. Diversificação não elimina riscos.');
fs.writeFileSync(new URL('requests.json',root),JSON.stringify(q));
console.log(q.length);
