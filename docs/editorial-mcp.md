# Edição dirigida por MCP

Este fluxo permite selecionar e reorganizar falas por uma sessão do Codex. O SupoClip prepara a mídia, mantém uma montagem editável e renderiza o vídeo localmente. O fluxo automático de clipes continua disponível.

## Conexão local

O iniciador `mcp/local.py` lê somente a configuração necessária de um arquivo privado. Ele usa uma chave local do SupoClip ou a autenticação assinada documentada para self-host. Ele não ativa autenticação sem assinatura e não carrega o token do OpenScreen como credencial do SupoClip.

Exemplo de registro, usando o Python do ambiente exclusivo do MCP:

```powershell
codex mcp add supoclip-local -- <python-do-ambiente-mcp> <checkout>/mcp/local.py <configuracao-privada.env>
```

O arquivo privado precisa de `SUPOCLIP_API_URL=http://127.0.0.1:8000` e de uma das opções:

- `SUPOCLIP_MCP_TOKEN`: chave de API da conta local, sem relação com chaves de provedores pagos.
- `SUPOCLIP_USER_ID` e `BACKEND_AUTH_SECRET`: autenticação assinada da instalação local.

Não coloque os valores das credenciais no prompt, no código ou no registro do MCP. Para novos ambientes, instale as dependências de `mcp/uv.lock` com `uv sync --frozen`. O iniciador precisa de `mcp[cli]`, `httpx` e suas dependências. A configuração STDIO é compartilhada pelos clientes locais compatíveis do Codex; sessões que já estavam abertas podem precisar reconectar o servidor. [Documentação oficial do Codex](https://learn.chatgpt.com/docs/extend/mcp).

Configure `startup_timeout_sec = 60` e `tool_timeout_sec = 1200` no bloco desse servidor. O prazo maior permite transmitir arquivos grandes. Preparação e renderização retornam IDs; acompanhe o estado sem manter uma chamada de geração bloqueada.

## Fluxo para uma produção

1. Na sessão que conhece o Caramelo, defina a tese, o público, a conexão com o projeto e as afirmações que a comunicação pode sustentar. Leve esse briefing para a sessão de edição.
2. Na sessão de edição com o MCP `supoclip-local`, informe o caminho do vídeo e o briefing. Para uma fonte nova, prepare e transcreva uma vez. Para novos cortes do mesmo vídeo, reutilize a fonte e a transcrição existentes. A preparação dirigida recebe um arquivo local; um link do YouTube precisa ser baixado antes.
3. Peça uma proposta de narrativa com trechos contextualizados e justificativas. Depois da escolha editorial, execute a montagem. Cortes internos e reordenação devem preservar o sentido original.
4. Abra a seção **Montagens** na página inicial ou na [biblioteca](http://localhost:3107/list). Ela mostra título, duração e revisão. Use **Retomar montagem** para revisar o vídeo e seus ajustes. A busca da biblioteca também filtra os títulos das montagens. Use **Atualizar montagens** se a sessão de edição acabou de criar outra montagem.
5. Peça ajustes à sessão de edição ou faça os ajustes disponíveis na interface. A sessão precisa reler a revisão atual para preservar o trabalho manual. Depois de mudar a montagem, use **Exportar versão atual** e confira essa exportação.
6. Revise legendas, nomes, enquadramento e emendas pelo áudio. Baixe o MP4 aprovado. A biblioteca conserva a montagem para retomadas; o arquivo exportado identifica uma revisão específica.

O formulário de geração da página inicial continua criando cortes pelo fluxo automático. O fluxo acima usa a montagem dirigida pelas suas instruções. A câmera de comentário sobreposta e o acompanhamento automático de quem fala ainda exigem outra etapa.

## Ferramentas do uso diário

1. Use `supoclip_list_edits` para encontrar uma montagem existente pelo título. Use `supoclip_list_sources` para reaproveitar uma fonte já preparada.
2. Para uma gravação nova, use `supoclip_prepare_source` com o caminho absoluto do arquivo neste computador. O Whisper local transcreve a fala. A ferramenta não solicita seleção automática ao Ollama.
3. Leia `supoclip_get_source` até a fonte estar pronta. Leia a transcrição por `supoclip_get_transcript` ou `supoclip_get_transcript_words`, seguindo `next_offset` até o fim das janelas necessárias.
4. Use `supoclip_create_edit` para uma montagem nova, ou `supoclip_get_edit` para retomar a atual. Leia `supoclip_get_edit_schema` antes de construir operações.
5. Crie um checkpoint. Aplique operações com a revisão lida e um `request_id` único. Após timeout incerto, repita o mesmo ID e o mesmo conteúdo. Após conflito, releia e reconcilie os ajustes manuais.
6. Exporte uma revisão explícita com `supoclip_export_edit`. Consulte `supoclip_get_edit_export`. Confira o mapa, as imagens e o arquivo antes de entregar.

A página de revisão fica em `http://localhost:3107/editorial/<edit_id>`. Ela exige a sessão da mesma conta que criou a montagem. Permite conferir a exportação, mover trechos, ajustar seus limites e recuperar falas removidas por cortes internos. O vídeo de prévia corresponde à revisão exportada; alterações posteriores precisam de nova exportação.

Fontes preparadas e transcrições são privadas por usuário. Uma transcrição importada exige o SHA256 da mídia exata e fica imutável, para manter os IDs. O teste de reprodução usa essa importação para conservar os tempos do OpenScreen. Gravações novas usam Whisper local por padrão.

Se usar um script no Windows para importar uma transcrição JSON, leia o arquivo com `encoding="utf-8"`. Compare o texto retornado pelo MCP com a referência antes de exportar. A codificação padrão de alguns ambientes Python no Windows pode corromper acentos sem produzir erro de leitura.

## Contrato editorial

Os limites dos clipes e dos cortes internos usam segundos fracionários do vídeo original. A régua soma os clipes antes dos cortes. O tempo efetivo de reprodução desconta a união dos cortes por ocorrência. Uma passagem repetida em dois clipes tem cortes e correções independentes.

Um lote tem de uma a cem operações tipadas e é atômico. Se uma operação for inválida, nenhuma alteração do lote é salva. Os cortes permanecem ligados ao clipe ao mover ou dividir trechos. Uma mudança de limite que deixe um corte fora do clipe é rejeitada; ajuste o marcador explicitamente, sem deslocar todos os cortes pela mesma diferença de tempo.

`set_word_text` corrige apenas o texto da legenda. `remove_words` remove áudio pelos tempos das palavras daquela ocorrência. Os tempos são aproximados: use contexto e pausas para decidir as bordas e ouça as emendas. Não remova áudio para corrigir uma suspeita de erro da transcrição.

A montagem dirigida não executa reparação automática de frases, teaser, seleção por viralização ou limite automático de cortes curtos. A duração é resultado dos trechos aprovados. O enquadramento explícito pode variar por clipe; identificar automaticamente quem está falando ainda não faz parte desta entrega.

## Prompt para outra sessão

```text
Use o MCP supoclip-local para editar conforme o objetivo e as preferências desta conversa.
Encontre a montagem por supoclip_list_edits e leia o documento atual antes de editar.
Leia a transcrição com contexto suficiente e siga a paginação. Não resuma páginas que não leu.
Priorize clareza, fidelidade e frases completas. Preserve negações, ressalvas e condições.
Reordene blocos somente quando as referências continuarem compreensíveis.
Para ajustar a duração, retire uma ideia secundária completa antes de truncar uma conclusão.
Remova hesitações por ocorrência e em contexto, sem apagar automaticamente toda repetição de uma palavra.
Crie checkpoint e use a revisão atual. Após conflito ou edição manual, releia e reconcilie.
Use os IDs reais das palavras e diferencie tempo-fonte, régua e reprodução.
Mantenha meus ajustes como a versão atual. Nunca restaure um snapshot antigo sobre eles sem considerar as mudanças.
Exporte em 9:16 com legendas em português e confira o participante enquadrado.
Confira o arquivo exportado, as imagens e o mapa da fonte.
Declare se a validação foi estrutural, visual, numérica ou por escuta. Não afirme naturalidade sem ouvir as emendas.
```

## Persistência e recuperação

As fontes e montagens ficam em `TEMP_DIR/editorial/<hash-do-usuário>/`, nos volumes locais compartilhados pela API e pelo worker. Rascunhos, checkpoints, pedidos idempotentes, transcrições e exportações permanecem fora do arquivo original.

A exportação usa uma revisão imutável. Cancelar um render não altera a montagem. Restaurar um checkpoint exige a revisão atual e cria uma revisão nova. Preserve os volumes nos reinícios e nas atualizações.
