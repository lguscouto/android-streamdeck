# Entrega — Fase 4: editor, revisões e adaptadores fechados

## Escopo da fase

A Fase 4 adiciona uma fatia vertical utilizável do editor de perfis/layouts sem
abrir uma fronteira de execução genérica:

- editor Android do perfil ativo;
- edição de nome do perfil, título da página, título/posição/cor/ícone do botão;
- formulários tipados para `hotkey`, `key`, `media`, `text`, `url` e
  `application`;
- serialização do perfil completo preservando páginas e ações não selecionadas;
- salvamento otimista com `expected_revision` e restauração local em caso de
  conflito/falha;
- auditoria de revisões sem devolver o conteúdo do snapshot;
- adaptadores fechados de `key`, `media`, `text` e `url` no servidor Windows;
- `application` permanece explicitamente rejeitada até existir um contrato
  seguro para seleção de aplicativos permitidos.

O Android continua enviando `press` somente com IDs e revisão. A ação e seus
parâmetros permanecem no snapshot validado e no registry do servidor; o cliente
não envia comandos de sistema.

## Contratos HTTP

Quando `require_auth` está ativo — obrigatório para bind remoto — as rotas de
perfil exigem os headers:

```text
Authorization: Bearer <token-do-pareamento>
X-StreamDeck-Client-Id: <client_id-do-pareamento>
```

Atualização otimista:

```text
PUT /api/v1/profiles/{profile_id}?expected_revision=N
```

O corpo é o perfil completo validado. Em sucesso, o servidor cria a revisão
`N + 1`, persiste a alteração de forma transacional, devolve o perfil resultante
e emite `profile_changed` para sessões do perfil.

Conflito:

```json
{
  "code": "PROFILE_REVISION_CONFLICT",
  "message": "Profile revision conflict",
  "retryable": true
}
```

Auditoria sanitizada:

```text
GET /api/v1/profiles/{profile_id}/audit?limit=50
```

A resposta contém somente metadados como revisão, timestamp, origem e motivo.
Não inclui `snapshot_json`, títulos, textos de ação, URLs, caminhos ou tokens.

## Modelo Android

`ProfileSnapshotParser` agora preserva todas as páginas, ordem, botões e ações
em classes tipadas:

- `StreamDeckHotkeyAction`;
- `StreamDeckKeyAction`;
- `StreamDeckMediaAction`;
- `StreamDeckTextAction`;
- `StreamDeckUrlAction`;
- `StreamDeckApplicationAction`.

`ProfileSnapshotSerializer` gera o wire profile completo para o `PUT`. O
`ProfileEditorDraft` valida campos de posição, cor, limites de texto, catálogo
de mídia, HTTPS e IDs antes de produzir um novo snapshot.

A tela Compose `ProfileEditorScreen` permite selecionar botões da página ativa,
alterar metadados e alternar entre formulários específicos por tipo. O botão
salvar aplica a versão otimista imediatamente; se a atualização HTTP falhar, o
snapshot anterior é restaurado e o draft permanece disponível para retry.

## Adaptadores Windows

| Ação | Implementação | Limite |
|---|---|---|
| `hotkey` | mapa fechado + `keybd_event` | modificadores/teclas permitidos |
| `key` | mapa fechado + down/up | somente teclas permitidas |
| `media` | mapa fechado + down/up | somente comandos multimídia permitidos |
| `text` | `SendInput` com `KEYEVENTF_UNICODE` | texto já limitado pelo schema |
| `url` | `ShellExecuteW` | somente URL `https://` validada |
| `application` | rejeição explícita | sem execução de caminho arbitrário |

Nenhum adapter usa shell, `subprocess`, concatenação de comandos ou caminho
recebido livremente do Android. Os testes usam emissores/abertura injetados; o
smoke instrumentado usa recorders para não disparar entrada real no desktop.

## Validações executadas

Gates locais aprovados:

```text
Servidor: 185 testes aprovados
Servidor: Ruff aprovado
Servidor: compileall aprovado
Servidor: uv lock --check aprovado
Android: testDebugUnitTest aprovado
Android: lintDebug aprovado
Android: compileDebugKotlin aprovado
Android: assembleAndroidTest aprovado
Android: connectedDebugAndroidTest — BUILD SUCCESSFUL, 1 teste no Pixel_8
```

O smoke instrumentado foi executado com banco temporário, código efêmero e
recorders de ação. O log confirmou pareamento, WebSocket autenticado, hotkey e
mídia controladas, `PUT ... expected_revision=1` com status 200, revisão 2,
reconexão e auditoria HTTP sanitizada. O banco temporário e a porta foram
removidos após a execução. O Galaxy A10 continua não conectado e não é coberto
por esta validação.

## Operação manual (histórica)

Este trecho conserva a validação original da Fase 4. O fluxo atual é o
pareamento temporário HTTPS/WSS descrito em [`server/README.md`](../server/README.md):
a janela/tray emite senha ou QR de uso único, sem `STREAMDECK_PAIRING_CODE`
estático, e o endpoint do emulador é `https://10.0.2.2:8765`.
