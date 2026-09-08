import fs from 'node:fs';
const root = new URL('./', import.meta.url);
const raw = JSON.parse(fs.readFileSync(new URL('raw-template.json',root),'utf8'));
const source = raw.structuredContent.result || raw.structuredContent;
const C={bg:'070A12',navy:'111A2D',deep:'0B1020',white:'F5F7FB',muted:'9CA9BF',line:'2C3952',gold:'E3BE72',blue:'54C7FF',purple:'A78BFA',slate:'B6C0D2'};
const RGB=h=>({red:parseInt(h.slice(0,2),16)/255,green:parseInt(h.slice(2,4),16)/255,blue:parseInt(h.slice(4,6),16)/255});
const pt=n=>({magnitude:n,unit:'PT'}), all={type:'ALL'};
const site='https://italostatonato.github.io/stock-screener-automation/';
const repo='https://github.com/italostatonato/stock-screener-automation';
let q=[],sid='',seq=0;
const batches=[];
function id(label='obj'){return `rs26_${sid}_${label}_${++seq}`;}
function props(x,y,w,h){return {pageObjectId:sid,size:{width:pt(w),height:pt(h)},transform:{scaleX:1,scaleY:1,translateX:x,translateY:y,unit:'PT'}};}
function rect(x,y,w,h,color){let o=id('rect');q.push({createShape:{objectId:o,shapeType:'RECTANGLE',elementProperties:props(x,y,w,h)}},{updateShapeProperties:{objectId:o,shapeProperties:{shapeBackgroundFill:{solidFill:{color:{rgbColor:RGB(color)},alpha:1}},outline:{propertyState:'NOT_RENDERED'}},fields:'shapeBackgroundFill,outline'}});return o;}
function text(t,x,y,w,h,size=22,color=C.white,bold=false,options={}){let o=id(options.label||'text');q.push({createShape:{objectId:o,shapeType:'TEXT_BOX',elementProperties:props(x,y,w,h)}},{insertText:{objectId:o,text:t,insertionIndex:0}},{updateShapeProperties:{objectId:o,shapeProperties:{shapeBackgroundFill:{propertyState:'NOT_RENDERED'},outline:{propertyState:'NOT_RENDERED'},contentAlignment:'TOP',autofit:{autofitType:'NONE'}},fields:'shapeBackgroundFill,outline,contentAlignment,autofit.autofitType'}},{updateTextStyle:{objectId:o,textRange:all,style:{fontFamily:'Proxima Nova',fontSize:pt(size),bold,foregroundColor:{opaqueColor:{rgbColor:RGB(color)}},...(options.link?{link:{url:options.link},underline:true}:{})},fields:'fontFamily,fontSize,bold,foregroundColor'+(options.link?',link,underline':'')}},{updateParagraphStyle:{objectId:o,textRange:all,style:{lineSpacing:105,spaceAbove:pt(0),spaceBelow:pt(0),alignment:options.align||'START'},fields:'lineSpacing,spaceAbove,spaceBelow,alignment'}});return o;}
function begin(n,section){sid=`p${n}`;q=[];seq=0;for(const e of source.slides.find(s=>s.objectId===sid).pageElements||[])q.push({deleteObject:{objectId:e.objectId}});q.push({updatePageProperties:{objectId:sid,pageProperties:{pageBackgroundFill:{solidFill:{color:{rgbColor:RGB(C.bg)},alpha:1}}},fields:'pageBackgroundFill'}},{updateSlideProperties:{objectId:sid,slideProperties:{isSkipped:n===10},fields:'isSkipped'}});if(n!==1){text(section.toUpperCase(),48,27,760,23,11,C.gold,true);text(String(n).padStart(2,'0'),865,27,47,23,11,C.muted,false,{align:'END'});} }
function foot(t){rect(52,489,856,0.7,C.line);text(t,48,499,812,24,10.5,C.muted);}
function title(t){text(t,48,67,864,106,41,C.white,true,{label:'title'});}
function note(t){const n=source.slides.find(s=>s.objectId===sid).slideProperties.notesPage.notesProperties.speakerNotesObjectId;q.push({deleteText:{objectId:n,textRange:all}},{insertText:{objectId:n,text:t,insertionIndex:0}});}
function end(){batches.push({slide:sid,requests:q});}
function photo(url,x,y,w,h){let o=id('image');q.push({createImage:{objectId:o,url,elementProperties:props(x,y,w,h)}});return o;}
function table(rows,x,y,widths,rowheights,accent=C.white,font=22){let o=id('table');q.push({createTable:{objectId:o,rows:rows.length,columns:widths.length,elementProperties:props(x,y,widths.reduce((a,b)=>a+b,0),rowheights.reduce((a,b)=>a+b,0))}},{updateTableCellProperties:{objectId:o,tableCellProperties:{tableCellBackgroundFill:{solidFill:{color:{rgbColor:RGB(C.bg)},alpha:1}},contentAlignment:'MIDDLE'},fields:'tableCellBackgroundFill,contentAlignment'}},{updateTableBorderProperties:{objectId:o,borderPosition:'ALL',tableBorderProperties:{tableBorderFill:{solidFill:{color:{rgbColor:RGB(C.bg)},alpha:0}},weight:pt(0.5)},fields:'tableBorderFill,weight'}},{updateTableBorderProperties:{objectId:o,borderPosition:'INNER_HORIZONTAL',tableBorderProperties:{tableBorderFill:{solidFill:{color:{rgbColor:RGB(C.line)},alpha:1}},weight:pt(0.6)},fields:'tableBorderFill,weight'}});
 widths.forEach((w,c)=>q.push({updateTableColumnProperties:{objectId:o,columnIndices:[c],tableColumnProperties:{columnWidth:pt(w)},fields:'columnWidth'}}));rowheights.forEach((h,r)=>q.push({updateTableRowProperties:{objectId:o,rowIndices:[r],tableRowProperties:{minRowHeight:pt(h)},fields:'minRowHeight'}}));
 rows.forEach((row,r)=>row.forEach((t,c)=>{if(!t)return;const loc={rowIndex:r,columnIndex:c};q.push({insertText:{objectId:o,cellLocation:loc,text:t,insertionIndex:0}},{updateTextStyle:{objectId:o,cellLocation:loc,textRange:all,style:{fontFamily:'Proxima Nova',fontSize:pt(r===0?11:font),bold:r===0||c===widths.length-1,foregroundColor:{opaqueColor:{rgbColor:RGB(r===0?C.muted:c===widths.length-1?accent:C.white)}}},fields:'fontFamily,fontSize,bold,foregroundColor'}},{updateParagraphStyle:{objectId:o,cellLocation:loc,textRange:all,style:{alignment:c===widths.length-1?'END':'START',spaceAbove:pt(0),spaceBelow:pt(0),lineSpacing:105},fields:'alignment,spaceAbove,spaceBelow,lineSpacing'}});if(t.includes('\n')&&r>0){let start=t.indexOf('\n')+1;q.push({updateTextStyle:{objectId:o,cellLocation:loc,textRange:{type:'FIXED_RANGE',startIndex:start,endIndex:t.length},style:{fontSize:pt(15),foregroundColor:{opaqueColor:{rgbColor:RGB(C.muted)}},bold:false},fields:'fontSize,foregroundColor,bold'}})}}));return o;}

