# Redesenho Radar Semanal

Fonte integral: apresentação nativa, 10 slides inspecionados, PDF e JSON arquivados. Edição no próprio documento autorizada expressamente. Layout p12 sem placeholders. Reconstruir os objetos locais porque a composição visual original foi rejeitada pelo usuário; manter IDs de slides, 16:9 (960 x 540 pt), Proxima Nova e identidade cromática. Proxima Nova confirmada no PDF como fonte incorporada Regular e Bold.

1. p1: abertura tipográfica, promessa do produto. Fonte p1; remover captura antiga com rentabilidade.
2. p2: problema e seleção, contraste de escala 1.505 / 40. Fonte p2 e snapshot 02/09/2026.
3. p3: fluxo de dados e score em quatro etapas. Fontes p3/p4, scorer.py, filters.py. Diagrama nativo editável, sem lista de 14 métricas.
4. p4: exploração do site. Fonte p5, substituir captura antiga por recorte real do resumo do ranking, somente preço e score; quatro primeiras linhas identificadas como recorte. Sem distorção.
5. p5: carteira híbrida R$ 10.000. Fonte p6; gráfico de área proporcional nativo 30/30/20/20, funções e regra Top 20.
6. p6: R$ 3.000 em ações. Fonte p7, quatro primeiras ações do snapshot com nomes e códigos, tabela nativa de R$ 750 cada. Explicitar redução ilustrativa do Top 20.
7. p7: R$ 2.000 de renda fixa. Fonte p7; R$ 800 Tesouro Selic, R$ 700 CDB, R$ 500 LCI ou LCA. Sem taxas inventadas. CDI/Taxa DI e Selic distintos. Fontes oficiais nas notas.
8. p8: rastreabilidade e limites. Fonte p8 e repositório, registros públicos, histórico de composições e ML em observação.
9. p9: encerramento, autoria e acesso ao site. Fonte p9; preservar link de acesso e usar foto original do repositório sem distorção.
10. p10: guia visual atualizado, manter oculto. Fonte p10.

Tempo alvo 5 minutos: 20 + 25 + 40 + 35 + 35 + 35 + 50 + 25 + 20 segundos.

Permissões originais: anyone/reader, allowFileDiscovery=false e proprietário original. Não alterar compartilhamento.

Exportação: helper de fetch do skill utilizado. O helper completo depende de caminhos POSIX/Perl. Neste Windows, manter fluxo equivalente: resposta integral em arquivo, parser do skill, exportação via connector, decodificação local e Poppler; referência sediment sem workspace_path exige fallback base64 limitado (<10MB).
