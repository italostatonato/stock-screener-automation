# Site no Sites e contador de visitantes

Informações verificadas em **30/09/2026** na versão 2 publicada no Sites.

## Endereços e acesso

- **[Radar Semanal no Sites](https://radar-semanal-italo.italo-st.chatgpt.site/)**: site público com contador de visitantes.
- **[Dashboard no GitHub Pages](https://italostatonato.github.io/stock-screener-automation/)**: publicação original do projeto.
- **[Repositório](https://github.com/italostatonato/stock-screener-automation)** e **[wiki](https://github.com/italostatonato/stock-screener-automation/wiki)**: código do screener e documentação.

O site foi criado em 29/09/2026 como réplica da página publicada no GitHub Pages.
Preserva a identidade visual e as nove abas: Introdução, Visão geral, Carteira
Híbrida, Modelos ML, Recorrentes, Ações, FIIs, Indicadores e Score e Info.
Inclui rankings, gráficos, guia para iniciantes e simulador de aporte.
As premissas de cálculos e simulações estão no
[guia do dashboard](https://github.com/italostatonato/stock-screener-automation/blob/main/docs/DASHBOARD.md).

## Atualização dos dados

A coleta continua no pipeline Python e no GitHub Actions deste repositório:
**segunda-feira às 08h de Brasília** (`America/Sao_Paulo`), ou por execução manual.
O site no Sites não mantém outra rotina de coleta nem recalcula o ranking.

1. Ao abrir a página, o navegador consulta o
   [índice de snapshots do GitHub Pages](https://italostatonato.github.io/stock-screener-automation/data/index.json).
2. Carrega o snapshot mais recente disponível e consulta os demais conforme
   a navegação e os cálculos do dashboard.
3. Se o carregamento inicial falhar, tenta os snapshots incluídos na última
   publicação do site. A tela informa que está exibindo a última cópia disponível
   e conserva a data real do snapshot apresentado.

Os dados não são cotações em tempo real. Uma página já aberta não passa a
consultar continuamente novas coletas; recarregue para buscar uma nova publicação.
A cópia de contingência só muda quando os arquivos correspondentes são atualizados
e o site é publicado novamente. Atualizações de HTML, CSS e scripts do GitHub
Pages também precisam ser incorporadas e publicadas separadamente no Sites.

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

Para alterar a interface ou o contador, abra o projeto existente no Sites,
preserve seu banco, valide a mudança e publique uma nova versão. Publicar
`docs/` pelo workflow do GitHub Pages não publica o projeto do Sites.
As permissões de acesso são administradas no Sites; o modo público foi confirmado
na data de verificação deste guia.

Se os dados parecerem antigos, confira a data do snapshot, o aviso de cópia
incluída e a conclusão do workflow original. Se o contador estiver indisponível,
consulte os logs do Worker e a disponibilidade da tabela e do vínculo `DB`.
Para conferir o total sem gerar uma visita de teste, use
[a consulta do contador](https://radar-semanal-italo.italo-st.chatgpt.site/api/visitors).

O projeto tem finalidade educacional e analítica. O simulador não executa compras,
e os resultados não constituem recomendação de investimento.