begin(1,'');
rect(656,0,304,540,C.navy);
text('BOLETIM QUANTITATIVO',48,40,568,28,12,C.gold,true);
text('Radar',44,118,605,106,90,C.white,true);
text('Semanal',44,203,605,115,90,C.gold,true);
text('Uma seleção organizada de\nações e FIIs para começar sua análise.',49,348,590,75,25,C.white);
text('20',696,101,210,95,78,C.blue,true);
text('AÇÕES BRASILEIRAS',700,194,211,29,14,C.blue,true);
rect(704,254,199,0.8,C.line);
text('20',696,282,210,95,78,C.purple,true);
text('FUNDOS IMOBILIÁRIOS',700,377,224,29,14,C.purple,true);
text('Ítalo Petricioni Statonato',49,478,565,26,17,C.white,true);
text('DADOS PÚBLICOS\nATUALIZAÇÃO SEMANAL',700,472,225,44,11,C.muted);
note('Abertura (20s). O Radar Semanal é um projeto de dados e automação que organiza ações e fundos imobiliários em uma lista para estudo. A proposta é reduzir o esforço de triagem inicial. Não há recomendação de compra.\nFonte: README.md e apresentação original p1. '+site);
end();

begin(2,'O problema');title('O Radar organiza por onde\ncomeçar a análise');
text('1.505',44,189,475,125,100,C.white,true);
text('ativos no universo coletado',49,320,443,38,23,C.white);
text('956 ações brasileiras\n549 fundos imobiliários',49,363,430,74,21,C.muted);
rect(492,207,1,217,C.line);
text('40',550,170,355,149,125,C.gold,true);
text('ativos em destaque',563,320,335,38,23,C.white);
text('Top 20 Ações + Top 20 FIIs',563,365,352,38,20,C.muted);
foot('Universo e rankings de 02/09/2026. A seleção define uma prioridade de estudo.');
note('Problema (25s). Com tantos papéis, comparar preços e indicadores manualmente consome tempo. No retrato de 02/09/2026, o projeto coletou 956 ações e 549 FIIs, totalizando 1.505 ativos. A publicação destacou 20 de cada classe. Esses números refletem o universo coletado nessa data, não todo o mercado de forma permanente.\nFonte: docs/data/2026-09-02.json, kpis.total_acoes_universo=956, kpis.total_fiis_universo=549, resumo.total_acoes=20, resumo.total_fiis=20.');end();

