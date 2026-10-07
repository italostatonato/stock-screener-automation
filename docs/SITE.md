# Site no Sites e contador de visitantes

Informações verificadas em **05/10/2026** no site público, na API de versão e nos scripts servidos pela publicação atual.

## Endereços e acesso

- **[Radar Semanal no Sites](https://radar-semanal-italo.italo-st.chatgpt.site/)**: site público com contador de visitantes.
- **[Dashboard no GitHub Pages](https://italostatonato.github.io/stock-screener-automation/)**: publicação original do projeto.
- **[Repositório](https://github.com/italostatonato/stock-screener-automation)** e **[wiki](https://github.com/italostatonato/stock-screener-automation/wiki)**: código do screener e documentação.

O site foi criado em 29/09/2026 como réplica da página publicada no GitHub Pages.
Preserva a identidade visual e as seis abas principais: Introdução, Visão geral, Carteira
Híbrida, Modelos ML, Top 20 e Indicadores e metodologia.
Inclui rankings, gráficos, guia para iniciantes e simulador de aporte.
As premissas de cálculos e simulações estão no
[guia do dashboard](https://github.com/italostatonato/stock-screener-automation/blob/main/docs/DASHBOARD.md).

## Atualização dos dados

A coleta continua no pipeline Python e no GitHub Actions deste repositório:
**segunda-feira às 10h de Brasília** (`America/Sao_Paulo`), ou por execução manual.
O site no Sites não mantém outra rotina de coleta nem recalcula o ranking.

1. A cada acesso, o servidor do Sites busca o HTML, os dados e os recursos na
   origem fixa do GitHub Pages. O navegador recebe os snapshots por `/data/`
   no próprio domínio do Sites, a partir do
   [índice do Pages](https://italostatonato.github.io/stock-screener-automation/data/index.json).
2. O servidor acrescenta as adaptações do Sites, como o contador e os scripts
   de sincronização. O HTML original atualizado no Pages chega à réplica sem
   precisar publicar novamente o projeto do Sites.
3. Enquanto a aba está visível, consulta `/api/source-version` a cada **60 segundos**,
   além da verificação inicial e ao voltar à aba. A versão compara o HTML, o
   índice e o snapshot mais recente, detectando também correções na mesma data.
4. Quando há mudança, recarrega a página. Se um campo estiver em edição, aguarda
   o término. Tenta preservar a aba, as buscas, os períodos, as opções do gráfico
   ML e a simulação válida da carteira durante essa recarga.
5. Se a origem falhar, tenta a cópia incluída na publicação, identifica a
   contingência e preserva a data dos dados. As verificações tentam recuperar a
   fonte quando ela volta a responder.

Os dados não são cotações em tempo real. Verificar a versão a cada minuto não
coleta fontes financeiras, não treina modelos e não recalcula o ranking: a coleta
continua semanal ou manual. A versão não inclui o conteúdo de cada recurso
externo ao HTML; uma alteração isolada nesses arquivos pode exigir recarga manual.

Worker, contador, adaptações próprias e cópia de contingência continuam tendo
código e publicação no Sites. Essa cópia só muda quando seus arquivos são
atualizados e o site é publicado novamente. Ela não é atualizada pela consulta
automática à origem.

## Contador de visitantes únicos

O rodapé exibe **Visitantes únicos** e a data de início da contagem,
**29/09/2026**. O total considera somente este site no domínio
`radar-semanal-italo.italo-st.chatgpt.site`; acessos ao GitHub Pages e visitas
anteriores à instalação do contador não entram nele.

- Cada navegador recebe um identificador aleatório no cookie `radar_visitor`.
- Recarregar ou retornar com o mesmo cookie não aumenta o total.
- O total é compartilhado entre navegadores e salvo no servidor, permanecendo
  entre publicações que preservem o banco do projeto.
- Limpar cookies, usar outro navegador, outro dispositivo ou navegação privada
  pode produzir uma nova contagem. O bloqueio ou a expiração do cookie também
  impede reconhecer corretamente um retorno.
- Trata-se de uma aproximação por navegador, não de pessoas identificadas nem de
  visualizações de página. Acessos de teste ou automatizados também podem contar.
- Se a consulta falhar, aparece **Indisponível**, sem substituir o total por zero.

O cookie dura até um ano e tem a validade renovada no retorno. Usa `HttpOnly`,
`SameSite=Lax` e `Secure` em HTTPS. A tabela do contador armazena apenas o hash
SHA-256 do identificador e a data da primeira visita; não contém nome, e-mail
ou endereço IP. Essa descrição se refere à tabela da aplicação, não aos registros
operacionais da plataforma de hospedagem.

## Implementação e manutenção

A versão no Sites tem código e publicação próprios, mantidos no projeto do Sites.
Um clone deste repositório entrega o pipeline e o dashboard do GitHub Pages;
não inclui automaticamente o Worker, o banco ou os scripts específicos do Sites.

Na publicação do Sites, um Cloudflare Worker atende `/api/visitors` e usa o banco
D1 vinculado como `DB`. A tabela `radar_visitors` tem uma chave única por hash,
para evitar duplicação de um identificador já registrado.

- `GET /api/visitors`: consulta o total e a data inicial sem registrar visita.
- `POST /api/visitors`: registra o identificador se ainda não existir, devolve o
  total e renova o cookie. Exige origem do próprio site e conteúdo JSON.
- A interface registra a visita quando a página está visível. Contador e dados
  financeiros têm fontes independentes.

O Worker também atende `GET /api/source-version`, que devolve o identificador
da versão da origem e a data do snapshot mais recente. Essa consulta não registra
uma visita. A resposta usa `X-Radar-Source: github-pages` quando a origem está
disponível; páginas e dados servidos da cópia de contingência usam `local-copy`.

Para alterar a interface original, atualize o dashboard deste repositório e
publique no GitHub Pages. Para alterar Worker, contador ou adaptações próprias,
abra o projeto existente no Sites, preserve seu banco, valide a mudança e
publique uma nova versão. Publicar `docs/` não publica esse código específico
do Sites, embora o conteúdo original passe a ser consultado pelo espelhamento.
As permissões de acesso são administradas no Sites; o modo público foi confirmado
na data de verificação deste guia.

Se os dados parecerem antigos, confira a data do snapshot, o aviso de cópia
incluída, a [versão da origem](https://radar-semanal-italo.italo-st.chatgpt.site/api/source-version)
e a conclusão do workflow original. Uma aba oculta ou um campo ainda em edição
pode adiar a recarga automática. Se o contador estiver indisponível, consulte
os logs do Worker e a disponibilidade da tabela e do vínculo `DB`.
Para conferir o total sem gerar uma visita de teste, use
[a consulta do contador](https://radar-semanal-italo.italo-st.chatgpt.site/api/visitors).

O projeto tem finalidade educacional e analítica. O simulador não executa compras,
e os resultados não constituem recomendação de investimento.
