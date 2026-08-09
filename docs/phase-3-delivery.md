# Entrega — Fase 3: execução controlada pelo Android

## Resultado entregue

A Fase 3 conclui o primeiro fluxo de ação ponta a ponta do Android Stream Deck:

1. o Android pareado e autenticado recebe o `profile_snapshot`;
2. valida o perfil antes de renderizar a grade da página ativa;
3. exibe a grade configurada por `rows × columns` — o perfil de desenvolvimento
   usa 3 colunas × 5 linhas;
4. ao tocar um botão, envia somente `request_id`, IDs de perfil/página/botão e a
   revisão recebida;
5. o servidor valida a sessão, revisão e botão, encaminhando a ação somente ao
   registry fechado;
6. o Android mostra `Executando`, `Concluído` ou `Erro` no botão associado à
   requisição.

O cliente não recebe nem constrói hotkeys, comandos, caminhos, shell ou payloads
livres. O tipo de ação continua definido apenas no perfil validado pelo servidor.

## Implementação

### Android

- `ProfileSnapshotParser` valida envelope, versão de protocolo, página ativa,
  dimensões, IDs e posições únicas, limites da grade e cores hexadecimais antes
  de a interface usar os dados.
- `GridLayout` gera todas as células da página em ordem determinística, inclusive
  células vazias.
- `StreamDeckGrid` usa os títulos, cores e ícones/símbolos declarados pelo
  perfil; desabilita o botão enquanto uma solicitação está pendente.
- `ProtocolMessages.press` serializa apenas os identificadores e a revisão.
- `ack/completed`, `ack/rejected` e `error` atualizam o botão correto pela
  associação temporária entre `request_id` e `button_id`.
- O ciclo de vida do WebSocket preserva a nova conexão durante recomposição; ao
  substituir ou fechar a tela, somente a instância anterior é encerrada.

### Servidor

- O registry continua fechado e somente `hotkey` está habilitada nesta versão.
- A hotkey Windows usa mapa interno de virtual keys e `keybd_event`, sem shell ou
  subprocesso.
- A fábrica `create_app` aceita injeção explícita de executor para testes. A
  execução padrão de produção permanece `WindowsHotkeyAdapter`.
- `server/scripts/phase3_e2e_server.py` existe somente para o smoke: injeta um
  adaptador gravador, permitindo provar Android → WebSocket → registry → ACK sem
  emitir uma hotkey real na área de trabalho durante testes automatizados.

As ações `key`, `media`, `text`, `url` e `application` seguem rejeitadas com
`ack/rejected` até receberem adaptadores fechados e testes próprios.

## Testes e evidências executadas

### TDD

Foram criados e observados como falhos antes da implementação os testes de:

- parser de `profile_snapshot` inexistente;
- serialização de `press` inexistente;
- composição da grade inexistente;
- parser de `ack` inexistente;
- executor WebSocket não injetável e falhas de ação sem resposta sanitizada;
- rejeição/erro de ação no fluxo instrumentado.

Depois das implementações e correções, os gates verificados foram:

```text
Servidor: pytest -q                         175 passed
Servidor: Ruff, compileall e uv lock --check aprovados
Compartilhado: JSON do perfil 3×5 validado
Android: testDebugUnitTest aprovado
Android: assembleDebug aprovado
Android: assembleAndroidTest aprovado
Android: connectedDebugAndroidTest aprovado no Pixel_8 / emulator-5554
```

O smoke UiAutomator comprovou pareamento HTTP, WebSocket autenticado, snapshot
3×5, renderização dos três botões configurados, `ack/completed` da hotkey,
`ack/rejected` de mídia e reconexão com a credencial cifrada. O log controlado
registrou a chamada `ctrl+shift+s`; nenhum atalho real foi emitido no desktop
nesse smoke.

## Operação manual

1. Inicie o servidor normalmente, com bind remoto somente sob código de
   pareamento e autenticação:

   ```bash
   export STREAMDECK_HOST=0.0.0.0
   export STREAMDECK_PORT=8765
   export STREAMDECK_PAIRING_CODE='CODIGO_FORA_DO_GIT'
   cd E:/projetos/android-streamdeck/server
   env -u PYTHONPATH -u VIRTUAL_ENV uv run --locked --no-sync streamdeck-server
   ```

2. No emulador, use `http://10.0.2.2:8765`. Em aparelho físico, use o IP privado
   do Windows na mesma rede, com a porta permitida somente no perfil privado do
   firewall.
3. Pareie pelo código efêmero. O primeiro botão do perfil de desenvolvimento
   envia `Ctrl+Shift+S` quando pressionado; tenha certeza de que essa é uma ação
   desejada na janela Windows ativa.
4. Abra `http://127.0.0.1:8765/health` no host para verificar o servidor local.

## Limites assumidos

- O smoke do emulador valida o fluxo com adaptador gravador para evitar efeitos
  colaterais no desktop; a emissão real por `keybd_event` foi validada por testes
  unitários com emissor controlado.
- O Galaxy A10 não foi conectado; a validação efetiva é do `Pixel_8`.
- HTTP/WS em LAN, TLS/mTLS, rotação administrativa de dispositivos e demais
  adaptadores de ação pertencem às fases posteriores.
- O APK release é compilável, porém não assinado para distribuição.