begin(3,'O método');title('Dados públicos passam pelo\nmesmo método toda semana');
const steps=[['01','Coleta','Ações: Fundamentus.\nFIIs: Fundsexplorer.'],['02','Padronização','Preços e percentuais\nem formato comparável.'],['03','Score e filtros','Nota de 0 a 100 e\ncritérios mínimos.'],['04','Publicação','Top 20 de cada classe\nno painel e no histórico.']];
rect(53,223,854,1,C.line);
steps.forEach((s,i)=>{let x=48+i*219;text(s[0],x,187,80,33,18,C.gold,true);rect(x+4,221,35,4,C.gold);text(s[1],x,243,215,38,24,C.white,true);text(s[2],x,289,212,75,18.5,C.muted);});
rect(0,386,960,97,C.navy);
text('7',48,388,85,77,60,C.gold,true);text('indicadores com pesos iguais\npor classe de ativo',134,409,386,57,21,C.white);
text('0–100',601,398,268,57,42,C.gold,true);text('posição relativa no universo',601,450,310,26,14,C.muted);
foot('O score compara indicadores. Ele não representa uma previsão de retorno.');
note('Método (40s). A rotina coleta fontes públicas, limpa formatos, calcula o score no universo completo da classe, aplica pisos de elegibilidade e publica a seleção. Cada classe possui sete fatores de peso 1/7. As ações usam dividend yield, preço/VPA, EV/EBITDA, margem líquida, ROInvC, RPL e volume diário médio. Nos FIIs, entram renda, preço/patrimônio, liquidez, patrimônio, desempenho no período e taxas. Fatores são transformados em percentis relativos ao universo de cada classe. Campos ausentes recebem nota neutra 50; isso é uma limitação. Menor preço relativo ou custo pontua em direção inversa.\nFontes: src/scorer.py, src/filters.py, config.yaml, README.md.');end();

begin(4,'O produto');title('O ranking ganha contexto no site');
photo('C:/Users/Ítalo/OneDrive/stock-screener-automation/apresentacao/redesign-2026-09-06/product-ranking.png',49,137,535,535*380/596);
text('Ações e FIIs',648,181,264,35,23,C.white,true);text('Busque um ativo e compare\npreço, score e indicadores.',648,222,264,66,19,C.muted);
text('Recorrentes',648,302,264,33,23,C.white,true);text('Veja quem aparece com\nfrequência nas seleções.',648,342,264,61,19,C.muted);
text('Score e Info',648,418,264,31,23,C.white,true);text('Confira método e fontes.',648,454,264,28,18,C.muted);
foot('Recorte do painel de 02/09/2026: quatro primeiras posições. Site completo no link final.');
note('Demonstração do produto (35s). O recorte mostra a comparação entre ações e FIIs por posição, com preço e score. Ações e FIIs têm telas de busca e indicadores. Recorrentes organiza frequência de presença nas composições. Indicadores traz contexto macroeconômico. Carteira Híbrida explica alocação, e Score e Info descreve método e fontes. Modelos ML ficam em observação, sem substituir o ranking oficial.\nImagem: captura do próprio site, resumo do ranking, base de 02/09/2026; só quatro posições aparecem neste recorte. '+site);end();

begin(5,'A carteira híbrida');title('R$ 10.000 distribuídos\nem quatro funções');
const bx=53,by=196,bw=500,bh=260;
rect(bx,by,bw/2,bh*.6,C.blue);rect(bx+bw/2,by,bw/2,bh*.6,C.purple);rect(bx,by+bh*.6,bw/2,bh*.4,C.gold);rect(bx+bw/2,by+bh*.6,bw/2,bh*.4,C.slate);
rect(bx+bw/2-1,by,2,bh,C.bg);rect(bx,by+bh*.6-1,bw,2,C.bg);
text('30%',66,204,216,61,45,C.bg,true);text('Ações brasileiras',66,268,230,31,21,C.bg,true);text('R$ 3.000',66,305,214,34,24,C.bg);
text('30%',316,204,216,61,45,C.bg,true);text('FIIs',316,268,220,31,21,C.bg,true);text('R$ 3.000',316,305,214,34,24,C.bg);
text('20%   Renda fixa',66,363,228,34,21,C.bg,true);text('R$ 2.000',66,407,218,34,24,C.bg);
text('20%   IVVB11',316,363,224,34,21,C.bg,true);text('R$ 2.000',316,407,218,34,24,C.bg);
text('Crescimento no Brasil',599,190,313,32,21,C.blue,true);text('Renda e exposição imobiliária',599,234,315,32,21,C.purple,true);text('Menor oscilação no conjunto',599,278,315,32,21,C.gold,true);text('Empresas dos EUA e câmbio',599,322,315,32,21,C.slate,true);
text('Cada Top 20 divide seu bloco\nem 20 partes: R$ 150 por ativo.\nRebalanceamento semanal.',599,387,312,88,17,C.muted);
foot('Alocação educacional. O modelo usa CDI como referência da renda fixa. Diversificação não elimina riscos.');
note('Carteira híbrida (35s). A regra combina 30% Top 20 ações, 30% Top 20 FIIs, 20% CDI e 20% IVVB11. Com R$ 10.000, são R$ 3.000 + R$ 3.000 + R$ 2.000 + R$ 2.000 = R$ 10.000. No modelo, a parcela de ações e a de FIIs dividem-se igualmente entre 20 ativos, equivalendo a R$ 150 por papel e 1,5% do total. O projeto rebalanceia a cada nova composição. O CDI é a referência teórica da parcela de renda fixa; os instrumentos reais do slide seguinte são exemplos educacionais. Os valores são alvos de alocação e não ordens executadas: quantidades inteiras, preços, custos e mínimos podem exigir ajustes. IVVB11 busca acompanhar o S&P 500 em reais, sujeitando-se às ações dos EUA e à variação cambial.\nFontes: README.md, docs/index.html seção hibrida, src/benchmark.py. IVVB11: https://www.blackrock.com/br/products/251902/ishares-sp-500-fi-em-cotas-de-fundo-de-ndice-inv-no-exterior-fund');end();

begin(6,'Exemplo de aplicação');title('R$ 3.000 em ações,\ncom nomes e valores');
text('R$ 750',45,210,264,77,57,C.blue,true);text('por empresa\nnesta ilustração',49,296,247,76,23,C.white);
text('4 empresas do ranking\nde 02/09/2026',49,397,247,63,18,C.muted);
table([['EMPRESA','CÓDIGO','ALOCAÇÃO'],['Petrobras','PETR4','R$ 750'],['Wiz Co','WIZC3','R$ 750'],['Guararapes','RIAA3','R$ 750'],['JHSF','JHSF3','R$ 750'],['Total em ações','','R$ 3.000']],326,187,[290,128,158],[31,48,48,48,48,54],C.blue,22);
foot('Ilustração reduzida a 4 empresas. A estratégia integral usa 20 ações. Valores de alocação, sem simular ordens.');
note('Ações do exemplo (35s). Mantivemos as quatro primeiras posições da base de 02/09/2026: PETR4, PETROLEO BRASILEIRO S.A. PETROBRAS; WIZC3, WIZ CO PARTICIPAÇÕES E CORRETAGEM DE SEGUROS S.A.; RIAA3, Guararapes Confecções S.A.; JHSF3, JHSF PARTICIPACOES S.A. Destinamos R$ 750 para cada uma: 4 x 750 = 3.000. Esta simplificação ilustra a divisão de capital; não reproduz a estratégia integral nem seus pesos de 20 ações. São valores destinados a cada ativo, sem arredondamento de quantidade de ações, custos ou execução.\nFonte: docs/data/2026-09-02.json, acoes[0:4], e data/lake/snapshots/2026-09-02/top_acoes.parquet. Não é recomendação de investimento.');end();

begin(7,'Renda fixa na prática');title('Os R$ 2.000 podem combinar\nprodutos com regras diferentes');
table([['EXEMPLO EDUCACIONAL','ALOCAÇÃO'],['Tesouro Selic\nTítulo público ligado à Selic','R$ 800'],['CDB\nTítulo bancário, pode seguir o CDI','R$ 700'],['LCI ou LCA\nCrédito imobiliário ou do agro','R$ 500'],['Total em renda fixa','R$ 2.000']],50,183,[330,136],[30,67,67,67,44],C.gold,21);
text('CDI / taxa DI',542,189,366,38,26,C.gold,true);text('Referência calculada pela B3\na partir de operações de um dia\nentre instituições financeiras.',542,233,366,84,19,C.white);
rect(546,332,362,0.7,C.line);text('Selic',542,345,366,38,26,C.white,true);text('Taxa básica da economia.\nO Copom define sua meta.\nO Tesouro Selic acompanha a Selic.',542,389,368,87,19,C.muted);
foot('Valores hipotéticos, sem oferta ou taxa contratada. Liquidez, prazo, risco e condições variam por produto.');
note('Renda fixa (50s). O exemplo soma R$ 800 em Tesouro Selic, R$ 700 em CDB e R$ 500 em uma LCI ou LCA, totalizando R$ 2.000. Não estamos afirmando disponibilidade de ofertas, taxas, mínimos de aplicação ou liquidez diária para todos os produtos. CDI é o nome usual da referência Taxa DI, calculada pela B3 com operações interfinanceiras de um dia, conforme metodologia oficial. A Selic é a taxa básica; o Copom fixa a meta e o Banco Central atua para manter a taxa efetiva em linha com ela. Embora próximas, são referências distintas. Tesouro Selic é vinculado à Selic. CDB e LCI/LCA podem ter remunerações diferentes, inclusive percentuais da taxa DI conforme o contrato. Antes de aplicar, conferir emissor, prazos, liquidez, custos, tributação e condições específicas. Não há promessa de proteção integral ou ausência de risco.\nFontes oficiais: https://www.bcb.gov.br/controleinflacao/taxaselic ; https://www.b3.com.br/pt_br/market-data-e-indices/indices/indices-de-segmentos-e-setoriais/di/metodologia-de-apuracao-da-taxa/ ; https://www.b3.com.br/pt_br/produtos-e-servicos/central-depositaria/renda-fixa-e-valores-mobiliarios/certificado-de-deposito-bancario.htm ; https://borainvestir.b3.com.br/tipos-de-investimentos/lc-lca-e-lci-o-que-sao-e-como-funcionam-as-letras-de-renda-fixa/ ; https://www.tesourodireto.com.br/produtos/titulos/selic');end();

begin(8,'Transparência');
rect(0,0,484,540,C.navy);text('TRANSPARÊNCIA',48,27,403,23,11,C.gold,true);
text('O caminho\ndo dado fica\naberto à consulta',48,141,411,200,43,C.white,true);
text('Fontes públicas e código aberto\npermitem examinar o processo.',49,365,382,76,23,C.muted);
text('Origem dos dados',535,129,363,39,25,C.gold,true);text('As fontes ficam identificadas\nna página Score e Info.',535,176,363,62,20,C.white);
rect(539,256,365,0.7,C.line);
text('Composições registradas',535,274,363,39,25,C.gold,true);text('Cada execução preserva a seleção\ne a data dos dados utilizados.',535,321,363,62,20,C.white);
rect(539,401,365,0.7,C.line);
text('Limites explícitos',535,418,363,39,25,C.gold,true);text('Modelos preditivos em observação.',535,462,363,35,19,C.muted);
note('Transparência (25s). O usuário consegue conferir fontes e critérios em Score e Info, consultar o código público e recuperar as composições que o projeto registrou. Os snapshots mantêm a data de referência. Verificações automatizadas buscam inconsistências, mas dados públicos podem apresentar falhas, atrasos e ausências. Os modelos preditivos operam em modo sombra e não substituem o score oficial.\nFontes: README.md, docs/ARCHITECTURE.md, docs/ML_PIPELINE.md, data/lake/manifest.json. '+repo);end();

begin(9,'Conheça o Radar');
text('O próximo ativo a estudar\npode estar no Radar',48,91,844,132,45,C.white,true);
text('Abra o ranking, compare os indicadores\ne aprofunde a análise.',49,253,589,85,25,C.muted);
text('Explorar o Radar Semanal',49,369,590,44,29,C.gold,true,{link:site,label:'cta'});
text('italostatonato.github.io/stock-screener-automation',49,422,616,27,15,C.muted,false,{link:site});
photo('https://italostatonato.github.io/stock-screener-automation/assets/italo-profile.png',733,250,155,155*353/294);
rect(52,470,856,0.7,C.line);
text('Ítalo Petricioni Statonato',49,486,518,32,21,C.white,true,{link:'https://www.linkedin.com/in/italo-petricioni-statonato/'});
text('Conteúdo educacional.\nNão é recomendação de investimento.',600,485,311,41,12,C.muted,false,{align:'END'});
note('Encerramento (20s). Convidar a pessoa a abrir o Radar pelo link, buscar um ativo conhecido, verificar os indicadores e aprofundar a análise. A decisão depende de objetivos, riscos e perfil. Projeto de Ítalo Petricioni Statonato, profissional de dados, analytics e estratégia.\nSite: '+site+'\nFoto: docs/assets/italo-profile.png, imagem original do projeto.\nPerfil: https://www.linkedin.com/in/italo-petricioni-statonato/');end();

begin(10,'Apêndice oculto');title('Guia visual do Radar Semanal');
text('Paleta',48,167,382,40,26,C.white,true);
const colors=[['Fundo',C.bg],['Superfície',C.navy],['Destaque',C.gold],['Ações',C.blue],['FIIs',C.purple],['Internacional',C.slate]];
colors.forEach((a,i)=>{let x=52+(i%3)*143,y=223+Math.floor(i/3)*104;rect(x,y,120,38,a[1]);text(a[0],x-4,y+43,133,29,16,C.white,true);text('#'+a[1],x-4,y+70,133,23,11,C.muted);});
text('Proxima Nova',537,167,368,50,35,C.white,true);text('Bold para títulos. Regular para texto.\nTítulos de 41–45 pt e corpo de 18–25 pt.\nAbertura com escala tipográfica maior.',538,229,368,98,20,C.muted);
text('Composição',537,350,368,40,26,C.white,true);text('16:9. Margens de 52 pt.\nLinhas finas e superfícies azul-marinho.\nCores secundárias identificam as classes.\nTexto e dados permanecem editáveis.',538,398,368,94,18,C.muted);
note('Guia visual interno. Manter este slide oculto na apresentação. Proxima Nova Regular e Bold. Base #070A12, superfície #111A2D, destaque #E3BE72, ações #54C7FF, FIIs #A78BFA. As áreas no gráfico de alocação são proporcionais ao capital.');end();

fs.writeFileSync(new URL('batches.json',root),JSON.stringify(batches));
fs.writeFileSync(new URL('slide-copy.json',root),JSON.stringify(batches.map(b=>({slide:b.slide,text:b.requests.filter(r=>r.insertText).map(r=>r.insertText.text)})),null,2));
console.log(JSON.stringify(batches.map(b=>({slide:b.slide,requests:b.requests.length}))));
